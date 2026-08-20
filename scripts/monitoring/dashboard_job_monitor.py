#!/usr/bin/env python3
"""
Dashboard de Monitoramento - Sistema de Aplicação Automática de Vagas.
Exibe estatísticas de emails enviados, vagas encontradas, grupos monitorados.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Paths
LOG_DIR = Path("/tmp/email_logs")
LOG_DB = LOG_DIR / "email_sends.db"
MONITOR_LOG = Path("/tmp/job_monitor/monitor.log")


def get_email_stats() -> dict:
    """Get email sending statistics from database."""
    if not LOG_DB.exists():
        return {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "draft": 0,
            "last_24h": 0,
            "last_7d": 0
        }
    
    conn = sqlite3.connect(str(LOG_DB))
    c = conn.cursor()
    
    # Total counts
    c.execute("SELECT COUNT(*) FROM email_sends")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM email_sends WHERE status = 'sent'")
    sent = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM email_sends WHERE status = 'failed'")
    failed = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM email_sends WHERE status = 'draft'")
    draft = c.fetchone()[0]
    
    # Time-based counts
    now = datetime.now()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    
    c.execute("SELECT COUNT(*) FROM email_sends WHERE timestamp >= ?", (day_ago,))
    last_24h = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM email_sends WHERE timestamp >= ?", (week_ago,))
    last_7d = c.fetchone()[0]
    
    conn.close()
    
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "draft": draft,
        "last_24h": last_24h,
        "last_7d": last_7d
    }


def get_recent_emails(limit: int = 10) -> list[dict]:
    """Get recent email records."""
    if not LOG_DB.exists():
        return []
    
    conn = sqlite3.connect(str(LOG_DB))
    c = conn.cursor()
    
    c.execute("""
        SELECT timestamp, to_email, subject, status, notes
        FROM email_sends
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    emails = []
    for row in rows:
        emails.append({
            "timestamp": row[0],
            "to_email": row[1],
            "subject": row[2],
            "status": row[3],
            "notes": row[4]
        })
    
    return emails


def get_monitor_stats() -> dict:
    """Parse monitor log for statistics."""
    if not MONITOR_LOG.exists():
        return {
            "running": False,
            "last_check": "N/A",
            "iterations": 0
        }
    
    # Read last 100 lines of log
    try:
        with open(MONITOR_LOG, 'r') as f:
            lines = f.readlines()[-100:]
        
        # Count iterations
        iterations = sum(1 for line in lines if "Iteration #" in line)
        
        # Find last check timestamp
        last_check = "N/A"
        for line in reversed(lines):
            if "Starting job search" in line:
                # Extract timestamp from log line
                parts = line.split(" - ")
                if len(parts) > 0:
                    last_check = parts[0]
                break
        
        running = any("Starting job search" in line for line in lines[-10:])
        
        return {
            "running": running,
            "last_check": last_check,
            "iterations": iterations
        }
    except Exception as e:
        return {
            "running": False,
            "last_check": f"Error: {e}",
            "iterations": 0
        }


def print_dashboard():
    """Print dashboard to console."""
    print("\n" + "="*70)
    print("       📊 DASHBOARD - SISTEMA DE APLICAÇÃO AUTOMÁTICA DE VAGAS")
    print("="*70 + "\n")
    
    # Email Statistics
    email_stats = get_email_stats()
    print("📧 ESTATÍSTICAS DE EMAILS")
    print("-" * 70)
    print(f"   Total enviados:     {email_stats['total']}")
    print(f"   ✅ Sucesso:         {email_stats['sent']}")
    print(f"   ❌ Falhas:          {email_stats['failed']}")
    print(f"   📝 Rascunhos:       {email_stats['draft']}")
    print(f"   🕐 Últimas 24h:     {email_stats['last_24h']}")
    print(f"   📅 Últimos 7 dias:  {email_stats['last_7d']}")
    print()
    
    # Monitor Statistics
    monitor_stats = get_monitor_stats()
    print("⚙️  MONITORAMENTO CONTÍNUO")
    print("-" * 70)
    status_icon = "🟢" if monitor_stats['running'] else "🔴"
    status_text = "ATIVO" if monitor_stats['running'] else "INATIVO"
    print(f"   Status:             {status_icon} {status_text}")
    print(f"   Última verificação: {monitor_stats['last_check']}")
    print(f"   Iterações (cache):  {monitor_stats['iterations']}")
    print()
    
    # Recent Emails
    recent = get_recent_emails(limit=5)
    if recent:
        print("📬 ÚLTIMOS 5 EMAILS ENVIADOS")
        print("-" * 70)
        for i, email in enumerate(recent, 1):
            ts = datetime.fromisoformat(email['timestamp']).strftime('%Y-%m-%d %H:%M')
            status_icon = "✅" if email['status'] == 'sent' else "❌" if email['status'] == 'failed' else "📝"
            print(f"   [{i}] {ts} | {status_icon} {email['status']}")
            print(f"       Para: {email['to_email']}")
            print(f"       Assunto: {email['subject'][:60]}")
            if email.get('notes'):
                print(f"       Notas: {email['notes'][:60]}")
            print()
    else:
        print("📬 Nenhum email registrado ainda")
        print()
    
    # Footer
    print("="*70)
    print(f"   🕐 Atualizado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


def export_json():
    """Export dashboard data as JSON."""
    data = {
        "email_stats": get_email_stats(),
        "monitor_stats": get_monitor_stats(),
        "recent_emails": get_recent_emails(limit=10),
        "generated_at": datetime.now().isoformat()
    }
    
    output_file = LOG_DIR / "dashboard.json"
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Dashboard exported to: {output_file}")
    return output_file


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        export_json()
    else:
        print_dashboard()
