#!/usr/bin/env python3
"""LinkedIn Job Scanner Agent — Busca, filtra e candidata-se a vagas compatíveis.

Pipeline:
  1. Carrega currículo (.docx do Google Drive ou cache local)
  2. Busca vagas no LinkedIn com filtros (remote, keywords)
  3. Calcula compatibilidade contra o currículo
  4. Para vagas compatíveis: abre com Selenium e tenta Easy Apply
  5. Envia notificação via Telegram para cada candidatura

Uso:
  python linkedin_job_scanner.py                    # Busca padrão (remote, skills do CV)
  python linkedin_job_scanner.py --keywords "SRE"   # Keywords customizadas
  python linkedin_job_scanner.py --min-score 70      # Score mínimo (default: 60)
  python linkedin_job_scanner.py --max-apply 5       # Máximo de candidaturas (default: 10)
  python linkedin_job_scanner.py --dry-run           # Apenas mostra vagas, sem candidatar
  python linkedin_job_scanner.py --headed            # Mostra navegador
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
# File handler separado (sem duplicar stdout)
_file_handler = logging.FileHandler("data/linkedin_jobs/scanner.log", mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))
logger = logging.getLogger("linkedin_scanner")
logger.addHandler(_file_handler)

# ─── Constantes ──────────────────────────────────────────────────────────────
DATA_DIR = Path("data/linkedin_jobs")
COOKIES_FILE = DATA_DIR / "linkedin_cookies.json"
APPLIED_FILE = DATA_DIR / "applied_jobs.json"
CV_CACHE = Path("data/curriculo_edenilson.txt")
CV_DOCX = Path("data/curriculo_edenilson.docx")
LAUDO_PDF = Path("data/laudo_medico_pcd.pdf")
REQUERIMENTO_PDF = Path("data/requerimento_necessidades_especiais.pdf")
GDRIVE_TOKENS = Path("specialized_agents/gdrive_tokens/edenilson.adm_at_gmail.com.json")
CV_GDRIVE_ID = "1y2eeV4No2zQD_ezeZCaBZiuswvANF8V3"
RECOMMENDATION_GDRIVE_ID = "1QtcBNL_tZ5y8G5KQhJbF2i9wWY5S18wp"

# Regex para detectar campo de upload de laudo médico / PCD
_LAUDO_UPLOAD_RE = re.compile(
    r"laudo|atestado|m[ée]dico|medical|pcd|defici[eê]ncia|necessidades"
    r"|disabilit|special.?need|cid[- ]|report.?m[ée]d",
    re.IGNORECASE,
)

# Regex para detectar campo de foto/avatar (NÃO anexar CV)
_PHOTO_UPLOAD_RE = re.compile(
    r"photo|foto|picture|imagem|avatar|profile.?pic|selfie|retrato",
    re.IGNORECASE,
)

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "1105143633:AAG5BrfOsGbV88BFztljR7fH5ekmszFnulA",
)
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "948686300"))

MIN_COMPAT_SCORE = 60
MAX_APPLY = 10
LINKEDIN_BASE = "https://www.linkedin.com"
SEARCH_DELAY = 2.0  # Delay entre ações para evitar rate limit
PAGE_LOAD_TIMEOUT = 30
JOB_APPLY_TIMEOUT = 90  # Timeout máximo (segundos) por candidatura individual

# ─── Pretensão Salarial Dinâmica (CLT mensal BRL) ────────────────────────────
# Faixas base por nível de senioridade (min, max)
SALARY_RANGES: dict[str, tuple[float, float]] = {
    "junior":       (4000.0,   7000.0),
    "pleno":        (8000.0,  14000.0),
    "senior":       (14000.0, 22000.0),
    "especialista": (18000.0, 28000.0),
    "lead":         (20000.0, 30000.0),
    "manager":      (22000.0, 35000.0),
    "director":     (30000.0, 45000.0),
    "default":      (14000.0, 20000.0),  # 15+ anos exp → assume sênior
}

# Multiplicadores por categoria de cargo (sobre a faixa base)
SALARY_CATEGORY_MULTIPLIER: dict[str, float] = {
    "sre":          1.15,   # SRE/Reliability paga mais
    "devops":       1.10,   # DevOps acima da média
    "platform":     1.12,   # Platform Engineer
    "architect":    1.20,   # Arquiteto de soluções
    "data":         1.08,   # Data Engineer
    "backend":      1.00,   # Backend padrão
    "fullstack":    0.95,   # Fullstack levemente abaixo
    "frontend":     0.92,   # Frontend
    "rpa":          0.95,   # RPA Developer
    "qa":           0.88,   # QA/Test
    "default":      1.00,
}

# ─── Filtros de vaga ─────────────────────────────────────────────────────────
# Vagas exclusivas para mulheres — excluir
EXCLUDE_WOMEN_ONLY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(afirmativ[ao]s?\s+(para|p/)\s*mulher)", re.IGNORECASE),
    re.compile(r"\bvaga\s+(exclusiva|afirmativa)\s+(para|p/)\s*mulher", re.IGNORECASE),
    re.compile(r"\b(exclusiv[ao]\s+para\s+mulher)", re.IGNORECASE),
    re.compile(r"\bwomen\s+only\b", re.IGNORECASE),
    re.compile(r"\b(apenas|somente)\s+(para\s+)?mulher", re.IGNORECASE),
]

# Níveis aceitos — PLENO e SÊNIOR apenas (excluir júnior/estagiário)
ACCEPTED_LEVELS: list[re.Pattern[str]] = [
    re.compile(r"\b(pleno|mid[- ]?level|mid|intermediário|intermedi[aá]rio)\b", re.IGNORECASE),
    re.compile(r"\b(s[eê]nior|senior|sr\.?|s[eê]nior|lead|principal|staff)\b", re.IGNORECASE),
    re.compile(r"\b(especialista|coordenador[a]?|gerente|manager|head|director)\b", re.IGNORECASE),
]

REJECTED_LEVELS: list[re.Pattern[str]] = [
    re.compile(r"\b(j[uú]nior|junior|jr\.?|est[aá]gi[oá]ri[oa]?|estagi[aá]ri[oa]?|trainee|aprendiz)\b", re.IGNORECASE),
]

# ─── Dados do currículo (extraído do .docx) ──────────────────────────────────
RESUME = {
    "nome": "Edenilson Teixeira Paschoa",
    "email": "edenilson.adm@gmail.com",
    "telefone": "+55 11 98119-3899",
    "localizacao": "Jundiaí, SP",
    "titulo": "Analista de Operações / SRE | Software Engineer | DevOps",
    "resumo": (
        "Profissional de TI com 15+ anos de experiência. "
        "Atuação em SRE/DevOps na B3, Software Engineer no Mercado Livre, "
        "e liderança de equipes RPA em grandes consultorias. "
        "Experiência sólida em automação, observabilidade, CI/CD, "
        "containers e cloud."
    ),
    "skills": {
        "linguagens": ["Python", "Go", "Java", "Bash", "C#", "COBOL", "VBA", "SQL"],
        "containers": ["Docker", "Kubernetes"],
        "cicd": ["GitHub Actions", "GitLab CI", "Jenkins"],
        "iac": ["Terraform", "Ansible"],
        "cloud": ["AWS", "GCP"],
        "observabilidade": ["Prometheus", "Grafana", "ELK", "Datadog", "Splunk",
                           "New Relic"],
        "banco_dados": ["PostgreSQL", "Oracle", "DB2", "MongoDB"],
        "rpa": ["Automation Anywhere", "UIPath", "Blue Prism", "Selenium"],
        "frameworks": ["Spring Boot", "FastAPI", "JavaEE"],
        "metodologias": ["SCRUM", "Agile", "SOLID", "Design Patterns",
                        "Clean Architecture", "Hexagonal"],
        "outros": ["Microsserviços", "REST APIs", "Arquitetura orientada a eventos",
                   "AIOps", "LLM", "ETL", "Flyway", "Git", "Jira", "Confluence",
                   "SharePoint", "SAS"],
    },
    "cargos_interesse": [
        "Analista de Sistemas",
        "Software Engineer",
        "SRE",
        "DevOps Engineer",
        "Platform Engineer",
        "Backend Developer",
        "Programador",
        "Cientista de Dados",
        "RPA Developer",
        "Automação",
    ],
    "experiencia_empresas": [
        "B3 S.A. (Bolsa, Brasil, Balcão)",
        "Mercado Livre",
        "BRQ",
        "Indra",
        "Deloitte",
        "Certsys",
        "Accenture/Avanade/Microsoft",
        "Itaú-Unibanco",
    ],
    "pcd": True,
}

# Termos técnicos para matching (lowercase)
TECH_TERMS: set[str] = set()
for _cat in RESUME["skills"].values():
    for _skill in _cat:
        TECH_TERMS.add(_skill.lower())
        # Adicionar variações
        if "(" in _skill:
            base = _skill.split("(")[0].strip().lower()
            TECH_TERMS.add(base)

# Keywords de busca derivadas do currículo
DEFAULT_SEARCH_KEYWORDS = [
    "SRE",
    "DevOps",
    "Software Engineer Backend",
    "Analista de Sistemas",
    "Platform Engineer",
    "Python Developer",
    "Site Reliability Engineer",
    "RPA Developer",
    "Automação Processos",
]


# ─── Dataclasses ─────────────────────────────────────────────────────────────
@dataclass
class LinkedInJob:
    """Representa uma vaga encontrada no LinkedIn."""

    job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    is_remote: bool = False
    is_easy_apply: bool = False
    posted_time: str = ""
    compatibility_score: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    applied: bool = False
    applied_at: str = ""


# ─── Telegram ────────────────────────────────────────────────────────────────
async def send_telegram(text: str, parse_mode: str = "Markdown") -> bool:
    """Envia mensagem via Telegram Bot API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": text[:4096],
                    "parse_mode": parse_mode,
                },
            )
            if resp.status_code == 200:
                logger.info("📱 Telegram: mensagem enviada")
                return True
            logger.warning(f"📱 Telegram: HTTP {resp.status_code}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"📱 Telegram erro: {e}")
        return False


async def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """Envia foto via Telegram Bot API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(photo_path, "rb") as f:
                resp = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]},
                    files={"photo": f},
                )
            return resp.status_code == 200
    except (httpx.HTTPError, FileNotFoundError) as e:
        logger.error(f"📱 Telegram foto erro: {e}")
        return False


# ─── Google Drive ────────────────────────────────────────────────────────────
def download_cv_from_drive() -> str:
    """Baixa currículo do Google Drive e retorna texto extraído."""
    if CV_CACHE.exists():
        logger.info(f"📄 Currículo em cache: {CV_CACHE}")
        return CV_CACHE.read_text(encoding="utf-8")

    if not GDRIVE_TOKENS.exists():
        logger.warning("⚠️ Tokens Google Drive não encontrados")
        return ""

    try:
        import io

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        with open(GDRIVE_TOKENS, encoding="utf-8") as f:
            data = json.load(f)

        creds = Credentials(
            token=data.get("token"),
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes") or ["https://www.googleapis.com/auth/drive"],
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        # Download .docx
        req = service.files().get_media(fileId=CV_GDRIVE_ID)
        fh = io.BytesIO()
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = dl.next_chunk()

        CV_DOCX.parent.mkdir(parents=True, exist_ok=True)
        CV_DOCX.write_bytes(fh.getvalue())
        logger.info(f"📥 CV baixado do Drive: {len(fh.getvalue())} bytes")

        # Converter para texto
        from docx import Document

        doc = Document(str(CV_DOCX))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        CV_CACHE.write_text(text, encoding="utf-8")
        return text

    except ImportError as e:
        logger.error(f"❌ Dependência faltando: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ Erro ao baixar CV do Drive: {e}")
        return ""


# ─── Compatibilidade ────────────────────────────────────────────────────────
def filter_job_eligibility(job: LinkedInJob) -> tuple[bool, str]:
    """Filtra vagas por elegibilidade: nível e exclusividade.

    Returns:
        (eligible, reason): True se elegível, ou (False, motivo).
    """
    job_text = f"{job.title} {job.description}"

    # 1. Excluir vagas afirmativas exclusivas para mulheres
    for pattern in EXCLUDE_WOMEN_ONLY_PATTERNS:
        if pattern.search(job_text):
            return False, "Vaga afirmativa exclusiva para mulheres"

    # 2. Excluir vagas júnior/estagiário
    title_lower = job.title.lower()
    for pattern in REJECTED_LEVELS:
        if pattern.search(title_lower):
            # Verificar se não tem também pleno/sênior no título (ex: "Jr/Pleno")
            has_accepted = any(p.search(title_lower) for p in ACCEPTED_LEVELS)
            if not has_accepted:
                return False, f"Nível rejeitado (júnior/estagiário): {job.title}"

    # 3. Se o título menciona nível aceito, OK
    # Se não menciona nível nenhum, aceitar (muitas vagas não informam nível)
    return True, ""


def calculate_salary_expectation(job: "LinkedInJob") -> str:
    """Calcula pretensão salarial baseada no cargo, nível e match de skills.

    Retorna valor numérico como string (ex: '18000') para campos de formulário
    que exigem decimal. Cálculo considera:
    - Nível de senioridade extraído do título
    - Categoria do cargo (SRE paga mais que Frontend, etc.)
    - Score de compatibilidade (match alto → pedir mais, baixo → pedir menos)
    """
    title_lower = job.title.lower()

    # 1. Detectar nível de senioridade
    level = "default"
    level_patterns: list[tuple[str, str]] = [
        (r"\b(director|diretor|vp|vice)\b", "director"),
        (r"\b(manager|gerente|head|coordenador)\b", "manager"),
        (r"\b(lead|l[ií]der|tech.?lead|principal|staff)\b", "lead"),
        (r"\b(especialista|specialist|expert)\b", "especialista"),
        (r"\b(s[eê]nior|senior|sr\.?)\b", "senior"),
        (r"\b(pleno|mid[- ]?level|mid|intermedi[aá]rio)\b", "pleno"),
        (r"\b(j[uú]nior|junior|jr\.?)\b", "junior"),
    ]
    for pattern, lvl in level_patterns:
        if re.search(pattern, title_lower, re.IGNORECASE):
            level = lvl
            break

    # 2. Detectar categoria do cargo
    category = "default"
    category_patterns: list[tuple[str, str]] = [
        (r"architect|arquitet", "architect"),
        (r"\b(sre|site.?reliab|reliability)\b", "sre"),
        (r"\b(devops|dev.?ops|infra)\b", "devops"),
        (r"\b(platform|plataforma)\b", "platform"),
        (r"\b(data.?engineer|dados|data.?science|etl)\b", "data"),
        (r"\b(full.?stack|fullstack)\b", "fullstack"),
        (r"\b(front.?end|frontend|react|angular|vue)\b", "frontend"),
        (r"\b(back.?end|backend|api)\b", "backend"),
        (r"\b(rpa|automa[çc][ãa]o|automation)\b", "rpa"),
        (r"\b(qa|quality|test|qualidade)\b", "qa"),
    ]
    for pattern, cat in category_patterns:
        if re.search(pattern, title_lower, re.IGNORECASE):
            category = cat
            break

    # 3. Obter faixa base
    salary_min, salary_max = SALARY_RANGES.get(level, SALARY_RANGES["default"])

    # 4. Aplicar multiplicador de categoria
    cat_mult = SALARY_CATEGORY_MULTIPLIER.get(category, 1.0)
    salary_min *= cat_mult
    salary_max *= cat_mult

    # 5. Posicionar dentro da faixa baseado no score de compatibilidade
    # Score alto (90%+) → pedir no topo da faixa (confiança alta)
    # Score médio (70-90%) → pedir no meio-alto (75% da faixa)
    # Score baixo (<70%) → pedir no piso (ser competitivo)
    score = job.compatibility_score
    if score >= 90:
        position = 0.85  # 85% da faixa (topo, mas não máximo absoluto)
    elif score >= 80:
        position = 0.70  # 70% da faixa
    elif score >= 70:
        position = 0.55  # Meio-alto
    else:
        position = 0.35  # Piso competitivo

    salary = salary_min + (salary_max - salary_min) * position

    # 6. Arredondar para centenas (mais natural)
    salary = round(salary / 100) * 100

    # 7. Garantir mínimo razoável para 15+ anos de experiência
    salary = max(salary, 10000)

    logger.info(
        f"   💰 Pretensão: R$ {salary:,.0f}/mês "
        f"(nível={level}, cat={category}, mult={cat_mult:.2f}, "
        f"score={score}%, pos={position:.0%})"
    )
    return str(int(salary))


def calculate_compatibility(job: LinkedInJob) -> dict:
    """Calcula score de compatibilidade entre a vaga e o currículo."""
    job_text = f"{job.title} {job.description} {job.company}".lower()

    # Extrair termos técnicos da vaga
    job_terms: set[str] = set()
    for term in TECH_TERMS:
        # Busca por palavra completa
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, job_text, re.IGNORECASE):
            job_terms.add(term)

    # Sinônimos e variações
    synonyms = {
        "golang": "go", "go": "golang",
        "k8s": "kubernetes", "kubernetes": "k8s",
        "postgres": "postgresql", "postgresql": "postgres",
        "ci/cd": "github actions", "cicd": "github actions",
        "microservices": "microsserviços", "microsserviços": "microservices",
        "aws": "cloud", "gcp": "cloud", "azure": "cloud",
        "elk": "elasticsearch", "elasticsearch": "elk",
        "spring": "spring boot", "spring boot": "spring",
        "terraform": "iac", "ansible": "iac",
        "docker": "containers", "containers": "docker",
    }

    # Verificar sinônimos na vaga
    extra_terms: set[str] = set()
    for term in list(job_terms):
        if term in synonyms:
            syn = synonyms[term]
            if syn.lower() in TECH_TERMS:
                extra_terms.add(syn.lower())
    job_terms.update(extra_terms)

    # Verificar termos adicionais por regex
    additional_patterns = {
        "python": r"\bpython\b",
        "java": r"\bjava\b(?!script)",
        "go": r"\bgo(?:lang)?\b",
        "devops": r"\bdevops\b",
        "sre": r"\bsre\b",
        "docker": r"\bdocker\b",
        "kubernetes": r"\bkubernetes|k8s\b",
        "terraform": r"\bterraform\b",
        "ansible": r"\bansible\b",
        "aws": r"\baws\b",
        "gcp": r"\bgcp|google cloud\b",
        "ci/cd": r"\bci/?cd\b",
        "rest": r"\brest\s*api|restful\b",
        "sql": r"\bsql\b",
        "grafana": r"\bgrafana\b",
        "prometheus": r"\bprometheus\b",
        "datadog": r"\bdatadog\b",
        "jenkins": r"\bjenkins\b",
        "git": r"\bgit(?:hub|lab)?\b",
        "agile": r"\bagile|scrum\b",
        "microsserviços": r"\bmicro\s*servi[cç]os?\b",
        "spring boot": r"\bspring\s*boot\b",
        "selenium": r"\bselenium\b",
        "rpa": r"\brpa\b",
    }

    for term, pattern in additional_patterns.items():
        if re.search(pattern, job_text, re.IGNORECASE):
            job_terms.add(term)

    # Match com skills do currículo
    all_cv_skills: set[str] = set()
    for cat_skills in RESUME["skills"].values():
        for skill in cat_skills:
            all_cv_skills.add(skill.lower())

    matched = job_terms & all_cv_skills
    only_job = job_terms - all_cv_skills

    # Score: % de requisitos da vaga que o candidato atende
    if not job_terms:
        score = 50.0  # Sem info técnica = score neutro
    elif len(job_terms) <= 2:
        # Poucos termos detectados → score mais conservador
        base = (len(matched) / len(job_terms)) * 100
        score = base * 0.6  # Penaliza vagas vagas demais
    else:
        score = (len(matched) / len(job_terms)) * 100

    # Bônus por cargo-alvo
    for cargo in RESUME["cargos_interesse"]:
        if cargo.lower() in job.title.lower():
            score = min(100.0, score + 10)
            break

    # Bônus PCD
    if RESUME.get("pcd") and re.search(r"\bpcd|defici[eê]ncia\b", job_text, re.IGNORECASE):
        score = min(100.0, score + 15)

    # Bônus remote
    if job.is_remote:
        score = min(100.0, score + 5)

    return {
        "score": round(score, 1),
        "matched": sorted(matched),
        "missing": sorted(only_job),
    }


# ─── Selenium Driver ────────────────────────────────────────────────────────
def _kill_existing_chrome() -> None:
    """Mata processos Chrome/ChromeDriver existentes antes de abrir nova instância."""
    for proc_name in ("chrome", "chromedriver"):
        try:
            result = subprocess.run(
                ["pkill", "-f", proc_name],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                logger.info(f"🔪 Processos '{proc_name}' encerrados")
        except Exception:
            pass
    time.sleep(1)  # Aguardar processos morrerem


def create_driver(headed: bool = False, chrome_profile: bool = False) -> webdriver.Chrome:
    """Cria instância do Chrome WebDriver com configurações otimizadas.

    Mata processos Chrome existentes antes de criar nova instância.

    Args:
        headed: Se True, mostra o navegador.
        chrome_profile: Se True, usa perfil Chrome do usuário (herda sessão logada).
    """
    _kill_existing_chrome()
    options = Options()
    if not headed:
        options.add_argument("--headless=new")

    if chrome_profile:
        # Usar perfil padrão do Chrome — herda sessão logada no LinkedIn
        chrome_user_data = Path.home() / ".config" / "google-chrome"
        if chrome_user_data.exists():
            options.add_argument(f"--user-data-dir={chrome_user_data}")
            options.add_argument("--profile-directory=Default")
            logger.info(f"🔑 Usando perfil Chrome: {chrome_user_data}")
        else:
            logger.warning("⚠️ Perfil Chrome não encontrado, usando perfil temporário")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--shm-size=2g")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    )
    # Desabilitar webdriver detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Fallback: usar cache local se rede falhar
    try:
        driver_path = ChromeDriverManager().install()
    except Exception:
        import glob
        cached = sorted(
            glob.glob(str(Path.home() / ".wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver")),
            reverse=True,
        )
        if cached:
            driver_path = cached[0]
            logger.warning(f"Rede indisponível — usando chromedriver cache: {driver_path}")
        else:
            raise RuntimeError("ChromeDriver não encontrado: rede offline e sem cache local")
    service = Service(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()
    driver.implicitly_wait(0)  # Usar WebDriverWait explícito — implicit wait causa cascata de 5s/seletor
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    # Esconder webdriver flag
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    return driver


def save_cookies(driver: webdriver.Chrome) -> None:
    """Salva cookies do LinkedIn para reutilizar sessão."""
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    cookies = driver.get_cookies()
    COOKIES_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    logger.info(f"🍪 {len(cookies)} cookies salvos em {COOKIES_FILE}")


def load_cookies(driver: webdriver.Chrome) -> bool:
    """Carrega cookies salvos para restaurar sessão LinkedIn."""
    if not COOKIES_FILE.exists():
        return False

    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        driver.get(f"{LINKEDIN_BASE}/404")
        time.sleep(1)
        for cookie in cookies:
            # Remover campos que podem causar erro
            for key in ["sameSite", "expiry"]:
                cookie.pop(key, None)
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        logger.info(f"🍪 {len(cookies)} cookies carregados")
        return True
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning(f"⚠️ Erro ao carregar cookies: {e}")
        return False


def linkedin_login(driver: webdriver.Chrome) -> bool:
    """Faz login no LinkedIn via Selenium.

    Tenta em ordem:
    1. Restaurar sessão via cookies salvos
    2. Login automático via LINKEDIN_EMAIL + LINKEDIN_PASSWORD (env vars)
    3. Login manual (aguarda interação no browser headed)
    """
    def _safe_navigate(url: str) -> bool:
        """Navega para URL com tratamento de timeout."""
        for attempt in range(2):
            try:
                driver.get(url)
                return True
            except Exception as nav_e:
                logger.warning(f"⚠️ Timeout ao navegar ({attempt + 1}/2): {nav_e}")
                time.sleep(3)
                # Verificar se a página carregou parcialmente
                try:
                    if "/feed" in driver.current_url or "/mynetwork" in driver.current_url:
                        return True
                except Exception:
                    pass
        return False

    # 1. Tentar restaurar sessão via cookies
    if load_cookies(driver):
        if _safe_navigate(f"{LINKEDIN_BASE}/feed/"):
            time.sleep(3)
            if "/feed" in driver.current_url:
                logger.info("✅ Sessão LinkedIn restaurada via cookies")
                return True
        logger.warning("⚠️ Cookies expirados, tentando outro método")

    # 2. Verificar se já está logado (perfil Chrome)
    if _safe_navigate(f"{LINKEDIN_BASE}/feed/"):
        time.sleep(3)
        if "/feed" in driver.current_url:
            logger.info("✅ Sessão LinkedIn detectada via perfil Chrome")
            save_cookies(driver)
            return True

    # 3. Login automático com credenciais via env vars
    linkedin_email = os.environ.get("LINKEDIN_EMAIL", "")
    linkedin_password = os.environ.get("LINKEDIN_PASSWORD", "")

    if linkedin_email and linkedin_password:
        logger.info(f"🔑 Login automático com {linkedin_email[:5]}***")
        _safe_navigate(f"{LINKEDIN_BASE}/login")
        time.sleep(2)

        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.clear()
            email_field.send_keys(linkedin_email)
            time.sleep(0.5)

            pass_field = driver.find_element(By.ID, "password")
            pass_field.clear()
            pass_field.send_keys(linkedin_password)
            time.sleep(0.5)

            submit_btn = driver.find_element(
                By.CSS_SELECTOR, "button[type='submit']"
            )
            submit_btn.click()
            time.sleep(5)

            # Verificar se login foi bem-sucedido
            if "/feed" in driver.current_url or "/mynetwork" in driver.current_url:
                logger.info("✅ Login automático bem-sucedido!")
                save_cookies(driver)
                return True

            # Pode ter reCAPTCHA ou verificação 2FA
            logger.warning("⚠️ Login automático redirecionou — possível 2FA/CAPTCHA")
            logger.info("   Aguardando resolução manual (120s)...")

            for i in range(120):
                time.sleep(1)
                if "/feed" in driver.current_url or "/mynetwork" in driver.current_url:
                    logger.info("✅ Login detectado após verificação!")
                    save_cookies(driver)
                    return True
                if i % 15 == 14:
                    logger.info(f"   ⏳ Aguardando verificação... ({i + 1}s)")

        except Exception as e:
            logger.warning(f"⚠️ Erro no login automático: {e}")

    # 4. Login manual — abrir página e aguardar
    driver.get(f"{LINKEDIN_BASE}/login")
    time.sleep(2)

    logger.info("🔑 Aguardando login manual no LinkedIn...")
    logger.info("   → Faça login no navegador aberto")
    logger.info("   → O script continuará automaticamente após detectar o feed")

    # Enviar notificação Telegram para avisar que precisa de login
    try:
        import asyncio as _aio
        _aio.get_event_loop().run_until_complete(
            send_telegram(
                "🔑 *LinkedIn Scanner*: Aguardando login manual no LinkedIn!\n"
                "Abra o navegador Chrome e faça login.\n"
                "Timeout: 5 minutos."
            )
        )
    except Exception:
        pass

    # Aguardar até 300 segundos para o login (5 minutos)
    for i in range(300):
        time.sleep(1)
        current = driver.current_url
        if "/feed" in current or "/mynetwork" in current:
            logger.info("✅ Login LinkedIn detectado!")
            save_cookies(driver)
            return True
        if i % 15 == 14:
            logger.info(f"   ⏳ Aguardando login... ({i + 1}s)")

    logger.error("❌ Timeout aguardando login no LinkedIn")
    return False


# ─── Busca de Vagas (API pública, sem login) ─────────────────────────────────
async def search_linkedin_jobs_public(
    keywords: list[str],
    remote_only: bool = True,
    max_results: int = 50,
) -> list[LinkedInJob]:
    """Busca vagas no LinkedIn via páginas públicas (sem login)."""
    all_jobs: list[LinkedInJob] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(
        timeout=30.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
        },
        follow_redirects=True,
    ) as client:
        for keyword in keywords:
            logger.info(f"🔍 Buscando: '{keyword}'...")

            # LinkedIn public jobs API
            params = {
                "keywords": keyword,
                "location": "Brasil",
                "geoId": "106057199",
                "f_TPR": "r86400",  # Últimas 24 horas — vagas frescas
                "position": "1",
                "pageNum": "0",
                "start": "0",
            }
            if remote_only:
                params["f_WT"] = "2"  # Remote

            # Usar página pública (acessível sem login)
            search_url = f"{LINKEDIN_BASE}/jobs-guest/jobs/api/seeMoreJobPostings/search"

            # Paginar: 2 páginas de 25 resultados por keyword
            for page_start in [0, 25]:
                if len(all_jobs) >= max_results:
                    break
                params["start"] = str(page_start)

                try:
                    resp = await client.get(search_url, params=params)
                    if resp.status_code != 200:
                        if page_start == 0:
                            logger.warning(f"   ⚠️ HTTP {resp.status_code} para '{keyword}'")
                            # Fallback: tentar página HTML pública
                            jobs_from_page = await _search_public_html(client, keyword, remote_only)
                            for j in jobs_from_page:
                                if j.job_id not in seen_ids:
                                    seen_ids.add(j.job_id)
                                    all_jobs.append(j)
                        break

                    html = resp.text
                    jobs_parsed = _parse_public_html(html)
                    if page_start == 0:
                        logger.info(f"   📋 {len(jobs_parsed)} vagas encontradas")
                    elif jobs_parsed:
                        logger.info(f"   📋 +{len(jobs_parsed)} vagas (página 2)")

                    if not jobs_parsed:
                        break  # Sem mais resultados

                    for job in jobs_parsed:
                        if job.job_id not in seen_ids:
                            seen_ids.add(job.job_id)
                            all_jobs.append(job)

                except httpx.HTTPError as e:
                    logger.warning(f"   ⚠️ Erro HTTP para '{keyword}': {e}")
                    break

                await asyncio.sleep(1)  # Delay entre páginas

            if len(all_jobs) >= max_results:
                break

            await asyncio.sleep(SEARCH_DELAY)

    logger.info(f"📊 Total de vagas encontradas: {len(all_jobs)}")
    return all_jobs[:max_results]


async def _search_public_html(
    client: httpx.AsyncClient,
    keyword: str,
    remote_only: bool,
) -> list[LinkedInJob]:
    """Fallback: busca vagas via página HTML pública do LinkedIn."""
    params = f"keywords={keyword.replace(' ', '%20')}&location=Brasil&geoId=106057199"
    if remote_only:
        params += "&f_WT=2"
    params += "&f_TPR=r86400"

    url = f"{LINKEDIN_BASE}/jobs/search/?{params}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return _parse_public_html(resp.text)
    except httpx.HTTPError:
        pass
    return []


def _parse_public_html(html: str) -> list[LinkedInJob]:
    """Extrai vagas do HTML público do LinkedIn."""
    jobs: list[LinkedInJob] = []

    # Padrão de cards na página pública
    # <div class="base-card ... base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:XXXXX">
    card_pattern = re.compile(
        r'data-entity-urn="urn:li:jobPosting:(\d+)"',
        re.IGNORECASE,
    )

    # Extrair cada card
    for match in card_pattern.finditer(html):
        job_id = match.group(1)
        # Extrair bloco do card (próximos ~2000 chars)
        start = max(0, match.start() - 200)
        end = min(len(html), match.end() + 2000)
        block = html[start:end]

        # Título
        title = ""
        title_match = re.search(
            r'class="base-search-card__title[^"]*"[^>]*>([^<]+)',
            block,
        )
        if title_match:
            title = title_match.group(1).strip()

        # Empresa
        company = ""
        company_match = re.search(
            r'class="hidden-nested-link"[^>]*>([^<]+)',
            block,
        )
        if not company_match:
            company_match = re.search(
                r'class="base-search-card__subtitle[^"]*"[^>]*>\s*<[^>]+>([^<]+)',
                block,
            )
        if company_match:
            company = company_match.group(1).strip()

        # Local
        location = ""
        loc_match = re.search(
            r'class="job-search-card__location[^"]*"[^>]*>([^<]+)',
            block,
        )
        if loc_match:
            location = loc_match.group(1).strip()

        # URL
        url = ""
        url_match = re.search(
            r'href="(https://[^"]*linkedin\.com/jobs/view/[^"]+)"',
            block,
        )
        if url_match:
            url = url_match.group(1).split("?")[0]  # Limpar tracking params

        # Tempo de postagem
        posted = ""
        time_match = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if time_match:
            posted = time_match.group(1)

        is_remote = bool(
            re.search(r"\bremot[eo]|home\s*office|anywhere\b", location, re.IGNORECASE)
            or re.search(r"\bremot[eo]|home\s*office\b", title, re.IGNORECASE)
        )

        if title:
            jobs.append(
                LinkedInJob(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    url=url or f"{LINKEDIN_BASE}/jobs/view/{job_id}",
                    is_remote=is_remote,
                    posted_time=posted,
                )
            )

    return jobs


def search_linkedin_jobs(
    driver: webdriver.Chrome,
    keywords: list[str],
    remote_only: bool = True,
    max_results: int = 50,
) -> list[LinkedInJob]:
    """Busca vagas no LinkedIn usando Selenium (logado)."""
    all_jobs: list[LinkedInJob] = []
    seen_ids: set[str] = set()

    for keyword in keywords:
        logger.info(f"🔍 Buscando (logado): '{keyword}'...")

        params = f"keywords={keyword.replace(' ', '%20')}"
        if remote_only:
            params += "&f_WT=2"
        params += "&location=Brasil&geoId=106057199"
        params += "&f_TPR=r86400"

        search_url = f"{LINKEDIN_BASE}/jobs/search/?{params}"
        driver.get(search_url)
        time.sleep(SEARCH_DELAY + 1)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.5)

        try:
            job_cards = driver.find_elements(
                By.CSS_SELECTOR,
                "div.job-search-card, li.jobs-search-results__list-item, "
                "div.base-card, li.result-card",
            )
            logger.info(f"   📋 {len(job_cards)} cards encontrados")

            for card in job_cards:
                try:
                    job = _parse_job_card(card)
                    if job and job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"   ⚠️ Erro ao extrair vagas para '{keyword}': {e}")

        if len(all_jobs) >= max_results:
            break

        time.sleep(SEARCH_DELAY)

    logger.info(f"📊 Total de vagas encontradas: {len(all_jobs)}")
    return all_jobs[:max_results]


def _parse_job_card(card) -> Optional[LinkedInJob]:
    """Extrai informações de um card de vaga do LinkedIn."""
    try:
        # Tentar diferentes seletores (LinkedIn muda frequentemente)
        title_el = None
        for selector in [
            "h3.base-search-card__title",
            "a.job-card-list__title",
            "h3.job-search-card__title",
            ".job-card-container__link",
            "a[data-control-name='job_card_title']",
        ]:
            els = card.find_elements(By.CSS_SELECTOR, selector)
            if els:
                title_el = els[0]
                break

        if not title_el:
            # Tenta <a> com href /jobs/view/
            links = card.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href") or ""
                if "/jobs/view/" in href:
                    title_el = link
                    break

        if not title_el:
            return None

        title = title_el.text.strip()
        if not title:
            title = title_el.get_attribute("aria-label") or ""
            title = title.strip()

        # URL
        url = ""
        link_el = title_el if title_el.tag_name == "a" else None
        if not link_el:
            links = card.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href") or ""
                if "/jobs/view/" in href:
                    link_el = link
                    break
        if link_el:
            url = link_el.get_attribute("href") or ""

        # Job ID do URL
        job_id = ""
        if url:
            match = re.search(r"/jobs/view/(\d+)", url)
            if match:
                job_id = match.group(1)

        if not job_id:
            data_id = card.get_attribute("data-entity-urn") or ""
            match = re.search(r":(\d+)$", data_id)
            if match:
                job_id = match.group(1)
            else:
                job_id = f"unknown_{hash(title)}"

        # Empresa
        company = ""
        for sel in [
            "h4.base-search-card__subtitle",
            ".job-card-container__primary-description",
            "a.job-card-container__company-name",
            ".base-search-card__subtitle",
        ]:
            els = card.find_elements(By.CSS_SELECTOR, sel)
            if els:
                company = els[0].text.strip()
                break

        # Local
        location = ""
        for sel in [
            "span.job-search-card__location",
            ".job-card-container__metadata-item",
            ".base-search-card__metadata",
        ]:
            els = card.find_elements(By.CSS_SELECTOR, sel)
            if els:
                location = els[0].text.strip()
                break

        is_remote = bool(
            re.search(r"\bremot[eo]|home\s*office|anywhere\b", location, re.IGNORECASE)
            or re.search(r"\bremot[eo]|home\s*office\b", title, re.IGNORECASE)
        )

        # Tempo de postagem
        posted = ""
        for sel in [
            "time.job-search-card__listdate",
            ".job-card-container__listed-date",
            "time",
        ]:
            els = card.find_elements(By.CSS_SELECTOR, sel)
            if els:
                posted = els[0].text.strip() or els[0].get_attribute("datetime") or ""
                break

        return LinkedInJob(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            url=url,
            is_remote=is_remote,
            posted_time=posted,
        )

    except Exception:
        return None


async def get_job_details_public(job: LinkedInJob) -> LinkedInJob:
    """Acessa a página pública da vaga para extrair descrição."""
    if not job.url:
        return job

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
                    ),
                },
                follow_redirects=True,
            ) as client:
                resp = await client.get(job.url)
                if resp.status_code != 200:
                    return job

            html = resp.text

            # Extrair descrição
            desc_match = re.search(
                r'class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
                html,
                re.DOTALL | re.IGNORECASE,
            )
            if desc_match:
                desc_html = desc_match.group(1)
                # Limpar HTML
                desc = re.sub(r"<[^>]+>", " ", desc_html)
                desc = re.sub(r"\s+", " ", desc).strip()
                job.description = desc

            if not job.description:
                # Fallback: extrair do JSON-LD
                jsonld_match = re.search(
                    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                    html,
                    re.DOTALL,
                )
                if jsonld_match:
                    try:
                        data = json.loads(jsonld_match.group(1))
                        job.description = data.get("description", "")
                        if not job.company and data.get("hiringOrganization"):
                            job.company = data["hiringOrganization"].get("name", "")
                        if not job.location and data.get("jobLocation"):
                            loc = data["jobLocation"]
                            if isinstance(loc, list) and loc:
                                loc = loc[0]
                            addr = loc.get("address", {})
                            job.location = f"{addr.get('addressLocality', '')} {addr.get('addressRegion', '')}".strip()
                    except (json.JSONDecodeError, KeyError):
                        pass

            # Clean HTML entities
            job.description = (
                job.description.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&nbsp;", " ")
                .replace("&#39;", "'")
            )

            # Verificar Easy Apply
            job.is_easy_apply = bool(
                re.search(r"Easy Apply|Candidatura simplificada", html, re.IGNORECASE)
            )

            # Verificar remoto
            if not job.is_remote and re.search(
                r"\bremot[eo]|home\s*office|trabalho\s*remoto\b",
                job.description,
                re.IGNORECASE,
            ):
                job.is_remote = True

            # Sucesso — sair do loop de retry
            break

        except (httpx.HTTPError, Exception) as e:
            if attempt == 0:
                logger.warning(f"⚠️ Retry detalhes de {job.job_id}: {e}")
                await asyncio.sleep(2)
                continue
            logger.warning(f"⚠️ Erro ao obter detalhes de {job.job_id}: {e}")

    return job


def get_job_details(driver: webdriver.Chrome, job: LinkedInJob) -> LinkedInJob:
    """Acessa a página da vaga via Selenium para extrair descrição completa."""
    if not job.url:
        return job

    try:
        driver.get(job.url)
        time.sleep(SEARCH_DELAY)

        # Clicar em "Show more" / "Ver mais" se existir
        for sel in [
            "button.show-more-less-html__button",
            "button[aria-label*='more']",
            "button[aria-label*='mais']",
        ]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    btns[0].click()
                    time.sleep(0.5)
                except Exception:
                    pass
                break

        # Extrair descrição
        for sel in [
            "div.show-more-less-html__markup",
            "div.description__text",
            "div.jobs-description__content",
            "section.description",
        ]:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                job.description = els[0].text.strip()
                break

        if not job.description:
            # Fallback: pegar todo texto da seção principal
            main = driver.find_elements(By.CSS_SELECTOR, "main, .job-view-layout")
            if main:
                job.description = main[0].text[:3000]

        # Verificar se é Easy Apply
        easy_apply = driver.find_elements(
            By.CSS_SELECTOR,
            "button.jobs-apply-button, "
            "button[aria-label*='Easy Apply'], "
            "button[aria-label*='Candidatura simplificada']",
        )
        job.is_easy_apply = len(easy_apply) > 0

        # Verificar remoto na descrição
        if not job.is_remote and re.search(
            r"\bremot[eo]|home\s*office|trabalho\s*remoto|anywhere\b",
            job.description,
            re.IGNORECASE,
        ):
            job.is_remote = True

    except Exception as e:
        logger.warning(f"⚠️ Erro ao obter detalhes de {job.job_id}: {e}")

    return job


# ─── Click Helpers ───────────────────────────────────────────────────────────
def _safe_click(driver: webdriver.Chrome, element, timeout: int = 10) -> bool:
    """Clica em um elemento com fallback JavaScript.

    Tenta click nativo → scroll into view + click → JS click.
    """
    try:
        # Scroll para o elemento
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
            element,
        )
        time.sleep(0.5)

        # Tentar click nativo
        try:
            element.click()
            return True
        except Exception:
            pass

        # Fallback: JS click
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            pass

        # Fallback: ActionChains
        from selenium.webdriver.common.action_chains import ActionChains
        try:
            ActionChains(driver).move_to_element(element).click().perform()
            return True
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"   ⚠️ _safe_click falhou: {e}")

    return False


def _wait_and_find(
    driver: webdriver.Chrome,
    selectors: list[str],
    timeout: int = 10,
) -> Optional[object]:
    """Aguarda e retorna o primeiro elemento clicável entre os seletores.

    Combina todos os seletores em um único CSS (OR) para usar
    um único WebDriverWait — evita N × timeout.
    """
    combined = ", ".join(selectors)
    wait = WebDriverWait(driver, timeout)
    try:
        el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, combined)))
        return el
    except Exception:
        pass

    # Fallback: buscar sem esperar clickability (pode estar atrás de overlay)
    els = driver.find_elements(By.CSS_SELECTOR, combined)
    if els:
        return els[0]

    return None


def _dismiss_overlays(driver: webdriver.Chrome) -> None:
    """Fecha overlays/modais do LinkedIn que bloqueiam interação."""
    overlay_selectors = [
        # Modal de login
        "button.modal__dismiss",
        "button[data-test-modal-close-btn]",
        "button.artdeco-modal__dismiss",
        # Cookies banner
        "button.artdeco-global-alert__action",
        # "Join now" overlay
        "button.contextual-sign-in-modal__modal-dismiss",
        "button[aria-label='Dismiss']",
        "button[aria-label='Fechar']",
    ]
    for sel in overlay_selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.5)
        except Exception:
            pass


# ─── Easy Apply ──────────────────────────────────────────────────────────────
def apply_easy_apply(
    driver: webdriver.Chrome,
    job: LinkedInJob,
    cover_letter: str,
    ss_dir: Path,
) -> bool:
    """Tenta candidatar-se via Easy Apply do LinkedIn."""
    try:
        # Página já carregada pelo loop principal — não navegar novamente
        logger.info(f"   🔄 Easy Apply: iniciando para {job.job_id}")

        # Fechar overlays que bloqueiam botões
        _dismiss_overlays(driver)

        # Clicar botão Easy Apply com WebDriverWait
        # Nota: aria-label do LinkedIn usa lowercase ("candidatura simplificada")
        # CSS attr selectors são case-sensitive — usar 'i' flag p/ case-insensitive
        apply_btn = _wait_and_find(driver, [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply' i]",
            "button[aria-label*='candidatura' i]",
            "button.jobs-apply-button--top-card",
            # LinkedIn mudou para <a> em vez de <button>
            "a[aria-label*='candidatura' i]",
            "a[aria-label*='Easy Apply' i]",
        ], timeout=10)

        if not apply_btn:
            # Fallback: buscar via JavaScript (funciona com <a>, <button>, <span>)
            logger.info(f"   🔍 CSS falhou — buscando Easy Apply via JS...")
            apply_btn = driver.execute_script("""
                var kws = ['candidatura simplificada', 'easy apply'];
                // Rejeitar links para similar-jobs, collections, anúncios
                var reject_hrefs = ['similar-jobs', 'collections', 'premium', '/feed/'];
                var els = document.querySelectorAll('a, button');
                for (var i = 0; i < els.length; i++) {
                    var el = els[i];
                    if (!el.offsetParent && el.offsetWidth === 0) continue;
                    var txt = (el.textContent || '').trim().toLowerCase();
                    var aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    var href = (el.getAttribute('href') || '').toLowerCase();
                    // Rejeitar links que não são Easy Apply
                    var rejected = false;
                    for (var r = 0; r < reject_hrefs.length; r++) {
                        if (href.includes(reject_hrefs[r])) { rejected = true; break; }
                    }
                    if (rejected) continue;
                    for (var k = 0; k < kws.length; k++) {
                        if (txt.includes(kws[k]) || aria.includes(kws[k])) return el;
                    }
                }
                return null;
            """)
            if apply_btn:
                logger.info(f"   ✅ JS encontrou botão Easy Apply (tag={apply_btn.tag_name})")

        if not apply_btn:
            logger.warning(f"   ⚠️ Botão Easy Apply não encontrado para {job.job_id}")
            _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_no_btn.png")
            return False

        # Log: qual elemento foi encontrado
        btn_tag = apply_btn.tag_name if apply_btn else "?"
        btn_aria = (apply_btn.get_attribute("aria-label") or "")[:40] if apply_btn else ""
        btn_txt = (apply_btn.text or "")[:40] if apply_btn else ""
        btn_href = (apply_btn.get_attribute("href") or "")[:80] if apply_btn else ""
        logger.info(f"   🔍 Easy Apply btn: <{btn_tag}> aria='{btn_aria}' txt='{btn_txt}' href='{btn_href}'")

        # Validação: rejeitar botões que não são Easy Apply real
        # (acontece quando a vaga já foi aplicada e o botão sumiu)
        if btn_tag.lower() == "a" and btn_href:
            _reject_keywords = ["similar-jobs", "collections", "/feed/", "premium"]
            if any(rk in btn_href.lower() for rk in _reject_keywords):
                logger.warning(
                    f"   ⚠️ Botão Easy Apply é link falso (href contém similar-jobs/collections) — "
                    f"vaga provavelmente já candidatada"
                )
                _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_already_applied.png")
                return False

        # Seletor combinado para detectar modais/dialogs (LinkedIn varia o container)
        _DIALOG_CSS = (
            "[role='dialog'], .artdeco-modal, .jobs-easy-apply-modal, "
            ".jobs-apply-form, [data-test-modal], "
            "div[class*='easy-apply'], div[class*='artdeco-modal-overlay--visible']"
        )

        # ── SDUI vs Modal: LinkedIn usa 2 fluxos distintos para Easy Apply ──
        # 1) SDUI (Server-Driven UI): <a> com href contendo /apply/?openSDUIApplyFlow=true
        #    → Navega para página separada com formulário embutido (NÃO é modal)
        # 2) Modal tradicional: <button> que abre [role='dialog'] na mesma página
        sdui_mode = False
        sdui_apply_url = ""
        original_job_url = driver.current_url

        if btn_tag.lower() == "a" and btn_href:
            # Extrair href completo do atributo (pode estar truncado no log)
            full_href = apply_btn.get_attribute("href") or ""
            if "/apply" in full_href or "openSDUIApplyFlow" in full_href:
                sdui_mode = True
                sdui_apply_url = full_href
                logger.info(f"   🌐 SDUI Apply detectado — navegando para URL de candidatura")
                logger.info(f"      URL: {sdui_apply_url[:100]}")
                driver.get(sdui_apply_url)
                time.sleep(4)
            else:
                # <a> sem /apply/ — clicar normalmente (deixar navegar)
                logger.info(f"   🔧 Easy Apply <a> sem SDUI — clicando normalmente")
                _safe_click(driver, apply_btn)
                time.sleep(3)
        else:
            # <button> — fluxo modal tradicional
            if not _safe_click(driver, apply_btn):
                logger.warning(f"   ⚠️ Não conseguiu clicar no Easy Apply para {job.job_id}")
                _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_click_fail.png")
                return False
            time.sleep(3)

        # ── Detectar container do formulário ──
        # SDUI: formulário está na página (pode ou não ter dialog)
        # Modal: formulário está dentro de [role='dialog']
        dialog = None
        form_container = None  # None = usar driver (full page)

        # Primeiro: procurar dialog/modal (funciona para ambos os fluxos)
        try:
            dialog = WebDriverWait(driver, 6 if not sdui_mode else 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, _DIALOG_CSS))
            )
            form_container = dialog
            logger.info(f"   ✅ Dialog/modal encontrado{' (dentro da SDUI page)' if sdui_mode else ''}")
        except Exception:
            if sdui_mode:
                # SDUI: normal não ter dialog — formulário está na página
                # Verificar se a página de apply carregou
                cur_url = driver.current_url
                if "/apply" in cur_url:
                    logger.info(f"   ✅ Página SDUI Apply carregada (sem dialog — OK)")
                    form_container = None  # usar full page
                else:
                    logger.warning(f"   ⚠️ SDUI: URL não contém /apply/ — url={cur_url[:80]}")
                    # Tentar navegar novamente
                    if sdui_apply_url:
                        driver.get(sdui_apply_url)
                        time.sleep(4)
                        if "/apply" in driver.current_url:
                            logger.info(f"   ✅ SDUI Apply carregada na 2ª tentativa")
                            form_container = None
                        else:
                            logger.warning(f"   ⚠️ SDUI falhou ao carregar")
                            _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_sdui_fail.png")
                            driver.get(original_job_url)
                            time.sleep(2)
                            return False
            else:
                # Modal tradicional: dialog não abriu — retry
                cur_url = driver.current_url
                logger.warning(
                    f"   ⚠️ Modal Easy Apply NÃO abriu — url={cur_url[:80]}"
                )

                # Retry: ENTER key
                try:
                    apply_btn.send_keys("\n")
                    time.sleep(3)
                    page_dialogs = driver.find_elements(By.CSS_SELECTOR, _DIALOG_CSS)
                    if page_dialogs:
                        dialog = page_dialogs[-1]
                        form_container = dialog
                        logger.info(f"   ✅ Modal aberto via ENTER key")
                except Exception:
                    pass

                # Retry: navegar para /apply/ (fallback SDUI)
                if not dialog:
                    try:
                        apply_url = cur_url.split("?")[0].rstrip("/") + "/apply/"
                        logger.info(f"   🔄 Fallback: navegando para {apply_url[:60]}")
                        driver.get(apply_url)
                        time.sleep(4)
                        if "/apply" in driver.current_url:
                            sdui_mode = True
                            logger.info(f"   ✅ Fallback SDUI carregado")
                            # Verificar se tem dialog na SDUI page
                            page_dialogs = driver.find_elements(By.CSS_SELECTOR, _DIALOG_CSS)
                            if page_dialogs:
                                form_container = page_dialogs[-1]
                            else:
                                form_container = None  # full page
                        else:
                            page_dialogs = driver.find_elements(By.CSS_SELECTOR, _DIALOG_CSS)
                            if page_dialogs:
                                dialog = page_dialogs[-1]
                                form_container = dialog
                    except Exception:
                        pass

                if not dialog and not sdui_mode:
                    logger.warning(f"   ⚠️ Modal Easy Apply não abriu para {job.job_id}")
                    _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_no_modal.png")
                    return False

        # Screenshot do formulário
        _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_form.png")

        # ── Diagnóstico: listar elementos do formulário ──
        _diag_ctx = form_container if form_container else driver
        try:
            _inputs = _diag_ctx.find_elements(By.TAG_NAME, "input")
            _selects = _diag_ctx.find_elements(By.TAG_NAME, "select")
            _textareas = _diag_ctx.find_elements(By.TAG_NAME, "textarea")
            _buttons = _diag_ctx.find_elements(By.TAG_NAME, "button")
            logger.info(
                f"   📋 Formulário: {len(_inputs)} inputs, {len(_selects)} selects, "
                f"{len(_textareas)} textareas, {len(_buttons)} buttons "
                f"(container={'dialog' if form_container else 'full-page'}, sdui={sdui_mode})"
            )
        except Exception:
            pass

        # ── Preencher campos do formulário Easy Apply (multi-step) ──
        max_steps = 12
        _prev_form_sig = ""  # Assinatura completa do formulário (detecção de loop)
        _stuck_count = 0  # Contador de steps sem progresso
        _MAX_STUCK = 3  # Max steps repetidos antes de desistir
        for step in range(max_steps):
            time.sleep(1.5)

            # Re-localizar container a cada step (DOM pode mudar)
            _ctx = None
            for _dsel in [
                "[role='dialog']", ".artdeco-modal", ".jobs-easy-apply-modal",
                ".jobs-apply-form", "[data-test-modal]",
                "div[class*='easy-apply']",
            ]:
                _dlgs = driver.find_elements(By.CSS_SELECTOR, _dsel)
                if _dlgs:
                    _ctx = _dlgs[-1]
                    break

            # SDUI sem dialog: buscar main/form/section como container
            if not _ctx and sdui_mode:
                for _fsel in ["main form", "main", "form", "[class*='apply']", "section"]:
                    _forms = driver.find_elements(By.CSS_SELECTOR, _fsel)
                    if _forms:
                        _ctx = _forms[0]
                        break

            # Fallback final: usar driver (full page)
            if not _ctx:
                _ctx = driver

            # Fechar overlays dentro do modal
            _dismiss_overlays(driver)

            # Preencher campos de texto, selects, radios, checkboxes
            # IMPORTANTE: scopar busca dentro do container (_ctx) para não pegar
            # a barra de pesquisa do LinkedIn e outros elementos da página
            # Nota: _fill_visible_fields já chama _fill_radios/_fill_checkboxes internamente
            filled = _fill_visible_fields(driver, cover_letter, container=_ctx, job=job)

            # LinkedIn usa dropdowns artdeco (não-nativos) — tratar separadamente
            _fill_artdeco_dropdowns(driver, container=_ctx)

            # Log: listar campos não preenchidos para debug
            _log_unfilled_fields(driver, step, container=_ctx)

            # Detecção de loop: verificar se o formulário está idêntico entre steps
            _cur_form_sig = _get_form_signature(driver, container=_ctx)
            if _cur_form_sig == _prev_form_sig:
                _stuck_count += 1
                if _stuck_count >= _MAX_STUCK:
                    logger.warning(
                        f"   🔁 Loop detectado: formulário idêntico por {_stuck_count} steps — "
                        f"desistindo do Easy Apply {job.job_id}"
                    )
                    break
            else:
                _stuck_count = 0
            _prev_form_sig = _cur_form_sig

            # Verificar erros de validação e corrigir
            _handle_validation_errors(driver, cover_letter, job=job)

            # Verificar se há botão de enviar (buscar na página inteira,
            # pois botões de ação podem estar fora do form container)
            submit_btn = _wait_and_find(driver, [
                "button[aria-label*='Submit']",
                "button[aria-label*='Enviar']",
                "button[data-easy-apply-next-button][aria-label*='ubmit']",
                "button[data-easy-apply-next-button][aria-label*='nviar']",
            ], timeout=3)
            if submit_btn:
                _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_submit.png")
                _safe_click(driver, submit_btn)
                time.sleep(2)

                # Verificar se apareceu confirmação
                page_text = driver.page_source.lower()
                if any(kw in page_text for kw in [
                    "application submitted", "candidatura enviada",
                    "your application", "sua candidatura", "applied",
                ]):
                    logger.info(f"   ✅ Easy Apply enviado para {job.job_id}")
                    _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_done.png")
                    if sdui_mode:
                        driver.get(original_job_url)
                        time.sleep(2)
                    return True

                # Pode ter ido para página de review — verificar submit de novo
                submit2 = _wait_and_find(driver, [
                    "button[aria-label*='Submit']",
                    "button[aria-label*='Enviar']",
                ], timeout=3)
                if submit2:
                    _safe_click(driver, submit2)
                    time.sleep(2)

                logger.info(f"   ✅ Easy Apply enviado para {job.job_id}")
                _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_done.png")
                if sdui_mode:
                    driver.get(original_job_url)
                    time.sleep(2)
                return True

            # Botão "Next" / "Avançar" / "Review"
            next_btn = _wait_and_find(driver, [
                "button[aria-label*='Next']",
                "button[aria-label*='Avançar']",
                "button[aria-label*='Continue']",
                "button[aria-label*='Review']",
                "button[aria-label*='Revisar']",
                "button[data-easy-apply-next-button]",
            ], timeout=3)
            if next_btn:
                logger.info(f"      ➡️ Step {step + 1}: '{next_btn.get_attribute('aria-label') or next_btn.text}'")
                _safe_click(driver, next_btn)
                time.sleep(1.5)

                # Verificar se clicou mas não avançou (erro de validação)
                _handle_validation_errors(driver, cover_letter, job=job)
            else:
                # Tentar encontrar botão por texto
                found_next = False
                for el in driver.find_elements(By.TAG_NAME, "button"):
                    txt = (el.text or "").strip().lower()
                    if txt in ["next", "avançar", "continue", "review", "revisar",
                               "próximo", "continuar"]:
                        if el.is_displayed():
                            _safe_click(driver, el)
                            time.sleep(1.5)
                            found_next = True
                            break
                if not found_next:
                    break

        # Se não encontrou submit, tenta fechar e reportar
        logger.warning(f"   ⚠️ Easy Apply incompleto para {job.job_id} (sem botão submit)")
        _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_incomplete.png")
        if sdui_mode:
            driver.get(original_job_url)
            time.sleep(2)
        return False

    except Exception as e:
        logger.error(f"   ❌ Erro no Easy Apply {job.job_id}: {e}")
        _take_screenshot(driver, ss_dir / f"easy_apply_{job.job_id}_error.png")
        return False


def _fill_artdeco_dropdowns(driver: webdriver.Chrome, container: object | None = None) -> None:
    """Preenche dropdowns artdeco do LinkedIn (não-nativos).

    LinkedIn usa custom selects com classe artdeco-dropdown.
    Se container fornecido, busca apenas dentro dele.
    """
    ctx = container if container is not None else driver
    # Artdeco select triggers
    triggers = ctx.find_elements(
        By.CSS_SELECTOR,
        "select[data-test-text-selectable-option], "
        "button[data-test-text-selectable-option], "
        ".artdeco-dropdown__trigger, "
        ".fb-dash-form-element__select button",
    )
    for trigger in triggers:
        try:
            if not trigger.is_displayed():
                continue
            # Verificar se já tem valor selecionado
            selected = trigger.text.strip()
            if selected and selected.lower() != "select an option":
                continue

            label = _get_field_label(driver, trigger)

            # Abrir dropdown
            _safe_click(driver, trigger)
            time.sleep(0.5)

            # Procurar opções
            options = driver.find_elements(
                By.CSS_SELECTOR,
                ".artdeco-dropdown__content li, "
                ".fb-dash-form-element__select-option, "
                "[role='option'], [role='listbox'] li",
            )
            best_opt = None
            for pat_label, pat_opt in _SELECT_MAP:
                if re.search(pat_label, label, re.IGNORECASE):
                    for opt in options:
                        opt_text = opt.text.strip()
                        if re.search(pat_opt, opt_text, re.IGNORECASE):
                            best_opt = opt
                            break
                    break

            if best_opt:
                _safe_click(driver, best_opt)
                logger.info(f"      📝 Artdeco: '{label[:25]}' → '{best_opt.text[:25]}'")
            elif options:
                # Selecionar primeira opção válida
                for opt in options:
                    if opt.text.strip() and opt.is_displayed():
                        _safe_click(driver, opt)
                        logger.info(f"      📝 Artdeco fallback: '{label[:25]}' → '{opt.text[:25]}'")
                        break
            else:
                # Fechar dropdown sem selecionar
                driver.find_element(By.TAG_NAME, "body").click()

            time.sleep(0.3)
        except Exception:
            pass

    # LinkedIn typeahead inputs (ex: cidade, empresa)
    typeaheads = ctx.find_elements(
        By.CSS_SELECTOR,
        "input[role='combobox'], input.fb-single-typeahead-entity__input",
    )
    for ta in typeaheads:
        try:
            if not ta.is_displayed():
                continue
            val = ta.get_attribute("value") or ""
            if val.strip():
                continue

            label = _get_field_label(driver, ta)
            value = _infer_value(label, "")
            if value:
                ta.clear()
                ta.send_keys(value)
                time.sleep(1)

                # Selecionar primeira sugestão do typeahead
                suggestions = driver.find_elements(
                    By.CSS_SELECTOR,
                    "[role='option'], .basic-typeahead__selectable, "
                    ".fb-single-typeahead-entity__option",
                )
                if suggestions:
                    for sug in suggestions:
                        if sug.is_displayed():
                            _safe_click(driver, sug)
                            logger.info(f"      📝 Typeahead: '{label[:25]}' → '{sug.text[:25]}'")
                            break
                time.sleep(0.3)
        except Exception:
            pass


def _get_form_signature(driver: webdriver.Chrome, container: object | None = None) -> str:
    """Gera assinatura COMPLETA do formulário visível para detecção de loop.

    Inclui todos os campos visíveis (preenchidos E vazios) com seus valores.
    Se a assinatura é idêntica entre steps consecutivos, o formulário está preso.
    Detecta tanto campos vazios repetidos quanto campos preenchidos sem avanço.
    """
    ctx = container if container is not None else driver
    sig_parts: list[str] = []
    try:
        all_inputs = ctx.find_elements(
            By.CSS_SELECTOR,
            "input:not([type='hidden']):not([type='file']):not([type='submit']):not([type='button']), "
            "select, textarea",
        )
        for inp in all_inputs:
            try:
                if not inp.is_displayed():
                    continue
                val = (inp.get_attribute("value") or "")[:20]
                tag = inp.tag_name
                inp_type = inp.get_attribute("type") or ""
                el_id = inp.get_attribute("id") or ""
                sig_parts.append(f"{tag}:{inp_type}:{el_id[:30]}={val}")
            except Exception:
                pass
    except Exception:
        pass
    return "|".join(sorted(sig_parts))


def _log_unfilled_fields(driver: webdriver.Chrome, step: int, container: object | None = None) -> None:
    """Loga campos visíveis não preenchidos para debug."""
    ctx = container if container is not None else driver
    unfilled: list[str] = []
    all_inputs = ctx.find_elements(
        By.CSS_SELECTOR,
        "input:not([type='hidden']):not([type='file']):not([type='submit']):not([type='button']), "
        "select, textarea",
    )
    for inp in all_inputs:
        try:
            if not inp.is_displayed():
                continue
            val = inp.get_attribute("value") or ""
            if val.strip():
                continue
            # Campo vazio visível
            label = _get_field_label(driver, inp)
            tag = inp.tag_name
            inp_type = inp.get_attribute("type") or "text"
            required = inp.get_attribute("required") or inp.get_attribute("aria-required")
            req_str = " [REQUIRED]" if required else ""
            unfilled.append(f"{tag}({inp_type}): '{label[:50]}'{req_str}")
        except Exception:
            pass

    if unfilled:
        logger.info(f"      🔍 Step {step + 1} — {len(unfilled)} campo(s) vazio(s):")
        for uf in unfilled[:5]:
            logger.info(f"         ↳ {uf}")


# ─── Mapa inteligente de campos → valores ────────────────────────────────────
# Cada tupla: (padrões regex para match no label/name/id/placeholder, valor a preencher)
_FIELD_MAP: list[tuple[str, str]] = [
    # Nome completo
    (r"full.?name|nome.?complet|your.?name", RESUME["nome"]),
    # Primeiro nome
    (r"first.?name|primeiro.?nome|given.?name|^nome$", RESUME["nome"].split()[0]),
    # Sobrenome
    (r"last.?name|sobrenome|surname|family.?name", " ".join(RESUME["nome"].split()[1:])),
    # Email
    (r"e?.?mail|correo", RESUME["email"]),
    # Telefone
    (r"phone|telefone|celular|mobile|whatsapp|tel$", RESUME["telefone"]),
    # Cidade / Localização
    (r"city|cidade|location|localiza|endere|address", RESUME["localizacao"]),
    # LinkedIn URL
    (r"linkedin|perfil.?linked", "https://www.linkedin.com/in/edenilson-paschoa"),
    # GitHub / Portfolio
    (r"github|portfolio|website|site", "https://github.com/eddiejdi"),
    # Idade
    (r"(?:qual|what).{0,5}(?:sua|your).{0,5}idade|(?:how|what).{0,5}(?:old|age)|^idade$|^age$", "36"),
    # Experiência (anos) — genérico
    (r"years?.?(?:of)?.?experience|anos?.?(?:de)?.?experi[eê]ncia|tempo.?experi|h[aá].?quanto.?tempo", "15"),
    # Experiência com tech específica (fallback genérico)
    (r"experi[eê]ncia.?com|experience.?with|tempo.?(?:de|com).?(?:atua|trabalh)", "5"),
    # Pretensão salarial — usa __SALARY__ sentinel, calculado dinamicamente
    (r"salary|sal[aá]rio|pretens[aã]o|remunera|compensation|expect.?salar", "__SALARY__"),
    # Disponibilidade
    (r"availab|disponibil|start.?date|in[ií]cio|quando.?pode|notice.?period", "Imediata"),
    # CPF (PCD geralmente pede)
    (r"cpf|documento|identity.?number", ""),  # vazio — não expor
    # País / País de residência
    (r"country|pa[ií]s", "Brasil"),
    # Estado
    (r"state|estado|province|uf$", "São Paulo"),
    # Empresa atual / Company
    (r"company.?(?:name|where)|(?:nome|name).?(?:da)?.?empresa|employer|empregador|onde.?trabalha|where.?you.?work", "B3 - Brasil, Bolsa, Balcão"),
    # CEP
    (r"zip|cep|postal.?code", "13216-000"),
    # Tipo de vaga preferido
    (r"work.?type|modelo.?trabalho|remote.?preference", "Remoto"),
    # Como soube da vaga
    (r"how.?did.?you|como.?soube|source|refer|where.?did", "LinkedIn"),
    # PCD
    (r"disab|defici[eê]ncia|pcd|necessidade.?especial|accommodation", "Sim"),
    # Gênero
    (r"gender|g[eê]nero|sexo", "Masculino"),
    # Raça/Etnia
    (r"race|ra[cç]a|ethnic|etnia", "Prefiro não informar"),
    # Nacionalidade
    (r"national|nacional", "Brasileiro"),
    # Cargo desejado
    (r"desired.?(?:role|position)|cargo.?desejado|vaga", "SRE / DevOps / Software Engineer"),
    # Resumo / Sobre mim
    (r"summary|resumo|about|sobre.?voc[eê]|bio|brief", 
     f"Profissional com 15+ anos em TI. SRE na B3, experiência em Mercado Livre, Itaú. "
     f"Especialista em Python, Go, Docker, Kubernetes, AWS, GCP. PCD."),
    # Nota de apresentação
    (r"cover|carta|mensagem|message|note|additional|adicional", "__COVER_LETTER__"),
    # Conforto / Comfortable with
    (r"confort[aá]vel|comfortable|se.?sente.?confort|are.?you.?comfortable", "Sim"),
    # Autorização para trabalhar
    (r"authorized?.?to.?work|autoriza.{0,5}trabalh|work.?permit|visto.?de.?trabalho|elegível|eligible", "Sim"),
    # Aceita viajar / Relocação
    (r"willing.?to.?(?:travel|relocat)|dispos.{0,5}(?:viaj|mudar|relocar)|aceita.?(?:viaj|mudar)", "Sim"),
    # Nível de inglês
    (r"english.?(?:level|proficiency|n[ií]vel)|n[ií]vel.?(?:de)?.?ingl[eê]s|ingl[eê]s", "Avançado"),
    # Nível de espanhol
    (r"spanish|espanhol", "Básico"),
]

# Padrões para selects/dropdowns: (regex do label, regex da opção preferida)
_SELECT_MAP: list[tuple[str, str]] = [
    (r"country|pa[ií]s", r"bra[sz]il|brasil"),
    (r"state|estado", r"s[aã]o.?paulo|sp$"),
    (r"gender|g[eê]nero|sexo", r"masc|male|homem"),
    (r"experience|experi[eê]ncia|seniority|senioridade", r"senior|s[eê]nior|pleno|senior|15|10\+"),
    (r"disab|defici|pcd", r"sim|yes|true"),
    (r"work.?type|modelo|remote|remoto", r"remot|remote|home"),
    (r"education|escolaridade|forma[cç][aã]o", r"superior|gradua|bachelor|completo"),
    (r"english|ingl[eê]s", r"avan[cç]|fluent|advanced|interm"),
    (r"how.?did|como.?soube|source", r"linkedin"),
    (r"notice|aviso|disponibil|start", r"immed|imedia|now|agora|0|asap"),
    (r"race|ra[cç]a|ethn", r"prefer.?n|n[aã]o.?inform|decline"),
    (r"veteran", r"n[aã]o|no|not"),
    (r"din[aâ]mica|pair.?programming|coding.?challenge|test|entrevista.?t[eé]cnica", r"sim|yes"),
    (r"confort[aá]vel|comfortable|se.?sente|dispon[ií]vel|available", r"sim|yes"),
    (r"english|ingl[eê]s", r"avan[cç]|advanced|fluent|interm"),
    (r"aceita|accept|concord|agree", r"sim|yes|agree|aceito|accept"),
]

# Padrões para radio buttons/checkboxes
_RADIO_MAP: list[tuple[str, str]] = [
    (r"disab|defici|pcd", r"sim|yes"),
    (r"remote|remoto", r"sim|yes"),
    (r"authorized|autoriza|work.?permit|visto", r"sim|yes"),
    (r"relocat|mudar|dispos", r"sim|yes"),
    (r"veteran", r"n[aã]o|no"),
    (r"gender|sexo", r"masc|male"),
    (r"privacy|privac|lgpd|consent|aceito|agree|termos|terms", r"sim|yes|agree|aceito|accept"),
]


def _get_field_label(driver: webdriver.Chrome, element) -> str:
    """Obtém o label/contexto de um campo de formulário.

    Tenta (em ordem): JS DOM walking (melhor para SDUI), aria-labelledby,
    label[for], aria-label, placeholder, name, id, texto do parent.
    """
    parts: list[str] = []

    # 0. JS DOM walking — encontra label visual mais próxima (essencial para SDUI)
    # SDUI usa IDs genéricos como 'text-entity-list-form-component-formElem'
    # mas tem labels/spans visíveis acima do campo no DOM
    try:
        js_label = driver.execute_script("""
            var el = arguments[0];
            // 1. aria-labelledby
            var lblBy = el.getAttribute('aria-labelledby');
            if (lblBy) {
                var parts = lblBy.split(' ');
                var texts = [];
                for (var i = 0; i < parts.length; i++) {
                    var ref = document.getElementById(parts[i]);
                    if (ref) texts.push(ref.textContent.trim());
                }
                if (texts.length) return texts.join(' ');
            }
            // 2. Walk up DOM looking for label/legend/span with descriptive text
            var parent = el.parentElement;
            for (var depth = 0; depth < 6 && parent; depth++) {
                // Check direct label children of parent  
                var candidates = parent.querySelectorAll(
                    ':scope > label, :scope > legend, :scope > span, '
                    + ':scope > div > label, :scope > div > span'
                );
                for (var j = 0; j < candidates.length; j++) {
                    var c = candidates[j];
                    // Skip if candidate contains our element
                    if (c.contains(el)) continue;
                    var txt = c.textContent.trim();
                    if (txt.length > 2 && txt.length < 200) return txt;
                }
                parent = parent.parentElement;
            }
            // 3. Preceding siblings
            var prev = el.parentElement;
            if (prev) {
                prev = prev.previousElementSibling;
                for (var k = 0; k < 3 && prev; k++) {
                    var pt = prev.textContent.trim();
                    if (pt.length > 2 && pt.length < 200 &&
                        !prev.querySelector('input, select, textarea')) {
                        return pt;
                    }
                    prev = prev.previousElementSibling;
                }
            }
            return '';
        """, element)
        if js_label:
            parts.append(js_label)
    except Exception:
        pass

    # aria-label
    aria = element.get_attribute("aria-label") or ""
    if aria:
        parts.append(aria)

    # placeholder
    placeholder = element.get_attribute("placeholder") or ""
    if placeholder:
        parts.append(placeholder)

    # name e id
    for attr in ["name", "id"]:
        val = element.get_attribute(attr) or ""
        if val:
            # Converter camelCase/snake_case em palavras
            val = re.sub(r"([a-z])([A-Z])", r"\1 \2", val)
            val = val.replace("_", " ").replace("-", " ")
            parts.append(val)

    # label[for]
    el_id = element.get_attribute("id")
    if el_id:
        try:
            labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{el_id}']")
            if labels:
                lbl_text = labels[0].text.strip()
                if lbl_text:
                    parts.append(lbl_text)
        except Exception:
            pass

    # Texto do wrapper/parent imediato (fallback)
    if not parts:
        try:
            parent = element.find_element(By.XPATH, "..")
            parent_text = parent.text.strip()[:100]
            if parent_text:
                parts.append(parent_text)
        except Exception:
            pass

    return " | ".join(parts).lower()


def _infer_value(
    label: str,
    cover_letter: str,
    job: "LinkedInJob | None" = None,
) -> str | None:
    """Infere o valor correto para um campo com base no seu label.

    Args:
        label: Texto identificador do campo (aria-label, placeholder, etc.).
        cover_letter: Carta de apresentação para campos de texto livre.
        job: Vaga atual — usado para calcular pretensão salarial dinâmica.
    """
    for pattern, value in _FIELD_MAP:
        if re.search(pattern, label, re.IGNORECASE):
            if value == "__COVER_LETTER__":
                return cover_letter[:2000]
            if value == "__SALARY__":
                if job is not None:
                    return calculate_salary_expectation(job)
                return "15000"  # Fallback: sênior padrão
            return value
    return None


def _fill_visible_fields(
    driver: webdriver.Chrome,
    cover_letter: str,
    container: object | None = None,
    job: "LinkedInJob | None" = None,
) -> int:
    """Preenche todos os campos visíveis no formulário (Easy Apply ou externo).

    Lê labels de cada campo e infere o valor correto via _FIELD_MAP.
    Se container fornecido, busca apenas dentro dele (ex: modal dialog).
    Se job fornecido, calcula pretensão salarial dinâmica.
    Retorna quantidade de campos preenchidos.
    """
    filled = 0
    ctx = container if container is not None else driver

    # 1. Inputs de texto visíveis
    inputs = ctx.find_elements(
        By.CSS_SELECTOR,
        "input[type='text'], input[type='email'], input[type='tel'], "
        "input[type='url'], input[type='number'], input:not([type])",
    )
    for inp in inputs:
        try:
            if not inp.is_displayed():
                continue
            # Pular campos já preenchidos
            current_val = inp.get_attribute("value") or ""
            if current_val.strip():
                continue

            label = _get_field_label(driver, inp)
            value = _infer_value(label, cover_letter, job=job)
            if value:
                _safe_click(driver, inp)
                inp.clear()
                inp.send_keys(value)
                filled += 1
                logger.info(f"      📝 Preenchido: '{label[:40]}' → '{value[:30]}'")
                time.sleep(0.3)
        except Exception as e:
            logger.debug(f"      Skip input: {e}")

    # 2. Textareas
    textareas = ctx.find_elements(By.CSS_SELECTOR, "textarea")
    for ta in textareas:
        try:
            if not ta.is_displayed():
                continue
            current_val = ta.get_attribute("value") or ta.text or ""
            if current_val.strip():
                continue

            label = _get_field_label(driver, ta)
            value = _infer_value(label, cover_letter, job=job)
            # Para textareas sem match, usar cover letter como fallback
            if not value:
                value = cover_letter[:2000]
            _safe_click(driver, ta)
            ta.clear()
            ta.send_keys(value)
            filled += 1
            logger.info(f"      📝 Textarea preenchida: '{label[:40]}'")
            time.sleep(0.3)
        except Exception as e:
            logger.debug(f"      Skip textarea: {e}")

    # 3. Contenteditable divs
    editables = ctx.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']")
    for ed in editables:
        try:
            if not ed.is_displayed() or ed.text.strip():
                continue
            ed.click()
            ed.send_keys(cover_letter[:2000])
            filled += 1
            time.sleep(0.3)
        except Exception:
            pass

    # 4. Upload inteligente: CV ou laudo médico conforme o campo
    uploads = ctx.find_elements(By.CSS_SELECTOR, "input[type='file']")
    for upload in uploads:
        try:
            if not upload.is_enabled():
                continue
            label = _get_field_label(driver, upload)
            # Pular campos de foto/avatar — NÃO anexar CV
            if _PHOTO_UPLOAD_RE.search(label):
                logger.info(f"      ⏭️ Campo de foto ignorado: {label[:60]}")
                continue
            if _LAUDO_UPLOAD_RE.search(label) and LAUDO_PDF.exists():
                upload.send_keys(str(LAUDO_PDF.resolve()))
                filled += 1
                logger.info(f"      📎 LAUDO MÉDICO anexado (campo: {label[:60]})")
            elif CV_DOCX.exists():
                upload.send_keys(str(CV_DOCX.resolve()))
                filled += 1
                logger.info(f"      📎 CV anexado (campo: {label[:60]})")
            time.sleep(1)
        except Exception:
            pass

    # 5. Selects/Dropdowns (native + Angular Material)
    selects = ctx.find_elements(By.CSS_SELECTOR, "select")
    for select in selects:
        try:
            if not select.is_displayed():
                continue
            from selenium.webdriver.support.ui import Select
            sel = Select(select)
            current_opt = sel.first_selected_option
            current_val = current_opt.get_attribute("value") or ""
            current_text = (current_opt.text or "").strip().lower()
            # Pular se já tem valor válido selecionado (não placeholder)
            placeholder_values = {"", "0", "--", "select", "selecione", "escolha", "select an option"}
            if current_val and current_text not in placeholder_values:
                continue  # Já selecionado com valor real

            label = _get_field_label(driver, select)
            logger.info(f"      🔍 Select: label='{label[:60]}' opts={len(sel.options)} current='{current_text[:20]}'")

            # SDUI: se select tem 0-1 opções, tentar clicar para carregar opções dinamicamente
            if len(sel.options) <= 1:
                try:
                    _safe_click(driver, select)
                    time.sleep(0.8)
                    # Re-criar Select após possível carregamento
                    sel = Select(select)
                    logger.debug(f"      🔄 SDUI select reload: {len(sel.options)} opções após click")
                except Exception:
                    pass

            # Tentar match inteligente
            best_option = None
            for pat_label, pat_opt in _SELECT_MAP:
                if re.search(pat_label, label, re.IGNORECASE):
                    for opt in sel.options:
                        opt_text = opt.text.strip()
                        opt_val = opt.get_attribute("value") or ""
                        if opt_val and re.search(pat_opt, f"{opt_text} {opt_val}", re.IGNORECASE):
                            best_option = opt
                            break
                    break

            if best_option:
                sel.select_by_visible_text(best_option.text)
                filled += 1
                logger.info(f"      📝 Select: '{label[:30]}' → '{best_option.text[:30]}'")
            elif not current_val or current_text in placeholder_values:
                # Fallback: selecionar primeira opção não-vazia e não-placeholder
                for opt in sel.options:
                    opt_val = opt.get_attribute("value") or ""
                    opt_text = (opt.text or "").strip().lower()
                    if opt_val and opt_text not in placeholder_values:
                        sel.select_by_value(opt_val)
                        filled += 1
                        logger.info(f"      📝 Select fallback: '{label[:30]}' → '{opt.text[:30]}'")
                        break
            time.sleep(0.3)
        except Exception as e:
            logger.debug(f"      Skip select: {e}")

    # 5b. Angular Material mat-select e custom dropdowns (role="combobox")
    custom_selects = ctx.find_elements(
        By.CSS_SELECTOR,
        "mat-select, [role='combobox'], [role='listbox']",
    )
    for cs in custom_selects:
        try:
            if not cs.is_displayed():
                continue
            # Verificar se já tem valor selecionado
            current_text = (cs.text or "").strip()
            if current_text and current_text.lower() not in ["selecione", "select", "escolha", "--"]:
                continue
            label = _get_field_label(driver, cs)
            # Tentar abrir o dropdown e selecionar opção adequada
            for pat_label, pat_opt in _SELECT_MAP:
                if re.search(pat_label, label, re.IGNORECASE):
                    _safe_click(driver, cs)
                    time.sleep(0.5)
                    # Buscar opções no dropdown aberto
                    options = driver.find_elements(
                        By.CSS_SELECTOR,
                        "mat-option, [role='option'], .cdk-option, "
                        "li[role='option'], div[role='option']",
                    )
                    for opt in options:
                        opt_text = (opt.text or "").strip()
                        if re.search(pat_opt, opt_text, re.IGNORECASE):
                            _safe_click(driver, opt)
                            filled += 1
                            logger.info(f"      📝 Custom select: '{label[:30]}' → '{opt_text[:30]}'")
                            break
                    time.sleep(0.3)
                    break
        except Exception as e:
            logger.debug(f"      Skip custom select: {e}")

    # 6. Radio buttons
    _fill_radios(driver, container=ctx)

    # 7. Checkboxes obrigatórios (privacy, consent, terms)
    _fill_checkboxes(driver, container=ctx)

    # 8. Diagnóstico: se 0 campos preenchidos, logar o que existe no container
    if filled == 0:
        diag = driver.execute_script("""
            var root = arguments[0] || document;
            var info = {inputs: 0, textareas: 0, selects: 0, uploads: 0, fields: []};
            
            function findLabel(el) {
                // aria-label/placeholder first
                var lbl = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
                if (lbl) return lbl.substring(0, 60);
                // Walk up DOM for label/span text (SDUI support)
                var p = el.parentElement;
                for (var d = 0; d < 5 && p; d++) {
                    var candidates = p.querySelectorAll(':scope > label, :scope > span, :scope > div > label, :scope > div > span');
                    for (var j = 0; j < candidates.length; j++) {
                        var c = candidates[j];
                        if (c.contains(el)) continue;
                        var txt = c.textContent.trim();
                        if (txt.length > 2 && txt.length < 200) return txt.substring(0, 60);
                    }
                    p = p.parentElement;
                }
                return (el.getAttribute('name') || el.id || '').substring(0, 60);
            }
            
            root.querySelectorAll('input').forEach(function(el) {
                info.inputs++;
                if (el.offsetParent !== null && el.type !== 'hidden' && el.type !== 'submit'
                    && el.type !== 'button' && el.type !== 'file') {
                    info.fields.push({
                        tag: 'input', type: el.type || 'text',
                        label: findLabel(el),
                        val: (el.value || '').substring(0, 20),
                        req: el.required || el.getAttribute('aria-required') === 'true'
                    });
                }
            });
            root.querySelectorAll('textarea').forEach(function(el) {
                info.textareas++;
                if (el.offsetParent !== null) {
                    info.fields.push({tag: 'textarea', type: '', label: findLabel(el), val: '', req: el.required});
                }
            });
            root.querySelectorAll('select').forEach(function(el) {
                info.selects++;
                if (el.offsetParent !== null) {
                    var optCount = el.options ? el.options.length : 0;
                    info.fields.push({tag: 'select', type: '', label: findLabel(el), val: 'opts=' + optCount, req: el.required});
                }
            });
            info.uploads = root.querySelectorAll('input[type=file]').length;
            // Custom components (Angular Material, React)
            var customs = root.querySelectorAll('[role="combobox"], [role="listbox"], mat-select, [data-testid]');
            info.custom_count = customs.length;
            return info;
        """, ctx if ctx != driver else None)
        if diag:
            logger.info(
                f"      🔍 Debug: {diag.get('inputs',0)} inputs, {diag.get('textareas',0)} textareas, "
                f"{diag.get('selects',0)} selects, {diag.get('uploads',0)} uploads, "
                f"{diag.get('custom_count',0)} custom"
            )
            for f in (diag.get('fields') or [])[:5]:
                status = "✓filled" if f.get('val') else "✗empty"
                req = " [REQ]" if f.get('req') else ""
                logger.info(f"         ↳ {f['tag']}({f['type']}): '{f['label']}' = '{f.get('val','')}' {status}{req}")

    return filled


def _fill_radios(driver: webdriver.Chrome, container: object | None = None) -> None:
    """Preenche radio buttons com base no contexto do grupo."""
    ctx = container if container is not None else driver
    # Encontrar fieldsets ou grupos de radio
    radios = ctx.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    checked_names: set[str] = set()

    for radio in radios:
        try:
            name = radio.get_attribute("name") or ""
            if name in checked_names:
                continue
            if radio.is_selected():
                checked_names.add(name)
                continue
            if not radio.is_displayed():
                continue

            # Obter contexto do grupo
            group_label = _get_field_label(driver, radio)
            radio_text = ""
            try:
                label_el = radio.find_element(By.XPATH, "following-sibling::label | ..")
                radio_text = label_el.text.strip()
            except Exception:
                pass

            full_context = f"{group_label} {radio_text}".lower()

            for pat_group, pat_value in _RADIO_MAP:
                if re.search(pat_group, group_label, re.IGNORECASE):
                    if re.search(pat_value, full_context, re.IGNORECASE):
                        _safe_click(driver, radio)
                        checked_names.add(name)
                        logger.info(f"      🔘 Radio: '{group_label[:30]}' → '{radio_text[:20]}'")
                        break
        except Exception:
            pass


def _fill_checkboxes(driver: webdriver.Chrome, container: object | None = None) -> None:
    """Marca checkboxes de termos/privacidade/consent."""
    ctx = container if container is not None else driver
    checkboxes = ctx.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for cb in checkboxes:
        try:
            if cb.is_selected() or not cb.is_displayed():
                continue
            label = _get_field_label(driver, cb)
            if re.search(
                r"agree|aceito|consent|termos|terms|privacy|privac|lgpd|pol[ií]tica",
                label, re.IGNORECASE,
            ):
                _safe_click(driver, cb)
                logger.info(f"      ☑️ Checkbox: '{label[:40]}'")
                time.sleep(0.2)
        except Exception:
            pass


def apply_external(
    driver: webdriver.Chrome,
    job: LinkedInJob,
    cover_letter: str,
    ss_dir: Path,
    _apply_btn: object | None = None,
    _external_url: str | None = None,
) -> bool:
    """Candidatura via link externo (redireciona para site da empresa).

    Detecta ATS (Greenhouse, Lever, Gupy, etc.) e navega por formulários
    multi-página preenchendo campos adaptativamente.
    """
    try:
        # Página já carregada pelo loop principal — não navegar novamente
        logger.info(f"   🔄 External Apply: iniciando para {job.job_id}")

        original_window = driver.current_window_handle

        # CAMINHO RÁPIDO: se temos URL externa direta, navegar sem clicar
        if _external_url and 'linkedin.com' not in _external_url.lower():
            logger.info(f"   🔗 Navegando direto para URL externa: {_external_url[:80]}")
            driver.execute_script(f"window.open('{_external_url}', '_blank');")
            time.sleep(2)
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                try:
                    driver.maximize_window()
                except Exception:
                    pass
                try:
                    WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except Exception:
                    pass
            current_url = driver.current_url
            logger.info(f"   🔗 Página ATS carregada: {current_url[:80]}")
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_page.png")
            filled = _navigate_ats_and_fill(driver, cover_letter, job.job_id, ss_dir)
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(original_window)
            return filled

        # Fechar overlays do LinkedIn
        _dismiss_overlays(driver)

        # Usar botão já encontrado pelo loop principal (se disponível)
        external_btn = _apply_btn

        # Se botão é <a> com href externo, navegar direto pelo href
        if external_btn:
            try:
                tag_name = external_btn.tag_name.lower() if hasattr(external_btn, 'tag_name') else ''
                href = (external_btn.get_attribute('href') or '') if hasattr(external_btn, 'get_attribute') else ''
                if tag_name == 'a' and href and 'linkedin.com' not in href.lower() and href.startswith('http'):
                    logger.info(f"   🔗 Href externo encontrado: {href[:80]}")
                    driver.execute_script(f"window.open(arguments[0], '_blank');", href)
                    time.sleep(2)
                    if len(driver.window_handles) > 1:
                        driver.switch_to.window(driver.window_handles[-1])
                        try:
                            driver.maximize_window()
                        except Exception:
                            pass
                        try:
                            WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                                lambda d: d.execute_script("return document.readyState") == "complete"
                            )
                        except Exception:
                            pass
                    current_url = driver.current_url
                    logger.info(f"   🔗 Navegou para: {current_url[:80]}")
                    _take_screenshot(driver, ss_dir / f"external_{job.job_id}_page.png")
                    filled = _navigate_ats_and_fill(driver, cover_letter, job.job_id, ss_dir)
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(original_window)
                    return filled
            except Exception as href_err:
                logger.warning(f"   ⚠️ Falha ao extrair href: {href_err}")

        if not external_btn:
            # Procurar botão de apply externo — combinado para velocidade
            logger.info("   🔍 Buscando botão Apply externo...")
            _combined_apply_sel = (
                "a.jobs-apply-button, "
                "button.jobs-apply-button, "
                "button.jobs-apply-button--top-card, "
                "a.jobs-apply-button--top-card, "
                "button[aria-label*='Apply'], "
                "button[aria-label*='Candidatar'], "
                "a[aria-label*='Candidatar'], "
                "a[aria-label*='Apply'], "
                "a[data-tracking-control-name*='apply'], "
                "button.jobs-s-apply button"
            )
            external_btn = _wait_and_find(driver, [_combined_apply_sel], timeout=8)

        if not external_btn:
            # Tentar encontrar qualquer link/botão com texto "Apply" ou "Candidatar"
            logger.info("   🔍 Seletores CSS falharam, buscando por texto...")
            for tag in ["button", "a"]:
                els = driver.find_elements(By.TAG_NAME, tag)
                for el in els:
                    txt = (el.text or "").lower()
                    if any(kw in txt for kw in ["apply", "candidatar", "inscrever"]):
                        if el.is_displayed():
                            external_btn = el
                            break
                if external_btn:
                    break

        if not external_btn:
            logger.info(f"   ℹ️ Sem botão de candidatura para {job.job_id}")
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_no_btn.png")
            return False

        # Clicar com safe_click (JS fallback)
        logger.info("   🖱️ Clicando botão Apply...")
        if not _safe_click(driver, external_btn):
            logger.warning(f"   ⚠️ Não conseguiu clicar no botão apply para {job.job_id}")
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_click_fail.png")
            return False

        time.sleep(3)

        # Verificar se abriu nova aba
        if len(driver.window_handles) > 1:
            logger.info("   🔀 Nova aba aberta, alternando...")
            driver.switch_to.window(driver.window_handles[-1])
            try:
                driver.maximize_window()
            except Exception:
                pass
            try:
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                logger.warning("   ⚠️ Timeout esperando página externa carregar")

        current_url = driver.current_url
        logger.info(f"   🔗 Redirecionado para: {current_url[:80]}")
        _take_screenshot(driver, ss_dir / f"external_{job.job_id}_page.png")

        # --- Navegar na página ATS: clicar "Apply"/"Candidatar-se" se existir ---
        filled = _navigate_ats_and_fill(driver, cover_letter, job.job_id, ss_dir)

        if filled:
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_filled.png")
            # Esperar 3s para página de confirmação carregar e capturar
            time.sleep(3)
            post_url = driver.current_url
            post_title = driver.title
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_CONFIRMATION.png")
            # Verificar se realmente submeteu (indicadores de sucesso)
            page_text = (driver.execute_script(
                "return document.body ? document.body.innerText.substring(0, 2000) : ''"
            ) or "").lower()
            success_indicators = [
                "thank", "obrigad", "sucesso", "success", "aplicação enviada",
                "application submitted", "candidatura enviada", "received",
                "recebemos", "confirma", "parabéns", "congratul",
                "inscrição realizada", "inscrição enviada",
            ]
            confirmed = any(kw in page_text for kw in success_indicators)
            logger.info(
                f"   📝 Formulário preenchido e submetido para {job.job_id}\n"
                f"      🔗 Pós-submit URL: {post_url[:100]}\n"
                f"      📄 Título: {post_title[:80]}\n"
                f"      {'✅ CONFIRMAÇÃO DETECTADA' if confirmed else '⚠️ SEM confirmação explícita'}\n"
                f"      📸 Screenshot: external_{job.job_id}_CONFIRMATION.png"
            )
        else:
            # Mesmo sem preencher, logar o que existe na página
            _log_unfilled_fields(driver, 0)
            _take_screenshot(driver, ss_dir / f"external_{job.job_id}_nofill.png")
            logger.info(f"   ⏭️ Formulário não preenchido — {current_url[:60]}")

        # Fechar aba extra se abriu
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(original_window)
            logger.info(f"   🔙 Aba extra fechada, voltando ao LinkedIn")

        return filled

    except Exception as e:
        logger.error(f"   ❌ Erro na candidatura externa {job.job_id}: {e}")
        _take_screenshot(driver, ss_dir / f"external_{job.job_id}_error.png")
        # Recuperar: fechar abas extras
        try:
            if len(driver.window_handles) > 1:
                for wh in driver.window_handles[1:]:
                    driver.switch_to.window(wh)
                    driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass
        return False


# ─── Senha padrão para cadastros ATS ─────────────────────────────────────────
ATS_DEFAULT_PASSWORD = os.environ.get("ATS_PASSWORD", "Shared@2026Secure!")


def _handle_ats_auth(
    driver: webdriver.Chrome,
    ss_dir: Path,
    job_id: str,
    ats_name: str,
    original_apply_url: str = "",
) -> bool:
    """Tenta login ou cadastro automático em sites ATS.

    Fluxo:
    1. Tenta login social (Google/LinkedIn) — mais rápido
    2. Tenta login com email/senha
    3. Se login falhar, procura link de cadastro e faz signup
    4. Retorna True se autenticou, False se não conseguiu

    Args:
        original_apply_url: URL da candidatura original para redirecionamento pós-signup.
    """
    logger.info(f"   🔐 ATS ({ats_name}) requer autenticação — tentando...")
    _take_screenshot(driver, ss_dir / f"external_{job_id}_ats_auth.png")

    login_email = os.environ.get("LINKEDIN_EMAIL", RESUME["email"])
    login_pass = os.environ.get("LINKEDIN_PASSWORD", "")
    ats_pass = ATS_DEFAULT_PASSWORD

    # ── PASSO 1: Tentar login social (Google/LinkedIn) ──
    social_btns = driver.find_elements(
        By.CSS_SELECTOR,
        "a[href*='google'], button[class*='google'], "
        "a[href*='linkedin'], button[class*='linkedin'], "
        "a[href*='oauth'], [data-provider='google'], "
        "[data-provider='linkedin'], "
        "button[data-testid*='social'], "
        "a[class*='social-login'], "
        "button[aria-label*='Google'], "
        "button[aria-label*='LinkedIn']",
    )
    for sb in social_btns:
        try:
            if sb.is_displayed():
                txt = (sb.text or '').lower()
                aria = (sb.get_attribute('aria-label') or '').lower()
                href = (sb.get_attribute('href') or '').lower()
                if any(kw in f"{txt} {aria} {href}" for kw in ['google', 'linkedin']):
                    provider = 'Google' if 'google' in f"{txt} {aria} {href}" else 'LinkedIn'
                    logger.info(f"   🔗 Tentando login social via {provider}...")
                    _safe_click(driver, sb)
                    time.sleep(5)
                    # Verificar se saiu da página de login
                    new_url = driver.current_url.lower()
                    if not any(kw in new_url for kw in ["signin", "login", "register", "signup"]):
                        logger.info(f"   ✅ Login social ({provider}) bem-sucedido!")
                        return True
                    logger.info(f"   ⚠️ Login social ({provider}) não completou — continuando")
                    break
        except Exception:
            continue

    # ── PASSO 2: Tentar login com email/senha ──
    filled_email = _fill_auth_email(driver, login_email)
    if filled_email:
        filled_pass = _fill_auth_password(driver, login_pass or ats_pass)
        if filled_pass:
            if _submit_auth_form(driver):
                time.sleep(5)
                new_url = driver.current_url.lower()
                if not any(kw in new_url for kw in ["signin", "login", "register", "signup", "error"]):
                    logger.info("   ✅ Login ATS bem-sucedido!")
                    return True
                logger.info("   ⚠️ Login falhou — tentando cadastro...")
        else:
            # Pode ser página que pede só email primeiro (Gupy faz isso)
            if _submit_auth_form(driver):
                time.sleep(3)
                new_url = driver.current_url.lower()
                # Se redirecionou para signup/register, é cadastro
                if any(kw in new_url for kw in ["signup", "register", "create", "cadastr"]):
                    logger.info("   📝 Redirecionado para cadastro — preenchendo...")
                    return _do_ats_signup(driver, ss_dir, job_id, login_email, ats_pass, ats_name, original_apply_url)
                elif not any(kw in new_url for kw in ["signin", "login"]):
                    logger.info("   ✅ Login ATS bem-sucedido (só email)!")
                    return True

    # ── PASSO 3: Procurar link de cadastro e fazer signup ──
    signup_link = _find_signup_link(driver)
    if signup_link:
        logger.info("   📝 Link de cadastro encontrado — navegando...")
        _safe_click(driver, signup_link)
        time.sleep(3)
        return _do_ats_signup(driver, ss_dir, job_id, login_email, ats_pass, ats_name, original_apply_url)

    # ── PASSO 4: Sem opção de login/cadastro — falhar ──
    logger.warning(f"   ❌ Não conseguiu autenticar no ATS ({ats_name})")
    _take_screenshot(driver, ss_dir / f"external_{job_id}_auth_fail.png")
    return False


def _fill_auth_email(driver: webdriver.Chrome, email: str) -> bool:
    """Preenche campo de email/username em formulário de autenticação."""
    selectors = [
        "input[name='username']", "input[type='email']",
        "input[name='email']", "input[id='email']",
        "input[id='username']", "input[autocomplete='email']",
        "input[autocomplete='username']",
        "input[placeholder*='mail']", "input[placeholder*='CPF']",
        "input[placeholder*='e-mail']", "input[placeholder*='Email']",
        "input[data-testid*='email']", "input[data-testid*='username']",
    ]
    for sel in selectors:
        fields = driver.find_elements(By.CSS_SELECTOR, sel)
        for f in fields:
            try:
                if f.is_displayed():
                    f.clear()
                    f.send_keys(email)
                    logger.info(f"   📧 Email: {email[:15]}...")
                    return True
            except Exception:
                continue
    return False


def _fill_auth_password(driver: webdriver.Chrome, password: str) -> bool:
    """Preenche campo de senha em formulário de autenticação."""
    if not password:
        return False
    for sel in ["input[type='password']", "input[name='password']",
                "input[id='password']", "input[autocomplete='current-password']",
                "input[autocomplete='new-password']"]:
        fields = driver.find_elements(By.CSS_SELECTOR, sel)
        for f in fields:
            try:
                if f.is_displayed():
                    f.clear()
                    f.send_keys(password)
                    logger.info("   🔑 Senha preenchida")
                    return True
            except Exception:
                continue
    return False


def _submit_auth_form(driver: webdriver.Chrome) -> bool:
    """Clica no botão submit do formulário de autenticação."""
    submit_selectors = [
        "button[type='submit']", "input[type='submit']",
        "button.btn-primary", "button[data-testid*='submit']",
        "button[data-testid*='login']", "button[data-testid*='signin']",
    ]
    for sel in submit_selectors:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        for btn in btns:
            try:
                if btn.is_displayed():
                    _safe_click(driver, btn)
                    logger.info(f"   🚀 Formulário submetido: '{(btn.text or '')[:20]}'")
                    return True
            except Exception:
                continue

    # Fallback: buscar por texto
    for tag in ["button", "a", "input"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                txt = (el.text or el.get_attribute("value") or "").lower().strip()
                if txt in ["entrar", "login", "sign in", "continuar", "continue",
                           "submit", "enviar", "acessar", "logar", "enter",
                           "cadastrar", "criar conta", "sign up", "register"]:
                    if el.is_displayed():
                        _safe_click(driver, el)
                        logger.info(f"   🚀 Botão '{txt}' clicado")
                        return True
            except Exception:
                continue
    return False


def _find_signup_link(driver: webdriver.Chrome) -> object | None:
    """Procura link/botão de cadastro na página de login do ATS."""
    signup_keywords = [
        "sign up", "signup", "register", "criar conta", "cadastr",
        "create account", "new account", "nova conta", "registr",
        "don't have an account", "não tem conta", "não possui conta",
        "first time", "primeira vez", "new user", "novo usuário",
    ]
    # Buscar links e botões
    for tag in ["a", "button", "span"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                txt = (el.text or "").lower().strip()
                href = (el.get_attribute("href") or "").lower()
                if any(kw in txt or kw in href for kw in signup_keywords):
                    if el.is_displayed() and len(txt) < 80:
                        logger.info(f"   📝 Link cadastro: '{txt[:30]}' → {href[:60]}")
                        return el
            except Exception:
                continue
    return None


def _do_ats_signup(
    driver: webdriver.Chrome,
    ss_dir: Path,
    job_id: str,
    email: str,
    password: str,
    ats_name: str,
    original_apply_url: str = "",
) -> bool:
    """Efetua cadastro automático em site ATS.

    Preenche nome, email, senha e campos adicionais usando dados do RESUME.
    Aceita termos de uso automaticamente.
    Se o cadastro redirecionar para página de profile, tenta voltar à URL original.
    """
    logger.info(f"   📋 Cadastro automático no {ats_name}...")
    time.sleep(2)
    _take_screenshot(driver, ss_dir / f"external_{job_id}_signup_page.png")

    # Mapear campos de cadastro -> valores
    signup_fields: list[tuple[list[str], str]] = [
        # Nome completo
        ([
            "input[name*='name' i]", "input[id*='name' i]",
            "input[placeholder*='nome' i]", "input[placeholder*='name' i]",
            "input[autocomplete='name']",
        ], RESUME["nome"]),
        # Primeiro nome
        ([
            "input[name*='firstName' i]", "input[name*='first_name' i]",
            "input[id*='firstName' i]", "input[placeholder*='primeiro' i]",
            "input[placeholder*='first' i]", "input[autocomplete='given-name']",
        ], RESUME["nome"].split()[0]),
        # Sobrenome
        ([
            "input[name*='lastName' i]", "input[name*='last_name' i]",
            "input[id*='lastName' i]", "input[placeholder*='sobrenome' i]",
            "input[placeholder*='last' i]", "input[autocomplete='family-name']",
        ], " ".join(RESUME["nome"].split()[1:])),
        # Email
        ([
            "input[type='email']", "input[name*='email' i]",
            "input[id*='email' i]", "input[autocomplete='email']",
            "input[placeholder*='mail' i]",
        ], email),
        # Telefone
        ([
            "input[type='tel']", "input[name*='phone' i]",
            "input[name*='telefone' i]", "input[id*='phone' i]",
            "input[placeholder*='telefone' i]", "input[placeholder*='phone' i]",
            "input[autocomplete='tel']",
        ], RESUME["telefone"]),
    ]

    filled_count = 0
    filled_fields: set[str] = set()

    # Preencher campos de texto
    for selectors, value in signup_fields:
        for sel in selectors:
            try:
                fields = driver.find_elements(By.CSS_SELECTOR, sel)
                for f in fields:
                    field_id = f.get_attribute("id") or f.get_attribute("name") or sel
                    if f.is_displayed() and field_id not in filled_fields:
                        # Verificar se campo já tem valor
                        current_val = f.get_attribute("value") or ""
                        if current_val.strip():
                            filled_fields.add(field_id)
                            continue
                        f.clear()
                        f.send_keys(value)
                        filled_fields.add(field_id)
                        filled_count += 1
                        logger.info(f"   ✏️ Campo '{field_id[:25]}' = '{value[:20]}...'")
                        break
            except Exception:
                continue

    # Preencher senha(s) — pode ter 2 campos (senha + confirmação)
    pass_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
    visible_pass = [f for f in pass_fields if f.is_displayed()]
    for pf in visible_pass:
        try:
            pf.clear()
            pf.send_keys(password)
            filled_count += 1
            logger.info("   🔑 Senha de cadastro preenchida")
        except Exception:
            continue

    # Aceitar termos/checkboxes obrigatórios
    checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for cb in checkboxes:
        try:
            if cb.is_displayed() and not cb.is_selected():
                # Verificar se é checkbox de termos/privacidade
                label = _get_field_label(driver, cb).lower()
                if any(kw in label for kw in [
                    "terms", "termos", "privacy", "privac", "lgpd",
                    "consent", "aceito", "agree", "concordo", "política",
                    "policy", "accept", "acknowledge",
                ]):
                    _safe_click(driver, cb)
                    filled_count += 1
                    logger.info(f"   ☑️ Checkbox aceito: '{label[:30]}'")
                elif not any(kw in label for kw in ["newsletter", "marketing", "promo"]):
                    # Aceitar checkboxes genéricos (exceto marketing)
                    _safe_click(driver, cb)
                    filled_count += 1
        except Exception:
            continue

    # Preencher campos adicionais com _fill_visible_fields (pega o resto)
    extra_filled = _fill_visible_fields(driver, "")
    filled_count += extra_filled

    logger.info(f"   📝 {filled_count} campos preenchidos no cadastro")
    _take_screenshot(driver, ss_dir / f"external_{job_id}_signup_filled.png")

    if filled_count < 2:
        logger.warning("   ⚠️ Poucos campos preenchidos — cadastro pode estar incompleto")

    # Submeter cadastro
    submitted = False
    # Buscar botão de cadastro específico
    signup_btn_texts = [
        "cadastrar", "cadastre-se", "criar conta", "create account", "sign up",
        "register", "registrar", "enviar", "submit", "continuar",
        "continue", "próximo", "next", "finalizar", "concluir",
        "avançar", "prosseguir", "salvar", "save",
    ]
    # Palavras que indicam login social (NÃO são submit de cadastro)
    social_exclusion = ["google", "linkedin", "facebook", "apple", "github", "microsoft"]
    for tag in ["button", "input", "a"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                txt = (el.text or el.get_attribute("value") or "").lower().strip()
                # Pular botões de login social
                if any(sw in txt for sw in social_exclusion):
                    continue
                if any(kw in txt for kw in signup_btn_texts) and el.is_displayed():
                    _safe_click(driver, el)
                    submitted = True
                    logger.info(f"   🚀 Cadastro submetido via '{txt[:25]}'")
                    break
            except Exception:
                continue
        if submitted:
            break

    if not submitted:
        # Fallback: botão submit genérico
        for sel in [
            "button[type='submit']", "input[type='submit']",
            "button[data-testid*='create']", "button[data-testid*='signup']",
            "button[data-testid*='register']", "button[data-testid*='submit']",
        ]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                try:
                    if btn.is_displayed():
                        txt = (btn.text or "").strip()
                        # Pular botões de login social mesmo no fallback
                        if any(sw in txt.lower() for sw in social_exclusion):
                            continue
                        _safe_click(driver, btn)
                        submitted = True
                        logger.info(f"   🚀 Cadastro submetido (submit genérico: '{txt[:25]}')")
                        break
                except Exception:
                    continue
            if submitted:
                break

    if not submitted:
        # Fallback 3: JS click em qualquer botão visível com texto de signup
        js_submit = driver.execute_script("""
            var keywords = ['cadastr', 'register', 'sign up', 'criar conta',
                            'create account', 'submit', 'enviar', 'continuar',
                            'avançar', 'prosseguir', 'salvar'];
            var social = ['google', 'linkedin', 'facebook', 'apple', 'github'];
            var btns = document.querySelectorAll('button, input[type="submit"], a[role="button"]');
            for (var i = 0; i < btns.length; i++) {
                var t = (btns[i].textContent || btns[i].value || '').trim().toLowerCase();
                if (t.length < 2 || t.length > 50) continue;
                var isSocial = false;
                for (var s = 0; s < social.length; s++) {
                    if (t.includes(social[s])) { isSocial = true; break; }
                }
                if (isSocial) continue;
                for (var j = 0; j < keywords.length; j++) {
                    if (t.includes(keywords[j]) && btns[i].offsetParent !== null) {
                        btns[i].click();
                        return t.substring(0, 30);
                    }
                }
            }
            return null;
        """)
        if js_submit:
            submitted = True
            logger.info(f"   🚀 Cadastro submetido via JS: '{js_submit}'")

    if not submitted:
        logger.warning("   ⚠️ Não encontrou botão de submit para cadastro")
        return False

    time.sleep(5)
    _take_screenshot(driver, ss_dir / f"external_{job_id}_signup_result.png")

    # Verificar resultado do cadastro
    new_url = driver.current_url.lower()
    page_text = driver.page_source.lower()

    # Verificar se há erro de "email já cadastrado"
    already_exists = any(kw in page_text for kw in [
        "already registered", "já cadastrado", "already exists",
        "já existe", "conta existente", "existing account",
        "already have an account", "já possui",
    ])
    if already_exists:
        logger.info("   ℹ️ Email já cadastrado — tentando login...")
        # Voltar para login e tentar com a senha padrão ATS
        back_link = _find_login_link(driver)
        if back_link:
            _safe_click(driver, back_link)
            time.sleep(3)
            _fill_auth_email(driver, email)
            _fill_auth_password(driver, password)
            if _submit_auth_form(driver):
                time.sleep(5)
                new_url2 = driver.current_url.lower()
                if not any(kw in new_url2 for kw in ["signin", "login", "register"]):
                    logger.info("   ✅ Login com senha ATS bem-sucedido!")
                    return True
        logger.warning("   ⚠️ Email já cadastrado e login falhou")
        return False

    # Verificar se cadastro precisa de confirmação por email
    email_confirm = any(kw in page_text for kw in [
        "check your email", "verifique seu email", "confirma",
        "verification", "verificação", "enviamos",
        "we sent", "confirm your", "activate your",
    ])
    if email_confirm:
        logger.info("   📧 ATS requer confirmação por email — aguardando 15s...")
        time.sleep(15)
        # Tentar continuar mesmo assim
        driver.refresh()
        time.sleep(3)

    # Verificar se saiu da página de cadastro
    if any(kw in new_url for kw in ["signup", "register", "login", "signin"]):
        # Verificar se há formulário multi-step (Gupy, Workday)
        if _handle_multi_page_form(driver, ""):
            logger.info("   ✅ Cadastro multi-step completado!")
            return True
        # BairesDev fix: após signup, tentar navegar de volta à URL original de candidatura
        if original_apply_url:
            logger.info(f"   🔄 Tentando voltar à URL de candidatura: {original_apply_url[:80]}")
            driver.get(original_apply_url)
            time.sleep(5)
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass
            nav_url = driver.current_url.lower()
            if not any(kw in nav_url for kw in ["signup", "register", "login", "signin"]):
                logger.info("   ✅ Sessão autenticada — formulário de candidatura acessível!")
                return True
            logger.warning(f"   ⚠️ Redireccionado novamente para auth: {nav_url[:60]}")
        logger.warning("   ⚠️ Ainda na página de cadastro após submit")
        return False

    logger.info(f"   ✅ Cadastro no {ats_name} aparentemente bem-sucedido!")
    return True


def _find_login_link(driver: webdriver.Chrome) -> object | None:
    """Procura link para voltar à página de login."""
    login_keywords = [
        "sign in", "signin", "login", "log in", "entrar",
        "já tenho conta", "already have", "fazer login",
    ]
    for tag in ["a", "button", "span"]:
        for el in driver.find_elements(By.TAG_NAME, tag):
            try:
                txt = (el.text or "").lower().strip()
                if any(kw in txt for kw in login_keywords) and el.is_displayed():
                    return el
            except Exception:
                continue
    return None


def _navigate_ats_and_fill(
    driver: webdriver.Chrome,
    cover_letter: str,
    job_id: str,
    ss_dir: Path,
) -> bool:
    """Navega pela página do ATS e preenche formulários de candidatura.

    Fluxo:
    1. Verifica se saiu do LinkedIn (senão, falha)
    2. Detecta ATS (Gupy, Greenhouse, Lever, etc.)
    3. Procura botão "Apply"/"Candidatar-se" na página de descrição do ATS
    4. Clica e espera formulário carregar
    5. Preenche campos (_fill_visible_fields)
    6. Navega multi-page se necessário
    """
    time.sleep(2)
    current_url = driver.current_url

    # ── Guard: se ainda estamos no LinkedIn, não é ATS ──
    if "linkedin.com" in current_url.lower():
        logger.info("   ⚠️ Ainda no LinkedIn — não é página ATS externa")

        # Tentar extrair URL externa via JS (LinkedIn armazena em data)
        ext_url_js = driver.execute_script("""
            // Buscar href em links com 'candidat'/'apply' que NÃO são linkedin
            var links = document.querySelectorAll('a[href]');
            for (var i = 0; i < links.length; i++) {
                var h = links[i].href || '';
                var t = (links[i].textContent || '').toLowerCase();
                if ((t.includes('candidat') || t.includes('apply')) &&
                    !h.includes('linkedin.com') && h.startsWith('http')) {
                    return h;
                }
            }
            // Buscar em códigos internos do LinkedIn
            var codes = document.querySelectorAll('code');
            for (var j = 0; j < codes.length; j++) {
                var c = codes[j].textContent || '';
                var m = c.match(/"(?:applyUrl|companyApplyUrl)"\s*:\s*"([^"]+)"/i);
                if (m) return m[1];
            }
            return null;
        """)
        if ext_url_js and 'linkedin.com' not in ext_url_js.lower():
            logger.info(f"   🔗 URL externa encontrada via JS: {ext_url_js[:80]}")
            driver.get(ext_url_js)
            time.sleep(3)
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass
            # Rechamar _navigate_ats_and_fill com a nova URL
            return _navigate_ats_and_fill(driver, cover_letter, job_id, ss_dir)

        # Verificar se abriu modal Easy Apply na mesma página
        modals = driver.find_elements(
            By.CSS_SELECTOR,
            ".artdeco-modal[role='dialog'], .jobs-easy-apply-modal, "
            "div[data-test-modal], div.artdeco-modal-overlay--visible, "
            "div[role='dialog']",
        )
        if modals:
            logger.info("   📋 Modal Easy Apply detectado na mesma página")
            filled = _fill_visible_fields(driver, cover_letter)
            if filled > 0:
                _try_submit_form(driver)
                return True
        return False

    # Detectar tipo de ATS
    url_lower = current_url.lower()
    ats_name = "Desconhecido"
    for pattern, name in [
        ("greenhouse", "Greenhouse"), ("lever", "Lever"),
        ("gupy", "Gupy"), ("workable", "Workable"),
        ("icims", "iCIMS"), ("workday", "Workday"),
        ("myworkday", "Workday"), ("smartrecruiters", "SmartRecruiters"),
        ("bamboohr", "BambooHR"), ("recruitee", "Recruitee"),
        ("breezy", "Breezy"),
    ]:
        if pattern in url_lower:
            ats_name = name
            break
    logger.info(f"   🏢 ATS detectado: {ats_name} ({current_url[:60]})")

    # Salvar URL original de candidatura para redirecionamento pós-signup
    _original_apply_url = current_url

    # Detectar página de login/cadastro (Gupy/Workday mostram login para candidatar)
    if any(kw in url_lower for kw in ["signin", "login", "register", "signup", "candidates/signin"]):
        ats_auth_ok = _handle_ats_auth(driver, ss_dir, job_id, ats_name, _original_apply_url)
        if not ats_auth_ok:
            return False

    # JS diagnostic: listar todos os botões apply/candidat na página
    apply_info = driver.execute_script("""
        var results = [];
        document.querySelectorAll('button, a, [role="button"]').forEach(function(el) {
            var txt = (el.textContent || '').trim().toLowerCase();
            if (txt.includes('apply') || txt.includes('candidat') || txt.includes('inscrever')) {
                results.push({
                    tag: el.tagName,
                    cls: (el.className || '').toString().substring(0, 80),
                    text: txt.substring(0, 40),
                    aria: (el.getAttribute('aria-label') || '').substring(0, 40),
                    vis: el.offsetParent !== null
                });
            }
        });
        return results;
    """)
    if apply_info:
        for info in apply_info[:5]:
            logger.info(
                f"   🔎 <{info['tag']} class='{info['cls'][:40]}'> "
                f"'{info['text'][:25]}' aria='{info['aria'][:25]}' visible={info['vis']}"
            )
    else:
        logger.info("   🔎 Nenhum botão apply/candidatar encontrado via JS")

    # ── Scroll até o topo para garantir visibilidade ──
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    # PASSO 1: Tentar preencher campos existentes na página atual
    filled = _fill_visible_fields(driver, cover_letter)

    if filled > 0:
        logger.info(f"   📝 {filled} campos preenchidos na página de descrição")
        _try_submit_form(driver)
        return True

    # PASSO 2: Procurar botão "Apply"/"Candidatar-se" na página ATS
    logger.info("   🔍 Buscando botão de candidatura na página ATS...")
    ats_apply_btn = None

    # Seletores comuns de ATS (combinados para velocidade)
    _ats_combined_sel = (
        "button[data-testid*='apply'], a[data-testid*='apply'], "
        "#submit_app, a#apply_button, "
        "a.postings-btn, a[data-qa='btn-apply'], "
        "a.js-apply-btn"
    )
    for btn in driver.find_elements(By.CSS_SELECTOR, _ats_combined_sel):
        if btn.is_displayed():
            ats_apply_btn = btn
            break

    # Fallback: busca por texto (excluir botões genéricos muito curtos)
    if not ats_apply_btn:
        apply_keywords = [
            "candidatar", "candidatura", "apply", "inscrever", "me candidatar",
            "quero me candidatar", "apply now", "apply for this job",
            "candidatar-se", "candidature", "postuler",
        ]
        for tag in ["button", "a"]:
            for el in driver.find_elements(By.TAG_NAME, tag):
                try:
                    txt = (el.text or "").lower().strip()
                    if len(txt) < 3 or len(txt) > 60:
                        continue
                    if any(kw in txt for kw in apply_keywords) and el.is_displayed():
                        ats_apply_btn = el
                        break
                except Exception:
                    continue
            if ats_apply_btn:
                break

    # Fallback 2: botões invisíveis — tentar JS click direto
    if not ats_apply_btn:
        invisible_btn = driver.execute_script("""
            var btns = document.querySelectorAll('button, a, [role="button"]');
            var keywords = ['candidat', 'apply', 'inscrever'];
            for (var i = 0; i < btns.length; i++) {
                var t = (btns[i].textContent || '').trim().toLowerCase();
                if (t.length >= 3 && t.length <= 60) {
                    for (var j = 0; j < keywords.length; j++) {
                        if (t.includes(keywords[j])) {
                            btns[i].click();
                            return t.substring(0, 30);
                        }
                    }
                }
            }
            return null;
        """)
        if invisible_btn:
            logger.info(f"   🖱️ JS click em botão invisível: '{invisible_btn}'")
            time.sleep(3)
            new_url = driver.current_url
            if new_url != url_lower:
                logger.info(f"   🔗 Navegou para: {new_url[:80]}")
            # Verificar se redireccionou para login
            if any(kw in new_url.lower() for kw in ["signin", "login", "register", "signup"]):
                auth_ok = _handle_ats_auth(driver, ss_dir, job_id, ats_name, _original_apply_url)
                if not auth_ok:
                    return False
                time.sleep(3)
            # Tentar preencher formulário após o clique
            filled = _fill_visible_fields(driver, cover_letter)
            if filled > 0:
                _try_submit_form(driver)
                return True
            return _handle_multi_page_form(driver, cover_letter)

    if ats_apply_btn:
        btn_text = (ats_apply_btn.text or "").strip()[:30]
        logger.info(f"   🖱️ Clicando '{btn_text}' na página ATS")
        pre_click_url = driver.current_url
        _safe_click(driver, ats_apply_btn)
        time.sleep(3)

        # Verificar se abriu nova aba/modal/página
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass

        new_url = driver.current_url
        if new_url != pre_click_url:
            logger.info(f"   🔗 Navegou para: {new_url[:80]}")

        # Verificar se agora é uma página de login → tentar autenticação automática
        if any(kw in new_url.lower() for kw in ["signin", "login", "register", "signup", "cadastr"]):
            logger.info("   🔐 ATS redireccionou para login — tentando autenticação...")
            _take_screenshot(driver, ss_dir / f"external_{job_id}_login.png")
            auth_ok = _handle_ats_auth(driver, ss_dir, job_id, ats_name, _original_apply_url)
            if not auth_ok:
                return False
            # Após auth bem-sucedida, aguardar redirect do ATS
            time.sleep(5)
            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass
            logger.info(f"   🔗 Pós-auth URL: {driver.current_url[:80]}")
            # Se ainda em login, tentar navegar para a URL original do ATS
            post_auth = driver.current_url.lower()
            if any(kw in post_auth for kw in ["signin", "login"]):
                logger.info("   🔄 Ainda em login — retornando à URL do ATS")
                driver.get(pre_click_url)
                time.sleep(3)

        _take_screenshot(driver, ss_dir / f"external_{job_id}_ats_form.png")

        # PASSO 3: Preencher formulário na nova página
        filled2 = _fill_visible_fields(driver, cover_letter)
        if filled2 > 0:
            logger.info(f"   📝 {filled2} campos preenchidos no formulário ATS")
            _try_submit_form(driver)
            return True

        # PASSO 4: Tentar multi-page
        logger.info("   📋 Tentando formulário multi-página...")
        if _handle_multi_page_form(driver, cover_letter):
            return True

    else:
        logger.info("   ⚠️ Sem botão apply na página ATS — tentando multi-page...")
        if _handle_multi_page_form(driver, cover_letter):
            return True

    return False


def _try_fill_generic_form(driver: webdriver.Chrome, cover_letter: str) -> bool:
    """Preenche formulários genéricos de candidatura (ATS diversos).

    Suporta Greenhouse, Lever, Gupy, Workable, iCIMS, Workday e forms genéricos.
    Lê labels de cada campo para inferir o valor correto.
    """
    # Esperar o form carregar
    time.sleep(2)

    # Detectar ATS e logar
    current_url = driver.current_url.lower()
    ats_name = "Desconhecido"
    if "greenhouse" in current_url or "boards.greenhouse" in current_url:
        ats_name = "Greenhouse"
    elif "lever" in current_url or "jobs.lever" in current_url:
        ats_name = "Lever"
    elif "gupy" in current_url:
        ats_name = "Gupy"
    elif "workable" in current_url:
        ats_name = "Workable"
    elif "icims" in current_url:
        ats_name = "iCIMS"
    elif "workday" in current_url or "myworkday" in current_url:
        ats_name = "Workday"
    elif "smartrecruiters" in current_url:
        ats_name = "SmartRecruiters"
    logger.info(f"   🏢 ATS detectado: {ats_name} ({current_url[:60]})")

    # Usar preenchimento inteligente unificado
    filled = _fill_visible_fields(driver, cover_letter)

    # Tentar clicar em botão submit/apply no formulário externo
    if filled > 0:
        _try_submit_form(driver)

    return filled > 0


def _try_submit_form(driver: webdriver.Chrome) -> bool:
    """Tenta enviar formulário externo clicando em botões submit."""
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button[data-qa='btn-submit']",
        "button.btn-submit",
        "button#submit",
        "a.btn-submit",
    ]
    # Também procura por texto nos botões
    submit_texts = [
        "submit", "enviar", "apply", "candidatar", "inscrever",
        "send", "confirmar", "confirm", "next", "avançar", "continuar",
    ]

    # Tentar seletores CSS diretos — combinados para velocidade
    _all_submit = (
        "button[type='submit'], input[type='submit'], "
        "button[data-qa='btn-submit'], button.btn-submit, "
        "button#submit, a.btn-submit"
    )
    for btn in driver.find_elements(By.CSS_SELECTOR, _all_submit):
            if btn.is_displayed():
                logger.info(f"      🚀 Clicando submit: '{btn.text[:30]}'")
                _safe_click(driver, btn)
                time.sleep(2)
                return True

    # Tentar por texto do botão
    for tag in ["button", "a", "input"]:
        elements = driver.find_elements(By.TAG_NAME, tag)
        for el in elements:
            try:
                txt = (el.text or el.get_attribute("value") or "").lower().strip()
                if any(kw in txt for kw in submit_texts) and el.is_displayed():
                    logger.info(f"      🚀 Submit via texto: '{txt[:30]}'")
                    _safe_click(driver, el)
                    time.sleep(2)
                    return True
            except Exception:
                continue

    return False


def _handle_multi_page_form(driver: webdriver.Chrome, cover_letter: str, max_pages: int = 8) -> bool:
    """Navega por formulários multi-página preenchendo cada step.

    Útil para ATS como Greenhouse, Workday que dividem em várias telas.
    Retorna True somente se pelo menos 1 campo foi preenchido E submit enviado.
    """
    total_filled = 0
    for page in range(max_pages):
        logger.info(f"      📄 Form página {page + 1}...")
        time.sleep(1.5)

        # Preencher campos da página atual
        filled = _fill_visible_fields(driver, cover_letter)
        total_filled += filled
        logger.info(f"      📝 {filled} campos preenchidos nesta página")

        # Verificar erros de validação
        _handle_validation_errors(driver, cover_letter)

        # Procurar botão Submit (fim do form) — seletores combinados
        submit_found = False
        _submit_sel = (
            "button[type='submit'], button[aria-label*='Submit'], "
            "button[aria-label*='Enviar'], input[type='submit']"
        )
        for btn in driver.find_elements(By.CSS_SELECTOR, _submit_sel):
            txt = (btn.text or btn.get_attribute("value") or "").lower()
            if any(kw in txt for kw in ["submit", "enviar", "apply", "candidatar"]):
                if total_filled == 0:
                    logger.info(f"      ⚠️ Submit '{txt[:20]}' encontrado mas 0 campos preenchidos — ignorando")
                    return False
                submit_found = True
                logger.info(f"      🚀 Submit: '{txt[:20]}' ({total_filled} campos preenchidos)")
                _safe_click(driver, btn)
                time.sleep(3)
                return True

        # Procurar botão Next/Continue — seletores combinados
        next_btn = None
        _next_sel = (
            "button[data-qa='btn-next'], button[aria-label*='Next'], "
            "button[aria-label*='Avançar'], button[aria-label*='Continue']"
        )
        for btn in driver.find_elements(By.CSS_SELECTOR, _next_sel):
            if btn.is_displayed():
                next_btn = btn
                break

        # Fallback: procurar por texto
        if not next_btn:
            for tag in ["button", "a"]:
                for el in driver.find_elements(By.TAG_NAME, tag):
                    txt = (el.text or "").lower().strip()
                    if txt in ["next", "avançar", "continue", "continuar", "próximo"]:
                        if el.is_displayed():
                            next_btn = el
                            break
                if next_btn:
                    break

        if next_btn:
            _safe_click(driver, next_btn)
            time.sleep(2)
        else:
            # Sem next nem submit — formulário pode ser single-page
            if total_filled > 0 and _try_submit_form(driver):
                return True
            break

    return False


def _handle_validation_errors(
    driver: webdriver.Chrome,
    cover_letter: str,
    job: "LinkedInJob | None" = None,
) -> None:
    """Detecta e tenta corrigir erros de validação no formulário."""
    # Procurar mensagens de erro
    error_selectors = (
        ".field-error, .error-message, .form-error, "
        "[role='alert'], .artdeco-inline-feedback--error, "
        ".validation-error, .has-error, .is-invalid, "
        ".fb-form-message--is-error"
    )
    errors = driver.find_elements(By.CSS_SELECTOR, error_selectors)
    for err in errors:
            try:
                if not err.is_displayed():
                    continue
                err_text = err.text.strip().lower()
                if not err_text:
                    continue
                logger.info(f"      ⚠️ Erro de validação: '{err_text[:60]}'")

                # Tentar encontrar o campo associado ao erro
                # Subir no DOM até encontrar um input/select vazio
                parent = err
                for _ in range(5):
                    parent = parent.find_element(By.XPATH, "..")
                    inputs = parent.find_elements(
                        By.CSS_SELECTOR,
                        "input:not([type='hidden']):not([type='file']), select, textarea",
                    )
                    for inp in inputs:
                        if inp.is_displayed():
                            val = inp.get_attribute("value") or ""
                            if not val.strip():
                                label = _get_field_label(driver, inp)
                                value = _infer_value(label, cover_letter, job=job)
                                if value:
                                    inp.clear()
                                    inp.send_keys(value)
                                    logger.info(f"      🔧 Corrigido: '{label[:30]}' → '{value[:20]}'")
                                    time.sleep(0.3)
                            break
                    if inputs:
                        break
            except Exception:
                pass


def _take_screenshot(driver: webdriver.Chrome, path: Path) -> None:
    """Salva screenshot."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(str(path))
    except Exception:
        pass


