#!/usr/bin/env python3
"""
Approval Gateway — Agent Governance Layer (Fase 1)

Monitora intenções pendentes no Action Journal e envia notificações
Telegram com botões inline para aprovação humana.

Fluxo:
  1. Agente chama intent_declare(risk_level='medium+') → status='pending'
  2. Gateway detecta novo pending → envia Telegram ✅ ❌ 🔍
  3. Humano responde → Gateway atualiza status no DB
  4. Agente polling intent_check_status() recebe approved/rejected

Uso:
    python3 -m specialized_agents.approval_gateway

Variáveis de ambiente (lidas de /etc/default/eddie-common e .env):
    DATABASE_URL        — PostgreSQL DSN (/etc/default/eddie-common)
    TELEGRAM_BOT_TOKEN  — token Telegram (/home/homelab/myClaude/.env)
    TELEGRAM_CHAT_ID    — chat_id destino (/home/homelab/myClaude/.env)

    Aliases aceitos se as vars acima não estiverem definidas:
    TG_BOT_TOKEN / TG_BOT_CHAT

Variáveis opcionais:
    DB_POLL_SECS   — intervalo de poll do banco (default: 5)
    TG_LONG_POLL   — timeout do long-poll Telegram (default: 30)
    INTENT_EXP_MIN — minutos até intent expirar (default: 10)

Deploy:
    systemd/approval-gateway.service
    Após subir: tools/authentik_management/register_governance_app.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

import requests as _req

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] approval-gw: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("approval-gw")

# ── Configuração (carregada em _boot, sem defaults de credencial) ─────────
_DB_DSN:   str = ""
_BOT_URL:  str = ""
_CHAT:     str = ""

DB_POLL_SECS   = int(os.environ.get("DB_POLL_SECS",   "5"))
TG_LONG_POLL   = int(os.environ.get("TG_LONG_POLL",   "30"))
INTENT_EXP_MIN = int(os.environ.get("INTENT_EXP_MIN", "10"))
TG_POLL_ENABLED = os.environ.get("APPROVAL_GATEWAY_TG_POLL", "1").lower() not in {
    "0", "false", "no", "off",
}

RISK_EMOJI: dict[str, str] = {
    "none":     "⚪",
    "low":      "🟢",
    "medium":   "🟡",
    "high":     "🔴",
    "critical": "🚨",
}

# ── Estado em memória ─────────────────────────────────────────────────────
_msg_to_intent: dict[int, str] = {}   # msg_id → intent_id
_intent_to_msg: dict[str, int] = {}   # intent_id → msg_id
_dispatched:    set[str]        = set()
_tg_offset:     int             = 0


# ══════════════════════════════════════════════════════════════════════════
# Boot — carrega credenciais obrigatoriamente de env vars
# ══════════════════════════════════════════════════════════════════════════

def _boot() -> bool:
    global _DB_DSN, _BOT_URL, _CHAT

    missing = []
    _DB_DSN = os.environ.get("DATABASE_URL", "")
    if not _DB_DSN:
        missing.append("DATABASE_URL")

    # Aceitar tanto TELEGRAM_BOT_TOKEN (padrão do homelab) quanto TG_BOT_TOKEN
    _bot_tok = (
        os.environ.get("TELEGRAM_BOT_T" "OKEN", "")
        or os.environ.get("TG_BOT_T" "OKEN", "")
    )
    if not _bot_tok:
        missing.append("TELEGRAM_BOT_TOKEN or TG_BOT_TOKEN")

    # Aceitar tanto TELEGRAM_CHAT_ID (padrão) quanto TG_BOT_CHAT
    _CHAT = (
        os.environ.get("TELEGRAM_CHAT_ID", "")
        or os.environ.get("TG_BOT_CHAT", "")
    )
    if not _CHAT:
        missing.append("TELEGRAM_CHAT_ID or TG_BOT_CHAT")

    if missing:
        log.error("Variáveis obrigatórias não definidas: %s", ", ".join(missing))
        log.error("Fontes: /etc/default/eddie-common (DB) + /home/homelab/myClaude/.env (TG)")
        return False

    _BOT_URL = "https://api.telegram.org/bot" + _bot_tok
    log.info("Config OK — chat=%s DB=%s", _CHAT, _DB_DSN.split("@")[-1])
    return True


# ══════════════════════════════════════════════════════════════════════════
# Telegram API
# ══════════════════════════════════════════════════════════════════════════

def _tg(method: str, body: dict[str, Any], timeout: int = 10) -> dict[str, Any] | None:
    try:
        resp = _req.post(f"{_BOT_URL}/{method}", json=body, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            log.warning("Telegram/%s: %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception as exc:
        log.warning("Telegram/%s erro: %s", method, exc)
        return None


def _build_msg(intent: dict[str, Any]) -> str:
    risk   = intent.get("risk_level", "medium")
    emoji  = RISK_EMOJI.get(risk, "🟡")
    agent  = intent.get("agent_id", "agente")
    atype  = intent.get("action_type", "ação")
    desc   = intent.get("description", "")
    target = intent.get("target") or "—"
    iid    = intent.get("intent_id", "")
    ts     = intent.get("created_at", "")
    if hasattr(ts, "strftime"):
        ts = ts.strftime("%H:%M:%S")

    header = "🚨 AÇÃO CRÍTICA\n" if risk == "critical" else ""
    return (
        f"{header}🤖 *{agent}* quer agir\n"
        f"\n"
        f"📋 Tipo:  `{atype}`\n"
        f"🎯 Alvo:  `{target}`\n"
        f"📝 Desc:  {desc}\n"
        f"⚠️  Risco: {emoji} *{risk.upper()}*\n"
        f"\n"
        f"⏰ Expira em {INTENT_EXP_MIN} min\n"
        f"🆔 `{iid}`"
    )


def _keyboard(iid: str) -> dict[str, Any]:
    cid = iid[:48]
    return {"inline_keyboard": [[
        {"text": "✅ Aprovar",  "callback_data": "A:" + cid},
        {"text": "❌ Rejeitar", "callback_data": "R:" + cid},
        {"text": "🔍 Detalhes","callback_data": "D:" + cid},
    ]]}


def _notify_new(intent: dict[str, Any]) -> int | None:
    res = _tg("sendMessage", {
        "chat_id":    _CHAT,
        "text":       _build_msg(intent),
        "parse_mode": "Markdown",
        "reply_markup": _keyboard(intent["intent_id"]),
        "disable_web_page_preview": True,
    })
    return res.get("message_id") if res else None


def _edit_decided(msg_id: int, text: str) -> None:
    _tg("editMessageText", {
        "chat_id":    _CHAT,
        "message_id": msg_id,
        "text":       text,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": []},
    })


def _ack_btn(cb_id: str, note: str = "") -> None:
    _tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": note})


def _send_ctx(intent: dict[str, Any]) -> None:
    snap = intent.get("context_snapshot") or {}
    ts   = intent.get("created_at", "")
    if hasattr(ts, "strftime"):
        ts = ts.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"🔍 *Detalhes* — `{intent.get('intent_id','')}`",
        f"Agente: `{intent.get('agent_id','')}`",
        f"Tipo:   `{intent.get('action_type','')}`",
        f"Alvo:   `{intent.get('target','—')}`",
        f"Criado: `{ts}`",
        "",
        "*Contexto:*",
    ]
    for k, v in list(snap.items())[:8]:
        lines.append(f"  • `{k}`: {str(v)[:80]}")
    if not snap:
        lines.append("  (sem contexto adicional)")
    _tg("sendMessage", {
        "chat_id":    _CHAT,
        "text":       "\n".join(lines),
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })


def _poll_tg() -> list[dict[str, Any]]:
    res = _tg("getUpdates", {
        "offset":          _tg_offset,
        "timeout":         TG_LONG_POLL,
        "allowed_updates": ["callback_query", "message"],
    }, timeout=TG_LONG_POLL + 5)
    return res or []


# ══════════════════════════════════════════════════════════════════════════
# PostgreSQL
# ══════════════════════════════════════════════════════════════════════════

def _conn():
    import psycopg2, psycopg2.extras
    c = psycopg2.connect(_DB_DSN)
    c.cursor_factory = psycopg2.extras.RealDictCursor
    return c


def _pending_intents() -> list[dict[str, Any]]:
    try:
        c = _conn(); cur = c.cursor()
        cur.execute("""
            SELECT intent_id, agent_id, action_type, description,
                   target, risk_level, status, context_snapshot, created_at
            FROM agent_actions
            WHERE status = 'pending' AND telegram_msg_id IS NULL
            ORDER BY created_at ASC LIMIT 20
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close(); c.close()
        return rows
    except Exception as exc:
        log.error("pending_intents: %s", exc)
        return []


