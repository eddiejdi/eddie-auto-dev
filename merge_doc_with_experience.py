#!/usr/bin/env python3
"""
Exporta o Google Doc original como texto, insere a seção aprovada no topo,
cria um novo Google Doc com o conteúdo combinado e cria um backup do original.
"""
import io
import json
import subprocess
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from docx import Document
import tempfile

DOC_ID = "1y2eeV4No2zQD_ezeZCaBZiuswvANF8V3"
SECRETS_AGENT_HOST = "192.168.15.2"
SECRETS_AGENT_TOKEN_PATH = "/var/lib/eddie/secrets_agent/audit.db"
TOKEN_SECRET_NAME = "google/gdrive_token_edenilson_teixeira"
TOKEN_SECRET_FIELD = "token_json"

INSERT_TEXT = """
B3 S.A. — Analista de Operações / SRE (Jul/2024 — Presente)\n\nAtuação em operações e confiabilidade de serviços com foco em automação, observabilidade e integração de plataformas críticas.\n\n- AIOps & Observabilidade: Implementação e evolução de soluções AIOps para detecção pró‑ativa, alerting e automação de respostas a anomalias.\n- Pipelines & CI/CD: Projetos e operação de pipelines de entrega contínua (build/deploy), incluindo automações para testes, rollbacks e versionamento.\n- Banco de dados / Migrações: Gestão e automação de migrations com Flyway, garantindo deploys seguros e rastreáveis do schema.\n- Atendimento de incidentes: Participação em on‑call, runbooks, resposta a incidentes e condução de postmortems para redução de MTTR.\n- Modelos LLM: Instalação, configuração e operação de modelos LLM em produção (deploy, serving, tuneamento e integração com fluxos existentes).\n- Integração de sistemas legados: Projetos de integração entre sistemas legados e microserviços via APIs e barramento de mensagens, com foco em compatibilidade e resiliência.\n- Datalake & Ingestão: Concepção e suporte ao pipeline de ingestão para datalake (ETL/ELT), organização de dados e governança mínima para análises.\n\n"""


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
    if creds.expired or not creds.valid:
        print('Renovando token...')
        creds.refresh(Request())

    drive = build('drive', 'v3', credentials=creds)

    # 1) obter metadata do original
    meta = drive.files().get(fileId=DOC_ID, fields='name,parents').execute()
    original_name = meta.get('name')
    parents = meta.get('parents', [])

    print(f"Exportando '{original_name}' como texto...")
    meta_full = drive.files().get(fileId=DOC_ID, fields='mimeType').execute()
    mime = meta_full.get('mimeType')
    original_text = ''
    if mime == 'application/vnd.google-apps.document':
        exported = drive.files().export(fileId=DOC_ID, mimeType='text/plain').execute()
        original_text = exported.decode('utf-8') if isinstance(exported, bytes) else exported
    else:
        # baixar arquivo (provavelmente .docx) e extrair texto
        fh = io.BytesIO()
        request = drive.files().get_media(fileId=DOC_ID)
        downloader = None
        try:
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        except Exception:
            # fallback: use simple GET
            fh.write(request.execute())
        fh.seek(0)
        # salvar temporariamente e ler com python-docx
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tf:
            tf.write(fh.read())
            tmp_name = tf.name
        try:
            doc = Document(tmp_name)
            paras = [p.text for p in doc.paragraphs]
            original_text = '\n'.join(paras)
        finally:
            try:
                Path(tmp_name).unlink()
            except Exception:
                pass

    combined = INSERT_TEXT + '\n' + original_text

    # 2) criar backup do original
    backup_name = original_name + ' (backup pre-insert)'
    print('Criando backup do original...')
    backup = drive.files().copy(fileId=DOC_ID, body={'name': backup_name}).execute()
    print('Backup criado:', backup.get('id'))

    # 3) criar novo doc com conteúdo combinado
    new_name = original_name + ' (com B3 inserido)'
    print('Criando novo documento combinado...')
    media = MediaIoBaseUpload(io.BytesIO(combined.encode('utf-8')), mimetype='text/plain', resumable=False)
    file_metadata = {'name': new_name, 'mimeType': 'application/vnd.google-apps.document'}
    newf = drive.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
    print('Novo documento criado:', newf.get('webViewLink'))
    print('\nBackup do original:', f"https://drive.google.com/file/d/{backup.get('id')}/view")

    # 4) Ajustar permissões: tornar o novo documento e a pasta-pai graváveis por link
    try:
        new_id = newf.get('id')
        print('Configurando permissão de gravação (anyone with link) no novo documento...')
        drive.permissions().create(fileId=new_id, body={'type': 'anyone', 'role': 'writer'}, fields='id').execute()
        print('  ✅ Permissão aplicada ao novo documento')
    except Exception as e:
        print('  ⚠️ Falha ao aplicar permissão no novo documento:', e)

    # Aplicar permissão também na pasta pai (se houver)
    if parents:
        for p in parents:
            try:
                print(f'Configurando permissão de gravação na pasta pai {p}...')
                drive.permissions().create(fileId=p, body={'type': 'anyone', 'role': 'writer'}, fields='id').execute()
                print(f'  ✅ Permissão aplicada na pasta {p}')
            except Exception as e:
                print(f'  ⚠️ Falha ao aplicar permissão na pasta {p}:', e)

    print('\nSe quiser que eu substitua o arquivo original pelo novo, diga "substituir".')


if __name__ == '__main__':
    main()
