#!/usr/bin/env python3
"""
Diagnóstico de Conexão Phomemo Q30
Detecta conexão via USB e Bluetooth
"""
import os
import subprocess
import sys


def run_cmd(cmd, description):
    """Executa comando e retorna output."""
    print(f"\n📍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 1
    except Exception as e:
        return f"ERROR: {e}", 1

def check_local():
    """Verificações locais."""
    print("\n" + "="*60)
    print("🔍 DIAGNÓSTICO LOCAL (Máquina Atual)")
    print("="*60)
    
    # Check lsusb
    output, _ = run_cmd("lsusb", "Verificando dispositivos USB (lsusb)")
    print(output)
    if "phomemo" in output.lower() or "2e8d" in output.lower():
        print("✅ Phomemo Q30 detectada localmente!")
    else:
        print("⚠️  Phomemo Q30 não detectada localmente")
    
    # Check /dev/ttyUSB*
    output, _ = run_cmd("ls -la /dev/ttyUSB* 2>/dev/null || echo 'Nenhuma porta ttyUSB'", "Verificando portas /dev/ttyUSB*")
    print(output)
    
    # Check /dev/ttyACM*
    output, _ = run_cmd("ls -la /dev/ttyACM* 2>/dev/null || echo 'Nenhuma porta ttyACM'", "Verificando portas /dev/ttyACM*")
    print(output)
    
    # Check dmesg (últimas linhas USB)
    if os.path.exists("/proc/cmdline"):
        output, _ = run_cmd("dmesg 2>/dev/null | grep -i 'usb\\|tty' | tail -10 || echo 'dmesg não disponível'", "Verificando logs do kernel (dmesg)")
        print(output if output else "Logs não acessíveis ou vazios")

def check_remote(host=None):
    """Verificações no servidor remoto."""
    if host is None:
        host = os.environ.get('HOMELAB_SSH') or f"homelab@{os.environ.get('HOMELAB_HOST','localhost')}"
    print("\n" + "="*60)
    print(f"🔍 DIAGNÓSTICO REMOTO ({host})")
    print("="*60)
    
    # Check lsusb on remote
    output, _ = run_cmd(f"ssh {host} 'lsusb' 2>&1", "Verificando dispositivos USB no servidor")
    all_lines = output.split('\n')
    lines = all_lines[:10]
    print('\n'.join(lines))
    if len(all_lines) > 10:
        omitted = len(all_lines) - 10
        print(f"  ... ({omitted} linhas omitidas)")
    
    if any(x in output.lower() for x in ["phomemo", "2e8d", "q30"]):
        print("✅ Phomemo Q30 detectada no servidor!")
    else:
        print("⚠️  Phomemo Q30 não detectada no servidor")
    
    # Check portas USB/ACM no servidor
    output, _ = run_cmd(f"ssh {host} 'ls -la /dev/ttyUSB* 2>/dev/null || echo \"Nenhuma porta ttyUSB\"' 2>&1", 
                        "Verificando portas /dev/ttyUSB* no servidor")
    print(output)
    
    # Check if Phomemo driver already installed
    output, rc = run_cmd(f"ssh {host} 'dpkg -l | grep -i phomemo' 2>&1", "Verificando se driver Phomemo está instalado")
    if rc == 0 and output:
        print("✅ Driver Phomemo instalado:")
        print(output)
    else:
        print("⚠️  Driver Phomemo não encontrado (pode ser instalado se necessário)")

def test_print(host=None):
    """Testa impressão no servidor."""
    if host is None:
        host = os.environ.get('HOMELAB_SSH') or f"homelab@{os.environ.get('HOMELAB_HOST','localhost')}"
    print("\n" + "="*60)
    print("🖨️  TESTE DE IMPRESSÃO")
    print("="*60)
    
    output, rc = run_cmd(
        f"ssh {host} 'python3 /app/phomemo_print.py --text \"TESTE CONEXÃO\" 2>&1' 2>&1",
        "Enviando comando de teste para impressora"
    )
    print(output)
    
    if rc == 0:
        print("✅ Comando executado com sucesso!")
    else:
        print("❌ Erro ao executar comando")

def main():
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  DIAGNÓSTICO DE CONEXÃO PHOMEMO Q30".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    
    # Verificações locais
    check_local()
    
    # Verificações remotas
    if "--remote" in sys.argv or "--all" in sys.argv:
        check_remote()
        
        # Teste de impressão
        if "--test" in sys.argv:
            test_print()

    print("\n" + "="*60)
    print("📋 RESUMO:")
    print("="*60)
    print("""
✅ Se a Phomemo foi detectada:
    1. Conecte via Open WebUI no seu navegador
    2. Abra o chat e diga: "Imprima TESTE"
    3. Verifique se a impressora respondeu

❌ Se a Phomemo NÃO foi detectada:
    1. Verifique a conexão USB no servidor
    2. Use: ssh homelab@${HOMELAB_HOST} 'dmesg | tail -50'
    3. Procure por mensagens de USB
    4. Reinstale drivers se necessário

💡 Para mais informações:
    python3 diagnose_phomemo_connection.py --all --test
    """)

if __name__ == "__main__":
    main()
