#!/usr/bin/env python3
"""Diagnóstico da página de login ZTE — verifica JS de hashing de password.

Busca a função dosubmit() em scripts inline E externos.
"""
import urllib.request
import urllib.error
import http.cookiejar
import re
import sys

BASE = "http://192.168.14.1"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")]

try:
    page = opener.open(BASE + "/", timeout=8).read().decode("utf-8", "ignore")
    print(f"ZTE login page: {len(page)} bytes")
except urllib.error.URLError as exc:
    print(f"ZTE inacessível: {exc}")
    sys.exit(1)

# Mostrar form tag
for fm in re.findall(r"<form[^>]+>", page, re.I):
    print("FORM:", fm[:200])

# Mostrar campos relevantes do form
inputs = re.findall(r"<input[^>]+>", page, re.I)
for inp in inputs:
    if any(k in inp.lower() for k in ["user", "pass", "login", "token", "frm", "action"]):
        print("INPUT:", re.sub(r"\s+", " ", inp[:200]))

print()

# Buscar scripts externos (<script src="...">)
ext_scripts = re.findall(r'<script[^>]+src=["\']?([^"\'>\s]+)', page, re.I)
print(f"Scripts externos encontrados: {ext_scripts}")

# Buscar dosubmit nos scripts inline E externos
def search_dosubmit(text: str, source: str = "(inline)") -> None:
    m = re.search(r"(function\s+dosubmit\s*\(.*?\{.*?\})", text, re.S)
    if m:
        print(f"\n=== dosubmit() em {source} ===")
        print(m.group(1)[:2000])  # até 2000 chars
    # Também buscar por dosubmit em contexto mais amplo
    elif "dosubmit" in text.lower():
        idx = text.lower().find("dosubmit")
        print(f"\n=== dosubmit referência em {source} ===")
        print(text[max(0, idx - 50):idx + 800])

# Inline scripts
for s in re.findall(r"<script[^>]*>(.*?)</script>", page, re.I | re.S):
    search_dosubmit(s, "(inline)")
    if any(k in s.lower() for k in ["password", "md5", "hash", "Logintoken"]):
        print(f"JS relevante (inline):\n{s[:500]}")

# Fetch externos
for src in ext_scripts:
    url = src if src.startswith("http") else BASE + ("/" if not src.startswith("/") else "") + src
    try:
        js_text = opener.open(url, timeout=8).read().decode("utf-8", "ignore")
        print(f"\n--- JS externo {src}: {len(js_text)} bytes ---")
        search_dosubmit(js_text, src)
        if any(k in js_text for k in ["md5", "MD5", "hex_md5", "Logintoken", "dosubmit"]):
            idx = js_text.lower().find("dosubmit")
            if idx >= 0:
                print(js_text[max(0, idx - 100): idx + 600])
    except Exception as exc:
        print(f"Falha fetch {src}: {exc}")
