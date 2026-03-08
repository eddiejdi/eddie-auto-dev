#!/usr/bin/env python3
"""
Interface de Linha de Comando para Autenticação Google Drive
Guia o usuário passo a passo
"""

def print_header():
    print("\n" + "=" * 80)
    print("🔐 AUTENTICAÇÃO GOOGLE DRIVE - BUSCA DE CURRÍCULOS".center(80))
    print("=" * 80 + "\n")

def print_step(number, title, description):
    print(f"\n🔹 ETAPA {number}: {title}")
    print("-" * 80)
    print(description)

def print_instructions():
    print_header()
    
    print("""
📋 RESUMO: Você pediu para buscar seu currículo no Google Drive.
💼 Contexto: Encontramos referência de 3+ anos na B3 S.A. (até 09/02/2026)
🎯 Objetivo: Atualizar seu CV com essa experiência recente
""")
    
    print("\n" + "█" * 80)
    print_step(1, "ABRIR PÁGINA DE AUTORIZAÇÃO", """
Uma página HTML foi aberta no seu navegador.
👉 Se NÃO vir a página, abra em: http://localhost:9876/GOOGLE_DRIVE_AUTH.html

A página contém um botão roxo "🔑 Autorizar com Google"
Clique nele para iniciar a autorização.
""")
    
    print_step(2, "AUTORIZAR NO GOOGLE", """
Você será levado ao Google.com
1. Faça login com sua conta Google (se não estiver logado)
2. Revise as permissões solicitadas
3. Clique em "Permitir" ou "Continuar"
⚠️  IMPORTANTE: Use a conta Google que tem seus currículos!
""")
    
    print_step(3, "COPIAR O CÓDIGO", """
Após clicar em "Permitir", a Google pode:
   a) Redirecionar para http://localhost:8080/?code=XXXX&state=...
   b) Mostrar tela de sucesso com o código

🔍 PROCURE POR: code=
❄️  COPIE TUDO DEPOIS DE: code=
⏹️  COPIE ATÉ: & (ou fim da URL se não houver &)

EXEMPLO:
   URL:    http://localhost:8080/?code=4/0AfJohXx3wA9B_l2K3m4n5o6p7q8r9s&state=...
   CÓDIGO: ↓
           4/0AfJohXx3wA9B_l2K3m4n5o6p7q8r9s
""")
    
    print_step(4, "EXECUTAR SCRIPT INTERATIVO", """
Volte para este terminal e execute:

    python3 /home/edenilson/shared-auto-dev/complete_oauth_drive.py

O script pedirá para colar o código.
""")
    
    print_step(5, "COLAR O CÓDIGO", """
Quando solicitado:
    🔑 Cole o código de autorização: _

Cole o código copiado (a sequência longa com números e letras)
Pressione ENTER
""")
    
    print_step(6, "BÚSCA DE CURRÍCULOS", """
Se tudo correr bem, o script:
✅ Enviará o código para o servidor
✅ Trocará por token permanente
✅ Buscará seus currículos
✅ Exibirá os 5 mais recentes
✅ Mostrará links diretos no Google Drive
""")
    
    print("\n" + "█" * 80)
    print("""
⏱️  TEMPO ESTIMADO: 2-3 minutos

🎓 PRÓXIMOS PASSOS APÓS SUCESSO:
1. Você terá os links para seus currículos
2. Poderá abri-los em http://drive.google.com
3. Atualizar com experiência B3 S.A. recente
4. Salvar novamente no Drive

✨ TODOS OS ARQUIVOS ESTÃO PRONTOS!
Pode começar quando quiser. Boa sorte! 🚀
""")

