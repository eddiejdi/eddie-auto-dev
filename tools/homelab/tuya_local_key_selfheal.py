#!/usr/bin/env python3
"""Self-heal de local_key para devices tuya_local no Home Assistant.

Alguns dispositivos Tuya rotacionam a local_key periodicamente. A integração
tuya_local não reconfigura sozinha — fica unavailable até a chave ser
atualizada.

Fluxo:
1. Carrega o melhor token (bridge runtime vs entry cloud HA).
2. **Força refresh** do access token (evita sign invalid com token “ainda válido”).
3. Descobre automaticamente todas as config entries domain=tuya_local habilitadas
   (não só a lista hardcoded do quarto).
4. Compara local_key da nuvem com a do storage; se divergir, grava e reload.

Buracos cobertos 2026-07-22/27:
- Token bridge morto / sign invalid → refresh proativo + fallback HA.
- MONITORED dinâmico a partir de core.config_entries.
- Permissão clara em HA_TOKEN_FILE.
"""

from __future__ import annotations

import json
import logging
import os
import sys
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
TUYA_CLIENT_ID = os.environ.get("TUYA_CLIENT_ID", "HA_3y9q4ak7g4ephrvke")
TUYA_SHARING_SITE = Path(
    os.environ.get(
        "TUYA_SHARING_SITE",
        "/home/homelab/myClaude/.venv/lib/python3.12/site-packages",
    )
)
PROM_FILE = Path(
    os.environ.get(
        "PROM_FILE",
        "/var/lib/prometheus/node-exporter/tuya_local_key_selfheal.prom",
    )
)

# Fallback entity checks (entry_id -> entity) quando reload atualiza chave.
CHECK_ENTITY_FALLBACK = {
    "01KY3C3E97YAVYJS5PBN0Q6Q6A": "switch.luz_interruptor_quarto",
    "01KY3ESW9VY8S42JKX4ECEQ5B7": "switch.spot_quarto",
    "01KY3CEB7GEFG211KJF4MRJDPN": "switch.luz_fita_quarto",
}

RECONNECT_WAIT_S = 20
REQUIRED_TOKEN_FIELDS = {"access_token", "refresh_token", "expire_time", "t", "uid"}


def token_expiry_ms(token_info: dict) -> int:
    try:
        return int(token_info["t"]) + int(token_info["expire_time"]) * 1000
    except (KeyError, TypeError, ValueError):
        return 0


def valid_token_info(token_info: object) -> bool:
    return isinstance(token_info, dict) and REQUIRED_TOKEN_FIELDS.issubset(token_info)


def pick_newer_token(a: dict | None, b: dict | None) -> dict | None:
    a_ok = valid_token_info(a)
    b_ok = valid_token_info(b)
    if a_ok and b_ok:
        return a if token_expiry_ms(a) >= token_expiry_ms(b) else b  # type: ignore[arg-type]
    if a_ok:
        return a  # type: ignore[return-value]
    if b_ok:
        return b  # type: ignore[return-value]
    return None


