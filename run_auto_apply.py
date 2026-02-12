#!/usr/bin/env python3
"""
Script para executar apply_real_job.py em modo contínuo controlado.
Monitora o banco até atingir N envios e então cria arquivo de stop.
"""
import os
import sys
import time
import sqlite3
import subprocess
from pathlib import Path

VENV_PYTHON = Path(__file__).parent / ".venv" / "bin" / "python3"
SCRIPT = Path(__file__).parent / "apply_real_job.py"
LOG_DB = Path("/tmp/email_logs/email_sends.db")
STOP_FILE = Path("/tmp/stop_sending_apply_real_job")
AUTO_FLAG = Path("/tmp/auto_send_enabled")
PID_FILE = Path("/tmp/apply_pid")
OUT_LOG = Path("/tmp/apply_real_job.out")


def get_sent_count() -> int:
    """Get current count of SENT emails from DB."""
    try:
        conn = sqlite3.connect(str(LOG_DB))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM email_sends WHERE status='SENT'")
        r = c.fetchone()
        conn.close()
        return r[0] if r else 0
    except Exception as e:
        print(f"⚠️  Erro ao ler DB: {e}")
        return 0


def main():
    target_sends = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print(f"🚀 Iniciando envio automático de {target_sends} aplicações")
    
    # Get start count
    start = get_sent_count()
    print(f"📊 Emails enviados atualmente: {start}")
    
    target = start + target_sends
    print(f"🎯 Meta: {target} emails (enviar mais {target_sends})")
    
    # Cleanup
    STOP_FILE.unlink(missing_ok=True)
    PID_FILE.unlink(missing_ok=True)
    OUT_LOG.unlink(missing_ok=True)
    
    # Enable auto send
    AUTO_FLAG.touch()
    print("✅ Flag de auto-send ativada")
    
    # Start background process
    env = os.environ.copy()
    env.update({
        "AUTO_SEND_TO_SELF": "1",
        "AUTO_SEND_INTERVAL": "15",
        "WAHA_MAX_CHATS": "1000",  # Scan up to 1000 groups (including archived)
        "WAHA_MESSAGES_PER_CHAT": "100",  # Get up to 100 messages per group
        "STOP_AUTO_SEND": "0",
    })
    
    print(f"\n🔄 Iniciando processo em background...")
    process = subprocess.Popen(
        [str(VENV_PYTHON), str(SCRIPT)],
        stdout=open(OUT_LOG, 'w'),
        stderr=subprocess.STDOUT,
        env=env,
    )
    
    PID_FILE.write_text(str(process.pid))
    print(f"✅ Processo iniciado (PID: {process.pid})")
    
    # Monitor
    print(f"\n📡 Monitorando banco de dados...")
    iteration = 0
    while True:
        iteration += 1
        cnt = get_sent_count()
        print(f"[{iteration:03d}] Enviados: {cnt}/{target}", end="")
        
        if cnt >= target:
            print(" → ✅ Meta atingida!")
            STOP_FILE.touch()
            print(f"🛑 Arquivo de stop criado: {STOP_FILE}")
            break
        
        print()
        time.sleep(5)
    
    # Wait for process to finish
    print(f"\n⏳ Aguardando processo finalizar...")
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        print("⚠️  Timeout aguardando processo, forçando término...")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    
    print(f"\n✅ Processo finalizado")
    
    # Show final summary
    final_count = get_sent_count()
    print(f"\n📊 RESUMO FINAL:")
    print(f"   Início: {start} emails")
    print(f"   Final: {final_count} emails")
    print(f"   Enviados nesta execução: {final_count - start}")
    
    # Show last logs
    if OUT_LOG.exists():
        print(f"\n📋 Últimas 50 linhas do log:")
        print("=" * 70)
        with open(OUT_LOG) as f:
            lines = f.readlines()
            for line in lines[-50:]:
                print(line.rstrip())
        print("=" * 70)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido pelo usuário")
        STOP_FILE.touch()
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
