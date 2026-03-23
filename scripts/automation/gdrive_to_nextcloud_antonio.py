#!/usr/bin/env python3
"""
Migração Google Drive → Nextcloud: antonio.carneiro@rpa4all.com

Exporta arquivos do Google Drive acessíveis via token admin e faz upload
para o espaço do usuário no Nextcloud usando WebDAV (credencial admin).

Uso:
  python3 scripts/automation/gdrive_to_nextcloud_antonio.py [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configurações fixas do ambiente
# ─────────────────────────────────────────────────────────────────────────────

NEXTCLOUD_URL = "https://nextcloud.rpa4all.com"
NEXTCLOUD_ADMIN_USER = "admin"
NEXTCLOUD_ADMIN_PASS = os.environ.get("NEXTCLOUD_ADMIN_PASSWORD", "eddie_cloud_2026")
TARGET_NC_USER = "antonio.carneiro@rpa4all.com"
REMOTE_BASE_DIR = "GDrive-Migracao"

GOOGLE_TARGET_USER = "antonio.carneiro@rpa4all.com"

REPORT_JSON = Path("artifacts/gdrive_nc_antonio_report.json")
BASELINE_JSON = Path("artifacts/gdrive_nc_antonio_baseline.json")

# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses de resultado
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DriveFile:
    """Arquivo encontrado no Google Drive."""

    id: str
    name: str
    mime_type: str
    size_bytes: int
    owners: list[str]
    parents: list[str]
    modified_time: str
    web_view_link: str
    path: str = ""  # path remoto calculado


@dataclass
class MigrationResult:
    """Resultado de uma tentativa de migração de arquivo."""

    file_id: str
    name: str
    path: str
    size_bytes: int
    status: str  # "uploaded" | "skipped" | "failed" | "dry_run"
    error: str = ""
    sha256: str = ""


@dataclass
class MigrationReport:
    """Relatório completo de migração."""

    started_at: str = ""
    finished_at: str = ""
    dry_run: bool = False
    target_user: str = GOOGLE_TARGET_USER
    total_found: int = 0
    total_bytes: int = 0
    uploaded: int = 0
    uploaded_bytes: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[MigrationResult] = field(default_factory=list)
    note: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Google Drive Client
# ─────────────────────────────────────────────────────────────────────────────


def _load_gdrive_token() -> dict[str, Any]:
    """Carrega token GDrive do secrets agent (base64) ou da env var."""
    raw_b64 = os.environ.get("GDRIVE_TOKEN_B64", "")
    if raw_b64:
        return json.loads(base64.b64decode(raw_b64).decode())
    # Tenta arquivo local do session token
    token_file = Path("/tmp/gdrive_token_adm.json")
    if token_file.exists():
        return json.loads(token_file.read_text())
    raise RuntimeError(
        "Token GDrive não encontrado. Defina GDRIVE_TOKEN_B64 ou "
        "crie /tmp/gdrive_token_adm.json"
    )


def _build_drive_service() -> Any:
    """Constrói o serviço Google Drive API v3."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        token_data = _load_gdrive_token()
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        logger.error("Falha ao criar serviço Drive: %s", exc)
        raise


def list_user_files(service: Any, owner_email: str) -> list[DriveFile]:
    """
    Lista todos os arquivos do Google Drive acessíveis e pertencentes ao usuário.

    Usa querystring `'<email>' in owners` para filtrar por proprietário.
    """
    files: list[DriveFile] = []
    query = f"'{owner_email}' in owners and trashed = false"
    page_token: str | None = None
    fields = (
        "nextPageToken, files(id, name, mimeType, size, owners, parents, "
        "modifiedTime, webViewLink)"
    )

    logger.info("Listando arquivos do Drive para %s ...", owner_email)

    while True:
        try:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields=fields,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    corpora="allDrives",
                    pageSize=200,
                    pageToken=page_token,
                )
                .execute()
            )
        except Exception as exc:
            logger.error("Erro na listagem do Drive: %s", exc)
            break

        for f in response.get("files", []):
            mime = f.get("mimeType", "")
            # Pula pastas (serão re-criadas implicitamente)
            if mime == "application/vnd.google-apps.folder":
                continue
            size = int(f.get("size", 0))
            owners = [o["emailAddress"] for o in f.get("owners", [])]
            files.append(
                DriveFile(
                    id=f["id"],
                    name=f["name"],
                    mime_type=mime,
                    size_bytes=size,
                    owners=owners,
                    parents=f.get("parents", []),
                    modified_time=f.get("modifiedTime", ""),
                    web_view_link=f.get("webViewLink", ""),
                )
            )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return files


