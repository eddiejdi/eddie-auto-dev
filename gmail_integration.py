#!/usr/bin/env python3
"""
Integração Gmail para Eddie Assistant
Permite ler, classificar, organizar e limpar emails

Autor: Eddie Assistant
Data: 2026
"""

import os
import json
import pickle
import base64
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('GmailIntegration')

# Diretório de dados
DATA_DIR = Path(__file__).parent / "gmail_data"
DATA_DIR.mkdir(exist_ok=True)

# Arquivos de credenciais
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.pickle"

# Escopos necessários
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

# Palavras-chave para classificação de emails
SPAM_KEYWORDS = [
    'unsubscribe', 'descadastrar', 'cancelar inscrição',
    'você ganhou', 'you won', 'winner', 'ganhador',
    'oferta imperdível', 'promoção exclusiva', 'desconto',
    'últimas horas', 'não perca', 'grátis', 'free',
    'clique aqui', 'click here', 'compre agora', 'buy now',
    'lottery', 'loteria', 'prêmio', 'prize',
    'bitcoin investment', 'crypto opportunity',
    'urgent response', 'resposta urgente',
    'senha expirada', 'password expired',
    'verify your account', 'verifique sua conta',
    'confirme seus dados', 'confirm your data',
    'suspensão de conta', 'account suspension',
    'fatura disponível', 'invoice available',
    'newsletter', 'boletim informativo',
    'marketing', 'publicidade', 'advertising',
    'limited time', 'tempo limitado',
    'act now', 'aja agora',
    'special offer', 'oferta especial',
    'exclusive deal', 'negócio exclusivo',
    'black friday', 'cyber monday',
    'flash sale', 'liquidação',
]

# Domínios conhecidos de spam/marketing
SPAM_DOMAINS = [
    'mailchimp.com', 'sendgrid.net', 'mailgun.org',
    'constantcontact.com', 'hubspot.com', 'marketing',
    'newsletter', 'promo', 'noreply', 'no-reply',
    'donotreply', 'notifications', 'alert',
    'mailer-daemon', 'postmaster',
]

# Domínios relevantes para Edenilson (não spam)
WHITELIST_DOMAINS = [
    'gmail.com', 'hotmail.com', 'outlook.com',
    'github.com', 'google.com', 'microsoft.com',
    'amazon.com', 'aws.amazon.com',
    'digitalocean.com', 'linode.com',
    'cloudflare.com', 'namecheap.com',
    'paypal.com', 'mercadopago.com',
    'nubank.com.br', 'itau.com.br', 'bradesco.com.br',
    'gov.br', 'receita.fazenda.gov.br',
]

# Palavras que indicam email pessoal/importante
IMPORTANT_KEYWORDS = [
    'edenilson', 'eddie', 'edi',
    'urgente', 'importante', 'critical',
    'pagamento', 'payment', 'fatura', 'invoice',
    'contrato', 'contract', 'proposta', 'proposal',
    'reunião', 'meeting', 'entrevista', 'interview',
    'github', 'pull request', 'merge', 'commit',
    'servidor', 'server', 'deploy', 'production',
    'erro crítico', 'critical error', 'down', 'offline',
]


