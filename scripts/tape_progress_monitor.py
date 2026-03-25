#!/usr/bin/env python3
"""Monitor de progresso em tempo real para backup em fita LTO no NAS.

Conecta via SSH ao NAS (192.168.15.4) e exibe:
  - Barra de progresso de batches
  - Velocidade dd atual (MB/s)
  - MiB transferidos / total estimado
  - ETA baseado na média das últimas velocidades
  - Últimas linhas do log
  - Status FC e tape drive

Uso:
  python3 scripts/tape_progress_monitor.py
  python3 scripts/tape_progress_monitor.py --nas 192.168.15.4 --interval 5
"""

import argparse
import os
import re
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Configuração ──────────────────────────────────────────────────────────────
NAS_HOST = "192.168.15.4"
NAS_USER = "root"
NAS_PASS = "Rpa_four_all!"
LOG_GLOB = "/var/log/tape-dd-chunked-*.log"
STATE_FILE = "/srv/tape-staging/.dd-backup-state"
TOTAL_BATCHES_FILE = "/srv/tape-staging/.chunks/total_batches"
LOG_GENERAL = "/var/log/tape-dd-chunked.log"
REFRESH_INTERVAL = 5  # segundos

# Tamanho médio estimado por batch (MiB) — calculado do log
BATCH_SIZES_REGEX = re.compile(r"Tar criado: (\d+) MiB")
DD_SPEED_REGEX = re.compile(r"(\d+[\d.]*) MB/s")
PROGRESS_REGEX = re.compile(r"Progresso: (\d+)/(\d+) batches")
BATCH_START_REGEX = re.compile(r"=== BATCH (\d+)/(\d+) ===")
PIECE_PCT_REGEX = re.compile(r"Peça ok \((\d+)%\)")


# ── Terminal helpers ──────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BLUE = "\033[94m"
DIM = "\033[2m"
CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def color(text: str, c: str) -> str:
    """Aplica cor ANSI ao texto."""
    return f"{c}{text}{RESET}"


def progress_bar(current: int, total: int, width: int = 50) -> str:
    """Gera barra de progresso ASCII colorida."""
    if total <= 0:
        return "[" + " " * width + "]"
    pct = min(current / total, 1.0)
    filled = int(width * pct)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    pct_str = f"{pct * 100:5.1f}%"
    return f"[{color(bar, GREEN)}] {color(pct_str, BOLD)}"


def inner_bar(pct: int, width: int = 30) -> str:
    """Barra de progresso interno do dd (dentro do batch atual)."""
    filled = int(width * pct / 100)
    empty = width - filled
    bar = "▓" * filled + "░" * empty
    return f"[{color(bar, CYAN)}] {pct:3d}%"


def run_ssh(cmd: str, timeout: int = 10) -> str:
    """Executa comando no NAS via sshpass+ssh e retorna stdout."""
    full_cmd = [
        "sshpass", "-p", NAS_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={timeout}",
        f"{NAS_USER}@{NAS_HOST}",
        cmd
    ]
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except FileNotFoundError:
        # sshpass não instalado
        sys.exit(f"{RED}ERRO: sshpass não encontrado. Instale: sudo apt install sshpass{RESET}")


def fetch_state() -> dict:
    """Busca estado completo do backup no NAS de uma vez (1 SSH)."""
    cmd = (
        "cat " + STATE_FILE + " 2>/dev/null || echo '0';"
        "echo '---TOTAL---';"
        "cat " + TOTAL_BATCHES_FILE + " 2>/dev/null || echo '182';"
        "echo '---LOG---';"
        "tail -50 " + LOG_GLOB + " 2>/dev/null || tail -50 " + LOG_GENERAL + " 2>/dev/null;"
        "echo '---TAPE---';"
        "mt -f /dev/nst0 status 2>&1 | grep -E 'File number|BOT|EOT|ONLINE' | head -3;"
        "echo '---FC---';"
        "dmesg | grep -c 'LOOP DOWN' 2>/dev/null || echo 0;"
        "echo '---PID---';"
        "pgrep -f tape-dd-chunked.sh || echo '';"
        "echo '---NVME---';"
        "df -h / | tail -1;"
    )
    raw = run_ssh(cmd)
    return _parse_state(raw)


