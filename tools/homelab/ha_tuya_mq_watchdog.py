#!/usr/bin/env python3
"""Watchdog: detecta falha recorrente do tuya_sharing MQ no Home Assistant
e dispara reload da integracao Tuya via API local. Expoe metricas
Prometheus via textfile collector do node_exporter.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

LOG_WINDOW_MIN = 10
# Padrões que indicam integração cloud degradada (MQ + auth + unreachable).
ERROR_NEEDLES = (
    "tuya_sharing/mq",
    "sign invalid",
    "network error:(-9999999)",
    "network error:(2001)",
    "Device Unreachable",
    "Check device key or version",
)
# Mantém alias legado
ERROR_NEEDLE = ERROR_NEEDLES[0]
HA_URL = "http://localhost:8123"
CONTAINER = "homeassistant"
STATE_FILE = "/var/lib/ha-tuya-mq-watchdog/state.json"
METRICS_FILE = "/var/lib/prometheus/node-exporter/ha_tuya_mq_watchdog.prom"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("ha-tuya-mq-watchdog")


def docker_exec(cmd: list[str]) -> str:
    res = subprocess.run(
        ["docker", "exec", CONTAINER, *cmd],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return res.stdout


def recent_log_has_error() -> int:
    res = subprocess.run(
        ["docker", "logs", f"--since={LOG_WINDOW_MIN}m", CONTAINER],
        capture_output=True, text=True, timeout=60, check=False,
    )
    blob = (res.stdout or "") + (res.stderr or "")
    # Conta ocorrências de qualquer padrão (não só MQ).
    return sum(blob.count(n) for n in ERROR_NEEDLES)


def get_tuya_entry_id() -> str | None:
    out = docker_exec([
        "python3", "-c",
        "import json;d=json.load(open('/config/.storage/core.config_entries'));"
        "e=[x for x in d['data']['entries'] if x['domain']=='tuya'];"
        "print(e[0]['entry_id'] if e else '')",
    ])
    eid = out.strip()
    return eid or None


def get_jwt() -> str | None:
    out = docker_exec([
        "python3", "-c",
        "import json,jwt,time;"
        "a=json.load(open('/config/.storage/auth'));"
        "tok=next((t for t in a['data']['refresh_tokens'] "
        "if t.get('token_type')=='long_lived_access_token'), None);"
        "print(jwt.encode({'iss':tok['id'],'iat':int(time.time()),"
        "'exp':int(time.time())+300}, tok['jwt_key'], algorithm='HS256') "
        "if tok else '')",
    ])
    jwt_str = out.strip()
    return jwt_str or None


def reload_entry(entry_id: str, jwt_str: str) -> bool:
    req = urllib.request.Request(
        f"{HA_URL}/api/config/config_entries/entry/{entry_id}/reload",
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt_str}",
            "Content-Type": "application/json",
        },
        data=b"{}",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            log.info("reload HTTP %s", resp.status)
            return 200 <= resp.status < 300
    except Exception as ex:
        log.error("reload failed: %s", ex)
        return False


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as ex:
        log.warning("state load failed: %s", ex)
        return {}


def save_state(state: dict) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=".state.", dir=os.path.dirname(STATE_FILE)
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, STATE_FILE)
    except Exception as ex:
        log.warning("state save failed: %s", ex)


def write_metrics(state: dict, errors: int) -> None:
    lines = [
        "# HELP ha_tuya_mq_watchdog_runs_total Total runs of the watchdog",
        "# TYPE ha_tuya_mq_watchdog_runs_total counter",
        f"ha_tuya_mq_watchdog_runs_total {state.get('runs_total', 0)}",
        "# HELP ha_tuya_mq_watchdog_errors_detected Last run: count of "
        "tuya_sharing/mq matches in log window",
        "# TYPE ha_tuya_mq_watchdog_errors_detected gauge",
        f"ha_tuya_mq_watchdog_errors_detected {errors}",
        "# HELP ha_tuya_mq_watchdog_reloads_total Total successful reloads "
        "triggered",
        "# TYPE ha_tuya_mq_watchdog_reloads_total counter",
        f"ha_tuya_mq_watchdog_reloads_total {state.get('reloads_total', 0)}",
        "# HELP ha_tuya_mq_watchdog_last_run_timestamp Unix time of last run",
        "# TYPE ha_tuya_mq_watchdog_last_run_timestamp gauge",
        f"ha_tuya_mq_watchdog_last_run_timestamp {int(time.time())}",
        "",
    ]
    blob = "\n".join(lines)
    try:
        target_dir = os.path.dirname(METRICS_FILE)
        if not os.path.isdir(target_dir):
            log.info("textfile dir not present: %s", target_dir)
            return
        fd, tmp = tempfile.mkstemp(prefix=".ha_tuya_mq_watchdog.",
                                   dir=target_dir)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(blob)
        os.chmod(tmp, 0o644)
        os.replace(tmp, METRICS_FILE)
    except Exception as ex:
        log.warning("metrics write failed: %s", ex)


def main() -> int:
    state = load_state()
    state["runs_total"] = int(state.get("runs_total", 0)) + 1
    exit_code = 0
    errors = 0
    try:
        errors = recent_log_has_error()
        if errors == 0:
            log.info("ok: no tuya cloud/local error patterns in last %sm",
                     LOG_WINDOW_MIN)
        else:
            log.warning(
                "tuya error patterns found %d time(s) in last %sm — reload entry",
                errors, LOG_WINDOW_MIN,
            )
            entry_id = get_tuya_entry_id()
            if not entry_id:
                log.error("tuya entry_id not found; aborting")
                exit_code = 2
            else:
                jwt_str = get_jwt()
                if not jwt_str:
                    log.error("no long-lived token available; aborting")
                    exit_code = 3
                else:
                    log.info("reloading tuya entry %s", entry_id)
                    if reload_entry(entry_id, jwt_str):
                        state["reloads_total"] = int(
                            state.get("reloads_total", 0)
                        ) + 1
                        time.sleep(15)
                        after = recent_log_has_error()
                        log.info(
                            "post-reload error count in window: %d", after
                        )
                    else:
                        exit_code = 4
    finally:
        try:
            write_metrics(state, errors)
            save_state(state)
        except Exception as ex:
            log.warning("metrics/state finalize failed: %s", ex)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
