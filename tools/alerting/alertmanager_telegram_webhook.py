#!/usr/bin/env python3
# Webhook receiver para Alertmanager → Telegram
# Receives alerts from Alertmanager and sends notifications to Telegram
#
# Setup:
#   1. pip install bottle requests
#   2. Configure in alertmanager.yml:
#        - name: 'telegram'
#          webhook_configs:
#            - url: 'http://localhost:5000/alerts'
#   3. route:
#        receiver: 'telegram'
#
# Environment variables:
#   TELEGRAM_BOT_TOKEN: seu bot token
#   TELEGRAM_CHAT_ID: seu chat ID
#   WEBHOOK_PORT: porta (default 5000)
#   ALERT_SEND_RESOLVED: envia alertas resolvidos (default false)
#   ALERT_ALLOWED_SEVERITIES: severidades permitidas (default critical,warning,error)
#   ALERT_DEDUP_WINDOW_SECONDS: janela anti-duplicidade (default 900)
#   ALERT_DEDUP_CACHE_FILE: cache de dedup em disco (default /tmp/alertmanager_telegram_dedup.json)
#   ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD: limite de alertas por payload (default 8)
#   ALERT_MAX_LABELS: limite de labels extras por alerta (default 8)

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bottle import Bottle, abort, request

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/alertmanager-telegram.log'),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Configuration from environment
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5000'))
ALERT_SEND_RESOLVED = os.getenv('ALERT_SEND_RESOLVED', 'false').strip().lower() in {
    '1',
    'true',
    'yes',
    'on',
}
ALERT_ALLOWED_SEVERITIES = {
    item.strip().lower()
    for item in os.getenv('ALERT_ALLOWED_SEVERITIES', 'critical,warning,error').split(',')
    if item.strip()
}
ALERT_DEDUP_WINDOW_SECONDS = max(int(os.getenv('ALERT_DEDUP_WINDOW_SECONDS', '900')), 0)
ALERT_DEDUP_CACHE_FILE = os.getenv(
    'ALERT_DEDUP_CACHE_FILE',
    '/tmp/alertmanager_telegram_dedup.json',
)
ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD = max(
    int(os.getenv('ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD', '8')),
    1,
)
ALERT_MAX_LABELS = max(int(os.getenv('ALERT_MAX_LABELS', '8')), 1)
ALERT_MESSAGE_LIMIT = 3900

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error('TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set')
    sys.exit(1)

TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
CACHE_PATH = Path(ALERT_DEDUP_CACHE_FILE)

app = Bottle()


def _sanitize_text(value: Any, max_len: int = 300) -> str:
    """Sanitiza texto para HTML do Telegram e limita tamanho."""
    text = str(value) if value is not None else ''
    text = ' '.join(text.replace('\r', ' ').replace('\n', ' ').split())
    if len(text) > max_len:
        text = text[: max_len - 1] + '…'
    return html.escape(text)


def _format_timestamp(value: str) -> str:
    """Converte timestamp ISO para UTC legível."""
    if not value:
        return 'N/A'
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return _sanitize_text(value, max_len=40)


def _load_dedup_cache(now_ts: float) -> dict[str, float]:
    """Carrega cache de deduplicação e remove entradas expiradas."""
    if ALERT_DEDUP_WINDOW_SECONDS <= 0:
        return {}
    try:
        if not CACHE_PATH.exists():
            return {}
        raw = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            return {}
        min_ts = now_ts - (ALERT_DEDUP_WINDOW_SECONDS * 2)
        return {
            str(key): float(sent_at)
            for key, sent_at in raw.items()
            if isinstance(sent_at, (int, float)) and float(sent_at) >= min_ts
        }
    except Exception as exc:
        logger.warning('Falha ao carregar cache de dedup: %s', exc)
        return {}


def _save_dedup_cache(cache: dict[str, float], now_ts: float) -> None:
    """Persiste cache de deduplicação."""
    if ALERT_DEDUP_WINDOW_SECONDS <= 0:
        return
    min_ts = now_ts - (ALERT_DEDUP_WINDOW_SECONDS * 2)
    pruned = {
        key: sent_at
        for key, sent_at in cache.items()
        if sent_at >= min_ts
    }
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(pruned, ensure_ascii=True), encoding='utf-8')
    except Exception as exc:
        logger.warning('Falha ao salvar cache de dedup: %s', exc)


def _build_alert_fingerprint(alert: dict[str, Any]) -> str:
    """Gera hash estável para suprimir alertas repetidos na janela de dedup."""
    labels = alert.get('labels', {}) or {}
    annotations = alert.get('annotations', {}) or {}
    payload = {
        'status': str(alert.get('status', '')).lower(),
        'alertname': labels.get('alertname', ''),
        'severity': labels.get('severity', ''),
        'instance': labels.get('instance', ''),
        'job': labels.get('job', ''),
        'service': labels.get('service', ''),
        'summary': annotations.get('summary', ''),
        'description': annotations.get('description', ''),
    }
    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode('utf-8')
    ).hexdigest()
    return digest


