#!/usr/bin/env python3
"""Agente de qualidade dos componentes da stack de fita LTO.

Executa uma bateria de verificacoes sem depender da fita montada para medir a
qualidade operacional dos componentes envolvidos no caminho de fita:
- HBA Fibre Channel (reaproveitando o fc_hba_tester)
- Visibilidade do drive SCSI
- Nodes de device (/dev/sg, /dev/st, /dev/nst)
- Binarios LTFS e utilitarios auxiliares
- Gatekeeper de exclusividade tape-access
- Unit systemd do LTFS
- Diretorios de montagem/trabalho

Tambem pode expor os resultados como metricas Prometheus para dashboards no
Grafana.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("tape-component-quality")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

try:
    from prometheus_client import CollectorRegistry, Gauge, start_http_server

    HAS_PROMETHEUS = True
except ImportError:  # pragma: no cover - fallback simples para ambientes sem dependencia.
    CollectorRegistry = Any  # type: ignore[assignment]
    Gauge = Any  # type: ignore[assignment]
    start_http_server = None  # type: ignore[assignment]
    HAS_PROMETHEUS = False

DEFAULT_HOSTS = ["host0"]
DEFAULT_DEVICE = "/dev/sg0"
DEFAULT_ST_DEVICE = "/dev/st0"
DEFAULT_NST_DEVICE = "/dev/nst0"
DEFAULT_LTFS_SERVICE = "ltfs-lto6.service"
DEFAULT_MOUNT_POINT = "/mnt/tape/lto6"
DEFAULT_WORK_DIR = "/var/lib/ltfs/work"
DEFAULT_EXPORTER_PORT = 9124
DEFAULT_INTERVAL_S = 30

# Configuráveis via env para coincidir com o ambiente NAS.
LTFS_BIN = os.getenv("LTFS_BIN", "/usr/local/ltfs-patched/bin/ltfs")
LTFS_ORCH_LOCK = Path(os.getenv("LTFS_ORCH_LOCK", "/run/lock/ltfs-orchestrator.lock"))
LTFS_EXPORT_DIR = Path(os.getenv("LTFS_EXPORT_DIR", "/run/ltfs-export/lto6"))

# Componentes marcados como críticos recebem peso 2× no score geral.
_CRITICAL_COMPONENTS = frozenset({
    "drive_transport",
    "ltfs_stack",
    "tape_access",
    "ltfs_orchestrator_lock",
})


@dataclass
class ComponentQualityResult:
    """Resultado normalizado de um componente avaliado."""

    component: str
    category: str
    target: str
    score: float
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TapeComponentQualityReport:
    """Relatorio agregado dos componentes da stack de fita."""

    hostname: str
    generated_at: str
    overall_score: float
    components: list[ComponentQualityResult]
    summary: dict[str, int]


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Executa comando com captura segura de stdout/stderr."""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def _component_status_from_score(score: float) -> str:
    """Converte score num status qualitativo."""
    if score >= 90:
        return "pass"
    if score >= 60:
        return "degraded"
    return "fail"


def _status_code(status: str) -> int:
    """Mapeia status textual para codigo inteiro estavel para Prometheus/Grafana."""
    mapping = {
        "fail": 0,
        "degraded": 1,
        "pass": 2,
    }
    return mapping.get(status, -1)


def _binary_available(binary: str) -> tuple[bool, str]:
    """Retorna disponibilidade de um binario no PATH."""
    result = _run(["sh", "-c", f"command -v {binary}"])
    path = (result.stdout or "").strip()
    return result.returncode == 0 and bool(path), path


