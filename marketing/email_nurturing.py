#!/usr/bin/env python3
"""Sequência de nutrição por email — Marketing RPA4ALL.

Processa leads com drip_step pendente e envia o próximo email da sequência.
Executar via cron diário ou systemd timer.

Uso:
    python3 marketing/email_nurturing.py              # Processa todos pendentes
    python3 marketing/email_nurturing.py --dry-run     # Modo teste
    python3 marketing/email_nurturing.py --send-test EMAIL  # Envia sequência teste
"""

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger("marketing.email_nurturing")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# ─── Config ──────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@192.168.15.2:5433/shared",
)
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "marketing@rpa4all.com")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "RPA4ALL <marketing@rpa4all.com>")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"

# Intervalos entre emails (em dias)
DRIP_INTERVALS = [0, 2, 5, 8, 12]

# ─── Sequência de Emails ─────────────────────────────────────────────
DRIP_SEQUENCE = [
    {
        "step": 0,
        "subject": "✅ Diagnóstico de Automação RPA4ALL — Confirmação",
        "body_html": """
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
    <h1 style="color: #00d4ff; margin: 0; font-size: 28px;">RPA4ALL</h1>
    <p style="color: #aaa; margin: 5px 0 0;">Automação Inteligente</p>
  </div>
  <div style="padding: 30px; background: #fff;">
    <h2 style="color: #1a1a2e;">Olá {nome}! 👋</h2>
    <p>Obrigado pelo interesse no <strong>Diagnóstico de Automação Gratuito</strong> da RPA4ALL.</p>
    <p>Recebemos seu cadastro e um especialista entrará em contato em até <strong>48 horas</strong> para agendar sua sessão de 20 minutos.</p>
    <p>Durante o diagnóstico, vamos:</p>
    <ul>
      <li>🔍 Mapear seus processos mais repetitivos</li>
      <li>📊 Identificar oportunidades de automação</li>
      <li>💰 Estimar a economia potencial</li>
      <li>🗺️ Traçar um roadmap prático</li>
    </ul>
    <p>Enquanto isso, que tal pensar em qual processo da <strong>{empresa}</strong> mais consome tempo da sua equipe?</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="https://www.rpa4all.com/#solutions" style="background: #00d4ff; color: #1a1a2e; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">Ver nossas soluções</a>
    </div>
  </div>
  <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #999;">
    <p>RPA4ALL · Automação inteligente para empresas</p>
    <p><a href="mailto:contato@rpa4all.com" style="color: #00d4ff;">contato@rpa4all.com</a></p>
  </div>
</div>
""",
    },
    {
        "step": 1,
        "subject": "🔍 3 sinais de que sua empresa precisa de automação",
        "body_html": """
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
    <h1 style="color: #00d4ff; margin: 0; font-size: 28px;">RPA4ALL</h1>
  </div>
  <div style="padding: 30px; background: #fff;">
    <h2 style="color: #1a1a2e;">Olá {nome}!</h2>
    <p>Você sabia que muitas empresas perdem <strong>até 30% do tempo da equipe</strong> em tarefas que poderiam ser automatizadas?</p>
    <h3 style="color: #00d4ff;">3 sinais claros:</h3>
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0;">
      <p><strong>1. ⏰ Tarefas repetitivas diárias</strong><br/>Copiar dados entre sistemas, gerar relatórios manuais, enviar emails padronizados...</p>
      <p><strong>2. ❌ Erros humanos frequentes</strong><br/>Digitação incorreta, dados inconsistentes, prazos perdidos por esquecimento...</p>
      <p><strong>3. 📈 Crescimento = mais gente</strong><br/>Se a única forma de crescer é contratar mais pessoas para fazer o mesmo, automação é urgente.</p>
    </div>
    <p>Na <strong>{empresa}</strong>, quantos desses sinais você reconhece?</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="https://www.rpa4all.com/#contact" style="background: #00d4ff; color: #1a1a2e; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">Agendar meu diagnóstico</a>
    </div>
  </div>
  <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #999;">
    <p>RPA4ALL · <a href="mailto:contato@rpa4all.com" style="color: #00d4ff;">contato@rpa4all.com</a></p>
  </div>
</div>
""",
    },
    {
        "step": 2,
        "subject": "📊 Case real: como reduzimos 70% do trabalho manual",
        "body_html": """
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
    <h1 style="color: #00d4ff; margin: 0; font-size: 28px;">RPA4ALL</h1>
  </div>
  <div style="padding: 30px; background: #fff;">
    <h2 style="color: #1a1a2e;">{nome}, veja esse resultado 👇</h2>
    <div style="background: linear-gradient(135deg, #e8f5e8 0%, #f0faf0 100%); padding: 25px; border-radius: 8px; border-left: 4px solid #28a745; margin: 15px 0;">
      <h3 style="color: #28a745; margin-top: 0;">Case: Empresa de Contabilidade</h3>
      <p><strong>Problema:</strong> 3 pessoas dedicadas a lançamentos manuais de NFs no ERP. 120h/mês gastas em copy-paste.</p>
      <p><strong>Solução RPA4ALL:</strong> Agente inteligente que lê NFs (OCR + IA), classifica automaticamente e lança no ERP.</p>
      <p><strong>Resultados em 30 dias:</strong></p>
      <ul>
        <li>⏰ Redução de <strong>70%</strong> do tempo manual</li>
        <li>❌ Erros reduzidos de 8% para <strong>0.3%</strong></li>
        <li>💰 Economia de <strong>R$ 8.500/mês</strong></li>
        <li>😊 Equipe focada em análise (não digitação)</li>
      </ul>
    </div>
    <p>Imagine resultados assim na <strong>{empresa}</strong>. O primeiro passo é o diagnóstico gratuito.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="https://www.rpa4all.com/#contact" style="background: #00d4ff; color: #1a1a2e; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">Quero meu diagnóstico</a>
    </div>
  </div>
  <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #999;">
    <p>RPA4ALL · <a href="mailto:contato@rpa4all.com" style="color: #00d4ff;">contato@rpa4all.com</a></p>
  </div>
</div>
""",
    },
    {
        "step": 3,
        "subject": "📋 Checklist: 10 processos que podem ser automatizados hoje",
        "body_html": """
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
    <h1 style="color: #00d4ff; margin: 0; font-size: 28px;">RPA4ALL</h1>
  </div>
  <div style="padding: 30px; background: #fff;">
    <h2 style="color: #1a1a2e;">{nome}, um presente pra você! 🎁</h2>
    <p>Preparamos um checklist dos <strong>10 processos mais automatizáveis</strong> nas empresas brasileiras:</p>
    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 15px 0;">
      <ol style="line-height: 2;">
        <li>✅ Conciliação bancária</li>
        <li>✅ Emissão de notas fiscais</li>
        <li>✅ Envio de boletos e cobranças</li>
        <li>✅ Cadastro de clientes/fornecedores</li>
        <li>✅ Geração de relatórios periódicos</li>
        <li>✅ Processamento de emails padronizados</li>
        <li>✅ Atualização de planilhas e dashboards</li>
        <li>✅ Validação de documentos (CPF, CNPJ)</li>
        <li>✅ Integração entre ERPs e CRMs</li>
        <li>✅ Atendimento ao cliente (FAQ + triagem)</li>
      </ol>
    </div>
    <p>Quantos desses a <strong>{empresa}</strong> faz manualmente? Se forem 3 ou mais, o diagnóstico gratuito vai mostrar por onde começar.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="https://www.rpa4all.com/#contact" style="background: #00d4ff; color: #1a1a2e; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">Agendar diagnóstico gratuito</a>
    </div>
  </div>
  <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #999;">
    <p>RPA4ALL · <a href="mailto:contato@rpa4all.com" style="color: #00d4ff;">contato@rpa4all.com</a></p>
  </div>
</div>
""",
    },
    {
        "step": 4,
        "subject": "⏰ {nome}, última chance: diagnóstico gratuito de automação",
        "body_html": """
<div style="font-family: 'Inter', Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
  <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 30px; text-align: center;">
    <h1 style="color: #00d4ff; margin: 0; font-size: 28px;">RPA4ALL</h1>
  </div>
  <div style="padding: 30px; background: #fff;">
    <h2 style="color: #1a1a2e;">{nome}, tudo bem? 🤔</h2>
    <p>Notei que você ainda não agendou seu <strong>Diagnóstico de Automação Gratuito</strong>.</p>
    <p>Entendo que a agenda é corrida — por isso, a sessão é de apenas <strong>20 minutos</strong> e pode ser por videochamada.</p>
    <div style="background: #fff3cd; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 15px 0;">
      <p style="margin: 0;"><strong>⚡ O que você ganha (sem compromisso):</strong></p>
      <ul>
        <li>Mapeamento dos seus processos mais custosos</li>
        <li>Estimativa de economia com automação</li>
        <li>Roadmap personalizado de implementação</li>
        <li>Comparativo: manual vs. automatizado</li>
      </ul>
    </div>
    <p>Não deixe para depois — cada dia sem automação é dinheiro e tempo que a <strong>{empresa}</strong> está perdendo.</p>
    <div style="text-align: center; margin: 30px 0;">
      <a href="https://www.rpa4all.com/#contact" style="background: #ff6b35; color: #fff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">🚀 Agendar agora (é grátis)</a>
    </div>
    <p style="text-align: center; color: #999; font-size: 13px;">Caso não tenha mais interesse, desconsidere este email.<br/>Não enviaremos mais mensagens.</p>
  </div>
  <div style="background: #f5f5f5; padding: 20px; text-align: center; font-size: 12px; color: #999;">
    <p>RPA4ALL · <a href="mailto:contato@rpa4all.com" style="color: #00d4ff;">contato@rpa4all.com</a></p>
  </div>
</div>
""",
    },
]