def _is_duplicate(fingerprint: str, cache: dict[str, float], now_ts: float) -> bool:
    """Retorna True se alerta foi enviado recentemente."""
    if ALERT_DEDUP_WINDOW_SECONDS <= 0:
        return False
    last_sent = cache.get(fingerprint)
    if last_sent and (now_ts - last_sent) < ALERT_DEDUP_WINDOW_SECONDS:
        return True
    cache[fingerprint] = now_ts
    return False


def _should_notify(alert: dict[str, Any]) -> tuple[bool, str]:
    """Aplica filtros para reduzir ruído de alertas."""
    status = str(alert.get('status', '')).strip().lower()
    labels = alert.get('labels', {}) or {}
    severity = str(labels.get('severity', '')).strip().lower()

    if status == 'resolved' and not ALERT_SEND_RESOLVED:
        return False, 'resolved_ignored'

    if severity and ALERT_ALLOWED_SEVERITIES and severity not in ALERT_ALLOWED_SEVERITIES:
        return False, 'severity_filtered'

    return True, 'ok'


def send_telegram_message(message: str) -> bool:
    """Send message to Telegram channel."""
    try:
        response = requests.post(
            TELEGRAM_API_URL,
            json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            },
            timeout=10,
        )

        if response.status_code == 200:
            logger.info('Mensagem enviada para Telegram com sucesso')
            return True

        logger.error('Erro ao enviar mensagem: %s - %s', response.status_code, response.text)
        return False
    except Exception as exc:
        logger.error('Exception ao enviar mensagem: %s', exc)
        return False


def format_alert(alert: dict[str, Any]) -> str:
    """Format Alertmanager alert for Telegram."""
    status = str(alert.get('status', 'unknown')).strip().upper()

    status_icons = {
        'FIRING': '🔴',
        'RESOLVED': '🟢',
    }
    severity_icons = {
        'CRITICAL': '🚨',
        'WARNING': '⚠️',
        'ERROR': '❗',
        'INFO': 'ℹ️',
    }

    labels = alert.get('labels', {}) or {}
    annotations = alert.get('annotations', {}) or {}

    alert_name = _sanitize_text(labels.get('alertname', 'Unknown'), max_len=120)
    severity = str(labels.get('severity', 'unknown')).strip().upper()
    severity_label = _sanitize_text(severity, max_len=20)

    summary = _sanitize_text(
        annotations.get('summary') or annotations.get('message') or 'Sem resumo',
        max_len=260,
    )
    description = _sanitize_text(
        annotations.get('description') or annotations.get('details') or 'Sem detalhes',
        max_len=420,
    )

    starts_at = _format_timestamp(str(alert.get('startsAt', '')))
    ends_at = _format_timestamp(str(alert.get('endsAt', '')))
    job = _sanitize_text(labels.get('job', 'N/A'), max_len=80)
    instance = _sanitize_text(labels.get('instance', 'N/A'), max_len=120)
    service = _sanitize_text(labels.get('service', ''), max_len=80)
    runbook = _sanitize_text(annotations.get('runbook_url', ''), max_len=180)
    generator_url = _sanitize_text(alert.get('generatorURL', ''), max_len=180)

    lines = [
        f"<b>{status_icons.get(status, '⚪')} {status}</b> {severity_icons.get(severity, '🔔')} <b>{severity_label}</b>",
        f"<b>Alerta:</b> {alert_name}",
        f"<b>Resumo:</b> {summary}",
        f"<b>Detalhes:</b> {description}",
        f"<b>Origem:</b> job={job} instance={instance}",
        f"<b>Inicio:</b> {starts_at}",
    ]

    if status == 'RESOLVED' and ends_at != 'N/A':
        lines.append(f"<b>Resolvido em:</b> {ends_at}")

    if service:
        lines.append(f"<b>Service:</b> {service}")
    if runbook:
        lines.append(f"<b>Runbook:</b> {runbook}")
    if generator_url:
        lines.append(f"<b>Grafana/Prom:</b> {generator_url}")

    exclude_labels = {
        'alertname',
        'severity',
        'job',
        'instance',
        'service',
        'namespace',
        'pod',
    }
    extra_label_lines: list[str] = []
    for key in sorted(labels.keys()):
        if key in exclude_labels:
            continue
        extra_label_lines.append(
            f"• <b>{_sanitize_text(key, max_len=40)}:</b> {_sanitize_text(labels[key], max_len=120)}"
        )
        if len(extra_label_lines) >= ALERT_MAX_LABELS:
            break

    if extra_label_lines:
        lines.append('<b>Labels extras:</b>')
        lines.extend(extra_label_lines)

    return '\n'.join(lines)


