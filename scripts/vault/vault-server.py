#!/usr/bin/env python3
"""
Vault UI Server — backend local para o painel HTML5 do pendrive.
Escuta em 127.0.0.1:8765. Serve /mnt/vault/ui/index.html + API REST.
"""

import base64
import hashlib
import hmac
import json
import os
import platform
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_WIN = platform.system() == "Windows"

if _WIN:
    # Windows: vault aberto pelo LibreCrypt como drive letter (padrão V:\)
    VAULT_MOUNT   = Path(os.environ.get("VAULT_DRIVE",      "V:\\"))
    BACKUP_SCRIPT = Path(os.environ.get("VAULT_BACKUP",     ""))   # N/A no Windows
else:
    VAULT_MOUNT   = Path(os.environ.get("VAULT_MOUNT",      "/mnt/vault"))
    BACKUP_SCRIPT = Path(os.environ.get("VAULT_BACKUP",     "/opt/homelab/vault/backup-to-vault.sh"))

VAULT_ENV  = VAULT_MOUNT / "keepass" / "kucoin.env"
STORJ_MANIFEST = VAULT_MOUNT / "keys" / "storj" / "wallet" / "manifest.json"
UI_DIR     = VAULT_MOUNT / "ui"
HOST       = "127.0.0.1"
PORT       = int(os.environ.get("VAULT_PORT", "8765"))
KUCOIN_BASE = "https://api.kucoin.com"


def _vault_ok() -> bool:
    """Verifica se o vault está acessível (multiplataforma)."""
    if _WIN:
        return VAULT_MOUNT.exists() and VAULT_ENV.exists()
    return VAULT_MOUNT.is_mount()


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_storj_status() -> dict:
    wallet_dir = VAULT_MOUNT / "keys" / "storj" / "wallet"
    identity_dir = VAULT_MOUNT / "keys" / "storj" / "identity"
    manifest = _read_json(STORJ_MANIFEST) or {}
    secret_files = []
    identity_files = []

    if wallet_dir.exists():
        secret_files = sorted(
            path.name for path in wallet_dir.iterdir()
            if path.is_file() and path.name != "manifest.json"
        )

    if identity_dir.exists():
        identity_files = sorted(path.name for path in identity_dir.iterdir() if path.is_file())

    custody = manifest.get("custody", {})
    node_identity = manifest.get("nodeIdentity", {})
    wallet_features = manifest.get("walletFeatures") or []

    return {
        "configured": bool(manifest or secret_files or identity_files),
        "wallet": manifest.get("wallet"),
        "wallet_features": wallet_features,
        "zksync_enabled": "zksync-era" in wallet_features,
        "generated_at": manifest.get("generatedAt"),
        "quic_status": manifest.get("quicStatus"),
        "current_month_payout": (manifest.get("currentMonth") or {}).get("payout"),
        "current_month_expectations": manifest.get("currentMonthExpectations"),
        "secret_material_present": bool(
            custody.get("secretMaterialPresent") or secret_files
        ),
        "secret_files": custody.get("secretFiles") or secret_files,
        "identity_present": bool(node_identity.get("present") or identity_files),
        "identity_files": node_identity.get("files") or identity_files,
    }

# credenciais de acesso ao painel (mínimo por enquanto)
PANEL_USER = os.environ.get("VAULT_UI_USER", "admin")
PANEL_PASS = os.environ.get("VAULT_UI_PASS", "admin")

# sessões ativas { token: expiry_timestamp }
_sessions: dict = {}
_sessions_lock = threading.Lock()
SESSION_TTL = 3600  # 1h

# estado do backup em background
_backup = {"running": False, "log": [], "last": None, "rc": None}
_backup_lock = threading.Lock()


# ── auth ──────────────────────────────────────────────────────────────────────

def _new_session() -> str:
    token = secrets.token_hex(32)
    with _sessions_lock:
        _sessions[token] = time.time() + SESSION_TTL
    return token


def _valid(token: str) -> bool:
    with _sessions_lock:
        exp = _sessions.get(token)
        if exp and time.time() < exp:
            _sessions[token] = time.time() + SESSION_TTL  # renew
            return True
        _sessions.pop(token, None)
        return False


