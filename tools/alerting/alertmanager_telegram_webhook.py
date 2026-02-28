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

import os
import sys
import json
import logging
from datetime import datetime
import requests
from bottle import Bottle, request, abort

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/alertmanager-telegram.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '5000'))

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error('TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set')
    sys.exit(1)

TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'

app = Bottle()

def send_telegram_message(message: str) -> bool:
    """Send message to Telegram channel"""
    try:
        response = requests.post(
            TELEGRAM_API_URL,
            json={
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info('Mensagem enviada para Telegram com sucesso')
            return True
        else:
            logger.error(f'Erro ao enviar mensagem: {response.status_code} - {response.text}')
            return False
    except Exception as e:
        logger.error(f'Exception ao enviar mensagem: {e}')
        return False

def format_alert(alert: dict) -> str:
    """Format Alertmanager alert for Telegram"""
    status = alert.get('status', 'unknown').upper()
    
    # Status emoji
    status_emoji = '🔴' if status == 'FIRING' else '🟢'
    
    # Alert info
    labels = alert.get('labels', {})
    annotations = alert.get('annotations', {})
    
    alert_name = labels.get('alertname', 'Unknown')
    severity = labels.get('severity', 'unknown').upper()
    
    summary = annotations.get('summary', 'No summary')
    description = annotations.get('description', 'No description')
    
    # Format timestamp
    fired_at = alert.get('startsAt', '')
    if fired_at:
        try:
            dt = datetime.fromisoformat(fired_at.replace('Z', '+00:00'))
            time_str = dt.strftime('%H:%M:%S')
        except:
            time_str = fired_at
    else:
        time_str = 'N/A'
    
    # Build message
    message = f"""<b>{status_emoji} ALERTA - {status}</b>

<b>Nome:</b> {alert_name}
<b>Severidade:</b> {severity}
<b>Hora:</b> {time_str}

<b>Resumo:</b>
{summary}

<b>Detalhes:</b>
{description}

<b>Labels:</b>"""
    
    # Add labels (exclude common ones)
    exclude_labels = {'alertname', 'severity'}
    for key, value in labels.items():
        if key not in exclude_labels:
            message += f'\n  • {key}: {value}'
    
    return message

@app.post('/alerts')
def handle_alerts():
    """Receive alerts from Alertmanager"""
    try:
        alert_data = request.json
        
        if not alert_data:
            logger.warning('Received empty alert data')
            abort(400, 'Empty alert data')
        
        alerts = alert_data.get('alerts', [])
        
        if not alerts:
            logger.warning('No alerts in payload')
            return {'status': 'ok', 'message': 'No alerts'}
        
        logger.info(f'Received {len(alerts)} alert(s)')
        
        # Send message for each alert
        for alert in alerts:
            message = format_alert(alert)
            logger.debug(f'Formatted alert: {message}')
            
            if send_telegram_message(message):
                logger.info('Alert sent to Telegram successfully')
            else:
                logger.error('Failed to send alert to Telegram')
        
        return {'status': 'ok', 'alerts_processed': len(alerts)}
    
    except Exception as e:
        logger.error(f'Exception handling alerts: {e}', exc_info=True)
        abort(500, f'Internal error: {e}')

@app.get('/health')
def health_check():
    """Health check endpoint"""
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}

if __name__ == '__main__':
    logger.info(f'Starting Alertmanager → Telegram webhook on port {WEBHOOK_PORT}')
    logger.info(f'Chat ID: {TELEGRAM_CHAT_ID}')
    
    try:
        app.run(host='0.0.0.0', port=WEBHOOK_PORT, quiet=False)
    except KeyboardInterrupt:
        logger.info('Shutting down')
    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)
