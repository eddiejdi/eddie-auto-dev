#!/usr/bin/env python3
"""
SSH Agent - Agente para conexões SSH integrado com modelos de IA
Permite executar comandos remotos, transferir arquivos e gerenciar conexões SSH
"""

import paramiko
import json
import os
import sys
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import threading
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Arquivo de configuração de hosts
CONFIG_FILE = Path(__file__).parent / "ssh_hosts.json"


@dataclass
class SSHHost:
    """Configuração de um host SSH"""
    name: str
    hostname: str
    username: str
    port: int = 22
    key_file: Optional[str] = None
    password: Optional[str] = None
    description: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SSHHost':
        return cls(**data)


class SSHAgentManager:
    """Gerenciador de conexões SSH"""
    
    def __init__(self):
        self.hosts: Dict[str, SSHHost] = {}
        self.connections: Dict[str, paramiko.SSHClient] = {}
        self.load_hosts()
    
    def load_hosts(self):
        """Carrega hosts do arquivo de configuração"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    for name, host_data in data.get('hosts', {}).items():
                        self.hosts[name] = SSHHost.from_dict(host_data)
                logger.info(f"Carregados {len(self.hosts)} hosts")
            except Exception as e:
                logger.error(f"Erro ao carregar hosts: {e}")
    
    def save_hosts(self):
        """Salva hosts no arquivo de configuração"""
        try:
            data = {
                'hosts': {name: host.to_dict() for name, host in self.hosts.items()},
                'updated_at': datetime.now().isoformat()
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Hosts salvos com sucesso")
        except Exception as e:
            logger.error(f"Erro ao salvar hosts: {e}")
    
    def add_host(self, name: str, hostname: str, username: str, 
                 port: int = 22, key_file: str = None, 
                 password: str = None, description: str = "") -> dict:
        """Adiciona um novo host SSH"""
        host = SSHHost(
            name=name,
            hostname=hostname,
            username=username,
            port=port,
            key_file=key_file,
            password=password,
            description=description
        )
        self.hosts[name] = host
        self.save_hosts()
        return {"status": "success", "message": f"Host '{name}' adicionado", "host": host.to_dict()}
    
    def remove_host(self, name: str) -> dict:
        """Remove um host SSH"""
        if name in self.hosts:
            del self.hosts[name]
            if name in self.connections:
                self.disconnect(name)
            self.save_hosts()
            return {"status": "success", "message": f"Host '{name}' removido"}
        return {"status": "error", "message": f"Host '{name}' não encontrado"}
    
    def list_hosts(self) -> dict:
        """Lista todos os hosts configurados"""
        hosts_list = []
        for name, host in self.hosts.items():
            host_info = host.to_dict()
            host_info['connected'] = name in self.connections
            # Não expor senha
            if 'password' in host_info:
                host_info['password'] = '***' if host_info['password'] else None
            hosts_list.append(host_info)
        return {"status": "success", "hosts": hosts_list, "count": len(hosts_list)}
    
    def connect(self, name: str) -> dict:
        """Estabelece conexão com um host"""
        if name not in self.hosts:
            return {"status": "error", "message": f"Host '{name}' não encontrado"}
        
        if name in self.connections:
            return {"status": "success", "message": f"Já conectado a '{name}'"}
        
        host = self.hosts[name]
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_params = {
                'hostname': host.hostname,
                'port': host.port,
                'username': host.username,
                'timeout': 10
            }
            
            # Prioriza chave SSH
            if host.key_file and os.path.exists(os.path.expanduser(host.key_file)):
                connect_params['key_filename'] = os.path.expanduser(host.key_file)
            elif host.password:
                connect_params['password'] = host.password
            
            client.connect(**connect_params)
            self.connections[name] = client
            
            logger.info(f"Conectado a '{name}' ({host.hostname})")
            return {"status": "success", "message": f"Conectado a '{name}'"}
        
        except paramiko.AuthenticationException:
            return {"status": "error", "message": f"Falha de autenticação em '{name}'"}
        except paramiko.SSHException as e:
            return {"status": "error", "message": f"Erro SSH: {str(e)}"}
        except socket.timeout:
            return {"status": "error", "message": f"Timeout ao conectar em '{name}'"}
        except Exception as e:
            return {"status": "error", "message": f"Erro: {str(e)}"}
    
    def disconnect(self, name: str) -> dict:
        """Desconecta de um host"""
        if name in self.connections:
            try:
                self.connections[name].close()
                del self.connections[name]
                logger.info(f"Desconectado de '{name}'")
                return {"status": "success", "message": f"Desconectado de '{name}'"}
            except Exception as e:
                return {"status": "error", "message": f"Erro ao desconectar: {str(e)}"}
        return {"status": "error", "message": f"Não conectado a '{name}'"}
    
    def execute(self, name: str, command: str, timeout: int = 30) -> dict:
        """Executa um comando em um host remoto"""
        # Auto-connect se necessário
        if name not in self.connections:
            result = self.connect(name)
            if result['status'] == 'error':
                return result
        
        try:
            client = self.connections[name]
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8', errors='replace')
            error = stderr.read().decode('utf-8', errors='replace')
            
            return {
                "status": "success",
                "host": name,
                "command": command,
                "exit_code": exit_code,
                "stdout": output,
                "stderr": error
            }
        
        except socket.timeout:
            return {"status": "error", "message": f"Comando expirou após {timeout}s"}
        except Exception as e:
            # Tentar reconectar
            if name in self.connections:
                del self.connections[name]
            return {"status": "error", "message": f"Erro ao executar comando: {str(e)}"}
    
    def execute_multi(self, hosts: List[str], command: str, timeout: int = 30) -> dict:
        """Executa um comando em múltiplos hosts"""
        results = {}
        for host in hosts:
            results[host] = self.execute(host, command, timeout)
        return {"status": "success", "results": results}
    
    def upload_file(self, name: str, local_path: str, remote_path: str) -> dict:
        """Faz upload de um arquivo para o host remoto"""
        if name not in self.connections:
            result = self.connect(name)
            if result['status'] == 'error':
                return result
        
        try:
            sftp = self.connections[name].open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return {
                "status": "success",
                "message": f"Arquivo enviado para {name}:{remote_path}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Erro no upload: {str(e)}"}
    
    def download_file(self, name: str, remote_path: str, local_path: str) -> dict:
        """Faz download de um arquivo do host remoto"""
        if name not in self.connections:
            result = self.connect(name)
            if result['status'] == 'error':
                return result
        
        try:
            sftp = self.connections[name].open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return {
                "status": "success",
                "message": f"Arquivo baixado de {name}:{remote_path}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Erro no download: {str(e)}"}
    
    def test_connection(self, name: str) -> dict:
        """Testa a conexão com um host"""
        result = self.execute(name, "echo 'SSH Agent Test' && hostname && uptime")
        if result['status'] == 'success':
            return {
                "status": "success",
                "message": "Conexão OK",
                "output": result['stdout']
            }
        return result
    
    def get_system_info(self, name: str) -> dict:
        """Obtém informações do sistema remoto"""
        commands = {
            "hostname": "hostname",
            "os": "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'",
            "kernel": "uname -r",
            "uptime": "uptime -p",
            "cpu": "nproc",
            "memory": "free -h | grep Mem | awk '{print $2}'",
            "disk": "df -h / | tail -1 | awk '{print $4 \" livre de \" $2}'",
            "ip": "hostname -I | awk '{print $1}'"
        }
        
        info = {}
        for key, cmd in commands.items():
            result = self.execute(name, cmd, timeout=10)
            if result['status'] == 'success':
                info[key] = result['stdout'].strip()
            else:
                info[key] = "N/A"
        
        return {"status": "success", "host": name, "info": info}
    
    def close_all(self):
        """Fecha todas as conexões"""
        for name in list(self.connections.keys()):
            self.disconnect(name)


# Instância global do manager
ssh_manager = SSHAgentManager()


# ========== API Flask para uso via HTTP ==========

def create_api_server():
    """Cria servidor Flask para API REST"""
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)
    
    @app.route('/api/hosts', methods=['GET'])
    def api_list_hosts():
        return jsonify(ssh_manager.list_hosts())
    
    @app.route('/api/hosts', methods=['POST'])
    def api_add_host():
        data = request.json
        return jsonify(ssh_manager.add_host(**data))
    
    @app.route('/api/hosts/<name>', methods=['DELETE'])
    def api_remove_host(name):
        return jsonify(ssh_manager.remove_host(name))
    
    @app.route('/api/connect/<name>', methods=['POST'])
    def api_connect(name):
        return jsonify(ssh_manager.connect(name))
    
    @app.route('/api/disconnect/<name>', methods=['POST'])
    def api_disconnect(name):
        return jsonify(ssh_manager.disconnect(name))
    
    @app.route('/api/execute', methods=['POST'])
    def api_execute():
        data = request.json
        name = data.get('host')
        command = data.get('command')
        timeout = data.get('timeout', 30)
        return jsonify(ssh_manager.execute(name, command, timeout))
    
    @app.route('/api/test/<name>', methods=['GET'])
    def api_test(name):
        return jsonify(ssh_manager.test_connection(name))
    
    @app.route('/api/info/<name>', methods=['GET'])
    def api_info(name):
        return jsonify(ssh_manager.get_system_info(name))
    
    @app.route('/api/health', methods=['GET'])
    def api_health():
        return jsonify({"status": "ok", "service": "SSH Agent"})
    
    return app


# ========== Interface de Linha de Comando ==========

def cli_interface():
    """Interface de linha de comando interativa"""
    import readline
    
    print("=" * 50)
    print("🔐 SSH Agent - Interface de Comando")
    print("=" * 50)
    print("Comandos disponíveis:")
    print("  hosts              - Lista hosts configurados")
    print("  add <name> <host> <user> [port] [key_file] - Adiciona host")
    print("  remove <name>      - Remove host")
    print("  connect <name>     - Conecta a um host")
    print("  disconnect <name>  - Desconecta de um host")
    print("  exec <name> <cmd>  - Executa comando")
    print("  test <name>        - Testa conexão")
    print("  info <name>        - Info do sistema")
    print("  exit               - Sair")
    print("=" * 50)
    
    while True:
        try:
            cmd = input("\n🔐 ssh> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            
            if action == 'exit' or action == 'quit':
                ssh_manager.close_all()
                print("Bye!")
                break
            
            elif action == 'hosts':
                result = ssh_manager.list_hosts()
                if result['hosts']:
                    for h in result['hosts']:
                        status = "🟢" if h['connected'] else "⚪"
                        print(f"  {status} {h['name']}: {h['username']}@{h['hostname']}:{h['port']}")
                        if h['description']:
                            print(f"      {h['description']}")
                else:
                    print("  Nenhum host configurado")
            
            elif action == 'add' and len(parts) > 1:
                args = parts[1].split()
                if len(args) >= 3:
                    name, hostname, username = args[:3]
                    port = int(args[3]) if len(args) > 3 else 22
                    key_file = args[4] if len(args) > 4 else None
                    result = ssh_manager.add_host(name, hostname, username, port, key_file)
                    print(f"  {result['message']}")
                else:
                    print("  Uso: add <name> <hostname> <username> [port] [key_file]")
            
            elif action == 'remove' and len(parts) > 1:
                result = ssh_manager.remove_host(parts[1])
                print(f"  {result['message']}")
            
            elif action == 'connect' and len(parts) > 1:
                result = ssh_manager.connect(parts[1])
                print(f"  {result['message']}")
            
            elif action == 'disconnect' and len(parts) > 1:
                result = ssh_manager.disconnect(parts[1])
                print(f"  {result['message']}")
            
            elif action == 'exec' and len(parts) > 1:
                args = parts[1].split(maxsplit=1)
                if len(args) >= 2:
                    name, command = args
                    result = ssh_manager.execute(name, command)
                    if result['status'] == 'success':
                        print(f"  Exit code: {result['exit_code']}")
                        if result['stdout']:
                            print(result['stdout'])
                        if result['stderr']:
                            print(f"  STDERR: {result['stderr']}")
                    else:
                        print(f"  Erro: {result['message']}")
                else:
                    print("  Uso: exec <host> <command>")
            
            elif action == 'test' and len(parts) > 1:
                result = ssh_manager.test_connection(parts[1])
                print(f"  {result['message']}")
                if 'output' in result:
                    print(result['output'])
            
            elif action == 'info' and len(parts) > 1:
                result = ssh_manager.get_system_info(parts[1])
                if result['status'] == 'success':
                    for k, v in result['info'].items():
                        print(f"  {k}: {v}")
                else:
                    print(f"  Erro: {result['message']}")
            
            else:
                print("  Comando não reconhecido. Digite 'exit' para sair.")
        
        except KeyboardInterrupt:
            print("\n  Use 'exit' para sair")
        except Exception as e:
            print(f"  Erro: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SSH Agent")
    parser.add_argument('--server', action='store_true', help='Inicia servidor API')
    parser.add_argument('--port', type=int, default=5001, help='Porta do servidor')
    parser.add_argument('--cli', action='store_true', help='Modo CLI interativo')
    parser.add_argument('--exec', nargs=2, metavar=('HOST', 'CMD'), help='Executa comando')
    parser.add_argument('--list', action='store_true', help='Lista hosts')
    
    args = parser.parse_args()
    
    if args.server:
        app = create_api_server()
        print(f"🚀 SSH Agent API rodando em http://localhost:{args.port}")
        app.run(host='0.0.0.0', port=args.port, debug=False)
    
    elif args.cli:
        cli_interface()
    
    elif args.exec:
        result = ssh_manager.execute(args.exec[0], args.exec[1])
        print(json.dumps(result, indent=2))
    
    elif args.list:
        result = ssh_manager.list_hosts()
        print(json.dumps(result, indent=2))
    
    else:
        # Modo interativo por padrão
        cli_interface()