@dataclass
class Email:
    """Representa um email"""
    id: str
    thread_id: str
    subject: str
    sender: str
    sender_email: str
    recipient: str
    date: datetime
    snippet: str
    body: str = ""
    labels: List[str] = field(default_factory=list)
    is_read: bool = True
    is_important: bool = False
    has_attachments: bool = False
    
    # Classificação
    spam_score: float = 0.0
    is_spam: bool = False
    is_promotional: bool = False
    is_social: bool = False
    is_personal: bool = False
    classification_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'thread_id': self.thread_id,
            'subject': self.subject,
            'sender': self.sender,
            'sender_email': self.sender_email,
            'date': self.date.isoformat() if self.date else None,
            'snippet': self.snippet,
            'labels': self.labels,
            'is_read': self.is_read,
            'is_important': self.is_important,
            'spam_score': self.spam_score,
            'is_spam': self.is_spam,
            'is_promotional': self.is_promotional,
            'classification_reason': self.classification_reason
        }
    
    def format_display(self, include_body: bool = False) -> str:
        """Formata email para exibição"""
        status_icons = []
        if not self.is_read:
            status_icons.append("📬")
        if self.is_important:
            status_icons.append("⭐")
        if self.has_attachments:
            status_icons.append("📎")
        if self.is_spam:
            status_icons.append("🚫")
        if self.is_promotional:
            status_icons.append("📢")
        
        status = " ".join(status_icons) if status_icons else "📧"
        date_str = self.date.strftime('%d/%m/%Y %H:%M') if self.date else "N/A"
        
        lines = [
            f"{status} **{self.subject[:60]}{'...' if len(self.subject) > 60 else ''}**",
            f"👤 De: {self.sender} <{self.sender_email}>",
            f"📅 Data: {date_str}",
        ]
        
        if self.classification_reason:
            lines.append(f"🏷️ {self.classification_reason}")
        
        if include_body and self.body:
            body_preview = self.body[:300].replace('\n', ' ')
            lines.append(f"📝 {body_preview}...")
        elif self.snippet:
            lines.append(f"📝 {self.snippet[:150]}...")
        
        return '\n'.join(lines)


class EmailClassifier:
    """Classificador de emails"""
    
    def __init__(self):
        self.spam_keywords = [kw.lower() for kw in SPAM_KEYWORDS]
        self.spam_domains = [d.lower() for d in SPAM_DOMAINS]
        self.whitelist_domains = [d.lower() for d in WHITELIST_DOMAINS]
        self.important_keywords = [kw.lower() for kw in IMPORTANT_KEYWORDS]
    
    def classify(self, email: Email) -> Email:
        """Classifica um email"""
        score = 0.0
        reasons = []
        
        subject_lower = email.subject.lower()
        sender_lower = email.sender_email.lower()
        body_lower = (email.body or email.snippet).lower()
        content = f"{subject_lower} {body_lower}"
        
        # 1. Verificar domínio do remetente
        sender_domain = sender_lower.split('@')[-1] if '@' in sender_lower else ''
        
        # Whitelist - emails pessoais/importantes
        if any(wd in sender_domain for wd in self.whitelist_domains):
            score -= 30
            reasons.append("Domínio confiável")
        
        # Domínios de spam/marketing
        if any(sd in sender_domain or sd in sender_lower for sd in self.spam_domains):
            score += 40
            reasons.append("Domínio de marketing")
        
        # 2. Verificar palavras-chave de spam
        spam_matches = sum(1 for kw in self.spam_keywords if kw in content)
        if spam_matches > 0:
            score += min(spam_matches * 10, 50)
            reasons.append(f"{spam_matches} palavras de spam")
        
        # 3. Verificar palavras importantes
        important_matches = sum(1 for kw in self.important_keywords if kw in content)
        if important_matches > 0:
            score -= min(important_matches * 15, 45)
            reasons.append(f"{important_matches} palavras importantes")
        
        # 4. Labels do Gmail
        if 'SPAM' in email.labels:
            score += 50
            reasons.append("Marcado como SPAM")
        
        if 'CATEGORY_PROMOTIONS' in email.labels:
            score += 30
            email.is_promotional = True
            reasons.append("Categoria: Promoções")
        
        if 'CATEGORY_SOCIAL' in email.labels:
            score += 20
            email.is_social = True
            reasons.append("Categoria: Social")
        
        if 'IMPORTANT' in email.labels or 'STARRED' in email.labels:
            score -= 40
            reasons.append("Marcado como importante")
        
        if 'CATEGORY_PERSONAL' in email.labels:
            score -= 30
            email.is_personal = True
            reasons.append("Categoria: Pessoal")
        
        # 5. Verificar se email é para Edenilson diretamente
        if 'edenilson' in content or 'eddie' in sender_lower:
            score -= 25
            reasons.append("Menção direta a Edenilson")
        
        # 6. Emails de noreply/marketing
        if 'noreply' in sender_lower or 'no-reply' in sender_lower:
            score += 25
            reasons.append("Remetente noreply")
        
        # 7. Emails com muitos destinatários (possível newsletter)
        # (Isso seria detectado pelo header, simplificando aqui)
        
        # 8. Emails antigos não lidos podem ser irrelevantes
        if email.date:
            age_days = (datetime.now() - email.date).days
            if age_days > 30 and not email.is_read:
                score += 15
                reasons.append(f"Email antigo ({age_days} dias)")
        
        # Determinar classificação final
        email.spam_score = score
        
        if score >= 40:
            email.is_spam = True
            email.classification_reason = "🚫 SPAM/Irrelevante: " + ", ".join(reasons)
        elif score >= 20:
            email.is_promotional = True
            email.classification_reason = "📢 Promocional: " + ", ".join(reasons)
        elif score <= -20:
            email.is_important = True
            email.is_personal = True
            email.classification_reason = "⭐ Importante: " + ", ".join(reasons)
        else:
            email.classification_reason = "📧 Normal: " + ", ".join(reasons) if reasons else "📧 Sem classificação especial"
        
        return email


