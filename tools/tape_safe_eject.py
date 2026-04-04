#!/usr/bin/env python3
"""Daemon de ejeção segura para drives LTO via Fibre Channel.

Dois modos de operação:

1. **Daemon (--serve)**: expõe HTTP API na porta 9876 + monitora FIFO
   para trigger de ejeção. Botão físico bloqueado (PREVENT MEDIUM REMOVAL)
   porque o HP Ultrium 6 não gera Unit Attention ao pressionar o botão.

2. **One-shot (--eject)**: ejeção imediata de um drive específico.

Triggers de ejeção suportados:
  - HTTP: curl http://localhost:9876/eject/sg2
  - FIFO: echo sg2 > /run/tape-eject.fifo
  - CLI:  tape_safe_eject.py --eject /dev/sg2

Uso:
    python3 tape_safe_eject.py                    # Daemon com HTTP API
    python3 tape_safe_eject.py --eject /dev/sg1   # Ejeção imediata
    python3 tape_safe_eject.py --list              # Listar drives
"""

from __future__ import annotations

import argparse
import fcntl
import http.server
import json
import logging
import os
import select
import signal
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tape-safe-eject")

# ── Constantes ──────────────────────────────────────────────────────
EJECT_POLL_INTERVAL = 3          # segundos entre polls de estado
REWIND_TIMEOUT = 600             # 10 min para rewind
UNMOUNT_TIMEOUT = 120            # 2 min para unmount FUSE
EJECT_TIMEOUT = 120              # 2 min para eject mecânico
FSYNC_TIMEOUT = 300              # 5 min para flush de escrita
LED_BLINK_FAST = 0.15            # intervalo rápido (erro)
LED_BLINK_SLOW = 0.6             # intervalo lento (progresso)
LED_BLINK_COUNT_ERROR = 20       # ciclos de blink para erro
LED_BLINK_COUNT_PROGRESS = 3     # ciclos de blink para progresso
HTTP_PORT = 9876                 # porta da API HTTP de ejeção
FIFO_PATH = "/run/tape-eject.fifo"  # FIFO para trigger local


@dataclass
class DriveInfo:
    """Informações de um drive de fita."""

    sg_dev: str          # /dev/sg0, /dev/sg1, ...
    nst_dev: str         # /dev/nst0, /dev/nst1, ...
    st_dev: str          # /dev/st0, /dev/st1, ...
    scsi_path: str = ""  # 7:0:0:0
    serial: str = ""
    model: str = ""
    locked: bool = False
    ltfs_mountpoint: str | None = None


