#!/usr/bin/env python3
"""Self-heal do token Tuya no Home Assistant.

Quando o access token da config entry `tuya` expira (~2h), o HA entra em
estado degradado — comandos cloud falham com `sign invalid` / `2001` e o
MQTT tuya_sharing cai. O pandaplus-bridge mantém sessão própria, mas o SDK
só renova o token quando faltam <60s; sem intervenção proativa restam
janelas de 5–15 min com HA sem token válido.

Modos de falha cobertos (jul/2026 + ago/2026):
1. Token OAuth expirado / na janela soft → refresh proativo + injeção.
2. Entry em ``setup_error`` (timeout API Tuya) com token ainda "válido" →
   reload da config entry (self-heal antigo *não* cobria — só olhava token).
   Reload com entidades já ativas (zumbi) **não** consome MAX_HEALS_24H.
3. 0/N entidades ativas com token aparentemente válido → reload; se bridge
   tiver token mais novo, injeta mesmo acima do soft threshold.
4. Rate limit 24h: aplica a heals proativos; **bypass** se HA já expirou e
   o bridge/runtime é estritamente mais novo (incidente 2026-08-08).

Fluxo:
1. Se o access token (HA ou bridge) está abaixo do limiar soft, **força
   refresh** via API Tuya Sharing e grava em tuya_tokens_runtime.json.
2. Se entry em setup_error / 0 ativas com token válido → **reload** da entry.
3. Se o bridge/runtime ficou mais novo que o HA, injeta no HA:
   a. **hot** — serviço `tuya_token_inject.apply` (preferido)
   b. **core_restart** — storage + `homeassistant.restart`
   c. **docker_restart** — storage + `docker restart` (último recurso)

Exporta métricas via textfile collector.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tuya-token-selfheal")

CONTAINER = os.environ.get("HA_CONTAINER", "homeassistant")
HA_URL = os.environ.get("HA_URL", "http://127.0.0.1:8123").rstrip("/")
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
MAX_HEALS_24H = int(os.environ.get("MAX_HEALS_24H", "24"))
HA_BOOT_WAIT_S = int(os.environ.get("HA_BOOT_WAIT_S", "300"))
# Tempo de recovery do hot-apply (nome distinto de HA_BOOT_WAIT_S de propósito).
TUYA_SELFHEAL_HOT_WAIT_S = int(os.environ.get("TUYA_SELFHEAL_HOT_WAIT_S", "90"))
# Heal proativo quando o access token do HA está prestes a expirar (minutos).
# 0 = só com token já expirado (remaining <= 0).
HEAL_SOFT_THRESHOLD_MIN = float(os.environ.get("HEAL_SOFT_THRESHOLD_MIN", "45"))
# Client ID público da integração Tuya do Home Assistant core.
TUYA_CLIENT_ID = os.environ.get("TUYA_CLIENT_ID", "HA_3y9q4ak7g4ephrvke")
# site-packages do venv que tem tuya_sharing (bridge).
TUYA_SHARING_SITE = Path(
    os.environ.get(
        "TUYA_SHARING_SITE",
        "/home/homelab/myClaude/.venv/lib/python3.12/site-packages",
    )
)
IGNORED_DOMAINS = {"scene"}

REQUIRED_TOKEN_FIELDS = {"access_token", "refresh_token", "expire_time", "t", "uid"}

# Modos exportados em métrica tuya_selfheal_last_mode
MODE_NONE = 0
MODE_HOT = 1
MODE_CORE_RESTART = 2
MODE_DOCKER_RESTART = 3
MODE_RELOAD = 4

# entry_state → gauge tuya_entry_state_code
ENTRY_STATE_CODES = {
    "loaded": 0,
    "setup_error": 1,
    "setup_retry": 2,
    "not_loaded": 3,
    "migration_error": 4,
    "failed_unload": 5,
}


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


def should_reload_entry(
    entry_state: str | None,
    entities_active: int,
    entities_total: int,
    remaining_min: float,
) -> tuple[bool, str]:
    """Decide se a config entry Tuya deve ser recarregada (sem injetar token).

    Cobre o buraco do incidente 2026-07-25: entry em ``setup_error`` por
    timeout da API Tuya, token ainda com dezenas de minutos, 0 entidades
    ativas — o heal de token recusava com "ainda válido" e ninguém reloadava.

    Nota (2026-08-08): reload com entidades já ativas (zumbi) ainda pode
    rodar, mas **não** deve consumir ``MAX_HEALS_24H`` — ver
    ``reload_counts_toward_heal_budget``.
    """
    state = (entry_state or "").strip().lower()
    if state == "setup_error":
        return True, "entry em setup_error"
    if state in ("setup_retry", "not_loaded", "migration_error"):
        return True, f"entry state={state}"
    # Integração "loaded" mas zumbificada: token ok no storage, 0 ativas.
    if (
        entities_total > 0
        and entities_active == 0
        and remaining_min > 0
    ):
        return (
            True,
            f"0/{entities_total} ativas com token ainda válido "
            f"({remaining_min:.0f} min) — reload da entry",
        )
    return False, "reload não necessário"


def reload_counts_toward_heal_budget(
    entities_active_before: int,
    entities_active_after: int,
) -> bool:
    """Só conta reload no budget de heals se recuperou entidades (0 → >0).

    Incidente 2026-08-08: entry em ``setup_error`` com 82/82 ainda "ativas"
    fazia reload a cada 5 min, cada um contava como Heal OK e esgotava
    ``MAX_HEALS_24H`` — depois o inject legítimo (HA expirado + bridge fresco)
    era barrado pelo rate limit.
    """
    return entities_active_before <= 0 and entities_active_after > 0


def should_heal(
    ha_token: dict,
    runtime_token: dict | None,
    entities_active: int,
    heals_last_24h: int,
    now_ms: float | None = None,
    soft_threshold_min: float | None = None,
    entities_total: int = 0,
) -> tuple[bool, str]:
    """Decide se a injeção do token do bridge deve ser aplicada.

    Regras (2026-07-23 + buracos 2026-07-27 + rate-limit 2026-08-08):
    - Token do HA **expirado** (remaining <= 0): heal **mesmo com entidades
      ainda "ativas"** — estado zumbi típico (cloud morta, HA cacheia on/off).
      **Bypass de rate limit** quando o bridge é estritamente mais novo
      (inject é o único path automático; budget queimado em reload não pode
      bloquear).
    - Soft threshold (HEAL_SOFT_THRESHOLD_MIN, default 45): heal proativo se
      remaining estiver abaixo do limiar e o runtime/bridge for mais novo.
    - **0 entidades ativas** com entidades no registry: permite heal mesmo
      *acima* do soft threshold se o bridge for estritamente mais novo
      (token em memória pode estar stale / entry semi-morta).
    - Bridge/runtime precisa de token válido e estritamente mais novo (t maior).
    - Rate limit por 24h para heals **proativos** (soft / 0-ativas com token
      ainda válido); **não** aplica quando HA já expirou + bridge fresco.
    """
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if soft_threshold_min is None:
        soft_threshold_min = HEAL_SOFT_THRESHOLD_MIN

    remaining = token_remaining_minutes(ha_token, now_ms)
    zero_entities = entities_total > 0 and entities_active == 0

    # Token saudável e integração respondendo: não injeta.
    if remaining > soft_threshold_min and not zero_entities:
        return False, "token do HA ainda válido"

    if not valid_runtime_token(runtime_token):
        return False, "token runtime do bridge ausente/inválido"
    try:
        bridge_t = int(runtime_token["t"])
        ha_t = int(ha_token.get("t", 0) or 0)
    except (TypeError, ValueError):
        return False, "token runtime do bridge ausente/inválido"
    if bridge_t <= ha_t:
        return False, "token do bridge não é mais novo que o do HA"

    rate_limited = heals_last_24h >= MAX_HEALS_24H

    # HA access token morto + bridge fresco: inject prioritário (bypass budget).
    if remaining <= 0:
        return (
            True,
            f"token HA expirado ({remaining:.0f} min) + bridge mais novo"
            + (" | rate-limit bypass" if rate_limited else "")
            + (
                f" | {entities_active} entidades ainda ativas"
                if entities_active > 0
                else ""
            ),
        )

    if rate_limited:
        return False, f"rate limit: {heals_last_24h} heals nas últimas 24h"

    if zero_entities and remaining > soft_threshold_min:
        return (
            True,
            f"0/{entities_total} ativas com token HA 'válido' "
            f"({remaining:.0f} min) + bridge mais novo",
        )

    # Soft threshold: token ainda válido por poucos minutos.
    return (
        True,
        f"token HA expira em {remaining:.0f} min (<= {soft_threshold_min:.0f}) + bridge mais novo",
    )


def load_tuya_entry_meta() -> dict[str, str]:
    """Lê user_code e endpoint da entry tuya em core.config_entries (host)."""
    try:
        config = json.loads(CONFIG_ENTRIES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for entry in config.get("data", {}).get("entries", []):
        if entry.get("domain") != "tuya":
            continue
        data = entry.get("data") or {}
        return {
            "user_code": str(data.get("user_code") or ""),
            "endpoint": str(data.get("endpoint") or "https://apigw.tuyaus.com"),
        }
    return {}


def _import_tuya_sharing() -> tuple[object, object]:
    """Importa CustomerApi/CustomerTokenInfo (system ou venv do bridge)."""
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
) -> dict | None:
    """Força refresh do access token via API Tuya Sharing.

    O SDK só renova com <60s restantes; aqui forçamos expire_time no passado
    para obter um token novo antes da janela de blackout do HA.
    """
    if not valid_runtime_token(token_info) or not user_code:
        return None
    try:
        CustomerApi, CustomerTokenInfo = _import_tuya_sharing()
    except ImportError as exc:
        log.warning("tuya_sharing indisponível para refresh proativo: %s", exc)
        return None

    class _Listener:
        def __init__(self) -> None:
            self.updated: dict | None = None

        def update_token(self, new_token: dict) -> None:  # noqa: ANN001
            self.updated = new_token

    listener = _Listener()
    try:
        api = CustomerApi(
            CustomerTokenInfo(dict(token_info)),
            client_id,
            user_code,
            endpoint.rstrip("/"),
            listener,
        )
        # Força o ramo de refresh em refresh_access_token_if_need().
        api.token_info.expire_time = int(time.time() * 1000) - 1
        api.refresh_access_token_if_need()
    except Exception as exc:  # noqa: BLE001
        log.warning("force_refresh_token falhou: %s", exc)
        return None

    if listener.updated and valid_runtime_token(listener.updated):
        return listener.updated

    # Fallback: montar dict a partir do CustomerTokenInfo interno.
    try:
        ti = api.token_info
        # expire_time no objeto é absoluto (ms); reconverter para o formato storage.
        now_ms = int(time.time() * 1000)
        absolute = int(getattr(ti, "expire_time", 0) or 0)
        # Preferir o payload do listener; se só temos objeto, estimar t.
        built = {
            "access_token": getattr(ti, "access_token", ""),
            "refresh_token": getattr(ti, "refresh_token", ""),
            "uid": getattr(ti, "uid", token_info.get("uid", "")),
            "t": now_ms,
            "expire_time": max(0, (absolute - now_ms) // 1000) or int(token_info.get("expire_time") or 7200),
        }
        if valid_runtime_token(built) and built["access_token"] != token_info.get("access_token"):
            return built
    except Exception as exc:  # noqa: BLE001
        log.warning("force_refresh_token parse fallback falhou: %s", exc)
    return None


def persist_runtime_token(token_info: dict) -> None:
    """Grava token renovado no path do bridge (fonte do heal)."""
    RUNTIME_TOKENS.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNTIME_TOKENS.with_suffix(".tmp")
    tmp.write_text(json.dumps(token_info, ensure_ascii=True), encoding="utf-8")
    tmp.replace(RUNTIME_TOKENS)
    log.info(
        "runtime token atualizado (t=%s remaining=%.0f min)",
        token_info.get("t"),
        token_remaining_minutes(token_info),
    )


def ensure_fresh_runtime_token(
    ha_token: dict,
    runtime_token: dict | None,
    *,
    soft_threshold_min: float | None = None,
    now_ms: float | None = None,
    force: bool = False,
) -> dict | None:
    """Garante runtime token mais novo que o HA quando restam poucos minutos.

    Retorna o runtime token a usar (pode ser o mesmo de entrada se não
    precisou/conseguiu renovar).

    ``force=True``: tenta refresh mesmo com HA acima do soft threshold
    (ex.: 0 entidades ativas / setup_error — token "válido" mas integração morta).
    """
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    if soft_threshold_min is None:
        soft_threshold_min = HEAL_SOFT_THRESHOLD_MIN

    ha_remaining = token_remaining_minutes(ha_token, now_ms) if ha_token else -1
    runtime_remaining = (
        token_remaining_minutes(runtime_token, now_ms)
        if valid_runtime_token(runtime_token)
        else -1
    )

    # Nada a fazer se o HA ainda tem folga confortável (salvo force).
    if ha_remaining > soft_threshold_min and not force:
        return runtime_token if valid_runtime_token(runtime_token) else None

    # Já temos runtime estritamente mais novo e ainda com vida: usa direto.
    try:
        ha_t = int(ha_token.get("t", 0) or 0) if ha_token else 0
        rt_t = int(runtime_token["t"]) if valid_runtime_token(runtime_token) else 0
    except (TypeError, ValueError, KeyError):
        ha_t, rt_t = 0, 0
    if (
        valid_runtime_token(runtime_token)
        and rt_t > ha_t
        and runtime_remaining > soft_threshold_min
    ):
        return runtime_token

    # Escolhe a melhor base para refresh (runtime se existir, senão HA).
    source: dict | None = None
    if valid_runtime_token(runtime_token) and runtime_remaining >= ha_remaining:
        source = runtime_token  # type: ignore[assignment]
    elif valid_runtime_token(ha_token):
        source = ha_token
    elif valid_runtime_token(runtime_token):
        source = runtime_token  # type: ignore[assignment]
    else:
        log.warning("Sem token base válido para refresh proativo")
        return runtime_token if valid_runtime_token(runtime_token) else None

    meta = load_tuya_entry_meta()
    user_code = meta.get("user_code") or ""
    endpoint = meta.get("endpoint") or "https://apigw.tuyaus.com"
    if not user_code:
        log.warning("user_code tuya ausente em config_entries — skip refresh proativo")
        return runtime_token if valid_runtime_token(runtime_token) else None

    log.info(
        "Refresh proativo Tuya (HA resta %.0f min, runtime resta %.0f min, soft=%.0f)",
        ha_remaining,
        runtime_remaining,
        soft_threshold_min,
    )
    refreshed = force_refresh_token(source, user_code=user_code, endpoint=endpoint)
    if not refreshed:
        return runtime_token if valid_runtime_token(runtime_token) else None

    try:
        if int(refreshed["t"]) <= int(source.get("t", 0) or 0):
            log.warning("Refresh proativo não gerou t mais novo; mantendo runtime atual")
            return runtime_token if valid_runtime_token(runtime_token) else None
    except (TypeError, ValueError):
        pass

    persist_runtime_token(refreshed)
    return refreshed


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
        "tuya_selfheal_check_failures_total": ("counter", "Rodadas em que a checagem do HA falhou"),
        "tuya_selfheal_last_run_timestamp": ("gauge", "Unix time da última execução"),
        "tuya_selfheal_last_heal_timestamp": ("gauge", "Unix time do último heal"),
        "tuya_selfheal_healthy": ("gauge", "1=integração Tuya saudável no HA"),
        "tuya_selfheal_last_mode": (
            "gauge",
            "Último modo de heal: 0=none 1=hot 2=core_restart 3=docker_restart 4=reload",
        ),
        "tuya_selfheal_reloads_total": ("counter", "Reloads de config entry Tuya aplicados"),
        "tuya_entry_state_code": (
            "gauge",
            "Estado da entry: 0=loaded 1=setup_error 2=setup_retry 3=not_loaded "
            "4=migration_error 5=failed_unload 9=unknown -1=missing",
        ),
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
    """Coleta entry_id, token_info, entry_state e disponibilidade das entidades tuya."""
    script = (
        "import json\n"
        "ce=json.load(open('/config/.storage/core.config_entries'))\n"
        "e=[x for x in ce['data']['entries'] if x['domain']=='tuya']\n"
        "out={'entry_id':None,'token_info':{},'entry_state':None}\n"
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
        # Estados + state da config entry via JWT local
        jwt_script = (
            "import json,jwt,time,urllib.request\n"
            f"entry={status['entry_id']!r}\n"
            "a=json.load(open('/config/.storage/auth'))\n"
            "tok=next(t for t in a['data']['refresh_tokens']\n"
            "         if t.get('token_type')=='long_lived_access_token')\n"
            "j=jwt.encode({'iss':tok['id'],'iat':int(time.time()),\n"
            "              'exp':int(time.time())+300},tok['jwt_key'],algorithm='HS256')\n"
            "hdr={'Authorization':'Bearer '+j}\n"
            "req=urllib.request.Request('http://127.0.0.1:8123/api/states',\n"
            "    headers=hdr)\n"
            "st=json.load(urllib.request.urlopen(req,timeout=30))\n"
            "estate=None\n"
            "try:\n"
            "    req2=urllib.request.Request(\n"
            "        'http://127.0.0.1:8123/api/config/config_entries/entry',\n"
            "        headers=hdr)\n"
            "    entries=json.load(urllib.request.urlopen(req2,timeout=30))\n"
            "    for ent in entries:\n"
            "        if ent.get('entry_id')==entry:\n"
            "            estate=ent.get('state'); break\n"
            "        if estate is None and ent.get('domain')=='tuya':\n"
            "            estate=ent.get('state')\n"
            "except Exception:\n"
            "    estate=None\n"
            "print(json.dumps({'states':{s['entity_id']:s['state'] for s in st},"
            " 'entry_state':estate}))\n"
        )
        payload = json.loads(docker_py(jwt_script, timeout=180))
        states = payload.get("states") or {}
        status["entry_state"] = payload.get("entry_state")
        status["entities_total"] = len(entity_ids)
        status["entities_active"] = sum(
            1
            for eid in entity_ids
            if states.get(eid) not in (None, "unavailable", "unknown")
        )
    else:
        status["entities_total"] = 0
        status["entities_active"] = 0
        status["entry_state"] = None
    return status


def ha_tuya_status_with_retry(attempts: int = 3, backoff_s: int = 30) -> dict | None:
    """ha_tuya_status com retries; None quando a checagem falhou.

    Sob load alto o docker exec pode estourar timeout — falha de
    monitoramento não pode virar crash da unit nem disparar heal.
    """
    for attempt in range(1, attempts + 1):
        try:
            return ha_tuya_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("Checagem HA falhou (%d/%d): %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(backoff_s)
    return None


def load_runtime_token() -> dict | None:
    try:
        token = json.loads(RUNTIME_TOKENS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return token if valid_runtime_token(token) else None


def backup_config_entries() -> Path:
    backup = CONFIG_ENTRIES.with_name(
        CONFIG_ENTRIES.name + f".tuya-selfheal-{int(time.time())}.bak"
    )
    shutil.copy2(CONFIG_ENTRIES, backup)
    log.info("Backup criado: %s", backup)
    return backup


def inject_token_to_disk(runtime_token: dict) -> dict:
    """Persiste token_info em core.config_entries (host mount). Retorna a entry."""
    config = json.loads(CONFIG_ENTRIES.read_text(encoding="utf-8"))
    entry = inject_token(config, runtime_token)
    tmp = CONFIG_ENTRIES.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.move(tmp, CONFIG_ENTRIES)
    log.info("token_info injetado em disco (t=%s)", runtime_token["t"])
    return entry


def ha_long_lived_jwt() -> str:
    """JWT de short-lived a partir do long-lived access token do HA (no container)."""
    script = (
        "import json,jwt,time\n"
        "a=json.load(open('/config/.storage/auth'))\n"
        "tok=next(t for t in a['data']['refresh_tokens']\n"
        "         if t.get('token_type')=='long_lived_access_token')\n"
        "print(jwt.encode({'iss':tok['id'],'iat':int(time.time()),\n"
        "                  'exp':int(time.time())+300},tok['jwt_key'],algorithm='HS256'))\n"
    )
    return docker_py(script)


def ha_api_request(
    path: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    timeout: int = 60,
) -> tuple[int, str]:
    """Chama API local do HA; retorna (status_http, body_text)."""
    jwt_str = ha_long_lived_jwt()
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {jwt_str}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace") if exc.fp else ""
        return exc.code, detail
    except urllib.error.URLError as exc:
        # HA fechou a conexão no restart — esperado.
        return 0, str(exc.reason if hasattr(exc, "reason") else exc)


def ha_service_available(domain: str, service: str) -> bool:
    code, body = ha_api_request("/api/services")
    if code != 200:
        return False
    try:
        services = json.loads(body)
    except ValueError:
        return False
    for block in services:
        if block.get("domain") == domain and service in (block.get("services") or {}):
            return True
    return False


def apply_heal_hot(runtime_token: dict) -> bool:
    """Atualiza entry em memória via custom component (sem restart)."""
    if not ha_service_available("tuya_token_inject", "apply"):
        log.info("Serviço tuya_token_inject.apply indisponível — hot path skip")
        return False
    code, body = ha_api_request(
        "/api/services/tuya_token_inject/apply",
        method="POST",
        body={"token_info": runtime_token},
        timeout=120,
    )
    if code not in (200, 201):
        log.warning("hot apply HTTP %s: %s", code, body[:300])
        return False
    log.info("hot apply OK (tuya_token_inject.apply, t=%s)", runtime_token["t"])
    return True


def entry_state_code(entry_state: str | None, entry_id: str | None) -> int:
    if not entry_id:
        return -1
    if not entry_state:
        return 9
    return ENTRY_STATE_CODES.get(entry_state.strip().lower(), 9)


def reload_tuya_config_entry(entry_id: str) -> bool:
    """Recarrega a config entry Tuya via API (sem reiniciar o container).

    Resolve setup_error por timeout transitório da API Tuya e estados
    semi-mortos em que o token no storage ainda parece válido.
    """
    if not entry_id:
        return False
    code, body = ha_api_request(
        f"/api/config/config_entries/entry/{entry_id}/reload",
        method="POST",
        body={},
        timeout=120,
    )
    if code in (200, 201):
        log.info("Reload config entry %s OK (http=%s)", entry_id, code)
        return True
    log.warning("Reload config entry %s HTTP %s: %s", entry_id, code, body[:300])
    return False


def apply_heal_core_restart(runtime_token: dict) -> bool:
    """Grava storage e reinicia só o core do HA (container permanece)."""
    inject_token_to_disk(runtime_token)
    code, body = ha_api_request(
        "/api/services/homeassistant/restart",
        method="POST",
        body={},
        timeout=30,
    )
    # HA pode fechar a conexão ao reiniciar (HTTPError / URLError)
    if code in (200, 201, 500, 502, 503, 504) or code == 0:
        log.info("homeassistant.restart solicitado (http=%s)", code)
        return True
    log.warning("core restart HTTP %s: %s", code, body[:200])
    return False


def apply_heal_docker_restart(runtime_token: dict) -> None:
    """Último recurso: grava storage + docker restart."""
    inject_token_to_disk(runtime_token)
    subprocess.run(["docker", "restart", CONTAINER], check=True, timeout=180)
    log.info("Container %s reiniciado (docker restart)", CONTAINER)


def apply_heal(runtime_token: dict) -> int:
    """Aplica heal e retorna MODE_* usado (antes de validar recovery)."""
    backup_config_entries()

    # 1) Hot — preferido
    try:
        if apply_heal_hot(runtime_token):
            # Também espelha em disco para consistência (update_entry já grava;
            # disco host pode estar um tick atrás se o serviço falhar no meio).
            try:
                inject_token_to_disk(runtime_token)
            except Exception as exc:  # noqa: BLE001
                log.warning("Espelho em disco após hot falhou (não-fatal): %s", exc)
            return MODE_HOT
    except Exception as exc:  # noqa: BLE001
        log.warning("hot path falhou: %s", exc)

    # 2) Core restart
    try:
        if apply_heal_core_restart(runtime_token):
            return MODE_CORE_RESTART
    except Exception as exc:  # noqa: BLE001
        log.warning("core_restart path falhou: %s", exc)

    # 3) Docker restart
    apply_heal_docker_restart(runtime_token)
    return MODE_DOCKER_RESTART


def wait_recovery(deadline_s: int = HA_BOOT_WAIT_S, poll_s: int = 5) -> int:
    """Aguarda entidades Tuya voltarem; retorna contagem de ativas."""
    start = time.time()
    active = 0
    while time.time() - start < deadline_s:
        time.sleep(poll_s)
        try:
            active = ha_tuya_status()["entities_active"]
        except Exception:  # noqa: BLE001 - HA ainda subindo
            continue
        if active > 0:
            break
    return active


def wait_recovery_for_mode(mode: int) -> int:
    if mode in (MODE_HOT, MODE_RELOAD):
        return wait_recovery(deadline_s=TUYA_SELFHEAL_HOT_WAIT_S, poll_s=3)
    if mode == MODE_CORE_RESTART:
        return wait_recovery(deadline_s=min(HA_BOOT_WAIT_S, 180), poll_s=5)
    return wait_recovery(deadline_s=HA_BOOT_WAIT_S, poll_s=10)


# ------------------------------------------------------------------------ main


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "runs_total": 0,
            "heals_total": 0,
            "heal_failures_total": 0,
            "reloads_total": 0,
            "last_heal_timestamp": 0,
            "heal_history": [],
        }


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


def _prom_snapshot(
    state: dict,
    *,
    healthy: int,
    ha_remaining: float,
    runtime_token: dict | None,
    status: dict | None,
    last_mode: int,
) -> dict:
    return {
        "tuya_selfheal_runs_total": state["runs_total"],
        "tuya_selfheal_heals_total": state["heals_total"],
        "tuya_selfheal_heal_failures_total": state["heal_failures_total"],
        "tuya_selfheal_reloads_total": state.get("reloads_total", 0),
        "tuya_selfheal_check_failures_total": state.get("check_failures_total", 0),
        "tuya_selfheal_last_run_timestamp": int(time.time()),
        "tuya_selfheal_last_heal_timestamp": state.get("last_heal_timestamp", 0),
        "tuya_selfheal_healthy": healthy,
        "tuya_selfheal_last_mode": last_mode,
        "tuya_entry_state_code": entry_state_code(
            (status or {}).get("entry_state"),
            (status or {}).get("entry_id"),
        ),
        "tuya_token_remaining_minutes": round(ha_remaining, 1),
        "tuya_bridge_token_remaining_minutes": round(
            token_remaining_minutes(runtime_token) if runtime_token else -1, 1
        ),
        "tuya_entities_active": (status or {}).get("entities_active", 0),
        "tuya_entities_total": (status or {}).get("entities_total", 0),
    }


def main() -> int:
    state = load_state()
    state["runs_total"] += 1
    state["heal_history"] = prune_heal_history(state.get("heal_history", []))
    state.setdefault("reloads_total", 0)

    status = ha_tuya_status_with_retry()
    runtime_token = load_runtime_token()

    if status is None:
        state["check_failures_total"] = state.get("check_failures_total", 0) + 1
        save_state(state)
        write_prom(
            _prom_snapshot(
                state,
                healthy=0,
                ha_remaining=-1,
                runtime_token=runtime_token,
                status=None,
                last_mode=int(state.get("last_mode", MODE_NONE)),
            )
        )
        log.error("Checagem do HA indisponível; heal não avaliado nesta rodada")
        return 1

    ha_token = status.get("token_info") or {}
    ha_remaining = token_remaining_minutes(ha_token)
    integration_dead = (
        status.get("entities_total", 0) > 0 and status.get("entities_active", 0) == 0
    ) or (status.get("entry_state") or "").lower() == "setup_error"

    # Antes de decidir heal: renova o runtime token se o HA está na janela soft
    # OU se a integração está morta (0 ativas / setup_error).
    try:
        runtime_token = (
            ensure_fresh_runtime_token(
                ha_token, runtime_token, force=integration_dead
            )
            or runtime_token
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ensure_fresh_runtime_token falhou (não-fatal): %s", exc)

    last_mode = int(state.get("last_mode", MODE_NONE))
    acted = False
    reason = "ok"

    # --- 1) Reload path (setup_error / 0 ativas com token ainda válido) ---
    do_reload, reload_reason = should_reload_entry(
        status.get("entry_state"),
        status["entities_active"],
        status["entities_total"],
        ha_remaining,
    )
    # Reload só faz sentido se o token no storage ainda pode autenticar.
    # Token já morto → pular direto para inject (reload só gasta tempo).
    if do_reload and status.get("entry_id") and ha_remaining > 0:
        entities_before_reload = int(status["entities_active"])
        log.info(
            "Tuya reload: %s/%s ativas | state=%s | %s",
            status["entities_active"],
            status["entities_total"],
            status.get("entry_state"),
            reload_reason,
        )
        try:
            if reload_tuya_config_entry(status["entry_id"]):
                state["reloads_total"] = state.get("reloads_total", 0) + 1
                last_mode = MODE_RELOAD
                state["last_mode"] = last_mode
                acted = True
                active = wait_recovery_for_mode(MODE_RELOAD)
                status = ha_tuya_status_with_retry() or status
                ha_token = status.get("token_info") or {}
                ha_remaining = token_remaining_minutes(ha_token)
                if active > 0:
                    # Zumbi (setup_error + entidades já ativas): reload pode
                    # "suceder" sem recuperar nada e não deve queimar MAX_HEALS.
                    if reload_counts_toward_heal_budget(
                        entities_before_reload, active
                    ):
                        state["heals_total"] += 1
                        state["last_heal_timestamp"] = int(time.time())
                        state["heal_history"].append(time.time())
                        log.info(
                            "Heal OK (reload): %s entidades ativas | token resta %.0f min | state=%s",
                            active,
                            ha_remaining,
                            status.get("entry_state"),
                        )
                    else:
                        log.info(
                            "Reload applied (not counted toward heal budget): "
                            "%s→%s ativas | token resta %.0f min | state=%s",
                            entities_before_reload,
                            active,
                            ha_remaining,
                            status.get("entry_state"),
                        )
                else:
                    log.warning(
                        "Reload aplicado mas entidades ainda 0 — tentando inject se bridge mais novo"
                    )
            else:
                log.warning("Reload da entry falhou; seguindo para inject se aplicável")
        except Exception:  # noqa: BLE001
            state["heal_failures_total"] += 1
            log.exception("Reload da entry falhou com exceção")

    # --- 2) Token inject path ---
    # Reavalia após possível reload (status/token podem ter mudado).
    heal, reason = should_heal(
        ha_token,
        runtime_token,
        status["entities_active"],
        len(state["heal_history"]),
        entities_total=status.get("entities_total", 0),
    )
    log.info(
        "Tuya: %s/%s ativas | state=%s | token HA resta %.0f min | heal=%s (%s)",
        status["entities_active"],
        status["entities_total"],
        status.get("entry_state"),
        token_remaining_minutes(ha_token),
        heal,
        reason,
    )

    # Se reload já restaurou entidades, não injeta de novo na mesma rodada.
    already_healthy = status["entities_active"] > 0 and token_remaining_minutes(ha_token) > 0
    if heal and not already_healthy:
        try:
            last_mode = apply_heal(runtime_token)
            state["last_mode"] = last_mode
            acted = True
            active = wait_recovery_for_mode(last_mode)
            if active > 0:
                state["heals_total"] += 1
                state["last_heal_timestamp"] = int(time.time())
                state["heal_history"].append(time.time())
                status = ha_tuya_status_with_retry() or status
                ha_token = status.get("token_info") or {}
                mode_name = {
                    MODE_HOT: "hot",
                    MODE_CORE_RESTART: "core_restart",
                    MODE_DOCKER_RESTART: "docker_restart",
                    MODE_RELOAD: "reload",
                }.get(last_mode, str(last_mode))
                log.info(
                    "Heal OK (%s): %s entidades ativas | token resta %.0f min",
                    mode_name,
                    active,
                    token_remaining_minutes(ha_token),
                )
            else:
                state["heal_failures_total"] += 1
                log.error(
                    "Heal aplicado (mode=%s) mas entidades não voltaram — reauth QR necessária",
                    last_mode,
                )
        except Exception:  # noqa: BLE001
            state["heal_failures_total"] += 1
            log.exception("Heal falhou")

    save_state(state)
    ha_remaining = token_remaining_minutes(ha_token)
    # Saudável = entidades respondendo E access token ainda válido.
    healthy = int(status["entities_active"] > 0 and ha_remaining > 0)
    write_prom(
        _prom_snapshot(
            state,
            healthy=healthy,
            ha_remaining=ha_remaining,
            runtime_token=runtime_token,
            status=status,
            last_mode=int(state.get("last_mode", MODE_NONE)),
        )
    )
    if not healthy and not acted:
        log.warning(
            "Tuya degradado sem ação: ativas=%s state=%s remaining=%.0f min reason=%s",
            status["entities_active"],
            status.get("entry_state"),
            ha_remaining,
            reason,
        )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