def _parse_state(raw: str) -> dict:
    """Parseia output composto do estado do NAS."""
    sections: dict = {
        "current_batch": 0,
        "total_batches": 182,
        "log_lines": [],
        "tape_status": "",
        "fc_drops": 0,
        "pid": "",
        "nvme_info": "",
        "last_speed_mbs": 0.0,
        "current_batch_pct": 0,
        "batch_sizes": [],
        "current_batch_in_progress": 0,
    }

    parts = raw.split("---TOTAL---")
    if len(parts) < 2:
        return sections

    sections["current_batch"] = int(parts[0].strip() or "0")

    rest = parts[1].split("---LOG---")
    sections["total_batches"] = int(rest[0].strip() or "182")

    if len(rest) < 2:
        return sections

    log_and_rest = rest[1].split("---TAPE---")
    log_text = log_and_rest[0]
    sections["log_lines"] = [l for l in log_text.splitlines() if l.strip()][-15:]

    # Parsear progresso do log
    for line in reversed(sections["log_lines"]):
        m = PROGRESS_REGEX.search(line)
        if m:
            sections["current_batch"] = int(m.group(1))
            sections["total_batches"] = int(m.group(2))
            break
        m = BATCH_START_REGEX.search(line)
        if m:
            sections["current_batch_in_progress"] = int(m.group(1))
            sections["total_batches"] = int(m.group(2))
            break

    # Velocidade dd mais recente
    speeds = DD_SPEED_REGEX.findall(log_text)
    if speeds:
        try:
            sections["last_speed_mbs"] = float(speeds[-1])
        except ValueError:
            pass

    # % interna do batch atual
    pcts = PIECE_PCT_REGEX.findall(log_text)
    if pcts:
        try:
            sections["current_batch_pct"] = int(pcts[-1])
        except ValueError:
            pass

    # Tamanhos dos batches (para estimar total MiB)
    sizes = BATCH_SIZES_REGEX.findall(log_text)
    sections["batch_sizes"] = [int(s) for s in sizes]

    after_tape = log_and_rest[1] if len(log_and_rest) > 1 else ""
    tape_fc = after_tape.split("---FC---")
    sections["tape_status"] = tape_fc[0].strip()

    if len(tape_fc) > 1:
        rest2 = tape_fc[1].split("---PID---")
        try:
            sections["fc_drops"] = int(rest2[0].strip() or "0")
        except ValueError:
            sections["fc_drops"] = 0

        if len(rest2) > 1:
            pid_nvme = rest2[1].split("---NVME---")
            sections["pid"] = pid_nvme[0].strip()
            if len(pid_nvme) > 1:
                sections["nvme_info"] = pid_nvme[1].strip()

    return sections


