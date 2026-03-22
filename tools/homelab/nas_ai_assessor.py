#!/usr/bin/env python3
"""Assess NAS/LTO health from Prometheus and publish an HTML panel in Grafana."""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3002")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "Rpa_four_all!")
GRAFANA_DASHBOARD_UID = os.environ.get("GRAFANA_DASHBOARD_UID", "nas-rpa4all-omv")
GRAFANA_FOLDER_UID = os.environ.get("GRAFANA_FOLDER_UID", "fffxoniykngn4e")
PANEL_ID = int(os.environ.get("GRAFANA_PANEL_ID", "31"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT_SECONDS", "20"))


def http_json(
    url: str,
    *,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    auth: Optional[tuple[str, str]] = None,
) -> Any:
    body = None
    headers = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth is not None:
        token = ("%s:%s" % auth).encode("utf-8")
        headers["Authorization"] = "Basic " + __import__("base64").b64encode(token).decode("ascii")
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.load(resp)


def prom_query(expr: str) -> Optional[float]:
    query = urllib.parse.urlencode({"query": expr})
    url = f"{PROMETHEUS_URL}/api/v1/query?{query}"
    data = http_json(url)
    result = data.get("data", {}).get("result", [])
    if not result:
        return None
    try:
        return float(result[0]["value"][1])
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def collect_metrics() -> Dict[str, Optional[float]]:
    queries = {
        "ltfs_service_up": 'nas_ltfs_service_up{job="nas-node-exporter",instance="rpa4all-nas-001",exported_service="ltfs-lto6.service"}',
        "ltfs_mount_up": 'nas_ltfs_mount_up{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}',
        "ltfs_read_only": 'nas_ltfs_read_only{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}',
        "tape_used_bytes": 'nas_ltfs_used_bytes{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}',
        "tape_avail_bytes": 'nas_ltfs_avail_bytes{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}',
        "tape_size_bytes": 'nas_ltfs_size_bytes{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}',
        "drive_ready": 'nas_tape_drive_ready{job="nas-node-exporter",instance="rpa4all-nas-001",device="HUL831AMRM"}',
        "medium_loaded": 'nas_tape_medium_loaded{job="nas-node-exporter",instance="rpa4all-nas-001",device="HUL831AMRM"}',
        "compression_enabled": 'nas_tape_compression_enabled{job="nas-node-exporter",instance="rpa4all-nas-001",device="HUL831AMRM"}',
        "write_timeouts_24h": 'nas_ltfs_write_timeout_events_24h{job="nas-node-exporter",instance="rpa4all-nas-001",exported_service="ltfs-lto6.service"}',
        "fc_abort_events_24h": 'nas_fc_abort_events_24h{job="nas-node-exporter",instance="rpa4all-nas-001",driver="qla2xxx"}',
        "tape_write_bps": 'clamp_min(rate(nas_ltfs_used_bytes{job="nas-node-exporter",instance="rpa4all-nas-001",mountpoint="/mnt/tape/lto6"}[5m]), 0)',
        "buffer_occupancy_pct": 'homelab_ltfs_flush_buffer_usage_percent{job="node-exporter",instance="node-exporter:9100"}',
        "flush_bps": 'clamp_min(rate(homelab_ltfs_flush_bytes_total{job="node-exporter",instance="node-exporter:9100"}[5m]), 0)',
        "flush_files_per_min": '60 * clamp_min(rate(homelab_ltfs_flush_files_total{job="node-exporter",instance="node-exporter:9100"}[15m]), 0)',
        "last_run_seconds": 'homelab_ltfs_flush_last_run_duration_seconds{job="node-exporter",instance="node-exporter:9100"}',
        "last_run_bytes": 'homelab_ltfs_flush_last_run_bytes{job="node-exporter",instance="node-exporter:9100"}',
        "last_run_files": 'homelab_ltfs_flush_last_run_files{job="node-exporter",instance="node-exporter:9100"}',
        "flush_runs_total": 'homelab_ltfs_flush_runs_total{job="node-exporter",instance="node-exporter:9100"}',
    }
    return {name: prom_query(expr) for name, expr in queries.items()}


def human_bytes(value: Optional[float]) -> str:
    if value is None:
        return "n/d"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(value)
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value:.1f} B"


def human_rate(value: Optional[float]) -> str:
    if value is None:
        return "n/d"
    return human_bytes(value) + "/s"


def status_label(value: Optional[float], good_text: str, bad_text: str, na_text: str = "N/A") -> str:
    if value is None or value < 0:
        return na_text
    return good_text if value >= 1 else bad_text


def build_summary(metrics: Dict[str, Optional[float]]) -> Dict[str, Any]:
    issues: List[str] = []
    positives: List[str] = []

    if metrics["ltfs_service_up"] == 1 and metrics["ltfs_mount_up"] == 1:
        positives.append("LTFS ativo e montado")
    else:
        issues.append("LTFS indisponível ou não montado")

    if metrics["ltfs_read_only"] == 1:
        issues.append("LTFS em modo somente leitura")
    else:
        positives.append("LTFS em leitura e escrita")

    if metrics["drive_ready"] == 1 and metrics["medium_loaded"] == 1:
        positives.append("Drive pronto com mídia carregada")
    else:
        issues.append("Drive ou mídia não confirmados como prontos")

    if (metrics["write_timeouts_24h"] or 0) > 0:
        issues.append(f"timeouts de escrita em 24h: {int(metrics['write_timeouts_24h'] or 0)}")
    if (metrics["fc_abort_events_24h"] or 0) > 0:
        issues.append(f"abortos FC em 24h: {int(metrics['fc_abort_events_24h'] or 0)}")

    if (metrics["buffer_occupancy_pct"] or 0) >= 85:
        issues.append("buffer acima do watermark alto")
    elif metrics["buffer_occupancy_pct"] is not None:
        positives.append("buffer abaixo do limite crítico")

    overall = "critico" if issues and ("indisponível" in " ".join(issues) or "somente leitura" in " ".join(issues)) else "atencao" if issues else "saudavel"
    return {"overall": overall, "issues": issues, "positives": positives}


def fallback_html(metrics: Dict[str, Optional[float]], summary: Dict[str, Any]) -> str:
    badge = {
        "saudavel": ("#16351f", "#79d27f", "Saudável"),
        "atencao": ("#3e3210", "#f1cf63", "Atenção"),
        "critico": ("#4a1818", "#ff8b8b", "Crítico"),
    }[summary["overall"]]
    bg, fg, title = badge
    issues_html = "".join(f"<li>{html.escape(item)}</li>" for item in summary["issues"]) or "<li>Nenhum problema crítico detectado.</li>"
    positives_html = "".join(f"<li>{html.escape(item)}</li>" for item in summary["positives"]) or "<li>Sem sinais positivos adicionais.</li>"
    return f"""
<div style="font-family:Inter,system-ui,sans-serif;padding:10px 14px;line-height:1.4">
  <div style="display:inline-block;padding:6px 10px;border-radius:999px;background:{bg};color:{fg};font-weight:700;margin-bottom:12px">{title}</div>
  <div style="font-size:24px;font-weight:700;margin-bottom:8px">Avaliação automática do drive LTO/NAS</div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 16px 0">
    <div><strong>Drive</strong><br>{html.escape(status_label(metrics['drive_ready'], 'Pronto', 'Indisponível'))}</div>
    <div><strong>Mídia</strong><br>{html.escape(status_label(metrics['medium_loaded'], 'Carregada', 'Ausente'))}</div>
    <div><strong>Compressão</strong><br>{html.escape(status_label(metrics['compression_enabled'], 'Ativa', 'Desativada', 'N/A'))}</div>
    <div><strong>Escrita na fita</strong><br>{html.escape(human_rate(metrics['tape_write_bps']))}</div>
    <div><strong>Flush do worker</strong><br>{html.escape(human_rate(metrics['flush_bps']))}</div>
    <div><strong>Buffer</strong><br>{'%.1f%%' % metrics['buffer_occupancy_pct'] if metrics['buffer_occupancy_pct'] is not None else 'n/d'}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
    <div>
      <strong>Pontos de atenção</strong>
      <ul>{issues_html}</ul>
    </div>
    <div>
      <strong>Sinais positivos</strong>
      <ul>{positives_html}</ul>
    </div>
  </div>
  <div style="margin-top:12px;color:#9aa4b2;font-size:12px">
    timeouts 24h: {int(metrics['write_timeouts_24h'] or 0)} | abortos FC 24h: {int(metrics['fc_abort_events_24h'] or 0)} | última execução: {metrics['last_run_seconds'] or 0:.0f}s / {human_bytes(metrics['last_run_bytes'])} / {int(metrics['last_run_files'] or 0)} arquivos
  </div>
</div>
""".strip()


def query_ollama(metrics: Dict[str, Optional[float]], summary: Dict[str, Any], fallback: str) -> str:
    prompt = {
        "model": OLLAMA_MODEL,
        "prompt": (
            "Você é um analista de armazenamento LTO e NAS. "
            "Com base nas métricas abaixo, gere APENAS um fragmento HTML válido, sem markdown e sem script. "
            "Escreva em português do Brasil, tom técnico e conciso. "
            "Inclua: status geral, 3-6 bullets curtos e uma recomendação prática. "
            "Use cores só com estilos inline discretos.\n\n"
            f"Resumo: {json.dumps(summary, ensure_ascii=False)}\n"
            f"Métricas: {json.dumps(metrics, ensure_ascii=False)}\n"
        ),
        "stream": False,
    }
    try:
        data = http_json(f"{OLLAMA_URL}/api/generate", method="POST", data=prompt)
        response = data.get("response", "").strip()
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return fallback
    if not response:
        return fallback
    response = re.sub(r"<script.*?</script>", "", response, flags=re.IGNORECASE | re.DOTALL)
    if "<" not in response or ">" not in response:
        return fallback
    return response


def ensure_panel(dashboard: Dict[str, Any], content: str) -> None:
    panels = dashboard.setdefault("panels", [])
    panel = None
    for item in panels:
        if item.get("id") == PANEL_ID:
            panel = item
            break
    if panel is None:
        panel = {
            "id": PANEL_ID,
            "title": "AI Assessment",
            "type": "text",
            "gridPos": {"h": 9, "w": 24, "x": 0, "y": 80},
            "datasource": None,
            "options": {"mode": "html", "content": ""},
            "transparent": True,
        }
        panels.append(panel)
    panel["title"] = "AI Assessment"
    panel["type"] = "text"
    panel["transparent"] = True
    panel["options"] = {"mode": "html", "content": content}


def publish_html(html_content: str) -> None:
    payload = http_json(
        f"{GRAFANA_URL}/api/dashboards/uid/{GRAFANA_DASHBOARD_UID}",
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
    )
    dashboard = payload["dashboard"]
    ensure_panel(dashboard, html_content)
    dashboard["version"] = int(dashboard.get("version", 0)) + 1
    post_body = {
        "dashboard": dashboard,
        "folderUid": GRAFANA_FOLDER_UID,
        "overwrite": True,
        "message": "Update AI assessment panel",
    }
    http_json(
        f"{GRAFANA_URL}/api/dashboards/db",
        method="POST",
        data=post_body,
        auth=(GRAFANA_USER, GRAFANA_PASSWORD),
    )


def main() -> int:
    metrics = collect_metrics()
    summary = build_summary(metrics)
    html_fallback = fallback_html(metrics, summary)
    html_content = query_ollama(metrics, summary, html_fallback)
    publish_html(html_content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
