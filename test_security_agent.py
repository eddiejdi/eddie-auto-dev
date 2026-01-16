#!/usr/bin/env python3
"""Test script for SecurityAgent"""

import json
import sys
sys.path.insert(0, '/home/eddie/myClaude')

from specialized_agents.security_agent import SecurityAgent

# Testar SecurityAgent
agent = SecurityAgent('/home/eddie/myClaude')

print('=== SecurityAgent Test ===')
print(f'Version: {agent.VERSION}')
print(f'Capabilities:')
for k,v in agent.capabilities.items():
    print(f'  {k}: {v}')
print(f'Rules inherited: {list(agent.AGENT_RULES.keys())}')

# Executar scan em um subset
print('\n=== Running Security Scan ===')
report = agent.scan_directory('./specialized_agents')
print(f'Scan ID: {report.scan_id}')
print(f'Files scanned: {report.summary.get("files_scanned", 0)}')
print(f'Vulnerabilities: {report.summary.get("total_vulnerabilities", 0)}')
print(f'  Critical: {report.summary.get("critical", 0)}')
print(f'  High: {report.summary.get("high", 0)}')
print(f'  Medium: {report.summary.get("medium", 0)}')
print(f'  Low: {report.summary.get("low", 0)}')

# Validar
validation = agent.validate_scan(report)
print(f'\n=== Validation (Regra 0.2) ===')
print(f'Valid: {validation["valid"]}')
print(f'Compliance: {report.compliance_status}')

# Mostrar algumas vulnerabilidades se houver
if report.vulnerabilities:
    print(f'\n=== Top 3 Vulnerabilities ===')
    for v in report.vulnerabilities[:3]:
        print(f'  [{v.severity.value}] {v.id}: {v.type.value}')
        print(f'    File: {v.file_path}:{v.line_number}')

print('\n✅ SecurityAgent smoke test PASSED')
