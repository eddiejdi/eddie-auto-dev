"""
Open WebUI Tool — Shared Tool Executor

Ferramenta para Open WebUI (porta 8510) que permite ao modelo executar
comandos no sistema via a API do Shared Tool Executor (porta 8503).

Instalação no Open WebUI:
    1. Acesse http://localhost:8510 → Workspace → Tools → "+"
    2. Cole o conteúdo deste arquivo inteiro
    3. Salve com nome "Shared Tool Executor"
    4. A tool ficará disponível para todos os modelos

Alternativamente via API:
    curl -X POST http://localhost:8510/api/v1/tools/create \\
      -H "Authorization: Bearer <token>" \\
      -H "Content-Type: application/json" \\
      -d '{"id":"shared-tool-executor","name":"Shared Tool Executor",
           "content":"<conteúdo deste arquivo>","meta":{"description":"..."}}'

Como funciona:
    1. Usuário pergunta: "qual o status do docker?"
    2. Open WebUI envia request com tools ao Ollama
    3. Ollama retorna tool_call: shell_exec(command="docker ps")
    4. Open WebUI executa esta Tool → chama API :8503
    5. Resultado volta ao Ollama para interpretação
    6. Usuário recebe resposta em linguagem natural

Referência:
    - https://docs.openwebui.com/tutorials/plugin/tools/
    - specialized_agents/llm_tool_schemas.py (schemas nativos)
    - specialized_agents/llm_tools_api.py (API endpoints)
"""

import os
import json
import logging
from typing import Optional

# ── Tentar importar httpx (preferido) ou requests como fallback ──
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    httpx = None
    HAS_HTTPX = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)

# ── Configuração ──
EDDIE_API_URL = os.getenv("EDDIE_API_URL", "http://localhost:8503")
TOOL_TIMEOUT = int(os.getenv("EDDIE_TOOL_TIMEOUT", "60"))


# ══════════════════════════════════════════════════════════════════════════
# Open WebUI Tool Functions
# ══════════════════════════════════════════════════════════════════════════

