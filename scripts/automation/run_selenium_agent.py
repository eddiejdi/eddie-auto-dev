#!/usr/bin/env python3
"""
🤖 Executor do Agent Selenium - Orquestra autenticação OAuth
"""

import subprocess
import sys


def print_welcome():
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║        🤖 AGENT SELENIUM - AUTENTICAÇÃO AUTOMÁTICA OAUTH GOOGLE             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝

📋 O QUE VAI ACONTECER:

1. Um navegador será aberto automaticamente
2. Você fará login com sua conta Google (como de costume)
3. Você clicará em "Permitir"
4. O navegador será detectado o redirecionamento
5. O código será capturado automaticamente
6. Seus currículos serão listados

⏱️  Tempo estimado: ~3-5 minutos

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

""")

def main():
    print_welcome()
    
    print("🔄 Conectando ao servidor homelab...")
    print("   (Se o navegador fica em branco, aguarde alguns segundos)\n")
    
    # Executar agent Selenium no servidor
    cmd = "ssh -X homelab@192.168.15.2 'cd /home/homelab/myClaude && python3 selenium_oauth_agent.py'"
    
    result = subprocess.run(cmd, shell=True)
    
    print("\n" + "="*80)
    if result.returncode == 0:
        print("\n✅ SUCESSO TOTAL!")
        print("\nProximas ações:")
        print("  1. Abra os links dos currículos no Google Drive")
        print("  2. Atualize com experiência B3 S.A. recente")
        print("  3. Salve os arquivos")
    else:
        print("\n⚠️  Houve um problema durante o processo")
        print("\nDicas:")
        print("  • Se o navegador não abriu, verifique se X11 está disponível")
        print("  • Certifique-se de completar a autorização em tempo útil")
        print("  • Repita o comando se necessário")
    print("="*80 + "\n")
    
    return result.returncode

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