# ── kucoin ───────────────────────────────────────────────────────────────────

def _load_creds() -> dict | None:
    if not _vault_ok():
        return None
    creds = {}
    for line in VAULT_ENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip()
    return creds if "KUCOIN_API_KEY" in creds else None


def _sign(secret: str, msg: str) -> str:
    return base64.b64encode(
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()


def _kucoin_headers(creds: dict, method: str, path: str, body: str = "") -> dict:
    ts = str(int(time.time() * 1000))
    ver = creds.get("API_KEY_VERSION", "1")
    sig = _sign(creds["KUCOIN_API_SECRET"], ts + method.upper() + path + body)
    pp = creds["KUCOIN_API_PASSPHRASE"]
    if ver == "2":
        pp = _sign(creds["KUCOIN_API_SECRET"], pp)
    return {
        "KC-API-KEY": creds["KUCOIN_API_KEY"],
        "KC-API-SIGN": sig,
        "KC-API-TIMESTAMP": ts,
        "KC-API-PASSPHRASE": pp,
        "KC-API-KEY-VERSION": ver,
        "Content-Type": "application/json",
    }


def _kucoin_get(creds: dict, path: str) -> dict:
    req = urllib.request.Request(KUCOIN_BASE + path, headers=_kucoin_headers(creds, "GET", path))
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _kucoin_post(creds: dict, path: str, payload: dict) -> dict:
    body = json.dumps(payload)
    req = urllib.request.Request(
        KUCOIN_BASE + path, data=body.encode(),
        headers=_kucoin_headers(creds, "POST", path, body), method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ── backup background ─────────────────────────────────────────────────────────

def _run_backup():
    with _backup_lock:
        if _backup["running"]:
            return
        _backup["running"] = True
        _backup["log"] = []
        _backup["rc"] = None

    def _go():
        proc = subprocess.Popen(
            ["bash", str(BACKUP_SCRIPT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            with _backup_lock:
                _backup["log"].append(line.rstrip())
        proc.wait()
        with _backup_lock:
            _backup["running"] = False
            _backup["rc"] = proc.returncode
            _backup["last"] = time.strftime("%Y-%m-%d %H:%M:%S")

    threading.Thread(target=_go, daemon=True).start()


# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silenciar log padrão

    def _send(self, status: int, data, content_type="application/json"):
        body = json.dumps(data).encode() if not isinstance(data, bytes) else data
        if isinstance(data, str):
            body = data.encode()
            content_type = "text/html; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _token(self) -> str | None:
        auth = self.headers.get("Authorization", "")
        return auth.removeprefix("Bearer ").strip() or None

    def _auth(self) -> bool:
        tok = self._token()
        return tok is not None and _valid(tok)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization,Content-Type")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]

        # ── servir UI ──
        if p in ("/", "/index.html"):
            f = UI_DIR / "index.html"
            if f.exists():
                self._send(200, f.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, {"error": "index.html não encontrado no vault"})
            return

        # ── API ──
        if not self._auth():
            self._send(401, {"error": "não autorizado"})
            return

        if p == "/api/status":
            mounted = _vault_ok()
            disk = {}
            if mounted:
                st = os.statvfs(VAULT_MOUNT)
                total = st.f_blocks * st.f_frsize
                free  = st.f_bavail * st.f_frsize
                used  = total - free
                disk  = {
                    "total_gb": round(total / 1e9, 1),
                    "used_gb":  round(used  / 1e9, 1),
                    "free_gb":  round(free  / 1e9, 1),
                    "pct":      round(used / total * 100, 1) if total else 0,
                }
            self._send(200, {"vault_mounted": mounted, "disk": disk,
                             "backup": {k: _backup[k] for k in ("running","last","rc")},
                             "storj": _load_storj_status()})

        elif p == "/api/backup/log":
            with _backup_lock:
                self._send(200, {"log": list(_backup["log"]),
                                 "running": _backup["running"],
                                 "rc": _backup["rc"]})

        elif p == "/api/kucoin/balance":
            coin = self.path.split("coin=")[-1].upper() if "coin=" in self.path else "BTC"
            creds = _load_creds()
            if not creds:
                self._send(503, {"error": "credenciais KuCoin não disponíveis"})
                return
            try:
                data = _kucoin_get(creds, f"/api/v1/accounts?currency={coin}&type=main")
                accs = data.get("data", [])
                bal = next((float(a["available"]) for a in accs
                            if a.get("currency") == coin and a.get("type") == "main"), 0.0)
                self._send(200, {"coin": coin, "available": bal})
            except Exception as e:
                self._send(500, {"error": str(e)})

        elif p == "/api/kucoin/chains":
            coin = self.path.split("coin=")[-1].upper() if "coin=" in self.path else "BTC"
            creds = _load_creds()
            if not creds:
                self._send(503, {"error": "credenciais KuCoin não disponíveis"})
                return
            try:
                data = _kucoin_get(creds, f"/api/v3/currencies/{coin}")
                chains = [
                    {"name": c.get("chainName"), "fee": c.get("withdrawalMinFee"),
                     "min": c.get("withdrawalMinSize"),
                     "deposit": c.get("isDepositEnabled"),
                     "withdraw": c.get("isWithdrawEnabled")}
                    for c in data.get("data", {}).get("chains", [])
                ]
                self._send(200, {"coin": coin, "chains": chains})
            except Exception as e:
                self._send(500, {"error": str(e)})

        else:
            self._send(404, {"error": "não encontrado"})

    def do_POST(self):
        p = self.path

        if p == "/api/login":
            body = self._body()
            if body.get("username") == PANEL_USER and body.get("password") == PANEL_PASS:
                self._send(200, {"token": _new_session()})
            else:
                self._send(401, {"error": "credenciais inválidas"})
            return

        if not self._auth():
            self._send(401, {"error": "não autorizado"})
            return

        if p == "/api/backup/start":
            if _backup["running"]:
                self._send(409, {"error": "backup já em execução"})
                return
            if not BACKUP_SCRIPT.exists():
                self._send(503, {"error": f"script não encontrado: {BACKUP_SCRIPT}"})
                return
            _run_backup()
            self._send(200, {"status": "iniciado"})

        elif p == "/api/kucoin/withdraw":
            body = self._body()
            coin    = body.get("coin", "").upper()
            amount  = body.get("amount")
            address = body.get("address", "")
            network = body.get("network", "")
            memo    = body.get("memo", "")

            if not all([coin, amount, address, network]):
                self._send(400, {"error": "coin, amount, address e network são obrigatórios"})
                return

            creds = _load_creds()
            if not creds:
                self._send(503, {"error": "credenciais KuCoin não disponíveis"})
                return

            try:
                # checar saldo antes
                data = _kucoin_get(creds, f"/api/v1/accounts?currency={coin}&type=main")
                accs = data.get("data", [])
                bal = next((float(a["available"]) for a in accs
                            if a.get("currency") == coin and a.get("type") == "main"), 0.0)
                if float(amount) > bal:
                    self._send(400, {"error": f"saldo insuficiente: {bal:.8f} {coin}"})
                    return

                payload = {"currency": coin, "address": address,
                           "amount": str(amount), "chain": network}
                if memo:
                    payload["memo"] = memo

                resp = _kucoin_post(creds, "/api/v1/withdrawals", payload)
                if resp.get("code") == "200000":
                    wid = resp.get("data", {}).get("withdrawalId", "?")
                    self._send(200, {"withdrawal_id": wid, "status": "solicitado"})
                else:
                    self._send(500, {"error": resp.get("msg", "erro desconhecido"), "raw": resp})
            except Exception as e:
                self._send(500, {"error": str(e)})

        else:
            self._send(404, {"error": "não encontrado"})


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _vault_ok():
        print(f"ERRO: vault não encontrado em {VAULT_MOUNT}", file=sys.stderr)
        if _WIN:
            print("Abra o vault com LibreCrypt e defina VAULT_DRIVE=<letra>:\\", file=sys.stderr)
        sys.exit(1)

    UI_DIR.mkdir(parents=True, exist_ok=True)

    server = HTTPServer((HOST, PORT), Handler)
    print(f"Vault UI rodando em http://{HOST}:{PORT}")
    print(f"Abra o navegador e acesse: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
