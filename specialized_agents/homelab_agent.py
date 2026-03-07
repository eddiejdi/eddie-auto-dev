"""
Homelab Agent — Execução remota segura de comandos no homelab via SSH.

Funcionalidades:
- Validação de IP (apenas rede local RFC 1918 permitida)
- Whitelist/blocklist de comandos por categoria
- Audit log de todas as operações
- Comandos de conveniência (docker, systemd, sistema)
"""

import ipaddress
import logging
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Flag para indicar se paramiko está disponível
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    paramiko = None  # type: ignore[assignment]
    PARAMIKO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Enums e tipos
# ---------------------------------------------------------------------------

class CommandCategory(Enum):
    """Categorias de comandos permitidos no homelab."""
    SYSTEM_INFO = "system_info"
    DOCKER = "docker"
    SYSTEMD = "systemd"
    LOGS = "logs"
    FILES = "files"
    NETWORK = "network"
    PROCESS = "process"
    CUSTOM = "custom"


@dataclass
class AuditEntry:
    """Entrada de audit log para operações no homelab."""
    timestamp: str
    command: str
    caller_ip: str = ""
    success: bool = False
    exit_code: int = -1
    duration_ms: float = 0.0
    error: Optional[str] = None
    category: Optional[str] = None


@dataclass
class RunResult:
    """Resultado de execução de comando remoto."""
    success: bool
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: float = 0.0
    timestamp: str = ""
    error: Optional[str] = None
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Padrões de comandos
# ---------------------------------------------------------------------------

# Comandos perigosos que NUNCA devem ser executados
_BLOCKED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-\w+\s+)*/(etc|var|home|boot|usr|lib|bin|sbin|root|sys|proc|dev)?\b"),
    re.compile(r"\brm\s+(-\w+\s+)*/\s*$"),
    re.compile(r"\brm\s+-rf\s+/"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+if=.*of=/dev/"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bhalt\b"),
    re.compile(r"\bpoweroff\b"),
    re.compile(r"\bpasswd\b"),
    re.compile(r"\buseradd\b"),
    re.compile(r"\buserdel\b"),
    re.compile(r"\bgroupadd\b"),
    re.compile(r"\bgroupdel\b"),
    re.compile(r"\bchmod\s+777\b"),
    re.compile(r"\bchown\s+root\b"),
    re.compile(r":\(\)\s*\{.*\}"),  # fork bomb
    re.compile(r"\bcurl\b.*\|\s*(ba)?sh"),
    re.compile(r"\bwget\b.*\|\s*(ba)?sh"),
    re.compile(r"\bapt\s+(install|remove|purge)\b"),
    re.compile(r"\byum\s+(install|remove)\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bpython3?\s+-c\b"),
    re.compile(r"\beval\b"),
    re.compile(r"\bexec\b"),
]

