#!/usr/bin/env python3
"""Monitor de progresso da migração rclone com progress bar visual.

Conecta via SSH ao homelab e monitora o log do rclone em tempo real,
exibindo uma barra de progresso no terminal.

Uso:
    python3 tools/rclone_progress.py
    python3 tools/rclone_progress.py --log-file /tmp/rclone_migration.log
    python3 tools/rclone_progress.py --host 192.168.15.2 --user homelab
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time

# ── Constantes ──────────────────────────────────────────────────────────
TOTAL_SIZE_BYTES: int = 30_992_430_012  # ~29 GiB (de rclone size)
TOTAL_FILES: int = 357
REFRESH_INTERVAL: float = 5.0
BAR_CHAR_FILL: str = "█"
BAR_CHAR_EMPTY: str = "░"
COLOR_GREEN: str = "\033[92m"
COLOR_YELLOW: str = "\033[93m"
COLOR_RED: str = "\033[91m"
COLOR_CYAN: str = "\033[96m"
COLOR_RESET: str = "\033[0m"
COLOR_BOLD: str = "\033[1m"
CLEAR_LINE: str = "\033[K"


def parse_args() -> argparse.Namespace:
    """Parseia argumentos da CLI."""
    parser = argparse.ArgumentParser(description="Monitor de progresso rclone")
    parser.add_argument(
        "--host", default="192.168.15.2", help="Host SSH do homelab"
    )
    parser.add_argument(
        "--user", default="homelab", help="Usuário SSH"
    )
    parser.add_argument(
        "--log-file",
        default="/tmp/rclone_migration.log",
        help="Caminho do log no host remoto",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=REFRESH_INTERVAL,
        help="Intervalo de atualização em segundos",
    )
    return parser.parse_args()


def ssh_cmd(host: str, user: str, cmd: str) -> str:
    """Executa comando via SSH e retorna stdout."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
             f"{user}@{host}", cmd],
            capture_output=True, text=True, timeout=15,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return ""


def parse_rclone_stats(log_output: str) -> dict[str, str | int | float]:
    """Extrai métricas do log de stats do rclone.

    Returns:
        Dicionário com bytes_transferred, pct, speed, eta, files_done,
        files_total, errors, elapsed.
    """
    stats: dict[str, str | int | float] = {
        "bytes_transferred": 0,
        "bytes_total": TOTAL_SIZE_BYTES,
        "pct": 0.0,
        "speed": "0 B/s",
        "eta": "calculando...",
        "files_done": 0,
        "files_total": TOTAL_FILES,
        "errors": 0,
        "elapsed": "0s",
        "current_files": [],
    }

    if not log_output:
        return stats

    # Transferred bytes line: "Transferred:   1.234 GiB / 28.864 GiB, 4%, 5.0 MiB/s, ETA 1h2m"
    transferred_re = re.compile(
        r"Transferred:\s+([\d.]+)\s+(\w+)\s*/\s*([\d.]+)\s+(\w+),\s*([\d.]+)%,\s*(.+?),\s*ETA\s+(.+)"
    )
    # Files line: "Transferred:   42 / 357, 12%"
    files_re = re.compile(r"Transferred:\s+(\d+)\s*/\s*(\d+),\s*(\d+)%")
    # Errors line
    errors_re = re.compile(r"Errors:\s+(\d+)")
    # Elapsed
    elapsed_re = re.compile(r"Elapsed time:\s+(.+)")
    # Transferring files
    transferring_re = re.compile(r"\*\s+(.+?):\s+transferring")

    for line in log_output.split("\n"):
        line = line.strip()

        m = transferred_re.search(line)
        if m:
            amount = float(m.group(1))
            unit = m.group(3 - 1 + 1)  # fix: group(2)
            # Recalcular
            amount_val = float(m.group(1))
            unit_val = m.group(2)
            total_val = float(m.group(3))
            total_unit = m.group(4)
            stats["pct"] = float(m.group(5))
            stats["speed"] = m.group(6).strip()
            stats["eta"] = m.group(7).strip()
            stats["bytes_transferred"] = _to_bytes(amount_val, unit_val)
            stats["bytes_total"] = _to_bytes(total_val, total_unit)
            continue

        m = files_re.search(line)
        if m and "%" in line and "/" in line:
            # Diferenciar da linha de bytes (bytes tem unidades como GiB/MiB)
            if not any(u in line for u in ["KiB", "MiB", "GiB", "TiB", "Byte"]):
                stats["files_done"] = int(m.group(1))
                stats["files_total"] = int(m.group(2))
            continue

        m = errors_re.search(line)
        if m:
            stats["errors"] = int(m.group(1))
            continue

        m = elapsed_re.search(line)
        if m:
            stats["elapsed"] = m.group(1).strip()
            continue

        m = transferring_re.search(line)
        if m:
            stats["current_files"].append(m.group(1).strip())

    return stats