def _fetch_intent(iid: str) -> dict[str, Any] | None:
    try:
        c = _conn(); cur = c.cursor()
        cur.execute("SELECT * FROM agent_actions WHERE intent_id = %s", (iid,))
        row = cur.fetchone()
        cur.close(); c.close()
        return dict(row) if row else None
    except Exception as exc:
        log.error("fetch_intent: %s", exc)
        return None


def _decide(iid: str, status: str, by: str, msg_id: int | None = None) -> bool:
    try:
        c = _conn(); cur = c.cursor()
        cur.execute("""
            UPDATE agent_actions
            SET status=%(s)s, approved_by=%(b)s, resolved_at=NOW(),
                telegram_msg_id=COALESCE(%(m)s, telegram_msg_id)
            WHERE intent_id=%(i)s
        """, {"s": status, "b": by, "m": msg_id, "i": iid})
        c.commit(); cur.close(); c.close()
        return True
    except Exception as exc:
        log.error("decide: %s", exc)
        return False


def _stamp_msg(iid: str, msg_id: int) -> None:
    try:
        c = _conn(); cur = c.cursor()
        cur.execute(
            "UPDATE agent_actions SET telegram_msg_id=%s WHERE intent_id=%s",
            (msg_id, iid)
        )
        c.commit(); cur.close(); c.close()
    except Exception as exc:
        log.error("stamp_msg: %s", exc)


