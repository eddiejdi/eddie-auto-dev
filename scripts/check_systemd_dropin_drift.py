#!/usr/bin/env python3
"""Compara os drop-ins systemd versionados neste repo com os instalados no host.

O deploy do trading versionava `systemd/**/*.service.d/*.conf` mas nunca os
instalava: repo e produção podiam divergir para sempre, em silêncio (foi o caso
do `OLLAMA_PLAN_MODEL=gemma3-fast:gpu1` corrigido no PR #246 e que continuou
errado em produção). Este verificador fecha o buraco nos dois sentidos:

  * repo → host: arquivo ausente ou com conteúdo diferente = drift (falha).
  * host → repo: arquivo que só existe no host = configuração viva não
    versionada (aviso por padrão, falha com ``--fail-on-host-only``).

O escopo vem de ``systemd/managed_dropins.conf`` — a mesma lista usada pelo
``scripts/deploy_btc_trading_profiles.sh``.

Uso típico:
    scripts/check_systemd_dropin_drift.py --strict          # pós-deploy / CI
    scripts/check_systemd_dropin_drift.py --json            # automação
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_SYSTEM_DIR = Path("/etc/systemd/system")
MANIFEST_RELATIVE = Path("systemd/managed_dropins.conf")

# Drop-ins com placeholder NÃO são instaláveis: sobrescrever o host apagaria
# segredos vivos (ex.: crypto-agent@.service.d/common.conf traz
# SECRETS_AGENT_API_KEY=<from_bitwarden>). São ignorados pelo instalador e pelo
# comparador — divergir deles é esperado, não drift.
REDACTION_PATTERNS = (
    re.compile(r"<from_bitwarden>"),
    re.compile(r"<your_[a-z0-9_]+>", re.IGNORECASE),
    re.compile(r"\bCHANGEME\b"),
    re.compile(r"\bREPLACE_ME\b"),
    re.compile(r"<REDACTED>", re.IGNORECASE),
    re.compile(r"<PLACEHOLDER>", re.IGNORECASE),
)

# Sufixos que o systemd ignora e que o host acumula (backups do próprio deploy,
# resíduo de pacote). Não contam como "host-only".
IGNORED_HOST_SUFFIX = re.compile(
    r"(\.bak(\.[0-9_]+)?|\.bak-[A-Za-z0-9_.-]+|\.disabled(\.[0-9_]+)?"
    r"|\.dpkg-(old|new|dist)|\.rpmsave|\.rpmnew|~)$"
)

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_DIFFERS = "differs"
STATUS_REDACTED = "redacted"
STATUS_HOST_ONLY = "host_only"

DRIFT_STATUSES = (STATUS_MISSING, STATUS_DIFFERS)


def is_redacted(text: str) -> bool:
    """True quando o .conf do repo é um template com segredo placeholder."""
    return any(pattern.search(text) for pattern in REDACTION_PATTERNS)


def read_manifest(manifest_path: Path) -> list[str]:
    """Lê os diretórios gerenciados (uma entrada por linha, `#` comenta)."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifesto não encontrado: {manifest_path}")

    entries: list[str] = []
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("/") or ".." in line:
            raise ValueError(f"Entrada inválida no manifesto: {raw!r}")
        entries.append(line)
    return entries


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _host_conf_files(host_dir: Path) -> Iterable[Path]:
    if not host_dir.is_dir():
        return []
    return sorted(
        p
        for p in host_dir.iterdir()
        if p.is_file()
        and p.suffix == ".conf"
        and not IGNORED_HOST_SUFFIX.search(p.name)
    )