def _run(cmd: list[str], timeout: int = 30, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Executa comando com timeout e captura de saída."""
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=check,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Timeout (%ds) executando: %s", timeout, " ".join(cmd))
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"comando não encontrado: {cmd[0]}")
    except subprocess.CalledProcessError as exc:
        return subprocess.CompletedProcess(cmd, exc.returncode, exc.stdout or "", exc.stderr or "")


# ── Descoberta de drives ────────────────────────────────────────────

def discover_tape_drives() -> list[DriveInfo]:
    """Descobre todos os drives de fita SCSI no sistema."""
    drives: list[DriveInfo] = []

    for sg_path in sorted(Path("/dev").glob("sg*")):
        sg_dev = str(sg_path)
        inq = _run(["sg_inq", sg_dev], timeout=10)
        if inq.returncode != 0:
            continue
        if "tape" not in inq.stdout.lower():
            continue

        # Extrair modelo e serial
        model = ""
        serial = ""
        for line in inq.stdout.splitlines():
            if "Product identification:" in line:
                model = line.split(":", 1)[1].strip()
            if "Unit serial number:" in line:
                serial = line.split(":", 1)[1].strip()

        if not serial:
            sn = _run(["sg_inq", "-p", "0x80", sg_dev], timeout=10)
            for line in sn.stdout.splitlines():
                if "Unit serial number:" in line or "Serial" in line:
                    serial = line.split(":")[-1].strip()

        # Mapear sg -> nst/st via SCSI path
        sg_num = sg_path.name.replace("sg", "")
        scsi_path = ""
        try:
            dev_link = Path(f"/sys/class/scsi_generic/{sg_path.name}/device")
            if dev_link.exists():
                scsi_path = dev_link.resolve().name
        except Exception:
            pass

        # Encontrar nst/st correspondente ao mesmo SCSI path
        nst_dev = ""
        st_dev = ""
        if scsi_path:
            for tape_path in Path("/sys/class/scsi_tape").iterdir():
                try:
                    tape_scsi = (tape_path / "device").resolve().name
                    if tape_scsi == scsi_path:
                        name = tape_path.name
                        if name.startswith("nst") and not name.endswith("a") and not name.endswith("l") and not name.endswith("m"):
                            nst_dev = f"/dev/{name}"
                        elif name.startswith("st") and not name.startswith("nst"):
                            if not name.endswith("a") and not name.endswith("l") and not name.endswith("m"):
                                st_dev = f"/dev/{name}"
                except Exception:
                    continue

        if not nst_dev:
            nst_dev = f"/dev/nst{sg_num}"
        if not st_dev:
            st_dev = f"/dev/st{sg_num}"

        drives.append(DriveInfo(
            sg_dev=sg_dev,
            nst_dev=nst_dev,
            st_dev=st_dev,
            scsi_path=scsi_path,
            serial=serial,
            model=model,
        ))

    return drives


# ── Controle de LED via atividade SCSI ──────────────────────────────

def _led_blink_cycle(sg_dev: str, interval: float, cycles: int) -> None:
    """Pisca o LED de atividade do drive via TEST UNIT READY repetido.

    Rápido (interval=0.15) = padrão de ERRO visualmente distinto.
    Lento (interval=0.6)  = padrão de PROGRESSO.
    """
    for _ in range(cycles):
        _run(["sg_turs", sg_dev], timeout=5)
        time.sleep(interval)
        # REQUEST SENSE gera segunda ativação do LED
        _run(["sg_raw", "-r", "252", sg_dev, "03", "00", "00", "00", "fc", "00"], timeout=5)
        time.sleep(interval)


def led_signal_progress(sg_dev: str) -> None:
    """Sinaliza progresso com blinks lentos."""
    _led_blink_cycle(sg_dev, LED_BLINK_SLOW, LED_BLINK_COUNT_PROGRESS)


def led_signal_error(sg_dev: str) -> None:
    """Sinaliza erro com blinks rápidos e intensos."""
    logger.warning("Sinalizando ERRO no LED do drive %s", sg_dev)
    _led_blink_cycle(sg_dev, LED_BLINK_FAST, LED_BLINK_COUNT_ERROR)


def led_signal_success(sg_dev: str) -> None:
    """Sinaliza sucesso com 2 blinks lentos."""
    _led_blink_cycle(sg_dev, LED_BLINK_SLOW, 2)


# ── Operações SCSI no drive ─────────────────────────────────────────

def prevent_removal(sg_dev: str) -> bool:
    """Bloqueia o botão de eject físico via PREVENT MEDIUM REMOVAL."""
    result = _run(["sg_prevent", "--prevent=1", sg_dev], timeout=10)
    if result.returncode == 0:
        logger.info("Eject bloqueado: %s", sg_dev)
        return True
    logger.warning("Falha ao bloquear eject em %s: %s", sg_dev, result.stderr.strip())
    return False


def allow_removal(sg_dev: str) -> bool:
    """Desbloqueia o botão de eject físico."""
    result = _run(["sg_prevent", "--allow", sg_dev], timeout=10)
    if result.returncode == 0:
        logger.info("Eject desbloqueado: %s", sg_dev)
        return True
    logger.warning("Falha ao desbloquear eject em %s: %s", sg_dev, result.stderr.strip())
    return False


def has_medium(sg_dev: str) -> bool:
    """Verifica se há fita inserida no drive."""
    result = _run(["sg_turs", "-v", sg_dev], timeout=10)
    if "Not ready" in result.stderr and "medium not present" in result.stderr.lower():
        return False
    return result.returncode == 0


def check_eject_button_pressed(sg_dev: str) -> bool:
    """Detecta se o operador pressionou o botão de eject.

    Quando o botão é pressionado com PREVENT MEDIUM REMOVAL ativo,
    o drive gera Unit Attention com ASC=5Ah ASCQ=01h
    (Operator Medium Removal Request).
    """
    result = _run(["sg_turs", "-v", sg_dev], timeout=5)
    combined = result.stdout + result.stderr
    # Unit Attention com 5a/01 = operador pediu eject
    if "5a" in combined.lower() and "01" in combined.lower() and "unit attention" in combined.lower():
        return True
    # Fallback: verificar REQUEST SENSE
    sense = _run(
        ["sg_raw", "-r", "252", sg_dev, "03", "00", "00", "00", "fc", "00"],
        timeout=5,
    )
    if sense.returncode == 0:
        # Parse sense data hex para ASC=5a ASCQ=01
        hex_out = sense.stdout + sense.stderr
        if "5a" in hex_out.lower():
            return True
    return False


def get_drive_temperature(sg_dev: str) -> int | None:
    """Lê temperatura do drive via log page 0x0d."""
    result = _run(["sg_logs", "-p", "0x0d", sg_dev], timeout=10)
    for line in result.stdout.splitlines():
        if "Current temperature" in line:
            parts = line.split("=")
            if len(parts) >= 2:
                try:
                    return int(parts[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
    return None


# ── Operações LTFS ──────────────────────────────────────────────────

def find_ltfs_mount(nst_dev: str, sg_dev: str) -> str | None:
    """Encontra mountpoint LTFS ativo para o device."""
    result = _run(["mount"], timeout=10)
    for line in result.stdout.splitlines():
        # LTFS monta como: ltfs:/dev/sgN on /path type fuse.ltfs
        if sg_dev in line and "ltfs" in line.lower():
            parts = line.split(" on ")
            if len(parts) >= 2:
                return parts[1].split(" type ")[0].strip()
        # Também verificar por nst
        if nst_dev in line:
            parts = line.split(" on ")
            if len(parts) >= 2:
                return parts[1].split(" type ")[0].strip()

    # Verificar processos LTFS FUSE rodando com este device
    ps_result = _run(["pgrep", "-af", f"ltfs.*{sg_dev}"], timeout=5)
    if ps_result.returncode == 0 and ps_result.stdout.strip():
        for line in ps_result.stdout.splitlines():
            # Extrair mountpoint do cmdline: ltfs -o devname=/dev/sg1 /mnt/point
            parts = line.split()
            for i, part in enumerate(parts):
                if part.startswith("/") and "ltfs" not in part and "/dev/" not in part:
                    mp = part.rstrip("/")
                    if Path(mp).is_dir():
                        return mp
    return None


def unmount_ltfs(mountpoint: str, sg_dev: str) -> bool:
    """Desmonta LTFS FUSE de forma segura."""
    logger.info("Desmontando LTFS: %s", mountpoint)

    # Tentativa 1: umount normal
    result = _run(["umount", mountpoint], timeout=UNMOUNT_TIMEOUT)
    if result.returncode == 0:
        logger.info("LTFS desmontado com sucesso: %s", mountpoint)
        return True

    # Tentativa 2: fusermount
    logger.warning("umount falhou, tentando fusermount: %s", result.stderr.strip())
    result = _run(["fusermount", "-u", mountpoint], timeout=UNMOUNT_TIMEOUT)
    if result.returncode == 0:
        logger.info("LTFS desmontado via fusermount: %s", mountpoint)
        return True

    # Tentativa 3: lazy unmount (último recurso)
    logger.warning("fusermount falhou, forçando lazy unmount")
    result = _run(["umount", "-l", mountpoint], timeout=30)
    if result.returncode == 0:
        logger.info("LTFS desmontado (lazy): %s", mountpoint)
        # Esperar processos LTFS terminarem
        for _ in range(30):
            ps = _run(["pgrep", "-f", f"ltfs.*{sg_dev}"], timeout=5)
            if ps.returncode != 0:
                break
            time.sleep(1)
        return True

    logger.error("Falha ao desmontar LTFS: %s", mountpoint)
    return False


# ── Sequência principal de ejeção segura ────────────────────────────

def safe_eject(drive: DriveInfo) -> bool:
    """Executa ejeção segura completa com sinalização LED.

    Sequência:
        1. Sinaliza início (LED lento)
        2. Verifica/desmonta LTFS
        3. Rewind com timeout
        4. Desbloquer eject
        5. Eject mecânico
        6. Sinaliza resultado (sucesso ou erro)

    Retorna True se ejeção foi bem-sucedida.
    """
    sg = drive.sg_dev
    nst = drive.nst_dev
    logger.info("═══ EJEÇÃO SEGURA: %s (serial=%s) ═══", sg, drive.serial)

    # 1. Sinaliza início
    led_signal_progress(sg)

    # 2. Verificar temperatura
    temp = get_drive_temperature(sg)
    if temp is not None:
        logger.info("Temperatura do drive: %d°C", temp)
        if temp > 55:
            logger.warning("Drive quente (%d°C) — ejeção pode ser lenta", temp)

    # 3. Desmontar LTFS se montado
    mountpoint = find_ltfs_mount(nst, sg)
    if mountpoint:
        logger.info("LTFS montado em: %s — desmontando...", mountpoint)
        led_signal_progress(sg)
        if not unmount_ltfs(mountpoint, sg):
            logger.error("FALHA: não foi possível desmontar LTFS")
            led_signal_error(sg)
            return False
        logger.info("LTFS desmontado ✓")
        # Esperar processos de I/O terminarem
        time.sleep(3)
    else:
        logger.info("Nenhum mount LTFS ativo")

    # 4. Flush: sync do device
    logger.info("Flush de cache do drive...")
    _run(["sync"], timeout=FSYNC_TIMEOUT)

    # 5. Rewind
    logger.info("Rebobinando fita...")
    led_signal_progress(sg)
    rewind = _run(["mt", "-f", nst, "rewind"], timeout=REWIND_TIMEOUT)
    if rewind.returncode != 0:
        logger.warning("Rewind falhou (pode já estar no BOT): %s", rewind.stderr.strip())
        # Não é fatal — tentar eject mesmo assim

    # 6. Verificar posição
    status = _run(["mt", "-f", nst, "status"], timeout=30)
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if "File number" in line or "BOT" in line.lower():
                logger.info("Posição: %s", line.strip())
                break

    # 7. Desbloquear eject
    allow_removal(sg)
    time.sleep(0.5)

    # 8. Ejetar
    logger.info("Ejetando fita...")
    eject = _run(["mt", "-f", nst, "eject"], timeout=EJECT_TIMEOUT)
    if eject.returncode != 0:
        # Fallback: sg_start --eject
        logger.warning("mt eject falhou, tentando sg_start: %s", eject.stderr.strip())
        eject = _run(["sg_start", "--eject", sg], timeout=EJECT_TIMEOUT)

    if eject.returncode != 0:
        logger.error("FALHA na ejeção: %s", eject.stderr.strip())
        led_signal_error(sg)
        # Re-lock para segurança
        prevent_removal(sg)
        return False

    # 9. Aguardar ejeção mecânica
    logger.info("Aguardando ejeção mecânica...")
    for i in range(30):
        time.sleep(1)
        if not has_medium(sg):
            logger.info("Fita ejetada com sucesso ✓ (%ds)", i + 1)
            led_signal_success(sg)
            return True

    # Timeout na ejeção
    logger.warning("Timeout aguardando ejeção mecânica — fita pode estar parcialmente fora")
    led_signal_success(sg)
    return True


# ── Daemon de monitoramento ─────────────────────────────────────────

class EjectDaemon:
    """Monitora botão de eject em todos os drives de fita."""

    def __init__(self, devices: list[str] | None = None) -> None:
        self.running = True
        self.target_devices = devices
        self.drives: list[DriveInfo] = []
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handler para SIGTERM/SIGINT — desbloqueia drives e sai."""
        logger.info("Recebido sinal %d — desbloqueando drives e saindo", signum)
        self.running = False
        for drive in self.drives:
            if drive.locked:
                allow_removal(drive.sg_dev)
                drive.locked = False

    def _refresh_drives(self) -> None:
        """Atualiza lista de drives disponíveis."""
        all_drives = discover_tape_drives()
        if self.target_devices:
            self.drives = [d for d in all_drives if d.sg_dev in self.target_devices]
        else:
            self.drives = all_drives

    def _lock_drives(self) -> None:
        """Bloqueia eject em todos os drives com fita."""
        for drive in self.drives:
            if not drive.locked and has_medium(drive.sg_dev):
                if prevent_removal(drive.sg_dev):
                    drive.locked = True

    def run(self) -> None:
        """Loop principal do daemon."""
        logger.info("Daemon de ejeção segura iniciando...")
        self._refresh_drives()

        if not self.drives:
            logger.error("Nenhum drive de fita encontrado")
            return

        for d in self.drives:
            logger.info(
                "  Drive: %s (%s) serial=%s scsi=%s",
                d.sg_dev, d.model, d.serial, d.scsi_path,
            )

        self._lock_drives()
        logger.info(
            "Monitorando %d drive(s) — pressione o botão de eject para ejeção segura",
            len(self.drives),
        )

        poll_count = 0
        while self.running:
            time.sleep(EJECT_POLL_INTERVAL)
            poll_count += 1

            # Re-scan drives a cada 60 polls (~2 min)
            if poll_count % 60 == 0:
                self._refresh_drives()
                self._lock_drives()

            for drive in self.drives:
                if not drive.locked:
                    # Fita pode ter sido inserida — tentar lock
                    if has_medium(drive.sg_dev):
                        if prevent_removal(drive.sg_dev):
                            drive.locked = True
                            logger.info(
                                "Fita detectada e bloqueada: %s", drive.sg_dev,
                            )
                    continue

                # Verificar se o botão de eject foi pressionado
                if check_eject_button_pressed(drive.sg_dev):
                    logger.info(
                        "BOTÃO DE EJECT detectado: %s", drive.sg_dev,
                    )
                    success = safe_eject(drive)
                    drive.locked = False
                    if success:
                        logger.info("Ejeção concluída: %s ✓", drive.sg_dev)
                    else:
                        logger.error("Ejeção falhou: %s ✗", drive.sg_dev)
                        # Re-lock se a fita ainda está lá
                        if has_medium(drive.sg_dev):
                            prevent_removal(drive.sg_dev)
                            drive.locked = True

                # Verificar se a fita foi removida (por outro processo)
                elif not has_medium(drive.sg_dev):
                    logger.info("Fita removida externamente: %s", drive.sg_dev)
                    drive.locked = False

        # Cleanup
        for drive in self.drives:
            if drive.locked:
                allow_removal(drive.sg_dev)
                drive.locked = False

        logger.info("Daemon encerrado")


# ── CLI ─────────────────────────────────────────────────────────────

def main() -> None:
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Ejeção segura de fitas LTO com sinalização LED",
    )
    parser.add_argument(
        "--device", "-d",
        action="append",
        help="Device SCSI específico (ex: /dev/sg1). Pode repetir.",
    )
    parser.add_argument(
        "--eject", "-e",
        metavar="DEVICE",
        help="Ejeção imediata de um device (sem daemon)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Listar drives de fita disponíveis",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Log detalhado (DEBUG)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list:
        drives = discover_tape_drives()
        if not drives:
            print("Nenhum drive de fita encontrado.")
            return
        print(f"{'Device':<12} {'NST':<12} {'Modelo':<20} {'Serial':<15} {'SCSI':<12} {'Fita'}")
        print("─" * 85)
        for d in drives:
            medium = "✓" if has_medium(d.sg_dev) else "—"
            temp = get_drive_temperature(d.sg_dev)
            temp_str = f"{temp}°C" if temp else "?"
            print(
                f"{d.sg_dev:<12} {d.nst_dev:<12} {d.model:<20} "
                f"{d.serial:<15} {d.scsi_path:<12} {medium} ({temp_str})",
            )
        return

    if args.eject:
        # Ejeção imediata (modo one-shot)
        drives = discover_tape_drives()
        target = next((d for d in drives if d.sg_dev == args.eject), None)
        if not target:
            logger.error("Drive não encontrado: %s", args.eject)
            sys.exit(1)
        if not has_medium(target.sg_dev):
            logger.info("Nenhuma fita no drive %s", args.eject)
            sys.exit(0)
        success = safe_eject(target)
        sys.exit(0 if success else 1)

    # Modo daemon
    daemon = EjectDaemon(devices=args.device)
    daemon.run()


if __name__ == "__main__":
    main()