def _build_batched_messages(
    formatted_alerts: list[str],
    alert_type: str,
    stats: dict[str, int],
) -> list[str]:
    """Monta 1..N mensagens com cabeçalho e respeitando limite do Telegram."""
    header = (
        f"<b>📣 Alertmanager ({_sanitize_text(alert_type, max_len=30)})</b>\n"
        f"Recebidos: {stats['received']} | Validos: {stats['prepared']} | "
        f"Filtrados: {stats['filtered']} | Duplicados: {stats['deduped']} | "
        f"Cortados: {stats['dropped']}"
    )

    messages: list[str] = []
    current = header
    visible_alerts = formatted_alerts[:ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD]

    for index, block in enumerate(visible_alerts, start=1):
        section = f"\n\n<b>#{index}</b>\n{block}"
        if len(current) + len(section) > ALERT_MESSAGE_LIMIT:
            messages.append(current)
            current = f"{header}\n\n<b>#{index}</b>\n{block}"
        else:
            current += section

    if current:
        messages.append(current)
    return messages


@app.post('/alerts')
def handle_alerts() -> dict[str, Any]:
    """Receive alerts from Alertmanager."""
    try:
        alert_data = request.json

        if not alert_data:
            logger.warning('Received empty alert data')
            abort(400, 'Empty alert data')

        alerts = alert_data.get('alerts', [])

        if not alerts:
            logger.warning('No alerts in payload')
            return {'status': 'ok', 'message': 'No alerts'}

        now_ts = time.time()
        alert_type = request.headers.get('X-Alert-Type', 'generic')
        dedup_cache = _load_dedup_cache(now_ts)

        stats = {
            'received': len(alerts),
            'prepared': 0,
            'filtered': 0,
            'deduped': 0,
            'dropped': 0,
            'messages_sent': 0,
        }

        actionable_alerts: list[str] = []

        for alert in alerts:
            should_notify, reason = _should_notify(alert)
            if not should_notify:
                stats['filtered'] += 1
                logger.info('Alerta ignorado (%s)', reason)
                continue

            fingerprint = _build_alert_fingerprint(alert)
            if _is_duplicate(fingerprint, dedup_cache, now_ts):
                stats['deduped'] += 1
                logger.info('Alerta duplicado suprimido: %s', fingerprint[:12])
                continue

            actionable_alerts.append(format_alert(alert))

        stats['prepared'] = len(actionable_alerts)
        if len(actionable_alerts) > ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD:
            stats['dropped'] = len(actionable_alerts) - ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD

        _save_dedup_cache(dedup_cache, now_ts)

        if not actionable_alerts:
            logger.info('Nenhum alerta acionavel apos saneamento')
            return {
                'status': 'ok',
                'alerts_received': stats['received'],
                'alerts_actionable': 0,
                'alerts_filtered': stats['filtered'],
                'alerts_deduped': stats['deduped'],
            }

        telegram_messages = _build_batched_messages(actionable_alerts, alert_type, stats)
        for message in telegram_messages:
            if send_telegram_message(message):
                stats['messages_sent'] += 1

        return {
            'status': 'ok',
            'alerts_received': stats['received'],
            'alerts_actionable': stats['prepared'],
            'alerts_filtered': stats['filtered'],
            'alerts_deduped': stats['deduped'],
            'alerts_dropped': stats['dropped'],
            'telegram_messages_sent': stats['messages_sent'],
        }

    except Exception as exc:
        logger.error('Exception handling alerts: %s', exc, exc_info=True)
        abort(500, f'Internal error: {exc}')


@app.get('/health')
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}


if __name__ == '__main__':
    logger.info('Starting Alertmanager → Telegram webhook on port %s', WEBHOOK_PORT)
    logger.info('Chat ID: %s', TELEGRAM_CHAT_ID)
    logger.info(
        'Alert sane defaults: send_resolved=%s allowed_severities=%s dedup_window=%ss',
        ALERT_SEND_RESOLVED,
        sorted(ALERT_ALLOWED_SEVERITIES),
        ALERT_DEDUP_WINDOW_SECONDS,
    )
    logger.info(
        'Dedup cache: %s | max alerts/payload: %s',
        ALERT_DEDUP_CACHE_FILE,
        ALERT_MAX_NOTIFICATIONS_PER_PAYLOAD,
    )

    try:
        app.run(host='0.0.0.0', port=WEBHOOK_PORT, quiet=False)
    except KeyboardInterrupt:
        logger.info('Shutting down')
    except Exception as exc:
        logger.error('Fatal error: %s', exc, exc_info=True)
        sys.exit(1)
