#!/usr/bin/env python3
"""
Job Application Agent — Preenche vagas de emprego automaticamente.

Fluxo padrão (com aprovação):
  1. Recebe URL da vaga (Randstad, Gupy, LinkedIn, Workday, etc.)
  2. Extrai descrição e requisitos via scraping
  3. Calcula compatibilidade com o currículo
  4. Gera carta de apresentação personalizada (Ollama)
  5. Preenche o formulário via Playwright (headless)
  6. PARA e mostra screenshots para aprovação do usuário
  7. Só envia após confirmação explícita (s/N)

Uso:
  python job_application_agent.py <URL>                  # preenche e pede aprovação
  python job_application_agent.py <URL> --headed         # idem, com browser visível
  python job_application_agent.py <URL> --auto-submit    # preenche e envia sem pedir
  python job_application_agent.py <URL> --no-browser     # só analisa vaga + gera carta
  python job_application_agent.py <URL> --cover-only     # só gera carta
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

import httpx

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
LOG_DIR = DATA_DIR / "job_applications"
LOG_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

# Currículo consolidado — dados reais (sem exagero)
RESUME = {
    "nome": "Edenilson Teixeira Paschoa",
    "email": "edenilson.adm@gmail.com",
    "telefone": "+55 11 98119-3899",
    "localizacao": "São Paulo, SP",
    "titulo": "DevOps Engineer | SRE | Platform Engineer",
    "resumo": (
        "Profissional de TI com 8+ anos de experiência em infraestrutura, "
        "automação e operações. Forte atuação em observabilidade, CI/CD, "
        "containers e cloud."
    ),
    "experiencia": [
        {
            "empresa": "B3 S.A. (Bolsa, Brasil, Balcão)",
            "cargo": "Analista de Operações / SRE",
            "periodo": "Mar/2022 — Fev/2026",
            "atividades": [
                "AIOps & Observabilidade: detecção pró-ativa, alerting, automação de respostas a anomalias",
                "Pipelines CI/CD: automações de build/deploy, testes, rollbacks e versionamento",
                "Banco de dados / Migrações: Flyway, deploys seguros e rastreáveis",
                "Incidentes: on-call, runbooks, postmortems, redução de MTTR",
                "Modelos LLM: deploy, serving, tuning em produção",
                "Integração de sistemas legados com microserviços via APIs e barramento de mensagens",
                "Datalake & Ingestão: pipeline ETL/ELT, organização de dados",
            ],
        }
    ],
    "skills": {
        "linguagens": ["Python", "Go", "Bash"],
        "containers": ["Docker", "Kubernetes"],
        "cicd": ["GitHub Actions", "GitLab CI", "Jenkins"],
        "iac": ["Terraform", "Ansible"],
        "cloud": ["AWS (EC2, S3, Lambda, EKS)", "GCP (GKE, Cloud Run)"],
        "observabilidade": ["Prometheus", "Grafana", "ELK", "Datadog"],
        "banco_dados": ["PostgreSQL", "Flyway"],
        "outros": [
            "Microsserviços", "REST APIs", "Arquitetura orientada a eventos",
            "SOLID", "Design Patterns", "Clean Architecture",
            "Incident Response", "Postmortems", "Git", "Jira", "Confluence",
        ],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def call_ollama(prompt: str, temperature: float = 0.4, max_tokens: int = 1024) -> str:
    """Chama Ollama local para geração de texto."""
    try:
        resp = httpx.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        log(f"⚠ Ollama indisponível ({e}), usando template padrão")
        return ""


# ---------------------------------------------------------------------------
# Scraper — extrai descrição de vagas de múltiplas plataformas
# ---------------------------------------------------------------------------
@dataclass
class JobInfo:
    titulo: str = ""
    empresa: str = ""
    localizacao: str = ""
    descricao: str = ""
    requisitos: list[str] = field(default_factory=list)
    url: str = ""
    plataforma: str = ""
    modelo_contrato: str = ""


def _clean_html(raw: str) -> str:
    """Remove tags HTML e decodifica entidades."""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"<li>", "\n• ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _resolve_url(url: str) -> str:
    """Segue redirects para obter a URL final."""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        return str(resp.url)
    except Exception:
        return url


def scrape_job(url: str) -> JobInfo:
    """Extrai informação da vaga a partir da URL."""
    final_url = _resolve_url(url)
    log(f"📄 URL final: {final_url}")

    parsed = urlparse(final_url)
    domain = parsed.netloc.lower()

    try:
        resp = httpx.get(final_url, follow_redirects=True, timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        page = resp.text
    except Exception as e:
        log(f"❌ Falha ao acessar URL: {e}")
        return JobInfo(url=final_url, plataforma="desconhecida")

    job = JobInfo(url=final_url)

    # --- Randstad eTalent ---
    if "randstad" in domain:
        job.plataforma = "Randstad"
        # Título
        m = re.search(r"<title>\s*(.*?)\s*</title>", page, re.I | re.S)
        if m:
            t = _clean_html(m.group(1))
            t = re.sub(r"^Convite\s*-\s*", "", t)
            job.titulo = t

        # og:description tem o início da descrição
        m = re.search(r"og:description.*?content=['\"](.+?)['\"]", page, re.I | re.S)

        # Descrição completa (dentro do HTML)
        m = re.search(
            r"Detalhes:\s*</span>(.*?)(?=<span[^>]*>Declaro|<div[^>]*id=.*TermsLink)",
            page, re.I | re.S,
        )
        if m:
            raw_desc = m.group(1)
            job.descricao = _clean_html(raw_desc)

        # Requisitos (lista <li>)
        reqs = re.findall(r"<li>(.*?)</li>", page, re.I | re.S)
        job.requisitos = [_clean_html(r) for r in reqs]

        # Empresa (dica no texto)
        if "argentina" in page.lower() and "comércio eletrônico" in _clean_html(page).lower():
            job.empresa = "Mercado Livre"
        else:
            m2 = re.search(r"class=['\"]Text_Note['\"][^>]*>([^<]+)</", page)
            if m2:
                job.empresa = _clean_html(m2.group(1))

        # Local
        m_local = re.search(r"Local de atua.{1,5}o:\s*([^<\n]+)", _clean_html(page))
        if m_local:
            job.localizacao = m_local.group(1).strip()

        # Modelo
        m_modelo = re.search(r"Atua.{1,5}o:\s*([^<\n]+)", _clean_html(page))
        if m_modelo:
            job.modelo_contrato = m_modelo.group(1).strip()

    # --- Gupy ---
    elif "gupy" in domain:
        job.plataforma = "Gupy"
        m = re.search(r"<title>(.*?)</title>", page, re.I)
        if m:
            job.titulo = _clean_html(m.group(1))
        m = re.search(r'"description"\s*:\s*"(.*?)"', page)
        if m:
            job.descricao = _clean_html(m.group(1))

    # --- LinkedIn ---
    elif "linkedin" in domain:
        job.plataforma = "LinkedIn"
        m = re.search(r"<title>(.*?)</title>", page, re.I)
        if m:
            job.titulo = _clean_html(m.group(1))
        m = re.search(r'class="description__text.*?">(.*?)</section>', page, re.I | re.S)
        if m:
            job.descricao = _clean_html(m.group(1))

    # --- Genérico ---
    else:
        job.plataforma = "outro"
        m = re.search(r"<title>(.*?)</title>", page, re.I)
        if m:
            job.titulo = _clean_html(m.group(1))
        job.descricao = _clean_html(page[:5000])

    return job


# ---------------------------------------------------------------------------
# Compatibilidade
# ---------------------------------------------------------------------------
def calculate_compatibility(job: JobInfo) -> dict:
    """Calcula score de compatibilidade currículo × vaga (só termos técnicos)."""
    # Skills do candidato normalizadas
    all_skills = set()
    for v in RESUME["skills"].values():
        all_skills.update(s.lower() for s in v)

    job_text = (job.descricao + " " + " ".join(job.requisitos)).lower()

    # Apenas termos técnicos relevantes — evita palavras comuns do português
    TECH_TERMS = [
        "java", "golang", "go", "python", "javascript", "typescript",
        "docker", "kubernetes", "k8s", "ci/cd", "cicd", "jenkins",
        "github actions", "gitlab ci", "terraform", "ansible",
        "aws", "gcp", "azure", "prometheus", "grafana", "datadog",
        "kibana", "elk", "new relic", "opsgenie",
        "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq",
        "rest", "api", "microsserviços", "microservices", "microserviços",
        "solid", "design patterns", "clean architecture", "hexagonal",
        "git", "jira", "confluence", "flyway", "linux", "bash", "shell",
        "arquitetura orientada a eventos", "event-driven",
        "orientação a objetos", "oop",
        "bancos de dados", "banco de dados", "sql",
        "observabilidade", "monitoramento", "monitoring",
        "incident response", "on-call", "postmortem",
        "etl", "datalake", "pipeline",
        "llm", "machine learning",
    ]

    matched = []
    missing = []

    for term in TECH_TERMS:
        if term not in job_text:
            continue
        # Verificar se o candidato tem essa skill
        found = False
        for skill in all_skills:
            if term in skill or skill in term:
                found = True
                break
        # Checagens extra para sinônimos
        if not found and term == "golang":
            found = "go" in all_skills
        if not found and term == "go":
            found = any("go" in s for s in all_skills)
        if not found and term in ("microsserviços", "microservices", "microserviços"):
            found = any("microsserviço" in s or "microserviço" in s for s in all_skills)
        if not found and term in ("bancos de dados", "banco de dados", "sql"):
            found = any("postgresql" in s or "flyway" in s for s in all_skills)
        if not found and term in ("orientação a objetos", "oop"):
            found = any("solid" in s or "design pattern" in s for s in all_skills)
        if not found and term == "monitoramento":
            found = any(t in all_skills for t in ["prometheus", "grafana", "datadog", "elk"])
        if not found and term == "observabilidade":
            found = any("prometheus" in s or "grafana" in s or "datadog" in s for s in all_skills)

        if found:
            matched.append(term)
        else:
            missing.append(term)

    total = len(matched) + len(missing) if (matched or missing) else 1
    score = round(len(matched) / total * 100)

    return {
        "score": score,
        "matched": sorted(set(matched)),
        "missing": sorted(set(missing)),
    }


# ---------------------------------------------------------------------------
# Geração de carta de apresentação
# ---------------------------------------------------------------------------
def generate_cover_letter(job: JobInfo, compat: dict) -> str:
    """Gera carta de apresentação personalizada — tom natural, sem exagero."""

    matched_str = ", ".join(compat["matched"][:10]) if compat["matched"] else "infraestrutura e automação"

    prompt = f"""Gere uma carta de apresentação curta e natural (máximo 8 linhas) para a vaga abaixo.
