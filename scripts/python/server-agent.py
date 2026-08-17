#!/usr/bin/env python3
"""Agente de Administração Completo do Servidor"""
import os, sys, json, subprocess, time, psutil
from datetime import datetime
from pathlib import Path

class ServerAgent:
    def __init__(self):
        self.hostname = subprocess.getoutput('hostname')
        self.log_dir = Path('/var/log/server-agent')
        self.create_log_dir()
    
    def create_log_dir(self):
        try:
            self.log_dir.mkdir(exist_ok=True, mode=0o755)
        except: pass
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        try:
            with open(f'{self.log_dir}/agent.log', 'a') as f:
                f.write(log_msg + '\n')
            print(log_msg)
        except: print(message)
    
    def run_command(self, cmd, sudo=False):
        try:
            if sudo: cmd = f"sudo {cmd}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, "", str(e)
    
    def status_sistema(self):
        print("\n" + "="*60)
        print("STATUS DO SISTEMA")
        print("="*60)
        uptime = subprocess.getoutput('uptime')
        print(f"Uptime: {uptime}")
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        print(f"CPU: {cpu_percent}% ({cpu_count} núcleos)")
        memory = psutil.virtual_memory()
        print(f"Memória: {memory.percent}% ({memory.available // (1024**3)}GB disponível)")
        disco = psutil.disk_usage('/')
        print(f"Disco: {disco.percent}% ({disco.free // (1024**3)}GB livre)")
    
    def fazer_backup(self):
        print("\n" + "="*60)
        print("BACKUP")
        print("="*60)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/tmp/backup_servidor_{timestamp}.tar.gz"
        print(f"Criando backup em {backup_file}...")
        rc, out, err = self.run_command(
            f'tar -czf {backup_file} /home /etc --exclude=cache --exclude=.cache 2>/dev/null',
            sudo=True
        )
        if rc == 0:
            size = os.path.getsize(backup_file) / (1024**3)
            print(f"✓ Backup criado ({size:.2f}GB)")
            self.log(f"Backup criado: {backup_file}", "INFO")
        else:
            print(f"✗ Erro ao criar backup")
    
    def menu_principal(self):
        while True:
            os.system('clear')
            print("╔" + "="*58 + "╗")
            print("║" + " "*15 + "AGENTE DE ADMINISTRAÇÃO DO SERVIDOR" + " "*7 + "║")
            print("║" + f" "*20 + f"Servidor: {self.hostname}" + " "*(58-len(self.hostname)-20) + "║")
            print("╚" + "="*58 + "╝")
            print("\n1.  Status do Sistema")
            print("2.  Fazer Backup")
            print("3.  Ver Logs")
            print("0.  Sair")
            print()
            
            opcao = input("Escolha: ").strip()
            if opcao == "1":
                self.status_sistema()
            elif opcao == "2":
                self.fazer_backup()
            elif opcao == "3":
                os.system(f"tail -30 {self.log_dir}/agent.log")
            elif opcao == "0":
                print("Encerrando...")
                sys.exit(0)
            
            input("\nPressione ENTER para continuar...")

if __name__ == "__main__":
    agent = ServerAgent()
    agent.menu_principal()
