"""
Orquestrador remoto via SSH para executar containers em um host remoto (ex: homelab)

Implementação mínima compatível com DockerOrchestrator usada pelo AgentManager.
"""
import os
import json
import tempfile
import shutil
import stat
from pathlib import Path
from typing import Dict, Any, Optional, List

import paramiko

from .config import DATA_DIR, PROJECTS_DIR, LANGUAGE_DOCKER_TEMPLATES
from .docker_orchestrator import RunResult


class RemoteOrchestrator:
    """Orquestrador simples que executa comandos Docker via SSH em host remoto."""

    def __init__(self, host: str, user: str = "root", ssh_key: str = None, base_dir: str = "~/agent_projects"):
        self.host = host
        self.user = user
        self.ssh_key = os.path.expanduser(ssh_key) if ssh_key else None
        self.base_dir = base_dir
        self.containers: Dict[str, Dict] = {}

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.ssh_key and Path(self.ssh_key).exists():
            pkey = None
            try:
                pkey = paramiko.RSAKey.from_private_key_file(self.ssh_key)
            except Exception:
                pkey = None

            client.connect(self.host, username=self.user, pkey=pkey, timeout=10)
        else:
            client.connect(self.host, username=self.user, timeout=10)
        return client

    def is_available(self) -> bool:
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command("docker info")
            out = stdout.read().decode()
            err = stderr.read().decode()
            client.close()
            return "Server Version" in out
        except Exception:
            return False

    def _exec(self, cmd: str, timeout: int = 60) -> RunResult:
        try:
            client = self._connect()
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
            out = stdout.read().decode()
            err = stderr.read().decode()
            exit_code = stdout.channel.recv_exit_status()
            client.close()
            return RunResult(success=exit_code == 0, stdout=out, stderr=err, exit_code=exit_code)
        except Exception as e:
            return RunResult(success=False, error=str(e), exit_code=-1)

    def _sftp_put_dir(self, local_dir: Path, remote_dir: str) -> bool:
        try:
            client = self._connect()
            sftp = client.open_sftp()
            try:
                # Ensure remote dir exists
                try:
                    sftp.stat(remote_dir)
                except IOError:
                    sftp.mkdir(remote_dir)

                for root, dirs, files in os.walk(local_dir):
                    rel = os.path.relpath(root, local_dir)
                    if rel == ".":
                        rroot = remote_dir
                    else:
                        rroot = os.path.join(remote_dir, rel)
                        try:
                            sftp.stat(rroot)
                        except IOError:
                            sftp.mkdir(rroot)

                    for f in files:
                        lpath = os.path.join(root, f)
                        rpath = os.path.join(rroot, f)
                        sftp.put(lpath, rpath)
            finally:
                sftp.close()
                client.close()
            return True
        except Exception as e:
            print(f"[RemoteOrchestrator] SFTP error: {e}")
            return False

    async def create_project(self, language: str, code: str, dependencies: List[str] = None, project_name: str = None) -> Dict[str, Any]:
        project_name = project_name or f"{language}_{os.urandom(4).hex()}"
        local_tmp = Path(tempfile.mkdtemp())
        try:
            config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
            main_file = local_tmp / f"main{config['extension']}"
            main_file.write_text(code)

            # Write requirements/package.json if dependencies provided
            if dependencies:
                if language == "python":
                    (local_tmp / "requirements.txt").write_text("\n".join(dependencies))
                elif language in ["javascript", "typescript"]:
                    pkg = {"name": project_name, "version": "0.0.1", "dependencies": {d: "*" for d in dependencies}}
                    (local_tmp / "package.json").write_text(json.dumps(pkg))

            remote_dir = os.path.join(self.base_dir, language, project_name)
            # Copy files
            ok = self._sftp_put_dir(local_tmp, remote_dir)
            if not ok:
                return {"success": False, "error": "SFTP upload failed"}

            # Create Dockerfile remotely
            dockerfile = self._generate_dockerfile(language, dependencies)
            # write dockerfile via echo
            df_escaped = dockerfile.replace('"', '\"')
            cmd = f"mkdir -p {remote_dir} && cat > {remote_dir}/Dockerfile <<'DF'\n{dockerfile}\nDF\n"
            build = self._exec(f"cd {remote_dir} && docker build -t remote_{language}_{project_name} .", timeout=600)
            if not build.success:
                return {"success": False, "error": build.stderr}

            # Run container
            port = config.get("port_range", (8000, 8000))[0]
            run_cmd = f"docker run -d --name remote_{language}_{project_name} -v {remote_dir}:/app remote_{language}_{project_name}"
            run = self._exec(run_cmd)
            if not run.success:
                return {"success": False, "error": run.stderr}

            container_id = run.stdout.strip()[:12]
            info = {
                "container_id": container_id,
                "container_name": f"remote_{language}_{project_name}",
                "project_path": remote_dir,
                "image": f"remote_{language}_{project_name}"
            }
            self.containers[container_id] = info
            return {"success": True, **info}
        finally:
            shutil.rmtree(local_tmp)

    def _generate_dockerfile(self, language: str, dependencies: List[str] = None) -> str:
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        base_image = config["base_image"]
        install_cmd = config["install_cmd"]
        extra = config.get("dockerfile_extra", "")
        deps = dependencies or config.get("default_packages", [])
        dockerfile = f"FROM {base_image}\nWORKDIR /app\n{extra}\n"
        if deps:
            if language == "python":
                dockerfile += f"RUN {install_cmd} {' '.join(deps)}\n"
            elif language in ["javascript", "typescript"]:
                dockerfile += f"RUN npm init -y && npm install {' '.join(deps)}\n"
        dockerfile += "COPY . .\nCMD [\"tail\", \"-f\", \"/dev/null\"]\n"
        return dockerfile

    async def run_code(self, container_id: str, code: str = None, filename: str = None, language: str = "python") -> RunResult:
        info = self.containers.get(container_id)
        if not info:
            return RunResult(success=False, error="container not found")
        remote_path = info.get("project_path")
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        filename = filename or f"main{config['extension']}"

        # Write file via ssh
        tmp = tempfile.NamedTemporaryFile(delete=False)
        try:
            tmp.write(code.encode('utf-8'))
            tmp.flush()
            tmp.close()
            # upload
            client = self._connect()
            sftp = client.open_sftp()
            sftp.put(tmp.name, os.path.join(remote_path, filename))
            sftp.close()
            client.close()

            run_cmd = f"docker exec {info['container_name']} {config.get('run_cmd','python')} {filename}"
            return self._exec(run_cmd, timeout=60)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    async def run_tests(self, container_id: str, code: str = None, test_code: str = None, language: str = "python") -> Dict[str, Any]:
        info = self.containers.get(container_id)
        if not info:
            return {"success": False, "error": "container not found"}

        remote_path = info.get("project_path")
        config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        if test_code:
            tmp = tempfile.NamedTemporaryFile(delete=False)
            try:
                tmp.write(test_code.encode('utf-8'))
                tmp.flush()
                tmp.close()
                client = self._connect()
                sftp = client.open_sftp()
                sftp.put(tmp.name, os.path.join(remote_path, "test_main.py"))
                sftp.close()
                client.close()
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

        test_cmd = config.get("test_cmd", "pytest")
        result = self._exec(f"docker exec {info['container_name']} {test_cmd}", timeout=120)
        return {"success": result.success, "stdout": result.stdout, "stderr": result.stderr, "error": result.stderr if not result.success else None}

    async def import_project(self, zip_path: Path, language: str, project_name: str = None) -> Dict[str, Any]:
        # Upload zip and unzip remotely then call create_project
        project_name = project_name or f"imported_{os.urandom(4).hex()}"
        remote_dir = os.path.join(self.base_dir, language, project_name)
        client = self._connect()
        sftp = client.open_sftp()
        try:
            sftp.put(str(zip_path), os.path.join(remote_dir, "project.zip"))
            client.exec_command(f"mkdir -p {remote_dir} && cd {remote_dir} && unzip project.zip && rm project.zip")
        finally:
            sftp.close()
            client.close()

        return await self.create_project(language, "", [], project_name)