def load_ha_tuya_cloud_meta(config_entries_path: Path = CONFIG_ENTRIES) -> dict:
    try:
        config = json.loads(config_entries_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Não li config_entries: %s", exc)
        return {}
    for entry in config.get("data", {}).get("entries", []):
        if entry.get("domain") != "tuya":
            continue
        data = entry.get("data") or {}
        return {
            "token_info": data.get("token_info") or {},
            "user_code": str(data.get("user_code") or ""),
            "endpoint": str(data.get("endpoint") or "https://apigw.tuyaus.com"),
            # CRÍTICO: usar o mesmo terminal_id da sessão HA; terminal aleatório
            # gera sign invalid / 1010 mesmo com access_token "válido".
            "terminal_id": str(data.get("terminal_id") or ""),
        }
    return {}


def load_bridge_runtime_token(path: Path = BRIDGE_TOKENS) -> dict | None:
    try:
        token = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return token if valid_token_info(token) else None


def load_best_token_info(
    bridge_path: Path = BRIDGE_TOKENS,
    config_entries_path: Path = CONFIG_ENTRIES,
) -> tuple[dict | None, dict]:
    meta = load_ha_tuya_cloud_meta(config_entries_path)
    ha_token = meta.get("token_info") if valid_token_info(meta.get("token_info")) else None
    bridge_token = load_bridge_runtime_token(bridge_path)
    best = pick_newer_token(bridge_token, ha_token)  # type: ignore[arg-type]
    source = "none"
    if best is not None and bridge_token is not None and best is bridge_token:
        source = "bridge_runtime"
    elif best is not None and ha_token is not None and best is ha_token:
        source = "ha_config_entries"
    elif best is not None:
        source = (
            "bridge_runtime"
            if bridge_token and token_expiry_ms(best) == token_expiry_ms(bridge_token)
            else "ha_config_entries"
        )
    meta["token_source"] = source
    return best, meta


def discover_tuya_local_targets(config_entries_path: Path = CONFIG_ENTRIES) -> dict[str, str]:
    """entry_id -> device_id para todas as tuya_local habilitadas."""
    out: dict[str, str] = {}
    try:
        config = json.loads(config_entries_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.error("discover_tuya_local_targets: %s", exc)
        return out
    for entry in config.get("data", {}).get("entries", []):
        if entry.get("domain") != "tuya_local":
            continue
        if entry.get("disabled_by"):
            continue
        data = entry.get("data") or {}
        device_id = data.get("device_id")
        entry_id = entry.get("entry_id")
        if entry_id and device_id:
            out[str(entry_id)] = str(device_id)
    return out


def _import_tuya_sharing() -> tuple[object, object]:
    try:
        from tuya_sharing.customerapi import CustomerApi, CustomerTokenInfo  # type: ignore
        return CustomerApi, CustomerTokenInfo
    except ImportError:
        site = str(TUYA_SHARING_SITE)
        if site not in sys.path and TUYA_SHARING_SITE.is_dir():
            sys.path.insert(0, site)
        from tuya_sharing.customerapi import CustomerApi, CustomerTokenInfo  # type: ignore
        return CustomerApi, CustomerTokenInfo


def force_refresh_token(
    token_info: dict,
    *,
    user_code: str,
    endpoint: str,
    client_id: str = TUYA_CLIENT_ID,
    terminal_id: str = "",
) -> dict | None:
    """Força refresh OAuth (mesmo com token ainda dentro do TTL)."""
    if not valid_token_info(token_info) or not user_code:
        return None
    try:
        CustomerApi, CustomerTokenInfo = _import_tuya_sharing()
    except ImportError as exc:
        log.warning("tuya_sharing indisponível: %s", exc)
        return None

    class _Listener:
        def __init__(self) -> None:
            self.updated: dict | None = None

        def update_token(self, new_token: dict) -> None:  # noqa: ANN001
            self.updated = new_token

    listener = _Listener()
    try:
        # CustomerApi signature: token_info, client_id, user_code, endpoint, listener
        # terminal_id é usado pelo Manager, não pelo CustomerApi direto.
        api = CustomerApi(
            CustomerTokenInfo(dict(token_info)),
            client_id,
            user_code,
            endpoint.rstrip("/"),
            listener,
        )
        api.token_info.expire_time = int(time.time() * 1000) - 1
        api.refresh_access_token_if_need()
    except Exception as exc:  # noqa: BLE001
        log.warning("force_refresh_token falhou: %s", exc)
        return None

    if listener.updated and valid_token_info(listener.updated):
        return listener.updated
    try:
        ti = api.token_info
        now_ms = int(time.time() * 1000)
        absolute = int(getattr(ti, "expire_time", 0) or 0)
        built = {
            "access_token": getattr(ti, "access_token", ""),
            "refresh_token": getattr(ti, "refresh_token", ""),
            "uid": getattr(ti, "uid", token_info.get("uid", "")),
            "t": now_ms,
            "expire_time": max(0, (absolute - now_ms) // 1000)
            or int(token_info.get("expire_time") or 7200),
        }
        if valid_token_info(built) and built["access_token"] != token_info.get("access_token"):
            return built
    except Exception as exc:  # noqa: BLE001
        log.warning("force_refresh parse fallback: %s", exc)
    return None


def persist_runtime_token(token_info: dict) -> None:
    try:
        BRIDGE_TOKENS.parent.mkdir(parents=True, exist_ok=True)
        tmp = BRIDGE_TOKENS.with_suffix(".tmp")
        tmp.write_text(json.dumps(token_info, ensure_ascii=True), encoding="utf-8")
        tmp.replace(BRIDGE_TOKENS)
        log.info(
            "runtime token atualizado remaining=%.0f min",
            (token_expiry_ms(token_info) - time.time() * 1000) / 60000,
        )
    except OSError as exc:
        log.warning("Não persisti runtime token (%s) — seguindo em memória", exc)


def ensure_fresh_token(token_info: dict, meta: dict, *, force: bool = False) -> dict:
    """Refresh só se token já morto ou force=True (ex.: após sign invalid).

    Não renovar "proativo" cedo demais: o refresh_token da sessão Sharing
    costuma falhar com 1010 mesmo com access_token ainda útil para leitura
    de devices/local_key — e o refresh falho atrasa o ciclo sem ganho.
    """
    user_code = str(meta.get("user_code") or "")
    endpoint = str(meta.get("endpoint") or "https://apigw.tuyaus.com")
    remaining = (token_expiry_ms(token_info) - time.time() * 1000) / 60000
    if not force and remaining > 0:
        return token_info
    log.info(
        "Refresh local_key (remaining=%.0f min force=%s)", remaining, force
    )
    refreshed = force_refresh_token(token_info, user_code=user_code, endpoint=endpoint)
    if refreshed:
        persist_runtime_token(refreshed)
        return refreshed
    return token_info


def read_ha_token(path: Path = HA_TOKEN_FILE) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except PermissionError as exc:
        raise PermissionError(
            f"Sem permissão para ler {path} (esperado User=homelab com "
            f"chown homelab:homelab e mode 600). Detalhe: {exc}"
        ) from exc
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"HA token ausente em {path}. Crie com ha_create_token ou copie "
            f"o long-lived token do HA."
        ) from exc


def fetch_cloud_keys(
    device_ids: list[str],
    token_info: dict,
    *,
    user_code: str,
    endpoint: str,
    terminal_id: str = "",
    client_id: str = TUYA_CLIENT_ID,
) -> dict[str, str]:
    site = str(TUYA_SHARING_SITE)
    if site not in sys.path and TUYA_SHARING_SITE.is_dir():
        sys.path.insert(0, site)
    from tuya_sharing.customerapi import SharingTokenListener
    from tuya_sharing.manager import Manager

    class NoopListener(SharingTokenListener):
        def update_token(self, token_info):  # noqa: ANN001
            pass

    if not user_code:
        raise ValueError("user_code Tuya ausente (entry domain=tuya no HA)")

    # Preferir terminal_id da sessão HA; fallback só se ausente.
    tid = terminal_id or ("selfheal-" + uuid.uuid4().hex[:16])
    manager = Manager(
        client_id,
        user_code,
        tid,
        endpoint.rstrip("/"),
        token_info,
        NoopListener(),
    )
    manager.update_device_cache()

    out: dict[str, str] = {}
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
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def write_prom(metrics: dict[str, float | int]) -> None:
    help_text = {
        "tuya_local_key_selfheal_runs_total": ("counter", "Execuções do selfheal local_key"),
        "tuya_local_key_selfheal_updates_total": ("counter", "local_keys atualizadas"),
        "tuya_local_key_selfheal_errors_total": ("counter", "Falhas na execução"),
        "tuya_local_key_selfheal_last_run_timestamp": ("gauge", "Unix time última execução"),
        "tuya_local_key_selfheal_healthy": ("gauge", "1=OK 0=erro"),
        "tuya_local_key_token_remaining_minutes": (
            "gauge",
            "Minutos restantes do token usado (bridge ou HA)",
        ),
        "tuya_local_key_monitored_entries": ("gauge", "Entries tuya_local monitoradas"),
    }
    lines = []
    for name, value in metrics.items():
        mtype, mhelp = help_text.get(name, ("gauge", name))
        lines.append(f"# HELP {name} {mhelp}")
        lines.append(f"# TYPE {name} {mtype}")
        lines.append(f"{name} {value}")
    try:
        PROM_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROM_FILE.with_suffix(".prom.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(PROM_FILE)
    except OSError as exc:
        log.warning("Falha ao escrever métricas: %s", exc)


def main() -> int:
    errors = 0
    updates = 0

    try:
        ha_token = read_ha_token()
    except (PermissionError, FileNotFoundError) as exc:
        log.error("%s", exc)
        write_prom(
            {
                "tuya_local_key_selfheal_runs_total": 1,
                "tuya_local_key_selfheal_updates_total": 0,
                "tuya_local_key_selfheal_errors_total": 1,
                "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                "tuya_local_key_selfheal_healthy": 0,
                "tuya_local_key_token_remaining_minutes": -1,
                "tuya_local_key_monitored_entries": 0,
            }
        )
        return 2

    best_token, meta = load_best_token_info()
    if not best_token:
        log.error(
            "Nenhum token Tuya válido (bridge=%s, ha entry ausente/expirada).",
            BRIDGE_TOKENS,
        )
        write_prom(
            {
                "tuya_local_key_selfheal_runs_total": 1,
                "tuya_local_key_selfheal_updates_total": 0,
                "tuya_local_key_selfheal_errors_total": 1,
                "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                "tuya_local_key_selfheal_healthy": 0,
                "tuya_local_key_token_remaining_minutes": -1,
                "tuya_local_key_monitored_entries": 0,
            }
        )
        return 2

    best_token = ensure_fresh_token(best_token, meta, force=False)
    token_remaining = (token_expiry_ms(best_token) - time.time() * 1000) / 60000
    log.info(
        "Token fonte=%s remaining=%.0f min user_code=%s",
        meta.get("token_source"),
        token_remaining,
        (meta.get("user_code") or "")[:4] + "***",
    )

    monitored = discover_tuya_local_targets()
    if not monitored:
        log.warning("Nenhuma entry tuya_local habilitada para monitorar")
        write_prom(
            {
                "tuya_local_key_selfheal_runs_total": 1,
                "tuya_local_key_selfheal_updates_total": 0,
                "tuya_local_key_selfheal_errors_total": 0,
                "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                "tuya_local_key_selfheal_healthy": 1,
                "tuya_local_key_token_remaining_minutes": round(token_remaining, 1),
                "tuya_local_key_monitored_entries": 0,
            }
        )
        return 0

    log.info("Monitorando %d entries tuya_local: %s", len(monitored), list(monitored.values()))

    user_code = str(meta.get("user_code") or "")
    endpoint = str(meta.get("endpoint") or "https://apigw.tuyaus.com")

    terminal_id = str(meta.get("terminal_id") or "")

    def _fetch(tok: dict) -> dict[str, str]:
        return fetch_cloud_keys(
            list(monitored.values()),
            tok,
            user_code=user_code,
            endpoint=endpoint,
            terminal_id=terminal_id,
        )

    try:
        cloud_keys = _fetch(best_token)
    except Exception as exc:  # noqa: BLE001
        log.warning("1ª tentativa cloud falhou (%s) — tenta outro token + refresh", exc)
        # Alterna fonte: se usamos bridge, tenta HA puro e vice-versa.
        alt_meta = load_ha_tuya_cloud_meta()
        alt = None
        if meta.get("token_source") == "bridge_runtime" and valid_token_info(
            alt_meta.get("token_info")
        ):
            alt = alt_meta["token_info"]
        elif meta.get("token_source") != "bridge_runtime":
            alt = load_bridge_runtime_token()
        cloud_keys = None
        if alt and valid_token_info(alt):
            try:
                cloud_keys = _fetch(alt)  # type: ignore[arg-type]
                best_token = alt  # type: ignore[assignment]
                token_remaining = (token_expiry_ms(best_token) - time.time() * 1000) / 60000
                log.info("Fallback de fonte de token OK")
            except Exception as exc_alt:  # noqa: BLE001
                log.warning("Fallback de fonte também falhou: %s", exc_alt)
        if cloud_keys is None:
            refreshed = force_refresh_token(
                best_token, user_code=user_code, endpoint=endpoint
            )
            if not refreshed:
                log.error(
                    "Falha ao buscar local_keys na nuvem: %s "
                    "(sessão Sharing inválida — reauth QR no Smart Life se persistir)",
                    exc,
                )
                write_prom(
                    {
                        "tuya_local_key_selfheal_runs_total": 1,
                        "tuya_local_key_selfheal_updates_total": 0,
                        "tuya_local_key_selfheal_errors_total": 1,
                        "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                        "tuya_local_key_selfheal_healthy": 0,
                        "tuya_local_key_token_remaining_minutes": round(token_remaining, 1),
                        "tuya_local_key_monitored_entries": len(monitored),
                    }
                )
                # Soft-fail: não marca unit failed a cada 15 min; métrica healthy=0 alerta.
                return 0
            persist_runtime_token(refreshed)
            best_token = refreshed
            token_remaining = (token_expiry_ms(best_token) - time.time() * 1000) / 60000
            try:
                cloud_keys = _fetch(best_token)
            except Exception as exc2:  # noqa: BLE001
                log.error("Falha ao buscar local_keys após refresh: %s", exc2)
                write_prom(
                    {
                        "tuya_local_key_selfheal_runs_total": 1,
                        "tuya_local_key_selfheal_updates_total": 0,
                        "tuya_local_key_selfheal_errors_total": 1,
                        "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                        "tuya_local_key_selfheal_healthy": 0,
                        "tuya_local_key_token_remaining_minutes": round(token_remaining, 1),
                        "tuya_local_key_monitored_entries": len(monitored),
                    }
                )
                return 0

    try:
        entries = json.loads(CONFIG_ENTRIES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.error("Falha ao ler config_entries: %s", exc)
        return 2

    changed = False
    healed_entries: list[str] = []

    for entry in entries["data"]["entries"]:
        entry_id = entry.get("entry_id")
        if entry_id not in monitored:
            continue
        device_id = monitored[entry_id]
        cloud_key = cloud_keys.get(device_id)
        if cloud_key is None:
            log.warning(
                "device_id %s não encontrado na nuvem (title=%s)",
                device_id,
                entry.get("title"),
            )
            errors += 1
            continue
        current_key = (entry.get("data") or {}).get("local_key")
        if current_key != cloud_key:
            log.info(
                "local_key desatualizada entry=%s device=%s title=%s — atualizando",
                entry_id,
                device_id,
                entry.get("title"),
            )
            entry.setdefault("data", {})["local_key"] = cloud_key
            changed = True
            healed_entries.append(entry_id)
            updates += 1

    if not changed:
        log.info(
            "Todas as %d entries tuya_local com local_key em dia", len(monitored)
        )
        write_prom(
            {
                "tuya_local_key_selfheal_runs_total": 1,
                "tuya_local_key_selfheal_updates_total": 0,
                "tuya_local_key_selfheal_errors_total": errors,
                "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
                "tuya_local_key_selfheal_healthy": 1 if errors == 0 else 0,
                "tuya_local_key_token_remaining_minutes": round(token_remaining, 1),
                "tuya_local_key_monitored_entries": len(monitored),
            }
        )
        return 0 if errors == 0 else 1

    CONFIG_ENTRIES.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
            errors += 1

    time.sleep(RECONNECT_WAIT_S)
    stuck = []
    for entry_id in healed_entries:
        entity_id = CHECK_ENTITY_FALLBACK.get(entry_id)
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
            "Entidades ainda unavailable após reload (%s) — escalando restart HA",
            stuck,
        )
        try:
            ha_api("POST", "/api/services/homeassistant/restart", ha_token)
            log.info("Restart do Home Assistant disparado")
        except Exception as exc:  # noqa: BLE001
            log.error("Falha ao disparar restart: %s", exc)
            errors += 1
    else:
        log.info("Reload de local_key concluído (sem stuck conhecido)")

    write_prom(
        {
            "tuya_local_key_selfheal_runs_total": 1,
            "tuya_local_key_selfheal_updates_total": updates,
            "tuya_local_key_selfheal_errors_total": errors,
            "tuya_local_key_selfheal_last_run_timestamp": int(time.time()),
            "tuya_local_key_selfheal_healthy": 1 if errors == 0 else 0,
            "tuya_local_key_token_remaining_minutes": round(token_remaining, 1),
            "tuya_local_key_monitored_entries": len(monitored),
        }
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
