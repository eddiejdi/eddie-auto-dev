#!/usr/bin/env python3
"""
Prometheus Exporter para RPA4All Snapshot Service
Monitora status, travamento, falhas e duração do backup
"""

import os
import time
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from prometheus_client import start_http_server, Gauge, Counter, Histogram

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Métricas Prometheus
snapshot_up = Gauge('rpa4all_snapshot_service_up', 'Serviço rpa4all-snapshot está rodando')
snapshot_last_run_timestamp = Gauge('rpa4all_snapshot_last_run_timestamp', 'Timestamp do último snapshot')
snapshot_last_run_duration = Gauge('rpa4all_snapshot_last_run_duration_seconds', 'Duração do último snapshot em segundos')
snapshot_lock_age = Gauge('rpa4all_snapshot_lock_age_seconds', 'Idade do lock file em segundos')
snapshot_failed_count = Counter('rpa4all_snapshot_failed_total', 'Total de falhas de snapshot')
snapshot_success_count = Counter('rpa4all_snapshot_success_total', 'Total de snapshots bem-sucedidos')
snapshot_hung = Gauge('rpa4all_snapshot_hung', 'Snapshot travado (lock age > 1800s)')
snapshot_recovery_triggered = Counter('rpa4all_snapshot_recovery_triggered_total', 'Recuperações acionadas')
backup_size_bytes = Gauge('rpa4all_snapshot_backup_size_bytes', 'Tamanho do último backup em bytes')

LOCK_FILE = "/tmp/rpa4all-snapshot.lock"
BACKUP_DIR = "/mnt/raid1/backups"
MAX_LOCK_AGE = 1800  # 30 minutos


def check_service_status():
    """Verifica se o serviço está rodando"""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'rpa4all-snapshot.service'],
            capture_output=True,
            timeout=5
        )
        is_active = result.returncode == 0
        snapshot_up.set(1 if is_active else 0)
        return is_active
    except Exception as e:
        logger.error(f"Erro ao verificar serviço: {e}")
        snapshot_up.set(0)
        return False


def check_lock_file():
    """Monitora idade do lock file"""
    if not Path(LOCK_FILE).exists():
        snapshot_lock_age.set(-1)  # -1 = não existe
        snapshot_hung.set(0)
        return

    try:
        lock_age = time.time() - Path(LOCK_FILE).stat().st_mtime
        snapshot_lock_age.set(lock_age)
        
        # Detectar travamento
        if lock_age > MAX_LOCK_AGE:
            snapshot_hung.set(1)
            logger.warning(f"TRAVAMENTO DETECTADO! Lock age: {lock_age}s")
            snapshot_recovery_triggered.inc()
        else:
            snapshot_hung.set(0)
    except Exception as e:
        logger.error(f"Erro ao verificar lock file: {e}")


def get_backup_size():
    """Obtém tamanho do backup mais recente"""
    try:
        if not Path(BACKUP_DIR).exists():
            return
        
        # Encontrar pasta mais recente
        backups = sorted(
            [d for d in Path(BACKUP_DIR).iterdir() if d.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        if not backups:
            return
        
        latest = backups[0]
        
        # Calcular tamanho recursivamente
        total_size = sum(f.stat().st_size for f in latest.rglob('*') if f.is_file())
        backup_size_bytes.set(total_size)
        
        # Timestamp
        snapshot_last_run_timestamp.set(latest.stat().st_mtime)
        
    except Exception as e:
        logger.error(f"Erro ao calcular tamanho do backup: {e}")


def check_systemd_logs():
    """Verifica logs systemd para falhas e sucessos"""
    try:
        # Procurar por falhas no log das últimas 24h
        result = subprocess.run(
            ['journalctl', '-u', 'rpa4all-snapshot.service', '--since', '24 hours ago', '--grep', 'Failed'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        failed_count = len([l for l in result.stdout.split('\n') if l.strip()])
        
        # Procurar por sucessos (main process exited code=exited status=0)
        result_ok = subprocess.run(
            ['journalctl', '-u', 'rpa4all-snapshot.service', '--since', '24 hours ago', '--grep', 'Finished successfully'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        success_count = len([l for l in result_ok.stdout.split('\n') if l.strip()])
        
        # Atualizar contadores (apenas incrementar novos)
        if failed_count > 0:
            snapshot_failed_count._value._value = failed_count
        if success_count > 0:
            snapshot_success_count._value._value = success_count
            
    except Exception as e:
        logger.error(f"Erro ao verificar logs: {e}")


def export_metrics():
    """Coleta todas as métricas"""
    logger.info("Coletando métricas...")
    check_service_status()
    check_lock_file()
    get_backup_size()
    check_systemd_logs()


def main():
    """Função principal"""
    logger.info("Iniciando RPA4All Snapshot Exporter na porta 9752")
    
    # Iniciar servidor HTTP para Prometheus
    start_http_server(9752)
    
    # Loop de coleta de métricas
    while True:
        try:
            export_metrics()
        except Exception as e:
            logger.error(f"Erro ao exportar métricas: {e}")
        
        time.sleep(30)  # Coletar a cada 30 segundos


if __name__ == '__main__':
    main()
