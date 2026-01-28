#!/usr/bin/env python3
"""
Gmail Expurgo Inteligente - Limpa emails + Treina IA + Lembretes Inteligentes
Versão avançada com integração completa ao ecossistema Eddie

Funcionalidades:
1. Expurgo de emails por categoria/idade
2. Treinamento da IA eddie-* com emails importantes antes de excluir
3. Notificações inteligentes via WhatsApp e Telegram
4. Agendamento automático de lembretes baseado no conteúdo

Autor: Eddie Assistant
Data: 2026
"""

import os
import sys
import json
import asyncio
import hashlib
import requests
import httpx
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ExpurgoInteligente')

# Paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# Configurações
GMAIL_DATA_DIR = os.getenv("GMAIL_DATA_DIR", "/home/homelab/myClaude/gmail_data")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3001")
from tools.secrets_loader import get_telegram_token

TELEGRAM_BOT_TOKEN = get_telegram_token()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "948686300"))
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "5511999999999")

# Imports do ecossistema
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API não disponível")

try:
    from email_trainer import EmailTrainer, get_email_trainer
    TRAINER_AVAILABLE = True
except ImportError:
    TRAINER_AVAILABLE = False
    logger.warning("EmailTrainer não disponível")


class NotificationType(Enum):
    """Tipos de notificação"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    REMINDER = "reminder"


class MessagePriority(Enum):
    """Prioridade da mensagem"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class SmartReminder:
    """Lembrete inteligente extraído do email"""
    title: str
    description: str
    due_date: Optional[datetime]
    source_email_id: str
    source_subject: str
    priority: MessagePriority
    keywords: List[str]
    action_required: bool


class NotificationService:
    """Serviço unificado de notificações via WhatsApp e Telegram"""
    
    def __init__(self):
        self.waha_url = WAHA_URL
        self.telegram_token = TELEGRAM_BOT_TOKEN
        self.admin_chat_id = ADMIN_CHAT_ID
        self.admin_phone = ADMIN_PHONE
        self.telegram_api = f"https://api.telegram.org/bot{self.telegram_token}"
        
    async def send_telegram(self, message: str, chat_id: int = None, 
                           parse_mode: str = "Markdown") -> Tuple[bool, str]:
        """Envia mensagem via Telegram"""
        chat_id = chat_id or self.admin_chat_id
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.telegram_api}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message[:4096],
                        "parse_mode": parse_mode
                    }
                )
                
                if response.status_code == 200:
                    return True, "Telegram: mensagem enviada"
                else:
                    return False, f"Telegram erro: {response.text}"
                    
        except Exception as e:
            return False, f"Telegram erro: {e}"
    
    def send_whatsapp(self, message: str, phone: str = None) -> Tuple[bool, str]:
        """Envia mensagem via WhatsApp (WAHA)"""
        phone = phone or self.admin_phone
        
        # Formatar número
        phone_clean = ''.join(filter(str.isdigit, phone))
        if len(phone_clean) == 11:
            phone_clean = f"55{phone_clean}"
        elif len(phone_clean) == 10:
            phone_clean = f"5511{phone_clean}"
        
        chat_id = f"{phone_clean}@s.whatsapp.net"
        
        try:
            response = requests.post(
                f"{self.waha_url}/api/sendText",
                json={
                    "session": "default",
                    "chatId": chat_id,
                    "text": message
                },
                timeout=30
            )
            
            if response.status_code == 201:
                return True, "WhatsApp: mensagem enviada"
            else:
                return False, f"WhatsApp erro: {response.text}"
                
        except requests.exceptions.ConnectionError:
            return False, "WhatsApp: WAHA não disponível"
        except Exception as e:
            return False, f"WhatsApp erro: {e}"
    
    async def notify(self, message: str, 
                    notification_type: NotificationType = NotificationType.INFO,
                    channels: List[str] = None,
                    priority: MessagePriority = MessagePriority.NORMAL) -> Dict[str, Any]:
        """Envia notificação por múltiplos canais"""
        
        channels = channels or ["telegram", "whatsapp"]
        results = {"success": [], "failed": []}
        
        # Adicionar emoji baseado no tipo
        emoji_map = {
            NotificationType.INFO: "ℹ️",
            NotificationType.SUCCESS: "✅",
            NotificationType.WARNING: "⚠️",
            NotificationType.ERROR: "❌",
            NotificationType.REMINDER: "🔔"
        }
        emoji = emoji_map.get(notification_type, "📬")
        formatted_message = f"{emoji} {message}"
        
        # Enviar para cada canal
        if "telegram" in channels:
            success, msg = await self.send_telegram(formatted_message)
            if success:
                results["success"].append("telegram")
            else:
                results["failed"].append(f"telegram: {msg}")
        
        if "whatsapp" in channels:
            success, msg = self.send_whatsapp(formatted_message)
            if success:
                results["success"].append("whatsapp")
            else:
                results["failed"].append(f"whatsapp: {msg}")
        
        return results
    
    async def send_reminder(self, reminder: SmartReminder, 
                           channels: List[str] = None) -> Dict[str, Any]:
        """Envia lembrete inteligente"""
        
        priority_emoji = {
            MessagePriority.LOW: "🔵",
            MessagePriority.NORMAL: "🟢",
            MessagePriority.HIGH: "🟠",
            MessagePriority.URGENT: "🔴"
        }
        
        emoji = priority_emoji.get(reminder.priority, "🔔")
        
        message = f"""🔔 *Lembrete Inteligente* {emoji}

*{reminder.title}*

📋 {reminder.description}

📧 Origem: {reminder.source_subject[:50]}...
"""
        
        if reminder.due_date:
            message += f"📅 Data: {reminder.due_date.strftime('%d/%m/%Y %H:%M')}\n"
        
        if reminder.action_required:
            message += "\n⚡ *Ação necessária!*"
        
        if reminder.keywords:
            message += f"\n🏷️ Tags: {', '.join(reminder.keywords[:5])}"
        
        return await self.notify(
            message, 
            NotificationType.REMINDER, 
            channels, 
            reminder.priority
        )


