#!/usr/bin/env python3
"""
RÁPIDO: Tentar novamente com redirect_uri correto

Execute este script para contornar o erro 400
"""

import subprocess
import sys


def main():
    print("\n" + "🔧 "*20)
    print("\n  CORRIGINDO ERRO OAUTH 400: invalid_request\n")
    print("🔧 "*20 + "\n")
    
    print("""
📌 PROBLEMA:
   Erro 400 invalid_request (flowName=GeneralOAuthFlow)
   
   Causa: redirect_uri na URL não corresponde às credenciais Google
   
   Credenciais registradas: http://localhost (sem porta)
   URL usada antes:         http://localhost:8080 (com porta)

✅ SOLUÇÃO:
   Usar redirect_uri correto e fluxo manual alternativo
   
🚀 PRÓXIMAS AÇÕES:
   1. Tentar porta 80 (requer sudo em alguns sistemas)
   2. Se falhar, usar fluxo completamente manual
   3. Você irá copiar/colar o código
    """)
    
    confirm = input("\nDeseja continuar? (s/n): ").strip().lower()
    if confirm != 's':
        print("Cancelado pelo usuário")
        return False
    
    print("\n🔄 Conectando ao servidor...\n")
    
    # Executar script no servidor
    cmd = "ssh homelab@192.168.15.2 'python3 /home/homelab/myClaude/fix_oauth_400_error.py'"
    
    result = subprocess.run(cmd, shell=True)
    
    return result.returncode == 0

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n✅ Tudo pronto! Seu currículo deve estar listado acima.")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
