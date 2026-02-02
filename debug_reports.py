#!/usr/bin/env python3
"""Debug de relatórios"""

import sys

sys.path.insert(0, "/home/homelab/myClaude")

from reports_integration import (
    generate_btc_report,
    generate_system_report,
    generate_report,
    detect_report_type,
)

print("=== Debug de Relatórios ===\n")

# Testar geração direta
print("1. Testando generate_btc_report(24):")
try:
    report = generate_btc_report(24)
    print(f"   Tipo do retorno: {type(report)}")
    print(f"   Tamanho: {len(report) if report else 0}")
    if report:
        print(f"   Primeiros 300 chars:\n{report[:300]}")
except Exception as e:
    print(f"   ERRO: {e}")

print("\n2. Testando generate_system_report():")
try:
    report = generate_system_report()
    print(f"   Tipo do retorno: {type(report)}")
    print(f"   Tamanho: {len(report) if report else 0}")
    if report:
        print(f"   Primeiros 300 chars:\n{report[:300]}")
except Exception as e:
    print(f"   ERRO: {e}")

print("\n3. Testando generate_report('btc'):")
try:
    report = generate_report("btc")
    print(f"   Tipo do retorno: {type(report)}")
    print(f"   Tamanho: {len(report) if report else 0}")
    if report:
        print(f"   Primeiros 200 chars:\n{report[:200]}")
except Exception as e:
    print(f"   ERRO: {e}")

print("\n4. Testando detect_report_type + generate_report:")
test = "como está o btc?"
report_type = detect_report_type(test)
print(f"   Input: '{test}'")
print(f"   Tipo detectado: {report_type}")
if report_type:
    report = generate_report(report_type)
    print(f"   Relatório gerado: {'Sim' if report else 'Não'}")
    if report:
        print(f"   Primeiros 200 chars:\n{report[:200]}")
