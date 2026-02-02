"""
Orquestrador Docker Avançado
Gerencia containers de desenvolvimento por linguagem
"""
import os
import json
import shutil
import subprocess
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

try:
    import psutil
except Exception:
    psutil = None

from .config import (
    LANGUAGE_DOCKER_TEMPLATES, 
    DATA_DIR, 
    PROJECTS_DIR,
    BACKUP_DIR,
    DOCKER_RESOURCE_CONFIG
)
from .agent_communication_bus import log_docker_operation
try:
    from .metrics_exporter import get_metrics_collector
    metrics_available = True
except Exception:
    metrics_available = False


@dataclass
class ContainerInfo:
    container_id: str
    name: str
    language: str
    status: str
    image: str
    ports: Dict[str, str] = field(default_factory=dict)
    volumes: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    project_path: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "container_id": self.container_id,
            "name": self.name,
            "language": self.language,
            "status": self.status,
            "image": self.image,
            "ports": self.ports,
            "volumes": self.volumes,
            "created_at": self.created_at.isoformat(),
            "project_path": self.project_path
        }


@dataclass
class RunResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    container_id: Optional[str] = None
    error: Optional[str] = None


class DockerOrchestrator:
    """
    Orquestra containers Docker para desenvolvimento.
    Cada projeto/linguagem tem seu próprio ambiente isolado.
    """
    
    def __init__(self):
        self.containers: Dict[str, ContainerInfo] = {}
        self.network_name = "specialized_agents_network"
        self.container_prefix = "spec_agent"
        self.timeout = 300
        self._port_counter = 8000
        self._ensure_network()
    
    def _run_docker_cmd(self, args: List[str], timeout: int = None) -> RunResult:
        """Executa comando Docker"""
        timeout = timeout or self.timeout
        try:
            result = subprocess.run(
                ["docker"] + args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return RunResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode
            )
        except subprocess.TimeoutExpired:
            return RunResult(success=False, error="Timeout excedido", exit_code=-1)
        except Exception as e:
            return RunResult(success=False, error=str(e), exit_code=-1)
    
    def is_available(self) -> bool:
        """Verifica se Docker está disponível"""
        result = self._run_docker_cmd(["info"], timeout=10)
        return result.success
    
    def _ensure_network(self):
        """Garante que a rede Docker existe"""
        result = self._run_docker_cmd(["network", "inspect", self.network_name])
        if not result.success:
            self._run_docker_cmd(["network", "create", self.network_name])
    
    def _get_next_port(self, language: str) -> int:
        """Retorna próxima porta disponível para a linguagem"""
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, {})
        port_range = config.get("port_range", (8000, 9000))
        
        # Encontrar porta não usada
        used_ports = set()
        for container in self.containers.values():
            for port in container.ports.values():
                try:
                    used_ports.add(int(port.split(":")[0]))
                except:
                    pass
        
        for port in range(port_range[0], port_range[1]):
            if port not in used_ports:
                return port
        
        return port_range[0]  # Fallback
    
    def generate_dockerfile(
        self,
        language: str,
        dependencies: List[str] = None,
        custom_commands: List[str] = None
    ) -> str:
        """Gera Dockerfile para a linguagem"""
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        
        base_image = config["base_image"]
        install_cmd = config["install_cmd"]
        extra = config.get("dockerfile_extra", "")
        
        deps = dependencies or config.get("default_packages", [])
        
        dockerfile = f"""FROM {base_image}

WORKDIR /app

{extra}

"""
        
        if deps:
            if language == "python":
                dockerfile += f"RUN {install_cmd} {' '.join(deps)}\n"
            elif language in ["javascript", "typescript"]:
                dockerfile += f"RUN npm init -y && npm install {' '.join(deps)}\n"
            elif language == "go":
                for dep in deps:
                    dockerfile += f"RUN go get {dep}\n"
            elif language == "rust":
                for dep in deps:
                    dockerfile += f"RUN cargo add {dep}\n"
            elif language == "php":
                dockerfile += f"RUN composer require {' '.join(deps)}\n"
        
        if custom_commands:
            for cmd in custom_commands:
                dockerfile += f"RUN {cmd}\n"
        
        dockerfile += """
COPY . .

CMD ["tail", "-f", "/dev/null"]
"""
        return dockerfile

    def _get_resource_flags(self) -> List[str]:
        """Calcula flags de recursos Docker com base na configuração elástica."""
        if not DOCKER_RESOURCE_CONFIG.get("enabled", True):
            return []
        if psutil is None:
            return []

        total_cpus = os.cpu_count() or 2
        total_mem_mb = int(psutil.virtual_memory().total / (1024 * 1024))

        if DOCKER_RESOURCE_CONFIG.get("elastic", True):
            cpu_limit = total_cpus * DOCKER_RESOURCE_CONFIG.get("cpu_fraction_per_container", 0.5)
            mem_limit_mb = total_mem_mb * DOCKER_RESOURCE_CONFIG.get("mem_fraction_per_container", 0.10)
            mem_reservation_mb = total_mem_mb * DOCKER_RESOURCE_CONFIG.get("mem_reservation_fraction", 0.05)
        else:
            cpu_limit = DOCKER_RESOURCE_CONFIG.get("cpu_max", 2.0)
            mem_limit_mb = DOCKER_RESOURCE_CONFIG.get("mem_max_mb", 4096)
            mem_reservation_mb = DOCKER_RESOURCE_CONFIG.get("mem_reservation_max_mb", 2048)

        cpu_limit = max(DOCKER_RESOURCE_CONFIG.get("cpu_min", 0.5), min(cpu_limit, DOCKER_RESOURCE_CONFIG.get("cpu_max", 2.0)))
        mem_limit_mb = int(max(DOCKER_RESOURCE_CONFIG.get("mem_min_mb", 512), min(mem_limit_mb, DOCKER_RESOURCE_CONFIG.get("mem_max_mb", 4096))))
        mem_reservation_mb = int(max(DOCKER_RESOURCE_CONFIG.get("mem_reservation_min_mb", 256), min(mem_reservation_mb, DOCKER_RESOURCE_CONFIG.get("mem_reservation_max_mb", 2048))))

        memory_swap_ratio = DOCKER_RESOURCE_CONFIG.get("memory_swap_ratio", 1.5)
        mem_swap_mb = int(max(mem_limit_mb, mem_limit_mb * memory_swap_ratio))

        flags = [
            "--cpus", f"{cpu_limit}",
            "--memory", f"{mem_limit_mb}m",
            "--memory-reservation", f"{mem_reservation_mb}m",
            "--memory-swap", f"{mem_swap_mb}m",
            "--cpu-shares", str(DOCKER_RESOURCE_CONFIG.get("cpu_shares", 512)),
            "--pids-limit", str(DOCKER_RESOURCE_CONFIG.get("pids_limit", 512))
        ]

        return flags
    
    async def create_project(
        self,
        language: str,
        code: str,
        dependencies: List[str] = None,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Cria novo projeto com container Docker"""
        project_name = project_name or f"{language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_path = PROJECTS_DIR / language / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        
        # Salvar código
        main_file = project_path / f"main{config['extension']}"
        main_file.write_text(code)
        
        # Gerar Dockerfile
        dockerfile = self.generate_dockerfile(language, dependencies)
        dockerfile_path = project_path / "Dockerfile"
        dockerfile_path.write_text(dockerfile)
        
        # Build image
        image_tag = f"{self.container_prefix}_{language}:{project_name}"
        build_result = self._run_docker_cmd([
            "build", "-t", image_tag, str(project_path)
        ])
        
        if not build_result.success:
            return {
                "success": False,
                "error": build_result.stderr,
                "project_path": str(project_path)
            }
        
        # Run container
        port = self._get_next_port(language)
        container_name = f"{self.container_prefix}_{language}_{project_name}"
        
        run_args = [
            "run", "-d",
            "--name", container_name,
            "--network", self.network_name,
            *self._get_resource_flags(),
            "-v", f"{project_path}:/app",
            "-p", f"{port}:{config.get('port_range', (8000,))[0]}",
            image_tag
        ]
        
        run_result = self._run_docker_cmd(run_args)
        
        if not run_result.success:
            return {
                "success": False,
                "error": run_result.stderr,
                "project_path": str(project_path)
            }
        
        container_id = run_result.stdout.strip()[:12]
        
        # Registrar container
        container_info = ContainerInfo(
            container_id=container_id,
            name=container_name,
            language=language,
            status="running",
            image=image_tag,
            ports={str(port): str(config.get('port_range', (8000,))[0])},
            volumes={str(project_path): "/app"},
            project_path=str(project_path)
        )
        self.containers[container_id] = container_info
        
        # Registrar alocação de recursos nas métricas
        if metrics_available:
            try:
                cpu_limit = DOCKER_RESOURCE_CONFIG.get("cpu_fraction_per_container", 0.5)
                mem_limit = DOCKER_RESOURCE_CONFIG.get("memory_limit_mb", 512)
                metrics = get_metrics_collector()
                metrics.record_docker_resource_allocation(
                    container_id=container_id,
                    cpu_limit=cpu_limit,
                    memory_limit_mb=mem_limit
                )
            except Exception as e:
                log_docker_operation("warning", "metrics_registration_failed", str(e))
        
        return {
            "success": True,
            "container_id": container_id,
            "container_name": container_name,
            "project_path": str(project_path),
            "port": port,
            "image": image_tag
        }
    
    async def run_code(
        self,
        container_id: str,
        code: str = None,
        filename: str = None,
        language: str = "python"
    ) -> RunResult:
        """Executa código em um container"""
        container = self.containers.get(container_id)
        if not container:
            return RunResult(success=False, error=f"Container {container_id} não encontrado")
        
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        run_cmd = config.get("run_cmd", "python")
        
        # Se código fornecido, atualizar arquivo
        if code:
            project_path = Path(container.project_path)
            main_file = project_path / f"main{config['extension']}"
            main_file.write_text(code)
        
        filename = filename or f"main{config['extension']}"
        
        # Executar
        result = self._run_docker_cmd([
            "exec", container_id,
            *run_cmd.split(), filename
        ], timeout=60)
        
        result.container_id = container_id
        return result
    
    async def run_tests(
        self,
        container_id: str,
        code: str = None,
        test_code: str = None,
        language: str = "python"
    ) -> Dict[str, Any]:
        """Executa testes em um container"""
        container = self.containers.get(container_id)
        if not container:
            return {"success": False, "error": f"Container {container_id} não encontrado"}
        
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        project_path = Path(container.project_path)
        
        # Atualizar código se fornecido
        if code:
            main_file = project_path / f"main{config['extension']}"
            main_file.write_text(code)
        
        if test_code:
            if language == "python":
                test_file = project_path / "test_main.py"
            elif language in ["javascript", "typescript"]:
                test_file = project_path / "main.test.js"
            elif language == "go":
                test_file = project_path / "main_test.go"
            else:
                test_file = project_path / f"test_main{config['extension']}"
            test_file.write_text(test_code)
        
        # Executar testes
        test_cmd = config.get("test_cmd", "pytest")
        
        result = self._run_docker_cmd([
            "exec", container_id,
            *test_cmd.split()
        ], timeout=120)
        
        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": result.stderr if not result.success else None,
            "exit_code": result.exit_code
        }
    
    async def update_code(
        self,
        container_id: str,
        code: str,
        filename: str = None
    ) -> bool:
        """Atualiza código em um container"""
        container = self.containers.get(container_id)
        if not container:
            return False
        
        config = LANGUAGE_DOCKER_TEMPLATES.get(container.language, {})
        project_path = Path(container.project_path)
        
        filename = filename or f"main{config.get('extension', '.py')}"
        file_path = project_path / filename
        file_path.write_text(code)
        
        return True
    
    async def exec_command(
        self,
        container_id: str,
        command: str,
        timeout: int = 60
    ) -> RunResult:
        """Executa comando arbitrário em um container"""
        container = self.containers.get(container_id)
        if not container:
            return RunResult(success=False, error=f"Container {container_id} não encontrado")
        
        result = self._run_docker_cmd([
            "exec", container_id,
            "sh", "-c", command
        ], timeout=timeout)
        
        result.container_id = container_id
        return result
    
    async def install_packages(
        self,
        container_id: str,
        packages: List[str],
        language: str = None
    ) -> RunResult:
        """Instala pacotes em um container"""
        container = self.containers.get(container_id)
        if not container:
            return RunResult(success=False, error=f"Container {container_id} não encontrado")
        
        language = language or container.language
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, {})
        install_cmd = config.get("install_cmd", "pip install")
        
        result = self._run_docker_cmd([
            "exec", container_id,
            "sh", "-c", f"{install_cmd} {' '.join(packages)}"
        ], timeout=300)
        
        return result
    
    async def get_logs(self, container_id: str, lines: int = 100) -> str:
        """Obtém logs de um container"""
        result = self._run_docker_cmd([
            "logs", "--tail", str(lines), container_id
        ])
        return result.stdout + result.stderr
    
    async def stop_container(self, container_id: str) -> bool:
        """Para um container"""
        result = self._run_docker_cmd(["stop", container_id])
        if result.success and container_id in self.containers:
            self.containers[container_id].status = "stopped"
        return result.success
    
    async def start_container(self, container_id: str) -> bool:
        """Inicia um container"""
        result = self._run_docker_cmd(["start", container_id])
        if result.success and container_id in self.containers:
            self.containers[container_id].status = "running"
        return result.success
    
    async def remove_container(
        self,
        container_id: str,
        remove_project: bool = False,
        backup: bool = True
    ) -> bool:
        """Remove um container"""
        container = self.containers.get(container_id)
        
        # Parar se rodando
        self._run_docker_cmd(["stop", container_id])
        
        # Backup do projeto
        if container and backup and container.project_path:
            await self._backup_project(container)
        
        # Remover container
        result = self._run_docker_cmd(["rm", "-f", container_id])
        
        # Remover imagem
        if container:
            self._run_docker_cmd(["rmi", "-f", container.image])
            
            # Remover projeto
            if remove_project and container.project_path:
                project_path = Path(container.project_path)
                if project_path.exists():
                    shutil.rmtree(project_path)
        
        # Desregistrar
        if container_id in self.containers:
            del self.containers[container_id]
        
        return result.success
    
    async def _backup_project(self, container: ContainerInfo) -> Optional[str]:
        """Faz backup de um projeto antes de remover"""
        if not container.project_path:
            return None
        
        project_path = Path(container.project_path)
        if not project_path.exists():
            return None
        
        backup_name = f"{container.language}_{container.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = BACKUP_DIR / backup_name
        
        try:
            shutil.copytree(project_path, backup_path)
            
            # Salvar metadados
            metadata = {
                "container": container.to_dict(),
                "backup_date": datetime.now().isoformat(),
                "original_path": str(project_path)
            }
            (backup_path / "_backup_metadata.json").write_text(
                json.dumps(metadata, indent=2)
            )
            
            return str(backup_path)
        except Exception as e:
            print(f"[Docker] Erro no backup: {e}")
            return None
    
    async def cleanup_old_containers(self, max_age_hours: int = 24) -> List[str]:
        """Remove containers antigos"""
        removed = []
        now = datetime.now()
        
        for container_id, container in list(self.containers.items()):
            age = (now - container.created_at).total_seconds() / 3600
            if age > max_age_hours and container.status == "stopped":
                await self.remove_container(container_id, backup=True)
                removed.append(container_id)
        
        return removed
    
    def list_containers(self, language: str = None) -> List[Dict]:
        """Lista containers"""
        containers = self.containers.values()
        if language:
            containers = [c for c in containers if c.language == language]
        return [c.to_dict() for c in containers]
    
    def get_container_info(self, container_id: str) -> Optional[Dict]:
        """Obtém info de um container"""
        container = self.containers.get(container_id)
        return container.to_dict() if container else None
    
    async def export_project(
        self,
        container_id: str,
        output_path: Path = None
    ) -> Optional[str]:
        """Exporta projeto como ZIP"""
        container = self.containers.get(container_id)
        if not container or not container.project_path:
            return None
        
        project_path = Path(container.project_path)
        if not project_path.exists():
            return None
        
        output_path = output_path or (DATA_DIR / f"export_{container.name}.zip")
        
        try:
            shutil.make_archive(
                str(output_path).replace('.zip', ''),
                'zip',
                project_path
            )
            return str(output_path)
        except Exception as e:
            print(f"[Docker] Erro ao exportar: {e}")
            return None
    
    async def import_project(
        self,
        zip_path: Path,
        language: str,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Importa projeto de ZIP"""
        project_name = project_name or f"imported_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_path = PROJECTS_DIR / language / project_name
        
        try:
            shutil.unpack_archive(zip_path, project_path)
            
            # Ler código principal
            config = LANGUAGE_DOCKER_TEMPLATES.get(language, {})
            main_file = project_path / f"main{config.get('extension', '.py')}"
            
            code = ""
            if main_file.exists():
                code = main_file.read_text()
            
            # Ler dependências
            deps = []
            if language == "python":
                req_file = project_path / "requirements.txt"
                if req_file.exists():
                    deps = [l.strip() for l in req_file.read_text().splitlines() if l.strip()]
            elif language in ["javascript", "typescript"]:
                pkg_file = project_path / "package.json"
                if pkg_file.exists():
                    pkg = json.loads(pkg_file.read_text())
                    deps = list(pkg.get("dependencies", {}).keys())
            
            # Criar container
            return await self.create_project(language, code, deps, project_name)
        except Exception as e:
            return {"success": False, "error": str(e)}
