#!/usr/bin/env python3
"""Reescreve o tool 'video_generation' no DB do Open WebUI com conteúdo seguro.

Uso:
  python scripts/fix_tool_v4.py --db /path/to/webui.db --tool-name video_generation

Observações:
- O conteúdo inserido evita f-strings aninhadas e usa código estático simples.
- Ajuste `NEXTCLOUD_*` via variáveis de ambiente no servidor antes de executar.
"""
from __future__ import annotations

import argparse
import sqlite3
import textwrap
import uuid
import time
from pathlib import Path
from typing import Optional


def build_tool_content() -> str:
    """Retorna o conteúdo do script do tool (evita f-strings aninhadas).

    O script salvo é consciente de variáveis de ambiente para Nextcloud e usa chamadas
    externas (subprocess) para a etapa de geração de vídeo. Mantenha o conteúdo simples
    para evitar erros de parsing quando armazenado no banco.
    """
    content = textwrap.dedent('''\
#!/usr/bin/env python3
"""Tool de geração de vídeo (versão segura).

Este arquivo é executado pelo Open WebUI quando o tool é invocado.
Ele lê variáveis de ambiente para Nextcloud e chama o gerador de vídeo por subprocesso.
"""
import os
import sys
import subprocess
from pathlib import Path
import requests

def run(prompt: str) -> str:
    """Gera o vídeo a partir de `prompt` e retorna o caminho do arquivo gerado.

    Saídas e nomes são previsíveis para facilitar movimentação posterior.
    """
    out_dir = Path('/tmp/video_generation_outputs')
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / 'video_output.mp4'

    # Exemplo de comando externo (ajuste conforme ambiente/AnimateDiff wrapper)
    cmd = [
        'python3',
        '/usr/local/bin/animate_diff_generate.py',
        '--prompt', prompt,
        '--out', str(output_file),
    ]

    try:
        subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
    except subprocess.CalledProcessError as e:
        raise SystemExit(f'Video generation failed: {e}')

    if not output_file.exists():
        raise SystemExit('Output file not found after generation')

    return str(output_file)

def upload_to_nextcloud(local_path: str, remote_user: str) -> str:
    """Move o arquivo para a pasta Nextcloud do usuário e cria share público.

    Requer variáveis de ambiente: NEXTCLOUD_BASE_URL, NEXTCLOUD_API_TOKEN
    Retorna a URL pública (OCS) ou lança exceção.
    """
    base = os.environ.get('NEXTCLOUD_BASE_URL')
    token = os.environ.get('NEXTCLOUD_API_TOKEN')
    if not base or not token:
        raise SystemExit('NEXTCLOUD_BASE_URL or NEXTCLOUD_API_TOKEN not set')

    # Upload via WebDAV (simplificado) -- ajustar conforme layout do servidor
    user_files_path = f"/remote.php/dav/files/{remote_user}/"
    upload_url = base.rstrip('/') + user_files_path + Path(local_path).name

    with open(local_path, 'rb') as f:
        r = requests.put(upload_url, data=f, headers={'Authorization': f'Bearer {token}'})
    if r.status_code not in (200,201,204):
        raise SystemExit(f'Nextcloud upload failed: {r.status_code} {r.text}')

    # Criar share público via OCS
    ocs_url = base.rstrip('/') + '/ocs/v2.php/apps/files_sharing/api/v1/shares'
    payload = {'path': f'/'+Path(local_path).name, 'shareType': 3}
    r2 = requests.post(ocs_url, data=payload, headers={'OCS-APIRequest': 'true', 'Authorization': f'Bearer {token}'})
    if r2.status_code not in (200,201):
        raise SystemExit(f'Nextcloud share failed: {r2.status_code} {r2.text}')

    # parse response (simples)
    try:
        data = r2.json()
        url = data['ocs']['data']['url']
        return url
    except Exception:
        raise SystemExit('Failed to parse Nextcloud share response')

def main():
    prompt = os.environ.get('TOOL_PROMPT', 'Uma animação simples de teste')
    user = os.environ.get('TOOL_USER', 'anonymous')
    generated = run(prompt)
    share = upload_to_nextcloud(generated, user)
    print(share)

if __name__ == '__main__':
    main()
''')
    return content


def update_tool(db_path: Path, tool_name: str, content: str) -> None:
    """Atualiza (ou insere) o tool no banco SQLite do Open WebUI.

    Args:
        db_path: caminho para o arquivo SQLite do Open WebUI.
        tool_name: nome do tool a ser atualizado.
        content: conteúdo do script a ser salvo.
    """
    if not db_path.exists():
        raise SystemExit(f'DB not found: {db_path}')

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        before = conn.total_changes
        cur.execute('UPDATE tool SET content = ? WHERE name = ?', (content, tool_name))
        conn.commit()
        after = conn.total_changes
        changed = after - before
        if changed == 0:
            # Tentativa de inserir se não existir
            new_id = uuid.uuid4().hex
            now = int(time.time())
            # Tentar obter um user_id existente para satisfazer NOT NULL
            cur.execute('SELECT id FROM user LIMIT 1')
            row = cur.fetchone()
            user_id = row[0] if row and row[0] else new_id
            specs = '{}'
            meta = '{}'
            cur.execute(
                'INSERT INTO tool (id, user_id, name, content, specs, meta, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (new_id, user_id, tool_name, content, specs, meta, now, now),
            )
            conn.commit()
            print('Tool inserido/atualizado (insert)')
        else:
            print('Tool atualizado (update)')
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Atualiza tool video_generation no DB do Open WebUI')
    p.add_argument('--db', required=True, help='Caminho para o SQLite DB do Open WebUI')
    p.add_argument('--tool-name', default='video_generation', help='Nome do tool a atualizar')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)
    content = build_tool_content()
    update_tool(db_path, args.tool_name, content)


if __name__ == '__main__':
    main()
