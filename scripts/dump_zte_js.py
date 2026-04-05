#!/usr/bin/env python3
"""Extrai e imprime todos os blocos JavaScript inline da página de login ZTE.

Lê /tmp/zte_login.html e imprime cada bloco <script> completo.
Usado como diagnóstico para ver o conteúdo completo de dosubmit() e funções JS.
"""
import re
import sys

HTML_PATH = "/tmp/zte_login.html"

try:
    with open(HTML_PATH, encoding="utf-8", errors="ignore") as f:
        html = f.read()
except FileNotFoundError:
    print(f"[dump_zte_js] Arquivo não encontrado: {HTML_PATH}")
    sys.exit(0)

blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S | re.I)
print(f"Total de blocos JS inline: {len(blocks)}")

for i, content in enumerate(blocks):
    content = content.strip()
    if not content:
        continue
    print(f"\n{'='*60}")
    print(f"=== SCRIPT BLOCK {i} ({len(content)} chars) ===")
    print(f"{'='*60}")
    print(content)
