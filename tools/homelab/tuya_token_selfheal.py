#!/usr/bin/env python3
"""Self-heal do token Tuya no Home Assistant.

Quando o refresh token da config entry `tuya` morre, o HA loga
"could not authenticate" e todas as entidades ficam indisponíveis
(0/N ativas). O pandaplus-bridge mantém sessão Tuya própria e persiste
token renovado em /var/lib/pandaplus-bridge/tuya_tokens_runtime.json.

Este script detecta o cenário e aplica a recuperação validada em
2026-07-06/13/16: backup de core.config_entries, injeção do token_info
do bridge na entry `tuya` e restart do container do HA. Exporta métricas
via textfile collector para o painel Grafana "Tuya Token Selfheal".
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tuya-token-selfheal")

CONTAINER = os.environ.get("HA_CONTAINER", "homeassistant")
CONFIG_ENTRIES = Path(
    os.environ.get(
        "HA_CONFIG_ENTRIES",
        "/home/homelab/homeassistant/config/.storage/core.config_entries",
    )
)
RUNTIME_TOKENS = Path(
    os.environ.get(
        "BRIDGE_RUNTIME_TOKENS", "/var/lib/pandaplus-bridge/tuya_tokens_runtime.json"
    )
)
STATE_FILE = Path(os.environ.get("STATE_FILE", "/var/lib/tuya-selfheal/state.json"))
PROM_FILE = Path(
    os.environ.get(
        "PROM_FILE", "/var/lib/prometheus/node-exporter/tuya_token_selfheal.prom"
    )
)
MAX_HEALS_24H = int(os.environ.get("MAX_HEALS_24H", "3"))
HA_BOOT_WAIT_S = int(os.environ.get("HA_BOOT_WAIT_S", "300"))
IGNORED_DOMAINS = {"scene"}

REQUIRED_TOKEN_FIELDS = {"access_token", "refresh_token", "expire_time", "t", "uid"}


# ---------------------------------------------------------------- helpers puros


def token_expiry_ms(token_info: dict) -> int:
    """Timestamp (ms) de expiração do access token."""
    try:
        return int(token_info["t"]) + int(token_info["expire_time"]) * 1000
    except (KeyError, TypeError, ValueError):
        return 0


def token_remaining_minutes(token_info: dict, now_ms: float | None = None) -> float:
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    return (token_expiry_ms(token_info) - now_ms) / 60000


def valid_runtime_token(token_info: object) -> bool:
    return isinstance(token_info, dict) and REQUIRED_TOKEN_FIELDS.issubset(token_info)


def should_heal(
    ha_token: dict,
    runtime_token: dict | None,
    entities_active: int,
    heals_last_24h: int,
    now_ms: float | None = None,
) -> tuple[bool, str]:
    """Decide se a injeção do token do bridge deve ser aplicada.

    Conservador de propósito: só age com token do HA expirado, zero
    entidades ativas e token do bridge estritamente mais novo.
    """
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if entities_active > 0:
        return False, "entidades ativas > 0"
    if token_remaining_minutes(ha_token, now_ms) > 0:
        return False, "token do HA ainda válido"
    if not valid_runtime_token(runtime_token):
        return False, "token runtime do bridge ausente/inválido"
    if int(runtime_token["t"]) <= int(ha_token.get("t", 0)):
        return False, "token do bridge não é mais novo que o do HA"
    if heals_last_24h >= MAX_HEALS_24H:
        return False, f"rate limit: {heals_last_24h} heals nas últimas 24h"
    return True, "token HA expirado + 0 entidades + bridge com token mais novo"


def inject_token(config: dict, token_info: dict) -> dict:
    """Substitui token_info da entry domain=tuya (in place) e a retorna."""
    for entry in config["data"]["entries"]:
        if entry.get("domain") == "tuya":
            entry["data"]["token_info"] = token_info
            return entry
    raise LookupError("config entry domain=tuya não encontrada")


def render_prom(metrics: dict[str, float | int]) -> str:
    help_text = {
        "tuya_selfheal_runs_total": ("counter", "Execuções do selfheal"),
        "tuya_selfheal_heals_total": ("counter", "Heals aplicados com sucesso"),
        "tuya_selfheal_heal_failures_total": ("counter", "Heals que falharam"),
        "tuya_selfheal_last_run_timestamp": ("gauge", "Unix time da última execução"),
        "tuya_selfheal_last_heal_timestamp": ("gauge", "Unix time do último heal"),
        "tuya_selfheal_healthy": ("gauge", "1=integração Tuya saudável no HA"),
        "tuya_token_remaining_minutes": ("gauge", "Minutos até expirar o token da entry tuya no HA"),
        "tuya_bridge_token_remaining_minutes": ("gauge", "Minutos até expirar o token runtime do bridge"),
        "tuya_entities_active": ("gauge", "Entidades Tuya disponíveis no HA"),
        "tuya_entities_total": ("gauge", "Entidades Tuya habilitadas na entry"),
    }
    lines = []
    for name, value in metrics.items():
        mtype, mhelp = help_text.get(name, ("gauge", name))
        lines.append(f"# HELP {name} {mhelp}")
        lines.append(f"# TYPE {name} {mtype}")
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"


def prune_heal_history(history: list[float], now: float | None = None) -> list[float]:
    now = time.time() if now is None else now
    return [t for t in history if now - t < 86400]


# ------------------------------------------------------------ integração com HA


def docker_py(script: str, timeout: int = 60) -> str:
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "python3", "-c", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return proc.stdout.strip()


def ha_tuya_status() -> dict:
    """Coleta entry_id, token_info e disponibilidade das entidades tuya."""
    script = (
        "import json\n"
        "ce=json.load(open('/config/.storage/core.config_entries'))\n"
        "e=[x for x in ce['data']['entries'] if x['domain']=='tuya']\n"
        "out={'entry_id':None,'token_info':{}}\n"
        "if e:\n"
        "    out['entry_id']=e[0]['entry_id']\n"
        "    out['token_info']=e[0]['data'].get('token_info') or {}\n"
        "print(json.dumps(out))\n"
    )
    status = json.loads(docker_py(script))

    if status["entry_id"]:
        er_script = (
            "import json\n"
            f"entry={status['entry_id']!r}\n"
            "er=json.load(open('/config/.storage/core.entity_registry'))\n"
            "ents=[x for x in er['data']['entities']\n"
            "      if x.get('config_entry_id')==entry and not x.get('disabled_by')]\n"
            "print(json.dumps([e['entity_id'] for e in ents]))\n"
        )
        entity_ids = [
            eid
            for eid in json.loads(docker_py(er_script))
            if eid.split(".")[0] not in IGNORED_DOMAINS
        ]
        # Estados via JWT local (mesma técnica do ha-tuya-mq-watchdog)
        jwt_script = (
            "import json,jwt,time,urllib.request\n"
            "a=json.load(open('/config/.storage/auth'))\n"
            "tok=next(t for t in a['data']['refresh_tokens']\n"
            "         if t.get('token_type')=='long_lived_access_token')\n"
            "j=jwt.encode({'iss':tok['id'],'iat':int(time.time()),\n"
            "              'exp':int(time.time())+300},tok['jwt_key'],algorithm='HS256')\n"
            "req=urllib.request.Request('http://127.0.0.1:8123/api/states',\n"
            "    headers={'Authorization':'Bearer '+j})\n"
            "st=json.load(urllib.request.urlopen(req,timeout=30))\n"
            "print(json.dumps({s['entity_id']:s['state'] for s in st}))\n"
        )
        states = json.loads(docker_py(jwt_script))
        status["entities_total"] = len(entity_ids)
        status["entities_active"] = sum(
            1
            for eid in entity_ids
            if states.get(eid) not in (None, "unavailable", "unknown")
        )
    else:
        status["entities_total"] = 0
        status["entities_active"] = 0
    return status


def load_runtime_token() -> dict | None:
    try:
        token = json.loads(RUNTIME_TOKENS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return token if valid_runtime_token(token) else None


def apply_heal(runtime_token: dict) -> None:
    backup = CONFIG_ENTRIES.with_name(
        CONFIG_ENTRIES.name + f".tuya-selfheal-{int(time.time())}.bak"
    )
    shutil.copy2(CONFIG_ENTRIES, backup)
    log.info("Backup criado: %s", backup)

    config = json.loads(CONFIG_ENTRIES.read_text(encoding="utf-8"))
    inject_token(config, runtime_token)
    tmp = CONFIG_ENTRIES.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.move(tmp, CONFIG_ENTRIES)
    log.info("token_info injetado (t=%s)", runtime_token["t"])

    subprocess.run(["docker", "restart", CONTAINER], check=True, timeout=180)
    log.info("Container %s reiniciado; aguardando boot", CONTAINER)


def wait_recovery(deadline_s: int = HA_BOOT_WAIT_S) -> int:
    """Aguarda o HA subir e retorna a contagem de entidades ativas."""
    start = time.time()
    active = 0
    while time.time() - start < deadline_s:
        time.sleep(20)
        try:
            active = ha_tuya_status()["entities_active"]
        except Exception:  # noqa: BLE001 - HA ainda subindo
            continue
        if active > 0:
            break
    return active


# ------------------------------------------------------------------------ main


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"runs_total": 0, "heals_total": 0, "heal_failures_total": 0,
                "last_heal_timestamp": 0, "heal_history": []}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def write_prom(metrics: dict) -> None:
    try:
        PROM_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROM_FILE.with_suffix(".prom.tmp")
        tmp.write_text(render_prom(metrics), encoding="utf-8")
        tmp.replace(PROM_FILE)
    except OSError as exc:
        log.warning("Falha ao escrever métricas: %s", exc)


def main() -> int:
    state = load_state()
    state["runs_total"] += 1
    state["heal_history"] = prune_heal_history(state.get("heal_history", []))

    status = ha_tuya_status()
    runtime_token = load_runtime_token()
    ha_token = status.get("token_info") or {}

    heal, reason = should_heal(
        ha_token, runtime_token, status["entities_active"], len(state["heal_history"])
    )
    log.info(
        "Tuya: %s/%s ativas | token HA resta %.0f min | heal=%s (%s)",
        status["entities_active"], status["entities_total"],
        token_remaining_minutes(ha_token), heal, reason,
    )

    if heal:
        try:
            apply_heal(runtime_token)
            active = wait_recovery()
            if active > 0:
                state["heals_total"] += 1
                state["last_heal_timestamp"] = int(time.time())
                state["heal_history"].append(time.time())
                status = ha_tuya_status()
                ha_token = status.get("token_info") or {}
                log.info("Heal OK: %s entidades ativas", active)
            else:
                state["heal_failures_total"] += 1
                log.error("Heal aplicado mas entidades não voltaram — reauth QR necessária")
        except Exception:  # noqa: BLE001
            state["heal_failures_total"] += 1
            log.exception("Heal falhou")

    save_state(state)
    healthy = int(status["entities_active"] > 0)
    write_prom({
        "tuya_selfheal_runs_total": state["runs_total"],
        "tuya_selfheal_heals_total": state["heals_total"],
        "tuya_selfheal_heal_failures_total": state["heal_failures_total"],
        "tuya_selfheal_last_run_timestamp": int(time.time()),
        "tuya_selfheal_last_heal_timestamp": state["last_heal_timestamp"],
        "tuya_selfheal_healthy": healthy,
        "tuya_token_remaining_minutes": round(token_remaining_minutes(ha_token), 1),
        "tuya_bridge_token_remaining_minutes": round(
            token_remaining_minutes(runtime_token) if runtime_token else -1, 1
        ),
        "tuya_entities_active": status["entities_active"],
        "tuya_entities_total": status["entities_total"],
    })
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
