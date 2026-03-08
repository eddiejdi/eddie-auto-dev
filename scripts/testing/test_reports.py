#!/usr/bin/env python3
"""Testar módulo de relatórios"""

import asyncio
import sys
sys.path.insert(0, '/home/homelab/myClaude')

from reports_integration import detect_report_type, process_report_request, generate_report

# Testar detecção
tests = [
    "como está o btc?",
    "relatório bitcoin",
    "status trading",
    "status do sistema",
    "serviços rodando",
    "homelab",
    "visão geral infraestrutura",
    "olá tudo bem",
    "me conta uma piada"
]

print("=== Testando detecção de tipo de relatório ===\n")
for t in tests:
    tipo = detect_report_type(t)
    print(f"'{t[:35]:35}' -> {tipo or 'nenhum'}")

print("\n=== Testando geração de relatório BTC ===\n")
report = generate_report("btc")
if report:
    print(report[:500])
else:
    print("Nenhum relatório gerado")

print("\n=== Testando geração de relatório Sistema ===\n")
report = generate_report("system")
if report:
    print(report[:500])
else:
    print("Nenhum relatório gerado")
