#!/usr/bin/env python3
"""Monitor de progresso da migração rclone — Google Drive Pessoal → Nextcloud.

Conecta via SSH ao homelab e monitora o log do rclone em tempo real,
exibindo uma barra de progresso no terminal.

Uso:
    python3 tools/rclone_progress_pessoal.py
    python3 tools/rclone_progress_pessoal.py --interval 10
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

# ── Constantes ──────────────────────────────────────────────────────────
TOTAL_SIZE_BYTES: int = 50_264_498_380  # ~46.8 GiB (estimado de rclone size)
TOTAL_FILES: int = 10_126
REFRESH_INTERVAL: float = 5.0
DEFAULT_LOG_FILE: str = "/tmp/rclone-pessoal.log"
DEFAULT_DEST_DIR: str = "/mnt/raid1/gdrive-pessoal-temp/"

BAR_CHAR_FILL: str = "█"
BAR_CHAR_EMPTY: str = "░"
COLOR_GREEN: str = "\033[92m"
COLOR_YELLOW: str = "\033[93m"
COLOR_RED: str = "\033[91m"
COLOR_CYAN: str = "\033[96m"
COLOR_RESET: str = "\033[0m"
COLOR_BOLD: str = "\033[1m"
COLOR_DIM: str = "\033[2m"


def parse_args() -> argparse.Namespace:
    """Parseia argumentos da CLI."""
    parser = argparse.ArgumentParser(
        description="Monitor de progresso - Google Drive Pessoal → Nextcloud"
    )
    parser.add_argument("--host", default="192.168.15.2", help="Host SSH")
    parser.add_argument("--user", default="homelab", help="Usuário SSH")
    parser.add_argument(
        "--log-file", default=DEFAULT_LOG_FILE,
        help="Caminho do log no host remoto",
    )
    parser.add_argument(
        "--dest-dir", default=DEFAULT_DEST_DIR,
        help="Diretório destino no host remoto",
    )
    parser.add_argument(
        "--interval", type=float, default=REFRESH_INTERVAL,
        help="Intervalo de atualização em segundos",
    )
    return parser.parse_args()


def ssh_cmd(host: str, user: str, cmd: str, timeout: int = 15) -> str:
    """Executa comando via SSH e retorna stdout."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             f"{user}@{host}", cmd],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return ""


def parse_rclone_stats(log_output: str) -> dict[str, str | int | float | list]:
    """Extrai métricas do bloco de stats do rclone."""
    stats: dict[str, str | int | float | list] = {
        "bytes_transferred": 0,
        "bytes_total": TOTAL_SIZE_BYTES,
        "pct": 0.0,
        "speed": "0 B/s",
        "eta": "calculando...",
        "files_done": 0,
        "files_total": TOTAL_FILES,
        "errors": 0,
        "checks": 0,
        "elapsed": "0s",
        "current_files": [],
    }

    if not log_output:
        return stats

    # Transferred bytes: "Transferred:   502.751 MiB / 46.792 GiB, 1%, 2.380 MiB/s, ETA 5h32m2s"
    transferred_re = re.compile(
        r"Transferred:\s+([\d.]+)\s+(\w+)\s*/\s*([\d.]+)\s+(\w+),\s*([\d.]+)%,\s*(.+?),\s*ETA\s+(.+)"
    )
    # Files: "Transferred:   115 / 10126, 1%"
    files_re = re.compile(r"Transferred:\s+(\d+)\s*/\s*(\d+),\s*(\d+)%")
    errors_re = re.compile(r"Errors:\s+(\d+)")
    checks_re = re.compile(r"Checks:\s+(\d+)\s*/\s*\d+")
    elapsed_re = re.compile(r"Elapsed time:\s+(.+)")
    # Transferring: " * Meet...mp4: 7% /2.627Gi, 875Ki/s, 48m43s"
    transferring_re = re.compile(
        r"\*\s+(.+?):\s+(?:(\d+)%\s*/\s*([\d.]+\w+)|transferring)"
    )

    for line in log_output.split("\n"):
        line = line.strip()

        m = transferred_re.search(line)
        if m:
            stats["bytes_transferred"] = _to_bytes(float(m.group(1)), m.group(2))
            stats["bytes_total"] = _to_bytes(float(m.group(3)), m.group(4))
            stats["pct"] = float(m.group(5))
            stats["speed"] = m.group(6).strip()
            stats["eta"] = m.group(7).strip()
            continue

        m = files_re.search(line)
        if m and not any(u in line for u in ["KiB", "MiB", "GiB", "TiB", "Byte"]):
            stats["files_done"] = int(m.group(1))
            stats["files_total"] = int(m.group(2))
            continue

        m = errors_re.search(line)
        if m:
            stats["errors"] = int(m.group(1))
            continue

        m = checks_re.search(line)
        if m:
            stats["checks"] = int(m.group(1))
            continue

        m = elapsed_re.search(line)
        if m:
            stats["elapsed"] = m.group(1).strip()
            continue

        m = transferring_re.search(line)
        if m:
            name = m.group(1).strip()
            if m.group(2):
                pct_file = m.group(2)
                size_file = m.group(3)
                stats["current_files"].append(f"{name} ({pct_file}% de {size_file})")
            else:
                stats["current_files"].append(name)

    return stats


