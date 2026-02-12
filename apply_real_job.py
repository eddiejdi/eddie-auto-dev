#!/usr/bin/env python3
"""
Busca vaga real do WhatsApp, gera PDF do currículo e envia draft com anexo.
"""
import io
import json
import subprocess
import sys
import base64
import sqlite3
import logging
import time
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Logging
LOG_DIR = Path("/tmp/email_logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_DB = LOG_DIR / "email_sends.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "email_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Config
SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"
WAHA_API = os.environ.get("WAHA_URL", "http://192.168.15.2:3001")
COMPATIBILITY_THRESHOLD = float(os.environ.get("COMPATIBILITY_THRESHOLD", "20.0"))
TARGET_EMAIL = "edenilson.adm@gmail.com"
SEND_TO_CONTACT = os.environ.get("SEND_TO_CONTACT", "1") == "1"

# Whitelist de grupos confiáveis (IDs de grupos conhecidos de vagas)
# Deixe vazio [] para processar todos os grupos
GROUP_WHITELIST = os.environ.get("GROUP_WHITELIST", "").split(",") if os.environ.get("GROUP_WHITELIST") else []
USE_GROUP_WHITELIST = len(GROUP_WHITELIST) > 0 and GROUP_WHITELIST[0] != ""

# Simplified ML-first approach
USE_ADVANCED_COMPATIBILITY = True  # Sempre usar ML
COMPATIBILITY_METHOD = os.environ.get("COMPATIBILITY_METHOD", "semantic")  # Sempre usar ML (embeddings)
MESSAGE_MIN_LENGTH = int(os.environ.get("MESSAGE_MIN_LENGTH", "30"))

JOB_TERMS = [
    "vaga", "oportunidade", "contrat", "selecion", "processo seletivo",
    "clt", "pj", "remoto", "hibrido", "presencial", "salario", "requisitos",
    "devops", "sre", "engenheiro", "engenheira", "cloud", "kubernetes",
    "aws", "gcp", "azure", "infraestrutura", "plataforma", "desenvolvedor",
    "analista", "senior", "junior", "pleno", "tech lead", "architect"
]

PRODUCT_INDICATORS = [
    "r$", "reais", "desconto", "compre", "oferta", "promoção", "mercado",
    "🔥", "💰", "🛒", "link:", "comprar", "frete", "parcelado", "à vista",
    "http", "https", "loja", "cupom", "pix"
]


def classify_message(text: str) -> tuple[str, str]:
    """Classify message as job, false_positive, or ignore (BASIC - rule-based)."""
    if not text or len(text) < MESSAGE_MIN_LENGTH:
        return "ignore", "short_or_empty"

    lower = text.lower()

    if any(indicator in lower for indicator in PRODUCT_INDICATORS):
        return "false_positive", "product_indicator"

    if any(term in lower for term in JOB_TERMS):
        return "job", "job_terms"

    return "ignore", "no_job_terms"


def classify_message_strict(text: str) -> tuple[str, str]:
    """
    Filtro SIMPLIFICADO - ML fará a decisão final de compatibilidade.
    Apenas bloqueia conversas óbvias (saudações curtas, produtos).
    """
    if not text or len(text) < 50:
        return "ignore", "too_short"

    lower = text.lower()

    # Bloquear apenas produtos óbvios
    if any(indicator in lower for indicator in PRODUCT_INDICATORS):
        return "false_positive", "product_indicator"
    
    # Bloquear apenas saudações muito curtas
    if len(text) < 100 and any(x in lower for x in ["bom dia", "boa tarde", "boa noite", "obrigado", "valeu"]):
        return "ignore", "short_greeting"

    # Se menciona algum termo de vaga, deixar passar para ML decidir
    job_count = sum(1 for term in JOB_TERMS if term in lower)
    
    if job_count >= 1:
        return "job", f"potential_job_{job_count}_terms"

    return "ignore", "no_job_terms"


def classify_message_llm(text: str) -> tuple[str, str]:
    """Classify message using eddie-whatsapp LLM: job, false_positive, or ignore."""
    if not text or len(text) < MESSAGE_MIN_LENGTH:
        return "ignore", "short_or_empty"

    if not ADVANCED_AVAILABLE:
        # Fallback to strict rule-based
        label, reason = classify_message_strict(text)
        return label, f"llm_unavailable_{reason}"

    prompt = (
        "Você é um especialista em RecH e deve classificar mensagens de WhatsApp.\n\n"
        "Classifique como:\n"
        "- JOB: vaga de emprego legítima com descrição de cargo, requisitos ou contratação\n"
        "- FALSE_POSITIVE: conversa casual, pedido de indicação pessoal, anúncio de produto\n"
        "- IGNORE: spam, mensagem curta sem contexto, ou irrelevante\n\n"
        "EXEMPLOS:\n"
        "JOB: 'Vaga DevOps Senior - Remoto PJ - Kubernetes + AWS + Python - enviar CV para rh@empresa.com'\n"
        "FALSE_POSITIVE: 'Oi pessoal, alguém conhece um bom técnico de máquina de lavar?'\n"
        "IGNORE: 'Bom dia!'\n\n"
        "Responda APENAS com: JOB, FALSE_POSITIVE ou IGNORE\n\n"
        "Texto a classificar:\n"
    )
    prompt += text[:1500]

    response = call_ollama(prompt, temperature=0.1)
    if not response:
        # Fallback to strict rule-based
        return classify_message_strict(text)

    label = response.strip().upper()
    if "JOB" in label and "FALSE" not in label:
        return "job", "llm_job"
    if "FALSE" in label or "FALSE_POSITIVE" in label:
        return "false_positive", "llm_false_positive"
    if "IGNORE" in label:
        return "ignore", "llm_ignore"

    # Se LLM retornou algo inesperado, usar strict
    logger.warning(f"LLM returned unexpected: {label}, falling back to strict")
    return classify_message_strict(text)


def extract_contact_email(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE)
    return match.group(0) if match else None

# Import compatibility modules
try:
    from compatibility_allinone import compute_compatibility as compute_compatibility_advanced
    from llm_compatibility import call_ollama, temperature_for_match
    ADVANCED_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Advanced compatibility not available, using basic Jaccard: {e}")
    ADVANCED_AVAILABLE = False


def init_email_log_db():
    """Initialize email log database."""
    conn = sqlite3.connect(str(LOG_DB))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS email_sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            to_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            attachment_path TEXT,
            status TEXT NOT NULL,
            message_id TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_email_send(to_email: str, subject: str, attachment_path: str, status: str, message_id: str = None, notes: str = None):
    """Log email send to database."""
    init_email_log_db()
    
    conn = sqlite3.connect(str(LOG_DB))
    c = conn.cursor()
    c.execute("""
        INSERT INTO email_sends (timestamp, to_email, subject, attachment_path, status, message_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        to_email,
        subject,
        attachment_path,
        status,
        message_id,
        notes
    ))
    conn.commit()
    conn.close()
    
    logger.info(f"📧 Email registrado: {to_email} | {subject} | {status}")


def print_log_summary():
    """Print summary of email sends from database."""
    try:
        conn = sqlite3.connect(str(LOG_DB))
        c = conn.cursor()
        c.execute("SELECT COUNT(*), status FROM email_sends GROUP BY status")
        results = c.fetchall()
        conn.close()
        
        print("\n" + "="*70)
        print("📊 RESUMO DE EMAILS")
        print("="*70)
        
        total_sent = 0
        total_failed = 0
        total_draft = 0
        
        for count, status in results:
            if status == "SENT":
                total_sent = count
                print(f"✅ Enviados: {count}")
            elif status == "FAILED":
                total_failed = count
                print(f"❌ Falhados: {count}")
            elif status == "DRAFT_SAVED":
                total_draft = count
                print(f"📝 Rascunhos: {count}")
        
        print(f"📈 Total: {total_sent + total_failed + total_draft}")
        print(f"📂 Log salvo em: {LOG_DIR}")
        print("="*70 + "\n")
        
        logger.info(f"RESUMO: {total_sent} enviados, {total_failed} falhados, {total_draft} rascunhos")
        
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {e}")

# Currículo em texto
CURRICULUM_TEXT = """EDENILSON TEIXEIRA
DevOps Engineer | SRE | Platform Engineer
São Paulo, SP | +55 11 98765-4321 | edenilson.adm@gmail.com

EXPERIÊNCIA PROFISSIONAL

Senior Platform Engineer | XYZ Tech (2022 - Atual)
- Arquitetura e deployment de plataformas Kubernetes em produção
- Implementação de CI/CD pipelines usando GitLab CI e GitHub Actions
- Automação de infraestrutura com Terraform e Ansible
- Redução de 40% no MTTR através de runbooks autom
ativos
- Mentoria de 5 enqueiros junior em práticas SRE

DevOps Engineer | B3 (2019 - 2022)
- Gestão de clusters Kubernetes com 100+ nodes
- Implementação de observabilidade com Prometheus, Grafana e ELK
- Deploy automatizado de aplicações Python, Go e Java
- Redução de custos de infraestrutura em 35%
- Implementação de disaster recovery e high availability

Infrastructure Engineer | StartUp Fintech (2018 - 2019)
- Migração de on-premise para AWS
- Implementação de networking e segurança
- Automação de provisioning com CloudFormation

COMPETÊNCIAS TÉCNICAS

Linguagens: Python, Go, Bash, Terraform HCL
Orquestração: Kubernetes, Docker, Docker Swarm
CI/CD: GitLab CI, GitHub Actions, Jenkins, ArgoCD
Cloud: AWS (EC2, RDS, S3, VPC), GCP, Azure
Observabilidade: Prometheus, Grafana, ELK Stack, Jaeger, Loki
IaC: Terraform, Ansible, CloudFormation
Bancos: PostgreSQL, MongoDB, Redis, ElasticSearch
Melhores Práticas: SRE, GitOps, Infrastructure as Code, Incident Management

EDUCAÇÃO

Certificação: AWS Solutions Architect Professional (2023)
Certificação: Kubernetes Administrator (CKA) - 2022
Certificação: Terraform Associate - 2021
Formação: Engenharia de Computação, Universidade XXX (2015)

IDIOMAS

Português: Nativo
Inglês: Fluente (leitura, escrita, conversação)
Espanhol: Intermediário
"""


def get_secret_from_agent(secret_name: str, field: str = None) -> str:
    """Fetch secret from Secrets Agent."""
    field_clause = f" AND field='{field}'" if field else ""
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        f"""python3 - <<'PY'
import sqlite3, base64, sys
conn = sqlite3.connect('{SECRETS_AGENT_TOKEN_PATH}')
c = conn.cursor()
c.execute("SELECT value FROM secrets_store WHERE name='{secret_name}'{field_clause}")
row = c.fetchone()
conn.close()
if not row:
    print('NOT_FOUND')
    sys.exit(0)
try:
    print(base64.b64decode(row[0]).decode())
except:
    print(row[0])
PY"""
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"failed to fetch secret: {res.stderr}")
    out = res.stdout.strip()
    if out == "NOT_FOUND":
        raise KeyError(f"secret not found: {secret_name}")
    return out


def get_waha_api_key() -> str:
    """Get WAHA API key."""
    try:
        env_key = os.environ.get("WAHA_API_KEY")
        if env_key:
            return env_key
        return get_secret_from_agent("eddie/waha_api_key")
    except Exception:
        raise ValueError("WAHA_API_KEY not found in Secrets Agent")


def fetch_whatsapp_messages(limit: int = 20, max_retries: int = 3) -> list:
    """Fetch recent messages from WhatsApp (PROD - always try WAHA first)."""
    print("📱 Buscando grupos WhatsApp com vagas...")
    logger.info("🚀 Tentando conectar ao WAHA...")

    def is_job_message(text: str) -> bool:
        label, _ = classify_message(text)
        if label == "false_positive":
            return False
        llm_label, _ = classify_message_llm(text)
        return llm_label == "job"

    try:
        api_key = get_waha_api_key()
        logger.info("✅ API Key obtida do Secrets Agent")
    except Exception as e:
        logger.error(f"❌ WAHA API Key não encontrada: {e}")
        print(f"  ⚠️  WAHA KEY não disponível: {e}")
        return None

    def _curl_json(url: str, timeout: int = 10) -> tuple[int, str]:
        cmd = [
            "curl", "-s", "-m", str(timeout),
            "-H", f"X-Api-Key: {api_key}",
            "-H", "Accept: application/json",
            "-w", "\nHTTP_STATUS:%{http_code}\n",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        if res.returncode != 0:
            raise RuntimeError(f"curl failed: {res.returncode}")
        if "HTTP_STATUS:" not in res.stdout:
            return 0, res.stdout
        body, status_line = res.stdout.rsplit("HTTP_STATUS:", 1)
        status = int(status_line.strip() or 0)
        return status, body.strip()

    # Retry logic with exponential backoff
    for attempt in range(1, max_retries + 1):
        logger.info(f"🔄 Tentativa {attempt}/{max_retries} de conectar ao WAHA...")

        try:
            status, output = _curl_json(f"{WAHA_API}/api/sessions")

            if status == 401:
                logger.error("❌ WAHA respondeu 401 (API key invalida ou sem permissao)")
                return None

            if status >= 500 or status == 0:
                logger.warning(f"⚠️  Tentativa {attempt}: WAHA erro HTTP {status}")
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                    time.sleep(wait_time)
                    continue
                return None

            if "<!doctype" in output.lower() or "<html" in output.lower():
                logger.warning("⚠️  WAHA retornou HTML em vez de JSON (URL incorreta ou proxy)")
                return None

            try:
                data = json.loads(output)
            except json.JSONDecodeError as je:
                logger.warning(f"⚠️  Erro ao parsear JSON: {je}")
                return None

            sessions = data.get("data", []) if isinstance(data, dict) else data
            if not sessions:
                logger.warning("⚠️  Nenhuma sessao ativa no WAHA")
                return None

            session_name = (
                sessions[0].get("name")
                or sessions[0].get("id")
                or sessions[0].get("session")
                or "default"
            )
            logger.info(f"✅ Sessao WAHA ativa: {session_name}")

            status, chats_output = _curl_json(f"{WAHA_API}/api/{session_name}/chats")
            if status != 200:
                logger.warning(f"⚠️  Falha ao listar chats: HTTP {status}")
                return None

            chats = json.loads(chats_output) if chats_output else []
            if not chats:
                logger.warning("⚠️  Nenhum chat encontrado no WAHA")
                return None

            chat_id = chats[0].get("id") or chats[0].get("chatId")
            if not chat_id:
                logger.warning("⚠️  Chat sem ID valido")
                return None

            status, messages_output = _curl_json(
                f"{WAHA_API}/api/{session_name}/chats/{chat_id}/messages?limit={limit}"
            )
            if status != 200:
                logger.warning(f"⚠️  Falha ao buscar mensagens: HTTP {status}")
                return None

            messages = json.loads(messages_output) if messages_output else []
            counts = {"job": 0, "false_positive": 0, "ignore": 0}
            job_messages = []
            for m in messages:
                body = m.get("body", "")
                label, _ = classify_message(body)
                if label == "false_positive":
                    counts[label] = counts.get(label, 0) + 1
                    continue
                llm_label, _ = classify_message_llm(body)
                counts[llm_label] = counts.get(llm_label, 0) + 1
                if llm_label == "job":
                    job_messages.append(m)
            if not job_messages:
                logger.warning(
                    "⚠️  Nenhuma vaga real encontrada após aplicar filtros "
                    f"(job={counts['job']}, false_positive={counts['false_positive']}, ignore={counts['ignore']})"
                )
                return None
            logger.info(
                f"✅ {len(job_messages)} vaga(s) encontrada(s) após filtros "
                f"(job={counts['job']}, false_positive={counts['false_positive']}, ignore={counts['ignore']})"
            )
            return job_messages[:5]

        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  Tentativa {attempt}: Timeout na conexao com WAHA")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"⏳ Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
                continue
            logger.error(f"❌ WAHA nao respondeu apos {max_retries} tentativas")
            return None
        except Exception as e:
            logger.error(f"⚠️  Tentativa {attempt}: Erro inesperado: {e}")
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.info(f"⏳ Aguardando {wait_time}s...")
                time.sleep(wait_time)
                continue
            return None

    logger.error(f"❌ Falha em todas as {max_retries} tentativas de conectar ao WAHA")
    return None


def extract_job_from_message(message: str) -> Dict[str, str]:
    """Parse job details from a message."""
    lines = [line.strip() for line in message.split('\n') if line.strip()]
    title = lines[0] if lines else "Oportunidade de Emprego"
    company = "Empresa em Vagas"
    for line in lines:
        lower = line.lower()
        if lower.startswith("empresa:") or lower.startswith("company:"):
            company = line.split(":", 1)[1].strip() or company
            break

    contact_email = extract_contact_email(message)

    return {
        "title": title,
        "company": company,
        "description": message,
        "excerpt": message[:200],
        "contact_email": contact_email
    }


def get_curriculum_from_drive() -> str:
    """Download curriculum from Google Drive."""
    print(f"📄 Buscando currículo no Google Drive...")
    
    try:
        gmail_token_json = get_secret_from_agent("google/gmail_token")
        gmail_data = json.loads(gmail_token_json)
        
        creds = Credentials(
            token=gmail_data.get('token'),
            refresh_token=gmail_data.get('refresh_token'),
            token_uri=gmail_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=gmail_data.get('client_id'),
            client_secret=gmail_data.get('client_secret'),
            scopes=['https://www.googleapis.com/auth/drive'],
        )
        
        if creds.expired or not creds.valid:
            creds.refresh(Request())
        
        drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        
        # Search for curriculum file (Curriculum_Edenilson_2026 or similar)
        query = "name contains 'Curriculum' or name contains 'Currículo' or name contains 'curriculo'"
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType)',
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        if not files:
            print(f"  ⚠️  Nenhum currículo encontrado no Drive")
            return None
        
        # Get first curriculum file
        curriculum_file = files[0]
        file_id = curriculum_file['id']
        file_name = curriculum_file['name']
        mime_type = curriculum_file.get('mimeType', '')
        
        print(f"  ✅ Arquivo encontrado: {file_name}")
        
        # Determine output format
        if 'pdf' in mime_type.lower():
            output_path = f"Curriculo_Edenilson.pdf"
        elif 'document' in mime_type.lower() or 'word' in mime_type.lower() or file_name.endswith('.docx'):
            output_path = f"Curriculo_Edenilson.docx"
        else:
            output_path = f"Curriculo_Edenilson_{Path(file_name).suffix.lstrip('.')}"
        
        # Download file
        print(f"  ⏳ Baixando arquivo...")
        # If it's a Google Doc/Sheet, export as PDF; otherwise download as-is
        try:
            if 'google' in mime_type.lower() and '.google' in mime_type.lower():
                request = drive_service.files().export_media(fileId=file_id, mimeType='application/pdf')
                output_path = f"Curriculo_Edenilson.pdf"
            else:
                # Download the actual file (DOCX, PDF, etc.)
                request = drive_service.files().get_media(fileId=file_id)
            
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            with open(output_path, 'wb') as f:
                f.write(fh.getvalue())
            
            print(f"  ✅ Currículo baixado: {output_path}")
            return output_path
        except Exception as download_error:
            print(f"  ⚠️  Erro ao baixar arquivo: {download_error}")
            print(f"     Tentando gerar PDF padrão...")
            return None
        
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar currículo do Drive: {e}")
        return None


def create_curriculum_pdf(output_path: str = "Curriculo_Edenilson.pdf"):
    """Create PDF resume from curriculum text (fallback)."""
    print(f"📄 Gerando {output_path}...")
    
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom title style
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor='#1a1a1a',
        spaceAfter=6,
        alignment=1,  # Center
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor='#333333',
        spaceAfter=6,
        spaceBefore=10,
        bold=True,
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        spaceAfter=4,
    )
    
    # Add title
    story.append(Paragraph("EDENILSON TEIXEIRA", title_style))
    story.append(Paragraph("DevOps Engineer | SRE | Platform Engineer", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    
    # Parse and add content
    sections = CURRICULUM_TEXT.split('\n\n')
    for section in sections[1:]:  # Skip title
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        # Section heading
        heading = lines[0] if lines[0].isupper() or '|' in lines[0] or 'COMPETÊNCIAS' in lines[0] else None
        
        if heading and heading not in ["EDENILSON TEIXEIRA", "DevOps Engineer | SRE | Platform Engineer"]:
            story.append(Paragraph(heading, heading_style))
        
        # Content
        for line in lines[1:]:
            if line.strip():
                story.append(Paragraph(line.strip(), body_style))
        
        story.append(Spacer(1, 0.05*inch))
    
    # Build PDF
    doc.build(story)
    print(f"  ✅ PDF criado: {output_path}")
    return output_path


def generate_application_email(job: Dict[str, str]) -> tuple:
    """Generate professional application email."""
    title = job.get("title", "Oportunidade")
    company = job.get("company", "sua empresa")
    excerpt = job.get("excerpt") or ""

    subject = f"Candidatura – {title}"

    body_lines = [
        "Olá,",
        "",
        f"Encontrei a vaga de {title} na {company} e meu perfil se alinha bem com as demandas da posição.",
    ]

    if excerpt:
        body_lines.extend([
            "",
            "Resumo da vaga:",
            excerpt,
        ])

    body_lines.extend([
        "",
        "Tenho experiência sólida em infraestrutura, automação e operações, e tenho interesse em discutir como posso contribuir para a equipe.",
        "",
        "Segue em anexo meu currículo para sua análise. Fico à disposição para conversar e tirar dúvidas.",
        "",
        "Atenciosamente,",
        "Edenilson Teixeira",
        "+55 11 98765-4321",
        "edenilson.adm@gmail.com",
    ])

    return subject, "\n".join(body_lines)


def generate_application_email_llm(job: Dict[str, str], compatibility: float) -> tuple:
    """Generate application email using eddie-whatsapp with temperature tied to match."""
    if not ADVANCED_AVAILABLE:
        return generate_application_email(job)

    title = job.get("title", "Oportunidade")
    company = job.get("company", "sua empresa")
    excerpt = job.get("excerpt") or job.get("description") or ""

    tone = "assertivo e confiante" if compatibility >= 75 else "profissional e objetivo"
    temperature = temperature_for_match(compatibility)

    prompt = (
        "Voce e um assistente de recrutamento. Gere um email curto e direto para candidatura.\n"
        "Se a compatibilidade for alta, use tom mais afirmativo e certeiro.\n"
        "Responda no formato:\n"
        "Subject: <assunto>\n"
        "Body:\n<texto>\n\n"
        f"Compatibilidade: {compatibility:.1f}%\n"
        f"Tom: {tone}\n\n"
        f"Vaga: {title}\n"
        f"Empresa: {company}\n"
        f"Resumo da vaga:\n{excerpt[:800]}\n\n"
        f"Resumo do curriculo:\n{CURRICULUM_TEXT[:800]}\n"
    )

    response = call_ollama(prompt, temperature=temperature)
    if not response:
        return generate_application_email(job)

    subject = None
    body = None
    for line in response.splitlines():
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
        if line.lower().startswith("body:"):
            body_index = response.lower().find("body:")
            body = response[body_index + 5 :].strip()
            break

    if not subject or not body:
        return generate_application_email(job)

    return subject, body


def review_compatibility_with_llm(resume_text: str, job_text: str, compatibility: float, details: dict) -> str:
    """Ask the local LLM to review the computed compatibility and point out possible problems.

    Returns a short diagnostic string in Portuguese produced by the LLM.
    """
    try:
        if not ADVANCED_AVAILABLE:
            return "LLM não disponível para revisão." 

        # Build diagnostic prompt
        prompt = (
            "Você é um auditor técnico que analisa comparações entre um currículo e uma descrição de vaga.\n"
            "A compatibilidade calculada foi de {compat:.1f}%. Identifique possíveis falhas da comparação, como: tokenização fraca, falta de sinônimos, diferença de contexto (ex.: Python em DevOps vs Data Science), extração incompleta e ruído de texto.\n"
            "Responda em português, objetivo e técnico, no formato abaixo:\n"
            "1) Diagnóstico geral (1-2 linhas)\n"
            "2) Causas prováveis (até 5 bullets)\n"
            "3) Correções recomendadas (até 5 bullets)\n"
            "4) Confiança do diagnóstico (0-100)\n\n"
        ).format(compat=compatibility)

        prompt += "=== VAGA ===\n" + (job_text or '')[:4000] + "\n\n"
        prompt += "=== CURRÍCULO ===\n" + (resume_text or '')[:4000] + "\n\n"
        prompt += "=== DETALHES TÉCNICOS (json) ===\n" + (json.dumps(details, ensure_ascii=False) if details else "{}")[:2000] + "\n\n"

        temp = 0.1
        try:
            temp = temperature_for_match(float(compatibility))
        except Exception:
            temp = 0.1

        response = call_ollama(prompt, temperature=temp)
        if not response:
            return "LLM não retornou diagnóstico." 

        return response.strip()
    except Exception as e:
        logger.error(f"Erro na revisão LLM da compatibilidade: {e}")
        return f"Erro ao revisar com LLM: {e}"


def compute_compatibility(resume_text: str, job_text: str) -> tuple:
    """Compute compatibility percentage between resume and job text.

    Returns:
        (score, explanation, details) tuple
        - score: float 0-100
        - explanation: str describing the match
        - details: dict with additional info (method, component_scores, etc.)
    """
    if not resume_text or not job_text:
        return 0.0, "Empty text", {}

    # Use advanced compatibility if available
    if USE_ADVANCED_COMPATIBILITY and ADVANCED_AVAILABLE:
        try:
            score, explanation, details = compute_compatibility_advanced(resume_text, job_text, method=COMPATIBILITY_METHOD)
            
            # Log with appropriate icon based on method
            method = details.get('method', 'unknown')
            if 'semantic' in method:
                icon = "🧠"
            elif 'llm' in method:
                icon = "🤖"
            elif 'tfidf' in method:
                icon = "📊"
            elif 'ultra' in method:
                icon = "🏆"
            else:
                icon = "📏"
            
            logger.info(f"{icon} {method}: {score}%")
            if details.get('component_scores'):
                components = ", ".join([f"{k}={v:.1f}%" for k, v in details['component_scores'].items()])
                logger.info(f"   Components: {components}")
            
            return score, explanation, details
            
        except Exception as e:
            logger.warning(f"Advanced compatibility failed: {e}")
            logger.warning(f"Falling back to simple Jaccard")
    
    # Fallback to simple Jaccard
    stopwords = {
        'e','de','do','da','em','com','para','a','o','as','os','um','uma','que',
        'the','and','or','in','on','at','by','of','for','to','with'
    }

    def tokens(s: str):
        s = s.lower()
        s = re.sub(r"[^a-z0-9çãõáéíóúâêîôûàèìòù-]+", " ", s)
        toks = [t.strip() for t in s.split() if t and t not in stopwords and len(t) > 2]
        return set(toks)

    rset = tokens(resume_text)
    jset = tokens(job_text)
    if not rset or not jset:
        return 0.0, "No tokens", {"method": "jaccard_fallback"}

    inter = rset.intersection(jset)
    union = rset.union(jset)
    score = len(inter) / len(union)
    jaccard_score = round(score * 100.0, 1)
    
    details = {
        "method": "jaccard_fallback",
        "jaccard_score": jaccard_score,
        "common_tokens": len(inter),
        "total_tokens": len(union)
    }
    
    explanation = f"Jaccard similarity: {len(inter)}/{len(union)} tokens in common"
    logger.info(f"📏 Jaccard fallback: {jaccard_score}%")
    
    return jaccard_score, explanation, details


def search_group_chats_for_match(threshold: float = 20.0, max_chats: int = 300, messages_per_chat: int = 60):
    """Scan WAHA group chats (including archived) until a message meets the compatibility threshold.
    Filters messages from the last 60 days.

    Returns a job dict or None.
    """
    from datetime import datetime, timedelta
    
    # Demo mode: always return a simulated job for testing
    demo_mode = os.environ.get('DEMO_MODE', '0') == '1'
    if demo_mode:
        import random
        job_templates = [
            {"title": "DevOps Engineer - Remote", "company": "TechCorp", "desc": "Buscamos DevOps com experiência em Kubernetes, Docker, CI/CD e infraestrutura as code. Ambiente dinâmico."},
            {"title": "SRE - São Paulo", "company": "FinTech Analytics", "desc": "Vaga para SRE com conhecimento em observabilidade, automação, Python e plataformas cloud (AWS/GCP)."},
            {"title": "Platform Engineer", "company": "StartupX", "desc": "Procuramos engenheiro de plataforma para trabalhar com Terraform, Kubernetes, monitoramento e CI/CD."},
            {"title": "Cloud Engineer - Híbrido", "company": "Enterprise Solutions", "desc": "Oportunidade para engenheiro cloud com experiência em AWS, networking, segurança e automação."},
            {"title": "Infrastructure Lead", "company": "DataTech", "desc": "Liderança técnica em infraestrutura: Kubernetes, Docker, Terraform, Ansible, GitOps e observabilidade."},
        ]
        job = random.choice(job_templates)
        compat = round(random.uniform(threshold, min(threshold + 15, 35)), 1)
        logger.info(f"DEMO MODE: generating simulated job with {compat}% compatibility")
        return {
            'title': job['title'],
            'company': job['company'],
            'description': job['desc'],
            'excerpt': job['desc'][:300],
            'compatibility': compat,
        }
    
    try:
        api_key = get_waha_api_key()
    except Exception as e:
        logger.error(f"WAHA key error: {e}")
        return None

    def curl_json(url: str, timeout: int = 12):
        cmd = [
            "curl", "-s", "-m", str(timeout),
            "-H", f"X-Api-Key: {api_key}",
            "-H", "Accept: application/json",
            url,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)
        if res.returncode != 0:
            raise RuntimeError(f"curl failed: {res.stderr}")
        return res.stdout

    try:
        sessions_out = curl_json(f"{WAHA_API}/api/sessions")
        sessions = json.loads(sessions_out)
    except Exception:
        sessions = None

    session_name = 'default'
    if sessions:
        if isinstance(sessions, list) and sessions:
            session_name = sessions[0].get('name', session_name)
        elif isinstance(sessions, dict):
            data = sessions.get('data') or sessions
            if isinstance(data, list) and data:
                session_name = data[0].get('name', session_name)

    try:
        chats_out = curl_json(f"{WAHA_API}/api/{session_name}/chats")
        chats = json.loads(chats_out)
    except Exception as e:
        logger.error(f"Failed to list chats: {e}")
        return None

    # Filter ALL group chats (including archived) - not limited by isArchived status
    group_chats = [c for c in chats if ('@g.us' in (c.get('id') or '') or c.get('isGroup') == True or c.get('type') == 'group')]
    
    # Apply whitelist filter if configured
    if USE_GROUP_WHITELIST:
        original_count = len(group_chats)
        group_chats = [c for c in group_chats if c.get('id') in GROUP_WHITELIST]
        logger.info(f"Whitelist filter: {original_count} groups -> {len(group_chats)} whitelisted groups")
    
    logger.info(f"Scanning {len(group_chats)} group chats (including archived) for job postings from last 60 days")
    
    # 60 days cutoff
    cutoff_date = datetime.now() - timedelta(days=60)
    cutoff_timestamp = int(cutoff_date.timestamp())
    
    scanned_count = 0
    messages_checked = 0

    for chat in group_chats[:max_chats]:
        cid = chat.get('id') or chat.get('chatId')
        if not cid:
            continue
        
        scanned_count += 1
        is_archived = chat.get('isArchived') or chat.get('archived')
        chat_name = chat.get('name') or cid
        
        try:
            msgs_out = curl_json(f"{WAHA_API}/api/{session_name}/chats/{cid}/messages?limit={messages_per_chat}")
            msgs = json.loads(msgs_out)
        except Exception as ex:
            logger.debug(f"Failed to fetch messages from {chat_name}: {ex}")
            continue

        for m in msgs:
            # Filter by timestamp (last 60 days)
            msg_timestamp = m.get('timestamp') or m.get('t')
            if msg_timestamp:
                try:
                    # Handle both Unix timestamp and ISO format
                    if isinstance(msg_timestamp, (int, float)):
                        ts = int(msg_timestamp)
                    else:
                        ts = int(datetime.fromisoformat(str(msg_timestamp).replace('Z', '+00:00')).timestamp())
                    
                    if ts < cutoff_timestamp:
                        continue  # Skip messages older than 60 days
                except Exception:
                    pass  # If timestamp parsing fails, still process the message
            
            text = (m.get('body') or '')
            if not text or len(text) < MESSAGE_MIN_LENGTH:
                continue

            messages_checked += 1

            # Step 1: Quick filter with strict rules (fast)
            label, reason = classify_message_strict(text)
            if label != "job":
                if label == "false_positive":
                    logger.debug(f"Filtered out: {reason} - {text[:80]}")
                continue

            # Step 2: LLM classification (slower but more accurate)
            llm_label, llm_reason = classify_message_llm(text)
            if llm_label != "job":
                logger.debug(f"LLM filtered out: {llm_reason} - {text[:80]}")
                continue

            logger.info(f"✅ Potential job found: {text[:100]}...")

            # compute compatibility
            compat, explanation, details = compute_compatibility(CURRICULUM_TEXT, text)
            
            if compat >= threshold:
                contact_email = extract_contact_email(text)
                logger.info(f"Found match in {'archived ' if is_archived else ''}chat '{chat_name}' (ID: {cid}) with compat {compat}% - scanned {scanned_count} chats, checked {messages_checked} messages")
                return {
                    'title': text.split('\n', 1)[0][:120],
                    'company': chat.get('name') or 'Grupo WhatsApp',
                    'description': text,
                    'excerpt': text[:300],
                    'compatibility': compat,
                    'explanation': explanation,
                    'details': details,
                    'contact_email': contact_email,
                }
    
    logger.info(f"No matches found. Scanned {scanned_count} chats (including archived), checked {messages_checked} messages from last 60 days")
    return None


def send_gmail_with_attachment(to_email: str, subject: str, body: str, attachment_path: str):
    """Send email via Gmail API with PDF attachment."""
    print(f"\n📧 Preparando envio para {to_email}...")
    
    # Get Gmail credentials
    try:
        gmail_token_json = get_secret_from_agent("google/gmail_token")
        gmail_data = json.loads(gmail_token_json)
    except Exception as e:
        print(f"⚠️  Credenciais Gmail indisponíveis: {e}")
        return save_draft_locally(to_email, subject, body, attachment_path)
    
    # Try to send via Gmail API
    try:
        creds = Credentials(
            token=gmail_data.get('access_token'),
            refresh_token=gmail_data.get('refresh_token'),
            token_uri=gmail_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=gmail_data.get('client_id'),
            client_secret=gmail_data.get('client_secret'),
            scopes=['https://www.googleapis.com/auth/gmail.send'],
        )
        
        if creds.expired or not creds.valid:
            creds.refresh(Request())
        
        gmail_service = build('gmail', 'v1', credentials=creds, cache_discovery=False)
        
        # Build message
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.utils import formatdate
        from email import encoders
        
        msg = MIMEMultipart()
        msg['From'] = 'edenilson.adm@gmail.com'
        msg['To'] = to_email
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
        
        # Body
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attachment
        if Path(attachment_path).exists():
            with open(attachment_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= "{Path(attachment_path).name}"'
                )
                msg.attach(part)
        
        # Send
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f"  ✅ Email enviado com sucesso!")
        
        # Log to database
        message_id = result.get('id')
        log_email_send(to_email, subject, attachment_path, "SENT", message_id=message_id, notes="Gmail API")
        return True
    except Exception as e:
        print(f"  ⚠️  Erro ao enviar via Gmail API: {e}")
        print(f"     Salvando draft localmente...")
        # Log error
        log_email_send(to_email, subject, attachment_path, "FAILED", notes=f"Error: {str(e)}")
        return save_draft_locally(to_email, subject, body, attachment_path)


def save_draft_locally(to_email: str, subject: str, body: str, attachment_path: str) -> bool:
    """Save email draft locally when Gmail API fails."""
    draft_path = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}.eml"
    
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formatdate
    from email import encoders
    
    msg = MIMEMultipart()
    msg['From'] = 'edenilson.adm@gmail.com'
    msg['To'] = to_email
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    # Attach PDF
    if Path(attachment_path).exists():
        with open(attachment_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= "{Path(attachment_path).name}"'
            )
            msg.attach(part)
    
    # Save EML file
    with open(draft_path, 'w', encoding='utf-8') as f:
        f.write(msg.as_string())
    
    print(f"  ✅ Draft salvo em: {draft_path}")
    print(f"     Você pode enviar manualmente ou via script posterior.")
    
    # Log to database
    log_email_send(to_email, subject, draft_path, "DRAFT_SAVED", notes="Saved locally as EML")
    
    return True


def main():
    print("\n" + "="*70)
    print("🚀 APLICAÇÃO PARA VAGA REAL DO WHATSAPP")
    print("="*70 + "\n")

    # Initialize logging
    init_email_log_db()
    logger.info("="*70)
    logger.info("🚀 Iniciando processamento de aplicações")
    logger.info("="*70)

    # Control flags for continuous sending
    auto_send_env = os.environ.get('AUTO_SEND_TO_SELF', '0')
    auto_send_enabled = auto_send_env == '1' or os.path.exists('/tmp/auto_send_enabled')
    stop_file = '/tmp/stop_sending_apply_real_job'
    scan_interval = int(os.environ.get('AUTO_SEND_INTERVAL', '60'))
    max_chats = int(os.environ.get('WAHA_MAX_CHATS', '1000'))  # Increased to scan more groups
    messages_per_chat = int(os.environ.get('WAHA_MESSAGES_PER_CHAT', '100'))  # Increased to get more messages per group

    def should_stop() -> bool:
        if os.environ.get('STOP_AUTO_SEND', '0') == '1':
            return True
        if os.path.exists(stop_file):
            return True
        return False

    try:
        if auto_send_enabled:
            logger.info("🔁 MODO CONTÍNUO: enviando para o usuário até liberação (ou até criar /tmp/stop_sending_apply_real_job)")
            while True:
                if should_stop():
                    logger.info("🛑 Stop flag detectada. Encerrando modo contínuo de envio.")
                    break

                job = search_group_chats_for_match(threshold=COMPATIBILITY_THRESHOLD, max_chats=max_chats, messages_per_chat=messages_per_chat)
                if not job:
                    logger.info("🔎 Nenhuma vaga compatível encontrada nesta varredura. Aguardando próximo ciclo...")
                    time.sleep(scan_interval)
                    continue

                # Prepare curriculum
                curriculum_path = get_curriculum_from_drive()
                if not curriculum_path:
                    curriculum_path = create_curriculum_pdf("Curriculo_Edenilson.pdf")

                contact_email = job.get('contact_email')
                if SEND_TO_CONTACT:
                    if not contact_email:
                        logger.warning("⚠️  Nenhum email de contato encontrado na mensagem. Pulando envio.")
                        time.sleep(scan_interval)
                        continue
                    dest_email = contact_email
                else:
                    dest_email = TARGET_EMAIL

                compat = float(job.get('compatibility') or 0)
                subject, body = generate_application_email_llm(job, compat)

                # LLM review also in continuous mode (diagnóstico rápido)
                try:
                    llm_review = review_compatibility_with_llm(CURRICULUM_TEXT, job.get('description',''), compat, job.get('details', {}))
                    if llm_review:
                        logger.info(f"Revisão LLM (contínuo): {llm_review[:300]}")
                except Exception as _ex:
                    logger.warning(f"Falha ao executar revisão LLM (contínuo): {_ex}")

                # Send to contact
                success = send_gmail_with_attachment(dest_email, subject, body, curriculum_path)
                if success:
                    logger.info(f"✅ EMAIL ENVIADO (contínuo): {dest_email} | compat={job.get('compatibility')}% | {subject}")
                else:
                    logger.warning(f"⚠️ FALHA ENVIO (contínuo): {dest_email} | {subject}")

                # Wait before next scan
                time.sleep(scan_interval)

            print_log_summary()
            return

        # Single-run mode (no fallback mock): only process real matches once
        job = search_group_chats_for_match(threshold=COMPATIBILITY_THRESHOLD, max_chats=max_chats, messages_per_chat=messages_per_chat)
        if not job:
            print("⚠️ Nenhuma vaga compatível encontrada nas varreduras configuradas.")
            logger.info("Processamento finalizado: nenhuma vaga encontrada.")
            print_log_summary()
            return

        # Prepare curriculum
        curriculum_path = get_curriculum_from_drive()
        if not curriculum_path:
            curriculum_path = create_curriculum_pdf("Curriculo_Edenilson.pdf")

        # Compute compatibility and show
        try:
            if job.get('compatibility'):
                compat = job.get('compatibility')
                explanation = job.get('explanation', '')
                details = job.get('details', {})
            else:
                compat, explanation, details = compute_compatibility(CURRICULUM_TEXT, job.get('description',''))
            
            print(f"\n🔎 Compatibilidade currículo ↔ vaga: {compat}%")
            if explanation:
                print(f"   {explanation[:200]}")
            logger.info(f"Compatibilidade: {compat}% | {explanation[:100]}")
            # LLM-based review of the compatibility calculation (diagnóstico)
            try:
                llm_review = review_compatibility_with_llm(CURRICULUM_TEXT, job.get('description',''), compat, details if 'details' in locals() else {})
                if llm_review:
                    print("\n🔍 Revisão LLM da comparação:\n")
                    print(llm_review)
                    logger.info(f"Revisão LLM (resumo): {llm_review[:300]}")
            except Exception as _ex:
                logger.warning(f"Falha ao executar revisão LLM: {_ex}")
        except Exception as e:
            logger.warning(f"Erro ao calcular compatibilidade: {e}")
            compat = 0.0

        contact_email = job.get('contact_email')
        if SEND_TO_CONTACT:
            if not contact_email:
                print("⚠️ Nenhum email de contato encontrado na mensagem. Abortando envio.")
                logger.info("Processamento finalizado: contato nao encontrado.")
                print_log_summary()
                return
            dest_email = contact_email
        else:
            dest_email = TARGET_EMAIL

        subject, body = generate_application_email_llm(job, compat)

        print(f"\n📝 Email draft:")
        print("="*70)
        print(f"PARA: {dest_email}")
        print(f"ASSUNTO: {subject}")
        print(f"ANEXO: {curriculum_path}\n")
        print(body)
        print("="*70)

        success = send_gmail_with_attachment(dest_email, subject, body, curriculum_path)
        if success:
            print(f"\n✅ Aplicação enviada com sucesso!")
            logger.info(f"✅ EMAIL ENVIADO: {dest_email} | {subject}")
        else:
            print(f"\n⚠️  Email não foi enviado, mas draft foi criado.")
            logger.warning(f"⚠️  EMAIL NÃO ENVIADO: {dest_email} | {subject}")

        print_log_summary()

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        logger.error(f"❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
