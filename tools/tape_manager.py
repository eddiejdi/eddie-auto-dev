#!/usr/bin/env python3
"""
tape_manager.py — Ciclo de vida completo da fita LTO.

Unifica: start (mount resiliente) → flush (com cursor) → stop → recover.
Notifica via Telegram a cada etapa importante.

Uso:
    tape-manager start              # monta até disponível, com retry e recovery
    tape-manager flush              # flush de CACHE_DIR → TAPE_DIR com cursor
    tape-manager stop               # fecha cursor + desmonta
    tape-manager recover [--deep]   # ltfsck + cursor-recover
    tape-manager run                # ciclo completo: start → flush → stop
    tape-manager status             # estado atual (sem lock)

Variáveis de ambiente:
    LTFS_DEVICE, LTFS_TAPE_DEVICE, LTFS_MOUNT_POINT, LTFS_SERVICE
    LTFS_CACHE_DIR          diretório de staging (padrão: /var/spool/lto6-cache)
    LTFS_VOLSER             volser da fita (ex: NC2508)
    LTFS_MAX_MOUNT_ATTEMPTS tentativas de mount (padrão: 5)
    LTFS_MOUNT_COOLDOWN     segundos entre tentativas (padrão: 60)
    TG_ENV_FILE             arquivo .env com credenciais de notificação
    TG_KEY_TOKEN            nome da chave do token no .env (padrão: TELEGRAM_BOT_TOKEN)
    TG_KEY_CHAT             nome da chave do chat_id no .env (padrão: TELEGRAM_CHAT_ID)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# ─── Configuração ──────────────────────────────────────────────────────────────
LTFS_DEVICE          = os.getenv("LTFS_DEVICE",        "/dev/sg0")
LTFS_TAPE_DEVICE     = os.getenv("LTFS_TAPE_DEVICE",   "/dev/nst0")
LTFS_MOUNT_POINT     = Path(os.getenv("LTFS_MOUNT_POINT",   "/mnt/tape/lto6"))
LTFS_SERVICE         = os.getenv("LTFS_SERVICE",        "ltfs-lto6.service")
LTFS_CACHE_DIR       = Path(os.getenv("LTFS_CACHE_DIR", "/var/spool/lto6-cache"))
LTFS_LOG             = Path(os.getenv("LTFS_FLUSH_LOG", "/var/log/lto6/tape_manager.log"))
LTFS_RECOVERY_SCRIPT = Path(os.getenv("LTFS_RECOVERY_SCRIPT", "/usr/local/tools/ltfs_recovery.py"))
LTFS_CURSOR_VOLSER_FILE = Path(os.getenv("LTFS_CURSOR_VOLSER_FILE", "/var/lib/ltfs/current_volser.txt"))
LTFS_MAX_MOUNT_ATTEMPTS = int(os.getenv("LTFS_MAX_MOUNT_ATTEMPTS", "5"))
LTFS_MOUNT_COOLDOWN     = int(os.getenv("LTFS_MOUNT_COOLDOWN",     "60"))
LTFS_ORCH_LOCK          = Path(os.getenv("LTFS_ORCH_LOCK", "/run/lock/ltfs-tape-exclusive.lock"))
LTFS_MEDIUM_WAIT_TIMEOUT = int(os.getenv("LTFS_MEDIUM_WAIT_TIMEOUT", "120"))  # segundos esperando fita

# Notificação: lê credenciais de arquivo .env externo
TG_ENV_FILE  = Path(os.getenv("TG_ENV_FILE",   "/home/homelab/myClaude/.env"))
TG_KEY_TOKEN = os.getenv("TG_KEY_TOKEN", "TELEGRAM_BOT_TOKEN")
TG_KEY_CHAT  = os.getenv("TG_KEY_CHAT",  "TELEGRAM_CHAT_ID")


# ─── Notificação via mensageiro externo ───────────────────────────────────────
def _load_notify_creds() -> tuple[str, str]:
    """Lê token e chat_id do arquivo .env externo. Nunca hardcode aqui."""
    token, chat_id = "", ""
    try:
        for line in TG_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip("'\"")
            if key.strip() == TG_KEY_TOKEN:
                token = val
            elif key.strip() == TG_KEY_CHAT:
                chat_id = val
    except OSError:
        pass
    return token, chat_id


_NOTIFY_TOKEN, _NOTIFY_CHAT = _load_notify_creds()


def notify(msg: str) -> None:
    """Envia mensagem pelo mensageiro configurado; falha silenciosa."""
    if not _NOTIFY_TOKEN or not _NOTIFY_CHAT:
        return
    try:
        data = urllib.parse.urlencode({
            "chat_id": _NOTIFY_CHAT,
            "text": msg,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_NOTIFY_TOKEN}/sendMessage",
            data=data, method="POST",
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


# ─── Log ──────────────────────────────────────────────────────────────────────
LTFS_LOG.parent.mkdir(parents=True, exist_ok=True)
_log_fh = LTFS_LOG.open("a", encoding="utf-8")


def log(level: str, msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] [{level}] {msg}"
    print(line, flush=True)
    _log_fh.write(line + "\n")
    _log_fh.flush()


# ─── Utilitários internos ─────────────────────────────────────────────────────
def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", "timeout")
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def _is_mounted() -> bool:
    return _run(["mountpoint", "-q", str(LTFS_MOUNT_POINT)]).returncode == 0


def _volser() -> str:
    v = os.getenv("LTFS_VOLSER", "").strip()
    if v:
        return v
    try:
        v = LTFS_CURSOR_VOLSER_FILE.read_text().strip()
        if v:
            return v
    except OSError:
        pass
    return "UNKNOWN"


def _recovery_call(mode: str, extra: list[str] | None = None) -> dict[str, Any]:
    """Chama ltfs_recovery.py e retorna o payload JSON da última linha."""
    cmd = ["python3", str(LTFS_RECOVERY_SCRIPT), f"--{mode}"] + (extra or [])
    r = _run(cmd, timeout=7200)
    for line in reversed((r.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    return {"success": r.returncode == 0, "raw": r.stdout.strip(), "stderr": r.stderr.strip()}


def _cursor(mode: str, extra: list[str] | None = None) -> dict[str, Any]:
    return _recovery_call(f"cursor-{mode}", ["--volser", _volser()] + (extra or []))


def _run_ltfsck(deep: bool = False) -> dict[str, Any]:
    cmd = ["/usr/local/bin/ltfsck"]
    if deep:
        cmd.append("--deep-recovery")
    cmd.append(LTFS_DEVICE)
    r = _run(cmd, timeout=7200)
    combined = (r.stdout or "") + (r.stderr or "")
    hw_error = _detect_hardware_error(combined)
    return {
        "success": r.returncode == 0,
        "returncode": r.returncode,
        "stdout": r.stdout[-3000:],
        "stderr": r.stderr[-500:],
        "hw_error": hw_error,  # None, "hw_io_error", "no_medium", "hung_process", "index_corrupt"
    }


# ─── Detecção de erros de hardware e estado ───────────────────────────────────

# Marcadores que indicam erro de hardware irrecuperável via software
_HW_ERROR_MARKERS = (
    "-29998",
    "unknown error code",
    "sense code 00001a",
    "scsi error",
    "medium check failed",
    "extra blocks detected",
)

# Marcadores de mídia ausente
_NO_MEDIUM_MARKERS = (
    "no medium present",
    "medium not present",
    "-20209",
    "ltfs20209",
    "no tape",
    "not ready",
)

# Marcadores de timeout / processo travado
_HUNG_MARKERS = (
    "transport endpoint is not connected",
    "resource temporarily unavailable",
    "device or resource busy",
    "input/output error",
    "ltfs30205i",   # LTFS SCSI read attempt
    "ltfs30263i",   # LTFS read returns error
)


def _detect_in(text: str, markers: tuple[str, ...]) -> bool:
    t = text.lower()
    return any(m in t for m in markers)


def _journal_for_service(lines: int = 60) -> str:
    r = _run(["journalctl", "-u", LTFS_SERVICE, f"-n{lines}", "--no-pager", "-o", "short"])
    return r.stdout or ""


def _clear_stale_lock() -> bool:
    """
    Verifica se o arquivo de lock existe e o PID anotado está morto.
    Se estiver morto, remove o lock e retorna True. Não remove lock de processo vivo.
    """
    if not LTFS_ORCH_LOCK.exists():
        return False
    try:
        content = LTFS_ORCH_LOCK.read_text().strip()
        pid = int(content.split()[0]) if content else 0
        if pid <= 0:
            LTFS_ORCH_LOCK.unlink(missing_ok=True)
            log("WARN", f"lock: arquivo de lock vazio removido ({LTFS_ORCH_LOCK})")
            return True
        # Verifica se o processo ainda existe
        try:
            os.kill(pid, 0)
            log("INFO", f"lock: processo {pid} ainda vivo, lock legítimo")
            return False
        except ProcessLookupError:
            LTFS_ORCH_LOCK.unlink(missing_ok=True)
            log("WARN", f"lock: PID {pid} morto — lock obsoleto removido ({LTFS_ORCH_LOCK})")
            notify(f"🔓 <b>Tape Manager</b> — lock obsoleto removido (PID {pid} morto)")
            return True
        except PermissionError:
            # processo existe mas pertence a outro usuário — trata como vivo
            log("INFO", f"lock: processo {pid} existe (sem permissão de sinal), lock mantido")
            return False
    except (ValueError, OSError) as exc:
        log("WARN", f"lock: erro lendo lock file — {exc}")
        LTFS_ORCH_LOCK.unlink(missing_ok=True)
        return True


def _wait_for_medium(timeout: int = LTFS_MEDIUM_WAIT_TIMEOUT) -> bool:
    """
    Aguarda a fita ser carregada no drive, com polling a cada 10s.
    Retorna True quando a fita estiver pronta ou False se timeout.
    """
    log("INFO", f"medium: aguardando inserção da fita em {LTFS_TAPE_DEVICE} (timeout={timeout}s)")
    notify(
        f"⏳ <b>Tape Manager</b> — fita não presente em <code>{LTFS_TAPE_DEVICE}</code>\n"
        f"Aguardando inserção… (timeout {timeout}s)"
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = _run(["mt", "-f", LTFS_TAPE_DEVICE, "status"], timeout=15)
        output = (r.stdout + r.stderr).lower()
        if r.returncode == 0 and not _detect_in(output, _NO_MEDIUM_MARKERS):
            log("INFO", "medium: fita detectada no drive")
            notify(f"✅ <b>Tape Manager</b> — fita detectada em <code>{LTFS_TAPE_DEVICE}</code>")
            return True
        time.sleep(10)
    log("ERROR", "medium: timeout aguardando fita")
    notify(
        f"❌ <b>Tape Manager</b> — timeout aguardando fita em <code>{LTFS_TAPE_DEVICE}</code>\n"
        "Insira a fita e execute novamente."
    )
    return False


def _kill_hung_ltfs() -> None:
    """
    Mata processos LTFS travados (ltfs, ltfsck, fusermount) que estejam usando o device.
    """
    log("WARN", "hung: matando processos LTFS travados")
    for proc_name in ("ltfs", "ltfsck", "fusermount"):
        _run(["pkill", "-9", "-f", f"{proc_name}.*{LTFS_DEVICE}"], timeout=10)
        _run(["pkill", "-9", "-f", f"{proc_name}.*{LTFS_TAPE_DEVICE}"], timeout=10)
    # tenta desmontar forçado se ainda houver mount fuse
    if _is_mounted():
        _run(["fusermount", "-u", "-z", str(LTFS_MOUNT_POINT)], timeout=15)
    time.sleep(3)


def _flush_scsi_port() -> bool:
    """
    Executa reset SCSI do device antes de tentar montar.
    Limpa estado de transport failure, power-on-reset e connection-down
    sem apagar dados da fita.
    """
    log("INFO", f"scsi-reset: flush da porta {LTFS_DEVICE}")
    r = _run(["sg_reset", "--device", LTFS_DEVICE], timeout=30)
    if r.returncode == 0:
        log("INFO", "scsi-reset: ok — aguardando estabilização do drive")
        time.sleep(5)
        # Confirma que o device responde após o reset
        r2 = _run(["sg_inq", LTFS_DEVICE], timeout=15)
        if r2.returncode == 0:
            log("INFO", "scsi-reset: drive respondendo normalmente")
            return True
        log("WARN", "scsi-reset: drive não respondeu ao sg_inq após reset")
        return False
    log("WARN", f"scsi-reset: sg_reset falhou rc={r.returncode} — {(r.stderr or '').strip()[:120]}")
    return False


def _rewind_tape() -> bool:
    """Rebobina a fita para o início (BOT). Requer confirmação explícita de hardware."""
    log("INFO", f"rewind: rebobinando {LTFS_TAPE_DEVICE} para BOT")
    r = _run(["mt", "-f", LTFS_TAPE_DEVICE, "rewind"], timeout=300)
    if r.returncode == 0:
        log("INFO", "rewind: ok")
        return True
    log("WARN", f"rewind: falhou rc={r.returncode} — {(r.stderr or '').strip()[:120]}")
    return False


def _detect_hardware_error(output: str) -> str | None:
    """
    Analisa saída de ltfsck/journal e retorna o tipo de problema, ou None.

    Retorna um dos tokens:
      "hw_io_error"     — erro SCSI hardware irrecuperável
      "no_medium"       — fita não presente no drive
      "hung_process"    — processo/device travado (I/O error, transport endpoint)
      "index_corrupt"   — índice LTFS corrompido (extra blocks)
    """
    t = output.lower()
    if _detect_in(t, _HW_ERROR_MARKERS):
        if "extra blocks" in t or "inconsistent" in t:
            return "index_corrupt"
        return "hw_io_error"
    if _detect_in(t, _NO_MEDIUM_MARKERS):
        return "no_medium"
    if _detect_in(t, _HUNG_MARKERS):
        return "hung_process"
    return None


# ─── Recovery de incidentes ────────────────────────────────────────────────────
_AUTO_ACTIONS = {"selfheal_remount", "ltfsck", "deep_recovery"}


def _execute_recovery_action(action: str, context: str = "") -> dict[str, Any]:
    """
    Executa uma ação de recovery.

    Ações suportadas:
      selfheal_remount  — reset-failed + restart (problema de serviço, sem ltfsck)
      ltfsck            — ltfsck normal + restart
      deep_recovery     — ltfsck --deep-recovery + restart
      clear_stale_lock  — remove lock com PID morto
      wait_medium       — aguarda inserção da fita no drive
      kill_hung         — mata processos LTFS travados + tenta desmontar
      rewind_retry      — rebobina fita (BOT) + restart
      hw_alert          — notifica erro de hardware irrecuperável, não tenta mais
    """
    if action == "selfheal_remount":
        _run(["systemctl", "reset-failed", LTFS_SERVICE])
        r = _run(["systemctl", "restart", LTFS_SERVICE], timeout=480)
        return {"success": r.returncode == 0 and _is_mounted(), "action": action}

    if action in ("ltfsck", "deep_recovery"):
        deep = action == "deep_recovery"
        res = _run_ltfsck(deep=deep)
        if res["success"]:
            _run(["systemctl", "reset-failed", LTFS_SERVICE])
            _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
        return {**res, "action": action}

    if action == "clear_stale_lock":
        cleared = _clear_stale_lock()
        return {"success": cleared, "action": action}

    if action == "wait_medium":
        ok = _wait_for_medium()
        return {"success": ok, "action": action}

    if action == "kill_hung":
        _kill_hung_ltfs()
        _flush_scsi_port()
        _run(["systemctl", "reset-failed", LTFS_SERVICE])
        r = _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
        ok = r.returncode == 0 and _is_mounted()
        return {"success": ok, "action": action}

    if action == "rewind_retry":
        _flush_scsi_port()
        rewound = _rewind_tape()
        if not rewound:
            return {"success": False, "action": action, "error": "rewind falhou"}
        _run(["systemctl", "reset-failed", LTFS_SERVICE])
        r = _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
        ok = r.returncode == 0 and _is_mounted()
        return {"success": ok, "action": action}

    if action == "hw_alert":
        log("ERROR", f"hardware: erro irrecuperável detectado — {context or LTFS_DEVICE}")
        notify(
            f"🆘 <b>Tape Manager</b> — ERRO DE HARDWARE\n"
            f"Device: <code>{LTFS_DEVICE}</code>  Fita: <code>{LTFS_TAPE_DEVICE}</code>\n"
            f"Erro SCSI irrecuperável por software.\n"
            f"<b>Ações recomendadas:</b>\n"
            f"  1. Limpar cabeçote (fita de limpeza)\n"
            f"  2. Testar com outra fita\n"
            f"  3. Verificar cabo SCSI / SAS\n"
            f"  4. Substituir drive se persistir\n"
            f"<code>{context[:200] if context else ''}</code>"
        )
        return {"success": False, "action": action, "hw_irrecoverable": True}

    return {"success": False, "error": f"ação desconhecida: {action}"}


# ─── Operações ────────────────────────────────────────────────────────────────
def _start_precheck() -> str | None:
    """
    Verificações antes de iniciar o loop de mount.
    Retorna "abort" se deve parar, ou None se ok para continuar.
    """
    # 1. Lock obsoleto — limpa antes de qualquer tentativa de start
    if LTFS_ORCH_LOCK.exists():
        cleared = _clear_stale_lock()
        if not cleared:
            log("WARN", "start: lock ativo por processo vivo — aguardando liberação")
            notify(
                f"⚠️ <b>Tape Manager</b> — lock ativo em <code>{LTFS_ORCH_LOCK}</code>\n"
                "Operação em curso? Aguardando antes de continuar."
            )
            time.sleep(30)

    # 2. Flush SCSI antes de qualquer tentativa de mount — limpa transport failures e power-on-resets
    _flush_scsi_port()

    # 3. Verifica se há fita no drive (mt status — rápido)
    mt_r = _run(["mt", "-f", LTFS_TAPE_DEVICE, "status"], timeout=15)
    mt_out = (mt_r.stdout + mt_r.stderr).lower()
    if _detect_in(mt_out, _NO_MEDIUM_MARKERS):
        log("WARN", "start: fita não presente no drive")
        if not _wait_for_medium():
            return "abort"

    return None


def op_start() -> bool:
    """
    Monta a fita com loop de retry e recovery automático.
    Detecta e trata: lock obsoleto, fita ausente, processo travado,
    erro de hardware SCSI, índice corrompido.
    Retorna True quando LTFS estiver disponível para escrita.
    """
    log("INFO", f"start: serviço={LTFS_SERVICE} mount={LTFS_MOUNT_POINT}")
    notify(f"🔄 <b>Tape Manager</b> — iniciando mount\n<code>{LTFS_SERVICE}</code> → <code>{LTFS_MOUNT_POINT}</code>")

    if _is_mounted():
        log("INFO", "start: LTFS já montado")
        notify("✅ <b>Tape Manager</b> — LTFS já disponível")
        return True

    # Pré-checagens de lock e mídia antes do loop
    precheck = _start_precheck()
    if precheck == "abort":
        return False

    for attempt in range(1, LTFS_MAX_MOUNT_ATTEMPTS + 1):
        log("INFO", f"start: tentativa {attempt}/{LTFS_MAX_MOUNT_ATTEMPTS}")
        notify(f"⏳ <b>Tape Manager</b> — mount tentativa {attempt}/{LTFS_MAX_MOUNT_ATTEMPTS}")

        _run(["systemctl", "enable", LTFS_SERVICE])
        _run(["systemctl", "reset-failed", LTFS_SERVICE])
        _run(["systemctl", "start", LTFS_SERVICE], timeout=480)

        if _is_mounted():
            log("INFO", f"start: LTFS montado na tentativa {attempt}")
            notify(f"✅ <b>Tape Manager</b> — LTFS montado (tentativa {attempt})")
            _cursor("open")
            return True

        log("WARN", f"start: mount falhou na tentativa {attempt} — diagnosticando")
        notify(f"⚠️ <b>Tape Manager</b> — mount falhou (tentativa {attempt}), diagnosticando…")

        # Coleta saída do journal para análise de hardware
        journal = _journal_for_service(80)
        hw_err = _detect_hardware_error(journal)

        if hw_err == "no_medium":
            log("WARN", "start: fita não presente — aguardando inserção")
            notify(f"📀 <b>Tape Manager</b> — fita não presente em <code>{LTFS_TAPE_DEVICE}</code>")
            if not _wait_for_medium():
                return False
            continue

        if hw_err == "hung_process":
            log("WARN", "start: processo/device travado detectado — tentando recuperar")
            notify(f"⚙️ <b>Tape Manager</b> — device travado em <code>{LTFS_DEVICE}</code>, liberando…")
            rec = _execute_recovery_action("kill_hung")
            if rec.get("success") and _is_mounted():
                log("INFO", "start: LTFS disponível após kill_hung")
                notify("✅ <b>Tape Manager</b> — LTFS disponível após liberação de processo")
                _cursor("open")
                return True
            # Tenta rewind após kill
            if attempt <= LTFS_MAX_MOUNT_ATTEMPTS - 1:
                log("INFO", "start: tentando rewind após kill_hung")
                notify(f"⏪ <b>Tape Manager</b> — rebobinando <code>{LTFS_TAPE_DEVICE}</code>…")
                _execute_recovery_action("rewind_retry")
            continue

        if hw_err == "hw_io_error":
            # Erro SCSI direto — tenta rewind + 1 retry antes de alertar hardware
            if attempt == 1:
                log("WARN", "start: erro SCSI detectado — tentando rewind antes de alertar")
                notify(f"⚠️ <b>Tape Manager</b> — erro SCSI em <code>{LTFS_DEVICE}</code>, tentando rewind…")
                rec = _execute_recovery_action("rewind_retry")
                if rec.get("success") and _is_mounted():
                    log("INFO", "start: LTFS disponível após rewind")
                    notify("✅ <b>Tape Manager</b> — LTFS disponível após rewind")
                    _cursor("open")
                    return True
            else:
                _execute_recovery_action("hw_alert", context=journal[-600:])
                return False

        if hw_err == "index_corrupt":
            log("WARN", "start: índice LTFS corrompido — iniciando ltfsck")
            notify(f"🔧 <b>Tape Manager</b> — índice corrompido em <code>{LTFS_DEVICE}</code>, executando ltfsck…")
            _run(["systemctl", "stop", LTFS_SERVICE], timeout=60)
            res = _execute_recovery_action("ltfsck")
            if res.get("success"):
                r2 = _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
                if r2.returncode == 0 and _is_mounted():
                    log("INFO", "start: LTFS disponível após ltfsck")
                    notify("✅ <b>Tape Manager</b> — LTFS disponível após ltfsck")
                    _cursor("recover")
                    _cursor("open")
                    return True
            else:
                # ltfsck falhou → tenta deep-recovery
                hw_err2 = res.get("hw_error")
                if hw_err2 == "hw_io_error":
                    _execute_recovery_action("hw_alert", context=(res.get("stdout") or "")[-600:])
                    return False
                log("WARN", "start: ltfsck falhou — tentando deep-recovery")
                notify("🔧 <b>Tape Manager</b> — ltfsck falhou, tentando deep-recovery…")
                res2 = _execute_recovery_action("deep_recovery")
                if res2.get("success"):
                    _cursor("recover")
                    _cursor("open")
                    log("INFO", "start: LTFS recuperado via deep-recovery")
                    notify("✅ <b>Tape Manager</b> — LTFS recuperado via deep-recovery")
                    return True
                _execute_recovery_action("hw_alert", context=(res2.get("stdout") or "")[-600:])
                return False

        # Nenhum erro de hardware detectado — tenta recovery via ltfs_recovery.py
        _clear_stale_lock()  # limpa lock morto antes do diagnóstico
        diag = _recovery_call("diagnose")
        issue = diag.get("details", {}).get("issue") or {}
        action = issue.get("recovery_action", "")

        if action in _AUTO_ACTIONS:
            log("INFO", f"start: executando recovery action={action} — {issue.get('title', '')}")
            notify(f"🔧 <b>Tape Manager</b> — recovery: <code>{action}</code>\n{issue.get('title', '')}")
            rec = _execute_recovery_action(action)
            if rec.get("hw_error") == "hw_io_error":
                _execute_recovery_action("hw_alert", context=(rec.get("stdout") or "")[-600:])
                return False
            if rec.get("success") and _is_mounted():
                log("INFO", f"start: LTFS disponível após {action}")
                notify(f"✅ <b>Tape Manager</b> — LTFS disponível após <code>{action}</code>")
                _cursor("open")
                return True
            log("WARN", f"start: recovery {action} não resolveu (success={rec.get('success')})")
        elif action == "manual_config_fix":
            log("ERROR", f"start: exige correção manual — {issue.get('title', '')}")
            notify(f"❌ <b>Tape Manager</b> — correção manual necessária\n{issue.get('title', '')}")
            return False
        else:
            log("WARN", f"start: incidente sem assinatura conhecida na tentativa {attempt}")

        if attempt < LTFS_MAX_MOUNT_ATTEMPTS:
            log("INFO", f"start: aguardando {LTFS_MOUNT_COOLDOWN}s")
            time.sleep(LTFS_MOUNT_COOLDOWN)

    log("ERROR", f"start: LTFS indisponível após {LTFS_MAX_MOUNT_ATTEMPTS} tentativas")
    notify(f"❌ <b>Tape Manager</b> — LTFS indisponível após {LTFS_MAX_MOUNT_ATTEMPTS} tentativas\nIntervenção manual necessária.")
    return False


def op_flush() -> bool:
    """
    Flush LTFS_CACHE_DIR → LTFS_MOUNT_POINT com cursor-update por arquivo.
    Análogo ao 'resume' de download manager: cada arquivo confirmado é marcado.
    Se a fita não estiver montada, tenta montá-la antes de começar.
    """
    # Verifica cache antes de montar — evita mount desnecessário se vazio
    files = sorted(LTFS_CACHE_DIR.rglob("*")) if LTFS_CACHE_DIR.exists() else []
    files = [f for f in files if f.is_file()]

    if not files:
        log("INFO", "flush: cache vazio, nada a fazer")
        return True

    if not _is_mounted():
        log("INFO", "flush: LTFS não montado — tentando start automático")
        if not op_start():
            log("ERROR", "flush: não foi possível montar a fita, abortando")
            return False

    total = len(files)
    log("INFO", f"flush: {total} arquivo(s) a copiar para {LTFS_MOUNT_POINT}")
    notify(f"📼 <b>Tape Manager flush</b> — {total} arquivo(s)\n→ <code>{LTFS_MOUNT_POINT}</code>")

    copied = failed = 0

    for src in files:
        rel = src.relative_to(LTFS_CACHE_DIR)
        dst = LTFS_MOUNT_POINT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
            subprocess.run(["sync", str(dst)], timeout=30, capture_output=True)
            # cursor atualizado ANTES de remover da cache — garante rastreabilidade
            _cursor("update", ["--file", str(rel)])
            src.unlink()
            copied += 1
            log("INFO", f"flush: ok {rel}")
        except Exception as exc:
            failed += 1
            log("ERROR", f"flush: falha {rel} — {exc}")
            notify(f"⚠️ <b>Tape Manager flush</b> — falha\n<code>{rel}</code>")

    # limpa dirs vazios da cache
    for d in sorted(LTFS_CACHE_DIR.rglob("*"), reverse=True):
        if d.is_dir():
            try:
                d.rmdir()
            except OSError:
                pass

    ok = failed == 0
    log("INFO" if ok else "ERROR", f"flush: {copied} ok, {failed} falhas")
    icon = "✅" if ok else "⚠️"
    notify(f"{icon} <b>Tape Manager flush</b> — {copied} copiados, {failed} falhas")
    return ok


def op_stop() -> bool:
    """Fecha cursor (status=clean) e para o serviço LTFS."""
    log("INFO", "stop: encerrando sessão")
    notify("⏹️ <b>Tape Manager</b> — encerrando sessão de escrita")

    _cursor("close")
    r = _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)
    still = _is_mounted()
    ok = r.returncode == 0 and not still
    log("INFO" if ok else "ERROR", f"stop: rc={r.returncode} still_mounted={still}")
    notify(f"{'✅' if ok else '⚠️'} <b>Tape Manager</b> — {'parado' if ok else 'falha ao parar'}")
    return ok


def op_recover(deep: bool = False) -> bool:
    """
    Recovery a partir do cursor:
      1. Para LTFS + libera processos travados
      2. ltfsck (ou --deep-recovery)
      3. Se erro SCSI → escalada para hw_alert (irrecuperável)
      4. Se ltfsck normal falha → tenta deep-recovery antes de desistir
      5. cursor-recover → lista confirmados + re-fila
      6. Reinicia LTFS e abre novo cursor
    """
    mode = "deep-recovery" if deep else "ltfsck"
    log("INFO", f"recover: {mode} volser={_volser()}")
    notify(f"🔧 <b>Tape Manager recover</b> — <code>{mode}</code> | volser <code>{_volser()}</code>")

    _run(["systemctl", "stop", LTFS_SERVICE], timeout=180)
    _run(["systemctl", "reset-failed", LTFS_SERVICE])
    _kill_hung_ltfs()
    _clear_stale_lock()

    res = _run_ltfsck(deep=deep)

    if not res["success"]:
        hw_err = res.get("hw_error")

        # Erro SCSI irrecuperável
        if hw_err == "hw_io_error":
            _execute_recovery_action("hw_alert", context=(res.get("stdout") or "")[-600:])
            return False

        # ltfsck normal falhou → escalada para deep-recovery
        if not deep:
            log("WARN", f"recover: ltfsck falhou — escalando para deep-recovery")
            notify("🔧 <b>Tape Manager recover</b> — ltfsck falhou, tentando deep-recovery…")
            res2 = _run_ltfsck(deep=True)
            if not res2["success"]:
                hw_err2 = res2.get("hw_error")
                if hw_err2 == "hw_io_error":
                    _execute_recovery_action("hw_alert", context=(res2.get("stdout") or "")[-600:])
                else:
                    log("ERROR", "recover: deep-recovery também falhou — intervenção manual")
                    notify(
                        "❌ <b>Tape Manager recover</b> — ltfsck e deep-recovery falharam\n"
                        "Intervenção manual necessária."
                    )
                return False
            # deep-recovery ok — continua com análise de cursor
            res = res2
            mode = "deep-recovery"
        else:
            log("ERROR", f"recover: {mode} falhou rc={res['returncode']}")
            notify(f"❌ <b>Tape Manager recover</b> — {mode} falhou\nIntervenção manual necessária.")
            return False

    log("INFO", f"recover: {mode} ok — analisando cursor")
    cur = _cursor("recover")
    confirmed = cur.get("details", {}).get("files_recovered", [])
    requeue   = cur.get("details", {}).get("files_to_requeue", [])
    log("INFO", f"recover: {len(confirmed)} confirmados, {len(requeue)} para re-fila")
    notify(
        f"📋 <b>Tape Manager recover</b>\n"
        f"✅ Confirmados: {len(confirmed)}\n"
        f"🔄 Re-fila: {len(requeue)}"
        + (("\nArquivos: " + ", ".join(f.get("path", "") for f in requeue[:3])) if requeue else "")
    )

    _run(["systemctl", "enable", LTFS_SERVICE])
    _run(["systemctl", "start", LTFS_SERVICE], timeout=480)
    mounted = _is_mounted()
    log("INFO" if mounted else "ERROR", f"recover: remount={mounted}")
    notify(f"{'✅' if mounted else '❌'} <b>Tape Manager recover</b> — remount {'ok' if mounted else 'falhou'}")

    if mounted:
        _cursor("open")

    return mounted


def op_run(deep_on_fail: bool = False) -> bool:
    """Ciclo completo: start → flush → stop, com recovery automático se flush falhar."""
    log("INFO", "run: ciclo completo iniciado")
    notify(f"🚀 <b>Tape Manager</b> — ciclo completo\n<code>{datetime.now().isoformat(timespec='seconds')}</code>")

    if not op_start():
        return False

    ok = op_flush()

    if not ok:
        log("WARN", "run: flush falhou — tentando recover e re-flush")
        notify("⚠️ <b>Tape Manager</b> — flush falhou, tentando recover…")
        if op_recover(deep=deep_on_fail):
            ok = op_flush()

    op_stop()

    icon = "✅" if ok else "❌"
    notify(f"{icon} <b>Tape Manager</b> — ciclo encerrado {'com sucesso' if ok else 'com falhas'}\n<code>{datetime.now().isoformat(timespec='seconds')}</code>")
    return ok


def op_status() -> bool:
    mounted = _is_mounted()
    r = _run(["systemctl", "is-active", LTFS_SERVICE])
    cur = _cursor("status")
    print(json.dumps({
        "mounted": mounted,
        "mountpoint": str(LTFS_MOUNT_POINT),
        "service": LTFS_SERVICE,
        "service_state": r.stdout.strip() or "unknown",
        "volser": _volser(),
        "cursor": cur.get("details", {}).get("cursor"),
        "timestamp": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2))
    return mounted


# ─── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="tape_manager — ciclo de vida completo da fita LTO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "operation",
        choices=["start", "flush", "stop", "recover", "run", "status"],
    )
    parser.add_argument("--deep", action="store_true", help="Deep recovery no ltfsck")
    parser.add_argument("--no-notify", action="store_true", help="Desabilitar notificações")
    args = parser.parse_args()

    if args.no_notify:
        global _NOTIFY_TOKEN
        _NOTIFY_TOKEN = ""

    result = {
        "start":   op_start,
        "flush":   op_flush,
        "stop":    op_stop,
        "recover": lambda: op_recover(deep=args.deep),
        "run":     lambda: op_run(deep_on_fail=args.deep),
        "status":  op_status,
    }[args.operation]()

    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
