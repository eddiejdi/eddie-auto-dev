#!/usr/bin/env python3
"""Adiciona port-forwards TCP para o Akash Provider no ZTE GPON Modem (VIVO_PPP).

Regras adicionadas:
  Akash-ACME           : TCP 80   → 192.168.15.252:31080  (Let's Encrypt HTTP-01)
  Akash-Provider-HTTPS : TCP 8443 → 192.168.15.252:30443
  Akash-Provider-gRPC  : TCP 8444 → 192.168.15.252:30444

Estratégia: lê TODOS os campos hidden do formulário e reenvia junto com os
novos dados — o firmware ZTE GPON exige que as regras existentes sejam
incluídas no POST para reconhecer o contexto.
"""
import sys
import os
import re
import json
import hashlib
import urllib.parse
import http.cookiejar
import urllib.request

BASE = "http://192.168.15.1"
ZTE_USER = os.environ.get("ZTE_USER", "admin")
ZTE_PASS = os.environ.get("ZTE_PASS", "")

SECRETS_API = os.environ.get("SECRETS_API_URL", "http://192.168.15.2:8088")
SECRETS_KEY = os.environ.get(
    "SECRETS_API_KEY",
    "188bbf4c1b43ed1730005288f89ad2d0708c071eca142a2b335e026e95e8cee3",
)

AKASH_TARGET = "192.168.15.252"
PF_PATH = "/getpage.gch?pid=1002&nextpage=app_virtual_conf_t.gch"

RULES = [
    {"name": "Akash-ACME",  "proto": "0", "ext": "80",   "int_port": "31080"},
    {"name": "Akash-HTTPS", "proto": "0", "ext": "8443", "int_port": "30443"},
    {"name": "Akash-gRPC",  "proto": "0", "ext": "8444", "int_port": "30444"},
]

HEADERS = [
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ("Accept-Language", "pt-BR,pt;q=0.9,en;q=0.8"),
    ("Connection", "keep-alive"),
]


def fetch_credentials() -> tuple[str, str]:
    def _get(field: str) -> str:
        url = f"{SECRETS_API}/secrets/network%2Fzte_gpon_modem?field={field}"
        req = urllib.request.Request(url, headers={"X-API-KEY": SECRETS_KEY})
        return json.loads(urllib.request.urlopen(req, timeout=5).read()).get("value", "")
    try:
        user = _get("username") or ZTE_USER
        pwd  = _get("password")
        print(f"  Credenciais do Secrets Agent (user={user!r})")
        return user, pwd
    except Exception as exc:
        print(f"  Secrets Agent: {exc!s:.80}")
        return ZTE_USER, ZTE_PASS


def decode_zte_hex(s: str) -> str:
    """Decode \\xNN escapes used by ZTE Transfer_meaning JS."""
    return re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), s)


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = HEADERS
    return opener


def login(opener: urllib.request.OpenerDirector, user: str, pwd: str) -> bool:
    page = opener.open(BASE + "/", timeout=12).read().decode("utf-8", "ignore")
    m = re.search(r"Frm_Logintoken['\"]?\)\.value\s*=\s*['\"](\w+)['\"]", page, re.I)
    token = m.group(1) if m else "1"
    data = urllib.parse.urlencode({
        "_lang": "", "frashnum": "", "action": "login",
        "Frm_Logintoken": token, "Username": user, "Password": pwd,
    }).encode()
    resp = opener.open(
        urllib.request.Request(BASE + "/", data=data, headers={"Referer": BASE + "/"}),
        timeout=12,
    )
    body = resp.read().decode("utf-8", "ignore")
    return ("logout" in body.lower() or "mainFrame" in body
            or "top.gch" in body or (len(body) > 3000 and "Username" not in body))


def parse_pf_page(body: str) -> dict:
    """Extract all Transfer_meaning values and construct form state."""
    transfers = re.findall(r"Transfer_meaning\('([^']+)',\s*'([^']*)'\)", body)
    fields = {k: decode_zte_hex(v) for k, v in transfers}

    # IF_INSTNUM (number of existing rules)
    instnum = int(fields.get("IF_INSTNUM", "0")) if fields.get("IF_INSTNUM", "").strip().isdigit() else 0

    # WAN interface name
    wan_opts = re.findall(r"<option[^>]+value=['\"]([^'\"]+)['\"][^>]*>([^<]+)</option>", body, re.I)
    wan_iface = next((v for v, _ in wan_opts if not v.isdigit()), "IGD.WD1.WCD1.WCPPP3")

    return {"fields": fields, "instnum": instnum, "wan_iface": wan_iface}