class SmartReminderExtractor:
    """Extrai lembretes inteligentes dos emails usando IA"""
    
    def __init__(self):
        self.ollama_url = OLLAMA_HOST
        
        # Palavras-chave que indicam ação necessária
        self.action_keywords = [
            'urgente', 'urgent', 'prazo', 'deadline', 'vencimento',
            'reunião', 'meeting', 'confirmar', 'confirm', 'responder',
            'pagamento', 'payment', 'fatura', 'invoice', 'boleto',
            'até', 'before', 'amanhã', 'tomorrow', 'hoje', 'today',
            'importante', 'important', 'critical', 'crítico',
            'lembrar', 'remind', 'agendar', 'schedule'
        ]
        
        # Padrões de data
        self.date_patterns = [
            r'\d{2}/\d{2}/\d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'(\d{1,2}) de (\w+)',
            r'amanhã|tomorrow|hoje|today',
            r'próxim[ao] (segunda|terça|quarta|quinta|sexta|sábado|domingo)',
            r'next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
        ]
    
    def extract_dates(self, text: str) -> List[datetime]:
        """Extrai datas do texto"""
        dates = []
        
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text.lower())
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        match = ' '.join(match)
                    
                    # Tentar parsear diferentes formatos
                    if 'amanhã' in match or 'tomorrow' in match:
                        dates.append(datetime.now() + timedelta(days=1))
                    elif 'hoje' in match or 'today' in match:
                        dates.append(datetime.now())
                    else:
                        # Tentar formato DD/MM/YYYY
                        try:
                            dates.append(datetime.strptime(match, '%d/%m/%Y'))
                        except:
                            pass
                except:
                    continue
        
        return dates
    
    def calculate_priority(self, email_data: Dict[str, Any]) -> MessagePriority:
        """Calcula prioridade baseada no conteúdo"""
        
        text = f"{email_data.get('subject', '')} {email_data.get('body', '')}".lower()
        
        # Verificar palavras-chave urgentes
        urgent_words = ['urgente', 'urgent', 'crítico', 'critical', 'imediato', 'immediate']
        if any(word in text for word in urgent_words):
            return MessagePriority.URGENT
        
        # Verificar palavras-chave de alta prioridade
        high_words = ['importante', 'important', 'prazo', 'deadline', 'vencimento']
        if any(word in text for word in high_words):
            return MessagePriority.HIGH
        
        # Verificar se é de remetente importante
        sender = email_data.get('sender_email', '').lower()
        important_senders = ['@google.com', '@microsoft.com', '@github.com', '@amazon.com']
        if any(domain in sender for domain in important_senders):
            return MessagePriority.HIGH
        
        return MessagePriority.NORMAL
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extrai palavras-chave relevantes"""
        keywords = []
        text_lower = text.lower()
        
        for keyword in self.action_keywords:
            if keyword in text_lower:
                keywords.append(keyword)
        
        return list(set(keywords))[:10]
    
    def extract_reminder(self, email_data: Dict[str, Any]) -> Optional[SmartReminder]:
        """Extrai lembrete de um email"""
        
        subject = email_data.get('subject', '')
        body = email_data.get('body', '') or email_data.get('snippet', '')
        full_text = f"{subject} {body}"
        
        # Verificar se contém palavras de ação
        keywords = self.extract_keywords(full_text)
        if not keywords:
            return None
        
        # Extrair datas
        dates = self.extract_dates(full_text)
        due_date = dates[0] if dates else None
        
        # Calcular prioridade
        priority = self.calculate_priority(email_data)
        
        # Verificar se ação é necessária
        action_required = any(
            word in full_text.lower() 
            for word in ['responder', 'confirm', 'pagar', 'agendar', 'revisar']
        )
        
        # Criar título do lembrete
        title = subject[:100] if subject else "Lembrete de Email"
        
        # Criar descrição
        description = body[:300] if body else "Verificar email original"
        
        return SmartReminder(
            title=title,
            description=description,
            due_date=due_date,
            source_email_id=email_data.get('id', ''),
            source_subject=subject,
            priority=priority,
            keywords=keywords,
            action_required=action_required
        )
    
    async def analyze_with_ai(self, email_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Usa IA para análise mais profunda do email"""
        
        try:
            subject = email_data.get('subject', '')
            body = email_data.get('body', '') or email_data.get('snippet', '')
            
            prompt = f"""Analise este email e extraia informações de lembrete:

Assunto: {subject}
Conteúdo: {body[:1000]}

Responda em JSON com:
{{
    "needs_reminder": true/false,
    "summary": "resumo curto do que precisa ser lembrado",
    "due_date": "data se houver (YYYY-MM-DD) ou null",
    "priority": "low/normal/high/urgent",
    "action_required": true/false,
    "keywords": ["lista", "de", "palavras-chave"]
}}

Apenas JSON, sem explicação."""
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "eddie-assistant",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get('response', '')
                # Tentar extrair JSON
                try:
                    # Encontrar JSON na resposta
                    json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                except:
                    pass
            
            return None
            
        except Exception as e:
            logger.warning(f"Erro na análise com IA: {e}")
            return None


