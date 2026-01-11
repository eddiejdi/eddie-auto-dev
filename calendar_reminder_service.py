#!/usr/bin/env python3
"""
Serviço de Lembretes do Calendário para Eddie Assistant

Roda em background e envia lembretes via Telegram e WhatsApp
antes dos eventos agendados.

Funcionalidades:
- Lembretes configuráveis (30min, 10min, etc)
- Agenda diária automática
- Notificações de novos eventos
- Resumo semanal

Autor: Eddie Assistant
Data: 2026
"""

import os
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Set
import signal
import sys

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

from google_calendar_integration import (
    GoogleCalendarClient, NotificationManager, CalendarEvent,
    get_calendar_assistant
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/calendar_reminder.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('CalendarReminder')

# Configurações
REMINDER_MINUTES = [int(x) for x in os.getenv('CALENDAR_REMINDER_MINUTES', '30,10,5').split(',')]
DAILY_DIGEST_HOUR = int(os.getenv('CALENDAR_DAILY_DIGEST_HOUR', '7'))
WEEKLY_DIGEST_DAY = int(os.getenv('CALENDAR_WEEKLY_DIGEST_DAY', '0'))  # 0 = Segunda
CHECK_INTERVAL_SECONDS = 60  # Verificar a cada minuto

# Telegram e WhatsApp
TELEGRAM_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID', '948686300'))
WHATSAPP_NUMBER = os.getenv('WHATSAPP_NUMBER', '5511981193899')

# Arquivo de estado
STATE_FILE = Path(__file__).parent / "calendar_data" / "reminder_state.json"


class ReminderState:
    """Gerencia estado dos lembretes enviados"""
    
    def __init__(self):
        self.sent_reminders: Dict[str, Set[int]] = {}  # event_id -> set of minutes
        self.last_daily_digest: str = ""
        self.last_weekly_digest: str = ""
        self._load()
    
    def _load(self):
        """Carrega estado do arquivo"""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                
                self.sent_reminders = {
                    k: set(v) for k, v in data.get('sent_reminders', {}).items()
                }
                self.last_daily_digest = data.get('last_daily_digest', '')
                self.last_weekly_digest = data.get('last_weekly_digest', '')
        except Exception as e:
            logger.error(f"Erro ao carregar estado: {e}")
    
    def _save(self):
        """Salva estado no arquivo"""
        try:
            STATE_FILE.parent.mkdir(exist_ok=True)
            
            data = {
                'sent_reminders': {k: list(v) for k, v in self.sent_reminders.items()},
                'last_daily_digest': self.last_daily_digest,
                'last_weekly_digest': self.last_weekly_digest
            }
            
            with open(STATE_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Erro ao salvar estado: {e}")
    
    def should_send_reminder(self, event_id: str, minutes_before: int) -> bool:
        """Verifica se deve enviar lembrete"""
        if event_id not in self.sent_reminders:
            self.sent_reminders[event_id] = set()
        
        return minutes_before not in self.sent_reminders[event_id]
    
    def mark_reminder_sent(self, event_id: str, minutes_before: int):
        """Marca lembrete como enviado"""
        if event_id not in self.sent_reminders:
            self.sent_reminders[event_id] = set()
        
        self.sent_reminders[event_id].add(minutes_before)
        self._save()
    
    def should_send_daily_digest(self) -> bool:
        """Verifica se deve enviar agenda diária"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.last_daily_digest != today
    
    def mark_daily_digest_sent(self):
        """Marca agenda diária como enviada"""
        self.last_daily_digest = datetime.now().strftime('%Y-%m-%d')
        self._save()
    
    def should_send_weekly_digest(self) -> bool:
        """Verifica se deve enviar resumo semanal"""
        today = datetime.now()
        week_key = f"{today.year}-W{today.isocalendar()[1]}"
        return self.last_weekly_digest != week_key and today.weekday() == WEEKLY_DIGEST_DAY
    
    def mark_weekly_digest_sent(self):
        """Marca resumo semanal como enviado"""
        today = datetime.now()
        self.last_weekly_digest = f"{today.year}-W{today.isocalendar()[1]}"
        self._save()
    
    def cleanup_old_reminders(self):
        """Remove lembretes antigos (eventos passados)"""
        # Manter apenas últimos 100 eventos
        if len(self.sent_reminders) > 100:
            # Remover os mais antigos (assumindo que IDs são cronológicos)
            sorted_ids = sorted(self.sent_reminders.keys())
            for old_id in sorted_ids[:-100]:
                del self.sent_reminders[old_id]
            self._save()


class CalendarReminderService:
    """Serviço principal de lembretes"""
    
    def __init__(self):
        self.calendar = GoogleCalendarClient()
        self.notifications = NotificationManager()
        self.state = ReminderState()
        self.running = True
    
    async def check_reminders(self):
        """Verifica e envia lembretes pendentes"""
        try:
            # Buscar eventos das próximas 2 horas
            events = await self.calendar.get_upcoming_events(hours=2)
            now = datetime.now()
            
            for event in events:
                if event.all_day:
                    continue  # Pular eventos de dia inteiro para lembretes
                
                # Calcular tempo até o evento
                time_until = (event.start - now).total_seconds() / 60  # minutos
                
                for reminder_min in REMINDER_MINUTES:
                    # Verificar se está na janela de lembrete (tolerância de 2 min)
                    if reminder_min - 2 <= time_until <= reminder_min + 2:
                        if self.state.should_send_reminder(event.id, reminder_min):
                            await self.send_reminder(event, reminder_min)
                            self.state.mark_reminder_sent(event.id, reminder_min)
            
        except Exception as e:
            logger.error(f"Erro ao verificar lembretes: {e}")
    
    async def send_reminder(self, event: CalendarEvent, minutes_before: int):
        """Envia lembrete de evento"""
        logger.info(f"Enviando lembrete: {event.summary} ({minutes_before}min)")
        
        if minutes_before >= 60:
            time_str = f"{minutes_before // 60}h"
        else:
            time_str = f"{minutes_before}min"
        
        message = f"""⏰ **LEMBRETE - {time_str} para o evento!**

📌 **{event.summary}**
🕐 Início: {event.start.strftime('%H:%M')}
{"📍 Local: " + event.location if event.location else ""}

Prepare-se! 🚀"""
        
        # Enviar para Telegram
        try:
            success = await self.notifications.send_telegram(TELEGRAM_CHAT_ID, message)
            if success:
                logger.info(f"Lembrete enviado via Telegram")
            else:
                logger.warning("Falha ao enviar lembrete via Telegram")
        except Exception as e:
            logger.error(f"Erro Telegram: {e}")
        
        # Enviar para WhatsApp
        try:
            success = await self.notifications.send_whatsapp(WHATSAPP_NUMBER, message)
            if success:
                logger.info(f"Lembrete enviado via WhatsApp")
            else:
                logger.warning("Falha ao enviar lembrete via WhatsApp")
        except Exception as e:
            logger.error(f"Erro WhatsApp: {e}")
    
    async def send_daily_digest(self):
        """Envia agenda diária"""
        logger.info("Enviando agenda diária...")
        
        try:
            # Buscar eventos do dia
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            success, _, events = await self.calendar.list_events(
                time_min=today_start,
                time_max=today_end,
                max_results=20
            )
            
            if not success:
                logger.error("Falha ao buscar eventos do dia")
                return
            
            await self.notifications.send_daily_agenda(
                events,
                telegram_chat_id=TELEGRAM_CHAT_ID,
                whatsapp_number=WHATSAPP_NUMBER
            )
            
            self.state.mark_daily_digest_sent()
            logger.info("Agenda diária enviada!")
            
        except Exception as e:
            logger.error(f"Erro ao enviar agenda diária: {e}")
    
    async def send_weekly_digest(self):
        """Envia resumo semanal"""
        logger.info("Enviando resumo semanal...")
        
        try:
            # Buscar eventos da semana
            week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            
            success, _, events = await self.calendar.list_events(
                time_min=week_start,
                time_max=week_end,
                max_results=50
            )
            
            if not success:
                logger.error("Falha ao buscar eventos da semana")
                return
            
            # Agrupar por dia
            events_by_day: Dict[str, List[CalendarEvent]] = {}
            for event in events:
                day = event.start.strftime('%A, %d/%m')
                if day not in events_by_day:
                    events_by_day[day] = []
                events_by_day[day].append(event)
            
            # Formatar mensagem
            message = f"📅 **RESUMO DA SEMANA**\n"
            message += f"📆 {week_start.strftime('%d/%m')} a {week_end.strftime('%d/%m/%Y')}\n\n"
            
            if events_by_day:
                for day, day_events in events_by_day.items():
                    message += f"**{day}:**\n"
                    for event in day_events:
                        time_str = event.start.strftime('%H:%M') if not event.all_day else "Dia inteiro"
                        message += f"  • {time_str} - {event.summary}\n"
                    message += "\n"
                
                message += f"📊 Total: {len(events)} evento(s)"
            else:
                message += "✨ Semana livre! Nenhum evento agendado."
            
            # Enviar
            await self.notifications.send_telegram(TELEGRAM_CHAT_ID, message)
            await self.notifications.send_whatsapp(WHATSAPP_NUMBER, message)
            
            self.state.mark_weekly_digest_sent()
            logger.info("Resumo semanal enviado!")
            
        except Exception as e:
            logger.error(f"Erro ao enviar resumo semanal: {e}")
    
    async def run(self):
        """Loop principal do serviço"""
        logger.info("🚀 Serviço de lembretes iniciado!")
        
        # Verificar autenticação
        if not self.calendar.is_authenticated():
            logger.error("❌ Não autenticado! Execute setup_google_calendar.py primeiro.")
            return
        
        logger.info("✅ Autenticado com Google Calendar")
        
        while self.running:
            try:
                now = datetime.now()
                
                # Verificar lembretes
                await self.check_reminders()
                
                # Verificar agenda diária (enviar no horário configurado)
                if now.hour == DAILY_DIGEST_HOUR and now.minute < 5:
                    if self.state.should_send_daily_digest():
                        await self.send_daily_digest()
                
                # Verificar resumo semanal
                if now.hour == DAILY_DIGEST_HOUR and now.minute < 5:
                    if self.state.should_send_weekly_digest():
                        await self.send_weekly_digest()
                
                # Limpeza periódica
                if now.minute == 0:
                    self.state.cleanup_old_reminders()
                
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
            
            # Aguardar intervalo
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
        
        logger.info("🛑 Serviço de lembretes encerrado.")
    
    def stop(self):
        """Para o serviço"""
        self.running = False


# Instância global
_service: CalendarReminderService = None


def signal_handler(signum, frame):
    """Handler para sinais de término"""
    global _service
    logger.info(f"Recebido sinal {signum}, encerrando...")
    if _service:
        _service.stop()


async def main():
    """Função principal"""
    global _service
    
    # Configurar handlers de sinal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    _service = CalendarReminderService()
    await _service.run()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║     🗓️  Eddie Calendar Reminder Service                   ║
╠════════════════════════════════════════════════════════════╣
║  Enviando lembretes via Telegram e WhatsApp               ║
║  Pressione Ctrl+C para encerrar                           ║
╚════════════════════════════════════════════════════════════╝
""")
    
    asyncio.run(main())
