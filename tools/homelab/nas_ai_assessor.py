"""Assess NAS/LTO health from Prometheus and publish an HTML panel in Grafana."""
from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3002")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "Rpa_four_all!")
GRAFANA_DASHBOARD_UID = os.environ.get("GRAFANA_DASHBOARD_UID", "nas-rpa4all-omv")
GRAFANA_FOLDER_UID = os.environ.get("GRAFANA_FOLDER_UID", "fffxoniykngn4e")
GRAFANA_PANEL_ID = int(os.environ.get("GRAFANA_PANEL_ID", "99"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))

QUERIES: Dict[str, str] = {
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


def http_json(url: str, method: str = "GET", data: Optional[Dict] = None, auth: Optional[tuple[str, str]] = None) -> Optional[Dict]:
    body = json.dumps(data).encode("utf-8") if data else None
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if auth:
        token = base64.b64encode(("%s:%s" % auth).encode("ascii")).decode("ascii")
        headers["Authorization"] = "Basic " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError):
        return None


def prom_query(expr: str) -> Optional[float]:
    url = PROMETHEUS_URL + "/api/v1/query?" + urllib.parse.urlencode({"query": expr})
    resp = http_json(url)
    try:
        return float(resp["data"]["result"][0]["value"][1])
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def collect_metrics() -> Dict[str, Optional[float]]:
    return {name: prom_query(expr) for name, expr in QUERIES.items()}


def human_bytes(size: Optional[float]) -> str:
    if size is None:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def human_rate(units: Optional[float]) -> str:
    if units is None:
        return "N/A"
    return human_bytes(units) + "/s"


def status_label(value: Optional[float], good_text: str, bad_text: str, na_text: str = "N/A") -> str:
    if value is None:
        return na_text
    return good_text if value >= 1.0 else bad_text


def build_summary(metrics: Dict[str, Optional[float]]) -> Dict:
    issues: List[str] = []
    positives: List[str] = []

    ltfs_up = metrics.get("ltfs_service_up")
    mount_up = metrics.get("ltfs_mount_up")
    read_only = metrics.get("ltfs_read_only")

    if ltfs_up and mount_up:
        positives.append("LTFS ativo e montado")
    else:
        issues.append("LTFS indisponível ou não montado")

    if read_only:
        issues.append("LTFS em modo somente leitura")
    elif ltfs_up:
        positives.append("LTFS em leitura e escrita")

    drive_ready = metrics.get("drive_ready")
    medium_loaded = metrics.get("medium_loaded")
    if drive_ready and medium_loaded:
        positives.append("Drive pronto com mídia carregada")
    else:
        issues.append("Drive ou mídia não confirmados como prontos")

    timeouts = metrics.get("write_timeouts_24h")
    if timeouts and timeouts > 0:
        issues.append(f"timeouts de escrita em 24h: {int(timeouts)}")

    fc_aborts = metrics.get("fc_abort_events_24h")
    if fc_aborts and fc_aborts > 0:
        issues.append(f"abortos FC em 24h: {int(fc_aborts)}")

    buf = metrics.get("buffer_occupancy_pct")
    if buf is not None:
        if buf > 85:
            issues.append(f"buffer acima do watermark alto {buf:.1f}%")
        elif buf < 5:
            issues.append("buffer abaixo do limite crítico")

    if issues:
        overall = "critico" if any("indisponível" in i or "LTFS" in i for i in issues) else "atencao"
    else:
        overall = "saudavel"

    return {"overall": overall, "issues": issues, "positives": positives}


