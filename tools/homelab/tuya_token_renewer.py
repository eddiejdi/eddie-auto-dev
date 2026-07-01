#!/usr/bin/env python3
"""Monitor da integração Tuya no Home Assistant.

O Home Assistant renova o token Tuya automaticamente. Este script monitora
falhas de autenticação e disponibilidade real das entidades da config entry,
evitando falso positivo baseado apenas em substring no `entity_id`.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tuya-monitor")

SECRETS_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
API_KEY = os.environ["SECRETS_AGENT_API_KEY"]
CONTAINER = os.environ.get("HA_CONTAINER", "homeassistant")

IGNORED_AVAILABILITY_DOMAINS = {"scene"}
HA_API_RETRIES = 6
HA_API_RETRY_SLEEP_S = 10


def get_secret(name: str, field: str = "password", required: bool = True) -> str:
    req = urllib.request.Request(
        f"{SECRETS_URL}/secrets/{name}?field={field}",
        headers={"X-API-KEY": API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp).get("value", "")
    except Exception as exc:
        if required:
            raise
        log.warning("Secret não encontrado: %s/%s (%s)", name, field, exc)
        return ""


def docker_py(script: str) -> dict:
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = proc.stdout.strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "reason": "docker_exec_failed",
            "stderr": (proc.stderr or "")[-400:],
        }
    if not stdout:
        return {"ok": False, "reason": "empty_docker_response"}
    return json.loads(stdout)


def send_telegram(msg: str, bot_token: str, chat_id: str) -> bool:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": msg}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp).get("ok", False)
    except Exception as exc:
        log.warning("Telegram falhou: %s", exc)
        return False


def get_container_state() -> dict[str, str]:
    proc = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}",
            CONTAINER,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return {"status": "unknown", "health": "unknown"}

    state = {"status": "unknown", "health": "unknown"}
    for part in proc.stdout.strip().split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        state[key] = value or "unknown"
    return state


def load_entry_snapshot(entry_id: str) -> dict:
    return docker_py(
        f"""
import json, time
with open('/config/.storage/core.config_entries') as f:
    config_entries = json.load(f)
with open('/config/.storage/core.entity_registry') as f:
    entity_registry = json.load(f)
entry = next((e for e in config_entries['data']['entries'] if e['entry_id'] == {json.dumps(entry_id)}), None)
if not entry:
    print(json.dumps({{'ok': False, 'reason': 'entry_not_found'}}))
    raise SystemExit
