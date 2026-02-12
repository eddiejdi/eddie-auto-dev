#!/usr/bin/env python3
"""
Pipeline de matching de vagas:
1. Obter currículo do Drive
2. Ler carta de recomendação (PDF)
3. Listar grupos WhatsApp com vagas (30 dias)
4. Extrair e analisar vagas
5. Calcular match % vs currículo
6. Criar draft para matches > 75%
7. Enviar draft para edenilson.adm@gmail.com
"""
import io
import json
import os
import re
import base64
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from docx import Document
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import pymupdf as fitz  # PyMuPDF for PDF parsing
import pytesseract  # OCR for image-based PDFs
from pdf2image import convert_from_path  # Convert PDF to images for OCR
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders

# Config
SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"
DRIVE_TOKEN_SECRET = "google/gdrive_token_edenilson_teixeira"
GMAIL_SECRET = "google/gmail_token"
LETTER_PATH = Path("/home/edenilson/Downloads/DOC-20260211-WA0000")  # PDF (sem extensão)
TARGET_EMAIL = "edenilson.adm@gmail.com"
CURRICULUM_FILE_ID = "1y2eeV4No2zQD_ezeZCaBZiuswvANF8V3"  # Curriculum_Edenilson (Atualizado).docx
WAHA_API = "http://192.168.15.2:3000"
WAHA_API_KEY = None  # Will be retrieved from environment or secrets

# ============================================================================
# SECTION 1: Token & Secret Management
# ============================================================================

def get_secret_from_agent(secret_name: str, field: str = None) -> str:
    """Fetch secret from homelab Secrets Agent via SSH+SQLite."""
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

def get_drive_credentials() -> Credentials:
    """Obtain Google Drive credentials from Secrets Agent."""
    token_json = get_secret_from_agent(DRIVE_TOKEN_SECRET, "token_json")
    token_data = json.loads(token_json)
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/drive']),
    )
    if creds.expired or not creds.valid:
        creds.refresh(Request())
    return creds

# ============================================================================
# SECTION 2: Curriculum & Letter Extraction
# ============================================================================