Regras:
- Tom profissional mas humano, NÃO exagerado, SEM bajulação
- NÃO invente experiências ou habilidades que não existem
- NÃO use emojis
- Foque na experiência como DESENVOLVEDOR backend
- NÃO cite o nome de empresas anteriores onde trabalhou
- Mencione 2-3 habilidades técnicas relevantes que o candidato TEM
- Seja direto e objetivo
- Escreva em português do Brasil
- NÃO use "Prezados" — comece com "Olá" ou o nome do recrutador se disponível

Candidato: {RESUME['nome']}
Experiência: Desenvolvedor backend com 8+ anos, experiência com {matched_str}
Skills matched: {matched_str}

Vaga: {job.titulo}
Empresa: {job.empresa or 'não informada'}
Descrição resumida: {job.descricao[:500] if job.descricao else 'não disponível'}

Gere APENAS o texto da carta, sem marcações ou explicações."""

    letter = call_ollama(prompt, temperature=0.5, max_tokens=512)

    # Detectar output ruim — modelo de código gera lixo em texto PT-BR
    # Validação rigorosa: exigir frases completas e sem repetições
    is_bad = True  # Assumir ruim; só aceitar se passar TODAS as checagens
    if letter and len(letter) >= 100:
        has_greeting = any(g in letter[:30].lower() for g in ("olá", "ola", "bom dia", "boa tarde"))
        has_sentences = letter.count(".") >= 3
        words = letter.split()
        avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
        reasonable_words = 2.0 < avg_word_len < 12.0
        no_garbage = (
            letter.count("!") < 4
            and "——" not in letter
            and "<|im_" not in letter
            and "ggg" not in letter
            and not re.search(r"(\w)\1{3,}", letter)  # repetições tipo "gggg", "aaaa"
            and not re.search(r"(—\s*){3,}", letter)  # sequências de traços
            and letter.count(",") < 15  # virgulite
        )
        if has_greeting and has_sentences and no_garbage and reasonable_words:
            is_bad = False
    if is_bad:
        # Fallback com template bem escrito
        empresa_str = f" na {job.empresa}" if job.empresa else ""
        # Foco em desenvolvimento, sem citar empresa anterior
        skills_dev = [s for s in compat["matched"] if s in (
            "go", "golang", "java", "python", "rest", "api", "microsserviços",
            "microservices", "solid", "design patterns", "clean architecture",
            "hexagonal", "arquitetura orientada a eventos", "bancos de dados",
            "git", "docker", "kubernetes",
        )]
        skills_str = ", ".join(skills_dev[:8]) if skills_dev else matched_str
        letter = (
            f"Olá,\n\n"
            f"Vi a vaga de {job.titulo}{empresa_str} e me identifiquei com o perfil.\n\n"
            f"Tenho experiência sólida como desenvolvedor backend, "
            f"com vivência em {skills_str}. "
            f"Atuo há anos em ambientes de alta escala, "
            f"com foco em escalabilidade, qualidade de código e boas práticas.\n\n"
            f"Fico à disposição para conversar sobre a oportunidade.\n\n"
            f"Abraços,\n{RESUME['nome']}\n{RESUME['telefone']}\n{RESUME['email']}"
        )

    # Garante assinatura
    if RESUME["nome"] not in letter:
        letter += f"\n\n{RESUME['nome']}\n{RESUME['telefone']}\n{RESUME['email']}"

    return letter


# ---------------------------------------------------------------------------
# Preenchimento automático via Playwright
# ---------------------------------------------------------------------------
def fill_randstad_form(
    url: str,
    job: JobInfo,
    cover_letter: str,
    *,
    headed: bool = False,
    auto_submit: bool = False,
) -> bool:
    """Preenche formulário da Randstad eTalent via Playwright.

    Por padrão, preenche tudo e para para aprovação do usuário.
    Com --auto-submit, envia automaticamente sem esperar.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("❌ Playwright não instalado. Execute: pip install playwright && playwright install chromium")
        return False

    log("🌐 Iniciando Playwright...")
    success = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            log("📄 Acessando página da vaga...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Screenshot inicial
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            ss_dir = LOG_DIR / ts
            ss_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(ss_dir / "01_pagina_vaga.png"), full_page=True)
            log(f"📸 Screenshot salvo em {ss_dir}/01_pagina_vaga.png")

            # Aceitar termos
            checkboxes = page.locator("input[type='checkbox']")
            count = checkboxes.count()
            log(f"☑ Encontrados {count} checkboxes")

            for i in range(count):
                cb = checkboxes.nth(i)
                if not cb.is_checked():
                    cb.check(force=True)
                    log(f"  ✓ Checkbox {i+1} marcado")
                    time.sleep(0.5)

            page.screenshot(path=str(ss_dir / "02_termos_aceitos.png"))

            # Clicar em "Se inscrever" para avançar ao formulário
            _click_apply_button(page)
            time.sleep(3)
            page.screenshot(path=str(ss_dir / "03_formulario.png"))
            log("📸 Screenshot do formulário salvo")

            # Preencher campos do formulário de cadastro
            current_url = page.url
            log(f"📍 URL atual: {current_url}")
            _try_fill_registration(page, cover_letter, ss_dir)

            # Screenshot final com tudo preenchido
            page.screenshot(path=str(ss_dir / "05_pronto_para_envio.png"), full_page=True)
            log(f"📸 Screenshot final: {ss_dir}/05_pronto_para_envio.png")

            # ---- PONTO DE APROVAÇÃO ----
            if auto_submit:
                log("🚀 Auto-submit ativado — enviando...")
                _click_final_submit(page)
                time.sleep(3)
                page.screenshot(path=str(ss_dir / "06_enviado.png"), full_page=True)
                log("✅ Formulário enviado automaticamente!")
                success = True
            else:
                # Parar e aguardar aprovação do usuário
                _save_session_log(ss_dir, job, cover_letter)
                log("")
                log("═" * 50)
                log("  🔍 FORMULÁRIO PREENCHIDO — AGUARDANDO APROVAÇÃO")
                log("═" * 50)
                log(f"  Screenshots: {ss_dir}/")
                log(f"  Carta:       {ss_dir}/carta_apresentacao.txt")
                log("")

                if headed:
                    # Browser visível — usuário pode ver e aprovar
                    log("  O navegador está aberto para revisão.")
                    log("  Após conferir, responda aqui:")
                else:
                    log("  Confira os screenshots na pasta acima.")
                    log("  Após conferir, responda aqui:")

                log("")
                resp = input("  Enviar candidatura? [s/N]: ").strip().lower()

                if resp in ("s", "sim", "y", "yes"):
                    log("🚀 Aprovado! Enviando...")
                    _click_final_submit(page)
                    time.sleep(3)
                    page.screenshot(path=str(ss_dir / "06_enviado.png"), full_page=True)
                    log("✅ Formulário enviado com sucesso!")
                    success = True
                else:
                    log("⏸ Candidatura NÃO enviada (cancelada pelo usuário)")
                    success = False

        except Exception as e:
            log(f"❌ Erro no Playwright: {e}")
            try:
                page.screenshot(path=str(ss_dir / "error.png"))
            except Exception:
                pass
        finally:
            _save_session_log(ss_dir, job, cover_letter)
            browser.close()

    return success