def build_add_payload(page_state: dict, rule: dict) -> dict:
    """Build the POST payload mimicking browser form submission.

    The ZTE firmware processes the non-indexed hidden fields (Name, Protocol,
    MinExtPort, etc.) that JavaScript copies from the Frm_ inputs before submit.
    InternalMacHost and MacEnable must be 'NULL' (as HiddenParaInit sets them
    and pageSetValue does not override them).
    """
    fields = page_state["fields"]
    instnum = page_state["instnum"]
    wan_iface = page_state["wan_iface"]

    payload = {
        # Global / navigation fields
        "IF_UPLOADING": "N/A",
        "_lang": "",
        "action": "",
        "logout": "",
        "temClickURL": "",
        # Operation control
        "IF_ACTION": "new",
        "IF_INDEX": "-1",
        "IF_ERRORSTR": "SUCC",
        "IF_ERRORPARAM": "SUCC",
        "IF_ERRORTYPE": "-1",
        "IF_INSTNUM": str(instnum),
        # Frm_ input fields (visible form elements)
        "Frm_Enable": "1",
        "Frm_Name":         rule["name"],
        "Frm_Protocol":     rule["proto"],
        "Frm_WANCViewName": wan_iface,
        "Frm_RemoteHost":    "",
        "Frm_EndRemoteHost": "",
        "Frm_MinExtPort": rule["ext"],
        "Frm_MaxExtPort": rule["ext"],
        "Frm_InternalHost": AKASH_TARGET,
        "Frm_MinIntPort": rule["int_port"],
        "Frm_MaxIntPort": rule["int_port"],
        # Button markers
        "Btn_Add": "",
        "Btn_Edit": "",
        "back": "",
        # Non-indexed hidden fields — JS copies from Frm_ inputs (pageSetValue)
        # FWPMSTATIC_PARA
        "Enable": "1",
        "Name": rule["name"],
        "Protocol": rule["proto"],
        "MinRemoteHost": "0.0.0.0",
        "MaxRemoteHost": "0.0.0.0",
        "MinExtPort": rule["ext"],
        "MaxExtPort": rule["ext"],
        "MinIntPort": rule["int_port"],
        "MaxIntPort": rule["int_port"],
        "WANCViewName": wan_iface,
        "InternalHost": AKASH_TARGET,
        # Not set by pageSetValue → remain as NULL (from HiddenParaInit)
        "InternalMacHost": "NULL",
        "MacEnable": "NULL",
        # OTHER_PARA — all NULL (pageSetValue does not set these for add)
        "ViewName": "NULL",
        "WANCName": "NULL",
        "Description": "NULL",
        "LeaseDuration": "NULL",
        "PortMappCreator": "NULL",
    }

    # Add all indexed hidden fields for existing rules (Name0, Protocol0, etc.)
    for i in range(instnum):
        for field in ["ViewName", "WANCViewName", "WANCName", "Enable", "Protocol",
                      "Name", "MinExtPort", "MaxExtPort", "InternalHost",
                      "MinIntPort", "MaxIntPort", "LeaseDuration",
                      "MinRemoteHost", "MaxRemoteHost", "InternalMacHost", "MacEnable",
                      "Description", "PortMappCreator"]:
            key = f"{field}{i}"
            if key in fields:
                payload[key] = fields[key]

    return payload


def get_pf_body(opener: urllib.request.OpenerDirector) -> str:
    return opener.open(BASE + PF_PATH, timeout=12).read().decode("utf-8", "ignore")


def rule_exists(body: str, ext_port: str) -> bool:
    return (f"MinExtPort" in body
            and f"'{ext_port}'" in body
            and len(body) > 10000)


