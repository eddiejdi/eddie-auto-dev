#!/usr/bin/env python3
"""Teste HTTP dos endpoints do interceptador."""

import subprocess

# Aguardar a API estar pronta
print("Aguardando API estar pronta...")
result = subprocess.run(
    [
        "wsl",
        "bash",
        "-c",
        "cd /home/eddie/myClaude && timeout 5 curl -s http://localhost:8503/health || echo 'TIMEOUT'",
    ],
    capture_output=True,
    text=True,
)

if "TIMEOUT" in result.stdout or result.returncode != 0:
    print("⚠ API não está respondendo em http://localhost:8503")
    print(
        "Execute em outro terminal: cd /home/eddie/myClaude && python3 -m uvicorn specialized_agents.api:app --host 0.0.0.0 --port 8503"
    )
else:
    print("✓ API está respondendo")

# Testar endpoint do interceptador
print("\nTestando endpoint /interceptor/conversations/active...")
result = subprocess.run(
    [
        "wsl",
        "bash",
        "-c",
        "curl -s http://localhost:8503/interceptor/conversations/active",
    ],
    capture_output=True,
    text=True,
)

print(f"Status HTTP: {result.stdout[:100] if result.stdout else 'sem resposta'}")
if "404" not in result.stdout and result.returncode == 0:
    print("✓ Endpoint está acessível (200 OK)")
else:
    print("✗ Endpoint retornou erro ou 404")
