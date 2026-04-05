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

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [
    ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
    ("Accept", "text/html,application/xhtml+xml,*/*"),
]

try:
    # Passo 1: carregar página de login e extrair Frm_Logintoken
    login_page = opener.open(BASE + "/", timeout=10).read().decode("utf-8", "ignore")

    token_match = re.search(
        r'Frm_Logintoken[^>]*value=["\']?([^"\'>\s]+)',
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
    pf_url = BASE + "/getpage.gch?pid=1002&nextpage=Internet_app_virtual_conf_t.gch"
    pf_body = opener.open(pf_url, timeout=10).read().decode("utf-8", "ignore")

    if WG_PORT in pf_body:
        print(f"WireGuard {WG_PORT} já está configurado no ZTE!")
        sys.exit(0)

    print(f"Adicionando port forward {WG_PORT} UDP -> {WG_DEST}...")

    # Passo 4: adicionar regra
    add_data = urllib.parse.urlencode({
        "IF_ACTION": "add",
        "Frm_Num": "",
        "Frm_SrvName": "WireGuard-VPN",
        "Frm_Protocol": "UDP",
        "Frm_ExtPort": WG_PORT,
        "Frm_InternalPort": WG_PORT,
        "Frm_InternalClient": WG_DEST,
        "Frm_Status": "1",
    }).encode()

    add_resp = opener.open(urllib.request.Request(pf_url, data=add_data), timeout=10)
    result = add_resp.read().decode("utf-8", "ignore")

    # Verificar resultado
    pf_body2 = opener.open(pf_url, timeout=10).read().decode("utf-8", "ignore")
    if WG_PORT in pf_body2:
        print(f"Port forward {WG_PORT} -> {WG_DEST} adicionado com SUCESSO!")
    else:
        print(f"AVISO: regra pode não ter sido adicionada. Resposta: {len(result)} bytes")
        sys.exit(1)

except Exception as exc:
    print(f"Erro ZTE: {type(exc).__name__}: {exc}")
    sys.exit(1)
