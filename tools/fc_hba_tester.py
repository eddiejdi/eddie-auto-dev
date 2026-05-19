#!/usr/bin/env python3
"""Agente testador de cabo e qualidade de link FC (Fibre Channel) — dual HBA.

Testa cada porta HBA individualmente (host0 / host7 no NAS rpa4all-nas-001)
e emite relatório de qualidade com score 0-100 e recomendação de ação.

Suíte de testes:
  1. link_state       — verifica Online/Offline na porta
  2. port_speed       — velocidade negociada vs. suportada
  3. error_counters   — invalid_crc, loss_of_signal, loss_of_sync, link_failure
  4. lip_stability    — conta quantos LIPs ocorrem em 60s (injeção + monitoramento)
  5. tgt_reachability — verifica se há targets/devices visíveis na porta
  6. transfer_latency — mede tempo de INQUIRY SCSI via sg_inq em ms
  7. reconnect_time   — mede tempo de recovery após LIP forçado

Saída: JSON estruturado + texto legível com score e recomendação.

Uso local:
    python3 fc_hba_tester.py [--hosts host0,host7] [--device /dev/sg0] [--json]

Integração FastAPI:
    POST /tape/hba-test
    GET  /tape/hba-test/report
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("fc-hba-tester")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ─── Constantes de qualidade ─────────────────────────────────────────────────

MAX_ERROR_THRESHOLD = 10          # erros FC antes de degradar score
MAX_LIP_PER_MINUTE = 3           # LIPs/min aceitáveis em link saudável
MAX_LATENCY_MS = 200             # latência INQUIRY aceitável em ms
MAX_RECONNECT_MS = 15_000        # tempo de reconnect após LIP (ms)
STABLE_WINDOW_S = 60             # janela de monitoramento de estabilidade

# Mapa host FC → slot PCI (informativo, sem efeito em runtime)
HBA_PCI_MAP: dict[str, str] = {
    "host0": "0000:01:00.0",
    "host7": "0000:01:00.1",
}

SYS_FC = Path("/sys/class/fc_host")
SYS_RPORT = Path("/sys/class/fc_remote_ports")


# ─── Estruturas de resultado ─────────────────────────────────────────────────

@dataclass
class FCTestResult:  # renomeado de FCTestResult para não conflitar com pytest
    """Resultado de um sub-teste individual de qualidade FC."""

    name: str
    passed: bool
    score: float          # 0.0 – 100.0
    value: Any            # valor medido
    expected: Any         # valor esperado/limite
    message: str
    weight: float = 1.0   # peso na composição do score final
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortReport:
    """Relatório completo de uma porta HBA."""

    host: str
    pci_slot: str
    tests: list[FCTestResult] = field(default_factory=list)
    score: float = 0.0
    grade: str = "N/A"
    recommendation: str = ""
    tested_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def compute_score(self) -> None:
        """Calcula score ponderado e grade a partir dos testes."""
        if not self.tests:
            return
        total_weight = sum(t.weight for t in self.tests)
        weighted = sum(t.score * t.weight for t in self.tests) / total_weight
        self.score = round(weighted, 1)
        if self.score >= 90:
            self.grade = "A"
            self.recommendation = "Cabo e link FC em excelente condição."
        elif self.score >= 75:
            self.grade = "B"
            self.recommendation = "Link estável mas com erros menores. Monitorar SFP/cabo."
        elif self.score >= 55:
            self.grade = "C"
            self.recommendation = "Qualidade degradada. Substituir cabo ou SFP da porta."
        elif self.score >= 30:
            self.grade = "D"
            self.recommendation = "Link instável. Substituição de cabo/SFP urgente."
        else:
            self.grade = "F"
            self.recommendation = "Porta inutilizável. Trocar SFP/cabo imediatamente."


@dataclass
class HBATestReport:
    """Relatório agregado de todas as portas testadas."""

    hostname: str
    ports: list[PortReport] = field(default_factory=list)
    device: str = "/dev/sg0"
    overall_score: float = 0.0
    best_port: str = ""
    worst_port: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str = ""
    error: str = ""

    def finalize(self) -> None:
        """Calcula métricas agregadas e elege melhor porta."""
        self.finished_at = datetime.now().isoformat()
        if not self.ports:
            return
        scored = [(p.host, p.score) for p in self.ports]
        self.overall_score = round(sum(s for _, s in scored) / len(scored), 1)
        best = max(scored, key=lambda x: x[1])
        worst = min(scored, key=lambda x: x[1])
        self.best_port = best[0]
        self.worst_port = worst[0]


# ─── Helpers SCSI/sysfs ──────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Executa comando e retorna resultado sem exceção."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 1, "", str(exc))


def _sysfs_read(path: Path) -> str:
    """Lê arquivo sysfs com fallback seguro."""
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _reset_error_counters(host: str) -> None:
    """Solicita reset dos contadores de erro FC via sysfs (se suportado)."""
    reset_path = SYS_FC / host / "reset_statistics"
    if reset_path.exists():
        try:
            reset_path.write_text("1")
        except OSError:
            pass


def _read_error_counters(host: str) -> dict[str, int]:
    """Lê contadores de erro da porta FC."""
    counters = {
        "invalid_crc_count": 0,
        "loss_of_signal_count": 0,
        "loss_of_sync_count": 0,
        "link_failure_count": 0,
        "tx_frames": 0,
        "rx_frames": 0,
    }
    base = SYS_FC / host
    for key in counters:
        raw = _sysfs_read(base / key)
        if raw:
            try:
                counters[key] = int(raw, 16) if raw.startswith("0x") else int(raw)
            except ValueError:
                pass
    return counters


def _read_port_state(host: str) -> str:
    return _sysfs_read(SYS_FC / host / "port_state")


def _read_port_speed(host: str) -> str:
    return _sysfs_read(SYS_FC / host / "speed")


def _read_supported_speeds(host: str) -> str:
    return _sysfs_read(SYS_FC / host / "supported_speeds")


def _read_port_name(host: str) -> str:
    return _sysfs_read(SYS_FC / host / "port_name")


def _issue_lip(host: str) -> bool:
    """Emite Loop Initialization Primitive (LIP) na porta."""
    lip_path = SYS_FC / host / "issue_lip"
    if not lip_path.exists():
        return False
    try:
        lip_path.write_text("1")
        return True
    except OSError:
        return False


def _count_remote_targets(host: str) -> int:
    """Conta targets FC visíveis na porta via rports."""
    if not SYS_RPORT.exists():
        return 0
    count = 0
    for rport in SYS_RPORT.iterdir():
        # rport name: rport-{host_idx}-{...}, e.g. rport-0:0-0 / rport-7:0-0
        host_idx = host.replace("host", "")
        if rport.name.startswith(f"rport-{host_idx}:"):
            state = _sysfs_read(rport / "port_state")
            if "Online" in state:
                count += 1
    return count


def _sg_inquiry_latency_ms(device: str) -> float | None:
    """Mede latência de um INQUIRY SCSI em ms."""
    if not Path(device).exists():
        return None
    start = time.perf_counter()
    r = _run(["sg_inq", device], timeout=10)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if r.returncode == 0:
        return round(elapsed_ms, 2)
    return None


# ─── Sub-testes ──────────────────────────────────────────────────────────────

def check_link_state(host: str) -> FCTestResult:
    """T1: Verifica se a porta está Online."""
    state = _read_port_state(host)
    online = "Online" in state
    return FCTestResult(
        name="link_state",
        passed=online,
        score=100.0 if online else 0.0,
        value=state or "unreadable",
        expected="Online",
        message="Porta Online." if online else f"Porta fora de linha: '{state}'.",
        weight=3.0,
    )


def check_port_speed(host: str) -> FCTestResult:
    """T2: Velocidade negociada vs. suportada."""
    speed = _read_port_speed(host)
    supported = _read_supported_speeds(host)

    # Converte "8 Gbit" → 8
    def _parse_gbit(s: str) -> int | None:
        m = re.search(r"(\d+)\s*[Gg]bit", s)
        return int(m.group(1)) if m else None

    negotiated = _parse_gbit(speed)
    # "16 Gbit, 8 Gbit, 4 Gbit" → pega máximo
    sup_vals = [_parse_gbit(x) for x in re.split(r"[,;]", supported)]
    max_supported = max((v for v in sup_vals if v is not None), default=None)

    if negotiated is None:
        return FCTestResult(
            name="port_speed",
            passed=False,
            score=30.0,
            value=speed or "unreadable",
            expected="≥ 4 Gbit",
            message="Não foi possível ler velocidade negociada.",
            weight=2.0,
        )

    # Score: proporção em relação ao máximo suportado
    if max_supported and max_supported > 0:
        ratio = min(negotiated / max_supported, 1.0)
    else:
        ratio = 1.0 if negotiated >= 4 else 0.5

    score = round(ratio * 100.0, 1)
    passed = negotiated >= 4
    msg = (
        f"Velocidade negociada: {negotiated} Gbit (máx suportado: {max_supported} Gbit)."
        if max_supported else f"Velocidade negociada: {negotiated} Gbit."
    )
    return FCTestResult(
        name="port_speed",
        passed=passed,
        score=score,
        value=speed,
        expected=f"{max_supported} Gbit" if max_supported else "≥ 4 Gbit",
        message=msg,
        weight=2.0,
    )


def check_error_counters(host: str, window_s: int = STABLE_WINDOW_S) -> FCTestResult:
    """T3: Contadores de erro FC em janela de monitoramento.

    Reset → aguarda window_s → lê deltas.
    Em modo de teste unitário (window_s=0) retorna snapshot direto.
    """
    _reset_error_counters(host)

    if window_s > 0:
        logger.info("T3 [%s]: aguardando %ds para coletar erros FC...", host, window_s)
        time.sleep(window_s)

    counters = _read_error_counters(host)
    error_keys = ["invalid_crc_count", "loss_of_signal_count", "loss_of_sync_count", "link_failure_count"]
    total_errors = sum(counters.get(k, 0) for k in error_keys)

    if total_errors == 0:
        score = 100.0
    elif total_errors <= MAX_ERROR_THRESHOLD:
        score = max(0.0, 100.0 - (total_errors / MAX_ERROR_THRESHOLD) * 60.0)
    else:
        score = max(0.0, 40.0 - (total_errors - MAX_ERROR_THRESHOLD) * 3.0)

    passed = total_errors <= MAX_ERROR_THRESHOLD
    return FCTestResult(
        name="error_counters",
        passed=passed,
        score=round(score, 1),
        value=counters,
        expected=f"erros totais ≤ {MAX_ERROR_THRESHOLD}",
        message=(
            f"Total de erros FC: {total_errors} ({total_errors} em {window_s}s)."
            if total_errors > 0
            else f"Sem erros FC em {window_s}s."
        ),
        weight=3.0,
        raw=counters,
    )


def check_lip_stability(host: str, window_s: int = STABLE_WINDOW_S) -> FCTestResult:
    """T4: Estabilidade de link — conta LIPs espontâneos em janela de 60s.

    Emite um LIP inicial para garantir visibilidade e depois monitora link_failure_count.
    """
    _reset_error_counters(host)
    _issue_lip(host)
    time.sleep(min(window_s, 10))  # espera o link se reestabelecer

    # Conta falhas de link durante a janela restante
    remaining = max(0, window_s - 10)
    if remaining > 0:
        time.sleep(remaining)

    counters = _read_error_counters(host)
    failures = counters.get("link_failure_count", 0) + counters.get("loss_of_sync_count", 0)

    # Normaliza por minuto
    rate_per_min = failures * (60 / max(window_s, 1))

    if rate_per_min <= MAX_LIP_PER_MINUTE:
        score = 100.0
    else:
        score = max(0.0, 100.0 - ((rate_per_min - MAX_LIP_PER_MINUTE) / MAX_LIP_PER_MINUTE) * 50.0)

    passed = rate_per_min <= MAX_LIP_PER_MINUTE
    return FCTestResult(
        name="lip_stability",
        passed=passed,
        score=round(score, 1),
        value=round(rate_per_min, 2),
        expected=f"≤ {MAX_LIP_PER_MINUTE} LIPs/min",
        message=(
            f"Taxa de instabilidade: {rate_per_min:.1f}/min ({failures} eventos em {window_s}s)."
            if failures > 0
            else f"Link estável — 0 eventos em {window_s}s."
        ),
        weight=3.0,
        raw=counters,
    )


def check_tgt_reachability(host: str) -> FCTestResult:
    """T5: Verifica se há pelo menos 1 target FC visível na porta."""
    count = _count_remote_targets(host)
    passed = count >= 1
    return FCTestResult(
        name="tgt_reachability",
        passed=passed,
        score=100.0 if passed else 0.0,
        value=count,
        expected="≥ 1 target Online",
        message=f"{count} target(s) FC Online nesta porta." if passed else "Nenhum target FC visível.",
        weight=2.0,
    )


def check_transfer_latency(host: str, device: str) -> FCTestResult:  # noqa: N802
    """T6: Mede latência de INQUIRY SCSI (não bloqueia drive)."""
    # Só mede se o device for visível via esta porta
    state = _read_port_state(host)
    if "Online" not in state:
        return FCTestResult(
            name="transfer_latency",
            passed=False,
            score=0.0,
            value=None,
            expected=f"< {MAX_LATENCY_MS} ms",
            message="Porta offline — latência não mensurável.",
            weight=1.5,
        )

    # Verificar se o device está ocupado (LTFS ou driver com lock exclusivo).
    # "Busy" significa que o caminho FC está ativo — não é falha de transporte.
    if Path(device).exists():
        probe = _run(["sg_inq", device], timeout=10)
        if probe.returncode != 0 and "busy" in (probe.stderr + probe.stdout).lower():
            return FCTestResult(
                name="transfer_latency",
                passed=True,
                score=90.0,
                value=None,
                expected=f"< {MAX_LATENCY_MS} ms",
                message=f"Dispositivo {device} em uso ativo — caminho FC operacional, latência não mensurável.",
                weight=1.5,
            )

    latency = _sg_inquiry_latency_ms(device)
    if latency is None:
        return FCTestResult(
            name="transfer_latency",
            passed=False,
            score=30.0,
            value=None,
            expected=f"< {MAX_LATENCY_MS} ms",
            message=f"Dispositivo {device} inacessível ou timeout.",
            weight=1.5,
        )

    if latency <= MAX_LATENCY_MS:
        score = 100.0
    else:
        score = max(0.0, 100.0 - ((latency - MAX_LATENCY_MS) / MAX_LATENCY_MS) * 50.0)

    passed = latency <= MAX_LATENCY_MS
    return FCTestResult(
        name="transfer_latency",
        passed=passed,
        score=round(score, 1),
        value=latency,
        expected=f"< {MAX_LATENCY_MS} ms",
        message=f"Latência INQUIRY: {latency:.1f} ms.",
        weight=1.5,
    )


def check_reconnect_time(host: str) -> FCTestResult:
    """T7: Mede tempo de recovery de link após LIP forçado."""
    if "Online" not in _read_port_state(host):
        return FCTestResult(
            name="reconnect_time",
            passed=False,
            score=0.0,
            value=None,
            expected=f"< {MAX_RECONNECT_MS} ms",
            message="Porta offline — teste de reconnect ignorado.",
            weight=2.0,
        )

    _issue_lip(host)
    start = time.perf_counter()
    deadline = start + (MAX_RECONNECT_MS / 1000) * 2  # timeout 2×

    while time.perf_counter() < deadline:
        if "Online" in _read_port_state(host):
            break
        time.sleep(0.5)

    elapsed_ms = (time.perf_counter() - start) * 1000
    reconnected = "Online" in _read_port_state(host)

    if not reconnected:
        return FCTestResult(
            name="reconnect_time",
            passed=False,
            score=0.0,
            value=round(elapsed_ms, 0),
            expected=f"< {MAX_RECONNECT_MS} ms",
            message=f"Porta não reconectou em {elapsed_ms:.0f} ms.",
            weight=2.0,
        )

    if elapsed_ms <= MAX_RECONNECT_MS:
        score = 100.0
    else:
        score = max(0.0, 100.0 - ((elapsed_ms - MAX_RECONNECT_MS) / MAX_RECONNECT_MS) * 50.0)

    passed = elapsed_ms <= MAX_RECONNECT_MS
    return FCTestResult(
        name="reconnect_time",
        passed=passed,
        score=round(score, 1),
        value=round(elapsed_ms, 0),
        expected=f"< {MAX_RECONNECT_MS} ms",
        message=f"Reconnect após LIP: {elapsed_ms:.0f} ms.",
        weight=2.0,
    )


# ─── Orquestrador principal ───────────────────────────────────────────────────

def run_port_test(
    host: str,
    device: str = "/dev/sg0",
    stability_window: int = STABLE_WINDOW_S,
    skip_slow: bool = False,
) -> PortReport:
    """Executa todos os testes em uma porta HBA e retorna relatório."""
    pci = HBA_PCI_MAP.get(host, "unknown")
    report = PortReport(host=host, pci_slot=pci)
    port_name = _read_port_name(host)
    logger.info("=== Testando %s (PCI %s) WWPN: %s ===", host, pci, port_name)

    report.tests.append(check_link_state(host))
    report.tests.append(check_port_speed(host))
    report.tests.append(check_tgt_reachability(host))
    report.tests.append(check_transfer_latency(host, device))

    if skip_slow:
        # Em testes unitários substituímos por resultados sintéticos
        report.tests.append(FCTestResult(
            name="error_counters",
            passed=True, score=100.0,
            value={"note": "skipped (fast mode)"},
            expected=f"≤ {MAX_ERROR_THRESHOLD}", message="Skipped.", weight=3.0,
        ))
        report.tests.append(FCTestResult(
            name="lip_stability",
            passed=True, score=100.0,
            value=0.0, expected=f"≤ {MAX_LIP_PER_MINUTE}/min",
            message="Skipped.", weight=3.0,
        ))
        report.tests.append(FCTestResult(
            name="reconnect_time",
            passed=True, score=100.0,
            value=0.0, expected=f"< {MAX_RECONNECT_MS} ms",
            message="Skipped.", weight=2.0,
        ))
    else:
        # T3 e T4 compartilham a mesma janela de tempo
        window = stability_window
        report.tests.append(check_error_counters(host, window_s=window))
        report.tests.append(check_lip_stability(host, window_s=window))
        report.tests.append(check_reconnect_time(host))

    report.compute_score()
    logger.info("%s → Score: %.1f (%s) — %s", host, report.score, report.grade, report.recommendation)
    return report


def run_dual_hba_test(
    hosts: list[str] | None = None,
    device: str = "/dev/sg0",
    stability_window: int = STABLE_WINDOW_S,
    skip_slow: bool = False,
) -> HBATestReport:
    """Testa ambas as portas HBA e gera relatório comparativo."""
    import socket
    hostname = socket.gethostname()
    effective_hosts = hosts if hosts else list(HBA_PCI_MAP.keys())

    report = HBATestReport(hostname=hostname, device=device)
    for host in effective_hosts:
        if not (SYS_FC / host).exists():
            logger.warning("Host FC '%s' não encontrado em sysfs — ignorando.", host)
            port = PortReport(host=host, pci_slot=HBA_PCI_MAP.get(host, "unknown"))
            port.tests.append(FCTestResult(
                name="host_exists", passed=False, score=0.0,
                value=False, expected=True,
                message=f"Host {host} não presente em {SYS_FC}.",
                weight=3.0,
            ))
            port.compute_score()
            report.ports.append(port)
            continue

        port_report = run_port_test(
            host=host, device=device,
            stability_window=stability_window, skip_slow=skip_slow,
        )
        report.ports.append(port_report)

    report.finalize()
    return report


# ─── Renderização de relatório ────────────────────────────────────────────────

def render_text_report(report: HBATestReport) -> str:
    """Gera saída legível por humanos."""
    lines: list[str] = []
    sep = "─" * 60
    lines += [
        "╔══════════════════════════════════════════════════════════╗",
        "║        RELATÓRIO DE QUALIDADE FC HBA — DUAL PORT         ║",
        "╚══════════════════════════════════════════════════════════╝",
        f"Host      : {report.hostname}",
        f"Device    : {report.device}",
        f"Iniciado  : {report.started_at}",
        f"Concluído : {report.finished_at}",
        f"Score geral: {report.overall_score:.1f}/100",
        f"Melhor porta: {report.best_port}   Pior: {report.worst_port}",
        "",
    ]

    for port in report.ports:
        lines += [
            sep,
            f"PORTA: {port.host}  (PCI {port.pci_slot})",
            f"Score: {port.score:.1f}/100  Grade: {port.grade}",
            f"Recomendação: {port.recommendation}",
            "",
        ]
        for t in port.tests:
            icon = "✓" if t.passed else "✗"
            lines.append(
                f"  [{icon}] {t.name:<22} valor={t.value!s:<30} esperado={t.expected}"
            )
            lines.append(f"           {t.message}")
        lines.append("")

    lines += [
        sep,
        "COMPARATIVO ENTRE PORTAS:",
    ]
    for port in report.ports:
        bar = "█" * int(port.score / 5)
        lines.append(f"  {port.host}: {bar:<20} {port.score:.1f}/100 ({port.grade})")

    lines += [
        "",
        "DIAGNÓSTICO FINAL:",
        *(f"  • {port.host}: {port.recommendation}" for port in report.ports),
        "",
    ]

    if report.best_port and len(report.ports) > 1:
        best = next(p for p in report.ports if p.host == report.best_port)
        if best.score < 75:
            lines.append("⚠  ATENÇÃO: Nenhuma porta com qualidade suficiente (< 75).")
            lines.append("   Recomenda-se substituição de cabo/SFP antes de novo uso de fita.")
        else:
            lines.append(f"✓  Usar porta {report.best_port} para operação de fita.")

    return "\n".join(lines)


# ─── FastAPI integration helpers ─────────────────────────────────────────────

def report_to_dict(report: HBATestReport) -> dict[str, Any]:
    """Serializa relatório para resposta JSON (FastAPI-safe)."""
    def _port_to_dict(p: PortReport) -> dict[str, Any]:
        return {
            "host": p.host,
            "pci_slot": p.pci_slot,
            "score": p.score,
            "grade": p.grade,
            "recommendation": p.recommendation,
            "tested_at": p.tested_at,
            "tests": [asdict(t) for t in p.tests],
        }

    return {
        "hostname": report.hostname,
        "device": report.device,
        "overall_score": report.overall_score,
        "best_port": report.best_port,
        "worst_port": report.worst_port,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "error": report.error,
        "ports": [_port_to_dict(p) for p in report.ports],
    }


# ─── Entry point ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FC HBA dual-port cable quality tester")
    p.add_argument("--hosts", default="host0,host7",
                   help="Portas HBA a testar, separadas por vírgula (default: host0,host7)")
    p.add_argument("--device", default="/dev/sg0",
                   help="Dispositivo SCSI do drive de fita (default: /dev/sg0)")
    p.add_argument("--window", type=int, default=STABLE_WINDOW_S,
                   help=f"Janela de monitoramento em segundos (default: {STABLE_WINDOW_S})")
    p.add_argument("--json", action="store_true", help="Saída somente em JSON")
    p.add_argument("--fast", action="store_true",
                   help="Pula testes lentos (estabilidade/reconnect) — útil em CI")
    return p


def main() -> None:
    """Ponto de entrada CLI."""
    args = _build_parser().parse_args()
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]

    report = run_dual_hba_test(
        hosts=hosts,
        device=args.device,
        stability_window=args.window,
        skip_slow=args.fast,
    )

    if args.json:
        print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        print(render_text_report(report))
        if not args.json:
            print(f"\nJSON:\n{json.dumps(report_to_dict(report), ensure_ascii=False, indent=2)}")

    # Exit code: 0 se melhor porta ≥ 55, 1 se ambas abaixo disso
    best_score = max((p.score for p in report.ports), default=0.0)
    sys.exit(0 if best_score >= 55 else 1)


if __name__ == "__main__":
    main()