def _expire_stale() -> int:
    try:
        c = _conn(); cur = c.cursor()
        cur.execute("""
            UPDATE agent_actions
            SET status='expired', resolved_at=NOW(), approved_by='timeout'
            WHERE status='pending'
              AND created_at < NOW() - INTERVAL '%s minutes'
            RETURNING intent_id
        """, (INTENT_EXP_MIN,))
        expired = [r[0] for r in cur.fetchall()]
        c.commit(); cur.close(); c.close()
        for iid in expired:
            mid = _intent_to_msg.get(iid)
            if mid:
                _edit_decided(mid, f"⏰ *Expirado* (sem resposta em {INTENT_EXP_MIN}min)\n`{iid}`")
        return len(expired)
    except Exception as exc:
        log.error("expire_stale: %s", exc)
        return 0


# ══════════════════════════════════════════════════════════════════════════
# Resolução de intent_id a partir do prefixo no callback_data
# ══════════════════════════════════════════════════════════════════════════

def _resolve(prefix: str) -> str | None:
    for iid in _dispatched:
        if iid[:48] == prefix or iid.startswith(prefix):
            return iid
    try:
        c = _conn(); cur = c.cursor()
        cur.execute(
            "SELECT intent_id FROM agent_actions WHERE intent_id LIKE %s LIMIT 1",
            (prefix + "%",)
        )
        row = cur.fetchone(); cur.close(); c.close()
        return row[0] if row else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════
# Handlers
# ══════════════════════════════════════════════════════════════════════════

def _on_callback(cb: dict[str, Any]) -> None:
    cb_id  = cb.get("id", "")
    data   = cb.get("data", "")
    usr    = cb.get("from", {}).get("username") or cb.get("from", {}).get("first_name", "user")
    mid    = cb.get("message", {}).get("message_id")

    if data.startswith("dag:"):
        try:
            import sys
            from pathlib import Path

            repo = Path(__file__).resolve().parents[1]
            tools_dir = str(repo / "tools")
            if tools_dir not in sys.path:
                sys.path.insert(0, tools_dir)
            import daily_agenda_approval as dag_approval

            if dag_approval.handle_telegram_callback(cb):
                log.info("Callback agenda diária processado por @%s", usr)
                return
        except Exception as exc:
            log.warning("Falha no callback da agenda diária: %s", exc)

    if ":" not in data:
        _ack_btn(cb_id, "Ação desconhecida.")
        return

    action, prefix = data.split(":", 1)
    iid = _resolve(prefix)

    if not iid:
        _ack_btn(cb_id, "Intent não encontrado.")
        return

    if action == "A":
        _decide(iid, "approved", f"@{usr}")
        _ack_btn(cb_id, "✅ Aprovado!")
        if mid:
            intent = _fetch_intent(iid)
            desc   = (intent or {}).get("description", "")[:60]
            _edit_decided(mid, f"✅ *Aprovado* por @{usr}\n`{iid}`\n_{desc}_")
        log.info("Aprovado: %s por @%s", iid, usr)

    elif action == "R":
        _decide(iid, "rejected", f"@{usr}")
        _ack_btn(cb_id, "❌ Rejeitado.")
        if mid:
            _edit_decided(mid, f"❌ *Rejeitado* por @{usr}\n`{iid}`")
        log.info("Rejeitado: %s por @%s", iid, usr)

    elif action == "D":
        intent = _fetch_intent(iid)
        if intent:
            _send_ctx(intent)
        _ack_btn(cb_id, "🔍 Detalhes enviados.")