def _click_apply_button(page) -> None:
    """Clica no botão de inscrição/candidatura."""
    submit_btn = page.locator(
        "input[type='submit'], button[type='submit'], "
        "a:has-text('inscrever'), button:has-text('inscrever'), "
        "a:has-text('Apply'), button:has-text('Apply'), "
        "input[value*='inscrever' i], input[value*='candidat' i]"
    ).first

    try:
        submit_btn.click(timeout=5000)
        log("🔘 Botão de inscrição clicado")
    except Exception:
        # Fallback via JavaScript
        page.evaluate("""() => {
            const btns = document.querySelectorAll('input[type=submit], button[type=submit]');
            for (const b of btns) {
                if (b.value && (b.value.toLowerCase().includes('inscrever') ||
                    b.value.toLowerCase().includes('candidat'))) {
                    b.click();
                    return;
                }
            }
            if (btns.length > 0) btns[btns.length-1].click();
        }""")
        log("🔘 Botão clicado via JavaScript")


def _click_final_submit(page) -> None:
    """Clica no botão final de envio do formulário de cadastro."""
    try:
        submit_btn = page.locator(
            "input[type='submit'], button[type='submit'], "
            "button:has-text('enviar'), button:has-text('salvar'), "
            "button:has-text('concluir'), button:has-text('finalizar'), "
            "input[value*='enviar' i], input[value*='salvar' i], "
            "input[value*='concluir' i], input[value*='submit' i]"
        ).first
        submit_btn.click(timeout=5000)
    except Exception:
        page.evaluate("""() => {
            const btns = document.querySelectorAll('input[type=submit], button[type=submit]');
            if (btns.length > 0) btns[btns.length-1].click();
        }""")