def _safe_excerpt(text: str, limit: int = 200) -> str:
    """Limita texto para retorno compacto no relatorio."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _mean_score(values: list[float], default: float = 0.0) -> float:
    """Calcula media simples arredondada com fallback seguro."""
    if not values:
        return default
    return round(sum(values) / len(values), 1)


def _derive_fc_subcomponent_scores(report: Any) -> dict[str, float]:
    """Deriva scores por subcomponente fisico FC a partir dos subtestes por porta."""
    test_values: dict[str, list[float]] = {}
    for port in getattr(report, "ports", []):
        for test in getattr(port, "tests", []):
            name = getattr(test, "name", "")
            score = float(getattr(test, "score", 0.0))
            test_values.setdefault(name, []).append(score)

    # Mapeamento heuristico de testes FC para itens fisicos diagnosticaveis.
    cable = _mean_score(
        test_values.get("error_counters", [])
        + test_values.get("lip_stability", [])
        + test_values.get("transfer_latency", []),
        default=0.0,
    )
    sfp = _mean_score(
        test_values.get("error_counters", [])
        + test_values.get("link_state", [])
        + test_values.get("lip_stability", []),
        default=0.0,
    )
    hba_pcie = _mean_score(
        test_values.get("link_state", [])
        + test_values.get("port_speed", [])
        + test_values.get("reconnect_time", []),
        default=0.0,
    )
    fc_switch = _mean_score(
        test_values.get("tgt_reachability", [])
        + test_values.get("link_state", [])
        + test_values.get("reconnect_time", []),
        default=0.0,
    )

    return {
        "fc_cable_lc_lc": cable,
        "fc_sfp_transceiver": sfp,
        "fc_hba_pcie": hba_pcie,
        "fc_switch_path": fc_switch,
    }


def _derive_fc_test_scores(report: Any) -> dict[str, float]:
    """Deriva scores medios dos subtestes FC para paineis tecnicos detalhados."""
    test_values: dict[str, list[float]] = {}
    for port in getattr(report, "ports", []):
        for test in getattr(port, "tests", []):
            name = getattr(test, "name", "")
            score = float(getattr(test, "score", 0.0))
            test_values.setdefault(name, []).append(score)

    mapping = {
        "fc_link_state": "link_state",
        "fc_port_speed": "port_speed",
        "fc_error_counters": "error_counters",
        "fc_lip_stability": "lip_stability",
        "fc_tgt_reachability": "tgt_reachability",
        "fc_transfer_latency": "transfer_latency",
        "fc_reconnect_time": "reconnect_time",
    }
    return {
        component: _mean_score(test_values.get(test_name, []), default=0.0)
        for component, test_name in mapping.items()
    }


def _check_device_nodes(device: str, st_device: str, nst_device: str) -> ComponentQualityResult:
    """Valida presenca dos nodes de device usados pela stack LTFS."""
    paths = [Path(device), Path(st_device), Path(nst_device)]
    existing = [str(path) for path in paths if path.exists()]
    score = round((len(existing) / len(paths)) * 100.0, 1)
    status = _component_status_from_score(score)
    missing = [str(path) for path in paths if not path.exists()]
    message = (
        f"{len(existing)}/{len(paths)} device nodes presentes."
        if not missing
        else f"Faltando: {', '.join(missing)}"
    )
    return ComponentQualityResult(
        component="device_nodes",
        category="device",
        target=device,
        score=score,
        status=status,
        message=message,
        details={
            "existing": existing,
            "missing": missing,
        },
    )


def _check_drive_transport(device: str) -> ComponentQualityResult:
    """Verifica se o drive responde a INQUIRY e Test Unit Ready SCSI."""
    if not Path(device).exists():
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=0.0,
            status="fail",
            message=f"Device {device} nao existe.",
        )

    inq = _run(["sg_inq", device], timeout=15)
    combined = (inq.stderr + inq.stdout).lower()

    if inq.returncode == 0:
        vendor_line = _safe_excerpt(inq.stdout, limit=120)
        # sg_turs distingue "drive pronto" de "drive presente sem midia".
        turs = _run(["sg_turs", device], timeout=10)
        tape_ready = turs.returncode == 0
        score = 100.0 if tape_ready else 85.0
        message = (
            "Drive respondeu ao INQUIRY e midia pronta (sg_turs ok)."
            if tape_ready
            else "Drive respondeu ao INQUIRY mas midia nao pronta (sem fita ou not-ready)."
        )
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=score,
            status=_component_status_from_score(score),
            message=message,
            details={
                "inquiry": vendor_line,
                "sg_turs_rc": turs.returncode,
                "sg_turs_stderr": _safe_excerpt(turs.stderr),
            },
        )

    # Device busy = LTFS tem lock exclusivo = transporte FC ativo.
    if "busy" in combined:
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=90.0,
            status="pass",
            message="Drive em uso pelo sistema (LTFS ativo) — transporte FC operacional.",
            details={"note": "sg_inq bloqueado por lock exclusivo do driver"},
        )

    # Transport failure (Fibre Channel instável — visto em sg1/host7).
    if "transport" in combined or "disrupted" in combined:
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=10.0,
            status="fail",
            message="Falha de transporte FC detectada — verificar cabo/SFP/switch.",
            details={"stderr": _safe_excerpt(inq.stderr or inq.stdout)},
        )

    score = 35.0
    return ComponentQualityResult(
        component="drive_transport",
        category="device",
        target=device,
        score=score,
        status=_component_status_from_score(score),
        message="Drive nao respondeu corretamente ao sg_inq.",
        details={"stderr": _safe_excerpt(inq.stderr or inq.stdout)},
    )


def _check_ltfs_stack() -> ComponentQualityResult:
    """Verifica os binarios principais da stack LTFS, incluindo o binario patched."""
    binaries = ["mkltfs", "ltfsck", "sg_inq", "sg_turs"]
    found: dict[str, str] = {}
    missing: list[str] = []

    # Valida o binário LTFS patched explicitamente (pode não estar no PATH como "ltfs").
    ltfs_bin_path = Path(LTFS_BIN)
    if ltfs_bin_path.exists() and os.access(ltfs_bin_path, os.X_OK):
        found["ltfs"] = str(ltfs_bin_path)
    else:
        # Fallback: tenta localizar no PATH.
        available, path = _binary_available("ltfs")
        if available:
            found["ltfs"] = path
        else:
            missing.append(f"ltfs (LTFS_BIN={LTFS_BIN})")

    for binary in binaries:
        available, path = _binary_available(binary)
        if available:
            found[binary] = path
        else:
            missing.append(binary)

    score = round((len(found) / (len(binaries) + 1)) * 100.0, 1)
    status = _component_status_from_score(score)
    if missing:
        message = f"Binarios ausentes: {', '.join(missing)}"
    else:
        message = f"Stack LTFS presente (binario patched: {found.get('ltfs', '?')})."

    return ComponentQualityResult(
        component="ltfs_stack",
        category="software",
        target="ltfs",
        score=score,
        status=status,
        message=message,
        details={"found": found, "missing": missing, "ltfs_bin_env": LTFS_BIN},
    )


def _check_orchestrator_lock() -> ComponentQualityResult:
    """Verifica se existe lock stale do orchestrador LTFS (PID morto mantendo o lock).

    Lock stale impede qualquer operação orchestrated-mount/stop sem aviso claro.
    Causa raiz de múltiplos deadlocks durante incidentes de sg1/sg0.
    """
    if not LTFS_ORCH_LOCK.exists():
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=100.0,
            status="pass",
            message="Nenhum lock de orchestrador ativo.",
        )

    try:
        content = LTFS_ORCH_LOCK.read_text()
    except OSError as exc:
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=50.0,
            status="degraded",
            message=f"Lock presente mas nao legivel: {exc}",
        )

    m = re.search(r"pid=(\d+)", content)
    if not m:
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=70.0,
            status="degraded",
            message="Lock presente sem PID identificavel — pode ser stale.",
            details={"content": _safe_excerpt(content)},
        )

    pid = int(m.group(1))
    try:
        os.kill(pid, 0)
        # Processo existe — lock legítimo.
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=90.0,
            status="pass",
            message=f"Lock ativo por PID {pid} vivo — orchestrador em operacao.",
            details={"pid": pid, "content": _safe_excerpt(content)},
        )
    except ProcessLookupError:
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=0.0,
            status="fail",
            message=f"Lock STALE: PID {pid} nao existe mais. Remover: rm {LTFS_ORCH_LOCK}",
            details={"pid": pid, "content": _safe_excerpt(content)},
        )
    except PermissionError:
        return ComponentQualityResult(
            component="ltfs_orchestrator_lock",
            category="orchestration",
            target=str(LTFS_ORCH_LOCK),
            score=80.0,
            status="pass",
            message=f"Lock ativo por PID {pid} (pertence a outro uid).",
            details={"pid": pid},
        )


def _check_tape_access_script() -> ComponentQualityResult:
    """Valida o gatekeeper exclusivo tape-access sem tocar na fita."""
    # Procura em múltiplos locais: adjacente ao script e em /usr/local/tools/.
    candidates = [
        Path(__file__).resolve().parent / "tape-access",
        Path("/usr/local/tools/tape-access"),
    ]
    script = next((p for p in candidates if p.exists()), None)
    if script is None:
        script = candidates[0]  # para a mensagem de erro
    if not script.exists():
        return ComponentQualityResult(
            component="tape_access",
            category="orchestration",
            target=str(script),
            score=0.0,
            status="fail",
            message="Script tape-access nao encontrado.",
        )
    if not script.stat().st_mode & 0o111:
        return ComponentQualityResult(
            component="tape_access",
            category="orchestration",
            target=str(script),
            score=20.0,
            status="fail",
            message="Script tape-access existe mas nao e executavel.",
        )

    version = _run([str(script), "version"], timeout=10)
    status_cmd = _run([str(script), "status"], timeout=10)

    score = 100.0 if version.returncode == 0 and status_cmd.returncode == 0 else 50.0
    message = "tape-access operacional."
    if score < 100.0:
        message = "tape-access respondeu parcialmente."

    return ComponentQualityResult(
        component="tape_access",
        category="orchestration",
        target=str(script),
        score=score,
        status=_component_status_from_score(score),
        message=message,
        details={
            "version_stdout": _safe_excerpt(version.stdout),
            "status_stdout": _safe_excerpt(status_cmd.stdout),
            "version_rc": version.returncode,
            "status_rc": status_cmd.returncode,
        },
    )


def _check_service_unit(service_name: str) -> ComponentQualityResult:
    """Avalia a unit systemd do LTFS sem exigir que ela esteja montada."""
    show = _run(
        [
            "systemctl",
            "show",
            service_name,
            "--property=LoadState,ActiveState,UnitFileState,SubState",
            "--value",
        ],
        timeout=15,
    )
    if show.returncode != 0:
        return ComponentQualityResult(
            component="ltfs_service_unit",
            category="service",
            target=service_name,
            score=0.0,
            status="fail",
            message=f"Nao foi possivel inspecionar {service_name}.",
            details={"stderr": _safe_excerpt(show.stderr)},
        )

    values = (show.stdout or "").splitlines()
    while len(values) < 4:
        values.append("")
    load_state, active_state, unit_file_state, sub_state = values[:4]

    transitional_states = {"activating", "reloading"}
    transitional_unit_states = {"enabled", "static", "indirect", "generated", "transient", "linked", "linked-runtime", "alias", "start"}

    if load_state == "not-found":
        score = 0.0
        message = f"Unit {service_name} nao encontrada."
    elif active_state == "active":
        score = 100.0
        message = f"Unit {service_name} ativa ({sub_state})."
    elif active_state in transitional_states:
        score = 80.0
        message = f"Unit {service_name} em inicializacao ({sub_state})."
    elif active_state == "deactivating":
        score = 60.0
        message = f"Unit {service_name} em transicao de parada ({sub_state})."
    elif unit_file_state in transitional_unit_states:
        score = 80.0
        message = f"Unit {service_name} instalada, mas inativa ({active_state})."
    else:
        score = 55.0
        message = f"Unit {service_name} presente, porem desabilitada ({unit_file_state})."

    return ComponentQualityResult(
        component="ltfs_service_unit",
        category="service",
        target=service_name,
        score=score,
        status=_component_status_from_score(score),
        message=message,
        details={
            "load_state": load_state,
            "active_state": active_state,
            "unit_file_state": unit_file_state,
            "sub_state": sub_state,
        },
    )


def _check_runtime_paths(mount_point: str, work_dir: str) -> ComponentQualityResult:
    """Confere os diretorios usados pelo LTFS, incluindo o export Samba."""
    mount_path = Path(mount_point)
    work_path = Path(work_dir)
    path_states: dict[str, bool | str] = {}
    score_parts = 0
    total_checks = 4  # mount_point exists, work_dir exists, mount active, export dir

    for label, path in (("mount_point", mount_path), ("work_dir", work_path)):
        try:
            exists = path.exists()
        except OSError as exc:
            path_states[f"{label}_exists"] = False
            path_states[f"{label}_error"] = f"{type(exc).__name__}: {exc}"
            continue
        path_states[f"{label}_exists"] = exists
        if exists:
            score_parts += 1

    try:
        mount_is_active = mount_path.is_mount() if path_states.get("mount_point_exists") else False
    except OSError as exc:
        mount_is_active = False
        path_states["mount_point_mount_error"] = f"{type(exc).__name__}: {exc}"

    path_states["mount_point_is_mount"] = mount_is_active
    if mount_is_active:
        score_parts += 1

    # Export Samba (/run/ltfs-export/lto6) — necessário para o share CIFS no homelab.
    try:
        export_exists = LTFS_EXPORT_DIR.exists()
    except OSError as exc:
        export_exists = False
        path_states["export_dir_error"] = f"{type(exc).__name__}: {exc}"
    path_states["export_dir"] = str(LTFS_EXPORT_DIR)
    path_states["export_dir_exists"] = export_exists
    if export_exists:
        score_parts += 1

    score = round((score_parts / total_checks) * 100.0, 1)
    if score == 100.0:
        message = "Mount point LTFS ativo, work dir e export Samba presentes."
    elif mount_is_active and not export_exists:
        message = f"LTFS montado mas export Samba ausente ({LTFS_EXPORT_DIR}) — share CIFS indisponivel."
    else:
        message = "Mount point LTFS e/ou diretorios da stack estao ausentes ou desmontados."

    return ComponentQualityResult(
        component="runtime_paths",
        category="filesystem",
        target=mount_point,
        score=score,
        status=_component_status_from_score(score),
        message=message,
        details=path_states,
    )


def _check_hba_quality(hosts: list[str], device: str) -> list[ComponentQualityResult]:
    """Reaproveita o fc_hba_tester para avaliar qualidade das portas HBA."""
    try:
        try:
            from tools.fc_hba_tester import run_dual_hba_test
        except ImportError:
            # Fallback para instalacao standalone em /usr/local/tools.
            from fc_hba_tester import run_dual_hba_test
    except ImportError as exc:
        logger.exception("Falha ao importar fc_hba_tester")
        return [
            ComponentQualityResult(
                component="fc_diagnostic_core",
                category="hba",
                target="import",
                score=0.0,
                status="fail",
                message="Nao foi possivel importar tools.fc_hba_tester.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_cable_lc_lc",
                category="hba",
                target="cable",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: cabo LC-LC nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_sfp_transceiver",
                category="hba",
                target="sfp",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: SFP nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_hba_pcie",
                category="hba",
                target="hba",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: HBA PCIe nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_switch_path",
                category="hba",
                target="switch",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: caminho de switch nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_link_state",
                category="hba",
                target="link",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: estado do link nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_port_speed",
                category="hba",
                target="speed",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: velocidade da porta nao avaliada.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_error_counters",
                category="hba",
                target="errors",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: contadores de erro nao avaliados.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_lip_stability",
                category="hba",
                target="stability",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: estabilidade de LIP nao avaliada.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_tgt_reachability",
                category="hba",
                target="target",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: alcance de target nao avaliado.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_transfer_latency",
                category="hba",
                target="latency",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: latencia de transferencia nao avaliada.",
                details={"error": str(exc)},
            ),
            ComponentQualityResult(
                component="fc_reconnect_time",
                category="hba",
                target="reconnect",
                score=0.0,
                status="fail",
                message="Sem diagnostico FC: tempo de reconexao nao avaliado.",
                details={"error": str(exc)},
            ),
        ]

    report = run_dual_hba_test(hosts=hosts, device=device, stability_window=0, skip_slow=True)
    components: list[ComponentQualityResult] = []
    for port in report.ports:
        components.append(
            ComponentQualityResult(
                component=f"fc_{port.host}",
                category="hba",
                target=port.host,
                score=port.score,
                status=_component_status_from_score(port.score),
                message=port.recommendation,
                details={
                    "pci_slot": port.pci_slot,
                    "grade": port.grade,
                    "tests": [
                        {
                            "name": test.name,
                            "score": test.score,
                            "passed": test.passed,
                            "message": test.message,
                        }
                        for test in port.tests
                    ],
                },
            )
        )

    for name, score in _derive_fc_subcomponent_scores(report).items():
        if name == "fc_cable_lc_lc":
            target = "cable"
            message = "Qualidade inferida do cabo LC-LC pelo comportamento do link FC."
        elif name == "fc_sfp_transceiver":
            target = "sfp"
            message = "Qualidade inferida do transceptor SFP por erros/estado/estabilidade."
        elif name == "fc_hba_pcie":
            target = "hba"
            message = "Qualidade inferida da controladora HBA PCIe por estado, speed e reconexao."
        else:
            target = "switch"
            message = "Qualidade inferida do caminho de switch FC por reachability e reconexao."

        components.append(
            ComponentQualityResult(
                component=name,
                category="hba",
                target=target,
                score=score,
                status=_component_status_from_score(score),
                message=message,
            )
        )

    detailed_test_targets = {
        "fc_link_state": "link",
        "fc_port_speed": "speed",
        "fc_error_counters": "errors",
        "fc_lip_stability": "stability",
        "fc_tgt_reachability": "target",
        "fc_transfer_latency": "latency",
        "fc_reconnect_time": "reconnect",
    }
    detailed_test_messages = {
        "fc_link_state": "Estado online/offline medio das portas FC.",
        "fc_port_speed": "Qualidade da velocidade negociada nas portas FC.",
        "fc_error_counters": "Qualidade baseada em CRC/loss/link_failure.",
        "fc_lip_stability": "Estabilidade do link FC durante eventos LIP.",
        "fc_tgt_reachability": "Capacidade de enxergar target/dispositivo na malha FC.",
        "fc_transfer_latency": "Latencia de transferencia SCSI via FC.",
        "fc_reconnect_time": "Tempo de reconexao apos oscilacao de link.",
    }
    for name, score in _derive_fc_test_scores(report).items():
        components.append(
            ComponentQualityResult(
                component=name,
                category="hba",
                target=detailed_test_targets[name],
                score=score,
                status=_component_status_from_score(score),
                message=detailed_test_messages[name],
            )
        )

    return components


def collect_component_quality(
    hosts: list[str] | None = None,
    device: str = DEFAULT_DEVICE,
    st_device: str = DEFAULT_ST_DEVICE,
    nst_device: str = DEFAULT_NST_DEVICE,
    service_name: str = DEFAULT_LTFS_SERVICE,
    mount_point: str = DEFAULT_MOUNT_POINT,
    work_dir: str = DEFAULT_WORK_DIR,
) -> TapeComponentQualityReport:
    """Coleta a qualidade de todos os componentes da stack de fita."""
    effective_hosts = hosts or list(DEFAULT_HOSTS)
    components: list[ComponentQualityResult] = []
    components.extend(_check_hba_quality(effective_hosts, device))
    components.append(_check_device_nodes(device, st_device, nst_device))
    components.append(_check_drive_transport(device))
    components.append(_check_ltfs_stack())
    components.append(_check_tape_access_script())
    components.append(_check_orchestrator_lock())
    components.append(_check_service_unit(service_name))
    components.append(_check_runtime_paths(mount_point, work_dir))

    # Score ponderado: componentes críticos têm peso 2× para que uma falha crítica
    # puxe o agregado abaixo de 60 mesmo com muitos checks passando.
    if components:
        total_weight = sum(2 if item.component in _CRITICAL_COMPONENTS else 1 for item in components)
        weighted_sum = sum(
            item.score * (2 if item.component in _CRITICAL_COMPONENTS else 1)
            for item in components
        )
        overall_score = round(weighted_sum / total_weight, 1)
    else:
        overall_score = 0.0

    summary = {
        "pass": sum(1 for item in components if item.status == "pass"),
        "degraded": sum(1 for item in components if item.status == "degraded"),
        "fail": sum(1 for item in components if item.status == "fail"),
    }
    return TapeComponentQualityReport(
        hostname=socket.gethostname(),
        generated_at=datetime.now().isoformat(),
        overall_score=overall_score,
        components=components,
        summary=summary,
    )


def report_to_dict(report: TapeComponentQualityReport) -> dict[str, Any]:
    """Converte relatorio em dicionario JSON-serializavel."""
    return asdict(report)


def render_text_report(report: TapeComponentQualityReport) -> str:
    """Gera relatorio textual resumido para terminal."""
    lines = [
        "Tape Component Quality Report",
        f"Host: {report.hostname}",
        f"Generated at: {report.generated_at}",
        f"Overall score: {report.overall_score:.1f}",
        "",
    ]
    for item in report.components:
        lines.append(
            f"- {item.component} [{item.category}] score={item.score:.1f} "
            f"status={item.status} target={item.target} :: {item.message}"
        )
    return "\n".join(lines)


class TapeComponentQualityExporter:
    """Exporter Prometheus dos scores de qualidade dos componentes."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        """Inicializa gauges Prometheus em registry dedicado."""
        if not HAS_PROMETHEUS:
            raise RuntimeError("prometheus_client nao esta instalado")

        self.registry = registry or CollectorRegistry()
        self._known_labels: set[tuple[str, str, str]] = set()
        self.overall_score = Gauge(
            "tape_component_quality_overall_score",
            "Score medio da stack de fita",
            registry=self.registry,
        )
        self.last_run_timestamp = Gauge(
            "tape_component_quality_last_run_timestamp_seconds",
            "Timestamp da ultima coleta de qualidade da stack de fita",
            registry=self.registry,
        )
        self.component_score = Gauge(
            "tape_component_quality_score",
            "Score por componente da stack de fita",
            ["component", "category", "target"],
            registry=self.registry,
        )
        self.component_status = Gauge(
            "tape_component_quality_status_code",
            "Codigo de status por componente (0=fail,1=degraded,2=pass)",
            ["component", "category", "target"],
            registry=self.registry,
        )

    def update(self, report: TapeComponentQualityReport) -> None:
        """Atualiza os gauges com um novo relatorio."""
        active_labels = {
            (item.component, item.category, item.target)
            for item in report.components
        }
        stale_labels = self._known_labels - active_labels
        for labels in stale_labels:
            self.component_score.remove(*labels)
            self.component_status.remove(*labels)

        for item in report.components:
            labels = (item.component, item.category, item.target)
            self.component_score.labels(*labels).set(item.score)
            self.component_status.labels(*labels).set(_status_code(item.status))

        self._known_labels = active_labels
        self.overall_score.set(report.overall_score)
        self.last_run_timestamp.set(time.time())


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parseia argumentos da CLI."""
    parser = argparse.ArgumentParser(description="Agente de qualidade da stack de fita")
    parser.add_argument("--hosts", default=",".join(DEFAULT_HOSTS), help="Hosts FC separados por virgula")
    parser.add_argument("--device", default=DEFAULT_DEVICE, help="Device sg do drive")
    parser.add_argument("--st-device", default=DEFAULT_ST_DEVICE, help="Device st do drive")
    parser.add_argument("--nst-device", default=DEFAULT_NST_DEVICE, help="Device nst do drive")
    parser.add_argument("--service", default=DEFAULT_LTFS_SERVICE, help="Unit systemd do LTFS")
    parser.add_argument("--mount-point", default=DEFAULT_MOUNT_POINT, help="Mount point LTFS")
    parser.add_argument("--work-dir", default=DEFAULT_WORK_DIR, help="Diretorio de trabalho LTFS")
    parser.add_argument("--json", action="store_true", help="Imprime JSON no stdout")
    parser.add_argument("--output", help="Arquivo para salvar snapshot JSON")
    parser.add_argument("--exporter", action="store_true", help="Executa loop exportando metricas Prometheus")
    parser.add_argument("--port", type=int, default=DEFAULT_EXPORTER_PORT, help="Porta do exporter Prometheus")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_S, help="Intervalo entre coletas no modo exporter")
    return parser.parse_args(list(argv) if argv is not None else None)


