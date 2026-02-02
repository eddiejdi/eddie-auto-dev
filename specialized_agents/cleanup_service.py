"""
Serviço de Limpeza Automática
Backup por 3 dias e exclusão automática de arquivos/containers não utilizados
"""

import json
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import logging

from .config import BACKUP_DIR, DATA_DIR, PROJECTS_DIR, CLEANUP_CONFIG, RAG_DIR

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup_service")


@dataclass
class CleanupItem:
    path: str
    item_type: str  # file, directory, container, image
    size_bytes: int
    created_at: datetime
    last_accessed: datetime
    language: Optional[str] = None
    marked_for_deletion: bool = False
    backup_path: Optional[str] = None


@dataclass
class CleanupReport:
    timestamp: datetime
    items_backed_up: List[str] = field(default_factory=list)
    items_deleted: List[str] = field(default_factory=list)
    space_freed_mb: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "items_backed_up": self.items_backed_up,
            "items_deleted": self.items_deleted,
            "space_freed_mb": self.space_freed_mb,
            "errors": self.errors,
        }


class CleanupService:
    """
    Serviço de limpeza automática com política de retenção.
    - Backup automático antes de deletar
    - Retenção de 3 dias para backups
    - Limpeza de containers Docker não utilizados
    - Limpeza de imagens órfãs
    """

    def __init__(self, docker_orchestrator=None):
        self.docker = docker_orchestrator
        self.backup_retention_days = CLEANUP_CONFIG.get("backup_retention_days", 3)
        self.cleanup_interval_hours = CLEANUP_CONFIG.get("cleanup_interval_hours", 24)
        self.max_backup_size_gb = CLEANUP_CONFIG.get("max_backup_size_gb", 10)
        self.auto_cleanup_enabled = CLEANUP_CONFIG.get("auto_cleanup_enabled", True)

        # Diretórios de backup organizados por tipo
        self.backup_dirs = {
            "projects": BACKUP_DIR / "projects",
            "containers": BACKUP_DIR / "containers",
            "files": BACKUP_DIR / "files",
            "rag": BACKUP_DIR / "rag",
        }

        # Criar diretórios
        for dir_path in self.backup_dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

        # Arquivo de tracking
        self.tracking_file = DATA_DIR / "cleanup_tracking.json"
        self.cleanup_history: List[Dict] = self._load_history()

        # Task de cleanup periódico
        self._cleanup_task = None

    def _load_history(self) -> List[Dict]:
        """Carrega histórico de limpezas"""
        if self.tracking_file.exists():
            try:
                return json.loads(self.tracking_file.read_text())
            except:
                pass
        return []

    def _save_history(self):
        """Salva histórico de limpezas"""
        # Manter apenas últimos 100 registros
        self.cleanup_history = self.cleanup_history[-100:]
        self.tracking_file.write_text(json.dumps(self.cleanup_history, indent=2))

    def _get_dir_size(self, path: Path) -> int:
        """Calcula tamanho de diretório"""
        total = 0
        if path.exists():
            for f in path.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except:
                        pass
        return total

    async def backup_item(
        self, source_path: str, item_type: str = "files", metadata: Dict = None
    ) -> Optional[str]:
        """Faz backup de um item"""
        source = Path(source_path)
        if not source.exists():
            return None

        # Nome do backup com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.name}_{timestamp}"
        backup_dir = self.backup_dirs.get(item_type, self.backup_dirs["files"])
        backup_path = backup_dir / backup_name

        try:
            if source.is_dir():
                shutil.copytree(source, backup_path)
            else:
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, backup_path)

            # Salvar metadados
            meta_path = backup_path.parent / f"{backup_name}_metadata.json"
            meta_data = {
                "original_path": str(source),
                "backup_date": datetime.now().isoformat(),
                "item_type": item_type,
                "retention_until": (
                    datetime.now() + timedelta(days=self.backup_retention_days)
                ).isoformat(),
                **(metadata or {}),
            }
            meta_path.write_text(json.dumps(meta_data, indent=2))

            logger.info(f"Backup criado: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Erro no backup de {source_path}: {e}")
            return None

    async def restore_backup(self, backup_path: str, destination: str = None) -> bool:
        """Restaura um backup"""
        backup = Path(backup_path)
        if not backup.exists():
            return False

        # Carregar metadados
        meta_path = backup.parent / f"{backup.name}_metadata.json"
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())
            destination = destination or metadata.get("original_path")

        if not destination:
            return False

        dest = Path(destination)

        try:
            # Remover destino existente
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()

            # Restaurar
            if backup.is_dir():
                shutil.copytree(backup, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, dest)

            logger.info(f"Backup restaurado: {backup} -> {dest}")
            return True

        except Exception as e:
            logger.error(f"Erro ao restaurar backup: {e}")
            return False

    async def cleanup_old_backups(self) -> CleanupReport:
        """Remove backups mais antigos que o período de retenção"""
        report = CleanupReport(timestamp=datetime.now())
        cutoff_date = datetime.now() - timedelta(days=self.backup_retention_days)

        for backup_type, backup_dir in self.backup_dirs.items():
            if not backup_dir.exists():
                continue

            for item in backup_dir.iterdir():
                # Pular metadados
                if item.name.endswith("_metadata.json"):
                    continue

                # Verificar metadados
                meta_path = backup_dir / f"{item.name}_metadata.json"
                should_delete = False

                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                        retention_until = datetime.fromisoformat(
                            meta.get("retention_until", "")
                        )
                        if datetime.now() > retention_until:
                            should_delete = True
                    except:
                        # Se não conseguir ler metadados, usar data de modificação
                        try:
                            mtime = datetime.fromtimestamp(item.stat().st_mtime)
                            if mtime < cutoff_date:
                                should_delete = True
                        except:
                            pass
                else:
                    # Sem metadados, usar data de modificação
                    try:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime < cutoff_date:
                            should_delete = True
                    except:
                        pass

                if should_delete:
                    try:
                        size = (
                            self._get_dir_size(item)
                            if item.is_dir()
                            else item.stat().st_size
                        )

                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()

                        if meta_path.exists():
                            meta_path.unlink()

                        report.items_deleted.append(str(item))
                        report.space_freed_mb += size / (1024 * 1024)
                        logger.info(f"Backup antigo removido: {item}")

                    except Exception as e:
                        report.errors.append(f"Erro ao remover {item}: {e}")

        return report

    async def cleanup_unused_projects(self, days_inactive: int = 7) -> CleanupReport:
        """Remove projetos inativos (com backup)"""
        report = CleanupReport(timestamp=datetime.now())
        cutoff_date = datetime.now() - timedelta(days=days_inactive)

        for lang_dir in PROJECTS_DIR.iterdir():
            if not lang_dir.is_dir():
                continue

            for project in lang_dir.iterdir():
                if not project.is_dir():
                    continue

                try:
                    # Verificar última modificação
                    latest_mtime = max(
                        f.stat().st_mtime for f in project.rglob("*") if f.is_file()
                    )
                    last_modified = datetime.fromtimestamp(latest_mtime)

                    if last_modified < cutoff_date:
                        # Fazer backup
                        backup_path = await self.backup_item(
                            str(project),
                            "projects",
                            {"language": lang_dir.name, "project": project.name},
                        )

                        if backup_path:
                            report.items_backed_up.append(backup_path)

                            # Remover
                            size = self._get_dir_size(project)
                            shutil.rmtree(project)

                            report.items_deleted.append(str(project))
                            report.space_freed_mb += size / (1024 * 1024)
                            logger.info(f"Projeto inativo removido: {project}")

                except Exception as e:
                    report.errors.append(f"Erro ao processar {project}: {e}")

        return report

    async def cleanup_docker_containers(self) -> CleanupReport:
        """Remove containers Docker não utilizados"""
        report = CleanupReport(timestamp=datetime.now())

        if not self.docker:
            return report

        try:
            import subprocess

            # Listar containers parados há mais de 24h
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    "status=exited",
                    "--format",
                    "{{.ID}}\t{{.Names}}\t{{.CreatedAt}}",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return report

            cutoff = datetime.now() - timedelta(hours=24)

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) < 3:
                    continue

                container_id = parts[0]
                container_name = parts[1]

                # Apenas containers dos agentes
                if not container_name.startswith("spec_agent"):
                    continue

                try:
                    # Backup dos logs
                    logs = subprocess.run(
                        ["docker", "logs", container_id],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if logs.stdout or logs.stderr:
                        log_backup = (
                            self.backup_dirs["containers"]
                            / f"{container_name}_logs.txt"
                        )
                        log_backup.write_text(logs.stdout + "\n" + logs.stderr)
                        report.items_backed_up.append(str(log_backup))

                    # Remover container
                    subprocess.run(
                        ["docker", "rm", "-f", container_id],
                        capture_output=True,
                        timeout=30,
                    )

                    report.items_deleted.append(f"container:{container_name}")
                    logger.info(f"Container removido: {container_name}")

                except Exception as e:
                    report.errors.append(
                        f"Erro ao remover container {container_name}: {e}"
                    )

        except Exception as e:
            report.errors.append(f"Erro geral cleanup Docker: {e}")

        return report

    async def cleanup_docker_images(self) -> CleanupReport:
        """Remove imagens Docker não utilizadas"""
        report = CleanupReport(timestamp=datetime.now())

        try:
            import subprocess

            # Remover imagens dangling
            result = subprocess.run(
                ["docker", "image", "prune", "-f"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if "Total reclaimed space" in result.stdout:
                report.items_deleted.append("docker:dangling_images")
                logger.info("Imagens Docker dangling removidas")

            # Remover imagens dos agentes não utilizadas
            result = subprocess.run(
                [
                    "docker",
                    "images",
                    "--format",
                    "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}",
                ],
                capture_output=True,
                text=True,
            )

            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) < 2:
                    continue

                image_name = parts[0]
                image_id = parts[1]

                # Apenas imagens dos agentes
                if not image_name.startswith("spec_agent"):
                    continue

                # Verificar se está em uso
                check = subprocess.run(
                    ["docker", "ps", "-a", "-q", "--filter", f"ancestor={image_id}"],
                    capture_output=True,
                    text=True,
                )

                if not check.stdout.strip():
                    # Não está em uso, remover
                    try:
                        subprocess.run(
                            ["docker", "rmi", "-f", image_id],
                            capture_output=True,
                            timeout=60,
                        )
                        report.items_deleted.append(f"image:{image_name}")
                        logger.info(f"Imagem removida: {image_name}")
                    except:
                        pass

        except Exception as e:
            report.errors.append(f"Erro cleanup imagens: {e}")

        return report

    async def cleanup_temp_files(self) -> CleanupReport:
        """Remove arquivos temporários"""
        report = CleanupReport(timestamp=datetime.now())

        temp_patterns = [
            "*.tmp",
            "*.temp",
            "*.pyc",
            "__pycache__",
            "*.log",
            "node_modules",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ]

        search_dirs = [DATA_DIR, PROJECTS_DIR]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for pattern in temp_patterns:
                for item in search_dir.rglob(pattern):
                    try:
                        size = (
                            self._get_dir_size(item)
                            if item.is_dir()
                            else item.stat().st_size
                        )

                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()

                        report.items_deleted.append(str(item))
                        report.space_freed_mb += size / (1024 * 1024)
                    except:
                        pass

        return report

    async def run_full_cleanup(self) -> CleanupReport:
        """Executa limpeza completa"""
        combined_report = CleanupReport(timestamp=datetime.now())

        # 1. Limpar backups antigos
        backup_report = await self.cleanup_old_backups()
        combined_report.items_deleted.extend(backup_report.items_deleted)
        combined_report.space_freed_mb += backup_report.space_freed_mb
        combined_report.errors.extend(backup_report.errors)

        # 2. Limpar projetos inativos (backup + delete)
        projects_report = await self.cleanup_unused_projects(days_inactive=7)
        combined_report.items_backed_up.extend(projects_report.items_backed_up)
        combined_report.items_deleted.extend(projects_report.items_deleted)
        combined_report.space_freed_mb += projects_report.space_freed_mb
        combined_report.errors.extend(projects_report.errors)

        # 3. Limpar containers Docker
        docker_report = await self.cleanup_docker_containers()
        combined_report.items_backed_up.extend(docker_report.items_backed_up)
        combined_report.items_deleted.extend(docker_report.items_deleted)
        combined_report.errors.extend(docker_report.errors)

        # 4. Limpar imagens Docker
        images_report = await self.cleanup_docker_images()
        combined_report.items_deleted.extend(images_report.items_deleted)
        combined_report.errors.extend(images_report.errors)

        # 5. Limpar arquivos temporários
        temp_report = await self.cleanup_temp_files()
        combined_report.items_deleted.extend(temp_report.items_deleted)
        combined_report.space_freed_mb += temp_report.space_freed_mb

        # Salvar no histórico
        self.cleanup_history.append(combined_report.to_dict())
        self._save_history()

        logger.info(
            f"Cleanup completo. Espaço liberado: {combined_report.space_freed_mb:.2f} MB"
        )

        return combined_report

    async def get_storage_status(self) -> Dict[str, Any]:
        """Retorna status de armazenamento"""

        def dir_info(path: Path) -> Dict:
            if not path.exists():
                return {"exists": False, "size_mb": 0}
            size = self._get_dir_size(path)
            return {
                "exists": True,
                "size_mb": size / (1024 * 1024),
                "file_count": sum(1 for _ in path.rglob("*") if _.is_file()),
            }

        return {
            "projects": dir_info(PROJECTS_DIR),
            "backups": dir_info(BACKUP_DIR),
            "data": dir_info(DATA_DIR),
            "rag": dir_info(RAG_DIR),
            "cleanup_config": {
                "retention_days": self.backup_retention_days,
                "auto_cleanup": self.auto_cleanup_enabled,
            },
            "last_cleanup": self.cleanup_history[-1] if self.cleanup_history else None,
        }

    async def start_periodic_cleanup(self):
        """Inicia cleanup periódico"""
        if not self.auto_cleanup_enabled:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)
                try:
                    await self.run_full_cleanup()
                except Exception as e:
                    logger.error(f"Erro no cleanup periódico: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(
            f"Cleanup periódico iniciado (intervalo: {self.cleanup_interval_hours}h)"
        )

    async def stop_periodic_cleanup(self):
        """Para cleanup periódico"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

    def list_backups(self, item_type: str = None) -> List[Dict]:
        """Lista backups disponíveis"""
        backups = []

        dirs_to_check = (
            [self.backup_dirs[item_type]] if item_type else self.backup_dirs.values()
        )

        for backup_dir in dirs_to_check:
            if not backup_dir.exists():
                continue

            for item in backup_dir.iterdir():
                if item.name.endswith("_metadata.json"):
                    continue

                # Ler metadados se existir
                meta_path = backup_dir / f"{item.name}_metadata.json"
                metadata = {}
                if meta_path.exists():
                    try:
                        metadata = json.loads(meta_path.read_text())
                    except:
                        pass

                backups.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": item_type or backup_dir.name,
                        "size_mb": (
                            self._get_dir_size(item) / (1024 * 1024)
                            if item.is_dir()
                            else item.stat().st_size / (1024 * 1024)
                        ),
                        "metadata": metadata,
                    }
                )

        return sorted(
            backups,
            key=lambda x: x.get("metadata", {}).get("backup_date", ""),
            reverse=True,
        )