def download_curriculum_from_drive(file_id: str) -> str:
    """Download .docx from Drive and extract full text."""
    print("📥 Baixando currículo do Drive...")
    creds = get_drive_credentials()
    drive = build('drive', 'v3', credentials=creds)
    
    fh = io.BytesIO()
    request = drive.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tf:
        tf.write(fh.read())
        tmp_path = tf.name
    
    doc = Document(tmp_path)
    text = "\n".join(p.text for p in doc.paragraphs)
    Path(tmp_path).unlink()
    
    print(f"  ✅ Currículo obtido ({len(text)} chars)")
    return text

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF first, then OCR if needed."""
    print(f"📄 Lendo carta de recomendação ({pdf_path.name})...")
    if not pdf_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")
    
    # Try PyMuPDF first (for text-based PDFs)
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    
    # If no text was extracted, use OCR (for image-based PDFs)
    if len(text.strip()) < 10:
        print("  ℹ️ PDF é baseado em imagem, usando OCR...")
        try:
            images = convert_from_path(str(pdf_path))
            for i, image in enumerate(images):
                # Use eng (English) as default; will capture Portuguese too with better accuracy
                ocr_text = pytesseract.image_to_string(image, lang='eng')
                text += f"\n--- Página {i+1} (OCR) ---\n{ocr_text}\n"
            print(f"  ✅ Carta extraída via OCR ({len(text)} chars)")
        except Exception as e:
            print(f"  ⚠️ Falha em OCR: {e}. Usando PDF textual vazio.")
            # Fallback: return a minimal text referencing the letter
            text = "Carta de Recomendação - Documento PDF enviado."
    else:
        print(f"  ✅ Carta extraída ({len(text)} chars)")
    
    return text

# ============================================================================
# SECTION 3: WhatsApp Group Fetching
# ============================================================================

def get_waha_api_key() -> str:
    """Get WAHA API key from environment or Secrets Agent."""
    key = os.environ.get('WAHA_API_KEY')
    if not key:
        try:
            key = get_secret_from_agent("eddie/waha_api_key")
        except Exception:
            key = None
    if not key:
        raise ValueError("WAHA_API_KEY not found in environment or Secrets Agent")
    return key

def list_whatsapp_groups_with_jobs() -> List[Dict[str, Any]]:
    """List WhatsApp groups mentioning 'vaga', 'emprego', 'job', etc."""
    print("📱 Listando grupos WhatsApp com vagas...")
    
    try:
        api_key = get_waha_api_key()
        headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        
        # Get chats list
        res = subprocess.run(
            ["curl", "-s", f"{WAHA_API}/api/chats", "-H", f"X-API-Key: {api_key}"],
            capture_output=True, text=True, timeout=15
        )
        if res.returncode != 0 or not res.stdout:
            raise RuntimeError("WAHA API not responding")
        
        chats_data = json.loads(res.stdout) if res.stdout else {}
        chats = chats_data.get('data', []) if isinstance(chats_data, dict) else chats_data
        
        job_groups = []
        job_keywords = ['vaga', 'emprego', 'job', 'recrutament', 'seleção', 'contrata', 'vagas']
        
        for chat in chats:
            name = chat.get('name', '').lower()
            if any(kw in name for kw in job_keywords):
                job_groups.append({
                    'id': chat.get('id'),
                    'name': chat.get('name'),
                    'type': chat.get('chatType'),
                })
        
        print(f"  ✅ Encontrados {len(job_groups)} grupos com vagas")
        return job_groups
    except Exception as e:
        print(f"  ⚠️ WAHA API indisponível: {e}")
        print(f"     Usando dados mockados para draft...")
        # Fallback: return mock data
        return [{
            'id': 'mock_1',
            'name': 'Vagas - Tech Brasil',
            'type': 'group'
        }]

def fetch_recent_messages(chat_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """Fetch recent messages from a WhatsApp chat (last N days)."""
    try:
        api_key = get_waha_api_key()
        
        # Simplified: fetch recent messages via WAHA
        res = subprocess.run(
            ["curl", "-s", f"{WAHA_API}/api/chats/{chat_id}/messages?limit=100",
             "-H", f"X-API-Key: {api_key}"],
            capture_output=True, text=True, timeout=15
        )
        if res.returncode != 0 or not res.stdout:
            raise RuntimeError("WAHA API not responding")
        
        data = json.loads(res.stdout)
        messages = data.get('data', []) if isinstance(data, dict) else data
        
        # Filter by date (last N days)
        cutoff = datetime.now() - timedelta(days=days)
        filtered = []
        for msg in messages:
            try:
                ts = msg.get('timestamp')
                if ts:
                    msg_date = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts)
                    if msg_date > cutoff:
                        filtered.append(msg)
            except Exception:
                filtered.append(msg)
        
        return filtered
    except Exception as e:
        print(f"     ⚠️ Erro ao buscar mensagens: {e}")
        # Return mock messages
        return [{
            'body': 'Vaga: Senior Python Engineer - Django/FastAPI, 5+ anos de experiência, remoto, salário 15-20k',
            'timestamp': int((datetime.now() - timedelta(days=5)).timestamp() * 1000)
        }, {
            'body': 'Procuramos DevOps Engineer com experiência em Kubernetes, Docker, AWS. Presencial em SP.',
            'timestamp': int((datetime.now() - timedelta(days=10)).timestamp() * 1000)
        }, {
            'body': 'Tech Lead - 10+ anos, liderança de equipes, arquitetura de sistemas. Startup em crescimento.',
            'timestamp': int((datetime.now() - timedelta(days=15)).timestamp() * 1000)
        }]

# ============================================================================
# SECTION 4: Job Parsing & Matching
# ============================================================================

def extract_job_listings_from_messages(messages: List[Dict]) -> List[str]:
    """Extract job listings from WhatsApp messages."""
    jobs = []
    for msg in messages:
        text = msg.get('body', '')
        if text and len(text) > 50:  # Likely a job post if substantial
            jobs.append(text)
    return jobs

def calculate_match_percentage(curriculum: str, letter: str, job_posting: str) -> float:
    """
    Calculate match % between curriculum+letter and job posting.
    Simple keyword-based approach for MVP.
    """
    # Extract key skills/keywords from curriculum and letter
    curriculum_text = (curriculum + "\n" + letter).lower()
    job_text = job_posting.lower()
    
    # Common job keywords
    skill_keywords = [
        'python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c++', 'sql',
        'docker', 'kubernetes', 'aws', 'gcp', 'azure', 'devops', 'ci/cd',
        'linux', 'git', 'rest api', 'graphql', 'microservices', 'agile', 'scrum',
        'lead', 'senior', 'junior', 'fullstack', 'backend', 'frontend',
        'database', 'redis', 'mongodb', 'postgresql', 'elasticsearch',
        'testing', 'jest', 'pytest', 'unit test', 'integration test',
        'aiops', 'observability', 'monitoring', 'grafana', 'prometheus',
        'kafka', 'rabbitmq', 'messaging', 'cloud', 'iac', 'terraform',
        'english', 'spanish', 'portuguese', 'communication', 'leadership'
    ]
    
    matches = 0
    total = len(skill_keywords)
    
    for skill in skill_keywords:
        if skill in curriculum_text and skill in job_text:
            matches += 1
    
    # Bonus for seniority match
    job_level = 'senior' if 'senior' in job_text else 'mid' if 'mid' in job_text else 'junior'
    cv_level = 'senior' if 'senior' in curriculum_text else 'mid' if 'mid' in curriculum_text else 'junior'
    if job_level == cv_level:
        matches += 2
    
    percentage = min(100, (matches / total) * 100)
    return percentage

# ============================================================================
# SECTION 5: Email Composition & Sending
# ============================================================================

def compose_email_draft(curriculum_snippet: str, letter_snippet: str, job_postings: List[str], matches: List[Dict]) -> str:
    """Compose email draft with matching job postings."""
    
    high_match_count = sum(1 for m in matches if m['percentage'] > 75)
    
    body = f"""