def _to_bytes(value: float, unit: str) -> int:
    """Converte valor com unidade para bytes."""
    multipliers = {
        "Byte": 1, "Bytes": 1,
        "KiB": 1024, "kib": 1024,
        "MiB": 1024**2, "mib": 1024**2,
        "GiB": 1024**3, "gib": 1024**3,
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


def render_progress_bar(
    pct: float,
    width: int = 40,
    errors: int = 0,
) -> str:
    """Renderiza barra de progresso colorida."""
    filled = int(width * pct / 100)
    empty = width - filled

    if errors > 0:
        color = COLOR_YELLOW
    elif pct >= 100:
        color = COLOR_GREEN
    else:
        color = COLOR_CYAN

    bar = f"{color}{BAR_CHAR_FILL * filled}{COLOR_RESET}{BAR_CHAR_EMPTY * empty}"
    return f"[{bar}] {COLOR_BOLD}{pct:5.1f}%{COLOR_RESET}"


def render_dashboard(stats: dict[str, str | int | float]) -> str:
    """Renderiza dashboard completo."""
    term_width = shutil.get_terminal_size().columns
    pct = float(stats.get("pct", 0))
    errors = int(stats.get("errors", 0))
    bar_width = min(50, term_width - 20)

    lines = []
    lines.append("")
    lines.append(f"{COLOR_BOLD}╔{'═' * (term_width - 2)}╗{COLOR_RESET}")
    title = " 📦 Migração Google Drive → Nextcloud (RPA4ALL) "
    pad = term_width - 2 - len(title) + len(COLOR_BOLD) + len(COLOR_RESET)
    lines.append(f"{COLOR_BOLD}║{title:^{term_width - 2}}║{COLOR_RESET}")
    lines.append(f"{COLOR_BOLD}╠{'═' * (term_width - 2)}╣{COLOR_RESET}")

    # Progress bar
    bar = render_progress_bar(pct, bar_width, errors)
    lines.append(f"{COLOR_BOLD}║{COLOR_RESET} {bar}")

    # Stats
    transferred = _format_bytes(int(stats.get("bytes_transferred", 0)))
    total = _format_bytes(int(stats.get("bytes_total", TOTAL_SIZE_BYTES)))
    speed = stats.get("speed", "0 B/s")
    eta = stats.get("eta", "calculando...")
    files_done = int(stats.get("files_done", 0))
    files_total = int(stats.get("files_total", TOTAL_FILES))
    elapsed = stats.get("elapsed", "0s")

    lines.append(f"{COLOR_BOLD}║{COLOR_RESET}")
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  📊 Dados:    {transferred} / {total}"
    )
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  📁 Arquivos: {files_done} / {files_total}"
    )
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  🚀 Velocidade: {speed}"
    )
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  ⏱️  Decorrido: {elapsed}"
    )
    lines.append(
        f"{COLOR_BOLD}║{COLOR_RESET}  ⏳ ETA:       {eta}"
    )

    if errors > 0:
        lines.append(
            f"{COLOR_BOLD}║{COLOR_RESET}  {COLOR_RED}⚠️  Erros: {errors} (retrying){COLOR_RESET}"
        )
    else:
        lines.append(
            f"{COLOR_BOLD}║{COLOR_RESET}  {COLOR_GREEN}✅ Sem erros{COLOR_RESET}"
        )

    # Current files being transferred
    current_files = stats.get("current_files", [])
    if current_files:
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}")
        lines.append(f"{COLOR_BOLD}║{COLOR_RESET}  📥 Transferindo:")
        for cf in current_files[:4]:
            name = cf if len(cf) < term_width - 12 else f"…{cf[-(term_width - 15):]}"
            lines.append(f"{COLOR_BOLD}║{COLOR_RESET}     • {name}")

    lines.append(f"{COLOR_BOLD}╚{'═' * (term_width - 2)}╝{COLOR_RESET}")
    lines.append(
        f"  {COLOR_CYAN}Ctrl+C para sair (download continua em background){COLOR_RESET}"
    )

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
        print(f"{COLOR_RED}rclone não está rodando no homelab!{COLOR_RESET}")
        sys.exit(1)

    try:
        while True:
            # Buscar últimas linhas do log (stats block)
            log_tail = ssh_cmd(
                args.host, args.user,
                f"tail -20 {args.log_file} 2>/dev/null"
            )

            stats = parse_rclone_stats(log_tail)

            # Também pegar du para tamanho real no disco
            du_output = ssh_cmd(
                args.host, args.user,
                "du -sb /mnt/raid1/nextcloud-external/RPA4ALL/ 2>/dev/null"
            )
            if du_output:
                try:
                    real_bytes = int(du_output.split()[0])
                    real_pct = (real_bytes / TOTAL_SIZE_BYTES) * 100
                    if stats["pct"] == 0 and real_bytes > 0:
                        stats["bytes_transferred"] = real_bytes
                        stats["pct"] = min(real_pct, 100.0)
                except (ValueError, IndexError):
                    pass

            # Limpar tela e renderizar
            print("\033[2J\033[H", end="")  # clear screen
            print(render_dashboard(stats))

            # Verificar se rclone ainda roda
            if not is_rclone_running(args.host, args.user):
                pct = float(stats.get("pct", 0))
                if pct >= 99:
                    print(f"\n{COLOR_GREEN}{COLOR_BOLD}✅ Migração concluída!{COLOR_RESET}")
                else:
                    print(f"\n{COLOR_YELLOW}⚠️  rclone parou (pct={pct:.1f}%). Verifique erros.{COLOR_RESET}")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n{COLOR_CYAN}Monitor encerrado. Download continua em background.{COLOR_RESET}")
        print(f"  Re-executar: python3 tools/rclone_progress.py")
        print(f"  Ver log: ssh {args.user}@{args.host} 'tail -f {args.log_file}'")


if __name__ == "__main__":
    main()