def _mime_to_export(mime_type: str) -> tuple[str, str]:
    """
    Retorna (mimetype_export, extensão) para exportação de tipos Google Docs.
    Retorna ("", "") se não for tipo Google Docs.
    """
    mapping = {
        "application/vnd.google-apps.document": ("text/plain", ".txt"),
        "application/vnd.google-apps.spreadsheet": (
            "text/csv",
            ".csv",
        ),
        "application/vnd.google-apps.presentation": (
            "application/pdf",
            ".pdf",
        ),
        "application/vnd.google-apps.drawing": ("image/svg+xml", ".svg"),
    }
    return mapping.get(mime_type, ("", ""))


def download_drive_file(service: Any, drive_file: DriveFile) -> bytes | None:
    """
    Baixa o conteúdo de um arquivo do Drive para memória.
    Google Docs são exportados para formato aberto compatível.
    """
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import]

    export_mime, _ = _mime_to_export(drive_file.mime_type)
    fh = BytesIO()

    try:
        if export_mime:
            request = service.files().export(
                fileId=drive_file.id, mimeType=export_mime
            )
        else:
            request = service.files().get_media(fileId=drive_file.id)

        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        return fh.getvalue()
    except Exception as exc:
        logger.warning("Não foi possível baixar %s: %s", drive_file.name, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Nextcloud WebDAV Client
# ─────────────────────────────────────────────────────────────────────────────


def _webdav_request(
    method: str, path: str, data: bytes | None = None, timeout: int = 60
) -> int:
    """Executa requisição WebDAV e retorna HTTP status code."""
    encoded_path = "/".join(
        urllib.parse.quote(segment, safe="@") for segment in path.split("/") if segment
    )
    url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{encoded_path}"
    credentials = base64.b64encode(
        f"{NEXTCLOUD_ADMIN_USER}:{NEXTCLOUD_ADMIN_PASS}".encode()
    ).decode()
    headers: dict[str, str] = {"Authorization": f"Basic {credentials}"}
    if method == "MKCOL":
        headers["Content-Length"] = "0"
    if data is not None:
        headers["Content-Length"] = str(len(data))

    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError:
        return 599


def ensure_remote_dir(remote_path: str) -> None:
    """Cria diretório remoto (e pais) no Nextcloud via MKCOL."""
    parts = [p for p in remote_path.split("/") if p]
    accumulated: list[str] = []
    for part in parts:
        accumulated.append(part)
        code = _webdav_request("MKCOL", "/".join(accumulated))
        if code not in (201, 301, 405):  # 405 = já existe
            logger.debug("MKCOL /%s → %d", "/".join(accumulated), code)


def upload_file_to_nextcloud(
    remote_path: str, content: bytes, overwrite: bool = True
) -> int:
    """
    Faz upload de conteúdo para o Nextcloud via WebDAV PUT.
    Retorna HTTP status code.
    """
    if not overwrite:
        code = _webdav_request("HEAD", remote_path)
        if code == 200:
            return 200  # já existe, pular

    return _webdav_request("PUT", remote_path, data=content)


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração da migração
# ─────────────────────────────────────────────────────────────────────────────


def _safe_remote_name(drive_file: DriveFile) -> str:
    """Gera nome remoto com extensão correta para arquivos Google Docs."""
    _, ext = _mime_to_export(drive_file.mime_type)
    name = drive_file.name
    if ext and not name.endswith(ext):
        name = f"{name}{ext}"
    return name


def run_migration(dry_run: bool = False) -> MigrationReport:
    """
    Executa a migração completa GDrive → Nextcloud para antonio.carneiro.

    Args:
        dry_run: Se True, apenas lista e reporta, sem fazer uploads.

    Returns:
        MigrationReport com resultados completos.
    """
    report = MigrationReport(
        started_at=datetime.now(timezone.utc).isoformat(),
        dry_run=dry_run,
    )

    # ── 1. Conectar ao Google Drive ─────────────────────────────────────────
    print("\n" + "═" * 70)
    print(f"  MIGRAÇÃO GOOGLE DRIVE → NEXTCLOUD")
    print(f"  Usuário-alvo: {GOOGLE_TARGET_USER}")
    print(f"  Destino NC:   {NEXTCLOUD_URL}/{REMOTE_BASE_DIR}/")
    if dry_run:
        print("  ⚠  MODO DRY-RUN — nenhum arquivo será enviado")
    print("═" * 70 + "\n")

    try:
        service = _build_drive_service()
    except Exception as exc:
        logger.error("Não foi possível conectar ao Google Drive: %s", exc)
        report.note = f"Falha ao conectar ao Drive: {exc}"
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    # ── 2. Listar arquivos do usuário ───────────────────────────────────────
    with tqdm(desc="Listando Drive", unit=" arq", bar_format="{l_bar}{bar}| {n_fmt} [{elapsed}]") as pbar:
        files = list_user_files(service, GOOGLE_TARGET_USER)
        pbar.update(len(files))

    total_bytes = sum(f.size_bytes for f in files)
    report.total_found = len(files)
    report.total_bytes = total_bytes

    if not files:
        report.note = (
            "Nenhum arquivo encontrado. O token admin pode não ter acesso "
            "aos arquivos pessoais de antonio.carneiro — use DWD ou token do próprio usuário."
        )
        logger.warning(report.note)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    logger.info(
        "Encontrados %d arquivos (%.1f MB) para %s",
        len(files),
        total_bytes / 1024 / 1024,
        GOOGLE_TARGET_USER,
    )

    # ── 3. Salvar baseline ──────────────────────────────────────────────────
    BASELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_user": GOOGLE_TARGET_USER,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "files": [
            {
                "id": f.id,
                "name": f.name,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
                "owners": f.owners,
                "modified_time": f.modified_time,
            }
            for f in files
        ],
    }
    BASELINE_JSON.write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
    logger.info("Baseline salvo em %s", BASELINE_JSON)

    # ── 4. Criar diretório raiz no NC ───────────────────────────────────────
    if not dry_run:
        nc_root = f"{TARGET_NC_USER}/{REMOTE_BASE_DIR}"
        ensure_remote_dir(nc_root)

    # ── 5. Migrar arquivos com progress bar ─────────────────────────────────
    bar_format = (
        "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining},"
        " {rate_fmt}]"
    )

    with tqdm(
        total=total_bytes,
        desc="Migrando",
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        bar_format=bar_format,
        colour="green",
        dynamic_ncols=True,
    ) as pbar:
        for drive_file in files:
            remote_name = _safe_remote_name(drive_file)
            remote_path = f"{TARGET_NC_USER}/{REMOTE_BASE_DIR}/{remote_name}"
            drive_file.path = remote_path

            pbar.set_description(f"↑ {drive_file.name[:40]:<40}")

            if dry_run:
                result = MigrationResult(
                    file_id=drive_file.id,
                    name=drive_file.name,
                    path=remote_path,
                    size_bytes=drive_file.size_bytes,
                    status="dry_run",
                )
                report.skipped += 1
            else:
                content = download_drive_file(service, drive_file)
                if content is None:
                    result = MigrationResult(
                        file_id=drive_file.id,
                        name=drive_file.name,
                        path=remote_path,
                        size_bytes=drive_file.size_bytes,
                        status="failed",
                        error="Download falhou",
                    )
                    report.failed += 1
                else:
                    sha256 = hashlib.sha256(content).hexdigest()
                    dir_path = f"{TARGET_NC_USER}/{REMOTE_BASE_DIR}"
                    ensure_remote_dir(dir_path)
                    http_code = upload_file_to_nextcloud(remote_path, content)

                    if http_code in (200, 201, 204):
                        result = MigrationResult(
                            file_id=drive_file.id,
                            name=drive_file.name,
                            path=remote_path,
                            size_bytes=drive_file.size_bytes,
                            status="uploaded",
                            sha256=sha256,
                        )
                        report.uploaded += 1
                        report.uploaded_bytes += drive_file.size_bytes
                    else:
                        result = MigrationResult(
                            file_id=drive_file.id,
                            name=drive_file.name,
                            path=remote_path,
                            size_bytes=drive_file.size_bytes,
                            status="failed",
                            error=f"WebDAV PUT retornou {http_code}",
                        )
                        report.failed += 1

            report.results.append(result)
            pbar.update(drive_file.size_bytes or 1)

    # ── 6. Resumo final ─────────────────────────────────────────────────────
    report.finished_at = datetime.now(timezone.utc).isoformat()

    print("\n" + "─" * 70)
    print("  RELATÓRIO DE MIGRAÇÃO")
    print("─" * 70)
    print(f"  Usuário:          {report.target_user}")
    print(f"  Total encontrado: {report.total_found} arquivos "
          f"({report.total_bytes / 1024 / 1024:.1f} MB)")

    if dry_run:
        print(f"  Dry-run (sem upload): {report.skipped} arquivos analisados")
    else:
        ok_icon = "✓" if report.failed == 0 else "⚠"
        print(f"  {ok_icon} Enviados:      {report.uploaded} "
              f"({report.uploaded_bytes / 1024 / 1024:.1f} MB)")
        print(f"  Pulados:          {report.skipped}")
        print(f"  Falhas:           {report.failed}")
        if report.failed > 0:
            print("\n  Arquivos com falha:")
            for r in report.results:
                if r.status == "failed":
                    print(f"    • {r.name}: {r.error}")

    print("─" * 70)
    print(f"  Relatório JSON:   {REPORT_JSON}")
    print(f"  Baseline JSON:    {BASELINE_JSON}")
    print("─" * 70 + "\n")

    # Salvar relatório JSON
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    report_data = asdict(report)
    REPORT_JSON.write_text(json.dumps(report_data, indent=2, ensure_ascii=False))

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada do script de migração."""
    parser = argparse.ArgumentParser(
        description="Migra Google Drive de antonio.carneiro para Nextcloud"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas lista arquivos, sem fazer upload",
    )
    args = parser.parse_args()

    report = run_migration(dry_run=args.dry_run)

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