token_info = entry['data']['token_info']
now_ms = int(time.time() * 1000)
expire_abs = token_info['t'] + token_info['expire_time'] * 1000
entities = [
    {{
        'entity_id': entity.get('entity_id'),
        'disabled_by': entity.get('disabled_by'),
        'platform': entity.get('platform'),
    }}
    for entity in entity_registry['data']['entities']
    if entity.get('config_entry_id') == {json.dumps(entry_id)}
]
print(json.dumps({{
    'ok': True,
    'remaining_min': (expire_abs - now_ms) / 60000,
    'entity_ids': entities,
}}))
"""
    )


def evaluate_ha_entities(ha_url: str, ha_token: str, entry_entities: list[dict]) -> dict:
    req = urllib.request.Request(
        f"{ha_url.rstrip('/')}/api/states",
        headers={"Authorization": f"Bearer {ha_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        states = json.load(resp)

    state_map = {state["entity_id"]: state for state in states}

    total_registry = len(entry_entities)
    monitored = []
    ignored = []
    disabled = 0
    problems = []

    for entity in entry_entities:
        entity_id = entity.get("entity_id") or ""
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        if entity.get("disabled_by"):
            disabled += 1
            continue
        if domain in IGNORED_AVAILABILITY_DOMAINS:
            ignored.append(entity_id)
            continue

        monitored.append(entity_id)
        state_obj = state_map.get(entity_id)
        state = state_obj.get("state") if state_obj else "MISSING"
        if state in {"unavailable", "unknown", "MISSING"}:
            problems.append({"entity_id": entity_id, "state": state})

    available = len(monitored) - len(problems)
    status = (
        f"{available}/{len(monitored)} entidades ativas"
        f" | {disabled} desabilitadas"
        f" | {len(ignored)} scenes ignoradas"
    )

    return {
        "registry_total": total_registry,
        "monitored_total": len(monitored),
        "available": available,
        "disabled": disabled,
        "ignored": len(ignored),
        "problems": problems,
        "status": status,
    }


def format_problem_list(problems: list[dict], limit: int = 5) -> str:
    if not problems:
        return ""
    head = ", ".join(
        f"{item['entity_id']}={item['state']}" for item in problems[:limit]
    )
    extra = len(problems) - limit
    if extra > 0:
        head += f", +{extra} mais"
    return head


def main() -> int:
    entry_id = get_secret("eddie/tuya_ha/entry_id")
    ha_url = get_secret("eddie/tuya_ha/ha_url")
    ha_token = get_secret("authentik/eddie/home_assistant_token")
    tg_token = get_secret(
        "authentik/eddie/telegram_bot_token", field="token", required=False
    )
    tg_chat_id = get_secret(
        "authentik/eddie/telegram_chat_id", field="chat_id", required=False
    )

    log.info("Verificando integração Tuya entry=%s", entry_id)

    result = load_entry_snapshot(entry_id)
    if not result.get("ok"):
        reason = result.get("reason", "erro_desconhecido")
        log.error("Integração Tuya com falha: %s", reason)
        if tg_token and tg_chat_id:
            send_telegram(
                f"⚠️ Tuya com falha no Home Assistant\n"
                f"Motivo: {reason}\n"
                f"Abra: {ha_url}/config/integrations",
                tg_token,
                tg_chat_id,
            )
        return 2

    ha_summary = None
    last_exc: Exception | None = None
    for attempt in range(1, HA_API_RETRIES + 1):
        try:
            ha_summary = evaluate_ha_entities(ha_url, ha_token, result["entity_ids"])
            break
        except Exception as exc:
            last_exc = exc
            state = get_container_state()
            is_conn_refused = isinstance(exc, urllib.error.URLError) and "Connection refused" in str(exc)
            if is_conn_refused and attempt < HA_API_RETRIES:
                log.warning(
                    "HA indisponível na tentativa %s/%s (%s); container=%s/%s; aguardando %ss",
                    attempt,
                    HA_API_RETRIES,
                    exc,
                    state.get("status", "unknown"),
                    state.get("health", "unknown"),
                    HA_API_RETRY_SLEEP_S,
                )
                time.sleep(HA_API_RETRY_SLEEP_S)
                continue

            if is_conn_refused and state.get("health") == "starting":
                log.warning(
                    "HA ainda está subindo; suprimindo alerta transitório (%s)",
                    exc,
                )
                return 0
            break

    if ha_summary is None:
        reason = f"ha_api_error: {last_exc}"
        log.error("Falha ao consultar Home Assistant: %s", last_exc)
        if tg_token and tg_chat_id:
            send_telegram(
                f"⚠️ Tuya monitor sem leitura do HA\n"
                f"Motivo: {reason[:180]}\n"
                f"Abra: {ha_url}/config/integrations",
                tg_token,
                tg_chat_id,
            )
        return 2

    remaining = result.get("remaining_min", 0)
    log.info("Tuya token expira em %.0f min | HA: %s", remaining, ha_summary["status"])

    if ha_summary["available"] == 0 and ha_summary["monitored_total"] > 0:
        problem_list = format_problem_list(ha_summary["problems"])
        log.error("Entidades Tuya indisponíveis: %s", ha_summary["status"])
        if tg_token and tg_chat_id:
            send_telegram(
                f"⚠️ Tuya sem entidades ativas no Home Assistant\n"
                f"HA: {ha_summary['status']}\n"
                f"{problem_list}\n"
                f"Abra: {ha_url}/config/integrations",
                tg_token,
                tg_chat_id,
            )
        return 2

    if remaining < 10:
        log.warning("Token expira em menos de 10 minutos!")
        if tg_token and tg_chat_id:
            send_telegram(
                f"⏰ Tuya perto de renovar no Home Assistant\n"
                f"Token expira em ~{remaining:.0f} min.\n"
                f"HA: {ha_summary['status']}\n"
                f"O HA costuma renovar sozinho. Reautentique só se aparecer erro de auth em:\n"
                f"{ha_url}/config/integrations",
                tg_token,
                tg_chat_id,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
