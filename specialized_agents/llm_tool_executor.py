"""
LLM Tool Executor - Permite ao LLM Ollama executar comandos no terminal.

Este módulo fornece uma camada de abstração que permite ao LLM invocar
ferramentas para executar comandos, análise de arquivos, etc, similar
ao function calling do GitHub Copilot.

Uso:
    executor = LLMToolExecutor()
    result = await executor.execute_tool("shell_exec", {"command": "ls -la"})
"""

import asyncio
import json
import logging
import re
import subprocess
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import psutil

logger = logging.getLogger(__name__)


class LLMToolExecutor:
    """Executor de ferramentas para LLM - simula function calling."""

    # Comandos permitidos por categoria (whitelist)
    ALLOWED_COMMANDS = {
        "system_info": [
            "uname", "lsb_release", "hostnamectl", "uptime", "whoami",
            "pwd", "date", "env", "systemctl", "journalctl", "ps", "top",
            "free", "df", "du", "lsblk", "ip", "netstat", "ss", "ifconfig",
        ],
        "files": [
            "ls", "cat", "head", "tail", "grep", "find", "wc", "file",
            "stat", "tree", "chmod", "chown", "mkdir", "rm", "cp", "mv",
            "echo", "touch", "tee", "sort", "uniq", "cut", "awk", "sed",
            "xargs", "basename", "dirname", "realpath", "readlink",
        ],
        "development": [
            "git", "docker", "python", "node", "npm", "pip", "poetry",
            "pytest", "make", "cargo", "go", "java", "javac", "gcc", "cc",
        ],
        "process": [
            "kill", "pkill", "systemctl", "service", "start", "stop",
            "restart", "status", "enable", "disable",
        ],
        "network": [
            "curl", "wget", "nc", "ncat", "telnet", "ssh", "scp",
            "ping", "traceroute", "dig", "nslookup", "host",
        ],
        "database": [
            "psql", "mysql", "mongo", "redis-cli", "pg_dump",
        ],
        "ai_tools": [
            "ollama", "pygmentize", "jq", "yq", "xmllint", "python",
        ]
    }

    # Bloqueio de padrões perigosos
    BLOCKED_PATTERNS = [
        r"rm\s+-[fr]*\s*/",  # rm -rf /
        r">\s*/dev/sd",      # > /dev/sda
        r"dd.*of=/dev/sd",   # dd of=/dev/sda
        r"mkfs",             # mkfs
        r"shred",            # shred
        r"chmod\s+777\s+/",  # chmod 777 /
    ]

    @staticmethod
    def is_command_allowed(command: str) -> tuple[bool, Optional[str]]:
        """Verifica se comando é permitido."""
        cmd_name = command.split()[0] if command else ""
        
        # Verificar bloqueios
        for pattern in LLMToolExecutor.BLOCKED_PATTERNS:
            if re.search(pattern, command):
                return False, f"Padrão bloqueado: {pattern}"
        
        # Verificar whitelist
        for category, allowed in LLMToolExecutor.ALLOWED_COMMANDS.items():
            if cmd_name in allowed or any(cmd_name.endswith(cmd) for cmd in allowed):
                return True, category
        
        return False, f"Comando '{cmd_name}' não permitido"

    async def execute_shell(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
        env_override: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Executa comando shell com segurança."""
        allowed, category = self.is_command_allowed(command)
        if not allowed:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Acesso negado: {category}",
                "exit_code": 1,
                "duration_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        try:
            # Preparar ambiente
            env = os.environ.copy()
            if env_override:
                env.update(env_override)
            
            # Executar
            start_time = datetime.utcnow()
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "success": process.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
                "command": command,
                "category": category,
            }
        
        except asyncio.TimeoutError:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Timeout após {timeout}s",
                "exit_code": -1,
                "duration_ms": timeout * 1000,
                "timestamp": datetime.utcnow().isoformat(),
                "command": command,
            }
        
        except Exception as e:
            logger.error(f"Erro ao executar comando: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": 0,
                "timestamp": datetime.utcnow().isoformat(),
                "command": command,
            }

    async def read_file(
        self,
        filepath: str,
        max_lines: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Lê arquivo com limite de segurança."""
        try:
            path = Path(filepath).resolve()
            
            # Segurança: não permitir fora de /home, /tmp, /opt, /etc, /var/log
            if not str(path).startswith(("/home", "/tmp", "/opt", "/etc", "/var/log")):
                return {
                    "success": False,
                    "content": "",
                    "error": f"Acesso negado ao caminho: {path}",
                }
            
            if not path.exists():
                return {
                    "success": False,
                    "content": "",
                    "error": f"Arquivo não existe: {path}",
                }
            
            if not path.is_file():
                return {
                    "success": False,
                    "content": "",
                    "error": f"Não é um arquivo: {path}",
                }
            
            # Limitar tamanho
            if path.stat().st_size > 10 * 1024 * 1024:  # 10 MB
                return {
                    "success": False,
                    "content": "",
                    "error": "Arquivo muito grande (>10 MB)",
                }
            
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            
            if max_lines and len(lines) > max_lines:
                lines = lines[:max_lines]
                content = "\n".join(lines)
            
            return {
                "success": True,
                "content": content,
                "size_bytes": path.stat().st_size,
                "lines": len(lines),
                "filepath": str(path),
            }
        
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return {
                "success": False,
                "content": "",
                "error": str(e),
            }

    async def list_directory(
        self,
        dirpath: str,
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """Lista diretório."""
        try:
            path = Path(dirpath).resolve()
            
            if not path.exists():
                return {
                    "success": False,
                    "entries": [],
                    "error": f"Diretório não existe: {path}",
                }
            
            if not path.is_dir():
                return {
                    "success": False,
                    "entries": [],
                    "error": f"Não é um diretório: {path}",
                }
            
            entries = []
            if recursive:
                for item in path.rglob("*"):
                    entries.append({
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
            else:
                for item in path.iterdir():
                    entries.append({
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    })
            
            return {
                "success": True,
                "entries": entries[:100],  # Limitar a 100 entradas
                "total": len(entries),
                "dirpath": str(path),
            }
        
        except Exception as e:
            logger.error(f"Erro ao listar diretório: {e}")
            return {
                "success": False,
                "entries": [],
                "error": str(e),
            }

    async def get_system_info(self) -> Dict[str, Any]:
        """Retorna informações do sistema."""
        try:
            import platform
            return {
                "success": True,
                "system": {
                    "platform": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "hostname": os.uname().nodename,
                },
                "resources": {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory": {
                        "total": psutil.virtual_memory().total,
                        "available": psutil.virtual_memory().available,
                        "percent": psutil.virtual_memory().percent,
                    },
                    "disk": {
                        "total": psutil.disk_usage("/").total,
                        "used": psutil.disk_usage("/").used,
                        "percent": psutil.disk_usage("/").percent,
                    },
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Erro ao obter info do sistema: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_available_tools(self) -> Dict[str, Any]:
        """Retorna lista de ferramentas disponíveis para o LLM."""
        return {
            "tools": [
                {
                    "name": "shell_exec",
                    "description": "Executar comando shell no terminal",
                    "parameters": {
                        "command": "str - comando a executar",
                        "timeout": "int - timeout em segundos (default 30)",
                        "cwd": "str - diretório de trabalho (opcional)",
                    },
                    "examples": [
                        {"command": "ls -la /home"},
                        {"command": "git status", "cwd": "/home/homelab/eddie-auto-dev"},
                        {"command": "docker ps", "timeout": 10},
                    ],
                },
                {
                    "name": "read_file",
                    "description": "Ler conteúdo de arquivo",
                    "parameters": {
                        "filepath": "str - caminho do arquivo",
                        "max_lines": "int - máximo de linhas (opcional)",
                    },
                },
                {
                    "name": "list_directory",
                    "description": "Listar arquivos e diretórios",
                    "parameters": {
                        "dirpath": "str - caminho do diretório",
                        "recursive": "bool - listar recursivamente (default false)",
                    },
                },
                {
                    "name": "system_info",
                    "description": "Obter informações do sistema",
                    "parameters": {},
                },
            ],
            "allowed_categories": list(self.ALLOWED_COMMANDS.keys()),
        }

    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executa uma ferramenta pelo nome."""
        if tool_name == "shell_exec":
            return await self.execute_shell(
                command=params.get("command"),
                cwd=params.get("cwd"),
                timeout=params.get("timeout", 30),
                env_override=params.get("env"),
            )
        
        elif tool_name == "read_file":
            return await self.read_file(
                filepath=params.get("filepath"),
                max_lines=params.get("max_lines"),
            )
        
        elif tool_name == "list_directory":
            return await self.list_directory(
                dirpath=params.get("dirpath"),
                recursive=params.get("recursive", False),
            )
        
        elif tool_name == "system_info":
            return await self.get_system_info()
        
        else:
            return {
                "success": False,
                "error": f"Ferramenta desconhecida: {tool_name}",
            }


# Singleton
_executor: Optional[LLMToolExecutor] = None


def get_llm_tool_executor() -> LLMToolExecutor:
    """Retorna instância singleton do executor."""
    global _executor
    if _executor is None:
        _executor = LLMToolExecutor()
    return _executor
