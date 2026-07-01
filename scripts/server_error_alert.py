#!/usr/bin/env python3
"""
server_error_alert.py
Motor de alertas de erros do servidor para o homelab Eddie.

Fontes de alertas:
  1. HTTP POST /alert na porta 5002 (webhook Alertmanager)
  2. journalctl -f streaming (prioridade error, todos os serviços)

Destino: Telegram (canal configurável via TELEGRAM_ERROR_CHAT_ID)

Callback inline "📋 Gerar análise":
  - Cria ticket no GLPI (ITSM)
  - Cria página no Wiki.js (base de conhecimento)
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote


# ─── Configuração ────────────────────────────────────────────────────────────
def _load_secrets_env() -> dict[str, str]:
    env_file = Path.home() / ".config" / "homelab" / "secrets.env"
    if not env_file.exists():
        return {}
    out: dict[str, str] = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


_env = _load_secrets_env()

BOT_TOKEN       = os.environ.get("TELEGRAM_BOT_TOKEN",    _env.get("TELEGRAM_BOT_TOKEN",    ""))
ERROR_CHAT_ID   = int(os.environ.get("TELEGRAM_ERROR_CHAT_ID", _env.get("TELEGRAM_ERROR_CHAT_ID", "948686300")))
WEBHOOK_PORT    = int(os.environ.get("SERVER_ALERT_PORT", "5002"))
DEDUP_WINDOW    = int(os.environ.get("DEDUP_WINDOW_SEC",  "1800"))  # 30 min

GLPI_URL  = os.environ.get("GLPI_URL",  "http://localhost:18092")
GLPI_USER = os.environ.get("GLPI_USER", "glpi")
GLPI_PASS = os.environ.get(
    "GLPI_PASS",
    os.environ.get(
        "GLPI_PASSWORD",
        _env.get("GLPI_PASS", _env.get("GLPI_PASSWORD", "glpi")),
    ),
)
GLPI_APP_TOKEN = os.environ.get(
    "GLPI_APP_TOKEN",
    _env.get("GLPI_APP_TOKEN", ""),
)

WIKIJS_AGENT_URL  = os.environ.get("WIKIJS_AGENT_URL",  "http://127.0.0.1:8503")
WIKIJS_PUBLIC_URL = os.environ.get("WIKIJS_PUBLIC_URL", "https://wiki.rpa4all.com")
WIKIJS_LOCALE = os.environ.get(
    "WIKIJS_LOCALE",
    os.environ.get(
        "WIKI_LOCALE",
        _env.get("WIKIJS_LOCALE", _env.get("WIKI_LOCALE", "pt")),
    ),
)

# Serviços ruidosos que não devem gerar alertas (prefixos/padrões)
_NOISE_UNITS = {
    "kernel", "init.scope", "-.scope", "server-error-alert",
    "dbus", "systemd-", "rsyslog", "cron", "sshd",
    "smartmontools", "smartd", "accounts-daemon", "polkit",
    "rtkit-daemon", "udisks2", "avahi-daemon", "colord",
}


# ─── Dedup ───────────────────────────────────────────────────────────────────
_dedup: dict[str, float] = {}
_dedup_lock = threading.Lock()


def _should_send(key: str) -> bool:
    now = time.time()
    with _dedup_lock:
        if now - _dedup.get(key, 0) < DEDUP_WINDOW:
            return False
        _dedup[key] = now
        return True


# ─── Contexto de alertas (para callback) ─────────────────────────────────────
_alert_context: dict[str, dict] = {}  # alert_key → {service, message, timestamp}
_ctx_lock = threading.Lock()


def _store_context(key: str, service: str, message: str) -> None:
    with _ctx_lock:
        _alert_context[key] = {
            "service": service,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }


def _get_context(key: str) -> dict:
    with _ctx_lock:
        return _alert_context.get(key, {})


# ─── Telegram ────────────────────────────────────────────────────────────────
def _tg(method: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[telegram] {method} erro: {e}", flush=True)
        return None


def _html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def send_alert(service: str, message: str, alert_key: str, severity: str = "error") -> int | None:
    """Envia alerta ao Telegram com botão inline. Retorna message_id."""
    icon = "🔴" if severity in ("critical", "error") else "🟡"
    text = (
        f"{icon} <b>ERRO — {_html(service)}</b>\n\n"
        f"<pre>{_html(message[:800])}</pre>"
    )
    result = _tg("sendMessage", {
        "chat_id": ERROR_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{
            "text": "📋 Gerar análise",
            "callback_data": f"analyze:{alert_key[:55]}",
        }]]},
    })
    if result and result.get("ok"):
        return result["result"]["message_id"]
    return None


def _esc(s: str) -> str:
    return s.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`")


def _edit_message(chat_id: int, msg_id: int, text: str) -> None:
    _tg("editMessageText", {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "parse_mode": "HTML",
    })


def _answer_callback(callback_id: str, text: str, alert: bool = False) -> None:
    _tg("answerCallbackQuery", {
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": alert,
    })


# ─── GLPI ────────────────────────────────────────────────────────────────────
def _normalize_base_url(url: str, *suffixes: str) -> str:
    clean = url.strip().rstrip("/")
    lowered = clean.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix.lower()):
            clean = clean[: -len(suffix)].rstrip("/")
            lowered = clean.lower()
    return clean


def _glpi_base_url(url: str | None = None) -> str:
    return _normalize_base_url(url or GLPI_URL, "/apirest.php", "/index.php")


def _glpi_api_url(path: str, url: str | None = None) -> str:
    return f"{_glpi_base_url(url)}/apirest.php/{path.lstrip('/')}"


def _glpi_ticket_url(ticket_id: int, url: str | None = None) -> str:
    return f"{_glpi_base_url(url)}/front/ticket.form.php?id={ticket_id}"


def _glpi_headers(*, session: str | None = None, content_type: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if session:
        headers["Session-Token"] = session
    if GLPI_APP_TOKEN:
        headers["App-Token"] = GLPI_APP_TOKEN
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _glpi_init_session() -> str | None:
    creds = base64.b64encode(f"{GLPI_USER}:{GLPI_PASS}".encode()).decode()
    req = urllib.request.Request(
        _glpi_api_url("initSession"),
        headers={
            **_glpi_headers(),
            "Authorization": f"Basic {creds}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read()).get("session_token")
    except Exception as e:
        print(f"[glpi] initSession falhou: {e}", flush=True)
        return None


def _glpi_kill_session(session: str) -> None:
    req = urllib.request.Request(
        _glpi_api_url("killSession"),
        headers=_glpi_headers(session=session),
    )
    try:
        urllib.request.urlopen(req, timeout=3).close()
    except Exception:
        pass


def create_glpi_ticket(title: str, description: str) -> int | None:
    """Cria incidente no GLPI e retorna o ID."""
    session = _glpi_init_session()
    if not session:
        return None
    try:
        body = json.dumps({"input": {
            "name": title[:250],
            "content": description,
            "type": 1,       # Incident
            "urgency": 3,    # Medium
            "impact": 3,
            "priority": 3,
            "status": 1,     # New
        }}).encode()
        req = urllib.request.Request(
            _glpi_api_url("Ticket"),
            data=body,
            headers=_glpi_headers(session=session, content_type="application/json"),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("id")
    except Exception as e:
        print(f"[glpi] criar ticket falhou: {e}", flush=True)
        return None
    finally:
        _glpi_kill_session(session)


# ─── Wiki.js (via wiki agent em 127.0.0.1:8503) ──────────────────────────────
def _wikijs_agent_base_url(url: str | None = None) -> str:
    return _normalize_base_url(url or WIKIJS_AGENT_URL, "/wiki/raw")


def _wikijs_raw_url(url: str | None = None) -> str:
    return f"{_wikijs_agent_base_url(url)}/wiki/raw"


def _build_wikijs_public_url(wiki_path: str, locale: str | None = None, base_url: str | None = None) -> str:
    clean_path = "/".join(part for part in wiki_path.strip("/").split("/") if part)
    locale_slug = (locale or WIKIJS_LOCALE or "pt").strip("/")
    root = (base_url or WIKIJS_PUBLIC_URL).rstrip("/")
    if root.endswith(f"/{locale_slug}"):
        return f"{root}/{quote(clean_path, safe='/')}"
    return f"{root}/{locale_slug}/{quote(clean_path, safe='/')}"


def create_wikijs_page(title: str, content: str, path: str) -> bool:
    """Delega criação de página ao wiki agent (/wiki/raw)."""
    body = json.dumps({
        "topic": title,
        "raw_text": content,
        "wiki_path": path,
        "tags": ["incidente", "alerta-automatico"],
        "locale": WIKIJS_LOCALE,
    }).encode()
    req = urllib.request.Request(
        _wikijs_raw_url(),
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("ok", False)
    except Exception as e:
        print(f"[wikijs] wiki agent falhou: {e}", flush=True)
        return False


# ─── Análise ─────────────────────────────────────────────────────────────────
def _get_logs(service: str, lines: int = 60) -> str:
    try:
        r = subprocess.run(
            ["journalctl", "-u", service, "-n", str(lines), "--no-pager", "-q"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() or "(sem logs)"
    except Exception:
        return "(falha ao ler logs)"


def _build_analysis(service: str, error_msg: str, ts: str) -> str:
    logs = _get_logs(service)
    return (
        f"# Incidente: {service}\n\n"
        f"**Detectado:** {ts}\n\n"
        f"## Erro\n```\n{error_msg[:600]}\n```\n\n"
        f"## Últimos logs\n```\n{logs[:3000]}\n```\n\n"
        f"## Ações sugeridas\n"
        f"- `journalctl -u {service} -n 100 --no-pager`\n"
        f"- `systemctl status {service}`\n"
        f"- `systemctl restart {service}`\n"
    )


# ─── Handler de callback ──────────────────────────────────────────────────────
def _handle_callback(alert_key: str, callback_id: str, msg_id: int, chat_id: int) -> None:
    _answer_callback(callback_id, "⏳ Gerando análise, aguarde...")

    ctx = _get_context(alert_key)
    service = ctx.get("service", alert_key)
    error_msg = ctx.get("message", "")
    ts = ctx.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))

    analysis = _build_analysis(service, error_msg, ts)
    safe = service.replace("@", "_").replace(".", "_").replace("/", "_")
    wiki_path = f"incidentes/{safe}-{int(time.time())}"

    ticket_id = create_glpi_ticket(
        title=f"Erro detectado: {service}",
        description=analysis,
    )
    wiki_ok = create_wikijs_page(
        title=f"Incidente: {service} ({time.strftime('%Y-%m-%d', time.gmtime())})",
        content=analysis,
        path=wiki_path,
    )

    lines = [f"✅ <b>Análise gerada para {_html(service)}</b>\n"]
    if ticket_id:
        lines.append(f"🎫 GLPI #{ticket_id}: {_glpi_ticket_url(ticket_id)}")
    else:
        lines.append("⚠️ Falha ao criar ticket GLPI")
    if wiki_ok:
        lines.append(f"📚 Wiki: {_build_wikijs_public_url(wiki_path)}")
    else:
        lines.append("⚠️ Falha ao criar página Wiki.js")

    _edit_message(chat_id, msg_id, "\n".join(lines))
    print(f"[callback] análise criada para {service} — GLPI #{ticket_id}", flush=True)


# ─── Webhook Alertmanager ────────────────────────────────────────────────────
class _AlertWebhook(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        self.send_response(200)
        self.end_headers()

        path = self.path.split("?")[0]

        if path == "/callback":
            # Callback vindo do eddie-telegram-bot (analyze: button)
            try:
                data = json.loads(body)
                alert_key = data.get("alert_key", "")
                callback_id = data.get("callback_id", "")
                msg_id = data.get("message_id")
                chat_id = data.get("chat_id")
                if alert_key and msg_id and chat_id:
                    threading.Thread(
                        target=_handle_callback,
                        args=(alert_key, callback_id, msg_id, chat_id),
                        daemon=True,
                    ).start()
            except Exception as e:
                print(f"[callback] erro: {e}", flush=True)
            return

        # Webhook Alertmanager (POST /alert ou /)
        try:
            data = json.loads(body)
        except Exception:
            return

        for alert in data.get("alerts", []):
            if alert.get("status") != "firing":
                continue
            labels = alert.get("labels", {})
            ann = alert.get("annotations", {})
            alertname = labels.get("alertname", "Alerta")
            service = labels.get("service", labels.get("job", alertname))
            summary = ann.get("summary", alertname)
            description = ann.get("description", "")
            severity = labels.get("severity", "warning")
            full_msg = f"{summary}\n{description}".strip()

            key = f"alertmanager:{alertname}:{service}"
            if not _should_send(key):
                continue

            _store_context(key, service, full_msg)
            send_alert(service=alertname, message=full_msg, alert_key=key, severity=severity)
            print(f"[webhook] alerta Alertmanager: {alertname} ({service})", flush=True)


def _run_webhook() -> None:
    server = HTTPServer(("127.0.0.1", WEBHOOK_PORT), _AlertWebhook)
    print(f"[webhook] ouvindo em 127.0.0.1:{WEBHOOK_PORT}", flush=True)
    server.serve_forever()


# ─── journalctl streaming ────────────────────────────────────────────────────
def _is_noisy(unit: str) -> bool:
    unit_lower = unit.lower()
    return any(n in unit_lower for n in _NOISE_UNITS)


def _journal_monitor() -> None:
    cmd = ["journalctl", "-f", "-o", "json", "-p", "err", "--no-pager"]
    print(f"[journal] monitorando erros de todos os serviços...", flush=True)
    while True:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, errors="replace")
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                priority = int(entry.get("PRIORITY", "7"))
                if priority > 3:
                    continue

                unit = (
                    entry.get("_SYSTEMD_UNIT", "")
                    or entry.get("SYSLOG_IDENTIFIER", "")
                    or ""
                )
                if not unit or _is_noisy(unit):
                    continue

                message = entry.get("MESSAGE", "")
                if not message:
                    continue

                # Dedup por template de serviço (sem instance)
                unit_base = unit.split("@")[0] if "@" in unit else unit.split(".")[0]
                key = f"journal:{unit_base}"
                if not _should_send(key):
                    continue

                _store_context(key, unit, message)
                send_alert(service=unit, message=message[:500], alert_key=key)
                print(f"[journal] erro detectado: {unit}", flush=True)

        except Exception as e:
            print(f"[journal] erro fatal: {e} — reiniciando em 10s", flush=True)
            time.sleep(10)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[server-error-alert] iniciando...", flush=True)
    print(f"  chat_id destino: {ERROR_CHAT_ID}", flush=True)
    print(f"  GLPI: {GLPI_URL}", flush=True)
    print(f"  Wiki.js agent: {WIKIJS_AGENT_URL}/wiki/raw → {WIKIJS_PUBLIC_URL}", flush=True)
    print("  callbacks: recebidos via eddie-telegram-bot → POST /callback", flush=True)

    for name, target in [
        ("webhook", _run_webhook),
        ("journal", _journal_monitor),
    ]:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[server-error-alert] encerrado", flush=True)
