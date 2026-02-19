"""
Agent Auto-Scaling Manager v2
Gerencia escalonamento automatico de agents com Docker REAL.
"""
import asyncio
import subprocess
import psutil
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

try:
    from .config import AUTOSCALING_CONFIG, SYNERGY_CONFIG
except ImportError:
    AUTOSCALING_CONFIG = {
        "enabled": True,
        "min_agents": 2,
        "max_agents": 16,
        "cpu_scale_up_threshold": 50,
        "cpu_scale_down_threshold": 80,
        "scale_check_interval_seconds": 60,
        "scale_up_increment": 2,
        "scale_down_increment": 1,
        "cooldown_seconds": 120,
    }
    SYNERGY_CONFIG = {
        "communication_bus_enabled": True,
        "max_parallel_tasks_per_agent": 3,
    }

CONTAINER_PREFIX = "spec_agent"


class ScaleAction(Enum):
    NONE = "none"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class ResourceMetrics:
    """Metricas de recursos do sistema."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_containers: int
    stopped_containers: int
    pending_tasks: int
    timestamp: datetime


@dataclass
class ScalingDecision:
    """Decisao de escalonamento."""
    action: ScaleAction
    current_agents: int
    target_agents: int
    reason: str
    metrics: ResourceMetrics
    containers_to_stop: List[str] = field(default_factory=list)
    containers_to_start: List[str] = field(default_factory=list)


class AgentAutoScaler:
    """
    Gerencia auto-scaling de agents baseado em uso de CPU/memoria.

    v2: Integracao REAL com Docker containers.
        - Sync counter com containers reais via 'docker ps'
        - Scale DOWN: para containers ociosos quando CPU > threshold
        - Scale UP: reinicia containers parados quando CPU < threshold
        - Safeguard: nunca cria novos containers, apenas start/stop existentes
        - Cleanup periodico de containers zumbi (Created)
    """

    def __init__(self):
        self.config = AUTOSCALING_CONFIG
        self.current_agents = 0
        self.last_scale_action = None
        self.last_scale_time = 0
        self.metrics_history: List[ResourceMetrics] = []
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._sync_container_count()

    def _run_docker_cmd(self, args: List[str], timeout: int = 30) -> tuple:
        """Executa comando Docker e retorna (success, stdout, stderr)."""
        try:
            result = subprocess.run(
                ["docker"] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return (result.returncode == 0, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            logger.warning(f"Docker cmd timeout: docker {' '.join(args)}")
            return (False, "", "timeout")
        except FileNotFoundError:
            return (False, "", "docker not found")
        except Exception as e:
            return (False, "", str(e))

    def _get_running_containers(self) -> List[Dict]:
        """Lista containers spec_agent em execucao."""
        ok, stdout, _ = self._run_docker_cmd([
            "ps", "--filter", f"name={CONTAINER_PREFIX}",
            "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"
        ])
        if not ok or not stdout:
            return []
        containers = []
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                containers.append({"id": parts[0], "name": parts[1], "status": parts[2] if len(parts) > 2 else "unknown"})
        return containers

    def _get_stopped_containers(self) -> List[Dict]:
        """Lista containers spec_agent parados (exited)."""
        ok, stdout, _ = self._run_docker_cmd([
            "ps", "-a", "--filter", f"name={CONTAINER_PREFIX}",
            "--filter", "status=exited",
            "--format", "{{.ID}}\t{{.Names}}\t{{.Status}}"
        ])
        if not ok or not stdout:
            return []
        containers = []
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                containers.append({"id": parts[0], "name": parts[1], "status": parts[2] if len(parts) > 2 else "exited"})
        return containers

    def _get_container_cpu_usage(self, container_id: str) -> float:
        """Obtem uso de CPU de um container."""
        ok, stdout, _ = self._run_docker_cmd([
            "stats", "--no-stream", "--format", "{{.CPUPerc}}", container_id
        ], timeout=15)
        if ok and stdout:
            try:
                return float(stdout.replace("%", ""))
            except ValueError:
                pass
        return 0.0

    def _find_idle_containers(self, running: List[Dict], count: int) -> List[str]:
        """Encontra containers ociosos (menor uso de CPU)."""
        usage = []
        for c in running:
            cpu = self._get_container_cpu_usage(c["id"])
            usage.append((c["id"], c["name"], cpu))
        usage.sort(key=lambda x: x[2])
        return [u[0] for u in usage[:count]]

    def _sync_container_count(self):
        """Sincroniza counter com containers Docker reais."""
        running = self._get_running_containers()
        self.current_agents = len(running)
        return self.current_agents

    def _cleanup_created_containers(self):
        """Remove containers spec_agent em estado Created (nunca iniciados)."""
        ok, stdout, _ = self._run_docker_cmd([
            "ps", "-a", "--filter", f"name={CONTAINER_PREFIX}",
            "--filter", "status=created", "-q"
        ])
        if ok and stdout:
            ids = [cid.strip() for cid in stdout.split("\n") if cid.strip()]
            if ids:
                logger.warning(f"Removendo {len(ids)} containers zumbi (Created)")
                for cid in ids:
                    self._run_docker_cmd(["rm", "-f", cid])

    async def start(self):
        """Inicia monitoramento de auto-scaling."""
        if not self.config.get("enabled", True):
            logger.info("Auto-scaling desabilitado")
            return
        self._cleanup_created_containers()
        self._sync_container_count()
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Auto-scaler v2 iniciado (containers reais: {self.current_agents})")

    async def stop(self):
        """Para monitoramento."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Auto-scaler parado")

    async def _monitor_loop(self):
        """Loop principal de monitoramento."""
        cycle = 0
        while self.running:
            try:
                self._sync_container_count()
                metrics = self._collect_metrics()
                self.metrics_history.append(metrics)

                cutoff = datetime.now().timestamp() - 600
                self.metrics_history = [
                    m for m in self.metrics_history
                    if m.timestamp.timestamp() > cutoff
                ]

                decision = self._evaluate_scaling(metrics)
                if decision.action != ScaleAction.NONE:
                    await self._execute_scaling(decision)

                cycle += 1
                if cycle % 20 == 0:
                    self._cleanup_created_containers()

                await asyncio.sleep(self.config.get("scale_check_interval_seconds", 60))
            except Exception as e:
                logger.error(f"Erro no auto-scaler: {e}")
                await asyncio.sleep(30)

    def _collect_metrics(self) -> ResourceMetrics:
        """Coleta metricas atuais."""
        running = self._get_running_containers()
        stopped = self._get_stopped_containers()
        return ResourceMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage('/').percent,
            active_containers=len(running),
            stopped_containers=len(stopped),
            pending_tasks=self._get_pending_tasks(),
            timestamp=datetime.now()
        )

    def _get_pending_tasks(self) -> int:
        """Obtem tarefas pendentes."""
        try:
            from .agent_communication_bus import get_communication_bus
            bus = get_communication_bus()
            if hasattr(bus, 'pending_count'):
                return bus.pending_count()
        except Exception:
            pass
        return 0

    def _evaluate_scaling(self, metrics: ResourceMetrics) -> ScalingDecision:
        """Avalia se deve escalar."""
        cooldown = self.config.get("cooldown_seconds", 120)
        if time.time() - self.last_scale_time < cooldown:
            return ScalingDecision(
                action=ScaleAction.NONE, current_agents=self.current_agents,
                target_agents=self.current_agents, reason="Em cooldown", metrics=metrics
            )

        recent = [m for m in self.metrics_history if (datetime.now() - m.timestamp).total_seconds() < 60]
        if not recent:
            recent = [metrics]
        avg_cpu = sum(m.cpu_percent for m in recent) / len(recent)

        scale_up_thr = self.config.get("cpu_scale_up_threshold", 50)
        scale_down_thr = self.config.get("cpu_scale_down_threshold", 80)
        min_a = self.config.get("min_agents", 2)
        max_a = self.config.get("max_agents", 16)

        running = self._get_running_containers()
        stopped = self._get_stopped_containers()

        if avg_cpu < scale_up_thr and len(running) < max_a and len(stopped) > 0:
            inc = min(self.config.get("scale_up_increment", 1), len(stopped), max_a - len(running))
            if inc > 0:
                return ScalingDecision(
                    action=ScaleAction.SCALE_UP, current_agents=len(running),
                    target_agents=len(running) + inc,
                    reason=f"CPU subutilizada ({avg_cpu:.1f}% < {scale_up_thr}%) - reiniciando {inc} container(s)",
                    metrics=metrics, containers_to_start=[c["id"] for c in stopped[:inc]]
                )

        if avg_cpu > scale_down_thr and len(running) > min_a:
            dec = min(self.config.get("scale_down_increment", 1), len(running) - min_a)
            if dec > 0:
                idle = self._find_idle_containers(running, dec)
                if idle:
                    return ScalingDecision(
                        action=ScaleAction.SCALE_DOWN, current_agents=len(running),
                        target_agents=len(running) - len(idle),
                        reason=f"CPU sobrecarregada ({avg_cpu:.1f}% > {scale_down_thr}%) - parando {len(idle)} container(s)",
                        metrics=metrics, containers_to_stop=idle
                    )

        return ScalingDecision(
            action=ScaleAction.NONE, current_agents=len(running),
            target_agents=len(running), reason=f"CPU estavel ({avg_cpu:.1f}%)", metrics=metrics
        )

    async def _execute_scaling(self, decision: ScalingDecision):
        """Executa scaling com Docker REAL."""
        try:
            old_count = self.current_agents

            if decision.action == ScaleAction.SCALE_UP:
                ok_count = 0
                for cid in decision.containers_to_start:
                    ok, _, stderr = self._run_docker_cmd(["start", cid])
                    if ok:
                        ok_count += 1
                        logger.info(f"  Container iniciado: {cid}")
                    else:
                        logger.warning(f"  Falha ao iniciar {cid}: {stderr}")
                if ok_count > 0:
                    logger.info(f"Scale UP: {ok_count} containers iniciados")

            elif decision.action == ScaleAction.SCALE_DOWN:
                ok_count = 0
                for cid in decision.containers_to_stop:
                    ok, _, stderr = self._run_docker_cmd(["stop", cid])
                    if ok:
                        ok_count += 1
                        logger.info(f"  Container parado: {cid}")
                    else:
                        logger.warning(f"  Falha ao parar {cid}: {stderr}")
                if ok_count > 0:
                    logger.info(f"Scale DOWN: {ok_count} containers parados")

            self._sync_container_count()
            self.last_scale_time = time.time()
            self.last_scale_action = decision.action

            action_emoji = "UP" if decision.action == ScaleAction.SCALE_UP else "DOWN"
            logger.info(f"Auto-scaling {action_emoji}: {old_count} -> {self.current_agents} agents | {decision.reason}")

            await self._notify_scaling(decision)
        except Exception as e:
            logger.error(f"Erro ao executar scaling: {e}")

    async def _notify_scaling(self, decision: ScalingDecision):
        """Notifica bus sobre scaling."""
        try:
            from .agent_communication_bus import log_coordinator
            log_coordinator(
                f"Auto-scaling v2: {decision.current_agents} -> {decision.target_agents} agents. "
                f"Razao: {decision.reason}"
            )
        except ImportError:
            pass

    def get_status(self) -> Dict:
        """Retorna status do auto-scaler."""
        self._sync_container_count()
        running = self._get_running_containers()
        stopped = self._get_stopped_containers()
        recent = self.metrics_history[-1] if self.metrics_history else None

        return {
            "enabled": self.config.get("enabled", True),
            "running": self.running,
            "current_agents": self.current_agents,
            "real_running_containers": len(running),
            "stopped_containers": len(stopped),
            "container_names": [c["name"] for c in running],
            "min_agents": self.config.get("min_agents", 2),
            "max_agents": self.config.get("max_agents", 16),
            "last_scale_action": self.last_scale_action.value if self.last_scale_action else None,
            "last_scale_time": datetime.fromtimestamp(self.last_scale_time).isoformat() if self.last_scale_time else None,
            "current_metrics": {
                "cpu_percent": recent.cpu_percent if recent else 0,
                "memory_percent": recent.memory_percent if recent else 0,
                "disk_percent": recent.disk_percent if recent else 0,
            } if recent else None,
            "thresholds": {
                "scale_up_below_cpu": self.config.get("cpu_scale_up_threshold", 50),
                "scale_down_above_cpu": self.config.get("cpu_scale_down_threshold", 80),
            },
            "version": "v2_docker_real"
        }

    def get_recommended_parallelism(self) -> int:
        """Retorna numero recomendado de tarefas paralelas."""
        max_per = SYNERGY_CONFIG.get("max_parallel_tasks_per_agent", 3)
        return max(self.current_agents, 1) * max_per


# Singleton
_autoscaler_instance: Optional[AgentAutoScaler] = None


def get_autoscaler() -> AgentAutoScaler:
    """Retorna instancia singleton do auto-scaler."""
    global _autoscaler_instance
    if _autoscaler_instance is None:
        _autoscaler_instance = AgentAutoScaler()
    return _autoscaler_instance