def add_rule(opener: urllib.request.OpenerDirector, payload: dict) -> tuple[bool, str]:
    data = urllib.parse.urlencode(payload).encode()
    resp = opener.open(
        urllib.request.Request(
            BASE + PF_PATH, data=data,
            headers={
                "Referer": BASE + PF_PATH,
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": BASE,
            },
        ),
        timeout=15,
    )
    body = resp.read().decode("utf-8", "ignore")
    return len(body) > 10000, body


def configure_rule(user: str, pwd: str, rule: dict) -> bool:
    print(f"\n=== {rule['name']} : TCP {rule['ext']} → {AKASH_TARGET}:{rule['int_port']} ===")

    for label, password in [("plain", pwd), ("MD5", hashlib.md5(pwd.encode()).hexdigest())]:
        op = build_opener()
        if not login(op, user, password):
            print(f"  Login [{label}] falhou")
            continue
        print(f"  Login [{label}] OK")

        pf_body = get_pf_body(op)
        print(f"  PF page: {len(pf_body)} bytes")

        if rule_exists(pf_body, rule["ext"]):
            print(f"  Regra já existe!")
            return True

        state = parse_pf_page(pf_body)
        print(f"  Regras existentes: {state['instnum']}  WAN: {state['wan_iface']!r}")

        payload = build_add_payload(state, rule)
        ok, resp_body = add_rule(op, payload)
        print(f"  POST: {len(resp_body)} bytes")

        if not ok:
            print(f"  Resposta curta: {resp_body[:200]!r}")
            continue

        # Check for error in response
        errstr = re.search(r"Transfer_meaning\('IF_ERRORSTR',\s*'([^']*)'\)", resp_body)
        errtype = re.search(r"Transfer_meaning\('IF_ERRORTYPE',\s*'([^']*)'\)", resp_body)
        errstr_val = decode_zte_hex(errstr.group(1)) if errstr else "?"
        errtype_val = decode_zte_hex(errtype.group(1)) if errtype else "?"
        print(f"  IF_ERRORSTR={errstr_val!r}  IF_ERRORTYPE={errtype_val!r}")

        # New instnum in response?
        new_instnum_m = re.search(r"Transfer_meaning\('IF_INSTNUM',\s*'(\d+)'\)", resp_body)
        new_instnum = int(new_instnum_m.group(1)) if new_instnum_m else state["instnum"]
        print(f"  Rules after: {new_instnum}")

        if rule_exists(resp_body, rule["ext"]):
            print(f"  ✅ Regra {rule['name']} confirmada na resposta!")
            return True

        if new_instnum > state["instnum"]:
            print(f"  ✅ IF_INSTNUM aumentou ({state['instnum']} → {new_instnum}) — regra adicionada!")
            return True

        if errtype_val == "-1" and errstr_val == "SUCC":
            print(f"  ⚠ Servidor reportou SUCC mas porta não confirmada. Verificando com nova sessão...")
            op2 = build_opener()
            if login(op2, user, password):
                pf2 = get_pf_body(op2)
                state2 = parse_pf_page(pf2)
                if rule_exists(pf2, rule["ext"]) or state2["instnum"] > state["instnum"]:
                    print(f"  ✅ Regra confirmada com nova sessão!")
                    return True

        print(f"  Falhou com [{label}], tentando próximo método...")

    return False


def main() -> None:
    print(f"ZTE Akash Provider Port-Forward  —  {BASE}")
    print(f"  target={AKASH_TARGET}")
    for r in RULES:
        print(f"  TCP {r['ext']} → {r['int_port']}  [{r['name']}]")

    user, pwd = ZTE_USER, ZTE_PASS
    if not pwd:
        user, pwd = fetch_credentials()
    if not pwd:
        print("\n❌ Sem credenciais.")
        sys.exit(1)

    print(f"\n  user={user!r}  MD5(pass)={hashlib.md5(pwd.encode()).hexdigest()}")

    try:
        urllib.request.urlopen(BASE + "/", timeout=6)
    except Exception as exc:
        print(f"\n❌ ZTE inacessível: {exc}")
        sys.exit(1)

    failed = []
    for rule in RULES:
        if not configure_rule(user, pwd, rule):
            failed.append(rule["name"])

    print()
    if not failed:
        print("✅ Todas as regras Akash configuradas no ZTE.")
        sys.exit(0)
    else:
        print(f"❌ Falha nas regras: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