class GmailClient:
    """Cliente para API do Gmail"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self.classifier = EmailClassifier()
        self.user_email = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Carrega credenciais do arquivo"""
        try:
            if TOKEN_FILE.exists():
                with open(TOKEN_FILE, 'rb') as f:
                    self.credentials = pickle.load(f)
                logger.info("Credenciais Gmail carregadas do cache")
        except Exception as e:
            logger.warning(f"Erro ao carregar credenciais: {e}")
            self.credentials = None
    
    def _save_credentials(self):
        """Salva credenciais no arquivo"""
        try:
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(self.credentials, f)
            logger.info("Credenciais Gmail salvas")
        except Exception as e:
            logger.error(f"Erro ao salvar credenciais: {e}")
    
    def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        if not self.credentials:
            return False
        if hasattr(self.credentials, 'expired'):
            return not self.credentials.expired
        return True
    
    async def authenticate(self, auth_code: str = None) -> Tuple[bool, str]:
        """Autentica com Gmail"""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            
            # Verificar credenciais existentes
            if self.credentials and not self.credentials.expired:
                self.service = build('gmail', 'v1', credentials=self.credentials)
                profile = self.service.users().getProfile(userId='me').execute()
                self.user_email = profile.get('emailAddress')
                return True, f"Já autenticado como {self.user_email}!"
            
            # Tentar refresh
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self._save_credentials()
                    self.service = build('gmail', 'v1', credentials=self.credentials)
                    profile = self.service.users().getProfile(userId='me').execute()
                    self.user_email = profile.get('emailAddress')
                    return True, f"Token renovado! Autenticado como {self.user_email}"
                except Exception as e:
                    logger.warning(f"Falha ao renovar token: {e}")
            
            # Novo fluxo de autenticação
            if not CREDENTIALS_FILE.exists():
                # Usar credenciais do Calendar se existirem
                calendar_creds = Path(__file__).parent / "calendar_data" / "credentials.json"
                if calendar_creds.exists():
                    import shutil
                    shutil.copy(calendar_creds, CREDENTIALS_FILE)
                    logger.info("Usando credenciais do Google Calendar")
                else:
                    return False, ("Arquivo credentials.json não encontrado.\n"
                                   "Configure as credenciais Google primeiro.\n"
                                   "Execute: python setup_google_calendar.py")
            
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            
            if auth_code:
                flow.fetch_token(code=auth_code)
                self.credentials = flow.credentials
                self._save_credentials()
                self.service = build('gmail', 'v1', credentials=self.credentials)
                profile = self.service.users().getProfile(userId='me').execute()
                self.user_email = profile.get('emailAddress')
                return True, f"✅ Autenticado como {self.user_email}!"
            else:
                auth_url, _ = flow.authorization_url(prompt='consent')
                return False, f"🔐 Acesse esta URL para autorizar:\n{auth_url}\n\nDepois use: /gmail auth <código>"
        
        except ImportError:
            return False, "Bibliotecas Google não instaladas. Execute: pip install google-auth-oauthlib google-api-python-client"
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            return False, f"Erro: {str(e)}"
    
    async def ensure_service(self) -> bool:
        """Garante que o serviço está inicializado"""
        if self.service:
            return True
        if not self.credentials:
            return False
        try:
            from googleapiclient.discovery import build
            self.service = build('gmail', 'v1', credentials=self.credentials)
            return True
        except Exception as e:
            logger.error(f"Erro ao inicializar serviço: {e}")
            return False
    
    def _parse_email(self, msg_data: Dict) -> Email:
        """Parse dados da API para objeto Email"""
        headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
        
        # Extrair remetente
        from_header = headers.get('From', '')
        sender_match = re.match(r'(.+?)\s*<(.+?)>', from_header)
        if sender_match:
            sender = sender_match.group(1).strip().strip('"')
            sender_email = sender_match.group(2).strip()
        else:
            sender = from_header
            sender_email = from_header
        
        # Extrair data
        date_str = headers.get('Date', '')
        try:
            # Tentar vários formatos de data
            for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%d %b %Y %H:%M:%S %z']:
                try:
                    date = datetime.strptime(date_str[:31], fmt)
                    break
                except:
                    continue
            else:
                date = datetime.now()
        except:
            date = datetime.now()
        
        # Extrair corpo
        body = ""
        payload = msg_data.get('payload', {})
        
        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        elif 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        
        # Verificar anexos
        has_attachments = False
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    has_attachments = True
                    break
        
        labels = msg_data.get('labelIds', [])
        
        return Email(
            id=msg_data['id'],
            thread_id=msg_data.get('threadId', ''),
            subject=headers.get('Subject', '(Sem assunto)'),
            sender=sender,
            sender_email=sender_email,
            recipient=headers.get('To', ''),
            date=date,
            snippet=msg_data.get('snippet', ''),
            body=body,
            labels=labels,
            is_read='UNREAD' not in labels,
            is_important='IMPORTANT' in labels,
            has_attachments=has_attachments
        )
    
    async def list_emails(self, 
                          max_results: int = 50,
                          query: str = None,
                          label_ids: List[str] = None,
                          include_spam: bool = False) -> Tuple[bool, str, List[Email]]:
        """Lista emails"""
        if not await self.ensure_service():
            return False, "Não autenticado. Use /gmail auth", []
        
        try:
            # Construir query
            q_parts = []
            if query:
                q_parts.append(query)
            if not include_spam:
                q_parts.append("-in:spam -in:trash")
            
            params = {
                'userId': 'me',
                'maxResults': max_results,
            }
            
            if q_parts:
                params['q'] = ' '.join(q_parts)
            if label_ids:
                params['labelIds'] = label_ids
            
            # Listar mensagens
            result = self.service.users().messages().list(**params).execute()
            messages = result.get('messages', [])
            
            emails = []
            for msg in messages:
                # Obter detalhes completos
                msg_data = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                email = self._parse_email(msg_data)
                email = self.classifier.classify(email)
                emails.append(email)
            
            if emails:
                msg = f"📬 **{len(emails)} email(s) encontrado(s)**\n\n"
            else:
                msg = "📭 Nenhum email encontrado."
            
            return True, msg, emails
        
        except Exception as e:
            logger.error(f"Erro ao listar emails: {e}")
            return False, f"Erro: {str(e)}", []
    
    async def get_email(self, email_id: str) -> Tuple[bool, str, Optional[Email]]:
        """Obtém um email específico"""
        if not await self.ensure_service():
            return False, "Não autenticado", None
        
        try:
            msg_data = self.service.users().messages().get(
                userId='me',
                id=email_id,
                format='full'
            ).execute()
            
            email = self._parse_email(msg_data)
            email = self.classifier.classify(email)
            
            return True, "Email encontrado", email
        
        except Exception as e:
            logger.error(f"Erro ao obter email: {e}")
            return False, f"Erro: {str(e)}", None
    
    async def move_to_trash(self, email_ids: List[str]) -> Tuple[bool, str]:
        """Move emails para a lixeira"""
        if not await self.ensure_service():
            return False, "Não autenticado"
        
        try:
            success_count = 0
            for email_id in email_ids:
                try:
                    self.service.users().messages().trash(
                        userId='me',
                        id=email_id
                    ).execute()
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Erro ao mover {email_id}: {e}")
            
            return True, f"🗑️ {success_count}/{len(email_ids)} email(s) movido(s) para lixeira"
        
        except Exception as e:
            logger.error(f"Erro ao mover para lixeira: {e}")
            return False, f"Erro: {str(e)}"
    
    async def delete_permanently(self, email_ids: List[str]) -> Tuple[bool, str]:
        """Deleta emails permanentemente (CUIDADO!)"""
        if not await self.ensure_service():
            return False, "Não autenticado"
        
        try:
            success_count = 0
            for email_id in email_ids:
                try:
                    self.service.users().messages().delete(
                        userId='me',
                        id=email_id
                    ).execute()
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Erro ao deletar {email_id}: {e}")
            
            return True, f"⚠️ {success_count}/{len(email_ids)} email(s) deletado(s) PERMANENTEMENTE"
        
        except Exception as e:
            logger.error(f"Erro ao deletar: {e}")
            return False, f"Erro: {str(e)}"
    
    async def mark_as_spam(self, email_ids: List[str]) -> Tuple[bool, str]:
        """Marca emails como spam"""
        if not await self.ensure_service():
            return False, "Não autenticado"
        
        try:
            success_count = 0
            for email_id in email_ids:
                try:
                    self.service.users().messages().modify(
                        userId='me',
                        id=email_id,
                        body={'addLabelIds': ['SPAM'], 'removeLabelIds': ['INBOX']}
                    ).execute()
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Erro ao marcar {email_id}: {e}")
            
            return True, f"🚫 {success_count}/{len(email_ids)} email(s) marcado(s) como spam"
        
        except Exception as e:
            logger.error(f"Erro ao marcar como spam: {e}")
            return False, f"Erro: {str(e)}"
    
    async def mark_as_read(self, email_ids: List[str]) -> Tuple[bool, str]:
        """Marca emails como lidos"""
        if not await self.ensure_service():
            return False, "Não autenticado"
        
        try:
            success_count = 0
            for email_id in email_ids:
                try:
                    self.service.users().messages().modify(
                        userId='me',
                        id=email_id,
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Erro ao marcar {email_id}: {e}")
            
            return True, f"✅ {success_count}/{len(email_ids)} email(s) marcado(s) como lido(s)"
        
        except Exception as e:
            logger.error(f"Erro ao marcar como lido: {e}")
            return False, f"Erro: {str(e)}"
    
    async def get_labels(self) -> Tuple[bool, str, List[Dict]]:
        """Lista labels/pastas"""
        if not await self.ensure_service():
            return False, "Não autenticado", []
        
        try:
            result = self.service.users().labels().list(userId='me').execute()
            labels = result.get('labels', [])
            
            msg = "🏷️ **Labels disponíveis:**\n\n"
            for label in labels:
                msg += f"• {label.get('name')} (`{label.get('id')}`)\n"
            
            return True, msg, labels
        
        except Exception as e:
            logger.error(f"Erro ao listar labels: {e}")
            return False, f"Erro: {str(e)}", []
    
    async def get_unread_count(self) -> Tuple[bool, int]:
        """Conta emails não lidos"""
        if not await self.ensure_service():
            return False, 0
        
        try:
            result = self.service.users().messages().list(
                userId='me',
                q='is:unread -in:spam -in:trash',
                maxResults=1
            ).execute()
            
            return True, result.get('resultSizeEstimate', 0)
        
        except Exception as e:
            logger.error(f"Erro ao contar não lidos: {e}")
            return False, 0


class EmailCleaner:
    """Limpa e organiza emails automaticamente"""
    
    def __init__(self, gmail_client: GmailClient):
        self.gmail = gmail_client
        self.classifier = EmailClassifier()
    
    async def analyze_inbox(self, max_emails: int = 100) -> Dict[str, Any]:
        """Analisa a caixa de entrada"""
        success, _, emails = await self.gmail.list_emails(max_results=max_emails)
        
        if not success:
            return {"error": "Não foi possível acessar emails"}
        
        stats = {
            'total': len(emails),
            'spam': [],
            'promotional': [],
            'social': [],
            'important': [],
            'normal': [],
            'unread': 0,
            'old_unread': []
        }
        
        for email in emails:
            if not email.is_read:
                stats['unread'] += 1
                if email.date and (datetime.now() - email.date).days > 7:
                    stats['old_unread'].append(email)
            
            if email.is_spam:
                stats['spam'].append(email)
            elif email.is_promotional:
                stats['promotional'].append(email)
            elif email.is_social:
                stats['social'].append(email)
            elif email.is_important:
                stats['important'].append(email)
            else:
                stats['normal'].append(email)
        
        return stats
    
    async def clean_spam_and_promotions(self, 
                                        dry_run: bool = True,
                                        max_emails: int = 100) -> Dict[str, Any]:
        """Limpa emails de spam e promoções"""
        stats = await self.analyze_inbox(max_emails)
        
        if 'error' in stats:
            return stats
        
        to_delete = stats['spam'] + stats['promotional']
        
        result = {
            'analyzed': stats['total'],
            'spam_found': len(stats['spam']),
            'promotional_found': len(stats['promotional']),
            'to_delete': len(to_delete),
            'deleted': 0,
            'dry_run': dry_run,
            'emails_to_delete': [e.to_dict() for e in to_delete[:20]]  # Prévia
        }
        
        if not dry_run and to_delete:
            ids_to_delete = [e.id for e in to_delete]
            success, msg = await self.gmail.move_to_trash(ids_to_delete)
            result['deleted'] = len(ids_to_delete) if success else 0
            result['delete_message'] = msg
        
        return result
    
    async def generate_report(self, max_emails: int = 100) -> str:
        """Gera relatório de análise"""
        stats = await self.analyze_inbox(max_emails)
        
        if 'error' in stats:
            return f"❌ {stats['error']}"
        
        report = f"""📊 **Análise da Caixa de Entrada**

📬 **Total analisado:** {stats['total']} emails
📭 **Não lidos:** {stats['unread']}

📈 **Classificação:**
• 🚫 Spam/Irrelevante: {len(stats['spam'])}
• 📢 Promoções: {len(stats['promotional'])}
• 👥 Social: {len(stats['social'])}
• ⭐ Importantes: {len(stats['important'])}
• 📧 Normais: {len(stats['normal'])}

"""
        
        # Top spam
        if stats['spam']:
            report += "🚫 **Emails identificados como SPAM:**\n"
            for i, email in enumerate(stats['spam'][:10], 1):
                report += f"{i}. {email.subject[:40]}... ({email.sender_email})\n"
            if len(stats['spam']) > 10:
                report += f"   ... e mais {len(stats['spam']) - 10}\n"
            report += "\n"
        
        # Top promoções
        if stats['promotional']:
            report += "📢 **Emails promocionais:**\n"
            for i, email in enumerate(stats['promotional'][:10], 1):
                report += f"{i}. {email.subject[:40]}... ({email.sender_email})\n"
            if len(stats['promotional']) > 10:
                report += f"   ... e mais {len(stats['promotional']) - 10}\n"
            report += "\n"
        
        # Emails antigos não lidos
        if stats['old_unread']:
            report += f"⏰ **Emails antigos não lidos ({len(stats['old_unread'])}):**\n"
            for email in stats['old_unread'][:5]:
                age = (datetime.now() - email.date).days
                report += f"• {email.subject[:30]}... ({age} dias)\n"
            report += "\n"
        
        # Recomendação
        to_clean = len(stats['spam']) + len(stats['promotional'])
        if to_clean > 0:
            report += f"""
💡 **Recomendação:**
Encontrei **{to_clean}** emails que podem ser movidos para lixeira.
Use `/gmail limpar` para executar a limpeza.
Use `/gmail limpar confirmar` para confirmar a exclusão."""
        else:
            report += "\n✨ Sua caixa de entrada está limpa!"
        
        return report


# Instância global
_gmail_client: Optional[GmailClient] = None
_email_cleaner: Optional[EmailCleaner] = None


def get_gmail_client() -> GmailClient:
    """Obtém instância do cliente Gmail"""
    global _gmail_client
    if _gmail_client is None:
        _gmail_client = GmailClient()
    return _gmail_client


def get_email_cleaner() -> EmailCleaner:
    """Obtém instância do limpador de emails"""
    global _email_cleaner
    if _email_cleaner is None:
        _email_cleaner = EmailCleaner(get_gmail_client())
    return _email_cleaner


async def process_gmail_command(command: str, args: str = "") -> str:
    """Processa comandos do Gmail"""
    gmail = get_gmail_client()
    cleaner = get_email_cleaner()
    
    command = command.lower().strip()
    
    if command in ['auth', 'login', 'autenticar']:
        success, msg = await gmail.authenticate(args if args else None)
        return msg
    
    if command in ['listar', 'list', 'inbox', 'caixa']:
        max_results = 20
        if args:
            try:
                max_results = int(args)
            except:
                pass
        
        success, _, emails = await gmail.list_emails(max_results=max_results)
        if not success:
            return "❌ Erro ao acessar emails. Use /gmail auth primeiro."
        
        if not emails:
            return "📭 Nenhum email encontrado."
        
        msg = f"📬 **{len(emails)} emails:**\n\n"
        for i, email in enumerate(emails[:15], 1):
            status = "🚫" if email.is_spam else "📢" if email.is_promotional else "⭐" if email.is_important else "📧"
            read_status = "" if email.is_read else "📬"
            msg += f"{i}. {status}{read_status} **{email.subject[:35]}**\n"
            msg += f"   {email.sender_email[:30]} • {email.date.strftime('%d/%m')}\n\n"
        
        if len(emails) > 15:
            msg += f"... e mais {len(emails) - 15} emails"
        
        return msg
    
    if command in ['analisar', 'analyze', 'relatorio', 'report']:
        return await cleaner.generate_report(max_emails=100)
    
    if command in ['limpar', 'clean', 'cleanup']:
        if 'confirmar' in args.lower() or 'confirm' in args.lower():
            # Executar limpeza
            result = await cleaner.clean_spam_and_promotions(dry_run=False, max_emails=100)
            
            if 'error' in result:
                return f"❌ {result['error']}"
            
            return f"""🧹 **Limpeza Executada!**

📊 Analisados: {result['analyzed']} emails
🚫 Spam: {result['spam_found']}
📢 Promoções: {result['promotional_found']}
🗑️ Movidos para lixeira: {result['deleted']}

{result.get('delete_message', '')}
"""
        else:
            # Prévia (dry run)
            result = await cleaner.clean_spam_and_promotions(dry_run=True, max_emails=100)
            
            if 'error' in result:
                return f"❌ {result['error']}"
            
            msg = f"""🔍 **Prévia da Limpeza** (nenhuma ação executada)

📊 Analisados: {result['analyzed']} emails
🚫 Spam encontrado: {result['spam_found']}
📢 Promoções encontradas: {result['promotional_found']}
🗑️ Total a ser movido: {result['to_delete']}

"""
            
            if result['emails_to_delete']:
                msg += "📋 **Serão movidos para lixeira:**\n"
                for email_data in result['emails_to_delete'][:10]:
                    msg += f"• {email_data['subject'][:40]}...\n  ({email_data['sender_email']})\n"
                
                if result['to_delete'] > 10:
                    msg += f"\n... e mais {result['to_delete'] - 10} emails\n"
            
            msg += "\n⚠️ **Para confirmar a limpeza:**\n`/gmail limpar confirmar`"
            
            return msg
    
    if command in ['spam', 'marcar_spam']:
        if not args:
            return "❌ Especifique os IDs dos emails ou use `/gmail limpar` para limpeza automática"
        
        ids = args.split()
        success, msg = await gmail.mark_as_spam(ids)
        return msg
    
    if command in ['lixeira', 'trash', 'deletar']:
        if not args:
            return "❌ Especifique os IDs dos emails ou use `/gmail limpar` para limpeza automática"
        
        ids = args.split()
        success, msg = await gmail.move_to_trash(ids)
        return msg
    
    if command in ['labels', 'pastas', 'categorias']:
        success, msg, _ = await gmail.get_labels()
        return msg
    
    if command in ['nao_lidos', 'unread', 'naolidos']:
        success, count = await gmail.get_unread_count()
        return f"📬 Você tem **{count}** email(s) não lido(s)"
    
    if command in ['ajuda', 'help', 'comandos']:
        return """📧 **Comandos do Gmail:**

🔐 **Autenticação:**
• `/gmail auth` - Autenticar com Google

📬 **Listar emails:**
• `/gmail listar` - Ver últimos 20 emails
• `/gmail listar 50` - Ver últimos 50 emails
• `/gmail nao_lidos` - Contar não lidos

📊 **Análise:**
• `/gmail analisar` - Relatório completo
• `/gmail labels` - Ver pastas/labels

�🧹 **Treinar e Limpar (RECOMENDADO):**
• `/gmail treinar` - Prévia do treinamento + limpeza
• `/gmail treinar confirmar` - Treina IA e limpa spam

🧹 **Limpeza simples:**
• `/gmail limpar` - Prévia da limpeza
• `/gmail limpar confirmar` - Executar limpeza

🔍 **Buscar:**
• `/gmail buscar <termo>` - Buscar nos emails indexados

📈 **Estatísticas:**
• `/gmail stats` - Ver estatísticas de treinamento

🗑️ **Ações manuais:**
• `/gmail spam <ids>` - Marcar como spam
• `/gmail lixeira <ids>` - Mover para lixeira

💡 **Dica:** Use `/gmail treinar confirmar` para preservar conhecimento dos emails importantes antes de limpar spam!"""
    
    # === COMANDOS DE TREINAMENTO ===
    if command in ['treinar', 'train', 'treinar_limpar', 'train_clean']:
        try:
            from email_trainer import process_email_training_command
            return await process_email_training_command('treinar_limpar', args)
        except ImportError:
            return "❌ Módulo de treinamento não disponível"
    
    if command in ['stats', 'estatisticas']:
        try:
            from email_trainer import process_email_training_command
            return await process_email_training_command('stats', '')
        except ImportError:
            return "❌ Módulo de treinamento não disponível"
    
    if command in ['buscar', 'search', 'pesquisar']:
        try:
            from email_trainer import process_email_training_command
            return await process_email_training_command('buscar', args)
        except ImportError:
            return "❌ Módulo de treinamento não disponível"
    
    return f"""❓ Comando '{command}' não reconhecido.
Use `/gmail ajuda` para ver comandos disponíveis."""


# Teste
if __name__ == "__main__":
    import asyncio
    
    async def test():
        gmail = get_gmail_client()
        
        # Testar autenticação
        print("Testando autenticação...")
        success, msg = await gmail.authenticate()
        print(msg)
        
        if success:
            # Testar análise
            cleaner = get_email_cleaner()
            report = await cleaner.generate_report(max_emails=50)
            print("\n" + report)
    
    asyncio.run(test())
