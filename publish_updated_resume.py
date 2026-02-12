#!/usr/bin/env python3
"""
Publica uma versão atualizada do currículo no Google Drive usando o token
armazenado no Secrets Agent (homelab). Cria um novo Google Doc com o conteúdo.
"""
import base64
import io
import json
import subprocess
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Conteúdo atualizado (aprovado)
UPDATED_SECTION = """
**B3 S.A. — Analista de Operações / SRE** (Jul/2024 — Presente)

Atuação em operações e confiabilidade de serviços com foco em automação,
observabilidade e integração de plataformas críticas.

- AIOps & Observabilidade: Implementação e evolução de soluções AIOps para
detecção pró‑ativa, alerting e automação de respostas a anomalias.
- Pipelines & CI/CD: Projetos e operação de pipelines de entrega contínua
  (build/deploy), incluindo automações para testes, rollbacks e versionamento.
- Banco de dados / Migrações: Gestão e automação de migrations com Flyway,
  garantindo deploys seguros e rastreáveis do schema.
- Atendimento de incidentes: Participação em on‑call, runbooks, resposta a
  incidentes e condução de postmortems para redução de MTTR.
- Modelos LLM: Instalação, configuração e operação de modelos LLM em produção
  (deploy, serving, tuneamento e integração com fluxos existentes).
- Integração de sistemas legados: Projetos de integração entre sistemas legados
  e microserviços via APIs e barramento de mensagens, com foco em compatibilidade
  e resiliência.
- Datalake & Ingestão: Concepção e suporte ao pipeline de ingestão para datalake
  (ETL/ELT), organização de dados e governança mínima para análises.
"""

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"
TOKEN_SECRET_NAME = "google/gdrive_token_edenilson_teixeira"
TOKEN_SECRET_FIELD = "token_json"


def get_token_from_agent():
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        (
            "python3 - <<'PY'",
            "import sqlite3, base64, json, sys",
            "conn = sqlite3.connect('" + SECRETS_AGENT_TOKEN_PATH + "')",
            "c = conn.cursor()",
            "c.execute(\"SELECT value FROM secrets_store WHERE name='" + TOKEN_SECRET_NAME + "' AND field='" + TOKEN_SECRET_FIELD + "'\")",
            "row = c.fetchone()",
            "conn.close()",
            "if not row: print('NOT_FOUND'); sys.exit(0)",
            "print(base64.b64decode(row[0]).decode())",
            "PY",
        )
    ]
    # join parts to single command string
    cmd = ["ssh", f"homelab@{SECRETS_AGENT_HOST}", "python3 - <<'PY'\nimport sqlite3, base64, sys\nconn = sqlite3.connect('" + SECRETS_AGENT_TOKEN_PATH + "')\nc = conn.cursor()\nc.execute(\"SELECT value FROM secrets_store WHERE name='" + TOKEN_SECRET_NAME + "' AND field='" + TOKEN_SECRET_FIELD + "'\")\nrow = c.fetchone()\nconn.close()\nif not row:\n    print('NOT_FOUND')\n    sys.exit(0)\nprint(base64.b64decode(row[0]).decode())\nPY"]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"failed to fetch token: {res.stderr}")
    out = res.stdout.strip()
    if out == "NOT_FOUND":
        raise KeyError("token not found in secrets agent")
    return json.loads(out)


def create_google_doc(creds: Credentials, title: str, content: str):
    drive = build('drive', 'v3', credentials=creds)
    # Create a Google Doc by uploading a plain text and converting
    media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')),
                              mimetype='text/plain', resumable=False)
    file_metadata = {'name': title, 'mimeType': 'application/vnd.google-apps.document'}
    f = drive.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
    return f


def main():
    print('Obtendo token do Secrets Agent...')
    token_data = get_token_from_agent()
    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/drive'])
    )
    if not creds.valid:
        creds.refresh(Request())
    title = 'Curriculum_Edenilson_Atualizado_B3_Analista_Operacoes_SRE'
    body = UPDATED_SECTION
    f = create_google_doc(creds, title, body)
    print('Criado documento:', f.get('webViewLink'))


if __name__ == '__main__':
    main()