def print_troubleshooting():
    print("\n" + "=" * 80)
    print("🆘 SOLUÇÃO DE PROBLEMAS".center(80))
    print("=" * 80)
    
    issues = {
        "Não vejo a página de autorização": [
            "1. A página foi aberta em http://localhost:9876/GOOGLE_DRIVE_AUTH.html",
            "2. Se não abrir, copie a URL no navegador",
            "3. Se ainda não funcionar, use esta URL direta:",
            "   https://accounts.google.com/o/oauth2/auth?response_type=code...",
            "4. Veja GOOGLE_DRIVE_AUTH.html ou GOOGLE_DRIVE_AUTH_RESUMO.md"
        ],
        "Não consigo encontrar o código na URL": [
            "1. Procure por 'code=' na URL do redirecionamento",
            "2. O código sempre começa com '4/0Af' (aprox)",
            "3. Se não vir nada, google pode ter dado erro", 
            "4. Tente novamente: limpe cookies e refaça"
        ],
        "Erro: 'Código inválido' ou 'Invalid code'": [
            "1. O código expirou (duram ~5 minutos)",
            "2. Você copiou errado - verifique se tem '/'",
            "3. Repita a autorização"
        ],
        "Conexão recusada ao servidor (192.168.15.2)": [
            "1. Verifique se consegue fazer ping: ping 192.168.15.2",
            "2. Se não, sua rede está isolada da homelab",
            "3. Contacte administrador da rede"
        ],
        "Erro: 'Nenhum currículo encontrado'": [
            "1. Verifique se tem arquivos no Google Drive",
            "2. Os nomes devem conter: 'currículo', 'curriculum', 'cv' ou 'resume'",
            "3. O arquivo não deve estar na lixeira",
            "4. Verifique permissões do arquivo"
        ]
    }
    
    for issue, solutions in issues.items():
        print(f"\n❓ {issue}")
        for solution in solutions:
            print(f"   {solution}")

def print_files_info():
    print("\n" + "=" * 80)
    print("📁 ARQUIVOS CRIADOS".center(80))
    print("=" * 80)
    
    print("""
LOCAL (Sua máquina):
  📄 /home/edenilson/shared-auto-dev/
     ├── complete_oauth_drive.py ........... Script interativo (EXECUTE ESTE)
     ├── interactive_auth.py .............. Script base (no servidor)
     ├── GOOGLE_DRIVE_AUTH_RESUMO.md ...... Este resumo
     └── GOOGLE_DRIVE_AUTH.html ........... Página web (já aberta)

SERVIDOR (homelab @ 192.168.15.2):
  📄 /home/homelab/myClaude/
     ├── credentials.json ................. Credenciais Google (já existe)
     ├── interactive_auth.py .............. Script de auth pura
     ├── drive_data/token.json ............ Token salvo após autorização
     └── complete_oauth_drive.py .......... Script auxiliar
""")

def print_architecture():
    print("\n" + "=" * 80)
    print("🏗️  ARQUITETURA".center(80))
    print("=" * 80)
    
    print("""
FLUXO DE DADOS:
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  1. Você → Navegador                                    │
│     (abrir URL autorização Google)                      │
│           ↓                                             │
│  2. Google → Seu navegador                              │
│     (redirecionar com code=XXXX)                        │
│           ↓                                             │
│  3. Você → Seu terminal (Python)                        │
│     (colar código no script)                            │
│           ↓                                             │
│  4. Seu terminal → Servidor homelab (SSH)              │
│     (enviar código e processar)                         │
│           ↓                                             │
│  5. Servidor → Google Drive API                         │
│     (trocar code por token, buscar arquivos)            │
│           ↓                                             │
│  6. Google Drive → Seu terminal                         │
│     (lista de currículos com links)                     │
│                                                         │
└─────────────────────────────────────────────────────────┘

🔒 SEGURANÇA:
  ✅ Código de autorização (code) é válido por ~5 minutos
  ✅ Token permanente (refresh_token) fica apenas no servidor  
  ✅ Seu terminal nunca vê o token
  ✅ Apenas leitura do Drive Drive (read-only)
""")

if __name__ == "__main__":
    import sys
    
    print_instructions()
    print_troubleshooting()
    print_files_info()
    print_architecture()
    
    print("\n" + "=" * 80)
    print("🚀 PRONTO PARA COMEÇAR!".center(80))
    print("=" * 80)
    print("""
Próximo passo:
  1. Verifique se página de autorização está aberta
  2. Clique no botão roxo "🔑 Autorizar com Google"
  3. Autorize e copie o código
  4. Execute: python3 /home/edenilson/shared-auto-dev/complete_oauth_drive.py
  5. Cole o código quando solicitado

Boa sorte! 🎯✨
""")
