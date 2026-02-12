#!/usr/bin/env python3
"""
Insere a seção de experiência aprovada no Google Doc existente.
"""
import json
import subprocess
import sys
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

DOC_ID = "1y2eeV4No2zQD_ezeZCaBZiuswvANF8V3"  # documento original

INSERT_TEXT = """
\n\nB3 S.A. — Analista de Operações / SRE (Jul/2024 — Presente)\n\nAtuação em operações e confiabilidade de serviços com foco em automação, observabilidade e integração de plataformas críticas.\n\n- AIOps & Observabilidade: Implementação e evolução de soluções AIOps para detecção pró‑ativa, alerting e automação de respostas a anomalias.\n- Pipelines & CI/CD: Projetos e operação de pipelines de entrega contínua (build/deploy), incluindo automações para testes, rollbacks e versionamento.\n- Banco de dados / Migrações: Gestão e automação de migrations com Flyway, garantindo deploys seguros e rastreáveis do schema.\n- Atendimento de incidentes: Participação em on‑call, runbooks, resposta a incidentes e condução de postmortems para redução de MTTR.\n- Modelos LLM: Instalação, configuração e operação de modelos LLM em produção (deploy, serving, tuneamento e integração com fluxos existentes).\n- Integração de sistemas legados: Projetos de integração entre sistemas legados e microserviços via APIs e barramento de mensagens, com foco em compatibilidade e resiliência.\n- Datalake & Ingestão: Concepção e suporte ao pipeline de ingestão para datalake (ETL/ELT), organização de dados e governança mínima para análises.\n\n"""

SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"
TOKEN_SECRET_NAME = "google/gdrive_token_edenilson_teixeira"
TOKEN_SECRET_FIELD = "token_json"


def get_token_from_agent():
    cmd = [
        "ssh", f"homelab@{SECRETS_AGENT_HOST}",
        "python3 - <<'PY'\nimport sqlite3, base64, sys\nconn = sqlite3.connect('" + SECRETS_AGENT_TOKEN_PATH + "')\nc = conn.cursor()\nc.execute(\"SELECT value FROM secrets_store WHERE name='" + TOKEN_SECRET_NAME + "' AND field='" + TOKEN_SECRET_FIELD + "'\")\nrow = c.fetchone()\nconn.close()\nif not row:\n    print('NOT_FOUND')\n    sys.exit(0)\nprint(base64.b64decode(row[0]).decode())\nPY"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if res.returncode != 0:
        raise RuntimeError(f"failed to fetch token: {res.stderr}")
    out = res.stdout.strip()
    if out == "NOT_FOUND":
        raise KeyError("token not found in secrets agent")
    return json.loads(out)


def main():
    print("Obtendo token do Secrets Agent...")
    token_data = get_token_from_agent()
    creds = Credentials(
        token=token_data['token'],
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive'])
    )
    if creds.expired or not creds.valid:
        print('Renovando token...')
        creds.refresh(Request())

    docs = build('docs', 'v1', credentials=creds)
    doc = docs.documents().get(documentId=DOC_ID).execute()
    body = doc.get('body', {})
    content = body.get('content', [])
    # insert at end
    end_index = content[-1].get('endIndex', 1)
    requests = [
        {
            'insertText': {
                'location': {'index': end_index - 1 if end_index>0 else 1},
                'text': INSERT_TEXT
            }
        }
    ]
    print('Inserindo seção no documento...')
    resp = docs.documents().batchUpdate(documentId=DOC_ID, body={'requests': requests}).execute()
    print('Inserção feita. Atualizações:', resp.get('replies'))
    print('Documento:', f'https://docs.google.com/document/d/{DOC_ID}/edit')


if __name__ == '__main__':
    main()