def compare(repo_root: Path, system_dir: Path, manifest_path: Path | None = None) -> dict:
    """Compara cada .conf gerenciado do repo com o correspondente no host."""
    manifest_path = manifest_path or (repo_root / MANIFEST_RELATIVE)
    managed_dirs = read_manifest(manifest_path)

    findings: list[dict] = []
    for rel_dir in managed_dirs:
        repo_dir = repo_root / "systemd" / rel_dir
        host_dir = system_dir / rel_dir

        if not repo_dir.is_dir():
            raise FileNotFoundError(
                f"Diretório do manifesto não existe no repo: {repo_dir}"
            )

        repo_files = sorted(p for p in repo_dir.iterdir() if p.suffix == ".conf")
        repo_names = {p.name for p in repo_files}

        for repo_file in repo_files:
            repo_text = _read_text(repo_file)
            host_file = host_dir / repo_file.name
            rel = f"{rel_dir}/{repo_file.name}"

            if is_redacted(repo_text):
                findings.append(
                    {
                        "status": STATUS_REDACTED,
                        "path": rel,
                        "detail": "template com placeholder — não instalado nem comparado",
                    }
                )
                continue

            if not host_file.is_file():
                findings.append(
                    {
                        "status": STATUS_MISSING,
                        "path": rel,
                        "detail": f"ausente no host ({host_file})",
                    }
                )
                continue

            if _read_text(host_file) != repo_text:
                findings.append(
                    {
                        "status": STATUS_DIFFERS,
                        "path": rel,
                        "detail": f"conteúdo diverge de {host_file}",
                    }
                )
            else:
                findings.append({"status": STATUS_OK, "path": rel, "detail": ""})

        for host_file in _host_conf_files(host_dir):
            if host_file.name in repo_names:
                continue
            findings.append(
                {
                    "status": STATUS_HOST_ONLY,
                    "path": f"{rel_dir}/{host_file.name}",
                    "detail": f"existe só no host ({host_file}) — versionar ou documentar",
                }
            )

    summary = {status: 0 for status in
               (STATUS_OK, STATUS_MISSING, STATUS_DIFFERS, STATUS_REDACTED, STATUS_HOST_ONLY)}
    for finding in findings:
        summary[finding["status"]] += 1

    return {
        "system_dir": str(system_dir),
        "managed_dirs": managed_dirs,
        "findings": findings,
        "summary": summary,
        "drift": sum(summary[s] for s in DRIFT_STATUSES),
        "host_only": summary[STATUS_HOST_ONLY],
    }


_ICONS = {
    STATUS_OK: "✅",
    STATUS_MISSING: "❌",
    STATUS_DIFFERS: "❌",
    STATUS_REDACTED: "🔒",
    STATUS_HOST_ONLY: "⚠️ ",
}


def render(report: dict, verbose: bool) -> str:
    lines = [f"🔎 Paridade de drop-ins systemd — host: {report['system_dir']}"]
    for finding in report["findings"]:
        if finding["status"] == STATUS_OK and not verbose:
            continue
        icon = _ICONS[finding["status"]]
        detail = f" — {finding['detail']}" if finding["detail"] else ""
        lines.append(f"  {icon} [{finding['status']}] {finding['path']}{detail}")

    summary = report["summary"]
    lines.append(
        "  Σ ok={ok} missing={missing} differs={differs} "
        "redacted={redacted} host_only={host_only}".format(**summary)
    )
    if report["host_only"]:
        lines.append(
            "  ↳ host_only: rode scripts/export_host_systemd_dropins.sh no homelab "
            "para versioná-los (ver docs/systemd/DROPIN_DEPLOY_PARITY.md)"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Raiz do repositório (default: pai de scripts/)",
    )
    parser.add_argument(
        "--system-dir",
        type=Path,
        default=DEFAULT_SYSTEM_DIR,
        help=f"Diretório de units do host (default: {DEFAULT_SYSTEM_DIR})",
    )
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 quando houver drift (missing/differs)",
    )
    parser.add_argument(
        "--fail-on-host-only",
        action="store_true",
        help="Exit 1 também quando houver .conf só no host",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Lista também os arquivos ok"
    )
    args = parser.parse_args(argv)

    try:
        report = compare(args.repo_root, args.system_dir)
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json
          else render(report, args.verbose))

    if args.strict and report["drift"]:
        print(
            f"❌ Drift de drop-ins systemd: {report['drift']} arquivo(s) fora de paridade "
            "— rode scripts/deploy_btc_trading_profiles.sh (ou o workflow "
            "Deploy BTC Trading Profiles) para reinstalar.",
            file=sys.stderr,
        )
        return 1
    if args.fail_on_host_only and report["host_only"]:
        print(
            f"❌ {report['host_only']} drop-in(s) existem só no host e não estão no git.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
