#!/usr/bin/env python3
"""Extrai a função dosubmit() da página de login ZTE salva em /tmp/zte_login.html."""
import re
import sys

try:
    with open("/tmp/zte_login.html") as f:
        page = f.read()
except FileNotFoundError:
    print("Arquivo /tmp/zte_login.html não encontrado")
    sys.exit(1)

for m in re.finditer(r"<script[^>]*>(.*?)</script>", page, re.S | re.I):
    script_content = m.group(1)
    if any(kw in script_content for kw in ["dosubmit", "Password", "MD5", "md5", "Logintoken"]):
        print("=== Script block ===")
        print(script_content[:3000])
        print()
