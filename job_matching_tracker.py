#!/usr/bin/env python3
"""
Arquivo de controle para rastreamento de emails de vaga enviados.
Impede reenvios duplicados em 30 dias.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path("/tmp/job_matching_tracker.db")

class JobMatchingTracker:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
    
    def init_db(self):
        """Initialize SQLite database for tracking."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sent_drafts (
            id INTEGER PRIMARY KEY,
            email_to TEXT UNIQUE,
            subject TEXT,
            sent_at TIMESTAMP,
            job_count INTEGER,
            status TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sent_applications (
            id INTEGER PRIMARY KEY,
            company TEXT,
            job_title TEXT,
            email_sent_to TEXT,
            sent_at TIMESTAMP,
            status TEXT
        )''')
        conn.commit()
        conn.close()
    
    def mark_draft_sent(self, email_to: str, subject: str, job_count: int):
        """Mark draft as sent to prevent re-sending in 30 days."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO sent_drafts (email_to, subject, sent_at, job_count, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (email_to, subject, datetime.now().isoformat(), job_count, 'SENT'))
        conn.commit()
        conn.close()
        print(f"✅ Marcado: draft enviado para {email_to} em {datetime.now()}")
    
    def mark_application_sent(self, company: str, job_title: str, email: str):
        """Mark a job application as sent."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('''
            INSERT INTO sent_applications (company, job_title, email_sent_to, sent_at, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (company, job_title, email, datetime.now().isoformat(), 'APPLIED'))
        conn.commit()
        conn.close()
    
    def should_send_draft_to(self, email_to: str) -> bool:
        """Check if draft should be sent (not sent in last 30 days)."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute('SELECT sent_at FROM sent_drafts WHERE email_to = ?', (email_to,))
        row = c.fetchone()
        conn.close()
        
        if not row:
            return True  # Never sent
        
        sent_at = datetime.fromisoformat(row[0])
        days_ago = (datetime.now() - sent_at).days
        
        if days_ago < 30:
            print(f"⚠️ Draft já enviado para {email_to} há {days_ago} dias. Aguarde 30 dias.")
            return False
        
        return True
    
    def should_apply_to(self, company: str, job_title: str) -> bool:
        """Check if already applied to this position."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute(
            'SELECT sent_at FROM sent_applications WHERE company = ? AND job_title = ?',
            (company, job_title)
        )
        row = c.fetchone()
        conn.close()
        
        return not row  # Return True if NOT found
    
    def get_stats(self) -> dict:
        """Get tracking statistics."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        
        c.execute('SELECT COUNT(*) FROM sent_drafts')
        draft_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM sent_applications')
        app_count = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT email_sent_to) FROM sent_applications')
        unique_companies = c.fetchone()[0]
        
        conn.close()
        
        return {
            'drafts_sent': draft_count,
            'applications_sent': app_count,
            'unique_companies': unique_companies,
        }

if __name__ == '__main__':
    tracker = JobMatchingTracker()
    
    # Mark the draft sent to edenilson.adm@gmail.com
    tracker.mark_draft_sent(
        'edenilson.adm@gmail.com',
        '[DRAFT] Oportunidades de Emprego - Análise de Matching',
        3
    )
    
    print("\n📊 Estatísticas:")
    stats = tracker.get_stats()
    for key, val in stats.items():
        print(f"  {key}: {val}")
    
    print("\n✅ Rastreador configurado. Próximo draft: em 30 dias ou manualmente.")
