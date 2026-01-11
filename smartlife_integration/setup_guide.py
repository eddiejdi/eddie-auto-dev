#!/usr/bin/env python3
"""
Guia passo-a-passo para configurar Tuya Cloud API.
Execute este script e siga as instruções.
"""
import webbrowser
import time

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║     🏠 SmartLife/Tuya - Guia de Configuração Completo               ║
╚══════════════════════════════════════════════════════════════════════╝

Para controlar seus dispositivos SmartLife via API, precisamos das 
credenciais da Tuya IoT Platform. Siga os passos abaixo:

════════════════════════════════════════════════════════════════════════
 PASSO 1: Criar conta na Tuya IoT Platform
════════════════════════════════════════════════════════════════════════

1. O navegador vai abrir em: https://auth.tuya.com/register
2. Clique em "Sign Up" 
3. Preencha:
   - Email: pode usar o mesmo do SmartLife
   - Password: crie uma senha (pode ser diferente do SmartLife)
   - Phone: opcional

NOTA: Se já tem conta, faça login direto.

Pressione ENTER para abrir o navegador...
""")
    input()
    webbrowser.open("https://auth.tuya.com/register")
    
    print("""
════════════════════════════════════════════════════════════════════════
 PASSO 2: Criar Cloud Project
════════════════════════════════════════════════════════════════════════

Após o login, você estará no console da Tuya:

1. No menu lateral, clique em "Cloud" > "Development"
2. Clique em "Create Cloud Project"
3. Preencha:
   - Project Name: "SmartHome API" (ou qualquer nome)
   - Industry: Smart Home
   - Development Method: Custom Development
   - Data Center: Western America (se seus dispositivos são região US)
                  Central Europe (se região EU)

4. Clique em "Create"
5. Na tela de autorização, marque TODAS as APIs:
   - IoT Core
   - Smart Home Basic Service
   - Device Management
   - etc.

6. Clique "Authorize"

Pressione ENTER quando criar o projeto...
""")
    input()
    
    print("""
════════════════════════════════════════════════════════════════════════
 PASSO 3: Copiar Access ID e Access Secret
════════════════════════════════════════════════════════════════════════

No seu projeto recém-criado:

1. Vá na aba "Overview"
2. Você verá:
   - Access ID/Client ID: xxxxxxxxxxxxxxxx (20 caracteres)
   - Access Secret/Client Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (32 caracteres)

3. Clique no ícone de "copiar" ao lado de cada um

ANOTE AQUI:
""")
    access_id = input("Access ID: ").strip()
    access_secret = input("Access Secret: ").strip()
    
    print(f"""
════════════════════════════════════════════════════════════════════════
 PASSO 4: Vincular conta SmartLife ao projeto
════════════════════════════════════════════════════════════════════════

IMPORTANTE: Este passo vincula seus dispositivos à API!

1. No seu projeto, vá na aba "Devices"
2. Clique em "Link Tuya App Account"
3. Clique em "Add App Account"
4. Um QR Code aparecerá
5. No app SmartLife do celular:
   - Vá em "Perfil" (Me)
   - Clique no ícone de "scan" (canto superior direito)
   - Escaneie o QR Code
   - Confirme a vinculação

Após vincular, seus dispositivos aparecerão na lista.

Pressione ENTER quando vincular...
""")
    input()
    
    print("""
════════════════════════════════════════════════════════════════════════
 PASSO 5: Região do Data Center
════════════════════════════════════════════════════════════════════════
""")
    print("Em qual região você criou o projeto?")
    print("  1. Western America (us)")
    print("  2. Central Europe (eu)")
    print("  3. China (cn)")
    print("  4. India (in)")
    
    region_choice = input("\nEscolha [1-4]: ").strip()
    regions = {"1": "us", "2": "eu", "3": "cn", "4": "in"}
    region = regions.get(region_choice, "us")
    
    # Salvar configuração
    import json
    from pathlib import Path
    
    config = {
        "access_id": access_id,
        "access_secret": access_secret,
        "region": region
    }
    
    config_dir = Path(__file__).parent / "config"
    config_dir.mkdir(exist_ok=True)
    
    with open(config_dir / "tuya_cloud.json", 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"""
════════════════════════════════════════════════════════════════════════
 ✅ CONFIGURAÇÃO SALVA!
════════════════════════════════════════════════════════════════════════

Suas credenciais foram salvas em:
  {config_dir / "tuya_cloud.json"}

Configuração:
  Access ID: {access_id[:8]}...
  Region: {region}

Agora você pode usar:

  # Testar conexão
  python tuya_cloud.py
  
  # Listar dispositivos
  python -c "from tuya_cloud import *; main()"

  # Controlar ventilador (após obter device_id)
  python control_fan.py max

""")
    
    # Testar conexão
    test = input("Deseja testar a conexão agora? [S/n]: ").strip().lower()
    if test != 'n':
        print("\n🔌 Testando conexão...")
        
        import requests
        import hmac
        import hashlib
        
        base_url = {
            "us": "https://openapi.tuyaus.com",
            "eu": "https://openapi.tuyaeu.com",
            "cn": "https://openapi.tuyacn.com",
            "in": "https://openapi.tuyain.com"
        }[region]
        
        t = str(int(time.time() * 1000))
        str_to_sign = access_id + t
        sign = hmac.new(
            access_secret.encode('utf-8'),
            str_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        
        headers = {
            "client_id": access_id,
            "sign": sign,
            "t": t,
            "sign_method": "HMAC-SHA256"
        }
        
        try:
            response = requests.get(f"{base_url}/v1.0/token?grant_type=1", headers=headers)
            result = response.json()
            
            if result.get("success"):
                print("✅ CONEXÃO OK!")
                print(f"   Token válido por {result['result']['expire_time']}s")
            else:
                print(f"❌ Erro: {result.get('msg')}")
                print("   Verifique as credenciais e tente novamente.")
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")


if __name__ == "__main__":
    main()
