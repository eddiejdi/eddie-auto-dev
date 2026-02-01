#!/usr/bin/env python3
"""
SSH Agent MCP Server - Model Context Protocol
Permite que modelos de IA executem comandos SSH de forma integrada
"""

import json
import sys
import logging
from typing import Any
from ssh_agent import ssh_manager

# Configurar logging para stderr (MCP usa stdout para comunicação)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class MCPServer:
    """Servidor MCP para SSH Agent"""

    def __init__(self):
        self.tools = {
            "ssh_list_hosts": self.tool_list_hosts,
            "ssh_add_host": self.tool_add_host,
            "ssh_connect_new": self.tool_connect_new,
            "ssh_remove_host": self.tool_remove_host,
            "ssh_execute": self.tool_execute,
            "ssh_execute_on": self.tool_execute_on,
            "ssh_test_connection": self.tool_test_connection,
            "ssh_get_system_info": self.tool_get_system_info,
            "ssh_upload_file": self.tool_upload_file,
            "ssh_download_file": self.tool_download_file,
            "ssh_interactive_connect": self.tool_interactive_connect,
        }

    def get_tools_schema(self) -> list:
        """Retorna schema das ferramentas disponíveis"""
        return [
            {
                "name": "ssh_list_hosts",
                "description": "Lista todos os hosts SSH configurados e seus status de conexão",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "ssh_add_host",
                "description": "Adiciona um novo host SSH à configuração. Use para registrar servidores para acesso remoto.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nome/alias único para identificar o host (ex: 'homelab', 'webserver')",
                        },
                        "hostname": {
                            "type": "string",
                            "description": "Endereço IP ou hostname do servidor (ex: '192.168.15.2')",
                        },
                        "username": {
                            "type": "string",
                            "description": "Nome de usuário para login SSH",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Porta SSH (padrão: 22)",
                            "default": 22,
                        },
                        "key_file": {
                            "type": "string",
                            "description": "Caminho para arquivo de chave SSH (opcional)",
                        },
                        "password": {
                            "type": "string",
                            "description": "Senha para autenticação (opcional, prefira usar key_file)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Descrição do servidor",
                        },
                    },
                    "required": ["name", "hostname", "username"],
                },
            },
            {
                "name": "ssh_remove_host",
                "description": "Remove um host SSH da configuração",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Nome do host a remover",
                        }
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ssh_execute",
                "description": "Executa um comando em um servidor SSH remoto. Conecta automaticamente se necessário.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Nome do host onde executar o comando",
                        },
                        "command": {
                            "type": "string",
                            "description": "Comando a ser executado no servidor remoto",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout em segundos (padrão: 30)",
                            "default": 30,
                        },
                    },
                    "required": ["host", "command"],
                },
            },
            {
                "name": "ssh_test_connection",
                "description": "Testa a conexão SSH com um host",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string",
                            "description": "Nome do host para testar",
                        }
                    },
                    "required": ["host"],
                },
            },
            {
                "name": "ssh_get_system_info",
                "description": "Obtém informações do sistema de um servidor remoto (hostname, OS, CPU, memória, disco, etc)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "Nome do host"}
                    },
                    "required": ["host"],
                },
            },
            {
                "name": "ssh_upload_file",
                "description": "Faz upload de um arquivo para um servidor remoto via SFTP",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "Nome do host"},
                        "local_path": {
                            "type": "string",
                            "description": "Caminho do arquivo local",
                        },
                        "remote_path": {
                            "type": "string",
                            "description": "Caminho destino no servidor remoto",
                        },
                    },
                    "required": ["host", "local_path", "remote_path"],
                },
            },
            {
                "name": "ssh_download_file",
                "description": "Faz download de um arquivo de um servidor remoto via SFTP",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string", "description": "Nome do host"},
                        "remote_path": {
                            "type": "string",
                            "description": "Caminho do arquivo no servidor remoto",
                        },
                        "local_path": {
                            "type": "string",
                            "description": "Caminho destino local",
                        },
                    },
                    "required": ["host", "remote_path", "local_path"],
                },
            },
            {
                "name": "ssh_connect_new",
                "description": "CRIA UMA NOVA CONEXÃO SSH com um servidor. Use esta ferramenta quando o usuário pedir para: 'conectar em um servidor', 'acessar via SSH', 'conecte no IP X com usuário Y', 'faça login SSH em...', 'abra uma conexão com...'. Esta é a ferramenta principal para estabelecer novas conexões SSH. Após conectar, você pode executar comandos com ssh_execute.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostname": {
                            "type": "string",
                            "description": "Endereço IP ou hostname do servidor (ex: '192.168.15.1', 'meuservidor.com', '10.0.0.5')",
                        },
                        "username": {
                            "type": "string",
                            "description": "Nome de usuário para login SSH (ex: 'root', 'admin', 'ubuntu', 'homelab')",
                        },
                        "password": {
                            "type": "string",
                            "description": "Senha para autenticação SSH. Necessária se o servidor não aceitar chave pública.",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Porta SSH (padrão: 22)",
                            "default": 22,
                        },
                        "save_as": {
                            "type": "string",
                            "description": "Nome para salvar esta conexão permanentemente. Se informado, a conexão fica disponível para uso futuro via ssh_execute.",
                        },
                    },
                    "required": ["hostname", "username"],
                },
            },
            {
                "name": "ssh_execute_on",
                "description": "CONECTA E EXECUTA um comando em um servidor SSH em uma única operação. Use quando o usuário pedir: 'execute o comando X no servidor Y', 'rode isso no servidor Z', 'verifique algo no IP X'. Esta ferramenta combina conexão + execução, ideal para comandos únicos sem manter conexão.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostname": {
                            "type": "string",
                            "description": "Endereço IP ou hostname do servidor (ex: '192.168.15.2', 'servidor.local')",
                        },
                        "username": {
                            "type": "string",
                            "description": "Nome de usuário para login SSH",
                        },
                        "password": {
                            "type": "string",
                            "description": "Senha para autenticação SSH",
                        },
                        "command": {
                            "type": "string",
                            "description": "Comando a ser executado no servidor remoto (ex: 'ls -la', 'systemctl status nginx')",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Porta SSH (padrão: 22)",
                            "default": 22,
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout em segundos (padrão: 30)",
                            "default": 30,
                        },
                    },
                    "required": ["hostname", "username", "command"],
                },
            },
            {
                "name": "ssh_interactive_connect",
                "description": "Inicia processo de conexão SSH INTERATIVA. Use quando o usuário quer conectar mas NÃO forneceu todas as informações (IP, usuário ou senha). Esta ferramenta guia o processo pedindo os dados faltantes. Retorna instruções sobre quais informações solicitar ao usuário.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hostname": {
                            "type": "string",
                            "description": "IP ou hostname do servidor (pode estar vazio se usuário não informou)",
                        },
                        "username": {
                            "type": "string",
                            "description": "Usuário SSH (pode estar vazio se usuário não informou)",
                        },
                        "password": {
                            "type": "string",
                            "description": "Senha SSH (pode estar vazia)",
                        },
                        "port": {
                            "type": "integer",
                            "description": "Porta SSH",
                            "default": 22,
                        },
                    },
                    "required": [],
                },
            },
        ]

    # ===== Implementação das ferramentas =====

    def tool_list_hosts(self, arguments: dict) -> dict:
        return ssh_manager.list_hosts()

    def tool_add_host(self, arguments: dict) -> dict:
        return ssh_manager.add_host(
            name=arguments["name"],
            hostname=arguments["hostname"],
            username=arguments["username"],
            port=arguments.get("port", 22),
            key_file=arguments.get("key_file"),
            password=arguments.get("password"),
            description=arguments.get("description", ""),
        )

    def tool_remove_host(self, arguments: dict) -> dict:
        return ssh_manager.remove_host(arguments["name"])

    def tool_execute(self, arguments: dict) -> dict:
        return ssh_manager.execute(
            name=arguments["host"],
            command=arguments["command"],
            timeout=arguments.get("timeout", 30),
        )

    def tool_test_connection(self, arguments: dict) -> dict:
        return ssh_manager.test_connection(arguments["host"])

    def tool_get_system_info(self, arguments: dict) -> dict:
        return ssh_manager.get_system_info(arguments["host"])

    def tool_upload_file(self, arguments: dict) -> dict:
        return ssh_manager.upload_file(
            name=arguments["host"],
            local_path=arguments["local_path"],
            remote_path=arguments["remote_path"],
        )

    def tool_download_file(self, arguments: dict) -> dict:
        return ssh_manager.download_file(
            name=arguments["host"],
            remote_path=arguments["remote_path"],
            local_path=arguments["local_path"],
        )

    def tool_connect_new(self, arguments: dict) -> dict:
        """Conecta em um servidor novo diretamente"""
        import paramiko
        import socket

        hostname = arguments["hostname"]
        username = arguments["username"]
        password = arguments.get("password")
        port = arguments.get("port", 22)
        save_as = arguments.get("save_as")

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_params = {
                "hostname": hostname,
                "port": port,
                "username": username,
                "timeout": 10,
            }

            if password:
                connect_params["password"] = password

            client.connect(**connect_params)

            # Testa a conexão
            stdin, stdout, stderr = client.exec_command(
                "hostname && echo 'Conexão estabelecida!'"
            )
            output = stdout.read().decode("utf-8", errors="replace")

            # Se pediu para salvar, adiciona ao manager
            if save_as:
                ssh_manager.add_host(
                    name=save_as,
                    hostname=hostname,
                    username=username,
                    port=port,
                    password=password,
                    description="Adicionado via conexão direta",
                )
                ssh_manager.connections[save_as] = client
                return {
                    "status": "success",
                    "message": f"Conectado e salvo como '{save_as}'",
                    "hostname": hostname,
                    "username": username,
                    "output": output.strip(),
                }
            else:
                # Conexão temporária
                temp_name = f"temp_{hostname.replace('.', '_')}"
                ssh_manager.connections[temp_name] = client
                return {
                    "status": "success",
                    "message": f"Conectado temporariamente a {username}@{hostname}",
                    "temp_name": temp_name,
                    "hostname": hostname,
                    "username": username,
                    "output": output.strip(),
                    "note": "Use o temp_name para executar comandos ou save_as para salvar permanentemente",
                }

        except paramiko.AuthenticationException:
            return {
                "status": "error",
                "message": f"Falha de autenticação em {username}@{hostname}. Verifique usuário/senha.",
            }
        except paramiko.SSHException as e:
            return {"status": "error", "message": f"Erro SSH: {str(e)}"}
        except socket.timeout:
            return {"status": "error", "message": f"Timeout ao conectar em {hostname}"}
        except socket.gaierror:
            return {
                "status": "error",
                "message": f"Não foi possível resolver o hostname: {hostname}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Erro: {str(e)}"}

    def tool_execute_on(self, arguments: dict) -> dict:
        """Executa comando em servidor sem configuração prévia"""
        import paramiko
        import socket

        hostname = arguments["hostname"]
        username = arguments["username"]
        password = arguments.get("password")
        command = arguments["command"]
        port = arguments.get("port", 22)
        timeout = arguments.get("timeout", 30)

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_params = {
                "hostname": hostname,
                "port": port,
                "username": username,
                "timeout": 10,
            }

            if password:
                connect_params["password"] = password

            client.connect(**connect_params)

            # Executa o comando
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")

            client.close()

            return {
                "status": "success",
                "hostname": hostname,
                "username": username,
                "command": command,
                "exit_code": exit_code,
                "stdout": output,
                "stderr": error,
            }

        except paramiko.AuthenticationException:
            return {
                "status": "error",
                "message": f"Falha de autenticação em {username}@{hostname}",
            }
        except paramiko.SSHException as e:
            return {"status": "error", "message": f"Erro SSH: {str(e)}"}
        except socket.timeout:
            return {
                "status": "error",
                "message": f"Timeout ao conectar/executar em {hostname}",
            }
        except Exception as e:
            return {"status": "error", "message": f"Erro: {str(e)}"}

    def tool_interactive_connect(self, arguments: dict) -> dict:
        """Conexão SSH interativa - guia o processo quando faltam informações"""
        hostname = arguments.get("hostname", "").strip()
        username = arguments.get("username", "").strip()
        password = arguments.get("password", "").strip()
        port = arguments.get("port", 22)

        missing = []
        if not hostname:
            missing.append("hostname/IP do servidor")
        if not username:
            missing.append("nome de usuário")

        # Se faltam informações, retorna instruções
        if missing:
            hosts = ssh_manager.list_hosts()
            saved_hosts = hosts.get("hosts", [])

            response = {
                "status": "need_info",
                "message": f"Para conectar via SSH, preciso das seguintes informações: {', '.join(missing)}",
                "missing_fields": missing,
                "instructions": "Por favor, pergunte ao usuário:",
            }

            if not hostname:
                response["ask_hostname"] = (
                    "Qual o IP ou hostname do servidor? (ex: 192.168.1.100, servidor.exemplo.com)"
                )
            if not username:
                response["ask_username"] = (
                    "Qual o nome de usuário para login SSH? (ex: root, admin, ubuntu)"
                )

            if saved_hosts:
                response["tip"] = (
                    f"Dica: Existem {len(saved_hosts)} hosts salvos. Use ssh_list_hosts para ver."
                )
                response["saved_hosts"] = [h["name"] for h in saved_hosts]

            return response

        # Se senha não foi fornecida, tentar conexão com chave
        if not password:
            # Primeiro tenta sem senha (usando chave SSH)
            import paramiko
            import socket

            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=hostname, port=port, username=username, timeout=10
                )

                stdin, stdout, stderr = client.exec_command("hostname")
                remote_hostname = stdout.read().decode("utf-8").strip()

                temp_name = f"temp_{hostname.replace('.', '_')}"
                ssh_manager.connections[temp_name] = client

                return {
                    "status": "success",
                    "message": "Conectado com sucesso via chave SSH!",
                    "hostname": hostname,
                    "username": username,
                    "remote_hostname": remote_hostname,
                    "temp_name": temp_name,
                    "note": "Conexão estabelecida usando chave SSH (sem senha)",
                }
            except paramiko.AuthenticationException:
                return {
                    "status": "need_password",
                    "message": "Conexão com chave SSH falhou. É necessário fornecer a senha.",
                    "hostname": hostname,
                    "username": username,
                    "ask_password": f"Qual a senha para {username}@{hostname}?",
                    "instructions": "Pergunte a senha ao usuário e tente novamente com ssh_connect_new",
                }
            except socket.timeout:
                return {
                    "status": "error",
                    "message": f"Timeout ao conectar em {hostname}. Verifique se o IP está correto e o servidor está acessível.",
                }
            except socket.gaierror:
                return {
                    "status": "error",
                    "message": f"Não foi possível resolver: {hostname}. Verifique o hostname/IP.",
                }
            except Exception as e:
                return {
                    "status": "need_password",
                    "message": f"Erro na conexão: {str(e)}. Tente fornecer a senha.",
                    "hostname": hostname,
                    "username": username,
                    "ask_password": f"Qual a senha para {username}@{hostname}?",
                }

        # Se temos tudo, conecta
        return self.tool_connect_new(
            {
                "hostname": hostname,
                "username": username,
                "password": password,
                "port": port,
            }
        )

    # ===== Protocolo MCP =====

    def handle_request(self, request: dict) -> dict:
        """Processa uma requisição MCP"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        try:
            if method == "initialize":
                return self.response(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "ssh-agent", "version": "1.0.0"},
                    },
                )

            elif method == "notifications/initialized":
                return None  # Notificação, não precisa resposta

            elif method == "tools/list":
                return self.response(req_id, {"tools": self.get_tools_schema()})

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name in self.tools:
                    result = self.tools[tool_name](arguments)
                    return self.response(
                        req_id,
                        {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        result, indent=2, ensure_ascii=False
                                    ),
                                }
                            ]
                        },
                    )
                else:
                    return self.error(
                        req_id, -32601, f"Tool não encontrada: {tool_name}"
                    )

            elif method == "ping":
                return self.response(req_id, {})

            else:
                return self.error(req_id, -32601, f"Método não suportado: {method}")

        except Exception as e:
            logger.error(f"Erro ao processar requisição: {e}")
            return self.error(req_id, -32603, str(e))

    def response(self, req_id: Any, result: dict) -> dict:
        """Cria resposta de sucesso"""
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def error(self, req_id: Any, code: int, message: str) -> dict:
        """Cria resposta de erro"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def run(self):
        """Executa o servidor MCP (comunicação via stdin/stdout)"""
        logger.info("SSH Agent MCP Server iniciado")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                logger.info(f"Requisição: {request.get('method', 'unknown')}")

                response = self.handle_request(request)

                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"JSON inválido: {e}")
            except Exception as e:
                logger.error(f"Erro: {e}")

        logger.info("SSH Agent MCP Server encerrado")


if __name__ == "__main__":
    server = MCPServer()
    server.run()
