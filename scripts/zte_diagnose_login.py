#!/usr/bin/env python3
"""Diagnóstico da página de login ZTE — dump completo de todo o JavaScript inline.

Extrai a função dosubmit() completa com contagem de chaves balanceadas.
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

# Form tags
for fm in re.findall(r"<form[^>]+>", page, re.I):
    print("FORM:", fm[:200])

# Campos relevantes
inputs = re.findall(r"<input[^>]+>", page, re.I)
for inp in inputs:
    if any(k in inp.lower() for k in ["user", "pass", "login", "token", "frm", "action"]):
        print("INPUT:", re.sub(r"\s+", " ", inp[:200]))

print()


def extract_function_body(text: str, func_name: str) -> str:
    """Extrai o corpo completo de uma função JS por contagem de chaves balanceadas."""
    pattern = rf"function\s+{func_name}\s*\([^)]*\)\s*\{{"
    m = re.search(pattern, text, re.S)
    if not m:
        return ""
    start = m.start()
    brace_count = 0
    in_string = False
    str_char = None
    i = m.end() - 1  # posição do primeiro {
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\" :
                i += 1  # pular escape
            elif ch == str_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                str_char = ch
            elif ch == "{":
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[start:i + 1]
        i += 1
    return text[start:]  # sem fim encontrado — retorna do início


# Buscar scripts externos
ext_scripts = re.findall(r'<script[^>]+src=["\']?([^"\'>\s]+)', page, re.I)
print(f"Scripts externos: {ext_scripts}")

# Processar scripts inline — dump COMPLETO
inline_blocks = re.findall(r"<script[^>]*>(.*?)</script>", page, re.I | re.S)
print(f"Blocos JS inline: {len(inline_blocks)}")

for idx, s in enumerate(inline_blocks):
    s = s.strip()
    if not s:
        continue
    print(f"\n{'='*60}")
    print(f"=== SCRIPT BLOCK {idx} ({len(s)} chars) ===")
    print(f"{'='*60}")
    print(s)  # DUMP COMPLETO — sem limite de chars

print()

# Extrair dosubmit() completo
full_js = "\n".join(inline_blocks)
dosubmit_body = extract_function_body(full_js, "dosubmit")
if dosubmit_body:
    print("\n" + "="*60)
    print("=== DOSUBMIT() FUNÇÃO COMPLETA ===")
    print("="*60)
    print(dosubmit_body)
else:
    print("\n[AVISO] dosubmit() não encontrado nos scripts inline")

# Fetch externos
for src in ext_scripts:
    url = src if src.startswith("http") else BASE + ("/" if not src.startswith("/") else "") + src
    try:
        js_text = opener.open(url, timeout=8).read().decode("utf-8", "ignore")
        print(f"\n--- JS externo {src}: {len(js_text)} bytes ---")
        dsub = extract_function_body(js_text, "dosubmit")
        if dsub:
            print("=== dosubmit() EXTERNO ===")
            print(dsub)
    except Exception as exc:
        print(f"Falha fetch {src}: {exc}")
