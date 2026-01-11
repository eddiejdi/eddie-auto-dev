#!/usr/bin/env python3
"""
Gmail Email Cleaner (Versão Simplificada)
Limpa spam/promoções e salva emails importantes em arquivo JSON para treinamento
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64

# Configuração
TOKEN_FILE = "/home/eddie/myClaude/gmail_data/token.json"
EMAILS_DB = "/home/eddie/myClaude/gmail_data/emails_knowledge.json"
LOG_FILE = "/home/eddie/myClaude/gmail_data/email_cleaner.log"
OWNER_NAME = "Edenilson"

# Criar diretório
os.makedirs("/home/eddie/myClaude/gmail_data", exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Email:
    id: str
    subject: str
    sender: str
    snippet: str
    body: str = ""
    date: str = ""

class EmailClassifier:
    PROMO_KEYWORDS = [
        'cupom', 'desconto', 'oferta', 'promoção', 'sale', 'off', 'compre',
        'black friday', 'liquidação', 'frete grátis', 'aproveite', 'não perca',
        'últimas unidades', 'exclusivo', 'newsletter', 'marketing', 'unsubscribe',
        'vip exclusive', 'win for rewards', 'giveaway', 'prize', 'winner'
    ]
    
    PROMO_SENDERS = [
        'marketing', 'promo', 'newsletter', 'noreply', 'no-reply', 'mkt@',
        'news@', 'kucoin', 'shopee', 'aliexpress', 'insider', 'loja', 
        'store', 'mercadolivre', 'amazon.com.br', '@email.', 'contato@email'
    ]
    
    IMPORTANT_SENDERS = [
        'google.com', 'linkedin.com', 'github.com', 'banco', 'bank',
        'gov.br', 'receita', 'nubank', 'mercadopago', 'inter.co'
    ]
    
    @classmethod
    def classify(cls, email: Email) -> str:
        subject_lower = email.subject.lower()
        sender_lower = email.sender.lower()
        body_lower = (email.body or email.snippet).lower()
        
        # Importante se menciona o dono
        if OWNER_NAME.lower() in subject_lower or OWNER_NAME.lower() in body_lower:
            return 'important'
        
        # Remetentes importantes
        if any(s in sender_lower for s in cls.IMPORTANT_SENDERS):
            return 'important'
        
        # Promoção/Spam
        promo_keywords = sum(1 for kw in cls.PROMO_KEYWORDS if kw in subject_lower or kw in body_lower)
        promo_sender = any(s in sender_lower for s in cls.PROMO_SENDERS)
        
        if promo_sender or promo_keywords >= 2:
            return 'promotional'
        
        return 'normal'

class GmailCleaner:
    def __init__(self):
        self.creds = self._load_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)
        self.knowledge_db = self._load_knowledge()
    
    def _load_credentials(self) -> Credentials:
        with open(TOKEN_FILE, encoding='utf-8-sig') as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data['token'],
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data['token_uri'],
            client_id=token_data['client_id'],
            client_secret=token_data['client_secret']
        )
        
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_data['token'] = creds.token
            with open(TOKEN_FILE, 'w') as f:
                json.dump(token_data, f, indent=2)
        
        return creds
    
    def _load_knowledge(self) -> Dict:
        if os.path.exists(EMAILS_DB):
            with open(EMAILS_DB) as f:
                return json.load(f)
        return {"emails": [], "processed_ids": []}
    
    def _save_knowledge(self):
        with open(EMAILS_DB, 'w') as f:
            json.dump(self.knowledge_db, f, indent=2, ensure_ascii=False)
    
    def list_emails(self, max_results: int = 50) -> List[Email]:
        logger.info(f"📥 Buscando até {max_results} emails...")
        
        results = self.service.users().messages().list(
            userId='me', maxResults=max_results, labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for i, msg in enumerate(messages):
            try:
                logger.info(f"📧 Carregando email {i+1}/{len(messages)}...")
                msg_data = self.service.users().messages().get(
                    userId='me', id=msg['id'], format='full'
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                
                body = ""
                payload = msg_data['payload']
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part['mimeType'] == 'text/plain' and part['body'].get('data'):
                            body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            break
                elif payload['body'].get('data'):
                    body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
                
                emails.append(Email(
                    id=msg['id'],
                    subject=headers.get('Subject', 'Sem assunto'),
                    sender=headers.get('From', 'Desconhecido'),
                    snippet=msg_data.get('snippet', ''),
                    body=body[:1500],
                    date=headers.get('Date', '')
                ))
            except Exception as e:
                logger.error(f"Erro: {e}")
        
        return emails
    
    def move_to_trash(self, email_id: str) -> bool:
        try:
            self.service.users().messages().trash(userId='me', id=email_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao mover: {e}")
            return False
    
    def train_email(self, email: Email):
        """Salva email na base de conhecimento"""
        if email.id in self.knowledge_db['processed_ids']:
            return False
        
        self.knowledge_db['emails'].append({
            'id': email.id,
            'subject': email.subject,
            'sender': email.sender,
            'body': email.body or email.snippet,
            'date': email.date,
            'indexed_at': datetime.now().isoformat()
        })
        self.knowledge_db['processed_ids'].append(email.id)
        return True
    
    def process_emails(self) -> Dict:
        logger.info("=" * 60)
        logger.info("🔄 PROCESSAMENTO DE EMAILS")
        logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        stats = {'total': 0, 'trained': 0, 'removed': 0, 'kept': 0}
        
        emails = self.list_emails(50)
        stats['total'] = len(emails)
        
        for email in emails:
            category = EmailClassifier.classify(email)
            
            if category == 'promotional':
                logger.info(f"🗑️ REMOVENDO: {email.subject[:50]}")
                if self.move_to_trash(email.id):
                    stats['removed'] += 1
            else:
                if self.train_email(email):
                    logger.info(f"🧠 TREINADO: {email.subject[:50]}")
                    stats['trained'] += 1
                stats['kept'] += 1
        
        self._save_knowledge()
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 RESULTADO")
        logger.info(f"📧 Total: {stats['total']}")
        logger.info(f"🧠 Treinados: {stats['trained']}")
        logger.info(f"🗑️ Removidos: {stats['removed']}")
        logger.info(f"✅ Mantidos: {stats['kept']}")
        logger.info(f"💾 Base de conhecimento: {len(self.knowledge_db['emails'])} emails")
        logger.info("=" * 60)
        
        return stats

def main():
    try:
        cleaner = GmailCleaner()
        stats = cleaner.process_emails()
        
        # Salvar stats
        with open("/home/eddie/myClaude/gmail_data/last_run.json", 'w') as f:
            stats['timestamp'] = datetime.now().isoformat()
            json.dump(stats, f, indent=2)
            
    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        raise

if __name__ == '__main__':
    main()