def _to_bytes(value: float, unit: str) -> int:
    """Converte valor com unidade para bytes."""
    multipliers = {
        "Byte": 1, "Bytes": 1,
        "KiB": 1024, "kib": 1024,
        "MiB": 1024**2, "mib": 1024**2,
        "GiB": 1024**3, "gib": 1024**3,
        "Gi": 1024**3,
        "TiB": 1024**4, "tib": 1024**4,
    }
    return int(value * multipliers.get(unit, 1))


def _format_bytes(b: int | float) -> str:
    """Formata bytes em unidade legível."""
    if b < 1024:
        return f"{b} B"
    if b < 1024**2:
        return f"{b / 1024:.1f} KiB"
    if b < 1024**3:
        return f"{b / 1024**2:.1f} MiB"
    return f"{b / 1024**3:.2f} GiB"


def render_progress_bar(pct: float, width: int = 40, errors: int = 0) -> str:
    """Renderiza barra de progresso colorida."""
    filled = int(width * min(pct, 100) / 100)
    empty = width - filled

    if errors > 0:
        color = COLOR_YELLOW
    elif pct >= 100:
        color = COLOR_GREEN
    else:
        color = COLOR_CYAN

    bar = f"{color}{BAR_CHAR_FILL * filled}{COLOR_RESET}{BAR_CHAR_EMPTY * empty}"
    return f"[{bar}] {COLOR_BOLD}{pct:5.1f}%{COLOR_RESET}"


def render_dashboard(
    stats: dict[str, str | int | float | list],
    real_bytes: int = 0,
    real_files: int = 0,
) -> str:
    """Renderiza dashboard completo."""
    term_width = min(shutil.get_terminal_size().columns, 100)
    pct = float(stats.get("pct", 0))
    errors = int(stats.get("errors", 0))
    bar_width = min(50, term_width - 20)

    # Se log não tem stats mas temos du, calcular pct
    if pct == 0 and real_bytes > 0:
        pct = min((real_bytes / TOTAL_SIZE_BYTES) * 100, 100.0)
        stats["bytes_transferred"] = real_bytes
        stats["pct"] = pct

    now = datetime.now().strftime("%H:%M:%S")
    sep = "═" * (term_width - 2)

    lines: list[str] = []
    lines.append("")
    lines.append(f"{COLOR_BOLD}╔{sep}╗{COLOR_RESET}")

    title = " 📦 Google Drive Pessoal → Nextcloud "
    lines.append(f"{COLOR_BOLD}║{title:^{term_width - 2}}║{COLOR_RESET}")
    subtitle = f" edenilson.teixeira → edenilson.paschoa@rpa4all.com "
    lines.append(f"{COLOR_BOLD}║{COLOR_DIM}{subtitle:^{term_width - 2}}{COLOR_RESET}{COLOR_BOLD}║{COLOR_RESET}")

    lines.append(f"{COLOR_BOLD}╠{sep}╣{COLOR_RESET}")

    # Progress bar
    bar = render_progress_bar(pct, bar_width, errors)
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET} {bar}")
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}")

    # Stats do log
    transferred = _format_bytes(int(stats.get("bytes_transferred", 0)))
    total = _format_bytes(int(stats.get("bytes_total", TOTAL_SIZE_BYTES)))
    speed = stats.get("speed", "—")
    eta = stats.get("eta", "calculando...")
    files_done = int(stats.get("files_done", 0))
    files_total = int(stats.get("files_total", TOTAL_FILES))
    elapsed = stats.get("elapsed", "—")
    checks = int(stats.get("checks", 0))

    # Usar contagens reais do disco se disponíveis
    if real_files > files_done:
        files_done = real_files
    if real_bytes > int(stats.get("bytes_transferred", 0)):
        transferred = _format_bytes(real_bytes)

    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  📊 Dados:      {transferred} / {total}")
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  📁 Arquivos:   {files_done:,} / {files_total:,}")
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  🚀 Velocidade: {speed}")
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  ⏱️  Decorrido:  {elapsed}")
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  ⏳ ETA:        {eta}")
    if checks > 0:
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  🔍 Checks:     {checks:,}")

    if errors > 0:
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  {COLOR_RED}⚠️  Erros: {errors}{COLOR_RESET}")
    else:
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  {COLOR_GREEN}✅ Sem erros{COLOR_RESET}")

    # Arquivos em transferência
    current_files = stats.get("current_files", [])
    if current_files:
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}")
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  📥 Transferindo agora:")
        for cf in current_files[:4]:
            max_name = term_width - 12
            name = cf if len(cf) < max_name else f"…{cf[-(max_name - 1):]}"
            lines.append(f"{COLOR_BOLD}║{COLOR_RESET}     • {COLOR_DIM}{name}{COLOR_RESET}")

    lines.append(f"{COLOR_BOLD}╠{sep}╣{COLOR_RESET}")
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  {COLOR_DIM}Atualizado: {now}  |  "
        f"Ctrl+C para sair (download continua em background){COLOR_RESET}"
    )
    lines.append(f"{COLOR_BOLD}╚{sep}╝{COLOR_RESET}")

    return "\n".join(lines)


