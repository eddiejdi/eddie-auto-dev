#!/usr/bin/env python3
"""Watchdog de presença dos dispositivos IoT da allowlist.

Incidente 16–17/07/2026: 6 dispositivos Tuya/smart sumiram do WiFi e
ninguém percebeu por dias. Este watchdog observa (lease DHCP + ARP) os
MACs de /etc/iot-vpn-bypass.conf e alerta via Telegram quando um
dispositivo some por mais de ABSENT_ALERT_MIN — e quando volta.

Deliberadamente **não executa nenhuma ação corretiva**: dispositivo fora
do WiFi só se resolve fisicamente; o valor aqui é detecção rápida.
Métricas via textfile collector para o Grafana.

Credenciais do Telegram vêm do ambiente (EnvironmentFile da unit —
/etc/default/eddie-common, fonte canônica); nada é lido/gravado aqui.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("iot-presence")

BYPASS_CONF = Path(os.environ.get("BYPASS_CONF", "/etc/iot-vpn-bypass.conf"))
LEASES_FILE = Path(os.environ.get("LEASES_FILE", "/var/lib/misc/dnsmasq.leases"))
STATE_FILE = Path(os.environ.get("STATE_FILE", "/var/lib/iot-presence/state.json"))
PROM_FILE = Path(
    os.environ.get("PROM_FILE", "/var/lib/prometheus/node-exporter/iot_presence.prom")
)
ABSENT_ALERT_MIN = int(os.environ.get("ABSENT_ALERT_MIN", "30"))

MAC_RE = re.compile(r"^DEVICE_MAC=([0-9a-fA-F:]{17})\s*$", re.MULTILINE)


def parse_allowlist_macs(conf_text: str) -> list[str]:
    return sorted({m.lower() for m in MAC_RE.findall(conf_text)})


def parse_leases(leases_text: str, now: float | None = None) -> dict[str, str]:
    """MAC→IP dos leases ainda válidos (expiry no futuro)."""
    now = time.time() if now is None else now
    out: dict[str, str] = {}
    for line in leases_text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit() and float(parts[0]) > now:
            out[parts[1].lower()] = parts[2]
    return out


def parse_arp(neigh_output: str) -> dict[str, str]:
    """MAC→IP das entradas ARP não-FAILED (IPv4)."""
    out: dict[str, str] = {}
    for line in neigh_output.splitlines():
        if "FAILED" in line or "lladdr" not in line:
            continue
        parts = line.split()
        try:
            ip = parts[0]
            mac = parts[parts.index("lladdr") + 1].lower()
        except (ValueError, IndexError):
            continue
        if ":" in ip:  # ignora IPv6 link-local
            continue
        out[mac] = ip
    return out


def evaluate_presence(
    macs: list[str],
    leases: dict[str, str],
    arp: dict[str, str],
    prev_state: dict,
    now: float | None = None,
    absent_alert_s: int = ABSENT_ALERT_MIN * 60,
) -> tuple[dict, list[str]]:
    """Retorna (novo estado, lista de mensagens de alerta).

    Alerta uma única vez por transição: ausente > absent_alert_s, e no retorno.
    """
    now = time.time() if now is None else now
    state = {"devices": {}, "alerts_sent_total": prev_state.get("alerts_sent_total", 0)}
    alerts: list[str] = []
    for mac in macs:
        ip = leases.get(mac) or arp.get(mac) or ""
        present = bool(ip)
        prev = prev_state.get("devices", {}).get(mac, {})
        absent_since = prev.get("absent_since", 0)
        alerted = prev.get("alerted", False)

        if present:
            if alerted:
                alerts.append(f"✅ IoT de volta: {mac} ({ip})")
            absent_since = 0
            alerted = False
        else:
            if absent_since == 0:
                absent_since = now
            if not alerted and now - absent_since >= absent_alert_s:
                mins = int((now - absent_since) / 60)
                last_ip = prev.get("last_ip", "?")
                alerts.append(
                    f"⚠️ IoT fora do WiFi há {mins} min: {mac} (último IP {last_ip})"
                )
                alerted = True

        state["devices"][mac] = {
            "present": present,
            "last_ip": ip or prev.get("last_ip", ""),
            "absent_since": absent_since,
            "alerted": alerted,
        }
    return state, alerts


def render_prom(state: dict) -> str:
    lines = [
        "# HELP iot_device_present Dispositivo da allowlist visível (lease DHCP ou ARP)",
        "# TYPE iot_device_present gauge",
    ]
    for mac, info in sorted(state["devices"].items()):
        ip = info.get("last_ip") or "unknown"
        lines.append(
            f'iot_device_present{{mac="{mac}",ip="{ip}"}} {1 if info["present"] else 0}'
        )
    present = sum(1 for i in state["devices"].values() if i["present"])
    lines += [
        "# HELP iot_devices_present_count Dispositivos presentes / total da allowlist",
        "# TYPE iot_devices_present_count gauge",
        f"iot_devices_present_count {present}",
        "# TYPE iot_devices_total gauge",
        f"iot_devices_total {len(state['devices'])}",
        "# TYPE iot_presence_alerts_sent_total counter",
        f"iot_presence_alerts_sent_total {state['alerts_sent_total']}",
        "# TYPE iot_presence_last_run_timestamp gauge",
        f"iot_presence_last_run_timestamp {int(time.time())}",
    ]
    return "\n".join(lines) + "\n"


def send_telegram(msgs: list[str]) -> bool:
    """Envia via bot do Telegram; credenciais só do ambiente da unit."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat or not msgs:
        return False
    body = urllib.parse.urlencode(
        {"chat_id": chat, "text": "📡 IoT presence\n" + "\n".join(msgs)}
    ).encode()
    url = "https://api.telegram.org/bot" + token + "/sendMessage"
    try:
        urllib.request.urlopen(url, body, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Falha ao enviar Telegram: %s", exc)
        return False


def main() -> int:
    macs = parse_allowlist_macs(BYPASS_CONF.read_text(encoding="utf-8"))
    leases = parse_leases(LEASES_FILE.read_text(encoding="utf-8"))
    arp = parse_arp(
        subprocess.run(
            ["ip", "neigh", "show"], capture_output=True, text=True, timeout=10
        ).stdout
    )
    try:
        prev = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}

    state, alerts = evaluate_presence(macs, leases, arp, prev)
    if alerts:
        for a in alerts:
            log.info(a)
        if send_telegram(alerts):
            state["alerts_sent_total"] += len(alerts)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    PROM_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROM_FILE.with_suffix(".prom.tmp")
    tmp.write_text(render_prom(state), encoding="utf-8")
    tmp.replace(PROM_FILE)

    present = sum(1 for i in state["devices"].values() if i["present"])
    log.info("presença: %d/%d dispositivos visíveis", present, len(macs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
