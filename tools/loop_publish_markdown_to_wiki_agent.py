#!/usr/bin/env python3
"""Envia arquivos Markdown do repositório para o WikiAgent em loop contínuo."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_URL = "http://127.0.0.1:8503"
DEFAULT_SLEEP_SECONDS = 10.0
DEFAULT_WIKI_LOCALE = "pt"


def load_infer_path() -> Callable[[str], str]:
    """Reusa a heurística já existente do sync para definir o wiki_path."""
    module_path = REPO_ROOT / "tools" / "hooks" / "wiki_sync.py"
    spec = importlib.util.spec_from_file_location("wiki_sync", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    infer_path = getattr(module, "infer_path", None)
    if infer_path is None:
        raise RuntimeError(f"infer_path não encontrado em {module_path}")
    return infer_path


def list_markdown_files() -> list[str]:
    """Lista todos os .md versionados/localizados no projeto em ordem estável."""
    try:
        result = subprocess.run(
            ["rg", "--files", "-g", "*.md"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except FileNotFoundError:
        files = [
            str(path.relative_to(REPO_ROOT))
            for path in sorted(REPO_ROOT.rglob("*.md"))
            if path.is_file()
        ]
    return sorted(files)


def extract_title(markdown_path: Path, content: str) -> str:
    """Usa o primeiro H1 como topic; fallback para o nome do arquivo."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return markdown_path.stem.replace("_", " ").replace("-", " ").strip()


def build_tags(relative_path: str) -> list[str]:
    parts = Path(relative_path).parts
    tags = ["auto-sync", "markdown"]
    if parts:
        tags.append(parts[0].lower())
    return tags


def post_json(url: str, payload: dict[str, object], timeout: int = 120) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def healthcheck(agent_url: str) -> None:
    url = f"{agent_url.rstrip('/')}/wiki/health"
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"WikiAgent healthcheck retornou HTTP {response.status}")


def publish_file(
    relative_path: str,
    agent_url: str,
    infer_path: Callable[[str], str],
    dry_run: bool,
    wiki_locale: str,
) -> None:
    full_path = REPO_ROOT / relative_path
    content = full_path.read_text(encoding="utf-8")
    topic = extract_title(full_path, content)
    wiki_path = infer_path(relative_path)
    payload = {
        "topic": topic,
        "raw_text": content,
        "wiki_path": wiki_path,
        "tags": build_tags(relative_path),
        "locale": wiki_locale,
    }

    if dry_run:
        print(
            f"DRY-RUN {relative_path} -> {wiki_path} | "
            f"topic={topic} | locale={wiki_locale}"
        )
        return

    url = f"{agent_url.rstrip('/')}/wiki/publish"
    status, body = post_json(url, payload)
    print(f"OK {relative_path} -> {wiki_path} | HTTP {status} | {body[:200]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia todos os .md do projeto para o WikiAgent, um por vez, em loop."
    )
    parser.add_argument(
        "--agent-url",
        default=DEFAULT_AGENT_URL,
        help=f"Base URL do WikiAgent. Padrão: {DEFAULT_AGENT_URL}",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help=f"Intervalo entre envios. Padrão: {DEFAULT_SLEEP_SECONDS}",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa apenas um ciclo completo e encerra.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Monta os payloads e imprime os destinos sem publicar.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limita a quantidade de arquivos por ciclo. 0 = sem limite.",
    )
    parser.add_argument(
        "--wiki-locale",
        default=DEFAULT_WIKI_LOCALE,
        help=f"Locale enviado ao WikiAgent. Padrão: {DEFAULT_WIKI_LOCALE}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    infer_path = load_infer_path()

    if not args.dry_run:
        try:
            healthcheck(args.agent_url)
        except Exception as exc:
            print(f"ERRO healthcheck WikiAgent: {exc}", file=sys.stderr)
            return 1

    cycle = 0
    try:
        while True:
            cycle += 1
            markdown_files = list_markdown_files()
            if args.limit > 0:
                markdown_files = markdown_files[: args.limit]
            print(f"Iniciando ciclo {cycle} com {len(markdown_files)} arquivos .md")

            for index, relative_path in enumerate(markdown_files, start=1):
                print(f"[{index}/{len(markdown_files)}] Processando {relative_path}")
                try:
                    publish_file(
                        relative_path=relative_path,
                        agent_url=args.agent_url,
                        infer_path=infer_path,
                        dry_run=args.dry_run,
                        wiki_locale=args.wiki_locale,
                    )
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace")
                    print(
                        f"ERRO HTTP {exc.code} em {relative_path}: {body[:400]}",
                        file=sys.stderr,
                    )
                except Exception as exc:
                    print(f"ERRO em {relative_path}: {exc}", file=sys.stderr)

                time.sleep(args.sleep_seconds)

            print(f"Ciclo {cycle} concluído")
            if args.once:
                return 0
    except KeyboardInterrupt:
        print("Interrompido pelo usuário")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
