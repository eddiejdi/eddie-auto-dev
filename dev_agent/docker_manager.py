"""
Gerenciador de containers Docker para desenvolvimento
"""
import os
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from pathlib import Path

from .config import DOCKER_CONFIG, DOCKER_TEMPLATES


@dataclass
class RunResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    container_id: Optional[str] = None


class DockerManager:
    def __init__(self, base_image: str = None, workdir: str = None):
        self.base_image = base_image or DOCKER_TEMPLATES["python"]["base_image"]
        self.workdir = workdir or "/app"
        self.container_prefix = "dev_agent"
        self.timeout = DOCKER_CONFIG.get("default_timeout", 300)
        self._containers: List[str] = []
    
    def is_docker_available(self) -> bool:
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def generate_dockerfile(self, language: str, dependencies: List[str] = None) -> str:
        template = DOCKER_TEMPLATES.get(language, DOCKER_TEMPLATES["python"])
        base_image = template.get("base_image", "python:3.11-slim")
        install_cmd = template.get("install_cmd", "pip install")
        deps = dependencies or []
        deps_str = " ".join(deps) if deps else ""
        
        dockerfile = f"""FROM {base_image}
WORKDIR /app
RUN {install_cmd} {deps_str} pytest
COPY . .
"""
        return dockerfile
    
    def build_image(self, dockerfile_content: str, tag: str = None) -> RunResult:
        tag = tag or f"{self.container_prefix}:latest"
        with tempfile.TemporaryDirectory() as tmpdir:
            dockerfile_path = Path(tmpdir) / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content)
            
            cmd = ["docker", "build", "-t", tag, tmpdir]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            return RunResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode
            )
    
    def run_code(self, code: str, language: str = "python", timeout: int = None) -> RunResult:
        timeout = timeout or self.timeout
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = {"python": ".py", "javascript": ".js", "sql": ".sql"}.get(language, ".py")
            filename = f"main{ext}"
            code_path = Path(tmpdir) / filename
            code_path.write_text(code)
            
            uid = f"{os.getuid()}:{os.getgid()}"
            cmd_map = {
                "python": ["docker", "run", "--rm", "-v", f"{tmpdir}:/app", "-w", "/app", "--user", uid, self.base_image, "python", filename],
                "javascript": ["docker", "run", "--rm", "-v", f"{tmpdir}:/app", "-w", "/app", "--user", uid, "node:18-alpine", "node", filename],
            }
            
            cmd = cmd_map.get(language, cmd_map["python"])
            
            try:
                # Use Popen + communicate with timeout in a thread-safe way to avoid blocking
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    stdout, stderr = proc.communicate(timeout=timeout)
                    return RunResult(success=proc.returncode == 0, stdout=stdout, stderr=stderr, exit_code=proc.returncode)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    stdout, stderr = proc.communicate()
                    return RunResult(success=False, stdout=stdout or "", stderr=(stderr or "") + "\nTimeout excedido", exit_code=-1)
            except Exception as e:
                return RunResult(success=False, stdout="", stderr=str(e), exit_code=-1)
    
    def run_tests(self, code: str, test_code: str, language: str = "python") -> RunResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            code_path = Path(tmpdir) / "main.py"
            test_path = Path(tmpdir) / "test_main.py"
            code_path.write_text(code)
            test_code_with_import = f"import sys\nsys.path.insert(0, '/app')\n{test_code}"
            test_path.write_text(test_code_with_import)
            # Tentar executar testes dentro do container; instalar pytest na linha de comando
            uid = f"{os.getuid()}:{os.getgid()}"
            cmd = [
                "docker", "run", "--rm", "-v", f"{tmpdir}:/app", "-w", "/app", "--user", uid,
                self.base_image,
                "bash", "-c",
                "python -m pip install --no-cache-dir pytest >/dev/null 2>&1 || true && python -m pytest -v test_main.py"
            ]
            
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    stdout, stderr = proc.communicate(timeout=self.timeout)
                    return RunResult(success=proc.returncode == 0, stdout=stdout, stderr=stderr, exit_code=proc.returncode)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    stdout, stderr = proc.communicate()
                    return RunResult(success=False, stdout=stdout or "", stderr=(stderr or "") + "\nTimeout", exit_code=-1)
            except Exception as e:
                return RunResult(success=False, stdout="", stderr=str(e), exit_code=-1)
    
    def create_dev_container(self, project_name: str, language: str = "python", ports: List[int] = None, volumes: Dict[str, str] = None) -> RunResult:
        container_name = f"{self.container_prefix}-{project_name}"
        ports = ports or []
        volumes = volumes or {}
        
        cmd = ["docker", "run", "-d", "--name", container_name]
        
        for host_port in ports:
            cmd.extend(["-p", f"{host_port}:{host_port}"])
        
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])
        
        cmd.append(self.base_image)
        cmd.extend(["tail", "-f", "/dev/null"])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self._containers.append(container_name)
            return RunResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                container_id=result.stdout.strip() if result.returncode == 0 else None
            )
        except Exception as e:
            return RunResult(success=False, stdout="", stderr=str(e), exit_code=-1)
    
    def exec_in_container(self, container_name: str, command: str) -> RunResult:
        cmd = ["docker", "exec", container_name, "bash", "-c", command]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            return RunResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode
            )
        except Exception as e:
            return RunResult(success=False, stdout="", stderr=str(e), exit_code=-1)
    
    def stop_container(self, container_name: str) -> bool:
        try:
            subprocess.run(["docker", "stop", container_name], capture_output=True, timeout=30)
            subprocess.run(["docker", "rm", container_name], capture_output=True, timeout=30)
            if container_name in self._containers:
                self._containers.remove(container_name)
            return True
        except:
            return False
    
    def cleanup_all(self):
        for container in self._containers.copy():
            self.stop_container(container)
