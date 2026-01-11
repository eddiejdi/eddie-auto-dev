#!/usr/bin/env python3
"""
Gmail Email Trainer & Cleaner
Treina a IA com emails importantes e remove spam/promoções
Executa semanalmente via systemd timer
"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import chromadb
import requests

# Configuração
OLLAMA_URL = "http://192.168.15.2:11434"
EMBED_MODEL = "nomic-embed-text"
TOKEN_FILE = "/home/homelab/myClaude/gmail_data/token.json"
CHROMA_PATH = "/home/homelab/myClaude/gmail_data/chroma_emails"
LOG_FILE = "/home/homelab/myClaude/gmail_data/email_cleaner.log"
OWNER_NAME = "Edenilson"
OWNER_EMAIL = "edenilson.adm@gmail.com"

# Configurar logging
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
    labels: List[str] = None
    date: str = ""

class EmailClassifier:
    """Classifica emails como spam, promoção, importante ou normal"""
    
    SPAM_KEYWORDS = [
        'unsubscribe', 'opt-out', 'click here', 'limited time', 
        'act now', 'winner', 'prize', 'lottery', 'casino',
        'viagra', 'cryptocurrency giveaway', 'free money'
    ]
    
    PROMO_KEYWORDS = [
        'cupom', 'desconto', 'oferta', 'promoção', 'sale', 'off',
        'black friday', 'liquidação', 'frete grátis', 'aproveite',
        'últimas unidades', 'compre agora', 'não perca', 'exclusivo',
        'newsletter', 'marketing', 'vip exclusive', 'win for rewards'
    ]
    
    PROMO_SENDERS = [
        'marketing', 'promo', 'newsletter', 'noreply', 'no-reply',
        'mkt@', 'news@', 'info@', 'contato@email', 'kucoin', 
        'mercadolivre', 'amazon.com.br', 'shopee', 'aliexpress',
        'insider', 'loja', 'store', 'shop'
    ]
    
    IMPORTANT_SENDERS = [
        'google.com', 'linkedin.com', 'github.com', 'microsoft.com',
        'banco', 'bank', 'gov.br', 'receita', 'caixa', 'itau',
        'bradesco', 'santander', 'nubank', 'inter', 'mercadopago'
    ]
    
    @classmethod
    def classify(cls, email: Email) -> Tuple[str, float]:
        """Retorna (categoria, confiança)"""
        subject_lower = email.subject.lower()
        sender_lower = email.sender.lower()
        body_lower = email.body.lower() if email.body else ""
        
        # Verificar se menciona o dono
        if OWNER_NAME.lower() in subject_lower or OWNER_NAME.lower() in body_lower:
            return ('important', 0.9)
        
        # Verificar remetentes importantes (bancos, gov, etc)
        for sender in cls.IMPORTANT_SENDERS:
            if sender in sender_lower:
                return ('important', 0.85)
        
        # Verificar spam
        spam_score = sum(1 for kw in cls.SPAM_KEYWORDS if kw in subject_lower or kw in body_lower)
        if spam_score >= 2:
            return ('spam', min(0.5 + spam_score * 0.1, 0.95))
        
        # Verificar promoção
        promo_score = sum(1 for kw in cls.PROMO_KEYWORDS if kw in subject_lower or kw in body_lower)
        promo_sender = any(s in sender_lower for s in cls.PROMO_SENDERS)
        
        if promo_sender and promo_score >= 1:
            return ('promotional', min(0.6 + promo_score * 0.1, 0.95))
        if promo_score >= 2:
            return ('promotional', min(0.5 + promo_score * 0.1, 0.9))
        
        return ('normal', 0.5)

class EmailTrainer:
    """Indexa emails importantes no ChromaDB para RAG"""
    
    def __init__(self):
        os.makedirs(CHROMA_PATH, exist_ok=True)
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_or_create_collection(
            name="emails",
            metadata={"description": "Emails importantes do usuário"}
        )
    
    def get_embedding(self, text: str) -> List[float]:
        """Gera embedding via Ollama"""
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
        return None
    
    def train_email(self, email: Email) -> bool:
        """Indexa um email no ChromaDB"""
        # Verificar se já existe
        existing = self.collection.get(ids=[email.id])
        if existing and existing['ids']:
            logger.debug(f"Email {email.id} já indexado")
            return False
        
        # Preparar texto
        text = f"De: {email.sender}\nAssunto: {email.subject}\n\n{email.body or email.snippet}"
        
        # Gerar embedding
        embedding = self.get_embedding(text)
        if not embedding:
            return False
        
        # Indexar
        self.collection.add(
            ids=[email.id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{
                "subject": email.subject[:200],
                "sender": email.sender[:100],
                "date": email.date,
                "indexed_at": datetime.now().isoformat()
            }]
        )
        logger.info(f"✅ Email indexado: {email.subject[:50]}")
        return True
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do treinamento"""
        return {
            "total_emails": self.collection.count(),
            "storage_path": CHROMA_PATH
        }