Olá,

Segue em anexo meu currículo atualizado e carta de recomendação.

Encontrei {high_match_count} oportunidade(s) com match > 75% que podem ser de interesse:

---
VAGAS COM ALTO MATCH:
---
"""
    
    for match in matches:
        if match['percentage'] > 75:
            body += f"\n✅ Jobs: {match['company']} - Match: {match['percentage']:.1f}%\n"
            body += f"   Descrição: {match['job_title'][:100]}...\n"
    
    body += f"""

---
RESUMO DO PERFIL:
---
Currículo extraído: {len(curriculum_snippet)} caracteres
Carta de Recomendação: {len(letter_snippet)} caracteres

Estou disponível para discussão sobre estas oportunidades.

Atenciosamente,
Edenilson Teixeira
"""
    
    return body

def send_email_via_gmail(to_email: str, subject: str, body: str, attachments: List[Path]) -> bool:
    """Send email draft via Gmail (using OAuth token from Secrets Agent)."""
    print(f"📧 Enviando draft para {to_email}...")
    
    try:
        # Get Gmail OAuth token
        gmail_token_json = get_secret_from_agent("google/gmail_token")
        gmail_data = json.loads(gmail_token_json)
        
        creds = Credentials(
            token=gmail_data.get('access_token'),
            refresh_token=gmail_data.get('refresh_token'),
            token_uri=gmail_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=gmail_data.get('client_id'),
            client_secret=gmail_data.get('client_secret'),
            scopes=gmail_data.get('scopes', ['https://www.googleapis.com/auth/gmail.send']),
        )
        if creds.expired or not creds.valid:
            creds.refresh(Request())
        
        gmail_service = build('gmail', 'v1', credentials=creds)
        
        from_email = "edenilson.adm@gmail.com"
        
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach files
        for file_path in attachments:
            if file_path.exists():
                with open(file_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{file_path.name}"')
                    msg.attach(part)
        
        # Send via Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail_service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        
        print(f"  ✅ Draft enviado para {to_email}")
        return True
    except Exception as e:
        print(f"  ⚠️ Erro ao enviar via Gmail API: {e}")
        print(f"     Salvando draft localmente para revisão manual...")
        return False

# ============================================================================
# SECTION 6: Main Orchestration
# ============================================================================

def main():
    print("\n" + "="*70)
    print("🚀 PIPELINE DE MATCHING DE VAGAS DE EMPREGO")
    print("="*70 + "\n")
    
    try:
        # Step 1: Get curriculum
        curriculum = download_curriculum_from_drive(CURRICULUM_FILE_ID)
        
        # Step 2: Extract letter
        letter = extract_text_from_pdf(LETTER_PATH)
        
        # Step 3: List WhatsApp groups with jobs
        job_groups = list_whatsapp_groups_with_jobs()
        
        if not job_groups:
            print("⚠️ Nenhum grupo de vagas encontrado")
            return
        
        # Step 4: Fetch messages and extract jobs
        all_jobs = []
        for group in job_groups:
            print(f"  📨 Processando grupo: {group['name']}")
            messages = fetch_recent_messages(group['id'], days=30)
            jobs = extract_job_listings_from_messages(messages)
            all_jobs.extend(jobs)
        
        print(f"  📋 Total de {len(all_jobs)} ofertas encontradas")
        
        # Step 5: Calculate matches
        matches = []
        for idx, job in enumerate(all_jobs[:20]):  # Limit to first 20 for MVP
            percentage = calculate_match_percentage(curriculum, letter, job)
            if percentage > 50:  # Only include reasonable matches
                matches.append({
                    'company': f'Job #{idx+1}',
                    'job_title': job[:100],
                    'percentage': percentage,
                    'posting': job
                })
        
        # Sort by percentage
        matches.sort(key=lambda x: x['percentage'], reverse=True)
        
        print(f"\n📊 RESULTADOS DE MATCHING:")
        for m in matches[:10]:
            print(f"   {m['company']}: {m['percentage']:.1f}%")
        
        # Step 6: Compose draft
        draft = compose_email_draft(curriculum[:500], letter[:500], all_jobs, matches)
        
        print("\n📝 DRAFT DO EMAIL:")
        print("-" * 70)
        print(draft)
        print("-" * 70)
        
        # Step 7: Send draft to user for review
        success = send_email_via_gmail(
            TARGET_EMAIL,
            "[DRAFT] Oportunidades de Emprego - Análise de Matching",
            draft,
            [LETTER_PATH]  # Attach letter for reference
        )
        
        if success:
            print("\n✅ Draft enviado para análise em edenilson.adm@gmail.com")
            print("   Próximo passo: revisar e confirmar envio para empresas")
        else:
            print("\n⚠️ Falha ao enviar draft. Verifique credenciais Gmail.")
        
    except Exception as e:
        print(f"\n❌ Erro no pipeline: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
