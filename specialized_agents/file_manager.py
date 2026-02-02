"""
Gerenciador de Arquivos
Upload, download, zip e organização de arquivos
"""

import shutil
import zipfile
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import mimetypes

from .config import UPLOAD_DIR, DATA_DIR, PROJECTS_DIR, BACKUP_DIR, FILE_EXTENSIONS


@dataclass
class FileInfo:
    name: str
    path: str
    size: int
    mime_type: str
    language: Optional[str]
    created_at: datetime
    modified_at: datetime
    checksum: str

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mime_type": self.mime_type,
            "language": self.language,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "checksum": self.checksum,
        }


class FileManager:
    """
    Gerencia upload, download e organização de arquivos.
    Suporta arquivos individuais e ZIP.
    """

    def __init__(self):
        self.upload_dir = UPLOAD_DIR
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.allowed_extensions = {
            ".py",
            ".js",
            ".ts",
            ".go",
            ".rs",
            ".java",
            ".cs",
            ".php",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            ".txt",
            ".md",
            ".rst",
            ".html",
            ".css",
            ".scss",
            ".sh",
            ".bash",
            ".sql",
            ".zip",
            ".tar",
            ".gz",
            ".dockerfile",
            ".env",
        }

    def _get_checksum(self, file_path: Path) -> str:
        """Calcula MD5 do arquivo"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def _detect_language(self, filename: str) -> Optional[str]:
        """Detecta linguagem pelo nome do arquivo"""
        ext = Path(filename).suffix.lower()
        return FILE_EXTENSIONS.get(ext)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitiza nome de arquivo"""
        # Remover caracteres perigosos
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        return filename

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        language: str = None,
        project_name: str = None,
    ) -> Dict[str, Any]:
        """Faz upload de arquivo"""
        filename = self._sanitize_filename(filename)
        ext = Path(filename).suffix.lower()

        # Validar extensão
        if ext not in self.allowed_extensions and ext != "":
            return {"success": False, "error": f"Extensão não permitida: {ext}"}

        # Validar tamanho
        if len(file_content) > self.max_file_size:
            return {"success": False, "error": "Arquivo muito grande"}

        # Detectar linguagem
        if not language:
            language = self._detect_language(filename) or "unknown"

        # Determinar diretório destino
        if project_name:
            dest_dir = PROJECTS_DIR / language / project_name
        else:
            dest_dir = self.upload_dir / language / datetime.now().strftime("%Y%m%d")

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        # Evitar sobrescrita
        if dest_path.exists():
            base = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = dest_dir / f"{base}_{counter}{suffix}"
                counter += 1

        # Salvar arquivo
        dest_path.write_bytes(file_content)

        # Criar info
        stat = dest_path.stat()
        file_info = FileInfo(
            name=dest_path.name,
            path=str(dest_path),
            size=stat.st_size,
            mime_type=mimetypes.guess_type(str(dest_path))[0]
            or "application/octet-stream",
            language=language,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            checksum=self._get_checksum(dest_path),
        )

        return {"success": True, "file": file_info.to_dict()}

    async def upload_zip(
        self,
        zip_content: bytes,
        language: str = None,
        project_name: str = None,
        extract: bool = True,
    ) -> Dict[str, Any]:
        """Faz upload e extração de ZIP"""
        # Salvar ZIP temporário
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_name = project_name or f"upload_{timestamp}"

        temp_zip = self.upload_dir / f"temp_{timestamp}.zip"
        temp_zip.write_bytes(zip_content)

        try:
            # Verificar se é um ZIP válido
            if not zipfile.is_zipfile(temp_zip):
                temp_zip.unlink()
                return {"success": False, "error": "Arquivo ZIP inválido"}

            if not extract:
                # Apenas salvar o ZIP
                dest_dir = self.upload_dir / "zips"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / f"{project_name}.zip"
                shutil.move(temp_zip, dest_path)

                return {"success": True, "zip_path": str(dest_path), "extracted": False}

            # Extrair
            extract_dir = PROJECTS_DIR / (language or "unknown") / project_name
            extract_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(temp_zip, "r") as zf:
                # Verificar arquivos
                files_extracted = []
                for member in zf.namelist():
                    # Segurança: evitar path traversal
                    member_path = Path(member)
                    if ".." in member_path.parts:
                        continue

                    zf.extract(member, extract_dir)
                    files_extracted.append(member)

            # Remover ZIP temporário
            temp_zip.unlink()

            # Auto-detectar linguagem se não especificada
            if not language:
                language = self._detect_project_language(extract_dir)

            return {
                "success": True,
                "project_path": str(extract_dir),
                "language": language,
                "files_extracted": files_extracted,
                "extracted": True,
            }

        except Exception as e:
            if temp_zip.exists():
                temp_zip.unlink()
            return {"success": False, "error": str(e)}

    def _detect_project_language(self, project_dir: Path) -> str:
        """Detecta linguagem principal do projeto"""
        language_files = {
            "python": ["setup.py", "pyproject.toml", "requirements.txt"],
            "javascript": ["package.json"],
            "typescript": ["tsconfig.json"],
            "go": ["go.mod"],
            "rust": ["Cargo.toml"],
            "java": ["pom.xml", "build.gradle"],
            "csharp": ["*.csproj", "*.sln"],
            "php": ["composer.json"],
        }

        for lang, files in language_files.items():
            for pattern in files:
                if "*" in pattern:
                    if list(project_dir.glob(pattern)):
                        return lang
                else:
                    if (project_dir / pattern).exists():
                        return lang

        # Contar extensões
        ext_count = {}
        for file in project_dir.rglob("*"):
            if file.is_file():
                ext = file.suffix.lower()
                lang = FILE_EXTENSIONS.get(ext)
                if lang:
                    ext_count[lang] = ext_count.get(lang, 0) + 1

        if ext_count:
            return max(ext_count, key=ext_count.get)

        return "unknown"

    async def download_file(self, file_path: str) -> Optional[bytes]:
        """Baixa um arquivo"""
        path = Path(file_path)
        if not path.exists():
            return None

        # Verificar se está em diretório permitido
        allowed_dirs = [UPLOAD_DIR, PROJECTS_DIR, DATA_DIR, BACKUP_DIR]
        if not any(str(path).startswith(str(d)) for d in allowed_dirs):
            return None

        return path.read_bytes()

    async def download_project_as_zip(
        self,
        project_path: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
    ) -> Optional[bytes]:
        """Baixa projeto como ZIP"""
        project_dir = Path(project_path)
        if not project_dir.exists():
            return None

        # Padrões default de exclusão
        default_exclude = [
            "__pycache__",
            "node_modules",
            ".git",
            "target",
            "bin",
            "obj",
            ".venv",
            "venv",
            "*.pyc",
            ".env",
        ]
        exclude_patterns = (exclude_patterns or []) + default_exclude

        # Criar ZIP em memória
        import io

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in project_dir.rglob("*"):
                if not file_path.is_file():
                    continue

                # Verificar exclusões
                relative = file_path.relative_to(project_dir)
                skip = False
                for pattern in exclude_patterns:
                    if pattern.startswith("*"):
                        if file_path.suffix == pattern[1:]:
                            skip = True
                            break
                    elif pattern in str(relative):
                        skip = True
                        break

                if skip:
                    continue

                # Verificar inclusões se especificado
                if include_patterns:
                    include = False
                    for pattern in include_patterns:
                        if pattern in str(relative):
                            include = True
                            break
                    if not include:
                        continue

                zf.write(file_path, relative)

        zip_buffer.seek(0)
        return zip_buffer.read()

    async def list_files(
        self, directory: str = None, language: str = None, recursive: bool = True
    ) -> List[Dict]:
        """Lista arquivos"""
        if directory:
            base_dir = Path(directory)
        elif language:
            base_dir = PROJECTS_DIR / language
        else:
            base_dir = self.upload_dir

        if not base_dir.exists():
            return []

        files = []
        iterator = base_dir.rglob("*") if recursive else base_dir.glob("*")

        for file_path in iterator:
            if not file_path.is_file():
                continue

            stat = file_path.stat()
            files.append(
                {
                    "name": file_path.name,
                    "path": str(file_path),
                    "size": stat.st_size,
                    "language": self._detect_language(file_path.name),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return sorted(files, key=lambda x: x["modified"], reverse=True)

    async def delete_file(self, file_path: str, backup: bool = True) -> bool:
        """Deleta arquivo"""
        path = Path(file_path)
        if not path.exists():
            return False

        # Backup
        if backup:
            backup_path = BACKUP_DIR / "deleted" / datetime.now().strftime("%Y%m%d")
            backup_path.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup_path / path.name)

        path.unlink()
        return True

    async def delete_directory(self, dir_path: str, backup: bool = True) -> bool:
        """Deleta diretório"""
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            return False

        # Backup
        if backup:
            backup_name = f"{path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_path = BACKUP_DIR / "deleted_dirs" / backup_name
            shutil.copytree(path, backup_path)

        shutil.rmtree(path)
        return True

    async def read_file_content(self, file_path: str) -> Optional[str]:
        """Lê conteúdo de arquivo de texto"""
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            return path.read_text()
        except:
            return None

    async def write_file_content(
        self, file_path: str, content: str, backup: bool = True
    ) -> bool:
        """Escreve conteúdo em arquivo"""
        path = Path(file_path)

        # Backup se existir
        if backup and path.exists():
            backup_dir = BACKUP_DIR / "edits" / datetime.now().strftime("%Y%m%d")
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                path,
                backup_dir
                / f"{path.stem}_{datetime.now().strftime('%H%M%S')}{path.suffix}",
            )

        # Criar diretório se necessário
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content)
        return True

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de armazenamento"""

        def get_dir_size(path: Path) -> int:
            total = 0
            if path.exists():
                for f in path.rglob("*"):
                    if f.is_file():
                        total += f.stat().st_size
            return total

        return {
            "upload_dir": {
                "path": str(self.upload_dir),
                "size_bytes": get_dir_size(self.upload_dir),
                "size_mb": get_dir_size(self.upload_dir) / (1024 * 1024),
            },
            "projects_dir": {
                "path": str(PROJECTS_DIR),
                "size_bytes": get_dir_size(PROJECTS_DIR),
                "size_mb": get_dir_size(PROJECTS_DIR) / (1024 * 1024),
            },
            "backup_dir": {
                "path": str(BACKUP_DIR),
                "size_bytes": get_dir_size(BACKUP_DIR),
                "size_mb": get_dir_size(BACKUP_DIR) / (1024 * 1024),
            },
        }

    async def search_files(
        self, query: str, language: str = None, search_content: bool = False
    ) -> List[Dict]:
        """Busca arquivos por nome ou conteúdo"""
        results = []

        if language:
            search_dir = PROJECTS_DIR / language
        else:
            search_dir = PROJECTS_DIR

        if not search_dir.exists():
            return []

        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Busca por nome
            if query.lower() in file_path.name.lower():
                results.append(
                    {
                        "name": file_path.name,
                        "path": str(file_path),
                        "match_type": "filename",
                    }
                )
                continue

            # Busca por conteúdo
            if search_content:
                try:
                    content = file_path.read_text()
                    if query.lower() in content.lower():
                        results.append(
                            {
                                "name": file_path.name,
                                "path": str(file_path),
                                "match_type": "content",
                            }
                        )
                except:
                    pass

        return results[:50]  # Limitar resultados