class Tools:
    """
    Shared Tool Executor — Permite ao modelo executar comandos no sistema.

    Ferramentas disponíveis:
    - shell_exec: Executar comandos shell (docker, systemctl, git, etc.)
    - read_file: Ler conteúdo de arquivos
    - list_directory: Listar diretórios
    - system_info: Obter informações do sistema (CPU, RAM, disco)
    """

    class Valves:
        """Configurações ajustáveis pelo admin no Open WebUI."""
        EDDIE_API_URL: str = EDDIE_API_URL
        TOOL_TIMEOUT: int = TOOL_TIMEOUT

    def __init__(self):
        self.valves = self.Valves()

    def _call_api(self, endpoint: str, method: str = "POST", payload: dict = None) -> dict:
        """Chama a API do Shared Tool Executor."""
        url = f"{self.valves.EDDIE_API_URL}/llm-tools/{endpoint}"
        timeout = self.valves.TOOL_TIMEOUT

        try:
            if HAS_HTTPX:
                with httpx.Client(timeout=timeout) as client:
                    if method == "GET":
                        resp = client.get(url)
                    else:
                        resp = client.post(url, json=payload or {})
                    resp.raise_for_status()
                    return resp.json()
            elif HAS_REQUESTS:
                if method == "GET":
                    resp = requests.get(url, timeout=timeout)
                else:
                    resp = requests.post(url, json=payload or {}, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            else:
                return {"success": False, "error": "Nem httpx nem requests disponíveis"}
        except Exception as e:
            logger.error(f"Erro ao chamar API {url}: {e}")
            return {"success": False, "error": str(e)}

    def shell_exec(
        self,
        command: str,
        timeout: int = 30,
        cwd: Optional[str] = None,
    ) -> str:
        """
        Execute a shell command on the Shared homelab system.

        Use this to run system commands like: docker ps, systemctl status,
        git log, journalctl, df -h, free -m, ps aux, etc.

        Blocked commands: rm -rf /, dd of=/dev, mkfs, shred, chmod 777 /

        :param command: The shell command to execute
        :param timeout: Timeout in seconds (default 30, max 300)
        :param cwd: Working directory (optional)
        :return: Command output (stdout) or error message
        """
        params = {"command": command, "timeout": timeout}
        if cwd:
            params["cwd"] = cwd

        result = self._call_api("execute", payload={
            "tool_name": "shell_exec",
            "params": params,
        })

        if result.get("success"):
            output = result.get("stdout", "")
            return output if output else "(comando executado sem saída)"
        else:
            error = result.get("stderr", result.get("error", "Erro desconhecido"))
            return f"ERRO: {error}"

    def read_file(
        self,
        filepath: str,
        max_lines: Optional[int] = None,
    ) -> str:
        """
        Read the contents of a file on the Shared homelab system.

        Allowed paths: /home, /tmp, /opt, /etc, /var/log
        Use max_lines to limit output for large files.

        :param filepath: Absolute path of the file to read
        :param max_lines: Maximum number of lines to read (optional)
        :return: File contents or error message
        """
        params = {"filepath": filepath}
        if max_lines:
            params["max_lines"] = max_lines

        result = self._call_api("execute", payload={
            "tool_name": "read_file",
            "params": params,
        })

        if result.get("success"):
            content = result.get("content", result.get("stdout", ""))
            return content if content else "(arquivo vazio)"
        else:
            error = result.get("error", result.get("stderr", "Erro desconhecido"))
            return f"ERRO: {error}"

    def list_directory(
        self,
        dirpath: str,
        recursive: bool = False,
    ) -> str:
        """
        List files and directories in a given path on the Shared homelab.

        Returns name, size, type, and modification date for each entry.

        :param dirpath: Directory path to list
        :param recursive: List recursively (default: false, max depth 2)
        :return: Directory listing or error message
        """
        result = self._call_api("execute", payload={
            "tool_name": "list_directory",
            "params": {"dirpath": dirpath, "recursive": recursive},
        })

        if result.get("success"):
            entries = result.get("entries", result.get("content", ""))
            if isinstance(entries, list):
                lines = []
                for e in entries:
                    name = e.get("name", "?")
                    size = e.get("size", "")
                    etype = e.get("type", "")
                    lines.append(f"{'📁' if etype == 'directory' else '📄'} {name} ({size})")
                return "\n".join(lines) if lines else "(diretório vazio)"
            return str(entries)
        else:
            error = result.get("error", result.get("stderr", "Erro desconhecido"))
            return f"ERRO: {error}"

    def system_info(self) -> str:
        """
        Get system information from the Shared homelab.

        Returns: hostname, OS, CPU count, memory usage, disk usage,
        uptime, and load averages.

        :return: System information summary
        """
        result = self._call_api("system-info", method="GET")

        if result.get("success"):
            info = result
            parts = [
                f"🖥️  Hostname: {info.get('hostname', '?')}",
                f"🐧 OS: {info.get('os', '?')}",
                f"⚙️  CPU: {info.get('cpu_count', '?')} cores ({info.get('cpu_percent', '?')}%)",
                f"🧠 RAM: {info.get('memory_used_gb', '?')}GB / {info.get('memory_total_gb', '?')}GB ({info.get('memory_percent', '?')}%)",
                f"💾 Disco: {info.get('disk_used_gb', '?')}GB / {info.get('disk_total_gb', '?')}GB ({info.get('disk_percent', '?')}%)",
                f"⏱️  Uptime: {info.get('uptime', '?')}",
                f"📊 Load: {info.get('load_avg', '?')}",
            ]
            return "\n".join(parts)
        else:
            error = result.get("error", "Erro desconhecido")
            return f"ERRO ao obter info do sistema: {error}"