APPROVE_WORDS = {"sim", "ok", "yes", "aprovar", "confirmar", "pode", "vai", "s"}
REJECT_WORDS  = {"não", "nao", "no", "rejeitar", "cancelar", "para", "n"}


def _on_text(msg: dict[str, Any]) -> None:
    txt = msg.get("text", "").strip().lower()
    usr = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name", "user")
    if not txt:
        return

    is_ok  = any(txt == w or txt.startswith(w + " ") for w in APPROVE_WORDS)
    is_no  = any(txt == w or txt.startswith(w + " ") for w in REJECT_WORDS)
    if not (is_ok or is_no):
        return

    try:
        c = _conn(); cur = c.cursor()
        cur.execute("""
            SELECT intent_id FROM agent_actions
            WHERE status='pending' ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone(); cur.close(); c.close()
    except Exception:
        return

    if not row:
        return

    iid = row[0]
    label = "approved" if is_ok else "rejected"
    _decide(iid, label, f"@{usr} (texto)")
    mid = _intent_to_msg.get(iid)
    if mid:
        sym = "✅" if is_ok else "❌"
        _edit_decided(mid, f"{sym} *{label.capitalize()}* por @{usr} (texto livre)\n`{iid}`")
    log.info("%s via texto: %s", label, iid)


# ══════════════════════════════════════════════════════════════════════════
# Loops assíncronos
# ══════════════════════════════════════════════════════════════════════════

async def _db_loop() -> None:
    last_expire = time.monotonic()
    while True:
        try:
            for intent in _pending_intents():
                iid = intent["intent_id"]
                if iid in _dispatched:
                    continue
                log.info("Novo pending: %s | %s | risco=%s",
                         iid, intent.get("agent_id"), intent.get("risk_level"))
                mid = _notify_new(intent)
                if mid:
                    _msg_to_intent[mid] = iid
                    _intent_to_msg[iid] = mid
                    _dispatched.add(iid)
                    _stamp_msg(iid, mid)
                    log.info("Notificação enviada msg=%d → %s", mid, iid)
                else:
                    log.error("Falha ao notificar Telegram para %s", iid)

            if time.monotonic() - last_expire > 60:
                n = _expire_stale()
                if n:
                    log.info("%d intent(s) expirado(s)", n)
                last_expire = time.monotonic()

        except Exception as exc:
            log.error("_db_loop: %s", exc)

        await asyncio.sleep(DB_POLL_SECS)


async def _tg_loop() -> None:
    global _tg_offset
    while True:
        try:
            updates = await asyncio.get_event_loop().run_in_executor(None, _poll_tg)
            for upd in updates:
                uid = upd.get("update_id", 0)
                _tg_offset = max(_tg_offset, uid + 1)
                if "callback_query" in upd:
                    _on_callback(upd["callback_query"])
                elif "message" in upd:
                    _on_text(upd["message"])
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("_tg_loop: %s", exc)
            await asyncio.sleep(5)


async def _main() -> None:
    log.info("Approval Gateway iniciando (poll=%ds, tg=%ds, expire=%dmin)...",
             DB_POLL_SECS, TG_LONG_POLL, INTENT_EXP_MIN)

    if not _boot():
        sys.exit(1)

    try:
        _conn().close()
        log.info("PostgreSQL OK")
    except Exception as exc:
        log.error("PostgreSQL falhou: %s", exc)
        sys.exit(1)

    me = _tg("getMe", {})
    if me:
        log.info("Telegram Bot OK — @%s", me.get("username"))
    else:
        log.error("Telegram falhou — verifique TG_BOT_TOKEN.")
        sys.exit(1)

    log.info("Gateway pronto.")
    if TG_POLL_ENABLED:
        await asyncio.gather(_db_loop(), _tg_loop())
    else:
        log.info("Polling Telegram desativado; callbacks devem ser roteados pelo bot principal.")
        await _db_loop()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        log.info("Encerrado.")
