#!/usr/bin/env python3
"""Self-heal de local_key para dispositivos Tuya Local do quarto.

Alguns dispositivos Tuya (categoria tdq/kg, módulos "mini") rotacionam a
local_key periodicamente a cada nova negociação de sessão com a nuvem,
mesmo sem re-pareamento físico. A integração tuya_local do Home Assistant
não acompanha essa rotação sozinha (não suporta reconfigure), então a
entidade fica "unavailable" até alguém atualizar a chave manualmente.

Este script consulta a nuvem Tuya (via sessão do pandaplus-bridge, sem
custo) para os device_ids monitorados, compara com a local_key gravada em
cada config entry do tuya_local, e se estiver diferente, atualiza o
storage do Home Assistant e recarrega a entry via API — sem reiniciar o
container.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tuya-local-key-selfheal")

HA_URL = os.environ.get("HA_URL", "http://127.0.0.1:8123").rstrip("/")
HA_TOKEN_FILE = Path(
    os.environ.get("HA_TOKEN_FILE", "/var/lib/tuya-local-selfheal/ha_token")
)
CONFIG_ENTRIES = Path(
    os.environ.get(
        "HA_CONFIG_ENTRIES",
        "/home/homelab/homeassistant/config/.storage/core.config_entries",
    )
)
BRIDGE_TOKENS = Path(
    os.environ.get(
        "BRIDGE_RUNTIME_TOKENS", "/var/lib/pandaplus-bridge/tuya_tokens_runtime.json"
    )
)

# entry_id (config entry da integração tuya_local) -> device_id Tuya monitorado
MONITORED = {
    "01KY3C3E97YAVYJS5PBN0Q6Q6A": "ebd0a5540ab0b8225ddwug",  # Luz Interruptor Quarto
    "01KY3ESW9VY8S42JKX4ECEQ5B7": "eb48a5c11d046286292ask",  # Spot Quarto
    "01KY3CEB7GEFG211KJF4MRJDPN": "eb75dc2918c27818b9zcue",  # Luz Fita Quarto
}

# entry_id -> entidade representativa para checar se reconectou de fato
CHECK_ENTITY = {
    "01KY3C3E97YAVYJS5PBN0Q6Q6A": "switch.luz_interruptor_quarto",
    "01KY3ESW9VY8S42JKX4ECEQ5B7": "switch.spot_quarto",
    "01KY3CEB7GEFG211KJF4MRJDPN": "switch.luz_fita_quarto",
}

RECONNECT_WAIT_S = 20
RECONNECT_POLL_S = 5


def fetch_cloud_keys(device_ids: list[str]) -> dict[str, str]:
    from tuya_sharing.customerapi import SharingTokenListener
    from tuya_sharing.manager import Manager

    token_info = json.loads(BRIDGE_TOKENS.read_text())

    class NoopListener(SharingTokenListener):
        def update_token(self, token_info):
            pass

    terminal_id = "selfheal-" + uuid.uuid4().hex[:16]
    manager = Manager(
        "HA_3y9q4ak7g4ephrvke",
        "Ba0osdh",
        terminal_id,
        "https://apigw.tuyaus.com",
        token_info,
        NoopListener(),
    )
    manager.update_device_cache()

    out = {}
    for did in device_ids:
        dev = manager.device_map.get(did)
        if dev is not None:
            out[did] = dev.local_key
    return out


def ha_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{HA_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def main() -> None:
    ha_token = HA_TOKEN_FILE.read_text().strip()

    cloud_keys = fetch_cloud_keys(list(MONITORED.values()))

    entries = json.loads(CONFIG_ENTRIES.read_text())
    changed = False
    healed_entries = []

    for entry in entries["data"]["entries"]:
        if entry.get("entry_id") not in MONITORED:
            continue
        entry_id = entry["entry_id"]
        device_id = MONITORED[entry_id]
        cloud_key = cloud_keys.get(device_id)
        if cloud_key is None:
            log.warning("device_id %s não encontrado na nuvem (talvez re-pareado)", device_id)
            continue
        current_key = entry.get("data", {}).get("local_key")
        if current_key != cloud_key:
            log.info(
                "local_key desatualizada para entry %s (device %s) — atualizando",
                entry_id,
                device_id,
            )
            entry["data"]["local_key"] = cloud_key
            changed = True
            healed_entries.append(entry_id)

    if not changed:
        log.info("Todas as %d entries monitoradas com local_key em dia", len(MONITORED))
        return

    CONFIG_ENTRIES.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    log.info("Storage atualizado, recarregando entries: %s", healed_entries)

    for entry_id in healed_entries:
        try:
            ha_api(
                "POST",
                f"/api/config/config_entries/entry/{entry_id}/reload",
                ha_token,
            )
            log.info("Reload OK: %s", entry_id)
        except Exception as exc:  # noqa: BLE001
            log.error("Falha ao recarregar %s: %s", entry_id, exc)

    # Verifica se o reload realmente restabeleceu a conexão. Às vezes o
    # tuya_local mantém a conexão TCP antiga presa mesmo após reload, e a
    # entidade continua "unavailable" — nesse caso escala para um restart
    # completo do Home Assistant (limpa todas as conexões de uma vez).
    time.sleep(RECONNECT_WAIT_S)
    stuck = []
    for entry_id in healed_entries:
        entity_id = CHECK_ENTITY.get(entry_id)
        if not entity_id:
            continue
        try:
            state = ha_api("GET", f"/api/states/{entity_id}", ha_token)
            if state.get("state") == "unavailable":
                stuck.append(entity_id)
        except Exception as exc:  # noqa: BLE001
            log.error("Falha ao checar %s: %s", entity_id, exc)
            stuck.append(entity_id)

    if stuck:
        log.warning(
            "Entidades ainda unavailable após reload (%s) — escalando para restart do HA",
            stuck,
        )
        try:
            ha_api("POST", "/api/services/homeassistant/restart", ha_token)
            log.info("Restart do Home Assistant disparado")
        except Exception as exc:  # noqa: BLE001
            log.error("Falha ao disparar restart: %s", exc)
    else:
        log.info("Todas as entidades reconectaram normalmente após reload")


if __name__ == "__main__":
    main()