class GmailCleaner:
    """Cliente Gmail para leitura e limpeza"""
    
    def __init__(self):
        self.creds = self._load_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)
        self.trainer = EmailTrainer()
    
    def _load_credentials(self) -> Credentials:
        """Carrega e atualiza credenciais"""
        with open(TOKEN_FILE, encoding='utf-8-sig') as f:
            token_data = json.load(f)
        
        creds = Credentials(
            token=token_data['token'],
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data['token_uri'],
            client_id=token_data['client_id'],
            client_secret=token_data['client_secret']
        )
        
        # Renovar se expirado
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Salvar novo token
            token_data['token'] = creds.token
            with open(TOKEN_FILE, 'w') as f:
                json.dump(token_data, f, indent=2)
        
        return creds
    
    def list_emails(self, max_results: int = 100) -> List[Email]:
        """Lista emails da inbox"""
        results = self.service.users().messages().list(
            userId='me', 
            maxResults=max_results,
            labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            try:
                msg_data = self.service.users().messages().get(
                    userId='me', 
                    id=msg['id'],
                    format='full'
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
                
                # Extrair corpo
                body = ""
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        if part['mimeType'] == 'text/plain':
                            import base64
                            body = base64.urlsafe_b64decode(part['body'].get('data', '')).decode('utf-8', errors='ignore')
                            break
                elif 'body' in msg_data['payload'] and msg_data['payload']['body'].get('data'):
                    import base64
                    body = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')
                
                emails.append(Email(
                    id=msg['id'],
                    subject=headers.get('Subject', 'Sem assunto'),
                    sender=headers.get('From', 'Desconhecido'),
                    snippet=msg_data.get('snippet', ''),
                    body=body[:2000],  # Limitar tamanho
                    labels=msg_data.get('labelIds', []),
                    date=headers.get('Date', '')
                ))
            except Exception as e:
                logger.error(f"Erro ao processar email {msg['id']}: {e}")
        
        return emails
    
    def move_to_trash(self, email_id: str) -> bool:
        """Move email para lixeira"""
        try:
            self.service.users().messages().trash(userId='me', id=email_id).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao mover para lixeira: {e}")
            return False
    
    def mark_as_spam(self, email_id: str) -> bool:
        """Marca email como spam"""
        try:
            self.service.users().messages().modify(
                userId='me', 
                id=email_id,
                body={'addLabelIds': ['SPAM'], 'removeLabelIds': ['INBOX']}
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Erro ao marcar como spam: {e}")
            return False
    
    def process_emails(self, dry_run: bool = False) -> Dict:
        """Processa emails: treina importantes, remove spam/promoções"""
        logger.info("=" * 60)
        logger.info("🔄 INICIANDO PROCESSAMENTO DE EMAILS")
        logger.info(f"📅 Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        stats = {
            'total': 0,
            'trained': 0,
            'spam_removed': 0,
            'promo_removed': 0,
            'kept': 0,
            'errors': 0
        }
        
        emails = self.list_emails(max_results=50)
        stats['total'] = len(emails)
        logger.info(f"📧 Total de emails para processar: {stats['total']}")
        
        for email in emails:
            try:
                category, confidence = EmailClassifier.classify(email)
                
                if category == 'spam':
                    logger.info(f"🗑️ SPAM ({confidence:.0%}): {email.subject[:50]}")
                    if not dry_run:
                        if self.mark_as_spam(email.id):
                            stats['spam_removed'] += 1
                        else:
                            stats['errors'] += 1
                    else:
                        stats['spam_removed'] += 1
                
                elif category == 'promotional':
                    logger.info(f"📢 PROMOÇÃO ({confidence:.0%}): {email.subject[:50]}")
                    if not dry_run:
                        if self.move_to_trash(email.id):
                            stats['promo_removed'] += 1
                        else:
                            stats['errors'] += 1
                    else:
                        stats['promo_removed'] += 1
                
                elif category == 'important':
                    logger.info(f"⭐ IMPORTANTE ({confidence:.0%}): {email.subject[:50]}")
                    if self.trainer.train_email(email):
                        stats['trained'] += 1
                    stats['kept'] += 1
                
                else:  # normal
                    logger.debug(f"📋 Normal: {email.subject[:50]}")
                    # Treinar emails normais também
                    if self.trainer.train_email(email):
                        stats['trained'] += 1
                    stats['kept'] += 1
                    
            except Exception as e:
                logger.error(f"Erro processando email: {e}")
                stats['errors'] += 1
        
        # Relatório final
        logger.info("\n" + "=" * 60)
        logger.info("📊 RELATÓRIO FINAL")
        logger.info("=" * 60)
        logger.info(f"📧 Total processados: {stats['total']}")
        logger.info(f"🧠 Emails treinados: {stats['trained']}")
        logger.info(f"🗑️ Spam removido: {stats['spam_removed']}")
        logger.info(f"📢 Promoções removidas: {stats['promo_removed']}")
        logger.info(f"✅ Emails mantidos: {stats['kept']}")
        logger.info(f"❌ Erros: {stats['errors']}")
        logger.info(f"💾 Total na base de conhecimento: {self.trainer.get_stats()['total_emails']}")
        logger.info("=" * 60)
        
        return stats

def main():
    """Executa o processamento de emails"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Gmail Email Trainer & Cleaner')
    parser.add_argument('--dry-run', action='store_true', help='Simula sem executar ações')
    parser.add_argument('--stats', action='store_true', help='Mostra apenas estatísticas')
    args = parser.parse_args()
    
    try:
        cleaner = GmailCleaner()
        
        if args.stats:
            stats = cleaner.trainer.get_stats()
            print(f"📊 Emails na base de conhecimento: {stats['total_emails']}")
            return
        
        if args.dry_run:
            logger.info("🔍 MODO DRY-RUN (simulação)")
        
        stats = cleaner.process_emails(dry_run=args.dry_run)
        
        # Salvar stats em arquivo
        stats_file = "/home/homelab/myClaude/gmail_data/last_run_stats.json"
        stats['timestamp'] = datetime.now().isoformat()
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        raise

if __name__ == '__main__':
    main()
