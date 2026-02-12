#!/usr/bin/env python3
"""
Exibidor visual da URL de autorização Google
Mostra em formato sempre legível
"""

def display_oauth_url():
    print("\n" + "=" * 90)
    print("🔐 URL DE AUTORIZAÇÃO GOOGLE DRIVE".center(90))
    print("=" * 90)
    
    # URL completa
    url = (
        "https://accounts.google.com/o/oauth2/auth?"
        "response_type=code&"
        "client_id=238307278672-47ifp1f9mj5c647ic204hgpbloofj276.apps.googleusercontent.com&"
        "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.readonly+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.metadata.readonly+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcalendar.events+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.readonly+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.modify+"
        "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.labels&"
        "state=ESTADO_ALEATÓRIO&"
        "prompt=consent&"
        "access_type=offline"
    )
    
    print("\n📋 OPÇÃO 1: Clique no navegador já aberto")
    print("─" * 90)
    print("Se você vê a página de autorização, apenas clique no botão roxo.")
    print("URL da página: http://localhost:9876/GOOGLE_DRIVE_AUTH.html")
    
    print("\n\n📋 OPÇÃO 2: Copie e cole a URL abaixo")
    print("─" * 90)
    print("\n🔗 URL COMPLETA (clique CTRL+Click para abrir):\n")
    
    # Mostrar em múltiplas linhas para facilitar
    print(url)
    
    print("\n\n📋 OPÇÃO 3: Partes da URL (para referência)")
    print("─" * 90)
    print("\nBase:")
    print("  https://accounts.google.com/o/oauth2/auth")
    
    print("\nParâmetros principals:")
    print("  response_type: code")
    print("  client_id: 238307278672-47ifp1f9mj5c647ic204hgpbloofj276.apps.googleusercontent.com")
    print("  scope: drive.readonly + drive.metadata + calendar + gmail + labels")
    print("  access_type: offline")
    print("  prompt: consent")
    
    print("\n\n" + "=" * 90)
    print("✅ PRÓXIMOS PASSOS".center(90))
    print("=" * 90)
    print("""
1. Abra uma das URLs acima
2. Faça login com sua conta Google
3. Clique em "Permitir"
4. Copie o código que aparece after redirect (code=XXXX)
5. Execute: python3 /home/edenilson/eddie-auto-dev/complete_oauth_drive.py
6. Cole o código quando solicitado

⏱️  Total: ~3 minutos
🎯 Resultado: Lista dos seus currículos no Drive
""")
    
    print("=" * 90 + "\n")

if __name__ == "__main__":
    display_oauth_url()
