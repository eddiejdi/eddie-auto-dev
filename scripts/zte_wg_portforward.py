#!/usr/bin/env python3
"""Adiciona port forward UDP 51820 (WireGuard) no ZTE GPON Modem.

Destino: 192.168.14.2 (TP-Link WAN) — topologia double-NAT.
Credenciais: via env vars ZTE_USER e ZTE_PASS.
"""
import sys
import os
import re
import json
import urllib.parse
import http.cookiejar
import urllib.request

ZTE_USER = os.environ.get("ZTE_USER", "")
ZTE_PASS = os.environ.get("ZTE_PASS", "")

if not ZTE_USER or not ZTE_PASS:
    print("ERROR: credenciais ZTE_USER/ZTE_PASS não definidas")
    sys.exit(1)

BASE = "http://192.168.14.1"
WG_DEST = os.environ.get("ZTE_WG_DEST", "192.168.14.2")
WG_PORT = "51820"
# URL correta do menu Port Forward (smPForward) do ZTE GPON
PF_URL_DISPLAY = BASE + "/getpage.gch?pid=1002&nextpage=app_virtual_conf_t.gch"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
    ("Accept", "text/html,application/xhtml+xml,*/*"),
]

try:
    # Passo 1: carregar página de login e extrair Frm_Logintoken
    login_page = opener.open(BASE + "/", timeout=10).read().decode("utf-8", "ignore")

    # Tenta extrair token do HTML (value=) ou do JS (getObj("Frm_Logintoken").value = "N")
    token_match = re.search(
        r'Frm_Logintoken[^>]*value=["\']([^"\'>\s]+)',
        login_page,
        re.IGNORECASE,
    )
    if not token_match:
        token_match = re.search(
            r'getObj\s*\(\s*["\']Frm_Logintoken["\']\s*\)\s*\.value\s*=\s*["\']?(\d+)',
            login_page,
            re.IGNORECASE,
        )
    login_token = token_match.group(1) if token_match else "1"
    print(f"Frm_Logintoken extraído: {login_token}")

    # Passo 2: login
    login_data = urllib.parse.urlencode({
        "_lang": "",
        "frashnum": "",
        "action": "login",
        "Frm_Logintoken": login_token,
        "Username": ZTE_USER,
        "Password": ZTE_PASS,
    }).encode()

    req = urllib.request.Request(BASE + "/", data=login_data)
    resp = opener.open(req, timeout=10)
    body = resp.read().decode("utf-8", "ignore")

    if 'name="Username"' in body or "id=\"Username\"" in body:
        print("Login ZTE falhou — página de login redisplayada")
        print(f"User utilizado: {ZTE_USER!r}")
        sys.exit(1)

    print("Login ZTE OK")

    # Passo 3: verificar se WireGuard 51820 já existe
    pf_url = PF_URL_DISPLAY
    pf_body = opener.open(pf_url, timeout=10).read().decode("utf-8", "ignore")

    # Verificar se já existe (pelo nome WireGuard ou pelo mapeamento porta+destino)
    min_ext_match = re.search(
        rf"MinExtPort\d+','{WG_PORT}'",
        pf_body,
    )
    wireguard_name_match = "WireGuard" in pf_body or "wireguard" in pf_body.lower()
    
    if wireguard_name_match or min_ext_match:
        print(f"WireGuard {WG_PORT} já está configurado no ZTE!")
        sys.exit(0)

    # Extrair WAN connection name (WANCViewName sem o .FWPMx suffix)
    # Extrair WANCViewName e WANCName do entry 0 (padrão)
    wanc_view_match = re.search(r"Transfer_meaning\('WANCViewName0','([^']+)'\)", pf_body)
    wanc_view = wanc_view_match.group(1).replace("\\x2e", ".").replace("\\x5f", "_") \
        if wanc_view_match else "IGD.WD1.WCD1.WCPPP3"

    wanc_name_match = re.search(r"Transfer_meaning\('WANCName0','([^']+)'\)", pf_body)
    wanc_name = wanc_name_match.group(1).replace("\\x5f", "_") \
        if wanc_name_match else "VIVO_PPP"

    # Extrair IF_INSTNUM (número de entradas atuais) para informar o ZTE
    instnum_match = re.search(r"Transfer_meaning\('IF_INSTNUM','(\d+)'\)", pf_body)
    instnum = instnum_match.group(1) if instnum_match else "2"

    print(f"Adicionando port forward {WG_PORT} UDP -> {WG_DEST} via {wanc_name} (instnum={instnum})...")

    # Passo 4: adicionar regra com campos corretos da API ZTE
    # IF_ACTION="new" e IF_INDEX="-1" para nova entrada
    add_data = urllib.parse.urlencode({
        "IF_ACTION": "new",       # ZTE usa "new" para adicionar, não "add"
        "IF_INSTNUM": instnum,
        "IF_INDEX": "-1",         # -1 = nova entrada
        "ViewName": "",           # vazio para nova entrada
        "WANCViewName": wanc_view,
        "WANCName": wanc_name,
        "Enable": "1",
        "Protocol": "1",          # 0=TCP, 1=UDP, 2=TCP+UDP
        "Name": "WireGuard-VPN",
        "MinExtPort": WG_PORT,
        "MaxExtPort": WG_PORT,
        "InternalHost": WG_DEST,
        "MinIntPort": WG_PORT,
        "MaxIntPort": WG_PORT,
        "Description": "WireGuard VPN",
        "LeaseDuration": "0",
        "PortMappCreator": "",
        "MinRemoteHost": "0.0.0.0",
        "MaxRemoteHost": "0.0.0.0",
        "MacEnable": "0",
        "InternalMacHost": "00:00:00:00:00:00",
    }).encode()

    add_resp = opener.open(urllib.request.Request(PF_URL_DISPLAY, data=add_data), timeout=15)
    result = add_resp.read().decode("utf-8", "ignore")

    # Verificar IF_ERRORTYPE na resposta
    err_match = re.search(r"Transfer_meaning\('IF_ERRORTYPE','([^']+)'\)", result)
    errortype = err_match.group(1).replace("\\x2d", "-") if err_match else "unknown"
    print(f"IF_ERRORTYPE após add: {errortype}")

    # Verificar resultado — ZTE retorna página atualizada com nova entrada
    if "WireGuard" in result:
        print(f"Port forward {WG_PORT} -> {WG_DEST} adicionado com SUCESSO!")
    else:
        # Checar de novo
        pf_body2 = opener.open(pf_url, timeout=10).read().decode("utf-8", "ignore")
        if "WireGuard" in pf_body2 or f"'{WG_PORT}'" in pf_body2:
            print(f"Port forward {WG_PORT} -> {WG_DEST} adicionado com SUCESSO!")
        else:
            print(f"AVISO: regra pode não ter sido adicionada. Resposta: {len(result)} bytes")
            err_match = re.search(r"Transfer_meaning\('IF_ERRORTYPE','([^']+)'\)", result)
            if err_match:
                errortype_val = err_match.group(1).replace("\\x2d", "-")
                print(f"IF_ERRORTYPE: {errortype_val}")
            sys.exit(1)

except Exception as exc:
    print(f"Erro ZTE: {type(exc).__name__}: {exc}")
    sys.exit(1)