# ─── Cover Letter ────────────────────────────────────────────────────────────
def generate_cover_letter(job: LinkedInJob, compat: dict) -> str:
    """Gera carta de apresentação baseada no template (sem LLM)."""
    matched_str = ", ".join(compat["matched"][:8]) if compat["matched"] else "infraestrutura e automação"

    pcd_line = ""
    if RESUME.get("pcd"):
        pcd_line = "\nSou pessoa com deficiência (PCD) e estou à disposição para informações adicionais.\n"

    letter = f"""Olá,

Vi a vaga de {job.title} na {job.company or 'empresa'} e me identifiquei com o perfil.

Tenho experiência sólida como desenvolvedor e especialista em operações, com vivência em {matched_str}. Atuo há mais de 15 anos na área de tecnologia, com passagem por grandes empresas do mercado financeiro e tecnologia, sempre com foco em escalabilidade, qualidade de código e boas práticas.
{pcd_line}
Fico à disposição para conversar sobre a oportunidade.

Abraços,
{RESUME['nome']}
{RESUME['telefone']}
{RESUME['email']}"""

    return letter.strip()


# ─── Persistência ────────────────────────────────────────────────────────────
def load_applied_jobs() -> set[str]:
    """Carrega IDs de vagas já candidatadas."""
    if not APPLIED_FILE.exists():
        return set()
    try:
        data = json.loads(APPLIED_FILE.read_text(encoding="utf-8"))
        return set(data.get("job_ids", []))
    except (json.JSONDecodeError, FileNotFoundError):
        return set()