# Padrões de comandos permitidos por categoria
_ALLOWED_PATTERNS: Dict[CommandCategory, list[re.Pattern[str]]] = {
    CommandCategory.SYSTEM_INFO: [
        re.compile(r"^uptime"),
        re.compile(r"^free(\s|$)"),
        re.compile(r"^df(\s|$)"),
        re.compile(r"^hostname"),
        re.compile(r"^uname(\s|$)"),
        re.compile(r"^cat\s+/proc/(loadavg|cpuinfo|meminfo|version)"),
        re.compile(r"^lsb_release"),
        re.compile(r"^top\s+-bn1"),
        re.compile(r"^w$"),
        re.compile(r"^who$"),
        re.compile(r"^date$"),
        re.compile(r"^timedatectl"),
        re.compile(r"^lscpu"),
        re.compile(r"^lsblk"),
        re.compile(r"^lspci"),
        re.compile(r"^nvidia-smi"),
    ],
    CommandCategory.DOCKER: [
        re.compile(r"^docker\s+(ps|images|stats|info|version|inspect|top|port|diff)"),
        re.compile(r"^docker\s+logs\b"),
        re.compile(r"^docker\s+restart\b"),
        re.compile(r"^docker\s+start\b"),
        re.compile(r"^docker\s+stop\b"),
        re.compile(r"^docker\s+compose\s+(ps|logs|up|down|restart|config)"),
    ],
    CommandCategory.SYSTEMD: [
        re.compile(r"^systemctl\s+(status|restart|start|stop|is-active|is-enabled|list-units|show)"),
        re.compile(r"^journalctl\b"),
    ],
    CommandCategory.FILES: [
        re.compile(r"^ls(\s|$)"),
        re.compile(r"^cat\s"),
        re.compile(r"^tail(\s|$)"),
        re.compile(r"^head(\s|$)"),
        re.compile(r"^grep(\s|$)"),
        re.compile(r"^find\s"),
        re.compile(r"^wc(\s|$)"),
        re.compile(r"^du(\s|$)"),
        re.compile(r"^stat(\s|$)"),
        re.compile(r"^file(\s|$)"),
        re.compile(r"^md5sum(\s|$)"),
    ],
    CommandCategory.LOGS: [
        re.compile(r"^journalctl\b"),
        re.compile(r"^tail\s+.*\.(log|txt)"),
        re.compile(r"^cat\s+/var/log/"),
        re.compile(r"^less\s+/var/log/"),
        re.compile(r"^zcat\s+/var/log/"),
    ],
    CommandCategory.NETWORK: [
        re.compile(r"^ip\s+(addr|link|route|neigh)"),
        re.compile(r"^ss(\s|$)"),
        re.compile(r"^netstat(\s|$)"),
        re.compile(r"^ping\s"),
        re.compile(r"^traceroute\s"),
        re.compile(r"^nslookup\s"),
        re.compile(r"^dig\s"),
        re.compile(r"^curl\s+(-s\s+)?http"),
        re.compile(r"^wget\s+-q"),
        re.compile(r"^ifconfig"),
    ],
    CommandCategory.PROCESS: [
        re.compile(r"^ps(\s|$)"),
        re.compile(r"^pgrep(\s|$)"),
        re.compile(r"^pidof(\s|$)"),
        re.compile(r"^kill\s+-0\s"),
        re.compile(r"^htop\b"),
    ],
    CommandCategory.CUSTOM: [],
}


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def is_local_ip(ip: str) -> bool:
    """Verifica se um IP está em rede local (RFC 1918, loopback, link-local)."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def classify_command(cmd: str) -> Optional[CommandCategory]:
    """Classifica um comando por categoria da whitelist.

    Retorna None se o comando for bloqueado ou desconhecido.
    Suporta pipes: bloqueia se qualquer parte do pipe for perigosa.
    """
    if not cmd or not cmd.strip():
        return None

    cmd = cmd.strip()

    # Verificar o comando completo contra a blocklist primeiro
    if _is_blocked(cmd):
        return None

    # Se contém pipe, avaliar cada parte
    if "|" in cmd:
        parts = [p.strip() for p in cmd.split("|")]
        # Verificar se alguma parte é bloqueada
        for part in parts:
            if _is_blocked(part):
                return None
        # Classificar pela primeira parte
        return _classify_single(parts[0])

    # Comando simples
    if _is_blocked(cmd):
        return None
    return _classify_single(cmd)


def _is_blocked(cmd: str) -> bool:
    """Verifica se um comando está na blocklist."""
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(cmd):
            return True
    return False


def _classify_single(cmd: str) -> Optional[CommandCategory]:
    """Classifica um comando simples (sem pipe)."""
    for category, patterns in _ALLOWED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(cmd):
                return category
    return None


# ---------------------------------------------------------------------------
# Classe principal
# ---------------------------------------------------------------------------

class HomelabAgent:
    """Agente para execução remota segura de comandos no homelab via SSH."""

    def __init__(
        self,
        host: str = "192.168.15.2",
        user: str = "homelab",
        ssh_key: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """Inicializa o HomelabAgent.

        Args:
            host: Endereço IP do servidor homelab (deve ser rede local).
            user: Usuário SSH.
            ssh_key: Caminho para chave SSH (opcional).
            timeout: Timeout padrão para comandos em segundos.

        Raises:
            ValueError: Se o host não estiver em rede local.
        """
        if not is_local_ip(host):
            raise ValueError(
                f"Host {host} não está em rede local. "
                f"O HomelabAgent só aceita conexões para redes RFC 1918."
            )

        self.host = host
        self.user = user
        self.ssh_key = ssh_key
        self.timeout = timeout
        self.audit_log: list[dict[str, Any]] = []
        self._ssh_client: Optional[Any] = None

    def _connect(self) -> Any:
        """Estabelece conexão SSH com o homelab."""
        if not PARAMIKO_AVAILABLE:
            raise RuntimeError("paramiko não está instalado")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: Dict[str, Any] = {
            "hostname": self.host,
            "username": self.user,
            "timeout": 10,
        }

        if self.ssh_key:
            from pathlib import Path
            key_path = Path(self.ssh_key).expanduser()
            if key_path.exists():
                try:
                    pkey = paramiko.RSAKey.from_private_key_file(str(key_path))
                    connect_kwargs["pkey"] = pkey
                except Exception:
                    pass

        client.connect(**connect_kwargs)
        return client

    def is_available(self) -> bool:
        """Verifica se o homelab está acessível via SSH."""
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command("echo ok", timeout=5)
            out = stdout.read().decode().strip()
            client.close()
            return out == "ok"
        except Exception:
            return False

    def validate_command(self, cmd: str) -> Tuple[bool, Optional[str], Optional[CommandCategory]]:
        """Valida se um comando é permitido pelo whitelist.

        Returns:
            Tupla (allowed, reason, category).
        """
        category = classify_command(cmd)
        if category is not None:
            return True, None, category
        return False, f"Comando bloqueado ou desconhecido: {cmd}", None

    async def execute(
        self,
        cmd: str,
        timeout: Optional[int] = None,
        caller_ip: str = "127.0.0.1",
    ) -> RunResult:
        """Executa um comando no homelab com validação de segurança.

        Args:
            cmd: Comando a executar.
            timeout: Timeout em segundos.
            caller_ip: IP do chamador (para audit e validação).

        Returns:
            RunResult com o resultado da execução.
        """
        ts = datetime.now().isoformat()
        effective_timeout = timeout or self.timeout

        # Validar IP do chamador
        if not is_local_ip(caller_ip):
            error = f"Acesso negado: IP {caller_ip} não está em rede local"
            result = RunResult(
                success=False,
                command=cmd,
                error=error,
                timestamp=ts,
            )
            self._audit(AuditEntry(
                timestamp=ts,
                command=cmd,
                caller_ip=caller_ip,
                success=False,
                error=error,
            ))
            return result

        # Validar comando
        allowed, reason, category = self.validate_command(cmd)
        if not allowed:
            error = f"Comando bloqueado: {reason}"
            result = RunResult(
                success=False,
                command=cmd,
                error=error,
                timestamp=ts,
                category=category.value if category else None,
            )
            self._audit(AuditEntry(
                timestamp=ts,
                command=cmd,
                caller_ip=caller_ip,
                success=False,
                error=error,
            ))
            return result

        # Executar
        result = await self._exec_async(cmd, effective_timeout)
        result.category = category.value if category else None
        result.timestamp = ts

        self._audit(AuditEntry(
            timestamp=ts,
            command=cmd,
            caller_ip=caller_ip,
            success=result.success,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            category=category.value if category else None,
        ))

        return result

    def _exec_once(self, cmd: str, timeout: int = 30) -> RunResult:
        """Executa um comando via SSH (síncrono)."""
        start = time.monotonic()
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode()
            err = stderr.read().decode()
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            duration = (time.monotonic() - start) * 1000
            return RunResult(
                success=exit_code == 0,
                command=cmd,
                stdout=out,
                stderr=err,
                exit_code=exit_code,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            return RunResult(
                success=False,
                command=cmd,
                error=str(e),
                exit_code=-1,
                duration_ms=duration,
            )

    async def _exec_async(self, cmd: str, timeout: int = 30) -> RunResult:
        """Executa comando de forma assíncrona (usa threadpool para SSH)."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._exec_once, cmd, timeout)

    def _audit(self, entry: AuditEntry) -> None:
        """Registra entrada no audit log."""
        self.audit_log.append(asdict(entry))

    def get_audit_log(self, last_n: int = 50) -> list[dict[str, Any]]:
        """Retorna as últimas N entradas do audit log."""
        return self.audit_log[-last_n:]

    def add_allowed_pattern(self, category: CommandCategory, pattern: str) -> None:
        """Adiciona um padrão regex à whitelist de comandos permitidos.

        Args:
            category: Categoria do comando.
            pattern: Regex do padrão a permitir.
        """
        compiled = re.compile(pattern)
        _ALLOWED_PATTERNS.setdefault(category, []).append(compiled)

    def get_allowed_categories(self) -> Dict[str, list[str]]:
        """Retorna categorias e padrões de comandos permitidos."""
        result: Dict[str, list[str]] = {}
        for cat, patterns in _ALLOWED_PATTERNS.items():
            result[cat.value] = [p.pattern for p in patterns]
        return result

    # -----------------------------------------------------------------------
    # Métodos de conveniência
    # -----------------------------------------------------------------------

    async def docker_ps(self, all_containers: bool = False) -> RunResult:
        """Lista containers Docker."""
        cmd = "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
        if all_containers:
            cmd = "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
        return await self._exec_async(cmd)

    async def docker_logs(self, container: str, tail: int = 50) -> RunResult:
        """Obtém logs de um container."""
        return await self._exec_async(f"docker logs --tail {tail} {container}")

    async def docker_stats(self) -> RunResult:
        """Uso de recursos dos containers."""
        return await self._exec_async("docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'")

    async def docker_restart(self, container: str) -> RunResult:
        """Reinicia um container."""
        return await self._exec_async(f"docker restart {container}")

    async def systemctl_status(self, service: str) -> RunResult:
        """Status de um serviço systemd."""
        return await self._exec_async(f"systemctl status {service}")

    async def systemctl_restart(self, service: str) -> RunResult:
        """Reinicia um serviço systemd."""
        return await self._exec_async(f"systemctl restart {service}")

    async def systemctl_list(self, state: str = "running") -> RunResult:
        """Lista serviços systemd."""
        return await self._exec_async(f"systemctl list-units --type=service --state={state}")

    async def journalctl(self, service: str, lines: int = 50) -> RunResult:
        """Logs de serviço via journalctl."""
        return await self._exec_async(f"journalctl -u {service} -n {lines} --no-pager")

    async def disk_usage(self, path: str = "/") -> RunResult:
        """Uso de disco."""
        return await self._exec_async(f"df -h {path}")

    async def memory_usage(self) -> RunResult:
        """Uso de memória."""
        return await self._exec_async("free -h")

    async def cpu_info(self) -> RunResult:
        """Informação de CPU e carga."""
        return await self._exec_async("uptime && echo '---' && lscpu | head -20")

    async def network_info(self) -> RunResult:
        """Interfaces de rede."""
        return await self._exec_async("ip addr show")

    async def list_listening_ports(self) -> RunResult:
        """Portas em escuta."""
        return await self._exec_async("ss -tlnp")

    async def server_health(self) -> Dict[str, Any]:
        """Status completo do servidor homelab."""
        commands = {
            "uptime": "uptime",
            "memory": "free -h",
            "disk": "df -h /",
            "load": "cat /proc/loadavg",
            "docker": "docker ps --format '{{.Names}}: {{.Status}}'",
        }
        results: Dict[str, Any] = {}
        for key, cmd in commands.items():
            r = await self._exec_async(cmd)
            results[key] = {
                "stdout": r.stdout.strip(),
                "success": r.success,
            }
        return results


# ---------------------------------------------------------------------------
# Singleton / Factory
# ---------------------------------------------------------------------------

_instance: Optional[HomelabAgent] = None


def get_homelab_agent(
    host: str = "192.168.15.2",
    user: str = "homelab",
) -> HomelabAgent:
    """Retorna instância singleton do HomelabAgent."""
    global _instance
    if _instance is None:
        _instance = HomelabAgent(host=host, user=user)
    return _instance
