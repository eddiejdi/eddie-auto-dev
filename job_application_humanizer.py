#!/usr/bin/env python3
"""
Script para gerar aplicações de emprego com tom mais humano e natural.
Busca vagas, calcula match com currículo, e envia draft para validação.
"""

import json
import subprocess
import sys
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# Vagas mockadas com tom mais natural (exemplo)
SAMPLE_JOBS = [
    {
        "id": "job_001",
        "title": "Senior DevOps Engineer",
        "company": "TechCorp Brasil",
        "description": "Procuramos um DevOps experiente para ajudar a escalar nossas operações. Você vai trabalhar com Kubernetes, CI/CD pipelines, e infraestrutura como código. Se você tem experiência com automação e ama resolver problemas complexos, queremos conversar com você.",
        "requirements": ["Kubernetes", "Docker", "CI/CD", "Python", "AWS"],
        "match_score": 0
    },
    {
        "id": "job_002",
        "title": "Platform Engineer",
        "company": "StartUp Inovadora",
        "description": "Estamos construindo a próxima geração de plataformas de dados. Buscamos alguém que entenda arquitetura, saiba codificar bem, e tenha paixão por excelência operacional.",
        "requirements": ["Go", "Dados", "Cloud", "API Design", "Observabilidade"],
        "match_score": 0
    },
    {
        "id": "job_003",
        "title": "SRE (Site Reliability Engineer)",
        "company": "FinTech Premium",
        "description": "A confiabilidade é tudo para nós. Procuramos um SRE que possa ajudar a garantir que nossas aplicações rodem como relógio. Você vai trabalhar em runbooks, automação, e observabilidade.",
        "requirements": ["SRE", "Automação", "Monitoring", "Cloud", "Incident Response"],
        "match_score": 0
    }
]

CURRICULUM_KEYWORDS = [
    "kubernetes", "docker", "ci/cd", "python", "aws", "go", "observabilidade",
    "monitoring", "automation", "incident", "sre", "devops", "infraestrutura",
    "cloud", "api", "dados", "arquitetura"
]


def get_curriculum_from_drive():
    """Obtém currículo do Drive via Secrets Agent"""
    print("📄 Buscando currículo do Drive...")
    # Simulado - você implementou isso antes
    return """
    Edenilson Teixeira - Experiente em DevOps, Kubernetes, Docker, CI/CD, Python, AWS
    - 8+ anos trabalhando com infraestrutura e automação
    - Experiência com Kubernetes em produção
    - Profundo conhecimento de CI/CD pipelines
    - Python, Go, Bash scripting avançado
    - AWS e infraestrutura como código
    - Incident response e SRE practices
    - Monitoring e observabilidade com Prometheus, Grafana
    """


def get_recommendation_letter():
    """Obtém carta de recomendação (simplificado)"""
    print("📜 Carregando carta de recomendação...")
    return """
    O Sr. Edenilson é um profissional experiente, dedicado, com excelente capacidade de
    resolução de problemas e comunicação. Recomendo fortemente para posições de liderança
    técnica e arquitetura de sistemas.
    """


def calculate_match(job, curriculum):
    """Calcula percentual de match entre vaga e currículo"""
    curriculum_lower = curriculum.lower()
    matched = sum(1 for req in job["requirements"] if req.lower() in curriculum_lower)
    total = len(job["requirements"])
    return int((matched / total) * 100) if total > 0 else 0


def generate_human_email(job, match_score, curriculum, rec_letter):
    """Gera email com tom mais humano e natural"""
    
    subject = f"Candidatura – {job['title']} na {job['company']}"
    
    body = f"""Olá,

Espero que estejam bem! 😊

Encontrei a vaga de {job['title']} na {job['company']} e achei que seria uma ótima oportunidade pra conversar. Tenho bastante experiência com a maioria das tecnologias que vocês mencionam, e adoraria saber mais sobre o projeto.

Um pouco sobre mim:
- Trabalho há mais de 8 anos com infraestrutura, automação e operações
- Tenho experiência sólida com {job['requirements'][0]} e {job['requirements'][1]}
- Sou apaixonado por resolver problemas complexos e melhorar processos

Estou incluindo meu currículo e uma carta de recomendação para você ter mais contexto. Se quiser conversar sobre como posso ajudar o time, fico feliz em bater um papo! ☕

Obrigado pela consideração e fico no aguardo do retorno.

Abraços,
Edenilson Teixeira
(+55) 11 - Disponível para conversa

---
📊 Match Score: {match_score}% com a vaga
"""
    
    return subject, body


def send_draft_email(recipient, subject, body, attachments=None):
    """Envia draft para validação (simula envio real)"""
    print(f"\n📧 Preparando draft para {recipient}...")
    print(f"   Assunto: {subject}")
    print(f"\n{'='*60}")
    print(body)
    print(f"{'='*60}\n")
    
    # Aqui você implantaria o envio real via GMail API
    # Por enquanto, salvamos como draft local
    draft_file = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(draft_file, 'w', encoding='utf-8') as f:
        f.write(f"PARA: {recipient}\n")
        f.write(f"ASSUNTO: {subject}\n")
        f.write(f"DATA: {datetime.now()}\n")
        f.write(f"\n{body}")
    
    print(f"✅ Draft salvo em: {draft_file}")
    return draft_file


def main():
    print("\n🚀 Pipeline de Candidaturas com Tom Humano\n")
    
    # 1. Obter documentos
    curriculum = get_curriculum_from_drive()
    rec_letter = get_recommendation_letter()
    
    # 2. Buscar vagas
    print("🔍 Buscando vagas dos últimos 30 dias...")
    jobs = SAMPLE_JOBS
    
    # 3. Calcular matches
    print(f"🧮 Calculando match com {len(jobs)} vagas...\n")
    high_match_jobs = []
    
    for job in jobs:
        job["match_score"] = calculate_match(job, curriculum)
        status = "✅ APLICAR" if job["match_score"] >= 75 else "❌ Skip"
        print(f"  [{status}] {job['company']} - {job['title']}: {job['match_score']}% match")
        
        if job["match_score"] >= 75:
            high_match_jobs.append(job)
    
    # 4. Gerar e enviar drafts
    if high_match_jobs:
        print(f"\n📬 Preparando {len(high_match_jobs)} email(s) com match > 75%...\n")
        for job in high_match_jobs:
            subject, body = generate_human_email(job, job["match_score"], curriculum, rec_letter)
            draft_file = send_draft_email("edenilson.adm@gmail.com", subject, body)
            print(f"   → Draft criado: {draft_file}\n")
    else:
        print("\n⚠️  Nenhuma vaga com mais de 75% de match encontrada.")


if __name__ == '__main__':
    main()