def save_applied_job(job: LinkedInJob) -> None:
    """Salva ID da vaga como candidatada."""
    applied = load_applied_jobs()
    applied.add(job.job_id)

    APPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPLIED_FILE.write_text(
        json.dumps({"job_ids": list(applied), "updated": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )


# ─── Pipeline Principal ─────────────────────────────────────────────────────
async def run_scanner(
    keywords: list[str] | None = None,
    remote_only: bool = True,
    min_score: float = MIN_COMPAT_SCORE,
    max_apply: int = MAX_APPLY,
    dry_run: bool = False,
    headed: bool = False,
    chrome_profile: bool = False,
) -> list[LinkedInJob]:
    """Pipeline principal: busca, filtra, candidata e notifica."""
    logger.info("🚀 LinkedIn Job Scanner iniciado")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = DATA_DIR / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)

    # Carregar currículo
    cv_text = download_cv_from_drive()
    if cv_text:
        logger.info(f"📄 Currículo carregado: {len(cv_text)} caracteres")

    # Keywords de busca
    search_keywords = keywords or DEFAULT_SEARCH_KEYWORDS
    logger.info(f"🔍 Keywords: {', '.join(search_keywords)}")
    logger.info(f"🏠 Preferência: {'Remote/Home Office' if remote_only else 'Todos'}")
    logger.info(f"📊 Score mínimo: {min_score}%")

    # NOTA: driver Chrome é criado SOMENTE quando necessário (candidatura)
    # Isso evita Chrome ocioso durante análise que pode crashar
    driver: webdriver.Chrome | None = None

    try:
        # Fase 1: Buscar vagas via API pública (sem login)
        logger.info("📡 Buscando vagas via páginas públicas (sem login)...")
        jobs = await search_linkedin_jobs_public(
            search_keywords, remote_only=remote_only,
        )

        # Se não encontrou vagas públicas, tentar com login
        if not jobs:
            logger.info("🔑 Tentando busca com login no LinkedIn...")
            driver = create_driver(headed=headed, chrome_profile=chrome_profile)
            if linkedin_login(driver):
                jobs = search_linkedin_jobs(
                    driver, search_keywords, remote_only=remote_only,
                )
            else:
                logger.warning("⚠️ Login falhou, continuando com resultados públicos")

        if not jobs:
            logger.info("📭 Nenhuma vaga encontrada")
            await send_telegram("📭 *LinkedIn Scanner*: Nenhuma vaga encontrada com os filtros atuais.")
            return []

        # Filtrar vagas já candidatadas
        applied_ids = load_applied_jobs()
        new_jobs = [j for j in jobs if j.job_id not in applied_ids]
        logger.info(f"📋 {len(new_jobs)} vagas novas (excluindo {len(jobs) - len(new_jobs)} já candidatadas)")

        # Deduplicar por título+empresa (evitar Mindrift x5)
        dedup_key: set[str] = set()
        unique_jobs: list[LinkedInJob] = []
        for j in new_jobs:
            key = f"{j.title.lower().strip()}|{j.company.lower().strip()}"
            if key not in dedup_key:
                dedup_key.add(key)
                unique_jobs.append(j)
            else:
                logger.info(f"   🔄 Duplicada removida: {j.title} @ {j.company}")
        new_jobs = unique_jobs
        logger.info(f"📋 {len(new_jobs)} vagas únicas após deduplicação")

        # Filtrar elegibilidade (nível + exclusividade) antes de buscar detalhes
        eligible_jobs: list[LinkedInJob] = []
        for job in new_jobs:
            eligible, reason = filter_job_eligibility(job)
            if eligible:
                eligible_jobs.append(job)
            else:
                logger.info(f"   🚫 Filtrada: {job.title} @ {job.company} — {reason}")
        logger.info(f"📋 {len(eligible_jobs)} vagas elegíveis (excluindo {len(new_jobs) - len(eligible_jobs)} por nível/exclusividade)")

        # Obter detalhes e calcular compatibilidade
        compatible_jobs: list[LinkedInJob] = []
        for i, job in enumerate(eligible_jobs):
            try:
                logger.info(f"📄 [{i + 1}/{len(eligible_jobs)}] Analisando: {job.title} @ {job.company}")
                job = await get_job_details_public(job)

                # Re-verificar elegibilidade após obter descrição completa
                eligible, reason = filter_job_eligibility(job)
                if not eligible:
                    logger.info(f"   🚫 Filtrada após detalhes: {reason}")
                    continue

                compat = calculate_compatibility(job)
                job.compatibility_score = compat["score"]
                job.matched_skills = compat["matched"]
                job.missing_skills = compat["missing"]

                if job.compatibility_score >= min_score:
                    compatible_jobs.append(job)
                    logger.info(
                        f"   ✅ Score: {job.compatibility_score}% — "
                        f"Match: {', '.join(compat['matched'][:5])}"
                    )
                else:
                    logger.info(f"   ⏭️ Score: {job.compatibility_score}% (abaixo de {min_score}%)")
            except Exception as e:
                logger.warning(f"   ⚠️ Erro ao analisar {job.title}: {e} — pulando")
                continue

            time.sleep(SEARCH_DELAY)

        # Ordenar por score (maior primeiro)
        compatible_jobs.sort(key=lambda j: j.compatibility_score, reverse=True)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  📊 {len(compatible_jobs)} vagas compatíveis (≥{min_score}%)")
        logger.info(f"{'=' * 60}")

        for j in compatible_jobs:
            remote_tag = "🏠 Remote" if j.is_remote else "🏢 Presencial/Híbrido"
            easy_tag = "⚡ Easy Apply" if j.is_easy_apply else "🔗 External"
            logger.info(
                f"  [{j.compatibility_score}%] {j.title} @ {j.company} "
                f"| {remote_tag} | {easy_tag}"
            )

        # Enviar resumo por Telegram
        summary_lines = [f"🔍 *LinkedIn Scanner — {len(compatible_jobs)} vagas compatíveis*\n"]
        for j in compatible_jobs[:15]:
            remote_icon = "🏠" if j.is_remote else "🏢"
            summary_lines.append(
                f"{remote_icon} *{j.title}* @ {j.company}\n"
                f"   Score: {j.compatibility_score}% | {j.location}\n"
            )
        await send_telegram("\n".join(summary_lines))

        if dry_run:
            logger.info("🏁 Modo dry-run: nenhuma candidatura enviada")
            # Salvar relatório
            _save_session(session_dir, compatible_jobs)
            return compatible_jobs

        # Login OBRIGATÓRIO antes de qualquer candidatura
        # LinkedIn bloqueia interação com botões apply em páginas públicas
        logger.info("🔑 Login obrigatório para candidaturas — fazendo login...")
        if driver is None:
            driver = create_driver(headed=headed, chrome_profile=chrome_profile)
        logged_in = linkedin_login(driver)
        if not logged_in:
            logger.error("❌ Login falhou — candidaturas impossíveis sem autenticação")
            await send_telegram(
                "⚠️ *LinkedIn Scanner*: Login falhou.\n"
                "Candidaturas não enviadas. Execute novamente com `--headed` "
                "e faça login manual no navegador."
            )
            _save_session(session_dir, compatible_jobs)
            return compatible_jobs

        logger.info("✅ Logado no LinkedIn — iniciando candidaturas")

        # Candidatar-se às vagas (detecção de Easy Apply feita inline)
        applied_count = 0
        crash_count = 0
        MAX_CRASHES = 5

        # Handler para timeout por job (signal.alarm)
        class _JobTimeout(Exception):
            pass

        def _alarm_handler(signum: int, frame: object) -> None:
            raise _JobTimeout("Timeout atingido para candidatura")

        old_handler = signal.signal(signal.SIGALRM, _alarm_handler)

        for job in compatible_jobs:
            if applied_count >= max_apply:
                logger.info(f"🛑 Limite de {max_apply} candidaturas atingido")
                break

            logger.info(
                f"\n🎯 Candidatando: {job.title} @ {job.company} "
                f"(score: {job.compatibility_score}%)"
            )

            cover_letter = generate_cover_letter(job, {
                "matched": job.matched_skills,
                "missing": job.missing_skills,
            })
            logger.info(f"   📝 Cover letter gerada ({len(cover_letter)} chars)")

            success = False
            try:
                # Timeout por job — evita bloqueio permanente
                signal.alarm(JOB_APPLY_TIMEOUT)

                # Navegar para a vaga e detectar tipo de botão inline
                logger.info(f"   🌐 Navegando para: {job.url}")
                try:
                    driver.get(job.url)
                    logger.info("   ✅ Página carregada")
                except Exception as nav_err:
                    logger.warning(f"   ⚠️ Timeout ao carregar página: {nav_err}")
                    continue
                time.sleep(4)
                logger.info("   🔍 Verificando overlays...")
                _dismiss_overlays(driver)

                # ── Login Gate Detection ──
                # LinkedIn mostra página de guest/login-wall para sessões expiradas.
                # Sintomas: viewport menor (1280x593), authwall, sign-in overlay.
                _is_login_gate = driver.execute_script("""
                    // Checar elementos típicos de login gate
                    var authWall = document.querySelector(
                        '.authwall-join-form, #join-form, .sign-in-modal, '
                        + '[data-tracking-control-name="public_jobs_topcard-sign-in-redirect"], '
                        + '.contextual-sign-in-modal, #base-contextual-sign-in-modal, '
                        + '.nav__button-secondary[data-tracking-control-name="guest_homepage-basic_sign-in-button"]'
                    );
                    if (authWall) return 'authwall';
                    // Checar se a URL é de guest/public
                    var url = window.location.href.toLowerCase();
                    if (url.includes('/pub/') || url.includes('authwall'))
                        return 'url';
                    // Checar se há botão "Sign in" ou "Entrar" proeminente no topo
                    var navBtns = document.querySelectorAll('nav a, nav button, header a, header button');
                    for (var i = 0; i < navBtns.length; i++) {
                        var t = (navBtns[i].textContent || '').trim().toLowerCase();
                        if ((t === 'sign in' || t === 'entrar' || t === 'join now')
                            && navBtns[i].offsetParent !== null) {
                            return 'nav-signin:' + t;
                        }
                    }
                    return null;
                """)
                if _is_login_gate:
                    logger.warning(f"   🚧 Login gate detectado ({_is_login_gate}) — re-autenticando...")
                    _take_screenshot(driver, ss_dir / f"login_gate_{job.job_id}.png")
                    # Re-fazer login no LinkedIn
                    _relogin_ok = False
                    try:
                        driver.get(f"{LINKEDIN_BASE}/login")
                        time.sleep(2)
                        # Tentar login automático
                        _li_email = os.environ.get("LINKEDIN_EMAIL", "")
                        _li_pass = os.environ.get("LINKEDIN_PASSWORD", "")
                        if _li_email and _li_pass:
                            try:
                                _ef = WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.ID, "username"))
                                )
                                _ef.clear()
                                _ef.send_keys(_li_email)
                                _pf = driver.find_element(By.ID, "password")
                                _pf.clear()
                                _pf.send_keys(_li_pass)
                                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                                time.sleep(5)
                                if "/feed" in driver.current_url or "/mynetwork" in driver.current_url:
                                    logger.info("   ✅ Re-login LinkedIn bem-sucedido!")
                                    save_cookies(driver)
                                    _relogin_ok = True
                            except Exception as login_err:
                                logger.warning(f"   ⚠️ Re-login falhou: {login_err}")
                        # Se re-login OK, re-navegar para a vaga
                        if _relogin_ok:
                            logger.info(f"   🔄 Re-navegando para: {job.url}")
                            driver.get(job.url)
                            time.sleep(4)
                            _dismiss_overlays(driver)
                        else:
                            logger.warning("   ⚠️ Re-login falhou — tentando mesmo assim")
                    except Exception as relogin_err:
                        logger.warning(f"   ⚠️ Erro no re-login: {relogin_err}")

                # Esperar mais para o LinkedIn renderizar os botões via JS
                time.sleep(2)

                # Detectar vagas expiradas/fechadas — buscar no body inteiro
                expired_check = driver.execute_script("""
                    var bodyText = (document.body.innerText || '').toLowerCase();
                    // Indicadores de vaga fechada/lotada (ordem de especificidade)
                    var indicators = [
                        'no longer accepting',
                        'não aceita mais',
                        'esta vaga não está mais',
                        'vaga encerrada',
                        'vaga fechada',
                        'position has been filled',
                        'this job is no longer',
                        'job is closed',
                        'aplicações encerradas'
                    ];
                    for (var i = 0; i < indicators.length; i++) {
                        if (bodyText.includes(indicators[i])) {
                            return indicators[i];
                        }
                    }
                    // Verificar banners/alertas de vaga expirada (seletores clássicos + modernos)
                    var closedBanners = document.querySelectorAll(
                        '.closed-job, .jobs-details-top-card__closed-notice, ' +
                        '[data-test-id="job-closed"], .job-closed-message, ' +
                        '[class*="closed"], [class*="expired"]'
                    );
                    for (var j = 0; j < closedBanners.length; j++) {
                        var t = (closedBanners[j].textContent || '').toLowerCase();
                        if (t.includes('não aceita') || t.includes('no longer') ||
                            t.includes('encerrad') || t.includes('fechad') ||
                            t.includes('closed') || t.includes('expired')) {
                            return t.trim().substring(0, 60);
                        }
                    }
                    return null;
                """)
                if expired_check:
                    logger.info(f"   ⏭️ Vaga fechada/expirada: '{expired_check}'")
                    continue

                # Scroll agressivo para trigger lazy-loading de botões
                driver.execute_script("""
                    window.scrollTo(0, document.body.scrollHeight / 3);
                    setTimeout(function() { window.scrollTo(0, 0); }, 500);
                """)
                time.sleep(2)

                # JS diagnostic: encontrar QUALQUER elemento com "apply"/"candidat"
                js_apply_info = driver.execute_script("""
                    var r = [];
                    document.querySelectorAll('button, a, [role="button"], span')
                        .forEach(function(el) {
                            var t = (el.textContent || '').trim().toLowerCase();
                            if (t.includes('apply') || t.includes('candidat')) {
                                r.push({
                                    tag: el.tagName,
                                    cls: (el.className||'').toString().substring(0,60),
                                    txt: t.substring(0,30),
                                    aria: (el.getAttribute('aria-label')||'').substring(0,30),
                                    vis: el.offsetParent !== null,
                                    href: (el.getAttribute('href')||'').substring(0,60)
                                });
                            }
                        });
                    return r.slice(0, 8);
                """)
                if js_apply_info:
                    for info in js_apply_info[:3]:
                        logger.info(
                            f"   🔎 JS: <{info['tag']}> cls='{info['cls'][:30]}' "
                            f"txt='{info['txt'][:20]}' aria='{info['aria'][:20]}' "
                            f"vis={info['vis']}"
                        )

                # Detectar Easy Apply — seletores amplos + filtro por aria-label
                all_apply_btns = driver.find_elements(
                    By.CSS_SELECTOR,
                    "button.jobs-apply-button, "
                    "button.jobs-apply-button--top-card, "
                    "a.jobs-apply-button, "
                    "a.jobs-apply-button--top-card, "
                    "button[aria-label*='Easy Apply'], "
                    "button[aria-label*='Candidatura simplificada'], "
                    "button[aria-label*='Candidatura'], "
                    "button[aria-label*='Apply'], "
                    "button[aria-label*='Candidatar'], "
                    "a[aria-label*='Candidatar'], "
                    "a[aria-label*='Candidatura'], "
                    "a[aria-label*='Apply'], "
                    "a[data-tracking-control-name*='apply']",
                )

                # FALLBACK: se CSS não achou, usar JS p/ buscar por texto
                if not all_apply_btns:
                    logger.info("   🔍 CSS falhou, buscando botões por texto via JS...")
                    js_btns = driver.execute_script("""
                        var found = [];
                        document.querySelectorAll('button, a, [role="button"]').forEach(function(el) {
                            var t = (el.textContent || '').trim().toLowerCase();
                            var a = (el.getAttribute('aria-label') || '').toLowerCase();
                            if ((t.includes('apply') || t.includes('candidat') || t.includes('inscrever')
                                 || a.includes('apply') || a.includes('candidat'))
                                && el.offsetParent !== null) {
                                found.push(el);
                            }
                        });
                        return found.slice(0, 5);
                    """)
                    if js_btns:
                        all_apply_btns = js_btns
                        logger.info(f"   ✅ JS encontrou {len(js_btns)} botão(ões)")

                # FALLBACK 2: extrair href externo via JS do data store do LinkedIn
                external_apply_url = None
                if not all_apply_btns:
                    logger.info("   🔍 Extraindo URL de apply via JS...")
                    external_apply_url = driver.execute_script("""
                        // Tentar extrair URL de apply de <a> com 'candidat' ou 'apply'
                        var links = document.querySelectorAll('a[href]');
                        for (var i = 0; i < links.length; i++) {
                            var t = (links[i].textContent || '').toLowerCase();
                            var h = links[i].href || '';
                            if ((t.includes('candidat') || t.includes('apply'))
                                && !h.includes('linkedin.com/login')
                                && h.length > 10) {
                                return h;
                            }
                        }
                        // Tentar pegar de dados internos do LinkedIn
                        var codes = document.querySelectorAll('code');
                        for (var j = 0; j < codes.length; j++) {
                            var txt = codes[j].textContent || '';
                            if (txt.includes('applyUrl') || txt.includes('companyApplyUrl')) {
                                var m = txt.match(/"(?:applyUrl|companyApplyUrl)"\s*:\s*"([^"]+)"/i);
                                if (m) return m[1];
                            }
                        }
                        return null;
                    """)
                    if external_apply_url:
                        logger.info(f"   🔗 URL de apply extraída: {external_apply_url[:80]}")

                easy_btns = [
                    btn for btn in all_apply_btns
                    if hasattr(btn, 'get_attribute') and
                    any(kw in (
                        (btn.get_attribute("aria-label") or "") + " " +
                        (btn.text or "")
                    ).lower()
                        for kw in ["easy apply", "candidatura simplificada"])
                ]
                job.is_easy_apply = len(easy_btns) > 0
                has_any_apply = len(all_apply_btns) > 0
                logger.info(
                    f"   🔍 Tipo: {'Easy Apply' if job.is_easy_apply else 'External'}"
                    f" ({len(all_apply_btns)} botões encontrados)"
                )

                if job.is_easy_apply:
                    success = apply_easy_apply(driver, job, cover_letter, session_dir)
                elif has_any_apply or external_apply_url:
                    success = apply_external(
                        driver, job, cover_letter, session_dir,
                        _apply_btn=all_apply_btns[0] if has_any_apply else None,
                        _external_url=external_apply_url,
                    )
                else:
                    # ── RETRY: recarregar e tentar uma vez mais ──
                    logger.info("   🔄 Nenhum botão — retry: recarregando página...")
                    driver.refresh()
                    time.sleep(5)
                    _dismiss_overlays(driver)
                    time.sleep(2)
                    # Scroll novamente
                    driver.execute_script("""
                        window.scrollTo(0, document.body.scrollHeight / 3);
                        setTimeout(function() { window.scrollTo(0, 0); }, 500);
                    """)
                    time.sleep(2)
                    # Tentar detectar botões novamente (CSS + JS)
                    retry_btns = driver.find_elements(
                        By.CSS_SELECTOR,
                        "button.jobs-apply-button, a.jobs-apply-button, "
                        "button[aria-label*='Apply'], button[aria-label*='Candidatar'], "
                        "a[aria-label*='Candidatar'], a[aria-label*='Apply'], "
                        "a[data-tracking-control-name*='apply']",
                    )
                    if not retry_btns:
                        retry_btns = driver.execute_script("""
                            var found = [];
                            document.querySelectorAll('button, a, [role="button"]').forEach(function(el) {
                                var t = (el.textContent || '').trim().toLowerCase();
                                var a = (el.getAttribute('aria-label') || '').toLowerCase();
                                if ((t.includes('apply') || t.includes('candidat') || t.includes('inscrever')
                                     || a.includes('apply') || a.includes('candidat'))
                                    && el.offsetParent !== null) {
                                    found.push(el);
                                }
                            });
                            return found.slice(0, 5);
                        """) or []
                    # Tentar extrair URL externa também
                    if not retry_btns:
                        retry_ext_url = driver.execute_script("""
                            var links = document.querySelectorAll('a[href]');
                            for (var i = 0; i < links.length; i++) {
                                var t = (links[i].textContent || '').toLowerCase();
                                var h = links[i].href || '';
                                if ((t.includes('candidat') || t.includes('apply'))
                                    && !h.includes('linkedin.com/login') && h.length > 10) {
                                    return h;
                                }
                            }
                            var codes = document.querySelectorAll('code');
                            for (var j = 0; j < codes.length; j++) {
                                var txt = codes[j].textContent || '';
                                if (txt.includes('applyUrl') || txt.includes('companyApplyUrl')) {
                                    var m = txt.match(/"(?:applyUrl|companyApplyUrl)"\\s*:\\s*"([^"]+)"/i);
                                    if (m) return m[1];
                                }
                            }
                            return null;
                        """)
                        if retry_ext_url:
                            logger.info(f"   🔗 Retry: URL de apply extraída: {retry_ext_url[:80]}")
                            success = apply_external(
                                driver, job, cover_letter, session_dir,
                                _apply_btn=None,
                                _external_url=retry_ext_url,
                            )
                        else:
                            logger.info(f"   ⏭️ Nenhum botão de candidatura encontrado (retry esgotado)")
                            _take_screenshot(driver, session_dir / f"no_btn_{job.job_id}.png")
                    else:
                        logger.info(f"   ✅ Retry encontrou {len(retry_btns)} botão(ões)!")
                        # Classificar botões encontrados
                        retry_easy = [
                            b for b in retry_btns
                            if hasattr(b, 'get_attribute') and
                            any(kw in (b.get_attribute("aria-label") or "").lower()
                                for kw in ["easy apply", "candidatura simplificada"])
                        ]
                        if retry_easy:
                            success = apply_easy_apply(driver, job, cover_letter, session_dir)
                        else:
                            success = apply_external(
                                driver, job, cover_letter, session_dir,
                                _apply_btn=retry_btns[0] if hasattr(retry_btns[0], 'get_attribute') else None,
                                _external_url=None,
                            )

                # Cancelar alarme após sucesso
                signal.alarm(0)

            except _JobTimeout:
                signal.alarm(0)
                logger.warning(
                    f"   ⏰ Timeout ({JOB_APPLY_TIMEOUT}s) atingido para "
                    f"{job.title} @ {job.company} — pulando"
                )
                # Fechar abas extras que possam ter aberto
                try:
                    if len(driver.window_handles) > 1:
                        for wh in driver.window_handles[1:]:
                            driver.switch_to.window(wh)
                            driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                except Exception:
                    pass
                continue
            except Exception as e:
                signal.alarm(0)
                err_msg = str(e).lower()
                is_crash = any(w in err_msg for w in [
                    "connection refused", "session", "chrome not reachable",
                    "webdriver", "disconnected", "no such window",
                    "target window already closed", "invalid session",
                ])
                if is_crash:
                    crash_count += 1
                    logger.error(
                        f"   ❌ Chrome crashou ({crash_count}/{MAX_CRASHES})! "
                        f"Recriando driver..."
                    )
                    try:
                        driver.quit()
                    except Exception:
                        pass
                    if crash_count >= MAX_CRASHES:
                        logger.error("❌ Máximo de crashes atingido — abortando")
                        break
                    time.sleep(3)
                    driver = create_driver(headed=headed, chrome_profile=chrome_profile)
                    if not linkedin_login(driver):
                        logger.error("❌ Não foi possível relogar — abortando candidaturas")
                        break
                    logger.info("✅ Driver recriado e logado")
                    continue
                else:
                    logger.error(f"   ❌ Erro inesperado: {e}")

            if success:
                job.applied = True
                job.applied_at = datetime.now().isoformat()
                applied_count += 1
                save_applied_job(job)

                # Notificar via Telegram
                remote_icon = "🏠" if job.is_remote else "🏢"
                msg = (
                    f"✅ *Candidatura enviada!*\n\n"
                    f"*{job.title}*\n"
                    f"🏢 {job.company}\n"
                    f"📍 {job.location} {remote_icon}\n"
                    f"📊 Compatibilidade: {job.compatibility_score}%\n"
                    f"🔗 {job.url}\n\n"
                    f"_Skills match: {', '.join(job.matched_skills[:6])}_"
                )
                await send_telegram(msg)

                # Enviar screenshot se disponível
                ss_files = list(session_dir.glob(f"*{job.job_id}*done*"))
                if ss_files:
                    await send_telegram_photo(
                        str(ss_files[0]),
                        f"Screenshot: {job.title} @ {job.company}",
                    )
            else:
                logger.info(f"   ⏭️ Candidatura não enviada (formulário complexo)")

            time.sleep(SEARCH_DELAY * 2)

        # Restaurar handler original do SIGALRM
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

        # Relatório final
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  🏁 RESULTADO FINAL")
        logger.info(f"  📊 Vagas encontradas: {len(jobs)}")
        logger.info(f"  ✅ Vagas compatíveis: {len(compatible_jobs)}")
        logger.info(f"  📨 Candidaturas enviadas: {applied_count}")
        logger.info(f"  📁 Screenshots: {session_dir}")
        logger.info(f"{'=' * 60}")

        final_msg = (
            f"🏁 *LinkedIn Scanner — Relatório Final*\n\n"
            f"📊 Vagas analisadas: {len(jobs)}\n"
            f"✅ Compatíveis: {len(compatible_jobs)}\n"
            f"📨 Candidaturas: {applied_count}\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        await send_telegram(final_msg)

        # Salvar sessão
        _save_session(session_dir, compatible_jobs)

        return compatible_jobs

    finally:
        if driver is not None:
            try:
                save_cookies(driver)
            except Exception:
                pass
            try:
                driver.quit()
            except Exception:
                pass


def _save_session(session_dir: Path, jobs: list[LinkedInJob]) -> None:
    """Salva dados da sessão em JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "total_jobs": len(jobs),
        "applied": sum(1 for j in jobs if j.applied),
        "jobs": [asdict(j) for j in jobs],
    }
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"💾 Sessão salva em {session_file}")


# ─── CLI ─────────────────────────────────────────────────────────────────────
LOCK_FILE = DATA_DIR / "scanner.lock"


def main() -> None:
    """Entry point CLI com lockfile para instância única."""
    # --- Lockfile: impede execução simultânea ---
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("⚠️ Outra instância do scanner já está rodando. Saindo.")
        lock_fp.close()
        sys.exit(1)
    lock_fp.write(f"{os.getpid()}\n")
    lock_fp.flush()

    parser = argparse.ArgumentParser(
        description="LinkedIn Job Scanner — Busca e candidata-se a vagas compatíveis",
    )
    parser.add_argument(
        "--keywords", "-k",
        nargs="+",
        help="Keywords de busca (default: derivadas do currículo)",
    )
    parser.add_argument(
        "--min-score", "-s",
        type=float,
        default=MIN_COMPAT_SCORE,
        help=f"Score mínimo de compatibilidade (default: {MIN_COMPAT_SCORE}%%)",
    )
    parser.add_argument(
        "--max-apply", "-m",
        type=int,
        default=MAX_APPLY,
        help=f"Máximo de candidaturas por execução (default: {MAX_APPLY})",
    )
    parser.add_argument(
        "--no-remote-filter",
        action="store_true",
        help="Não filtrar apenas vagas remotas",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas buscar e analisar, sem candidatar",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Mostrar navegador (default: headless)",
    )
    parser.add_argument(
        "--chrome-profile",
        action="store_true",
        help="Usar perfil Chrome do usuário (herda sessão LinkedIn logada)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_scanner(
                keywords=args.keywords,
                remote_only=not args.no_remote_filter,
                min_score=args.min_score,
                max_apply=args.max_apply,
                dry_run=args.dry_run,
                headed=args.headed,
                chrome_profile=args.chrome_profile,
            )
        )
    except KeyboardInterrupt:
        logger.info("⏹️ Scanner interrompido pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal no scanner: {e}", exc_info=True)
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            pass


if __name__ == "__main__":
    main()
