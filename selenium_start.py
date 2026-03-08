#!/usr/bin/env python3
"""
🤖 AGENTE SELENIUM LOCAL - Executa autenticação na sua máquina
Depois envia o token para o servidor remotamente
"""

import subprocess
import sys

OAUTH_URL = "https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=238307278672-47ifp1f9mj5c647ic204hgpbloofj276.apps.googleusercontent.com&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.metadata.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar.events+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.modify+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.labels&state=KgoVJaaxcHVIQ1mId3OtPdrGRdClCv&prompt=consent&access_type=offline"

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║     🤖 AGENTE SELENIUM - AUTENTICAÇÃO GOOGLE AUTOMÁTICA (LOCAL)            ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 O QUE VAI ACONTECER:
  1. ✅ Navegador será aberto com URL de autorização
  2. ✅ Credenciais podem ser digitadas automaticamente (opcional)
  3. ✅ Botão "Permitir" será clicado automaticamente
  4. ✅ Código será capturado automaticamente
  5. ✅ Token gerado e enviado ao servidor
  6. ✅ Currículos listados automaticamente

⏱️  Tempo estimado: 2-3 minutos

""")

confirm = input("Deseja continuar? (s/n): ").strip().lower()
if confirm != 's':
    print("Cancelado")
    sys.exit(1)

print("\n🔄 Iniciando Selenium...\n")

# Executar script Selenium com ativação do venv
result = subprocess.run(
    f"source /home/edenilson/shared-auto-dev/.venv/bin/activate && python3 /home/edenilson/shared-auto-dev/selenium_oauth_automation.py '{OAUTH_URL}'",
    shell=True
)

sys.exit(result.returncode)
