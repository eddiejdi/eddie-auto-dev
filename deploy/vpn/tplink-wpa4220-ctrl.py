#!/usr/bin/env python3
"""
TP-Link TL-WPA4220 — controle remoto via protocolo TDDP/XOR nativo.

Uso: TP_PASS='senha' python3 tplink-wpa4220-ctrl.py [--host IP] reboot|status|logout

O dispositivo usa cifra XOR com alfabeto customizado (extraído de /js/su/su.fun.js).
Senha via variável TP_PASS ou prompt interativo — nunca em argumento CLI.
"""
import sys, argparse, time, os, getpass, socket, urllib.parse

DEFAULT_HOST = os.environ.get("TP_HOST", "192.168.15.113")

# ── Cifra XOR (replicada de /js/su/su.fun.js: $.su.encrypt) ──────────────

DEFAULT_KEY = "RDpbLfCPsJZ7fiv"

# ALPHABET extraído de /js/su/su.fun.js (255 chars, estático no firmware)
_ALPHABET = (
    "yLwVl0zKqws7LgKPRQ84Mdt708T1qQ3Ha7xv3H7NyU84p21BriUWBU43odz3iP4rBL3cD02KZci"
    "XTysVXiV8ngg6vL48rPJyAUw0HurW20xqxv9aYb4M9wK1Ae0wlro510qXeU07kV57fQMc8L6aLg"
    "MLwygtc0F10a0Dg70TOoouyFhdysuRMO51yY5ZlOZZLEal1h0t9YQW0Ko7oBwmCAHoic4HYbUyVe"
    "U3sfQ1xtXcPcf1aT303wAQhv66qzW"
)


def _encrypt(e, t=DEFAULT_KEY, r=_ALPHABET):
    """Replica exata de $.su.encrypt(e, t, r) do firmware."""
    n, a, s = len(e), len(t), len(r)
    i = n if a < n else a  # max(n, a) — conforme JS: i = a<n ? n : a
    out = []
    for h in range(i):
        d = u = 187
        if n <= h:
            d = ord(t[h])
        elif a <= h:
            u = ord(e[h])
        else:
            u, d = ord(e[h]), ord(t[h])
        out.append(r[(u ^ d) % s])
    return "".join(out)


def _encode_para(s):
    """Replica encodeURIComponent do JS: não codifica -_.!~*'()"""
    return urllib.parse.quote(s, safe="-_.!~*'()")


# ── HTTP raw socket (sendall atômico — evita split TCP do http.client) ────

def _post(host, path, body=""):
    body_b = body.encode() if isinstance(body, str) else body
    hdrs = (
        f"POST {path} HTTP/1.0\r\n"
        f"Host: {host}\r\n"
        "Content-Type: text/plain;charset=UTF-8\r\n"
        "X-Requested-With: XMLHttpRequest\r\n"
        f"Referer: http://{host}/\r\n"
        "User-Agent: Mozilla/5.0\r\n"
        "Connection: close\r\n"
        f"Content-Length: {len(body_b)}\r\n"
        "\r\n"
    ).encode()
    sock = socket.socket()
    sock.settimeout(10)
    try:
        sock.connect((host, 80))
        sock.sendall(hdrs + body_b)
        buf = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
    finally:
        sock.close()
    sep = buf.find(b"\r\n\r\n")
    head = buf[:sep] if sep >= 0 else buf
    body_r = buf[sep + 4:] if sep >= 0 else b""
    parts = head.split(b"\r\n")[0].decode(errors="replace").split(None, 2)
    status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
    return status, body_r.decode(errors="replace")


# ── Protocolo TDDP ────────────────────────────────────────────────────────

TDDP_REBOOT  = 6
TDDP_AUTH    = 7
TDDP_LOGOUT  = 11


class WPA4220:
    def __init__(self, host, password):
        self.host = host
        self._pwd_enc = _encrypt(password)  # encrypt(plaintext, DEFAULT_KEY, ALPHABET)
        self._sid_q = None                  # session_id URL-encoded, preenchido em login()

    def _challenge(self):
        _, body = _post(self.host, f"/?code={TDDP_AUTH}&asyn=1")
        parts = body.strip().split("\r\n")
        # Resposta: [code, remaining, counter, auth3_32chars, alphabet_255chars, "00000"]
        # auth3 = parts[3] (32 chars), alphabet = parts[4] (255 chars, por sessão)
        if len(parts) < 5:
            raise RuntimeError(f"Challenge inválido: {repr(body[:80])}")
        auth3, auth4 = parts[3], parts[4]
        return auth3, auth4

    def login(self):
        auth3, auth4 = self._challenge()
        session_id = _encrypt(auth3, self._pwd_enc, auth4)
        sid_q = _encode_para(session_id)
        st, bd = _post(self.host, f"/?code={TDDP_AUTH}&asyn=0&id={sid_q}")
        if st == 200 and ("00000" in bd or "00001" in bd):
            self._sid_q = sid_q
            return
        parts = bd.strip().split("\r\n") if bd.strip() else []
        remaining = parts[1] if len(parts) > 1 else "?"
        raise RuntimeError(f"Login falhou (HTTP {st}, remaining={remaining}): {repr(bd[:60])}")

    def reboot(self):
        if not self._sid_q:
            raise RuntimeError("Não autenticado — chame login() primeiro")
        st, bd = _post(self.host, f"/?code={TDDP_REBOOT}&asyn=0&id={self._sid_q}")
        if st == 200 and ("00001" in bd or "00000" in bd):
            return True
        raise RuntimeError(f"Reboot falhou (HTTP {st}): {repr(bd[:60])}")

    def logout(self):
        if not self._sid_q:
            return
        _post(self.host, f"/?code={TDDP_LOGOUT}&asyn=0&id={self._sid_q}")
        self._sid_q = None

    def status(self):
        if not self._sid_q:
            raise RuntimeError("Não autenticado — chame login() primeiro")
        st, bd = _post(self.host, f"/?code=0&asyn=0&id={self._sid_q}")
        return {"http_status": st, "body": bd[:200]}


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Controla TL-WPA4220 via TDDP/XOR. Senha em TP_PASS ou prompt."
    )
    p.add_argument("--host", default=DEFAULT_HOST, help="IP do dispositivo")
    p.add_argument("action", choices=["reboot", "status", "logout"])
    args = p.parse_args()

    password = os.environ.get("TP_PASS") or getpass.getpass("Senha TL-WPA4220: ")
    if not password:
        sys.exit("Senha não fornecida.")

    dev = WPA4220(args.host, password)
    print(f"[*] Autenticando em {args.host}...")
    try:
        dev.login()
    except RuntimeError as e:
        sys.exit(f"[✗] {e}")
    print("[✓] Login OK")

    try:
        if args.action == "reboot":
            dev.reboot()
            print("[✓] Reboot enviado — aguardando ~30s para dispositivo voltar")
            time.sleep(30)
            # Verificar se voltou
            try:
                dev2 = WPA4220(args.host, os.environ.get("TP_PASS", ""))
                # Só checa se responde ao challenge
                dev2._challenge()
                print("[✓] Dispositivo respondeu ao challenge pós-reboot")
            except Exception:
                print("[!] Dispositivo ainda não respondeu (normal se reboot > 30s)")
            sys.exit(0)

        elif args.action == "status":
            result = dev.status()
            print(f"HTTP {result['http_status']}: {result['body']}")

        elif args.action == "logout":
            dev.logout()
            print("[✓] Logout OK")

    finally:
        try:
            dev.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
