#!/usr/bin/env python3
"""
Migração interativa: Google Drive (antonio.carneiro@rpa4all.com) → Nextcloud.

Fluxo:
  1. Verifica se já existe token salvo em /tmp/gdrive_token_antonio.json
  2. Se não existir, gera URL de autorização OAuth e aguarda o código
  3. Troca o código por tokens e salva
  4. Lista todos os arquivos do Drive do usuário  
  5. Faz upload para Nextcloud com progress bar
  6. Gera relatório JSON

Uso:
  python3 scripts/automation/migrate_antonio_gdrive.py [--dry-run]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import logging
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configurações
# ─────────────────────────────────────────────────────────────────────────────

OAUTH_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
OAUTH_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
OAUTH_PORT = 8765
OAUTH_REDIRECT_URI = f"http://localhost:{OAUTH_PORT}"
TOKEN_FILE = Path("/tmp/gdrive_token_antonio.json")
TARGET_GDRIVE_USER = "antonio.carneiro@rpa4all.com"

NEXTCLOUD_URL = "https://nextcloud.rpa4all.com"
NEXTCLOUD_ADMIN_USER = "admin"
NEXTCLOUD_ADMIN_PASS = os.environ.get("NEXTCLOUD_ADMIN_PASSWORD", "eddie_cloud_2026")
NC_TARGET_USER = "antonio.carneiro@rpa4all.com"
NC_REMOTE_DIR = "GDrive-Migracao"

REPORT_JSON = Path("artifacts/gdrive_nc_antonio_report.json")
BASELINE_JSON = Path("artifacts/gdrive_nc_antonio_baseline.json")


# ─────────────────────────────────────────────────────────────────────────────
# Autorização Google OAuth2
# ─────────────────────────────────────────────────────────────────────────────


def _build_auth_url() -> str:
    """Gera URL de autorização OAuth2 com redirect para localhost."""
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": TARGET_GDRIVE_USER,
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)


def _wait_for_oauth_code() -> str:
    """
    Sobe um servidor HTTP temporário na porta OAUTH_PORT e aguarda o
    redirecionamento do Google com o código de autorização.
    Retorna o código capturado.
    """
    captured: dict[str, str] = {}
    event = threading.Event()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                captured["code"] = params["code"][0]
                body = b"<html><body><h2>Autorizado! Pode fechar esta janela.</h2></body></html>"
            elif "error" in params:
                captured["error"] = params["error"][0]
                body = "<html><body><h2>Erro na autorizacao. Tente novamente.</h2></body></html>".encode()
            else:
                body = b"<html><body><h2>Aguardando...</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            event.set()

        def log_message(self, *args: Any) -> None:  # silencia logs do servidor
            pass

    server = http.server.HTTPServer(("", OAUTH_PORT), _Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    event.wait(timeout=120)
    server.server_close()

    if "error" in captured:
        raise RuntimeError(f"Google retornou erro OAuth: {captured['error']}")
    if "code" not in captured:
        raise RuntimeError("Timeout aguardando autorização OAuth (120s)")
    return captured["code"]


def _exchange_code_for_token(code: str) -> dict[str, Any]:
    """Troca o código de autorização por tokens OAuth2."""
    payload = urllib.parse.urlencode(
        {
            "code": code.strip(),
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "redirect_uri": OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        raise RuntimeError(f"Falha ao trocar código: {exc.code} — {body}") from exc


def _build_credentials(token_data: dict[str, Any]) -> Any:
    """Constrói objeto Credentials do google-auth."""
    from google.oauth2.credentials import Credentials  # type: ignore[import]
    return Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=OAUTH_CLIENT_ID,
        client_secret=OAUTH_CLIENT_SECRET,
        scopes=[OAUTH_SCOPE],
    )


def ensure_valid_token() -> dict[str, Any]:
    """
    Garante que existe um token válido para antonio.carneiro.

    Se não existir, conduz o fluxo OAuth interativo (gera URL + aguarda código).
    """
    if TOKEN_FILE.exists():
        data = json.loads(TOKEN_FILE.read_text())
        logger.info("Token existente carregado de %s", TOKEN_FILE)
        return data

    print("\n" + "─" * 70)
    print("  AUTORIZAÇÃO NECESSÁRIA — Google Drive de antonio.carneiro")
    print("─" * 70)
    url = _build_auth_url()
    print(
        f"\n  Para migrar os arquivos, antonio.carneiro precisa autorizar\n"
        f"  o acesso. Abrindo navegador com a conta {TARGET_GDRIVE_USER}...\n"
    )
    print(f"  Se o navegador não abrir automaticamente, acesse:\n  {url}\n")
    print(f"  Aguardando callback em http://localhost:{OAUTH_PORT} ...", flush=True)
    webbrowser.open(url)

    code = _wait_for_oauth_code()

    print("\n  Código recebido! Trocando por tokens...", end=" ")
    token_data = _exchange_code_for_token(code)
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))
    print("OK ✓")
    logger.info("Token salvo em %s", TOKEN_FILE)
    return token_data


def build_drive_service() -> Any:
    """Constrói o serviço Google Drive API v3."""
    from googleapiclient.discovery import build  # type: ignore[import]
    token_data = ensure_valid_token()
    creds = _build_credentials(token_data)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ─────────────────────────────────────────────────────────────────────────────
# Listagem de arquivos do Drive
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DriveFile:
    """Representação de um arquivo no Google Drive."""

    id: str
    name: str
    mime_type: str
    size_bytes: int
    modified_time: str
    parents: list[str]


def list_all_files(service: Any) -> list[DriveFile]:
    """Lista todos os arquivos não-excluídos do Drive (excluindo pastas)."""
    files: list[DriveFile] = []
    page_token: str | None = None

    with tqdm(
        desc="  Inventariando Drive",
        unit=" arq",
        bar_format="{l_bar}{bar}| {n_fmt} arqs [{elapsed}]",
        dynamic_ncols=True,
    ) as pbar:
        while True:
            resp = (
                service.files()
                .list(
                    q="trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                    spaces="drive",
                    fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,parents)",
                    pageSize=200,
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                files.append(
                    DriveFile(
                        id=f["id"],
                        name=f["name"],
                        mime_type=f.get("mimeType", ""),
                        size_bytes=int(f.get("size", 0)),
                        modified_time=f.get("modifiedTime", ""),
                        parents=f.get("parents", []),
                    )
                )
                pbar.update(1)
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    return files


def _export_mime_ext(mime_type: str) -> tuple[str, str]:
    """Retorna (mime_export, extensão) para tipos Google Docs."""
    mapping = {
        "application/vnd.google-apps.document": ("text/plain", ".txt"),
        "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
        "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
        "application/vnd.google-apps.drawing": ("image/svg+xml", ".svg"),
        "application/vnd.google-apps.script": ("application/vnd.google-apps.script+json", ".json"),
    }
    return mapping.get(mime_type, ("", ""))


def download_file(service: Any, f: DriveFile) -> bytes | None:
    """Baixa arquivo do Drive (com exportação automática para Google Docs)."""
    from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import]
    export_mime, _ = _export_mime_ext(f.mime_type)
    fh = BytesIO()
    try:
        if export_mime:
            req = service.files().export(fileId=f.id, mimeType=export_mime)
        else:
            req = service.files().get_media(fileId=f.id)
        dldr = MediaIoBaseDownload(fh, req, chunksize=4 * 1024 * 1024)
        done = False
        while not done:
            _, done = dldr.next_chunk()
        return fh.getvalue()
    except Exception as exc:
        logger.warning("Download falhou: %s — %s", f.name, exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# WebDAV Nextcloud
# ─────────────────────────────────────────────────────────────────────────────


def _auth_header() -> str:
    """Retorna header de autenticação Basic para o admin do Nextcloud."""
    cred = base64.b64encode(f"{NEXTCLOUD_ADMIN_USER}:{NEXTCLOUD_ADMIN_PASS}".encode()).decode()
    return f"Basic {cred}"


def _webdav(method: str, path: str, data: bytes | None = None) -> int:
    """Executa requisição WebDAV no Nextcloud."""
    encoded = "/".join(urllib.parse.quote(s, safe="@") for s in path.split("/") if s)
    url = f"{NEXTCLOUD_URL}/remote.php/dav/files/{encoded}"
    headers: dict[str, str] = {"Authorization": _auth_header()}
    if data is not None:
        headers["Content-Length"] = str(len(data))
    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError:
        return 599


def mkdirs(remote_path: str) -> None:
    """Cria diretório e todos os ancestrais no Nextcloud."""
    parts = [p for p in remote_path.split("/") if p]
    acc: list[str] = []
    for part in parts:
        acc.append(part)
        code = _webdav("MKCOL", "/".join(acc))
        if code not in (201, 301, 405):
            logger.debug("MKCOL /%s → %d", "/".join(acc), code)


def put_file(path: str, content: bytes) -> int:
    """Faz upload de arquivo ao Nextcloud via WebDAV PUT."""
    return _webdav("PUT", path, data=content)


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses de relatório
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class FileResult:
    """Resultado de migração de um arquivo individual."""

    id: str
    name: str
    remote_path: str
    size_bytes: int
    status: str  # uploaded | skipped | failed | dry_run
    error: str = ""
    sha256: str = ""


@dataclass
class Report:
    """Relatório completo de migração."""

    started_at: str = ""
    finished_at: str = ""
    dry_run: bool = False
    total_found: int = 0
    total_bytes: int = 0
    uploaded: int = 0
    uploaded_bytes: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[FileResult] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Orquestração
# ─────────────────────────────────────────────────────────────────────────────


def run(dry_run: bool = False) -> Report:
    """
    Executa o fluxo completo de migração GDrive → Nextcloud.

    Args:
        dry_run: Se True, somente inventaria — sem downloads ou uploads.

    Returns:
        Relatório detalhado da execução.
    """
    report = Report(
        started_at=datetime.now(timezone.utc).isoformat(),
        dry_run=dry_run,
    )

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print("╔" + "═" * 68 + "╗")
    print("║{:^68}║".format("MIGRAÇÃO GOOGLE DRIVE → NEXTCLOUD"))
    print("║{:^68}║".format(f"Usuário: {TARGET_GDRIVE_USER}"))
    print("║{:^68}║".format(f"Destino: {NEXTCLOUD_URL}/{NC_REMOTE_DIR}/"))
    if dry_run:
        print("║{:^68}║".format("⚠  MODO DRY-RUN — sem uploads"))
    print("╚" + "═" * 68 + "╝")

    # ── Conectar ao Drive ─────────────────────────────────────────────────────
    print("\n[1/4] Conectando ao Google Drive...")
    try:
        service = build_drive_service()
        logger.info("Serviço Drive construído com sucesso")
    except Exception as exc:
        logger.error("Falha ao conectar ao Drive: %s", exc)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    # ── Inventariar arquivos ──────────────────────────────────────────────────
    print("\n[2/4] Inventariando arquivos...")
    files = list_all_files(service)
    total_bytes = sum(f.size_bytes for f in files)
    report.total_found = len(files)
    report.total_bytes = total_bytes

    if not files:
        print("\n⚠  Nenhum arquivo encontrado no Drive de", TARGET_GDRIVE_USER)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        return report

    print(f"\n  ✓ Encontrados: {len(files)} arquivos ({total_bytes / 1024 / 1024:.1f} MB)\n")

    # ── Salvar baseline ───────────────────────────────────────────────────────
    print("[3/4] Salvando baseline...")
    BASELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "user": TARGET_GDRIVE_USER,
        "total_files": len(files),
        "total_bytes": total_bytes,
        "files": [
            {
                "id": f.id,
                "name": f.name,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
                "modified_time": f.modified_time,
            }
            for f in files
        ],
    }
    BASELINE_JSON.write_text(json.dumps(baseline, indent=2, ensure_ascii=False))
    print(f"  ✓ Baseline salvo: {BASELINE_JSON}")

    # ── Migrar ────────────────────────────────────────────────────────────────
    print(f"\n[4/4] {'Simulando migração' if dry_run else 'Migrando para Nextcloud'}...")

    if not dry_run:
        mkdirs(f"{NC_TARGET_USER}/{NC_REMOTE_DIR}")

    with tqdm(
        total=total_bytes,
        desc="  Progresso",
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        colour="green",
        dynamic_ncols=True,
    ) as pbar:
        for f in files:
            _, ext = _export_mime_ext(f.mime_type)
            name = f.name if not ext or f.name.endswith(ext) else f"{f.name}{ext}"
            remote = f"{NC_TARGET_USER}/{NC_REMOTE_DIR}/{name}"

            pbar.set_description(f"  ↑ {f.name[:38]:<38}")

            if dry_run:
                result = FileResult(
                    id=f.id, name=f.name, remote_path=remote,
                    size_bytes=f.size_bytes, status="dry_run"
                )
                report.skipped += 1
            else:
                content = download_file(service, f)
                if content is None:
                    result = FileResult(
                        id=f.id, name=f.name, remote_path=remote,
                        size_bytes=f.size_bytes, status="failed",
                        error="Download falhou",
                    )
                    report.failed += 1
                else:
                    sha = hashlib.sha256(content).hexdigest()
                    code = put_file(remote, content)
                    if code in (200, 201, 204):
                        result = FileResult(
                            id=f.id, name=f.name, remote_path=remote,
                            size_bytes=f.size_bytes, status="uploaded", sha256=sha,
                        )
                        report.uploaded += 1
                        report.uploaded_bytes += f.size_bytes
                    else:
                        result = FileResult(
                            id=f.id, name=f.name, remote_path=remote,
                            size_bytes=f.size_bytes, status="failed",
                            error=f"PUT retornou HTTP {code}",
                        )
                        report.failed += 1

            report.results.append(result)
            pbar.update(f.size_bytes or 1)

    # ── Relatório final ───────────────────────────────────────────────────────
    report.finished_at = datetime.now(timezone.utc).isoformat()

    print()
    print("╔" + "═" * 68 + "╗")
    print("║{:^68}║".format("RELATÓRIO DE MIGRAÇÃO"))
    print("╠" + "═" * 68 + "╣")
    print(f"║  Usuário:          {TARGET_GDRIVE_USER:<48}║")
    print(f"║  Total encontrado: {len(files)} arquivos ({total_bytes / 1024 / 1024:.1f} MB){' ' * 20}║"[:71] + "║")
    if dry_run:
        print(f"║  Dry-run:          {report.skipped} arquivos analisados{' ' * 30}║"[:71] + "║")
    else:
        icon = "✓" if report.failed == 0 else "⚠"
        print(f"║  {icon} Enviados:      {report.uploaded} ({report.uploaded_bytes / 1024 / 1024:.1f} MB){' ' * 25}║"[:71] + "║")
        print(f"║  Pulados:          {report.skipped:<48}║")
        print(f"║  Falhas:           {report.failed:<48}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Baseline: {str(BASELINE_JSON):<57}║")
    print(f"║  Relatório: {str(REPORT_JSON):<56}║")
    print("╚" + "═" * 68 + "╝")
    print()

    if not dry_run and report.failed > 0:
        print("  Arquivos com falha:")
        for r in report.results:
            if r.status == "failed":
                print(f"    • {r.name}: {r.error}")

    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False))

    return report


# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada da migração interativa."""
    parser = argparse.ArgumentParser(
        description="Migra Drive de antonio.carneiro para Nextcloud (com autenticação interativa)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Somente inventaria, sem uploads")
    args = parser.parse_args()

    try:
        report = run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário.")
        sys.exit(130)

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