def fallback_html(summary: Dict, metrics: Dict[str, Optional[float]]) -> str:
    BADGE_COLORS = {
        "saudavel": ("#16351f", "#79d27f", "Saudável"),
        "atencao": ("#3e3210", "#f1cf63", "Atenção"),
        "critico": ("#4a1818", "#ff8b8b", "Crítico"),
    }
    overall = summary.get("overall", "critico")
    bg, color, label = BADGE_COLORS.get(overall, BADGE_COLORS["critico"])

    issues_html = "".join(f"<li>{i}</li>" for i in summary.get("issues", []))
    if not issues_html:
        issues_html = "<li>Nenhum problema crítico detectado.</li>"

    positives_html = "".join(f"<li>{p}</li>" for p in summary.get("positives", []))
    if not positives_html:
        positives_html = "<li>Sem sinais positivos adicionais.</li>"

    drive_label = status_label(metrics.get("drive_ready"), "Pronto", "Indisponível")
    media_label = status_label(metrics.get("medium_loaded"), "Carregada", "Ausente")
    comp_val = metrics.get("compression_enabled")
    comp_label = "Ativa" if comp_val and comp_val >= 1 else ("Desativada" if comp_val is not None else "N/A")

    buf = metrics.get("buffer_occupancy_pct")
    buf_str = f"{buf:.1f}%" if buf is not None else "N/A"

    last_s = metrics.get("last_run_seconds")
    last_b = metrics.get("last_run_bytes")
    last_f = metrics.get("last_run_files")
    last_exec = "N/A"
    if last_s is not None:
        last_exec = f"{last_s:.0f}s / {human_bytes(last_b)} / {int(last_f or 0)} arquivos"

    timeouts = int(metrics.get("write_timeouts_24h") or 0)
    fc_aborts = int(metrics.get("fc_abort_events_24h") or 0)

    return f"""<div style="font-family:Inter,system-ui,sans-serif;padding:10px 14px;line-height:1.4">
  <div style="display:inline-block;padding:6px 10px;border-radius:999px;background:{bg};color:{color};font-weight:700;margin-bottom:12px">{label}</div>
  <div style="font-size:24px;font-weight:700;margin-bottom:8px">Avaliação automática do drive LTO/NAS</div>
  <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 16px 0">
    <div><strong>Drive</strong><br>{drive_label}</div>
    <div><strong>Mídia</strong><br>{media_label}</div>
    <div><strong>Compressão</strong><br>{comp_label}</div>
    <div><strong>Escrita na fita</strong><br>{human_rate(metrics.get("tape_write_bps"))}</div>
    <div><strong>Flush do worker</strong><br>{human_rate(metrics.get("flush_bps"))}</div>
    <div><strong>Buffer</strong><br>{buf_str}</div>
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
    timeouts 24h: {timeouts} | abortos FC 24h: {fc_aborts} | última execução: {last_exec}
  </div>
</div>"""


def query_ollama(summary: Dict, metrics: Dict[str, Optional[float]]) -> Optional[str]:
    metrics_str = json.dumps(
        {k: round(v, 4) if v is not None else None for k, v in metrics.items()},
        ensure_ascii=False,
    )
    prompt = (
        "Você é um analista de armazenamento LTO e NAS. Com base nas métricas abaixo, "
        "gere APENAS um fragmento HTML válido, sem markdown e sem script. "
        "Escreva em português do Brasil, tom técnico e conciso. "
        "Inclua: status geral, 3-6 bullets curtos e uma recomendação prática. "
        "Use cores só com estilos inline discretos.\n"
        f"Resumo: {json.dumps(summary, ensure_ascii=False)}\n"
        f"Métricas: {metrics_str}"
    )
    resp = http_json(
        OLLAMA_URL + "/api/generate",
        method="POST",
        data={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
    )
    if not resp:
        return None
    html = resp.get("response", "").strip()
    html = re.sub(r"<script.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    return html if html else None


def ensure_panel(dashboard: Dict, html_content: str) -> Dict:
    panels: List[Dict] = dashboard.setdefault("panels", [])
    for panel in panels:
        if panel.get("id") == GRAFANA_PANEL_ID:
            panel.setdefault("options", {})["content"] = html_content
            panel["options"]["mode"] = "html"
            return dashboard
    panels.append({
        "id": GRAFANA_PANEL_ID,
        "title": "AI Assessment",
        "type": "text",
        "datasource": None,
        "transparent": True,
        "gridPos": {"h": 12, "w": 12, "x": 0, "y": 0},
        "options": {"mode": "html", "content": html_content},
    })
    return dashboard


def publish_html(html_content: str) -> None:
    auth = (GRAFANA_USER, GRAFANA_PASSWORD)
    resp = http_json(GRAFANA_URL + f"/api/dashboards/uid/{GRAFANA_DASHBOARD_UID}", auth=auth)
    if not resp:
        print(f"ERROR: could not fetch dashboard {GRAFANA_DASHBOARD_UID}")
        raise SystemExit(1)

    dashboard = resp["dashboard"]
    version = resp.get("meta", {}).get("version", dashboard.get("version", 0))
    dashboard["version"] = version

    ensure_panel(dashboard, html_content)

    payload = {
        "dashboard": dashboard,
        "folderUid": GRAFANA_FOLDER_UID,
        "overwrite": True,
        "message": "Update AI assessment panel",
    }
    post_body = http_json(GRAFANA_URL + "/api/dashboards/db", method="POST", data=payload, auth=auth)
    if not post_body:
        print("ERROR: failed to publish dashboard")
        raise SystemExit(1)


def main() -> None:
    metrics = collect_metrics()
    summary = build_summary(metrics)

    html_fallback = fallback_html(summary, metrics)
    html_content = query_ollama(summary, metrics) or html_fallback

    publish_html(html_content)
    print(f"OK: panel updated — overall={summary['overall']}")


if __name__ == "__main__":
    main()
