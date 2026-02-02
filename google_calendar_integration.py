#!/usr/bin/env python3
"""
Integração Google Calendar para Eddie Assistant
Permite criar, listar, editar e deletar eventos do Google Calendar
Envia notificações via Telegram e WhatsApp

Autor: Eddie Assistant
Data: 2026
"""

import os
import pickle
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import logging
from dateutil import parser as date_parser
import re

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("GoogleCalendar")

# Diretório de dados
DATA_DIR = Path(__file__).parent / "calendar_data"
DATA_DIR.mkdir(exist_ok=True)

# Arquivo de credenciais
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.pickle"
EVENTS_CACHE = DATA_DIR / "events_cache.json"

# Configurações Google Calendar API
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

# Configurações de notificação (sempre obter chaves do cofre)
try:
    from tools.secrets_loader import get_telegram_token, get_telegram_chat_id

    TELEGRAM_BOT_TOKEN = get_telegram_token()
    TELEGRAM_ADMIN_CHAT_ID = get_telegram_chat_id()
except Exception:
    TELEGRAM_BOT_TOKEN = ""
    TELEGRAM_ADMIN_CHAT_ID = ""
try:
    TELEGRAM_ADMIN_CHAT_ID = int(TELEGRAM_ADMIN_CHAT_ID)
except Exception:
    TELEGRAM_ADMIN_CHAT_ID = None
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "5511981193899")
WAHA_API = os.getenv("WAHA_API", "http://localhost:3001")


