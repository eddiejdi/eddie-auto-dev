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

DEFAULT_HOSTS = ["host0", "host7"]
DEFAULT_DEVICE = "/dev/sg1"
DEFAULT_ST_DEVICE = "/dev/st1"
DEFAULT_NST_DEVICE = "/dev/nst1"
DEFAULT_LTFS_SERVICE = "ltfs-lto6.service"
DEFAULT_MOUNT_POINT = "/mnt/tape/lto6"
DEFAULT_WORK_DIR = "/var/lib/ltfs/work"
DEFAULT_EXPORTER_PORT = 9124
DEFAULT_INTERVAL_S = 300


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
    """Verifica se o drive responde a INQUIRY SCSI sem depender da fita."""
    if not Path(device).exists():
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=0.0,
            status="fail",
            message=f"Device {device} nao existe.",
        )

    result = _run(["sg_inq", device], timeout=15)
    if result.returncode == 0:
        vendor_line = _safe_excerpt(result.stdout, limit=120)
        return ComponentQualityResult(
            component="drive_transport",
            category="device",
            target=device,
            score=100.0,
            status="pass",
            message="Drive respondeu ao sg_inq com sucesso.",
            details={"inquiry": vendor_line},
        )

    score = 35.0
    return ComponentQualityResult(
        component="drive_transport",
        category="device",
        target=device,
        score=score,
        status=_component_status_from_score(score),
        message="Drive nao respondeu corretamente ao sg_inq.",
        details={"stderr": _safe_excerpt(result.stderr or result.stdout)},
    )


def _check_ltfs_stack() -> ComponentQualityResult:
    """Verifica os binarios principais da stack LTFS."""
    binaries = ["ltfs", "mkltfs", "ltfsck", "sg_inq", "sg_turs"]
    found: dict[str, str] = {}
    missing: list[str] = []

    for binary in binaries:
        available, path = _binary_available(binary)
        if available:
            found[binary] = path
        else:
            missing.append(binary)

    score = round((len(found) / len(binaries)) * 100.0, 1)
    status = _component_status_from_score(score)
    if missing:
        message = f"Binarios ausentes: {', '.join(missing)}"
    else:
        message = "Stack LTFS basica presente no sistema."

    return ComponentQualityResult(
        component="ltfs_stack",
        category="software",
        target="ltfs",
        score=score,
        status=status,
        message=message,
        details={"found": found, "missing": missing},
    )


def _check_tape_access_script() -> ComponentQualityResult:
    """Valida o gatekeeper exclusivo tape-access sem tocar na fita."""
    script = Path(__file__).resolve().parent / "tape-access"
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

    if load_state == "not-found":
        score = 0.0
        message = f"Unit {service_name} nao encontrada."
    elif active_state == "active":
        score = 100.0
        message = f"Unit {service_name} ativa ({sub_state})."
    elif unit_file_state in {"enabled", "static", "indirect"}:
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
    """Confere os diretorios usados pelo LTFS."""
    mount_path = Path(mount_point)
    work_path = Path(work_dir)
    present = [path for path in [mount_path, work_path] if path.exists()]
    score = round((len(present) / 2) * 100.0, 1)
    return ComponentQualityResult(
        component="runtime_paths",
        category="filesystem",
        target=mount_point,
        score=score,
        status=_component_status_from_score(score),
        message=(
            "Mount point e work dir presentes."
            if score == 100.0
            else "Um ou mais diretorios da stack LTFS estao ausentes."
        ),
        details={
            "mount_point_exists": mount_path.exists(),
            "work_dir_exists": work_path.exists(),
        },
    )


def _check_hba_quality(hosts: list[str], device: str) -> list[ComponentQualityResult]:
    """Reaproveita o fc_hba_tester para avaliar qualidade das portas HBA."""
    try:
        from tools.fc_hba_tester import run_dual_hba_test
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
    components.append(_check_service_unit(service_name))
    components.append(_check_runtime_paths(mount_point, work_dir))

    if components:
        overall_score = round(sum(item.score for item in components) / len(components), 1)
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