def _try_fill_registration(page, cover_letter: str, ss_dir: Path) -> None:
    """Tenta preencher campos de cadastro/registro se o formulário aparecer."""
    fields_map = {
        "nome": RESUME["nome"],
        "name": RESUME["nome"],
        "email": RESUME["email"],
        "e-mail": RESUME["email"],
        "telefone": RESUME["telefone"],
        "phone": RESUME["telefone"],
        "celular": RESUME["telefone"],
    }

    filled = 0
    inputs = page.locator("input[type='text'], input[type='email'], input[type='tel']")
    count = inputs.count()

    for i in range(count):
        inp = inputs.nth(i)
        try:
            placeholder = (inp.get_attribute("placeholder") or "").lower()
            name = (inp.get_attribute("name") or "").lower()
            label_text = ""
            input_id = inp.get_attribute("id") or ""
            if input_id:
                label = page.locator(f"label[for='{input_id}']")
                if label.count() > 0:
                    label_text = label.first.text_content().lower()

            combined = f"{placeholder} {name} {label_text}"

            for key, value in fields_map.items():
                if key in combined:
                    inp.fill(value)
                    log(f"  📝 Preenchido: {key} = {value}")
                    filled += 1
                    break
        except Exception:
            continue

    # Tentar preencher textarea (carta/mensagem)
    textareas = page.locator("textarea")
    if textareas.count() > 0:
        textareas.first.fill(cover_letter)
        log("  📝 Carta de apresentação preenchida")
        filled += 1

    if filled:
        page.screenshot(path=str(ss_dir / "04_campos_preenchidos.png"))
        log(f"📸 {filled} campos preenchidos")
    else:
        log("ℹ Nenhum campo de cadastro detectado nesta página")


