#!/usr/bin/env python3
"""
🔧 FIX OAuth 400 erro - Execute isto agora!

Erro identificado: redirect_uri não corresponde
Solução: Usar URL correta sem porta
"""

import subprocess
import sys

print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ✅  CORREÇÃO PARA ERRO OAUTH 400 (invalid_request)           ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

🔍 PROBLEMA IDENTIFICADO:
   Erro: 400 invalid_request (flowName=GeneralOAuthFlow)
   
   Credenciais Google usam:  http://localhost
   Script anterior usava:    http://localhost:8080
   
✅ SOLUÇÃO ATIVADA:
   Usar URL de autorização correta
   Script manual para colar código

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 PRÓXIMAS ETAPAS:

1. Um script será executado e gerará uma URL
2. Você copia a URL completa
3. Abre no navegador
4. Faz login e autoriza no Google
5. Copia o código recebido
6. Cola o código no script
7. Script busca seus currículos automaticamente

⏱️  Tempo: ~5 minutos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔄 CONECTANDO AO SERVIDOR...
""")

# Executar script no servidor
result = subprocess.run(
    'ssh homelab@192.168.15.2 "python3 /home/homelab/myClaude/oauth_fix.py"',
    shell=True
)

if result.returncode == 0:
    print("""
════════════════════════════════════════════════════════════════

✅ PROCESSO CONCLUÍDO COM SUCESSO!

Seus currículos foram listados acima. Você pode:
  1. Clique nos links para abrir no Google Drive
  2. Baixe os arquivos se preferir
  3. Atualize com experiência B3 S.A. recente
  4. Salve novamente

════════════════════════════════════════════════════════════════
    """)
else:
    print("""
════════════════════════════════════════════════════════════════

⚠️  PROCESSO REQUER INTERAÇÃO

Se viu uma URL acima:
  1. Copie a URL inteira
  2. Abra no navegador
  3. Autorize com sua conta Google
  4. Copie o código da URL redirecionada
  5. Cole o código no script

Se encontrou erro:
  • Verifique se está logado corretamente no Google
  • Certifique-se de copiar o código COMPLETO
  • Repita o processo

════════════════════════════════════════════════════════════════
    """)

sys.exit(result.returncode)
