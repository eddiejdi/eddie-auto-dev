#!/usr/bin/env python3
"""
Smart IR selfheal: detecta quando o Smart IR NovaDigital está travado
e toma ação (reload integration -> restart HA) com notificação Telegram.

Proteções importantes:
- usa o endpoint correto de reload de config entry do Home Assistant;
- não reinicia o Home Assistant quando o dispositivo está offline na LAN;
- expõe modo --once para diagnóstico manual.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("smart-ir-selfheal")

SECRETS_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
API_KEY = os.environ["SECRETS_AGENT_API_KEY"]
HA_URL = os.environ.get("SMART_IR_HA_URL", "http://127.0.0.1:8123")
REMOTE_ENTITY = os.environ.get("SMART_IR_REMOTE_ENTITY", "remote.smart_ir_novadigital")
ENTRY_ID = os.environ.get("SMART_IR_ENTRY_ID", "01KTFMCQY9BJ2B5FZR9JXC639F")
DEVICE_IP = os.environ.get("SMART_IR_DEVICE_IP", "192.168.15.71")
DEVICE_PORT = int(os.environ.get("SMART_IR_DEVICE_PORT", "6668"))
POLL_INTERVAL = int(os.environ.get("SMART_IR_POLL_INTERVAL", "60"))
FAIL_THRESHOLD = int(os.environ.get("SMART_IR_FAIL_THRESHOLD", "3"))
RELOAD_MAX = int(os.environ.get("SMART_IR_RELOAD_MAX", "2"))
ACTION_COOLDOWN = int(os.environ.get("SMART_IR_ACTION_COOLDOWN", "300"))
OFFLINE_NOTIFY_INTERVAL = int(os.environ.get("SMART_IR_OFFLINE_NOTIFY_INTERVAL", "3600"))


def get_secret(name: str, field: str = "password") -> str:
    req = urllib.request.Request(
        f"{SECRETS_URL}/secrets/{name}?field={field}",
        headers={"X-API-KEY": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)["value"]


def ha_get(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def ha_reload_integration(token: str) -> bool:
    """Reload da config entry do tuya_local."""
    req = urllib.request.Request(
        f"{HA_URL}/api/config/config_entries/entry/{ENTRY_ID}/reload",
        data=b"{}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            log.info("Reload HTTP %s para entry %s", response.status, ENTRY_ID)
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        log.warning("Reload falhou: HTTP %s %s | %s", exc.code, exc.reason, detail.strip())
        return False
    except Exception as exc:
        log.warning("Reload falhou: %s", exc)
        return False


def restart_ha() -> bool:
    """Restart do container Docker do Home Assistant."""
    try:
        subprocess.run(
            ["docker", "restart", "homeassistant"],
            timeout=60,
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("Container homeassistant reiniciado")
        time.sleep(30)
        return True
    except Exception as exc:
        log.error("Falha ao reiniciar container: %s", exc)
        return False


def send_telegram(token_tg: str, chat_id: str, msg: str) -> None:
    if not token_tg:
        return
    try:
        body = json.dumps(
            {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
        ).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token_tg}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as exc:
        log.warning("Telegram falhou: %s", exc)


def tcp_port_open(host: str, port: int, timeout_s: float = 3.0) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_s)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def check_device_status(token: str) -> dict[str, object]:
    """Retorna estado do remote no HA e conectividade direta com o device."""
    state_value = "error"
    state_ok = False
    try:
        state = ha_get(f"/api/states/{REMOTE_ENTITY}", token)
        state_value = state.get("state", "unknown")
        state_ok = state_value not in ("unavailable", "unknown")
    except Exception as exc:
        log.warning("Erro ao consultar estado do remote: %s", exc)

    tcp_ok = tcp_port_open(DEVICE_IP, DEVICE_PORT)
    responsive = state_ok and tcp_ok
    return {
        "ha_state": state_value,
        "state_ok": state_ok,
        "tcp_ok": tcp_ok,
        "responsive": responsive,
    }


def run_iteration(
    token: str,
    tg_token: str,
    tg_chat: str,
    fail_count: int,
    reload_count: int,
    last_action: float,
    last_offline_notify: float,
) -> tuple[str, int, int, float, float, str]:
    """
    Executa uma iteração.

    Retorna:
    - status textual
    - fail_count
    - reload_count
    - last_action
    - last_offline_notify
    - possivel novo token
    """
    status = check_device_status(token)
    ha_state = str(status["ha_state"])
    tcp_ok = bool(status["tcp_ok"])
    responsive = bool(status["responsive"])

    if responsive:
        if fail_count > 0:
            log.info("Smart IR recuperado após %d falhas", fail_count)
        return "ok", 0, 0, last_action, 0.0, token

    fail_count += 1
    log.warning(
        "Smart IR não responde (falha %d/%d) | ha_state=%s | tcp_%s=%s",
        fail_count,
        FAIL_THRESHOLD,
        ha_state,
        DEVICE_PORT,
        "ok" if tcp_ok else "down",
    )

    if fail_count < FAIL_THRESHOLD:
        return "failing", fail_count, reload_count, last_action, last_offline_notify, token

    now = time.time()

    # Se o device está realmente fora da LAN, não adianta recarregar integração
    # nem reiniciar o Home Assistant.
    if not tcp_ok:
        if now - last_offline_notify >= OFFLINE_NOTIFY_INTERVAL:
            send_telegram(
                tg_token,
                tg_chat,
                "⚠️ <b>Smart IR selfheal</b>\n"
                f"Device offline na rede ({DEVICE_IP}:{DEVICE_PORT}).\n"
                "Reload da integração e restart do Home Assistant foram suprimidos.",
            )
            last_offline_notify = now
        log.info("Device offline na LAN; ações de reload/restart foram suprimidas")
        return "device_offline", fail_count, 0, last_action, last_offline_notify, token

    if now - last_action < ACTION_COOLDOWN:
        log.info("Anti-flap: ação recente, aguardando")
        return "cooldown", fail_count, reload_count, last_action, last_offline_notify, token

    if reload_count < RELOAD_MAX:
        attempt = reload_count + 1
        log.info("Ação: reload integration tuya_local (tentativa %d)", attempt)
        ok = ha_reload_integration(token)
        reload_count = attempt
        last_action = now
        if ok:
            send_telegram(
                tg_token,
                tg_chat,
                "⚠️ <b>Smart IR selfheal</b>\n"
                f"Device não respondia ({fail_count} falhas).\n"
                f"Ação: reload integration (#{reload_count})",
            )
            return "reload_ok", 0, reload_count, last_action, last_offline_notify, token
        return "reload_failed", fail_count, reload_count, last_action, last_offline_notify, token

    log.warning("Reload não resolveu. Reiniciando HA container...")
    send_telegram(
        tg_token,
        tg_chat,
        "🔴 <b>Smart IR selfheal</b>\n"
        "Reload não resolveu. Reiniciando Home Assistant...",
    )
    restarted = restart_ha()
    last_action = time.time()
    reload_count = 0
    fail_count = 0
    if restarted:
        token = get_secret("authentik/eddie/home_assistant_token")
        send_telegram(tg_token, tg_chat, "✅ <b>Smart IR selfheal</b>\nHA reiniciado.")
        return "restart_ok", fail_count, reload_count, last_action, last_offline_notify, token
    return "restart_failed", fail_count, reload_count, last_action, last_offline_notify, token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart IR NovaDigital selfheal")
    parser.add_argument(
        "--once",
        action="store_true",
        help="executa uma única iteração e sai",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log.info("Smart IR selfheal iniciado | entity=%s | poll=%ss", REMOTE_ENTITY, POLL_INTERVAL)
    token = get_secret("authentik/eddie/home_assistant_token")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "948686300")
    if not tg_token:
        log.warning("TELEGRAM_BOT_TOKEN não definido — notificações desabilitadas")

    fail_count = 0
    reload_count = 0
    last_action = 0.0
    last_offline_notify = 0.0

    while True:
        try:
            status, fail_count, reload_count, last_action, last_offline_notify, token = run_iteration(
                token=token,
                tg_token=tg_token,
                tg_chat=tg_chat,
                fail_count=fail_count,
                reload_count=reload_count,
                last_action=last_action,
                last_offline_notify=last_offline_notify,
            )
            if args.once:
                log.info("Execução única concluída com status=%s", status)
                return 0
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                log.warning("Token expirado, renovando...")
                token = get_secret("authentik/eddie/home_assistant_token")
            else:
                log.warning("HTTP %s: %s", exc.code, exc.reason)
        except Exception as exc:
            log.warning("Erro inesperado: %s", exc)

        if args.once:
            return 1
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
