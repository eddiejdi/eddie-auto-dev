#!/usr/bin/env python3
"""
Script para corrigir o endpoint /set-live no Prometheus Exporter
Aplica isolamento de config por moeda (BTC, ETH, XRP, SOL, DOGE, ADA)

Uso: python3 fix_prometheus_exporter.py
"""

import re
import sys
from pathlib import Path


def fix_prometheus_exporter(filepath: str) -> bool:
    """Aplica a correção ao arquivo prometheus_exporter.py"""
    
    try:
        # Ler arquivo
        with open(filepath, "r") as f:
            content = f.read()
        
        print("[1] Lendo arquivo...")
        print(f"    Tamanho: {len(content)} bytes")
        
        # Verificar se arquivo já foi corrigido
        if "def get_config_path():" in content:
            print("[!] Arquivo já foi corrigido anteriormente")
            return True
        
        # Passo 1: Remover linha CONFIG_PATH
        print("[2] Removendo CONFIG_PATH global...")
        content_original = content
        pattern = r'\nCONFIG_PATH = BASE_DIR / "config\.json"\n'
        content = re.sub(pattern, '\n', content)
        
        if content == content_original:
            print("    [!] Linha CONFIG_PATH não encontrada")
            return False
        print("    [✓] CONFIG_PATH removida")
        
        # Passo 2: Adicionar função get_config_path()
        print("[3] Adicionando função get_config_path()...")
        schema_pos = content.find('SCHEMA = "btc"')
        if schema_pos == -1:
            print("    [!] Não foi possível localizar SCHEMA = \"btc\"")
            return False
        
        # Encontrar o fim da linha
        next_newline = content.find('\n', schema_pos)
        insert_pos = next_newline + 1
        
        new_function = '''
def get_config_path():
    """Obtém o caminho do arquivo de config específico da moeda"""
    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
    return BASE_DIR / config_name

'''
        content = content[:insert_pos] + new_function + content[insert_pos:]
        print("    [✓] Função get_config_path() adicionada")
        
        # Passo 3: Substituir CONFIG_PATH por get_config_path()
        print("[4] Substituindo referências de CONFIG_PATH...")
        replacements = {
            'with open(CONFIG_PATH)': 'with open(get_config_path())',
            'os.path.dirname(CONFIG_PATH)': 'os.path.dirname(get_config_path())',
            'os.replace(tmp_path, CONFIG_PATH)': 'os.replace(tmp_path, get_config_path())',
        }
        
        replaced_count = 0
        for old, new in replacements.items():
            if old in content:
                content = content.replace(old, new)
                replaced_count += 1
        
        print(f"    [✓] {replaced_count} referências substituídas")
        
        # Escrever arquivo
        print("[5] Escrevendo arquivo corrigido...")
        with open(filepath, "w") as f:
            f.write(content)
        
        print(f"    [✓] Arquivo salvo: {filepath}")
        return True
        
    except Exception as e:
        print(f"\n[!] ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Função principal"""
    
    # Detectar caminho do arquivo
    filepath = "/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py"
    
    print("=" * 70)
    print("Corrigindo /set-live Endpoint Prometheus Exporter")
    print("=" * 70)
    
    # Verificar se arquivo existe
    if not Path(filepath).exists():
        print(f"\n[!] Arquivo não encontrado: {filepath}")
        print("[*] Caminho alternativo esperado em um dos:")
        print("    - /home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py")
        print("    - ./btc_trading_agent/prometheus_exporter.py")
        print("    - ./prometheus_exporter.py")
        
        # Tentar caminhos alternativos
        alternatives = [
            Path.cwd() / "prometheus_exporter.py",
            Path.cwd() / "btc_trading_agent" / "prometheus_exporter.py",
            Path("/tmp/prometheus_exporter.py"),
        ]
        
        for alt_path in alternatives:
            if alt_path.exists():
                filepath = str(alt_path)
                print(f"\n[✓] Arquivo encontrado em: {filepath}")
                break
        else:
            print("\n[!] Nenhum arquivo encontrado. Encerrando.")
            return 1
    
    # Fazer backup
    backup_path = Path(filepath).with_suffix(".py.backup_" + Path(filepath).stat().st_mtime.__str__()[-6:])
    print(f"\n[*] Fazendo backup para: {backup_path}")
    try:
        import shutil
        shutil.copy(filepath, backup_path)
        print(f"    [✓] Backup salvo")
    except Exception as e:
        print(f"    [!] Aviso: Backup falhou: {e}")
    
    # Aplicar correção
    print()
    if fix_prometheus_exporter(filepath):
        print("\n" + "=" * 70)
        print("[✓] CORREÇÃO APLICADA COM SUCESSO!")
        print("=" * 70)
        print("\nPróximos passos:")
        print("1. Reiniciar os exporters:")
        print("   sudo systemctl restart crypto-exporter@ADA_USDT.service \\")
        print("     crypto-exporter@DOGE_USDT.service \\")
        print("     crypto-exporter@ETH_USDT.service \\")
        print("     crypto-exporter@SOL_USDT.service \\")
        print("     crypto-exporter@XRP_USDT.service \\")
        print("     autocoinbot-exporter.service")
        print("\n2. Testar o endpoint:")
        print("   curl http://192.168.15.2:9098/set-live")
        print("\n3. Validar que cada moeda tem seu próprio config:")
        print("   curl http://192.168.15.2:9092/mode")  # BTC")
        print("   curl http://192.168.15.2:9098/mode")  # ETH")
        return 0
    else:
        print("\n" + "=" * 70)
        print("[!] CORREÇÃO FALHOU")
        print("=" * 70)
        print(f"\nVerifique o arquivo: {filepath}")
        print(f"Ou restaure do backup: {backup_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
