#!/usr/bin/env python3
"""Ferramenta de tombamento piloto de arquivos para Nextcloud via WebDAV.

Este script foi desenhado para a fase piloto da migração Google Drive -> Nextcloud,
assumindo que os arquivos já foram exportados para um diretório local.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


LOGGER = logging.getLogger("gdrive_to_nextcloud_pilot")
DEFAULT_TIMEOUT_SECONDS: float = 60.0
DEFAULT_CHUNK_SIZE: int = 1024 * 1024


@dataclass
class FileEntry:
    """Representa um arquivo local candidato ao tombamento."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass
class MigrationReport:
    """Representa o resultado da execução de tombamento."""

    started_at: str
    finished_at: str
    source_dir: str
    remote_dir: str
    dry_run: bool
    total_files: int
    total_bytes: int
    uploaded_files: int
    uploaded_bytes: int
    skipped_files: int
    failed_files: int
    failures: list[dict[str, str]]


class NextcloudWebDavClient:
    """Cliente mínimo de WebDAV para operações de migração."""

    def __init__(self, *, base_url: str, username: str, password: str, timeout: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._timeout = timeout

    def _build_url(self, webdav_path: str) -> str:
        normalized_path = webdav_path.lstrip("/")
        return f"{self._base_url}/remote.php/dav/files/{parse.quote(self._username, safe='')}/{normalized_path}"

    def _auth_header(self) -> str:
        token = base64.b64encode(f"{self._username}:{self._password}".encode("utf-8")).decode("utf-8")
        return f"Basic {token}"

    def _request(
        self,
        *,
        method: str,
        webdav_path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        req_headers = {
            "Authorization": self._auth_header(),
            "User-Agent": "rpa4all-migration-pilot/1.0",
        }
        if headers:
            req_headers.update(headers)

        req = request.Request(
            url=self._build_url(webdav_path),
            data=body,
            headers=req_headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                return response.status, response.read()
        except error.HTTPError as exc:
            return exc.code, exc.read()
        except error.URLError as exc:
            LOGGER.error("Falha de rede no WebDAV (%s %s): %s", method, webdav_path, exc)
            return 599, b""

    async def exists(self, webdav_path: str) -> bool:
        """Verifica se um objeto já existe no destino remoto."""
        status, _ = await asyncio.to_thread(self._request, method="HEAD", webdav_path=webdav_path)
        return status == 200

    async def mkcol(self, webdav_path: str) -> bool:
        """Cria diretório remoto se necessário."""
        status, _ = await asyncio.to_thread(self._request, method="MKCOL", webdav_path=webdav_path)
        return status in {201, 405}

    async def put_file(self, *, webdav_path: str, local_file: Path) -> bool:
        """Envia arquivo local para um caminho remoto."""
        try:
            payload = await asyncio.to_thread(local_file.read_bytes)
        except OSError as exc:
            LOGGER.error("Falha ao ler arquivo local %s: %s", local_file, exc)
            return False

        status, _ = await asyncio.to_thread(
            self._request,
            method="PUT",
            webdav_path=webdav_path,
            body=payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        return status in {200, 201, 204}


def parse_args() -> argparse.Namespace:
    """Lê argumentos da linha de comando."""
    parser = argparse.ArgumentParser(description="Tombamento piloto de arquivos para Nextcloud")
    parser.add_argument("--source-dir", required=True, help="Diretório local com export do Drive")
    parser.add_argument("--remote-dir", default="RPA4ALL/Migracoes/Piloto", help="Diretório remoto no Nextcloud")
    parser.add_argument("--nextcloud-url", help="URL base do Nextcloud, ex.: https://nextcloud.rpa4all.com")
    parser.add_argument("--nextcloud-user", help="Usuário de destino no Nextcloud")
    parser.add_argument(
        "--nextcloud-password-env",
        default="NEXTCLOUD_APP_PASSWORD",
        help="Variável de ambiente contendo app password do Nextcloud",
    )
    parser.add_argument("--baseline-json", default="artifacts/gdrive_nextcloud_baseline.json")
    parser.add_argument("--report-json", default="artifacts/gdrive_nextcloud_report.json")
    parser.add_argument("--max-concurrency", type=int, default=3)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def compute_sha256(file_path: Path) -> str:
    """Calcula SHA-256 de um arquivo para baseline/integridade."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(DEFAULT_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def list_local_files(source_dir: Path) -> list[Path]:
    """Lista todos os arquivos do diretório de origem de forma estável."""
    return sorted([path for path in source_dir.rglob("*") if path.is_file()])


def to_file_entries(*, source_dir: Path, files: list[Path]) -> list[FileEntry]:
    """Converte arquivos locais para a estrutura de baseline."""
    entries: list[FileEntry] = []
    for local_path in files:
        relative_path = local_path.relative_to(source_dir).as_posix()
        file_stat = local_path.stat()
        entries.append(
            FileEntry(
                relative_path=relative_path,
                size_bytes=file_stat.st_size,
                sha256=compute_sha256(local_path),
            )
        )
    return entries


def build_baseline(*, source_dir: Path, remote_dir: str, entries: list[FileEntry]) -> dict[str, Any]:
    """Monta baseline de comparação do tombamento."""
    total_bytes = sum(entry.size_bytes for entry in entries)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "remote_dir": remote_dir,
        "total_files": len(entries),
        "total_bytes": total_bytes,
        "entries": [asdict(entry) for entry in entries],
    }


def build_webdav_path(*, remote_dir: str, relative_path: str) -> str:
    """Constrói caminho WebDAV com escape seguro por segmento."""
    remote_segments = [segment for segment in remote_dir.strip("/").split("/") if segment]
    relative_segments = [segment for segment in relative_path.split("/") if segment]
    encoded_segments = [parse.quote(segment, safe="") for segment in [*remote_segments, *relative_segments]]
    return "/".join(encoded_segments)


async def ensure_remote_directories(client: NextcloudWebDavClient, *, remote_dir: str, relative_path: str) -> bool:
    """Garante criação de toda a hierarquia de diretórios do arquivo remoto."""
    parent_parts = Path(relative_path).parent.parts
    if not parent_parts:
        return True

    current_parts: list[str] = []
    for segment in [part for part in remote_dir.strip("/").split("/") if part]:
        current_parts.append(segment)
        ok = await client.mkcol("/".join(parse.quote(item, safe="") for item in current_parts))
        if not ok:
            return False

    for part in parent_parts:
        current_parts.append(part)
        ok = await client.mkcol("/".join(parse.quote(item, safe="") for item in current_parts))
        if not ok:
            return False
    return True


async def migrate_files(
    *,
    source_dir: Path,
    remote_dir: str,
    entries: list[FileEntry],
    client: NextcloudWebDavClient | None,
    dry_run: bool,
    max_concurrency: int,
    skip_existing: bool,
) -> MigrationReport:
    """Executa tombamento dos arquivos para o destino remoto."""
    started = datetime.now(timezone.utc)
    report = MigrationReport(
        started_at=started.isoformat(),
        finished_at=started.isoformat(),
        source_dir=str(source_dir),
        remote_dir=remote_dir,
        dry_run=dry_run,
        total_files=len(entries),
        total_bytes=sum(item.size_bytes for item in entries),
        uploaded_files=0,
        uploaded_bytes=0,
        skipped_files=0,
        failed_files=0,
        failures=[],
    )

    if dry_run:
        report.skipped_files = len(entries)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    if client is None:
        raise ValueError("Cliente Nextcloud é obrigatório quando dry-run está desativado")

    semaphore = asyncio.Semaphore(max_concurrency)
    lock = asyncio.Lock()

    async def process_entry(entry: FileEntry) -> None:
        local_file = source_dir / entry.relative_path
        webdav_path = build_webdav_path(remote_dir=remote_dir, relative_path=entry.relative_path)

        async with semaphore:
            try:
                if skip_existing:
                    exists = await client.exists(webdav_path)
                    if exists:
                        async with lock:
                            report.skipped_files += 1
                        return

                dirs_ok = await ensure_remote_directories(client, remote_dir=remote_dir, relative_path=entry.relative_path)
                if not dirs_ok:
                    async with lock:
                        report.failed_files += 1
                        report.failures.append(
                            {
                                "relative_path": entry.relative_path,
                                "reason": "Falha ao garantir diretórios remotos",
                            }
                        )
                    return

                uploaded = await client.put_file(webdav_path=webdav_path, local_file=local_file)
                async with lock:
                    if uploaded:
                        report.uploaded_files += 1
                        report.uploaded_bytes += entry.size_bytes
                    else:
                        report.failed_files += 1
                        report.failures.append(
                            {
                                "relative_path": entry.relative_path,
                                "reason": "Falha no upload via WebDAV",
                            }
                        )
            except (OSError, ValueError) as exc:
                async with lock:
                    report.failed_files += 1
                    report.failures.append({"relative_path": entry.relative_path, "reason": str(exc)})

    await asyncio.gather(*(process_entry(entry) for entry in entries))
    report.finished_at = datetime.now(timezone.utc).isoformat()
    return report


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """Escreve JSON em disco com diretórios criados automaticamente."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def configure_logging(level: str) -> None:
    """Configura logging da execução."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def run() -> int:
    """Executa o fluxo principal do tombamento piloto."""
    args = parse_args()
    configure_logging(args.log_level)

    source_dir = Path(args.source_dir).expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        LOGGER.error("Diretório de origem inválido: %s", source_dir)
        return 2

    files = list_local_files(source_dir)
    entries = to_file_entries(source_dir=source_dir, files=files)
    baseline = build_baseline(source_dir=source_dir, remote_dir=args.remote_dir, entries=entries)
    write_json_file(Path(args.baseline_json), baseline)
    LOGGER.info("Baseline gerado: %s", args.baseline_json)

    client: NextcloudWebDavClient | None = None
    if not args.dry_run:
        if not args.nextcloud_url or not args.nextcloud_user:
            LOGGER.error("--nextcloud-url e --nextcloud-user são obrigatórios sem --dry-run")
            return 2
        nextcloud_password = os.environ.get(args.nextcloud_password_env)
        if not nextcloud_password:
            LOGGER.error("Variável de ambiente ausente: %s", args.nextcloud_password_env)
            return 2
        client = NextcloudWebDavClient(
            base_url=args.nextcloud_url,
            username=args.nextcloud_user,
            password=nextcloud_password,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

    report = await migrate_files(
        source_dir=source_dir,
        remote_dir=args.remote_dir,
        entries=entries,
        client=client,
        dry_run=args.dry_run,
        max_concurrency=args.max_concurrency,
        skip_existing=args.skip_existing,
    )
    write_json_file(Path(args.report_json), asdict(report))

    LOGGER.info(
        "Finalizado. total=%s enviados=%s pulados=%s falhas=%s",
        report.total_files,
        report.uploaded_files,
        report.skipped_files,
        report.failed_files,
    )
    return 0 if report.failed_files == 0 else 1


def main() -> None:
    """Ponto de entrada do script."""
    try:
        raise SystemExit(asyncio.run(run()))
    except KeyboardInterrupt:
        LOGGER.warning("Execução interrompida pelo operador")
        raise SystemExit(130)


if __name__ == "__main__":
    main()