# ─── Funções ─────────────────────────────────────────────────────────
def _get_conn():
    """Obtém conexão PostgreSQL."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def _get_pending_leads() -> list[dict]:
    """Retorna leads com drip pendente."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, nome, email, empresa, drip_step
                FROM marketing.leads
                WHERE status = 'novo'
                  AND drip_step < %s
                  AND (drip_next_at IS NULL OR drip_next_at <= NOW())
                ORDER BY drip_next_at ASC
                LIMIT 50
            """, (len(DRIP_SEQUENCE),))
            return cur.fetchall()
    finally:
        conn.close()


def _advance_drip(lead_id: int, new_step: int) -> None:
    """Avança lead para o próximo step do drip."""
    conn = _get_conn()
    try:
        next_interval = DRIP_INTERVALS[new_step] if new_step < len(DRIP_INTERVALS) else 999
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE marketing.leads
                SET drip_step = %s,
                    drip_next_at = NOW() + make_interval(days => %s),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (new_step, next_interval, lead_id),
            )
    finally:
        conn.close()


def _mark_completed(lead_id: int) -> None:
    """Marca lead como drip completo."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE marketing.leads
                SET status = 'nutrido', updated_at = NOW()
                WHERE id = %s
                """,
                (lead_id,),
            )
    finally:
        conn.close()


def _send_email(to_email: str, subject: str, html_body: str, dry_run: bool = False) -> bool:
    """Envia email via SMTP."""
    if dry_run:
        logger.info("[DRY RUN] Enviaria para %s: %s", to_email, subject)
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Reply-To"] = "contato@rpa4all.com"
    msg["List-Unsubscribe"] = "<mailto:unsubscribe@rpa4all.com>"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        logger.info("Email enviado para %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Falha ao enviar email para %s", to_email)
        return False


def _render_email(template: dict, lead: dict) -> tuple[str, str]:
    """Renderiza subject e body com dados do lead."""
    subject = template["subject"].format(
        nome=lead["nome"].split()[0],
        empresa=lead["empresa"],
    )
    body = template["body_html"].format(
        nome=lead["nome"].split()[0],
        empresa=lead["empresa"],
    )
    return subject, body


def process_drip(dry_run: bool = False) -> dict:
    """Processa todos os leads com drip pendente."""
    leads = _get_pending_leads()
    stats = {"processed": 0, "sent": 0, "failed": 0, "completed": 0}

    for lead in leads:
        step = lead["drip_step"]
        if step >= len(DRIP_SEQUENCE):
            _mark_completed(lead["id"])
            stats["completed"] += 1
            continue

        template = DRIP_SEQUENCE[step]
        subject, body = _render_email(template, lead)

        if _send_email(lead["email"], subject, body, dry_run=dry_run):
            next_step = step + 1
            _advance_drip(lead["id"], next_step)
            stats["sent"] += 1

            if next_step >= len(DRIP_SEQUENCE):
                _mark_completed(lead["id"])
                stats["completed"] += 1
        else:
            stats["failed"] += 1

        stats["processed"] += 1

    logger.info(
        "Drip processado: %s processados, %s enviados, %s falhas, %s completos",
        stats["processed"],
        stats["sent"],
        stats["failed"],
        stats["completed"],
    )
    return stats


# ─── CLI ─────────────────────────────────────────────────────────────
def main() -> None:
    """Entrypoint CLI."""
    parser = argparse.ArgumentParser(description="Email Nurturing — RPA4ALL Marketing")
    parser.add_argument("--dry-run", action="store_true", help="Modo teste (não envia)")
    parser.add_argument("--send-test", metavar="EMAIL", help="Envia sequência de teste para email")
    args = parser.parse_args()

    if args.send_test:
        logger.info("Enviando sequência de teste para %s", args.send_test)
        test_lead = {"nome": "Teste", "email": args.send_test, "empresa": "Empresa Teste"}
        for template in DRIP_SEQUENCE:
            subject, body = _render_email(template, test_lead)
            ok = _send_email(args.send_test, subject, body, dry_run=args.dry_run)
            status = "✅" if ok else "❌"
            print(f"  {status} Step {template['step']}: {subject}")
        return

    stats = process_drip(dry_run=args.dry_run)
    print(f"\n📧 Drip concluído:")
    print(f"   Processados: {stats['processed']}")
    print(f"   Enviados:    {stats['sent']}")
    print(f"   Falhas:      {stats['failed']}")
    print(f"   Completos:   {stats['completed']}")


if __name__ == "__main__":
    main()