@dataclass
class CalendarEvent:
    """Representa um evento do calendário"""

    id: str
    summary: str
    description: str = ""
    start: datetime = None
    end: datetime = None
    location: str = ""
    attendees: List[str] = field(default_factory=list)
    reminders: List[int] = field(default_factory=lambda: [30, 10])  # minutos
    recurring: str = None  # DAILY, WEEKLY, MONTHLY, YEARLY
    all_day: bool = False
    color_id: str = None
    created_at: datetime = None
    updated_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para API"""
        event_dict = {
            "summary": self.summary,
            "description": self.description or "",
            "location": self.location or "",
        }

        if self.all_day:
            event_dict["start"] = {"date": self.start.strftime("%Y-%m-%d")}
            event_dict["end"] = {"date": self.end.strftime("%Y-%m-%d")}
        else:
            event_dict["start"] = {
                "dateTime": self.start.isoformat(),
                "timeZone": "America/Sao_Paulo",
            }
            event_dict["end"] = {
                "dateTime": self.end.isoformat(),
                "timeZone": "America/Sao_Paulo",
            }

        if self.attendees:
            event_dict["attendees"] = [{"email": email} for email in self.attendees]

        if self.reminders:
            event_dict["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": m} for m in self.reminders
                ],
            }

        if self.recurring:
            freq_map = {
                "DAILY": "DAILY",
                "WEEKLY": "WEEKLY",
                "MONTHLY": "MONTHLY",
                "YEARLY": "YEARLY",
            }
            if self.recurring.upper() in freq_map:
                event_dict["recurrence"] = [
                    f"RRULE:FREQ={freq_map[self.recurring.upper()]}"
                ]

        if self.color_id:
            event_dict["colorId"] = self.color_id

        return event_dict

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "CalendarEvent":
        """Cria evento a partir de dados da API"""
        start_data = data.get("start", {})
        end_data = data.get("end", {})

        # Verificar se é evento de dia inteiro
        all_day = "date" in start_data

        if all_day:
            start = datetime.strptime(start_data["date"], "%Y-%m-%d")
            end = datetime.strptime(end_data["date"], "%Y-%m-%d")
        else:
            start = date_parser.parse(start_data.get("dateTime", ""))
            end = date_parser.parse(end_data.get("dateTime", ""))

        # Extrair lembretes
        reminders = []
        reminder_data = data.get("reminders", {})
        if not reminder_data.get("useDefault"):
            for override in reminder_data.get("overrides", []):
                reminders.append(override.get("minutes", 30))
        else:
            reminders = [30]

        # Extrair participantes
        attendees = [a.get("email") for a in data.get("attendees", [])]

        # Extrair recorrência
        recurring = None
        recurrence = data.get("recurrence", [])
        if recurrence:
            for rule in recurrence:
                if "FREQ=" in rule:
                    freq_match = re.search(r"FREQ=(\w+)", rule)
                    if freq_match:
                        recurring = freq_match.group(1)

        return cls(
            id=data.get("id", ""),
            summary=data.get("summary", "Sem título"),
            description=data.get("description", ""),
            start=start,
            end=end,
            location=data.get("location", ""),
            attendees=attendees,
            reminders=reminders,
            recurring=recurring,
            all_day=all_day,
            color_id=data.get("colorId"),
            created_at=(
                date_parser.parse(data["created"]) if "created" in data else None
            ),
            updated_at=(
                date_parser.parse(data["updated"]) if "updated" in data else None
            ),
        )

    def format_for_display(self) -> str:
        """Formata evento para exibição"""
        lines = [f"📅 **{self.summary}**"]

        if self.all_day:
            date_str = self.start.strftime("%d/%m/%Y")
            if self.end and self.end != self.start:
                date_str += f" - {self.end.strftime('%d/%m/%Y')}"
            lines.append(f"📆 Dia inteiro: {date_str}")
        else:
            start_str = self.start.strftime("%d/%m/%Y %H:%M")
            end_str = self.end.strftime("%H:%M") if self.end else ""
            lines.append(f"🕐 {start_str} - {end_str}")

        if self.location:
            lines.append(f"📍 {self.location}")

        if self.description:
            desc = (
                self.description[:100] + "..."
                if len(self.description) > 100
                else self.description
            )
            lines.append(f"📝 {desc}")

        if self.attendees:
            lines.append(f"👥 Participantes: {', '.join(self.attendees[:3])}")
            if len(self.attendees) > 3:
                lines.append(f"   ...e mais {len(self.attendees) - 3}")

        if self.recurring:
            freq_names = {
                "DAILY": "Diário",
                "WEEKLY": "Semanal",
                "MONTHLY": "Mensal",
                "YEARLY": "Anual",
            }
            lines.append(
                f"🔄 Repetição: {freq_names.get(self.recurring, self.recurring)}"
            )

        return "\n".join(lines)


class GoogleCalendarClient:
    """Cliente para Google Calendar API"""

    def __init__(self):
        self.service = None
        self.credentials = None
        self.calendar_id = "primary"
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self._load_credentials()

    def _load_credentials(self):
        """Carrega credenciais do arquivo"""
        try:
            if TOKEN_FILE.exists():
                with open(TOKEN_FILE, "rb") as f:
                    self.credentials = pickle.load(f)
                logger.info("Credenciais carregadas do cache")
        except Exception as e:
            logger.warning(f"Erro ao carregar credenciais: {e}")
            self.credentials = None

    def _save_credentials(self):
        """Salva credenciais no arquivo"""
        try:
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(self.credentials, f)
            logger.info("Credenciais salvas no cache")
        except Exception as e:
            logger.error(f"Erro ao salvar credenciais: {e}")

    def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        if not self.credentials:
            return False

        # Verificar se token é válido
        if hasattr(self.credentials, "expired"):
            return not self.credentials.expired

        return True

    async def authenticate(self, auth_code: str = None) -> Tuple[bool, str]:
        """
        Autentica com Google Calendar
        Se auth_code não fornecido, retorna URL de autenticação
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            # Verificar se já tem credenciais válidas
            if self.credentials and not self.credentials.expired:
                self.service = build("calendar", "v3", credentials=self.credentials)
                return True, "Já autenticado!"

            # Tentar refresh se expirado
            if (
                self.credentials
                and self.credentials.expired
                and self.credentials.refresh_token
            ):
                try:
                    self.credentials.refresh(Request())
                    self._save_credentials()
                    self.service = build("calendar", "v3", credentials=self.credentials)
                    return True, "Token renovado com sucesso!"
                except Exception as e:
                    logger.warning(f"Falha ao renovar token: {e}")

            # Iniciar novo fluxo de autenticação
            if not CREDENTIALS_FILE.exists():
                return (
                    False,
                    "Arquivo credentials.json não encontrado. Execute setup_google_calendar.py primeiro.",
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )

            if auth_code:
                # Completar autenticação com código
                flow.fetch_token(code=auth_code)
                self.credentials = flow.credentials
                self._save_credentials()
                self.service = build("calendar", "v3", credentials=self.credentials)
                return True, "Autenticação concluída com sucesso!"
            else:
                # Retornar URL para autenticação manual
                auth_url, _ = flow.authorization_url(prompt="consent")
                return (
                    False,
                    f"Acesse esta URL para autorizar:\n{auth_url}\n\nDepois use: /calendar auth <código>",
                )

        except ImportError:
            return (
                False,
                "Bibliotecas Google não instaladas. Execute: pip install google-auth-oauthlib google-api-python-client",
            )
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            return False, f"Erro na autenticação: {str(e)}"

    async def ensure_service(self) -> bool:
        """Garante que o serviço está inicializado"""
        if self.service:
            return True

        if not self.credentials:
            return False

        try:
            from googleapiclient.discovery import build

            self.service = build("calendar", "v3", credentials=self.credentials)
            return True
        except Exception as e:
            logger.error(f"Erro ao inicializar serviço: {e}")
            return False

    async def create_event(
        self, event: CalendarEvent
    ) -> Tuple[bool, str, Optional[CalendarEvent]]:
        """Cria um novo evento"""
        if not await self.ensure_service():
            return False, "Não autenticado. Use /calendar auth", None

        try:
            event_body = event.to_dict()
            result = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute()
            )

            created_event = CalendarEvent.from_api(result)
            logger.info(f"Evento criado: {created_event.id}")
            return True, f"✅ Evento criado!\nID: {created_event.id}", created_event

        except Exception as e:
            logger.error(f"Erro ao criar evento: {e}")
            return False, f"❌ Erro ao criar evento: {str(e)}", None

    async def get_event(
        self, event_id: str
    ) -> Tuple[bool, str, Optional[CalendarEvent]]:
        """Obtém um evento específico"""
        if not await self.ensure_service():
            return False, "Não autenticado", None

        try:
            result = (
                self.service.events()
                .get(calendarId=self.calendar_id, eventId=event_id)
                .execute()
            )

            event = CalendarEvent.from_api(result)
            return True, "Evento encontrado", event

        except Exception as e:
            logger.error(f"Erro ao buscar evento: {e}")
            return False, f"Erro ao buscar evento: {str(e)}", None

    async def update_event(
        self, event_id: str, event: CalendarEvent
    ) -> Tuple[bool, str]:
        """Atualiza um evento existente"""
        if not await self.ensure_service():
            return False, "Não autenticado"

        try:
            event_body = event.to_dict()
            self.service.events().update(
                calendarId=self.calendar_id, eventId=event_id, body=event_body
            ).execute()

            logger.info(f"Evento atualizado: {event_id}")
            return True, "✅ Evento atualizado!"

        except Exception as e:
            logger.error(f"Erro ao atualizar evento: {e}")
            return False, f"❌ Erro ao atualizar: {str(e)}"

    async def delete_event(self, event_id: str) -> Tuple[bool, str]:
        """Deleta um evento"""
        if not await self.ensure_service():
            return False, "Não autenticado"

        try:
            self.service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()

            logger.info(f"Evento deletado: {event_id}")
            return True, "✅ Evento deletado!"

        except Exception as e:
            logger.error(f"Erro ao deletar evento: {e}")
            return False, f"❌ Erro ao deletar: {str(e)}"

    async def list_events(
        self,
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 10,
        query: str = None,
    ) -> Tuple[bool, str, List[CalendarEvent]]:
        """Lista eventos do calendário"""
        if not await self.ensure_service():
            return False, "Não autenticado", []

        try:
            if not time_min:
                time_min = datetime.now()
            if not time_max:
                time_max = time_min + timedelta(days=30)

            params = {
                "calendarId": self.calendar_id,
                "timeMin": (
                    time_min.isoformat() + "Z"
                    if time_min.tzinfo is None
                    else time_min.isoformat()
                ),
                "timeMax": (
                    time_max.isoformat() + "Z"
                    if time_max.tzinfo is None
                    else time_max.isoformat()
                ),
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if query:
                params["q"] = query

            result = self.service.events().list(**params).execute()

            events = [CalendarEvent.from_api(e) for e in result.get("items", [])]

            if events:
                msg = f"📅 **{len(events)} evento(s) encontrado(s)**\n\n"
                for i, event in enumerate(events, 1):
                    msg += f"{i}. {event.format_for_display()}\n\n"
            else:
                msg = "📅 Nenhum evento encontrado no período."

            return True, msg, events

        except Exception as e:
            logger.error(f"Erro ao listar eventos: {e}")
            return False, f"Erro ao listar eventos: {str(e)}", []

    async def get_upcoming_events(self, hours: int = 24) -> List[CalendarEvent]:
        """Obtém eventos das próximas horas"""
        time_min = datetime.now()
        time_max = time_min + timedelta(hours=hours)

        _, _, events = await self.list_events(
            time_min=time_min, time_max=time_max, max_results=50
        )

        return events

    async def search_free_time(
        self,
        duration_minutes: int,
        date: datetime = None,
        work_hours: Tuple[int, int] = (9, 18),
    ) -> List[Tuple[datetime, datetime]]:
        """Busca horários livres no calendário"""
        if not date:
            date = datetime.now()

        # Buscar eventos do dia
        day_start = date.replace(hour=work_hours[0], minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=work_hours[1], minute=0, second=0, microsecond=0)

        _, _, events = await self.list_events(
            time_min=day_start, time_max=day_end, max_results=100
        )

        # Encontrar slots livres
        free_slots = []
        current_time = day_start

        for event in sorted(events, key=lambda e: e.start):
            if event.start > current_time:
                slot_duration = (event.start - current_time).total_seconds() / 60
                if slot_duration >= duration_minutes:
                    free_slots.append((current_time, event.start))
            current_time = max(current_time, event.end)

        # Verificar se há tempo após último evento
        if current_time < day_end:
            slot_duration = (day_end - current_time).total_seconds() / 60
            if slot_duration >= duration_minutes:
                free_slots.append((current_time, day_end))

        return free_slots

    async def list_calendars(self) -> Tuple[bool, str, List[Dict]]:
        """Lista todos os calendários disponíveis"""
        if not await self.ensure_service():
            return False, "Não autenticado", []

        try:
            result = self.service.calendarList().list().execute()
            calendars = result.get("items", [])

            msg = "📚 **Calendários disponíveis:**\n\n"
            for cal in calendars:
                primary = "⭐ " if cal.get("primary") else ""
                msg += f"{primary}• {cal.get('summary')}\n  ID: `{cal.get('id')}`\n\n"

            return True, msg, calendars

        except Exception as e:
            logger.error(f"Erro ao listar calendários: {e}")
            return False, f"Erro: {str(e)}", []

    def set_calendar(self, calendar_id: str):
        """Define o calendário a ser usado"""
        self.calendar_id = calendar_id
        logger.info(f"Calendário alterado para: {calendar_id}")


class NotificationManager:
    """Gerenciador de notificações via Telegram e WhatsApp"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.telegram_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    async def send_telegram(self, chat_id: int, message: str) -> bool:
        """Envia notificação via Telegram"""
        try:
            response = await self.http_client.post(
                f"{self.telegram_api}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar Telegram: {e}")
            return False

    async def send_whatsapp(self, number: str, message: str) -> bool:
        """Envia notificação via WhatsApp (WAHA)"""
        try:
            # Formato do número: 5511999999999
            if not number.startswith("55"):
                number = "55" + number

            chat_id = f"{number}@s.whatsapp.net"

            response = await self.http_client.post(
                f"{WAHA_API}/api/sendText",
                json={"chatId": chat_id, "text": message, "session": "default"},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {e}")
            return False

    async def send_event_notification(
        self,
        event: CalendarEvent,
        notification_type: str = "reminder",
        telegram_chat_id: int = None,
        whatsapp_number: str = None,
    ):
        """Envia notificação de evento"""

        if notification_type == "reminder":
            emoji = "⏰"
            title = "LEMBRETE DE EVENTO"
        elif notification_type == "created":
            emoji = "✅"
            title = "EVENTO CRIADO"
        elif notification_type == "updated":
            emoji = "📝"
            title = "EVENTO ATUALIZADO"
        elif notification_type == "deleted":
            emoji = "🗑️"
            title = "EVENTO CANCELADO"
        else:
            emoji = "📅"
            title = "EVENTO"

        message = f"{emoji} **{title}**\n\n{event.format_for_display()}"

        results = []

        # Enviar para Telegram
        if telegram_chat_id or TELEGRAM_ADMIN_CHAT_ID:
            target_chat = telegram_chat_id or TELEGRAM_ADMIN_CHAT_ID
            success = await self.send_telegram(target_chat, message)
            results.append(("Telegram", success))

        # Enviar para WhatsApp
        if whatsapp_number or WHATSAPP_NUMBER:
            target_number = whatsapp_number or WHATSAPP_NUMBER
            success = await self.send_whatsapp(target_number, message)
            results.append(("WhatsApp", success))

        return results

    async def send_daily_agenda(
        self,
        events: List[CalendarEvent],
        telegram_chat_id: int = None,
        whatsapp_number: str = None,
    ):
        """Envia agenda diária"""

        today = datetime.now().strftime("%d/%m/%Y")

        if events:
            message = f"📆 **AGENDA DO DIA - {today}**\n\n"
            for i, event in enumerate(events, 1):
                time_str = (
                    event.start.strftime("%H:%M")
                    if not event.all_day
                    else "Dia inteiro"
                )
                message += f"{i}. {time_str} - {event.summary}\n"
                if event.location:
                    message += f"   📍 {event.location}\n"
            message += f"\n📊 Total: {len(events)} evento(s)"
        else:
            message = f"📆 **AGENDA DO DIA - {today}**\n\n✨ Sem eventos agendados!"

        results = []

        if telegram_chat_id or TELEGRAM_ADMIN_CHAT_ID:
            success = await self.send_telegram(
                telegram_chat_id or TELEGRAM_ADMIN_CHAT_ID, message
            )
            results.append(("Telegram", success))

        if whatsapp_number or WHATSAPP_NUMBER:
            success = await self.send_whatsapp(
                whatsapp_number or WHATSAPP_NUMBER, message
            )
            results.append(("WhatsApp", success))

        return results


class CalendarAssistant:
    """Assistente de calendário com processamento de linguagem natural"""

    def __init__(self):
        self.calendar = GoogleCalendarClient()
        self.notifications = NotificationManager()
        self.pending_events: Dict[str, CalendarEvent] = {}

    def parse_datetime(
        self, text: str, reference: datetime = None
    ) -> Optional[datetime]:
        """Converte texto em datetime"""
        if not reference:
            reference = datetime.now()

        text = text.lower().strip()

        # Padrões relativos
        relative_patterns = {
            "agora": timedelta(minutes=0),
            "daqui a pouco": timedelta(minutes=30),
            "em 1 hora": timedelta(hours=1),
            "em uma hora": timedelta(hours=1),
            "em 2 horas": timedelta(hours=2),
            "em duas horas": timedelta(hours=2),
            "amanhã": timedelta(days=1),
            "depois de amanhã": timedelta(days=2),
            "próxima semana": timedelta(weeks=1),
            "semana que vem": timedelta(weeks=1),
            "próximo mês": timedelta(days=30),
        }

        for pattern, delta in relative_patterns.items():
            if pattern in text:
                result = reference + delta
                # Verificar se tem horário específico
                time_match = re.search(r"(\d{1,2})[h:](\d{2})?", text)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    result = result.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                return result

        # Dias da semana
        days_of_week = {
            "segunda": 0,
            "terça": 1,
            "quarta": 2,
            "quinta": 3,
            "sexta": 4,
            "sábado": 5,
            "domingo": 6,
        }

        for day_name, day_num in days_of_week.items():
            if day_name in text:
                days_ahead = day_num - reference.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                result = reference + timedelta(days=days_ahead)

                time_match = re.search(r"(\d{1,2})[h:](\d{2})?", text)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    result = result.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                else:
                    result = result.replace(hour=9, minute=0, second=0, microsecond=0)

                return result

        # Tentar parse direto
        try:
            # Formatos comuns brasileiros
            formats = [
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y %Hh%M",
                "%d/%m/%Y às %H:%M",
                "%d/%m/%Y",
                "%d/%m %H:%M",
                "%d/%m",
                "%H:%M",
                "%Hh%M",
                "%Hh",
            ]

            for fmt in formats:
                try:
                    result = datetime.strptime(text, fmt)
                    # Ajustar ano se não especificado
                    if result.year == 1900:
                        result = result.replace(year=reference.year)
                    # Ajustar dia se apenas hora
                    if "%d" not in fmt:
                        result = result.replace(
                            year=reference.year,
                            month=reference.month,
                            day=reference.day,
                        )
                    return result
                except:
                    continue

            # Usar dateutil como fallback
            return date_parser.parse(text, dayfirst=True, fuzzy=True)

        except:
            return None

    def parse_duration(self, text: str) -> timedelta:
        """Converte texto em duração"""
        text = text.lower()

        # Padrões de duração
        hour_match = re.search(r"(\d+)\s*h", text)
        min_match = re.search(r"(\d+)\s*min", text)

        hours = int(hour_match.group(1)) if hour_match else 0
        minutes = int(min_match.group(1)) if min_match else 0

        if hours == 0 and minutes == 0:
            # Padrão: 1 hora
            return timedelta(hours=1)

        return timedelta(hours=hours, minutes=minutes)

    async def parse_event_from_text(
        self, text: str
    ) -> Tuple[Optional[CalendarEvent], str]:
        """Extrai informações de evento a partir de texto natural"""

        # Padrões para extrair informações
        patterns = {
            "title": r'(?:agendar?|criar?|marcar?|adicionar?)\s+(?:uma?\s+)?(?:reunião|evento|compromisso|consulta|tarefa)?\s*(?:de|sobre|para|com)?\s*["\']?([^"\']+?)["\']?\s*(?:para|em|no dia|às|amanhã|hoje|$)',
            "date": r"(?:para|em|no dia)\s+(\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?)",
            "time": r"(?:às?|as)\s+(\d{1,2}[h:]?\d{0,2})",
            "duration": r"(?:duração|durante|por)\s+(\d+\s*(?:h|hora|min|minuto)s?)",
            "location": r"(?:em|no|na|local:?)\s+([^,\.]+?)(?:,|\.|$)",
            "with": r"(?:com)\s+([^,\.]+?)(?:,|\.|$)",
        }

        event = CalendarEvent(
            id="",
            summary="",
            start=datetime.now() + timedelta(hours=1),
            end=datetime.now() + timedelta(hours=2),
        )

        # Extrair título
        title_patterns = [
            r"(?:agendar?|criar?|marcar?)\s+(.+?)\s+(?:para|em|às|amanhã)",
            r"(?:reunião|evento|compromisso)\s+(?:de|sobre|com)\s+(.+?)\s+(?:para|em|às)",
            r"(?:lembrar?|lembrete)\s+(?:de|para)?\s+(.+?)\s+(?:para|em|às|amanhã)",
        ]

        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                event.summary = match.group(1).strip()
                break

        if not event.summary:
            # Usar o texto todo como título (simplificado)
            event.summary = text[:50] + ("..." if len(text) > 50 else "")

        # Extrair data/hora
        datetime_result = self.parse_datetime(text)
        if datetime_result:
            event.start = datetime_result
            event.end = datetime_result + timedelta(hours=1)

        # Extrair duração
        duration_match = re.search(patterns["duration"], text, re.IGNORECASE)
        if duration_match:
            duration = self.parse_duration(duration_match.group(1))
            event.end = event.start + duration

        # Extrair local
        location_match = re.search(patterns["location"], text, re.IGNORECASE)
        if location_match:
            event.location = location_match.group(1).strip()

        # Verificar se é dia inteiro
        if "dia inteiro" in text.lower() or "o dia todo" in text.lower():
            event.all_day = True
            event.start = event.start.replace(hour=0, minute=0, second=0)
            event.end = event.start + timedelta(days=1)

        # Verificar recorrência
        if "diário" in text.lower() or "todo dia" in text.lower():
            event.recurring = "DAILY"
        elif "semanal" in text.lower() or "toda semana" in text.lower():
            event.recurring = "WEEKLY"
        elif "mensal" in text.lower() or "todo mês" in text.lower():
            event.recurring = "MONTHLY"
        elif "anual" in text.lower() or "todo ano" in text.lower():
            event.recurring = "YEARLY"

        # Gerar confirmação
        confirm_msg = f"""📝 **Confirme o evento:**

📌 **Título:** {event.summary}
📅 **Data:** {event.start.strftime("%d/%m/%Y")}
🕐 **Horário:** {event.start.strftime("%H:%M")} - {event.end.strftime("%H:%M")}
{"📍 **Local:** " + event.location if event.location else ""}
{"🔄 **Repetição:** " + event.recurring if event.recurring else ""}

Responda:
✅ **sim** - confirmar criação
✏️ **editar** - modificar detalhes
❌ **cancelar** - cancelar"""

        return event, confirm_msg

    async def process_command(
        self, command: str, args: str = "", user_id: str = None
    ) -> str:
        """Processa comandos do calendário"""

        command = command.lower().strip()

        if command in ["auth", "login", "autorizar"]:
            success, msg = await self.calendar.authenticate(args if args else None)
            return msg

        if command in ["listar", "list", "eventos", "agenda"]:
            # Verificar período
            if "hoje" in args.lower():
                time_min = datetime.now().replace(hour=0, minute=0, second=0)
                time_max = time_min + timedelta(days=1)
            elif "amanhã" in args.lower() or "amanha" in args.lower():
                time_min = (datetime.now() + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0
                )
                time_max = time_min + timedelta(days=1)
            elif "semana" in args.lower():
                time_min = datetime.now()
                time_max = time_min + timedelta(weeks=1)
            elif "mês" in args.lower() or "mes" in args.lower():
                time_min = datetime.now()
                time_max = time_min + timedelta(days=30)
            else:
                time_min = datetime.now()
                time_max = time_min + timedelta(days=7)

            success, msg, _ = await self.calendar.list_events(time_min, time_max)
            return msg

        if command in ["criar", "create", "agendar", "novo", "add"]:
            if not args:
                return """📅 **Como criar um evento:**

Exemplos:
• `/calendar criar Reunião com equipe para amanhã às 14h`
• `/calendar criar Consulta médica 25/01/2026 10:00`
• `/calendar criar Aniversário do João dia 15/02 dia inteiro`

Você também pode simplesmente me pedir:
"Agende uma reunião para quinta às 15h" """

            event, confirm_msg = await self.parse_event_from_text(args)
            self.pending_events[user_id] = event
            return confirm_msg

        if command in ["confirmar", "sim", "yes", "ok"]:
            if user_id not in self.pending_events:
                return "❌ Não há evento pendente para confirmar."

            event = self.pending_events.pop(user_id)
            success, msg, created_event = await self.calendar.create_event(event)

            if success and created_event:
                # Enviar notificações
                await self.notifications.send_event_notification(
                    created_event, notification_type="created"
                )

            return msg

        if command in ["cancelar", "cancel", "não", "nao"]:
            if user_id in self.pending_events:
                del self.pending_events[user_id]
            return "❌ Operação cancelada."

        if command in ["deletar", "delete", "remover", "excluir"]:
            if not args:
                return "❌ Especifique o ID do evento. Use `/calendar listar` para ver os IDs."

            success, msg = await self.calendar.delete_event(args.strip())
            return msg

        if command in ["buscar", "search", "procurar"]:
            if not args:
                return "❌ Especifique o termo de busca."

            success, msg, _ = await self.calendar.list_events(query=args)
            return msg

        if command in ["livre", "free", "disponível", "disponivel"]:
            # Buscar horários livres
            duration = 60  # padrão: 1 hora

            duration_match = re.search(r"(\d+)", args)
            if duration_match:
                duration = int(duration_match.group(1))

            free_slots = await self.calendar.search_free_time(duration)

            if free_slots:
                msg = f"🕐 **Horários livres (mín. {duration} min):**\n\n"
                for start, end in free_slots[:5]:
                    msg += f"• {start.strftime('%H:%M')} - {end.strftime('%H:%M')}\n"
            else:
                msg = "😅 Sem horários livres disponíveis hoje!"

            return msg

        if command in ["calendarios", "calendars"]:
            success, msg, _ = await self.calendar.list_calendars()
            return msg

        if command in ["ajuda", "help", "comandos"]:
            return """📅 **Comandos do Calendário:**

🔐 **Autenticação:**
• `/calendar auth` - Inicia autenticação
• `/calendar auth <código>` - Completa com código

📋 **Listar eventos:**
• `/calendar listar` - Próximos 7 dias
• `/calendar listar hoje` - Eventos de hoje
• `/calendar listar amanhã` - Eventos de amanhã
• `/calendar listar semana` - Próxima semana

➕ **Criar eventos:**
• `/calendar criar <descrição>` - Cria evento
• `/calendar criar Reunião amanhã às 14h`
• Ou diga: "Agende uma reunião..."

🔍 **Buscar:**
• `/calendar buscar <termo>` - Busca eventos
• `/calendar livre` - Horários disponíveis

🗑️ **Gerenciar:**
• `/calendar deletar <id>` - Remove evento
• `/calendar calendarios` - Lista calendários

💡 **Dicas:**
Você pode me pedir naturalmente:
• "Me lembre de ligar para o cliente amanhã às 10h"
• "Agende reunião com João na sexta"
• "O que tenho agendado para hoje?" """

        # Comando não reconhecido - tentar interpretar como criação de evento
        if args:
            full_text = f"{command} {args}"
        else:
            full_text = command

        event, confirm_msg = await self.parse_event_from_text(full_text)
        self.pending_events[user_id] = event
        return confirm_msg


# Instância global
_calendar_assistant: Optional[CalendarAssistant] = None


def get_calendar_assistant() -> CalendarAssistant:
    """Obtém instância do assistente de calendário"""
    global _calendar_assistant
    if _calendar_assistant is None:
        _calendar_assistant = CalendarAssistant()
    return _calendar_assistant


async def process_calendar_request(text: str, user_id: str = None) -> str:
    """Processa requisição de calendário a partir de texto"""
    assistant = get_calendar_assistant()

    # Verificar se é comando direto
    if text.startswith("/calendar"):
        parts = text[9:].strip().split(" ", 1)
        command = parts[0] if parts else "ajuda"
        args = parts[1] if len(parts) > 1 else ""
        return await assistant.process_command(command, args, user_id)

    # Detectar intenção de calendário
    calendar_keywords = [
        "agendar",
        "agenda",
        "calendário",
        "calendario",
        "evento",
        "reunião",
        "reuniao",
        "compromisso",
        "lembrete",
        "lembrar",
        "marcar",
        "horário",
        "horario",
        "disponível",
        "disponivel",
        "livre",
        "consulta",
        "encontro",
    ]

    text_lower = text.lower()

    if any(kw in text_lower for kw in calendar_keywords):
        # Verificar tipo de ação
        if any(
            word in text_lower
            for word in [
                "listar",
                "quais",
                "o que tenho",
                "meus eventos",
                "minha agenda",
            ]
        ):
            return await assistant.process_command("listar", text, user_id)
        elif any(
            word in text_lower
            for word in ["agendar", "criar", "marcar", "lembrar", "lembrete"]
        ):
            return await assistant.process_command("criar", text, user_id)
        elif any(word in text_lower for word in ["cancelar", "remover", "deletar"]):
            return await assistant.process_command("deletar", text, user_id)
        elif any(word in text_lower for word in ["livre", "disponível", "horário"]):
            return await assistant.process_command("livre", text, user_id)

    # Verificar confirmação pendente
    if user_id and user_id in assistant.pending_events:
        if any(
            word in text_lower
            for word in ["sim", "confirmar", "ok", "confirma", "isso"]
        ):
            return await assistant.process_command("confirmar", "", user_id)
        elif any(word in text_lower for word in ["não", "nao", "cancelar", "cancela"]):
            return await assistant.process_command("cancelar", "", user_id)

    return None


# Teste standalone
if __name__ == "__main__":

    async def test():
        assistant = get_calendar_assistant()

        # Testar parse de data
        tests = [
            "reunião amanhã às 14h",
            "consulta dia 20/01/2026 às 10:00",
            "evento na próxima segunda às 9h",
            "lembrete daqui a 2 horas",
        ]

        for text in tests:
            event, msg = await assistant.parse_event_from_text(text)
            print(f"\nTexto: {text}")
            print(f"Evento: {event.summary}")
            print(f"Data: {event.start}")

        # Testar comandos
        print("\n" + "=" * 50)
        print(await assistant.process_command("ajuda"))

    asyncio.run(test())