class ExpurgoInteligente:
    """Agente de expurgo inteligente com treinamento e notificações"""
    
    def __init__(self):
        self.gmail_service = None
        self.trainer = get_email_trainer() if TRAINER_AVAILABLE else None
        self.notifier = NotificationService()
        self.reminder_extractor = SmartReminderExtractor()
        
        # Configuração de categorias e idade
        self.categories = [
            ('promotions', 30),   # Promoções: 30 dias
            ('social', 60),       # Social: 60 dias  
            ('updates', 90),      # Updates: 90 dias
            ('forums', 60),       # Fóruns: 60 dias
            ('spam', 7)           # Spam: 7 dias
        ]
        
        # Estatísticas
        self.stats = {
            'analyzed': 0,
            'trained': 0,
            'deleted': 0,
            'reminders_created': 0,
            'notifications_sent': 0,
            'errors': []
        }
    
    def _init_gmail(self) -> bool:
        """Inicializa cliente Gmail"""
        if not GOOGLE_AVAILABLE:
            return False
        
        try:
            token_path = f'{GMAIL_DATA_DIR}/token.json'
            
            with open(token_path, encoding='utf-8-sig') as f:
                t = json.load(f)
            
            creds = Credentials(
                token=t['token'],
                refresh_token=t['refresh_token'],
                token_uri=t['token_uri'],
                client_id=t['client_id'],
                client_secret=t['client_secret']
            )
            
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                t['token'] = creds.token
                with open(token_path, 'w') as f:
                    json.dump(t, f, indent=2)
            
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao inicializar Gmail: {e}")
            self.stats['errors'].append(f"Gmail init: {e}")
            return False
    
    def _get_email_details(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes completos de um email"""
        try:
            msg = self.gmail_service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()
            
            headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
            
            # Extrair corpo
            body = ''
            payload = msg.get('payload', {})
            
            if 'body' in payload and payload['body'].get('data'):
                import base64
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            elif 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                        import base64
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
            
            return {
                'id': msg_id,
                'subject': headers.get('subject', 'Sem assunto'),
                'sender': headers.get('from', ''),
                'sender_email': headers.get('from', ''),
                'date': headers.get('date', ''),
                'body': body,
                'snippet': msg.get('snippet', ''),
                'labels': msg.get('labelIds', [])
            }
            
        except Exception as e:
            logger.warning(f"Erro ao obter email {msg_id}: {e}")
            return None
    
    def _is_important_email(self, email_data: Dict[str, Any]) -> bool:
        """Verifica se email é importante para treinamento"""
        
        # Labels que indicam importância
        important_labels = ['IMPORTANT', 'STARRED', 'CATEGORY_PRIMARY']
        labels = email_data.get('labels', [])
        
        if any(label in labels for label in important_labels):
            return True
        
        # Palavras-chave importantes
        content = f"{email_data.get('subject', '')} {email_data.get('body', '')}".lower()
        important_keywords = [
            'projeto', 'reunião', 'meeting', 'proposta', 'contrato',
            'pagamento', 'relatório', 'código', 'deploy', 'servidor',
            'github', 'pull request', 'eddie', 'edenilson', 'importante'
        ]
        
        for kw in important_keywords:
            if kw in content:
                return True
        
        return False
    
    async def process_emails_for_training(self, emails: List[Dict], 
                                         notify_progress: bool = True) -> Dict[str, Any]:
        """Processa emails para treinamento antes de excluir"""
        
        if not self.trainer:
            return {'trained': 0, 'message': 'Trainer não disponível'}
        
        trained = 0
        reminders = []
        
        for i, email_data in enumerate(emails):
            # Verificar se vale treinar
            if self._is_important_email(email_data):
                success, msg = self.trainer.train_single_email(email_data)
                if success:
                    trained += 1
                    logger.info(f"Treinado: {email_data.get('subject', 'N/A')[:50]}")
            
            # Extrair lembrete se necessário
            reminder = self.reminder_extractor.extract_reminder(email_data)
            if reminder and reminder.priority.value >= MessagePriority.NORMAL.value:
                reminders.append(reminder)
            
            # Progresso
            if notify_progress and (i + 1) % 20 == 0:
                logger.info(f"Processados {i + 1}/{len(emails)} emails")
        
        self.stats['trained'] += trained
        
        return {
            'trained': trained,
            'reminders': reminders
        }
    
    async def send_reminders(self, reminders: List[SmartReminder], 
                            channels: List[str] = None) -> int:
        """Envia lembretes extraídos"""
        
        sent = 0
        channels = channels or ["telegram"]
        
        for reminder in reminders:
            result = await self.notifier.send_reminder(reminder, channels)
            if result.get('success'):
                sent += 1
                self.stats['reminders_created'] += 1
                
            # Pequena pausa para não sobrecarregar
            await asyncio.sleep(0.5)
        
        return sent
    
    async def run_expurgo(self, dry_run: bool = True, 
                         train_emails: bool = True,
                         send_notifications: bool = True,
                         notification_channels: List[str] = None) -> Dict[str, Any]:
        """Executa o expurgo inteligente"""
        
        notification_channels = notification_channels or ["telegram"]
        
        logger.info("=" * 50)
        logger.info("🚀 Iniciando Expurgo Inteligente")
        logger.info(f"   Modo: {'DRY RUN' if dry_run else 'EXECUÇÃO REAL'}")
        logger.info(f"   Treinamento: {'Ativo' if train_emails else 'Desativado'}")
        logger.info(f"   Notificações: {'Ativas' if send_notifications else 'Desativadas'}")
        logger.info("=" * 50)
        
        # Inicializar Gmail
        if not self._init_gmail():
            error_msg = "❌ Não foi possível conectar ao Gmail"
            if send_notifications:
                await self.notifier.notify(error_msg, NotificationType.ERROR)
            return {'error': error_msg}
        
        # Notificação inicial
        if send_notifications:
            await self.notifier.notify(
                f"🚀 *Expurgo Inteligente Iniciado*\n\nModo: {'Simulação' if dry_run else 'Execução'}\nTreinamento IA: {'Sim' if train_emails else 'Não'}",
                NotificationType.INFO,
                notification_channels
            )
        
        total_deleted = 0
        all_reminders = []
        results_by_category = {}
        
        for category, max_age_days in self.categories:
            date_limit = (datetime.now() - timedelta(days=max_age_days)).strftime('%Y/%m/%d')
            category_count = 0
            category_emails = []
            
            logger.info(f"\n📁 Processando: {category.upper()} (>{max_age_days} dias)")
            
            while True:
                try:
                    # Buscar emails da categoria
                    result = self.gmail_service.users().messages().list(
                        userId='me',
                        q=f'category:{category} before:{date_limit}',
                        maxResults=100
                    ).execute()
                    
                    messages = result.get('messages', [])
                    if not messages:
                        break
                    
                    # Obter detalhes para treinamento
                    if train_emails:
                        for msg in messages[:20]:  # Limitar para não sobrecarregar
                            email_data = self._get_email_details(msg['id'])
                            if email_data:
                                category_emails.append(email_data)
                    
                    if not dry_run:
                        # Mover para lixeira
                        ids = [m['id'] for m in messages]
                        self.gmail_service.users().messages().batchModify(
                            userId='me',
                            body={'ids': ids, 'addLabelIds': ['TRASH']}
                        ).execute()
                    
                    category_count += len(messages)
                    total_deleted += len(messages)
                    
                    logger.info(f"  {category}: +{len(messages)} (total: {category_count})")
                    
                except Exception as e:
                    logger.error(f"  Erro em {category}: {e}")
                    self.stats['errors'].append(f"{category}: {e}")
                    break
            
            # Processar emails para treinamento
            if train_emails and category_emails:
                train_result = await self.process_emails_for_training(category_emails, False)
                all_reminders.extend(train_result.get('reminders', []))
                logger.info(f"  🧠 Treinados: {train_result['trained']} emails")
            
            results_by_category[category] = {
                'deleted': category_count,
                'max_age_days': max_age_days
            }
            
            if category_count > 0:
                logger.info(f"  >>> {category.upper()}: {category_count} emails processados")
            else:
                logger.info(f"  >>> {category.upper()}: Já estava limpo")
        
        self.stats['deleted'] = total_deleted
        self.stats['analyzed'] = sum(r['deleted'] for r in results_by_category.values())
        
        # Enviar lembretes importantes
        if all_reminders and send_notifications:
            high_priority_reminders = [
                r for r in all_reminders 
                if r.priority.value >= MessagePriority.HIGH.value
            ]
            if high_priority_reminders:
                sent = await self.send_reminders(high_priority_reminders, notification_channels)
                logger.info(f"🔔 Enviados {sent} lembretes de alta prioridade")
        
        # Relatório final
        report = self._generate_report(results_by_category, all_reminders, dry_run)
        logger.info("\n" + report)
        
        # Notificação final
        if send_notifications:
            await self.notifier.notify(
                report,
                NotificationType.SUCCESS if not self.stats['errors'] else NotificationType.WARNING,
                notification_channels
            )
        
        return {
            'success': True,
            'dry_run': dry_run,
            'stats': self.stats,
            'by_category': results_by_category,
            'reminders_sent': len(all_reminders),
            'report': report
        }
    
    def _generate_report(self, results: Dict, reminders: List, dry_run: bool) -> str:
        """Gera relatório do expurgo"""
        
        mode = "SIMULAÇÃO" if dry_run else "EXECUÇÃO"
        
        report = f"""📊 *Relatório Expurgo Inteligente*
_{datetime.now().strftime('%d/%m/%Y %H:%M')}_

*Modo:* {mode}

📁 *Por Categoria:*
"""
        
        for cat, data in results.items():
            emoji = "✅" if data['deleted'] > 0 else "⚪"
            report += f"{emoji} {cat.upper()}: {data['deleted']} (>{data['max_age_days']}d)\n"
        
        report += f"""
📈 *Totais:*
• Analisados: {self.stats['analyzed']}
• Movidos p/ lixeira: {self.stats['deleted']}
• Treinados na IA: {self.stats['trained']}
• Lembretes criados: {len(reminders)}
"""
        
        if self.stats['errors']:
            report += f"\n⚠️ *Erros:* {len(self.stats['errors'])}"
        
        if self.trainer:
            trainer_stats = self.trainer.get_stats()
            report += f"""
🧠 *Base de Conhecimento:*
• Emails indexados: {trainer_stats.get('emails_indexed', 0)}
• ChromaDB: {'✅' if trainer_stats.get('chromadb_available') else '❌'}
"""
        
        return report
    
    async def schedule_smart_cleanup(self, interval_hours: int = 24) -> None:
        """Agenda limpeza automática"""
        
        logger.info(f"📅 Agendando limpeza a cada {interval_hours} horas")
        
        while True:
            try:
                await self.run_expurgo(
                    dry_run=False,
                    train_emails=True,
                    send_notifications=True
                )
            except Exception as e:
                logger.error(f"Erro no expurgo agendado: {e}")
                await self.notifier.notify(
                    f"❌ Erro no expurgo agendado: {e}",
                    NotificationType.ERROR
                )
            
            # Aguardar próxima execução
            await asyncio.sleep(interval_hours * 3600)


# ============ Funções de Interface ============

async def run_once(dry_run: bool = True, channels: List[str] = None):
    """Executa expurgo uma vez"""
    expurgo = ExpurgoInteligente()
    result = await expurgo.run_expurgo(
        dry_run=dry_run,
        train_emails=True,
        send_notifications=True,
        notification_channels=channels or ["telegram"]
    )
    return result


async def run_daemon(interval_hours: int = 24):
    """Executa como daemon"""
    expurgo = ExpurgoInteligente()
    await expurgo.schedule_smart_cleanup(interval_hours)


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gmail Expurgo Inteligente')
    parser.add_argument('--execute', action='store_true', help='Executar de verdade (não dry run)')
    parser.add_argument('--daemon', action='store_true', help='Executar como daemon')
    parser.add_argument('--interval', type=int, default=24, help='Intervalo em horas (daemon)')
    parser.add_argument('--channels', nargs='+', default=['telegram'], 
                       help='Canais de notificação: telegram, whatsapp')
    parser.add_argument('--no-notifications', action='store_true', help='Desabilitar notificações')
    parser.add_argument('--no-training', action='store_true', help='Desabilitar treinamento')
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           📧 Gmail Expurgo Inteligente v2.0 📧                ║
║                                                              ║
║  Funcionalidades:                                            ║
║  • Limpeza inteligente por categoria                        ║
║  • Treinamento da IA Eddie com emails importantes           ║
║  • Lembretes inteligentes via WhatsApp/Telegram            ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    if args.daemon:
        print(f"🔄 Iniciando modo daemon (intervalo: {args.interval}h)")
        asyncio.run(run_daemon(args.interval))
    else:
        dry_run = not args.execute
        print(f"📋 Modo: {'EXECUÇÃO' if args.execute else 'SIMULAÇÃO (dry run)'}")
        
        expurgo = ExpurgoInteligente()
        result = asyncio.run(expurgo.run_expurgo(
            dry_run=dry_run,
            train_emails=not args.no_training,
            send_notifications=not args.no_notifications,
            notification_channels=args.channels
        ))
        
        if result.get('error'):
            print(f"\n❌ Erro: {result['error']}")
            sys.exit(1)
        
        print("\n✅ Expurgo concluído!")
        
        if dry_run:
            print("\n💡 Para executar de verdade, use: --execute")


if __name__ == '__main__':
    main()
