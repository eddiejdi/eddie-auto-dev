#!/usr/bin/env python3
"""
Script para diagnosticar e testar Phomemo Q30 via USB no servidor
Execute no servidor: python3 this_script.py
"""
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, shell=True):
    """Executa comando."""
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True, timeout=5)
    return result.stdout.strip(), result.returncode

def main():
    print("\n" + "="*70)
    print("🔍 DIAGNÓSTICO PHOMEMO Q30 - SERVIDOR".center(70))
    print("="*70)
    
    # 1. lsusb
    print("\n📱 Dispositivos USB:")
    stdout, _ = run_cmd("lsusb")
    print(stdout)
    
    if "phomemo" in stdout.lower() or "2e8d" in stdout.lower():
        print("✅ Phomemo detectada em lsusb!")
    else:
        print("⚠️  Phomemo não aparece em lsusb - verifique conexão USB")
    
    # 2. Portas seriais
    print("\n🔌 Portas Seriais Disponíveis:")
    stdout, _ = run_cmd("ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo 'Nenhuma porta encontrada'")
    print(stdout)
    
    # 3. Testar python3 com pyserial
    print("\n🐍 Verificando pyserial:")
    stdout, rc = run_cmd("python3 -c 'import serial; print(\"✅ pyserial instalado\")'")
    if rc == 0:
        print(stdout)
    else:
        print("❌ pyserial não instalado")
        print("   Instale com: docker exec open-webui pip install pyserial")
    
    # 4. Listar portas com pyserial
    print("\n🔎 Listando com pyserial:")
    test_code = """
import serial.tools.list_ports
ports = list(serial.tools.list_ports.comports())
if not ports:
    print("  Nenhuma porta serial encontrada")
else:
    for p in ports:
        print(f"  {p.device}: {p.description} ({p.hwid})")
        if "phomemo" in (p.description or "").lower() or "2e8d" in (p.hwid or "").lower():
            print(f"    ✅ PHOMEMO DETECTADA!")
"""
    cmd = f"python3 -c '{test_code.replace(chr(10), '; ')}'"
    stdout, rc = run_cmd(cmd)
    if rc == 0:
        print(stdout)
    else:
        print("Erro ao listar portas")
    
    # 5. Testar script phomemo_print.py
    print("\n📋 Testando phomemo_print.py --list:")
    if Path("/app/phomemo_print.py").exists():
        stdout, rc = run_cmd("python3 /app/phomemo_print.py --list")
        print(stdout if stdout else "(nenhuma porta)")
    else:
        print("❌ /app/phomemo_print.py não encontrado")
    
    # 6. Teste de impressão (se encontrou porta)
    print("\n🖨️  Teste de Impressão:")
    if any(x in run_cmd("ls /dev/ttyUSB*")[0].lower() for x in ["usb", "acm"]):
        print("Enviando comando de teste...")
        stdout, rc = run_cmd("python3 /app/phomemo_print.py --text 'TESTE DO SERVIDOR'")
        if rc == 0:
            print("✅", stdout)
        else:
            print("❌", stdout)
    else:
        print("⚠️  Nenhuma porta USB detectada, pulando teste de impressão")
    
    # 7. Verificar permissões
    print("\n🔐 Verificando Permissões:")
    usb_ports = run_cmd("ls -la /dev/ttyUSB* 2>/dev/null || echo 'none'")[0]
    if "none" not in usb_ports:
        print(usb_ports)
    else:
        print("Nenhuma porta /dev/ttyUSB encontrada")
    
    print("\n" + "="*70)
    print("RESUMO".center(70))
    print("="*70)
    print("""
✅ Se Phomemo foi detectada:
   1. Teste: python3 /app/phomemo_print.py --text "TESTE"
   2. Se funcionar, a impressora está pronta!
   3. Use no Open WebUI: "Imprima TESTE"

❌ Se Phomemo NÃO foi detectada:
   1. Verifique conexão USB física
   2. Use: dmesg | tail -50
   3. Procure por mensagens de novo dispositivo USB
   4. Pode precisar instalar drivers ou resolver conflitos
    """)
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