def is_rclone_running(host: str, user: str) -> bool:
    """Verifica se rclone ainda está rodando."""
    output = ssh_cmd(host, user, "pgrep -f 'rclone copy' || echo 'NOT_RUNNING'")
    return "NOT_RUNNING" not in output


def main() -> None:
    """Loop principal do monitor."""
    args = parse_args()

    print(f"\n{COLOR_CYAN}Conectando ao homelab ({args.host})...{COLOR_RESET}")

    if not is_rclone_running(args.host, args.user):
        print(f"{COLOR_RED}⚠️  rclone não está rodando no homelab!{COLOR_RESET}")
        # Mostrar último estado mesmo assim
        log_tail = ssh_cmd(args.host, args.user, f"tail -25 {args.log_file}")
        if log_tail:
            stats = parse_rclone_stats(log_tail)
            du_out = ssh_cmd(
                args.host, args.user,
                f"du -sb {args.dest_dir} 2>/dev/null"
            )
            real_bytes = int(du_out.split()[0]) if du_out else 0
            files_out = ssh_cmd(
                args.host, args.user,
                f"find {args.dest_dir} -type f 2>/dev/null | wc -l"
            )
            real_files = int(files_out) if files_out else 0
            print(render_dashboard(stats, real_bytes, real_files))
            print(f"\n{COLOR_YELLOW}Download finalizado ou parou.{COLOR_RESET}")
        sys.exit(1)

    try:
        while True:
            # Buscar stats do log
            log_tail = ssh_cmd(
                args.host, args.user,
                f"tail -25 {args.log_file} 2>/dev/null"
            )
            stats = parse_rclone_stats(log_tail)

            # Tamanho real no disco
            du_cmd = f"du -sb {args.dest_dir} 2>/dev/null"
            files_cmd = f"find {args.dest_dir} -type f 2>/dev/null | wc -l"
            combined = ssh_cmd(
                args.host, args.user,
                f'{du_cmd} && echo "---FCOUNT---" && {files_cmd}',
                timeout=30,
            )

            real_bytes = 0
            real_files = 0
            if combined:
                parts = combined.split("---FCOUNT---")
                if len(parts) >= 1:
                    try:
                        real_bytes = int(parts[0].strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                if len(parts) >= 2:
                    try:
                        real_files = int(parts[1].strip())
                    except (ValueError, IndexError):
                        pass

            # Limpar tela e renderizar
            print("\033[2J\033[H", end="")
            print(render_dashboard(stats, real_bytes, real_files))

            # Verificar se rclone ainda roda
            if not is_rclone_running(args.host, args.user):
                pct = float(stats.get("pct", 0))
                if real_bytes > 0:
                    pct = (real_bytes / TOTAL_SIZE_BYTES) * 100
                if pct >= 95:
                    print(f"\n{COLOR_GREEN}{COLOR_BOLD}✅ Migração concluída!{COLOR_RESET}")
                else:
                    print(f"\n{COLOR_YELLOW}⚠️  rclone parou ({pct:.1f}%). Verifique erros.{COLOR_RESET}")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n{COLOR_CYAN}Monitor encerrado. Download continua em background.{COLOR_RESET}")
        print(f"  Re-executar: python3 tools/rclone_progress_pessoal.py")
        print(f"  Ver log:     ssh {args.user}@{args.host} 'tail -f {args.log_file}'")


if __name__ == "__main__":
    main()
