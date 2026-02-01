#!/usr/bin/env python3
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "gmail_data"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.pickle"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

WHITELIST = [
    "nubank",
    "itau",
    "bradesco",
    "gov.br",
    "github.com",
    "google.com",
    "microsoft.com",
    "openai.com",
    "anthropic.com",
    "paypal",
    "mercadopago",
]
IMPORTANT_SUBJECTS = [
    "pagamento",
    "fatura",
    "boleto",
    "senha",
    "password",
    "contrato",
    "urgente",
    "important",
    "reuniao",
    "servidor",
    "deploy",
    "erro",
    "pull request",
]
BLACKLIST = [
    "mailchimp",
    "sendgrid",
    "newsletter",
    "noreply",
    "no-reply",
    "marketing@",
    "promo@",
    "amazon.com.br",
    "mercadolivre",
    "shopee",
    "aliexpress",
    "facebookmail",
    "twitter",
    "linkedin",
    "instagram",
    "netflix",
    "spotify",
    "uber.com",
    "ifood",
    "rappi",
    "medium.com",
    "udemy",
]


class GmailCleaner:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.service = None
        self.stats = {
            "scanned": 0,
            "to_delete": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
        }
        self.by_sender = defaultdict(int)

    def authenticate(self):
        creds = None
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, "rb") as f:
                creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            if not CREDENTIALS_FILE.exists():
                logger.error("Arquivo credentials.json nao encontrado")
                return False
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
            DATA_DIR.mkdir(exist_ok=True)
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(creds, f)
        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Autenticado!")
        return True

    def is_whitelisted(self, sender, subject):
        s = (sender + " " + subject).lower()
        return any(w.lower() in s for w in WHITELIST) or any(
            w.lower() in subject.lower() for w in IMPORTANT_SUBJECTS
        )

    def is_blacklisted(self, sender):
        return any(b.lower() in sender.lower() for b in BLACKLIST)

    def get_header(self, headers, name):
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return ""

    def scan_and_clean(self, query, max_results=500):
        candidates = []
        try:
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = results.get("messages", [])
            logger.info("Encontrados {} emails".format(len(messages)))
            for i, msg in enumerate(messages):
                if (i + 1) % 50 == 0:
                    logger.info("Analisando {}/{}...".format(i + 1, len(messages)))
                self.stats["scanned"] += 1
                try:
                    email = (
                        self.service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=msg["id"],
                            format="metadata",
                            metadataHeaders=["From", "Subject"],
                        )
                        .execute()
                    )
                    headers = email.get("payload", {}).get("headers", [])
                    sender = self.get_header(headers, "From")
                    subject = self.get_header(headers, "Subject")
                    if self.is_whitelisted(sender, subject):
                        self.stats["skipped"] += 1
                        continue
                    if self.is_blacklisted(sender):
                        candidates.append(msg["id"])
                        domain = (
                            sender.split("@")[-1].split(">")[0]
                            if "@" in sender
                            else sender[:30]
                        )
                        self.by_sender[domain] += 1
                        self.stats["to_delete"] += 1
                except:
                    self.stats["errors"] += 1
        except HttpError as e:
            logger.error("Erro: {}".format(e))
        return candidates

    def delete_emails(self, ids):
        if self.dry_run:
            logger.info("[SIMULACAO] {} emails seriam excluidos".format(len(ids)))
            return 0
        deleted = 0
        for i in range(0, len(ids), 100):
            batch = ids[i : i + 100]
            try:
                self.service.users().messages().batchModify(
                    userId="me",
                    body={
                        "ids": batch,
                        "addLabelIds": ["TRASH"],
                        "removeLabelIds": ["INBOX"],
                    },
                ).execute()
                deleted += len(batch)
                logger.info("Excluidos {}/{}".format(deleted, len(ids)))
            except Exception as e:
                logger.error("Erro: {}".format(e))
        self.stats["deleted"] = deleted
        return deleted

    def clean_promotions(self, days=30):
        date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
        query = "before:{} category:promotions".format(date)
        logger.info("Query: {}".format(query))
        ids = self.scan_and_clean(query)
        if ids:
            self.delete_emails(ids)

    def clean_social(self, days=60):
        date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
        query = "before:{} category:social".format(date)
        logger.info("Query: {}".format(query))
        ids = self.scan_and_clean(query)
        if ids:
            self.delete_emails(ids)

    def report(self):
        print("\n" + "=" * 50)
        print("RELATORIO DE LIMPEZA")
        print("=" * 50)
        print("  Analisados:  {}".format(self.stats["scanned"]))
        print("  P/ Excluir:  {}".format(self.stats["to_delete"]))
        print("  Pulados:     {}".format(self.stats["skipped"]))
        print("  Excluidos:   {}".format(self.stats["deleted"]))
        print("  Erros:       {}".format(self.stats["errors"]))
        if self.by_sender:
            print("\nTop remetentes:")
            for s, c in sorted(self.by_sender.items(), key=lambda x: -x[1])[:10]:
                print("    {}: {}".format(s, c))
        print("=" * 50)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    print("\nEMAIL CLEANER - Limpeza para Edenilson")
    print("=" * 50)
    dry_run = not args.execute
    print("Modo: {}\n".format("SIMULACAO" if dry_run else "EXECUCAO"))
    cleaner = GmailCleaner(dry_run=dry_run)
    if not cleaner.authenticate():
        return
    cleaner.clean_promotions(days=args.days)
    cleaner.clean_social(days=args.days * 2)
    cleaner.report()
    if dry_run:
        print("\nPara executar: python3 email_cleaner.py --execute")


if __name__ == "__main__":
    main()
