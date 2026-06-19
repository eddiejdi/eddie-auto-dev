#!/usr/bin/env python3
"""Gerador diário de diagnóstico AI para a stack de fita LTO6/FC via Ollama.

Consulta o Prometheus para obter os scores atuais de todos os componentes,
envia ao Ollama (GPU0 → GPU1 fallback) para gerar um descritivo técnico
detalhado em português, e atualiza o painel de diagnóstico AI no Grafana
via API.

Execução: uma vez por dia via systemd timer. Guarda timestamp da última
geração em STATE_FILE para evitar dupla execução.

Uso:
    python3 tools/tape_quality_ollama_narrator.py [--force] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("tape-quality-narrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Configurações de infraestrutura
# ---------------------------------------------------------------------------
PROMETHEUS_URL: str = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
GRAFANA_URL: str = os.environ.get("GRAFANA_URL", "http://localhost:3002/grafana")
GRAFANA_USER: str = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASS: str = os.environ.get("GRAFANA_PASS", "Shared@2026")

OLLAMA_GPU0: str = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_GPU1: str = os.environ.get("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "shared-coder")

DASHBOARD_UID: str = "tape-component-quality-v1"
AI_PANEL_ID: int = 50  # painel de diagnóstico AI (adicionado no dashboard)

STATE_FILE: Path = Path(
    os.environ.get("NARRATOR_STATE_FILE", "/var/lib/tape-quality/narrator_state.json")
)

# ---------------------------------------------------------------------------
# Categorização de componentes para o prompt
# ---------------------------------------------------------------------------

# Mapeamento de component-id → descrição humana clara para o modelo
COMPONENT_DESCRIPTIONS: dict[str, str] = {
    # Hardware FC
    "fc_host0": "Porta HBA FC host0 (QLogic QLE2460, PCIe)",
    "fc_host7": "Porta HBA FC host7 (QLogic QLE2460, PCIe)",
    "fc_cable_lc_lc": "Cabo de fibra óptica LC-LC entre HBA e drive",
    "fc_sfp_transceiver": "Módulo SFP (transceptor) instalado no HBA",
    "fc_hba_pcie": "Controladora HBA PCIe (placa de rede Fibre Channel)",
    "fc_switch_path": "Caminho no switch FC / zoneamento",
    # Subtestes FC
    "fc_link_state": "Estado do link FC (online/offline) nas portas",
    "fc_port_speed": "Velocidade negociada no link FC (ex: 4Gbps, 8Gbps)",
    "fc_error_counters": "Contadores de erro FC: CRC, loss_of_signal, link_failure",
    "fc_lip_stability": "Estabilidade do link durante Loop Initialization Primitives (LIP)",
    "fc_tgt_reachability": "Visibilidade do drive LTO6 como target SCSI na malha FC",
    "fc_transfer_latency": "Latência de transferência SCSI sobre FC",
    "fc_reconnect_time": "Tempo de reconexão após oscilação de link FC",
    # Hardware drive
    "drive_transport": "Drive LTO6: resposta ao SCSI INQUIRY via /dev/sg0",
    "device_nodes": "Nodes de dispositivo SCSI: /dev/sg0, /dev/st0, /dev/nst0",
    # Software
    "ltfs_stack": "Binários LTFS instalados: ltfs, mkltfs, ltfsck, sg_inq, sg_turs",
    "tape_access": "Script tape-access (gatekeeper exclusivo de acesso à fita)",
    "ltfs_service_unit": "Serviço systemd ltfs-lto6.service (active/running)",
    "runtime_paths": "Diretórios de runtime: /mnt/tape/lto6, /var/lib/ltfs/work",
}

# Quais componentes são hardware (causa raiz) vs software (impacto cascata)
HARDWARE_COMPONENTS: frozenset[str] = frozenset({
    "fc_host0", "fc_host7", "fc_cable_lc_lc", "fc_sfp_transceiver",
    "fc_hba_pcie", "fc_switch_path", "fc_link_state", "fc_port_speed",
    "fc_error_counters", "fc_lip_stability", "fc_tgt_reachability",
    "fc_transfer_latency", "fc_reconnect_time", "drive_transport", "device_nodes",
})

SOFTWARE_COMPONENTS: frozenset[str] = frozenset({
    "ltfs_stack", "tape_access", "ltfs_service_unit", "runtime_paths",
})

# Relações de cascata conhecidas: falha em X → causa falha provável em Y
CASCADE_MAP: dict[str, list[str]] = {
    "fc_link_state": ["device_nodes", "drive_transport", "ltfs_service_unit", "runtime_paths"],
    "fc_tgt_reachability": ["device_nodes", "drive_transport", "ltfs_service_unit"],
    "drive_transport": ["ltfs_service_unit", "runtime_paths"],
    "device_nodes": ["ltfs_service_unit", "runtime_paths"],
}


# ---------------------------------------------------------------------------
# Consulta Prometheus
# ---------------------------------------------------------------------------

def query_prometheus(metric: str, timeout: int = 10) -> list[dict[str, Any]]:
    """Retorna lista de resultados do Prometheus para uma métrica instantânea."""
    try:
        resp = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query",
            params={"query": metric},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return []
        return data.get("data", {}).get("result", [])
    except Exception as exc:
        logger.warning("Prometheus indisponível: %s", exc)
        return []


def fetch_component_scores() -> dict[str, float]:
    """Retorna {component_id: score_0_a_100} consultando Prometheus."""
    results = query_prometheus("tape_component_quality_score")
    scores: dict[str, float] = {}
    for item in results:
        comp = item.get("metric", {}).get("component", "")
        try:
            scores[comp] = float(item["value"][1])
        except (KeyError, ValueError, IndexError):
            pass
    return scores


def fetch_overall_score() -> float | None:
    """Retorna o score geral da stack."""
    results = query_prometheus("tape_component_quality_overall_score")
    if results:
        try:
            return float(results[0]["value"][1])
        except (KeyError, ValueError, IndexError):
            pass
    return None


# ---------------------------------------------------------------------------
# Construção do prompt
# ---------------------------------------------------------------------------

def _classify_score(score: float) -> str:
    """Retorna emoji + classificação textual do score."""
    if score >= 70:
        return "🟢 OK"
    if score >= 30:
        return "🟡 DEGRADADO"
    return "🔴 FALHA"


def build_prompt(scores: dict[str, float], overall: float | None) -> str:
    """Constrói o prompt técnico detalhado para o Ollama."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    overall_str = f"{overall:.1f}%" if overall is not None else "N/D"

    # Separar por categoria e por severidade
    failing_hw = {k: v for k, v in scores.items() if k in HARDWARE_COMPONENTS and v < 30}
    degraded_hw = {k: v for k, v in scores.items() if k in HARDWARE_COMPONENTS and 30 <= v < 70}
    ok_hw = {k: v for k, v in scores.items() if k in HARDWARE_COMPONENTS and v >= 70}

    failing_sw = {k: v for k, v in scores.items() if k in SOFTWARE_COMPONENTS and v < 30}
    degraded_sw = {k: v for k, v in scores.items() if k in SOFTWARE_COMPONENTS and 30 <= v < 70}
    ok_sw = {k: v for k, v in scores.items() if k in SOFTWARE_COMPONENTS and v >= 70}

    # Detectar cascata: quais falhas de software são consequência de hardware
    cascade_victims: set[str] = set()
    for hw_comp, sw_comps in CASCADE_MAP.items():
        if scores.get(hw_comp, 100) < 30:
            for sw_comp in sw_comps:
                if scores.get(sw_comp, 100) < 30:
                    cascade_victims.add(sw_comp)

    lines: list[str] = [
        "Você é um engenheiro especialista em storage SAN/LTO e Fibre Channel.",
        "Analise o estado atual da stack de fita LTO6 e gere um diagnóstico técnico detalhado em português.",
        "",
        f"Data/Hora: {now}",
        f"Score Geral: {overall_str}",
        "",
        "=== COMPONENTES DE HARDWARE ===",
    ]

    for comp, score in {**failing_hw, **degraded_hw, **ok_hw}.items():
        desc = COMPONENT_DESCRIPTIONS.get(comp, comp)
        lines.append(f"  {_classify_score(score)} [{score:.0f}%] {comp}: {desc}")

    lines += ["", "=== COMPONENTES DE SOFTWARE ==="]
    for comp, score in {**failing_sw, **degraded_sw, **ok_sw}.items():
        desc = COMPONENT_DESCRIPTIONS.get(comp, comp)
        cascade_note = " ⚠️ (provável cascata de falha de hardware)" if comp in cascade_victims else ""
        lines.append(f"  {_classify_score(score)} [{score:.0f}%] {comp}: {desc}{cascade_note}")

    if cascade_victims:
        lines += [
            "",
            "=== ANÁLISE DE CASCATA DETECTADA ===",
            "Os seguintes componentes de software falharam como CONSEQUÊNCIA de falha de hardware,",
            "não por erro de configuração ou bug de software:",
        ]
        for v in cascade_victims:
            lines.append(f"  - {v}")

    lines += [
        "",
        "=== INSTRUÇÃO ===",
        "Gere um diagnóstico técnico completo com as seguintes seções:",
        "1. **Resumo Executivo** (2-3 frases): estado geral e causa raiz principal",
        "2. **Falhas Críticas — Hardware** (uma subseção por componente com score < 30%):",
        "   - O que o score indica sobre o componente físico",
        "   - Causa provável (ex: cabo danificado, SFP queimado, slot PCIe com problema)",
        "   - Comandos de diagnóstico para confirmar a causa",
        "   - Ação de remediação recomendada",
        "3. **Componentes Degradados** (score 30-69%): análise e ação preventiva",
        "4. **Impacto em Cascata**: explicar quais falhas de software são consequência do hardware",
        "5. **Prioridade de Ação**: lista ordenada do que fazer primeiro",
        "6. **Comandos Úteis**: snippet pronto para colar no terminal para diagnosticar",
        "",
        "Use linguagem técnica precisa. Seja específico sobre hardware LTO6, HBA QLogic, FC.",
        "Não inclua disclaimers. Formate em Markdown.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chamada Ollama GPU-first
# ---------------------------------------------------------------------------

def call_ollama(prompt: str, timeout: int = 120) -> str | None:
    """Chama Ollama GPU0 → GPU1 → retorna None se ambos indisponíveis."""
    for gpu_url in (OLLAMA_GPU0, OLLAMA_GPU1):
        try:
            logger.info("Tentando Ollama em %s …", gpu_url)
            resp = requests.post(
                f"{gpu_url}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1200,
                    },
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            if text:
                logger.info("Ollama respondeu via %s (%d chars)", gpu_url, len(text))
                return text
        except Exception as exc:
            logger.warning("Ollama %s indisponível: %s", gpu_url, exc)

    logger.error("Ambas as GPUs indisponíveis. Narração cancelada.")
    return None


# ---------------------------------------------------------------------------
# Atualização do painel Grafana
# ---------------------------------------------------------------------------

def get_dashboard(uid: str) -> dict[str, Any] | None:
    """Obtém o dashboard JSON via API do Grafana."""
    try:
        resp = requests.get(
            f"{GRAFANA_URL}/api/dashboards/uid/{uid}",
            auth=(GRAFANA_USER, GRAFANA_PASS),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Erro ao obter dashboard %s: %s", uid, exc)
        return None


def update_ai_panel_content(dashboard_data: dict[str, Any], content: str) -> dict[str, Any]:
    """Localiza o painel AI_PANEL_ID e atualiza seu conteúdo."""
    dashboard = dashboard_data.get("dashboard", {})
    panels: list[dict[str, Any]] = dashboard.get("panels", [])

    found = False
    for panel in panels:
        if panel.get("id") == AI_PANEL_ID:
            panel.setdefault("options", {})["content"] = content
            found = True
            logger.info("Painel AI (id=%d) atualizado.", AI_PANEL_ID)
            break

    if not found:
        logger.warning("Painel id=%d não encontrado. Skipping update.", AI_PANEL_ID)

    return dashboard_data


def push_dashboard(dashboard_data: dict[str, Any]) -> bool:
    """Faz POST do dashboard atualizado no Grafana."""
    dashboard = dashboard_data.get("dashboard", {})
    payload = {
        "dashboard": dashboard,
        "overwrite": True,
        "folderId": dashboard_data.get("meta", {}).get("folderId", 0),
    }
    try:
        resp = requests.post(
            f"{GRAFANA_URL}/api/dashboards/db",
            json=payload,
            auth=(GRAFANA_USER, GRAFANA_PASS),
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("status") == "success":
            logger.info("Dashboard atualizado: %s", result.get("url", ""))
            return True
        logger.warning("Grafana retornou: %s", result)
        return False
    except Exception as exc:
        logger.error("Erro ao atualizar dashboard: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Controle de execução diária
# ---------------------------------------------------------------------------

def already_ran_today() -> bool:
    """Retorna True se a narração já foi gerada hoje."""
    if not STATE_FILE.exists():
        return False
    try:
        state = json.loads(STATE_FILE.read_text())
        last_run = state.get("last_run_date", "")
        return last_run == date.today().isoformat()
    except Exception:
        return False


def save_state(narration: str) -> None:
    """Persiste o estado com a data de hoje e o texto gerado."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "last_run_date": date.today().isoformat(),
        "last_run_ts": datetime.now().isoformat(),
        "narration_length": len(narration),
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    logger.info("Estado salvo em %s", STATE_FILE)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def build_narration_header(scores: dict[str, float], overall: float | None) -> str:
    """Gera cabeçalho Markdown com metadados para o painel Grafana."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    overall_str = f"{overall:.1f}%" if overall is not None else "N/D"
    failing = sum(1 for v in scores.values() if v < 30)
    degraded = sum(1 for v in scores.values() if 30 <= v < 70)
    ok_count = sum(1 for v in scores.values() if v >= 70)
    return (
        f"_Gerado em {now} via Ollama ({OLLAMA_MODEL}) — "
        f"Score geral: **{overall_str}** | "
        f"🔴 {failing} falha(s) | 🟡 {degraded} degradado(s) | 🟢 {ok_count} OK_\n\n---\n\n"
    )


def run(force: bool = False, dry_run: bool = False) -> int:
    """Executa o fluxo completo de narração.

    Args:
        force: Ignora o controle de execução diária.
        dry_run: Gera o texto mas não atualiza o Grafana.

    Returns:
        Código de saída (0=sucesso, 1=erro, 2=já rodou hoje).
    """
    if not force and already_ran_today():
        logger.info("Narração já gerada hoje. Use --force para forçar.")
        return 2

    logger.info("Coletando scores do Prometheus…")
    scores = fetch_component_scores()
    overall = fetch_overall_score()

    if not scores:
        logger.error("Nenhum score obtido do Prometheus. Abortando.")
        return 1

    logger.info("Construindo prompt para Ollama (%d componentes)…", len(scores))
    prompt = build_prompt(scores, overall)

    narration = call_ollama(prompt)
    if narration is None:
        logger.error("Ollama indisponível. Narração não gerada.")
        return 1

    header = build_narration_header(scores, overall)
    full_content = header + narration

    if dry_run:
        print(full_content)
        logger.info("Modo dry-run: sem atualização no Grafana.")
        return 0

    logger.info("Atualizando painel Grafana (uid=%s, panel=%d)…", DASHBOARD_UID, AI_PANEL_ID)
    dashboard_data = get_dashboard(DASHBOARD_UID)
    if dashboard_data is None:
        logger.error("Não foi possível obter dashboard. Abortando.")
        return 1

    updated = update_ai_panel_content(dashboard_data, full_content)
    success = push_dashboard(updated)

    if success:
        save_state(full_content)
        logger.info("Narração concluída com sucesso.")
        return 0

    logger.error("Falha ao persistir narração no Grafana.")
    return 1


def main() -> None:
    """Ponto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Gera descritivo AI da stack de fita via Ollama (1x/dia)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força geração mesmo se já rodou hoje.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Imprime o descritivo gerado sem atualizar o Grafana.",
    )
    args = parser.parse_args()
    sys.exit(run(force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