def _save_session_log(ss_dir: Path, job: JobInfo, cover_letter: str) -> None:
    """Salva log da sessão de candidatura."""
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "job": asdict(job),
        "cover_letter": cover_letter,
        "candidato": RESUME["nome"],
    }
    log_file = ss_dir / "session.json"
    log_file.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    log(f"💾 Sessão salva em {log_file}")

    # Salvar carta em txt separado para fácil cópia
    cover_file = ss_dir / "carta_apresentacao.txt"
    cover_file.write_text(cover_letter)
    log(f"💾 Carta salva em {cover_file}")


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
def print_report(job: JobInfo, compat: dict, cover_letter: str) -> None:
    """Imprime relatório da candidatura."""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  RELATÓRIO DE CANDIDATURA")
    print(f"{sep}\n")

    print(f"Vaga:       {job.titulo}")
    print(f"Empresa:    {job.empresa or 'não informada'}")
    print(f"Plataforma: {job.plataforma}")
    print(f"Local:      {job.localizacao or 'não informado'}")
    print(f"Modelo:     {job.modelo_contrato or 'não informado'}")
    print(f"URL:        {job.url}")

    print(f"\n--- Compatibilidade: {compat['score']}% ---")
    if compat["matched"]:
        print(f"✓ Match:   {', '.join(compat['matched'])}")
    if compat["missing"]:
        print(f"✗ Faltam:  {', '.join(compat['missing'])}")

    print(f"\n--- Carta de Apresentação ---")
    print(cover_letter)
    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Agent de candidatura a vagas")
    parser.add_argument("url", help="URL da vaga de emprego")
    parser.add_argument("--auto-submit", action="store_true",
                        help="Envia automaticamente sem pedir aprovação")
    parser.add_argument("--headed", action="store_true",
                        help="Abre navegador visível para revisão")
    parser.add_argument("--cover-only", action="store_true",
                        help="Só gera carta de apresentação")
    parser.add_argument("--no-browser", action="store_true",
                        help="Não abre navegador (só analisa)")
    args = parser.parse_args()

    log("🚀 Job Application Agent iniciado")

    # 1. Scrape
    log("📋 Extraindo informações da vaga...")
    job = scrape_job(args.url)

    if not job.titulo:
        log("⚠ Não foi possível extrair título — usando URL como referência")
        job.titulo = args.url

    log(f"   Título: {job.titulo}")
    log(f"   Empresa: {job.empresa or '?'}")
    log(f"   Plataforma: {job.plataforma}")

    # 2. Compatibilidade
    log("📊 Calculando compatibilidade...")
    compat = calculate_compatibility(job)
    log(f"   Score: {compat['score']}%")
    log(f"   Match: {', '.join(compat['matched'][:5])}")
    if compat["missing"]:
        log(f"   Faltam: {', '.join(compat['missing'][:5])}")

    # 3. Carta
    log("✍ Gerando carta de apresentação...")
    cover_letter = generate_cover_letter(job, compat)

    # 4. Relatório
    print_report(job, compat, cover_letter)

    if args.cover_only or args.no_browser:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ss_dir = LOG_DIR / ts
        ss_dir.mkdir(parents=True, exist_ok=True)
        _save_session_log(ss_dir, job, cover_letter)
        log("✅ Concluído (modo somente análise)")
        return

    # 5. Preencher formulário (para para aprovação por padrão)
    log("🌐 Iniciando preenchimento automático...")
    if not args.auto_submit:
        log("ℹ Modo aprovação: o formulário será preenchido e pausará para sua revisão")

    ok = fill_randstad_form(
        args.url, job, cover_letter,
        headed=args.headed,
        auto_submit=args.auto_submit,
    )

    if ok:
        log("✅ Candidatura enviada com sucesso!")
    else:
        log("⏸ Candidatura não enviada — verifique os screenshots e decida")


if __name__ == "__main__":
    main()