class SpeedTracker:
    """Registra velocidades para calcular ETA."""
    def __init__(self, maxlen: int = 20) -> None:
        self._speeds: deque[float] = deque(maxlen=maxlen)

    def add(self, speed: float) -> None:
        """Adiciona uma amostra de velocidade."""
        if speed > 0:
            self._speeds.append(speed)

    @property
    def avg_mbs(self) -> float:
        """Retorna velocidade média."""
        if not self._speeds:
            return 0.0
        return sum(self._speeds) / len(self._speeds)

    def eta(self, remaining_mib: float) -> Optional[str]:
        """Calcula ETA como string legível."""
        avg = self.avg_mbs
        if avg <= 0:
            return None
        secs = remaining_mib / avg
        if secs < 60:
            return f"{int(secs)}s"
        elif secs < 3600:
            return f"{int(secs // 60)}m {int(secs % 60)}s"
        else:
            h = int(secs // 3600)
            m = int((secs % 3600) // 60)
            return f"{h}h {m}m"


def render(state: dict, tracker: SpeedTracker, start_time: datetime) -> None:
    """Renderiza o painel completo no terminal."""
    # Atualizar tracker
    if state["last_speed_mbs"] > 0:
        tracker.add(state["last_speed_mbs"])

    current = state["current_batch"]
    total = state["total_batches"]
    in_progress = state.get("current_batch_in_progress", current + 1)

    # Estimativa de MiB
    avg_batch_mib = (
        sum(state["batch_sizes"]) / len(state["batch_sizes"])
        if state["batch_sizes"] else 470.0
    )
    done_mib = current * avg_batch_mib
    total_mib = total * avg_batch_mib
    remaining_mib = total_mib - done_mib

    eta_str = tracker.eta(remaining_mib) or "calculando..."
    elapsed = datetime.now() - start_time
    elapsed_str = str(elapsed).split(".")[0]

    is_running = bool(state["pid"])
    status_icon = color("● RODANDO", GREEN) if is_running else color("○ PARADO", RED)

    term_width = os.get_terminal_size().columns if sys.stdout.isatty() else 100
    sep = "─" * min(term_width, 80)

    lines = []
    lines.append(CLEAR_SCREEN)
    lines.append(f"{BOLD}{CYAN}╔{'═' * (min(term_width,78) - 2)}╗{RESET}")
    lines.append(f"{BOLD}{CYAN}║{'  🎞  BACKUP LTO-6 — Nextcloud → Fita':^{min(term_width,78) - 2}}║{RESET}")
    lines.append(f"{BOLD}{CYAN}╚{'═' * (min(term_width,78) - 2)}╝{RESET}")
    lines.append("")

    # Status + tempo
    now_str = datetime.now().strftime("%H:%M:%S")
    lines.append(f"  Status: {status_icon}   {DIM}{now_str}  |  rodando há {elapsed_str}{RESET}")
    lines.append("")

    # Barra principal
    lines.append(f"  {color('Progresso geral:', BOLD)}")
    lines.append(f"  {progress_bar(current, total, width=min(term_width - 20, 55))}")
    lines.append(f"  Batches: {color(str(current), GREEN)}/{total}   "
                 f"Estimado: {color(f'{done_mib:.0f}', GREEN)} / {total_mib:.0f} MiB "
                 f"({done_mib/1024:.1f} GB / {total_mib/1024:.1f} GB)")
    lines.append("")

    # Batch atual (inner progress)
    if in_progress > current and is_running:
        inner_pct = state.get("current_batch_pct", 0)
        lines.append(f"  {color(f'Batch em andamento: #{in_progress}/{total}', BOLD)}")
        lines.append(f"  {inner_bar(inner_pct)}")
        lines.append("")

    # Performance
    speed = state["last_speed_mbs"]
    avg_speed = tracker.avg_mbs
    speed_color = GREEN if speed > 30 else YELLOW if speed > 10 else RED
    lines.append(f"  {color('Desempenho:', BOLD)}")
    lines.append(f"  Velocidade atual: {color(f'{speed:.1f} MB/s', speed_color)}   "
                 f"Média:  {color(f'{avg_speed:.1f} MB/s', CYAN)}   "
                 f"ETA: {color(eta_str, YELLOW)}")
    lines.append("")

    # Hardware
    fc_drops = state["fc_drops"]
    fc_color = GREEN if fc_drops == 0 else YELLOW if fc_drops < 5 else RED
    lines.append(sep)
    lines.append(f"  {color('Hardware:', BOLD)}")
    lines.append(f"  Tape: {state['tape_status'] or 'OK'}   |   "
                 f"FC LOOP DOWN (total): {color(str(fc_drops), fc_color)}   |   "
                 f"NVMe: {state['nvme_info']}")
    lines.append(sep)

    # Log recente
    lines.append(f"  {color('Log recente:', BOLD)}")
    for l in state["log_lines"][-8:]:
        ts_end = l.find("]") + 1
        if ts_end > 0:
            ts_part = color(l[:ts_end], DIM)
            msg_part = l[ts_end:].strip()
            # colorir linhas especiais
            if "SUCESSO" in msg_part or "Progresso" in msg_part:
                msg_part = color(msg_part, GREEN)
            elif "ERRO" in msg_part or "FATAL" in msg_part or "falhou" in msg_part.lower():
                msg_part = color(msg_part, RED)
            elif "dd de" in msg_part:
                msg_part = color(msg_part, CYAN)
            elif "recovery" in msg_part.lower():
                msg_part = color(msg_part, YELLOW)
            lines.append(f"  {ts_part} {msg_part}")
        else:
            lines.append(f"  {DIM}{l}{RESET}")

    lines.append(sep)
    lines.append(f"  {DIM}Ctrl+C para sair | atualiza a cada {REFRESH_INTERVAL}s{RESET}")

    print("\n".join(lines), flush=True)


def check_sshpass() -> None:
    """Verifica se sshpass está instalado."""
    result = subprocess.run(["which", "sshpass"], capture_output=True)
    if result.returncode != 0:
        print(f"{YELLOW}sshpass não encontrado. Instalando...{RESET}")
        subprocess.run(["sudo", "apt-get", "install", "-y", "sshpass"],
                       check=True, capture_output=True)


def main() -> None:
    """Loop principal do monitor."""
    global NAS_HOST, REFRESH_INTERVAL  # noqa: PLW0603

    parser = argparse.ArgumentParser(description="Monitor de backup em fita LTO")
    parser.add_argument("--nas", default=NAS_HOST, help="IP do NAS")
    parser.add_argument("--interval", type=int, default=REFRESH_INTERVAL,
                        help="Intervalo de atualização em segundos")
    args = parser.parse_args()

    NAS_HOST = args.nas
    REFRESH_INTERVAL = args.interval

    check_sshpass()

    tracker = SpeedTracker()
    start_time = datetime.now()

    if sys.stdout.isatty():
        print(HIDE_CURSOR, end="", flush=True)

    try:
        while True:
            state = fetch_state()
            render(state, tracker, start_time)

            # Parar se backup terminou normalmente
            current = state["current_batch"]
            total = state["total_batches"]
            pid = state["pid"]

            if current >= total and total > 0 and not pid:
                print(f"\n{color('🎉 BACKUP COMPLETO!', GREEN)} {current}/{total} batches gravados em fita.\n")
                break

            time.sleep(REFRESH_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        if sys.stdout.isatty():
            print(SHOW_CURSOR, end="", flush=True)
        print(f"\n{DIM}Monitor encerrado.{RESET}")


if __name__ == "__main__":
    main()
