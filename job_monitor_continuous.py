#!/usr/bin/env python3
"""
Monitoramento contínuo de vagas do WhatsApp.
Executa em loop, verifica periodicamente por novas vagas.
"""
import time
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Ensure apply_real_job is importable
sys.path.insert(0, str(Path(__file__).parent))

from apply_real_job import search_group_chats_for_match, TARGET_EMAIL

# Config
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))  # Default: 1 hora
COMPATIBILITY_THRESHOLD = float(os.environ.get("COMPATIBILITY_THRESHOLD", "75.0"))
MAX_CHATS_PER_RUN = int(os.environ.get("MAX_CHATS_PER_RUN", "300"))
MESSAGES_PER_CHAT = int(os.environ.get("MESSAGES_PER_CHAT", "60"))

# Logging
LOG_DIR = Path("/tmp/job_monitor")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def send_telegram_notification(message: str):
    """Send notification via Telegram bot (if configured)."""
    try:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if not bot_token or not chat_id:
            logger.debug("Telegram not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing)")
            return
        
        import requests
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=data, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Telegram notification sent")
        else:
            logger.warning(f"Telegram notification failed: {response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")


def run_search():
    """Execute single search iteration."""
    logger.info("="*70)
    logger.info(f"🔍 Starting job search - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Threshold: {COMPATIBILITY_THRESHOLD}%")
    logger.info(f"   Max chats: {MAX_CHATS_PER_RUN}")
    logger.info(f"   Messages per chat: {MESSAGES_PER_CHAT}")
    logger.info("="*70)
    
    try:
        match = search_group_chats_for_match(
            threshold=COMPATIBILITY_THRESHOLD,
            max_chats=MAX_CHATS_PER_RUN,
            messages_per_chat=MESSAGES_PER_CHAT
        )
        
        if match:
            title = match.get('title', 'N/A')
            company = match.get('company', 'N/A')
            compat = match.get('compatibility', 0)
            
            logger.info("="*70)
            logger.info("✅ MATCH FOUND!")
            logger.info(f"   Vaga: {title}")
            logger.info(f"   Empresa: {company}")
            logger.info(f"   Compatibilidade: {compat}%")
            logger.info(f"   Email target: {TARGET_EMAIL}")
            logger.info("="*70)
            
            # Send Telegram notification
            notification = (
                f"🎯 *Nova vaga compatível encontrada!*\n\n"
                f"*Vaga:* {title}\n"
                f"*Empresa:* {company}\n"
                f"*Compatibilidade:* {compat}%\n"
                f"*Email enviado para:* {TARGET_EMAIL}\n\n"
                f"Verifique sua caixa de entrada!"
            )
            send_telegram_notification(notification)
            
            return True
        else:
            logger.info("ℹ️  No compatible jobs found in this iteration")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during search: {e}", exc_info=True)
        
        # Send error notification
        error_notification = (
            f"⚠️ *Erro no monitoramento de vagas*\n\n"
            f"```\n{str(e)[:500]}\n```\n\n"
            f"Verifique os logs em {LOG_DIR}"
        )
        send_telegram_notification(error_notification)
        
        return False


def main():
    """Main loop - run continuously."""
    logger.info("🚀 Job Monitor Started")
    logger.info(f"   Check interval: {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"   Threshold: {COMPATIBILITY_THRESHOLD}%")
    logger.info(f"   Log directory: {LOG_DIR}")
    
    # Send startup notification
    send_telegram_notification(
        f"🤖 *Job Monitor Iniciado*\n\n"
        f"Intervalo: {CHECK_INTERVAL_MINUTES} minutos\n"
        f"Threshold: {COMPATIBILITY_THRESHOLD}%"
    )
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"Iteration #{iteration}")
            logger.info(f"{'='*70}\n")
            
            run_search()
            
            logger.info(f"\n⏳ Sleeping for {CHECK_INTERVAL_MINUTES} minutes until next check...")
            logger.info(f"   Next check at: {datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=CHECK_INTERVAL_MINUTES)}")
            
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Job Monitor stopped by user")
        send_telegram_notification("🛑 *Job Monitor Parado*\n\nMonitoramento interrompido manualmente.")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}", exc_info=True)
        send_telegram_notification(f"💥 *Job Monitor Crashed*\n\n```\n{str(e)[:500]}\n```")
        raise


if __name__ == "__main__":
    from datetime import timedelta
    main()
