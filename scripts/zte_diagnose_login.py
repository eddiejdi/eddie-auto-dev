#!/usr/bin/env python3
"""Diagnóstico da página de login ZTE — verifica JS de hashing de password."""
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

# Buscar JS relevante para hashing de password
scripts = re.findall(r"<script[^>]*>(.*?)</script>", page, re.I | re.S)
found_js = False
for s in scripts:
    if any(k in s.lower() for k in ["password", "md5", "hash", "crypt", "encode", "pass"]):
        print("JS relevante encontrado:")
        print(s[:600])
        found_js = True

if not found_js:
    print("Nenhum JS de hashing encontrado no login")

# Mostrar campos do form
inputs = re.findall(r"<input[^>]+>", page, re.I)
for inp in inputs:
    if any(k in inp.lower() for k in ["user", "pass", "login", "token", "frm"]):
        print("INPUT:", re.sub(r"\s+", " ", inp[:200]))

# Snippet da página
print("\nSnippet:", re.sub(r"\s+", " ", page[:500]))
