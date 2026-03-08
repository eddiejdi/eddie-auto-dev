#!/usr/bin/env python3
"""
Recriação COMPLETA da função de impressora com persistência no banco
"""
import os
import requests
import json
import sys

HOMELAB_HOST = os.environ.get("HOMELAB_HOST", "localhost")
WEBUI_URL = os.environ.get("WEBUI_URL", f"http://{HOMELAB_HOST}:8002")
EMAIL = "edenilson.teixeira@rpa4all.com"
PASSWORD = "Shared@2026"
FUNCTION_ID = "printer_etiqueta"

# Código-fonte simplificado e testado
FUNCTION_CODE = '''"""
Função Open WebUI para impressão em Phomemo Q30
"""
import json
import subprocess
import os

class Pipe:
    class Valves:
        def __init__(self):
            self.PRINTER_SCRIPT = "/home/homelab/agents_workspace/phomemo_print.py"
            self.PRINTER_PORT = ""
            self.BAUDRATE = 9600
    
    def __init__(self):
        self.valves = self.Valves()
        self.name = "🖨️ Impressora de Etiquetas"
    
    async def pipe(self, body: dict, __user__: dict = None, __event_emitter__=None) -> str:
        """Processa impressão de etiquetas"""
        try:
            # Extrair mensagem do usuário
            if isinstance(body, dict):
                messages = body.get("messages", [])
                if not messages:
                    return "❌ Nenhuma mensagem"
                
                user_message = None
                for msg in reversed(messages):
                    if msg.get("role") == "user":
                        user_message = msg.get("content", "")
                        break
                
                if not user_message:
                    return "❌ Mensagem de usuário não encontrada"
                
                text_to_print = user_message
            else:
                text_to_print = str(body)
            
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": "🖨️ Imprimindo..."}})
            
            # Imprimir
            cmd = ["python3", self.valves.PRINTER_SCRIPT, "--text", text_to_print, "--baud", str(self.valves.BAUDRATE)]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return f"✅ Impresso com sucesso!\\n\\nTexto: {text_to_print}"
            else:
                return f"❌ Erro: {result.stderr}"
        
        except Exception as e:
            return f"❌ Exceção: {str(e)}"
'''

def main():
    print("\n" + "="*80)
    print("RECRIAÇÃO COMPLETA - IMPRESSORA DE ETIQUETAS")
    print("="*80)
    
    # 1. Autenticar
    print("\n1️⃣ Autenticando...")
    auth_response = requests.post(
        f"{WEBUI_URL}/api/v1/auths/signin",
        headers={"Content-Type": "application/json"},
        json={"email": EMAIL, "password": PASSWORD}
    )
    
    if auth_response.status_code != 200:
        print(f"❌ Erro: {auth_response.text}")
        sys.exit(1)
    
    token = auth_response.json()["token"]
    print(f"✅ Token: {token[:20]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 2. DELETAR função antiga
    print("\n2️⃣ Deletando função antiga (se existir)...")
    delete_response = requests.delete(
        f"{WEBUI_URL}/api/v1/functions/id/{FUNCTION_ID}/delete",
        headers=headers
    )
    print(f"   Status delete: {delete_response.status_code}")
    
    # 3. CRIAR função nova com is_active=True
    print("\n3️⃣ Criando função nova...")
    create_payload = {
        "id": FUNCTION_ID,
        "name": "🖨️ Impressora de Etiquetas",
        "type": "pipe",
        "content": FUNCTION_CODE,
        "meta": {
            "description": "Imprime etiquetas no Phomemo Q30",
            "author": "Shared Auto-Dev"
        }
    }
    
    create_response = requests.post(
        f"{WEBUI_URL}/api/v1/functions/create",
        headers=headers,
        json=create_payload
    )
    
    print(f"   Status create: {create_response.status_code}")
    if create_response.status_code == 200:
        print("   ✅ Função criada!")
        func_data = create_response.json()
        print(f"   ID criado: {func_data.get('id')}")
    else:
        print(f"   ❌ Erro: {create_response.text}")
        sys.exit(1)
    
    # 4. ATIVAR via banco de dados
    print("\n4️⃣ Ativando via SSH...")
    import subprocess
    
    activate_script = '''
import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
cursor = conn.cursor()
cursor.execute("UPDATE function SET is_active=1, is_global=1 WHERE id='printer_etiqueta'")
conn.commit()
affected = cursor.rowcount
cursor.execute("SELECT id, is_active, is_global FROM function WHERE id='printer_etiqueta'")
result = cursor.fetchone()
conn.close()
print(f"Linhas afetadas: {affected}")
if result:
    print(f"Status final: ID={result[0]}, Ativo={result[1]}, Global={result[2]}")
else:
    print("ERRO: Função não encontrada no banco!")
'''
    
    # Salvar script temporário
    with open('/tmp/activate_printer_db.py', 'w') as f:
        f.write(activate_script)
    
    # Copiar e executar no servidor
    ssh_target = os.environ.get('HOMELAB_SSH') or f"homelab@{HOMELAB_HOST}"
    subprocess.run(['scp', '/tmp/activate_printer_db.py', f"{ssh_target}:/tmp/"])
    subprocess.run(['ssh', ssh_target, 
                   'docker cp /tmp/activate_printer_db.py open-webui:/tmp/ && docker exec open-webui python3 /tmp/activate_printer_db.py'])
    
    # 5. Reiniciar Open WebUI para recarregar funções
    print("\n5️⃣ Reiniciando Open WebUI...")
    subprocess.run(['ssh', ssh_target, 'docker restart open-webui'])
    
    print("\n" + "="*80)
    print("✅ CONCLUÍDO!")
    print("="*80)
    print("\n💡 Aguarde ~10 segundos para o Open WebUI reiniciar.")
    print(f"   Depois acesse: {WEBUI_URL}")
    print("   E teste: 'Imprima TESTE 123'")
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