def _save_snapshot(report: TapeComponentQualityReport, output_path: str | None) -> None:
    """Salva snapshot JSON em arquivo, se solicitado."""
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2) + "\n")


def _run_exporter(args: argparse.Namespace) -> int:
    """Executa loop de coleta e exportacao Prometheus."""
    if not HAS_PROMETHEUS or start_http_server is None:
        logger.error("prometheus_client nao esta disponivel")
        return 1

    exporter = TapeComponentQualityExporter()
    start_http_server(args.port, registry=exporter.registry)
    logger.info("Exporter de qualidade de fita escutando na porta %d", args.port)

    while True:
        try:
            report = collect_component_quality(
                hosts=[host for host in args.hosts.split(",") if host],
                device=args.device,
                st_device=args.st_device,
                nst_device=args.nst_device,
                service_name=args.service,
                mount_point=args.mount_point,
                work_dir=args.work_dir,
            )
            exporter.update(report)
            _save_snapshot(report, args.output)
            logger.info("Coleta concluida: overall_score=%.1f", report.overall_score)
        except Exception:
            logger.exception("Erro na coleta — exporter mantido ativo, tentando novamente em %ds", args.interval)
        time.sleep(args.interval)


def main(argv: Iterable[str] | None = None) -> int:
    """Ponto de entrada da CLI."""
    args = _parse_args(argv)
    if args.exporter:
        return _run_exporter(args)

    report = collect_component_quality(
        hosts=[host for host in args.hosts.split(",") if host],
        device=args.device,
        st_device=args.st_device,
        nst_device=args.nst_device,
        service_name=args.service,
        mount_point=args.mount_point,
        work_dir=args.work_dir,
    )
    _save_snapshot(report, args.output)

    if args.json:
        print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        print(render_text_report(report))

    return 0 if report.summary["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
