#!/usr/bin/env python3
"""
Baixa arquivos da Google Drive (incluindo Shared Drives) e salva em um diretório.
Usa os tokens em `specialized_agents/gdrive_tokens` já presentes no repositório.

Exemplo:
  python3 tools/gdrive_download_and_process.py --out /home/homelab/gdrive_docs --folder RPA4All
"""
import argparse
import os
import io
import importlib.util
from googleapiclient.http import MediaIoBaseDownload

# Carrega GDriveAgent diretamente do arquivo para evitar importar o package
spec = importlib.util.spec_from_file_location("gdrive_agent", os.path.join(os.path.dirname(__file__), '..', 'specialized_agents', 'gdrive_agent.py'))
gdrv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gdrv)
GDriveAgent = gdrv.GDriveAgent


def find_folder(service, name):
    resp = service.files().list(
        q=f"name='{name}' and mimeType='application/vnd.google-apps.folder'",
        spaces='drive', fields='files(id,name)',
        includeItemsFromAllDrives=True, supportsAllDrives=True, corpora='allDrives'
    ).execute()
    return resp.get('files', [])


def download_file(service, fid, dest_path, mimeType):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if mimeType == 'application/vnd.google-apps.document':
        req = service.files().export(fileId=fid, mimeType='text/plain')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        with open(dest_path, 'wb') as out:
            out.write(fh.getvalue())
    else:
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        with open(dest_path, 'wb') as out:
            out.write(fh.getvalue())


def walk_and_download(service, folder_id, base_path):
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents",
            spaces='drive', fields='nextPageToken, files(id,name,mimeType)',
            includeItemsFromAllDrives=True, supportsAllDrives=True, corpora='allDrives', pageToken=page_token
        ).execute()
        for f in resp.get('files', []):
            fid = f['id']
            name = f['name']
            mtype = f.get('mimeType', '')
            if mtype == 'application/vnd.google-apps.folder':
                new_base = os.path.join(base_path, name)
                walk_and_download(service, fid, new_base)
            else:
                dest = os.path.join(base_path, f"{name}")
                print('Downloading', name, '->', dest)
                try:
                    download_file(service, fid, dest, mtype)
                except Exception as e:
                    print('Failed to download', name, e)
        page_token = resp.get('nextPageToken')
        if not page_token:
            break


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True, help='Diretório destino para salvar arquivos')
    p.add_argument('--folder', default='RPA4All', help='Nome da pasta compartilhada a baixar')
    p.add_argument('--tokens-dir', default=os.path.join(os.path.dirname(__file__), '..', 'specialized_agents', 'gdrive_tokens'))
    args = p.parse_args()

    outdir = args.out
    os.makedirs(outdir, exist_ok=True)

    g = GDriveAgent(tokens_dir=os.path.abspath(args.tokens_dir))
    accounts = []
    for fn in os.listdir(g.tokens_dir):
        if fn.endswith('.json'):
            accounts.append(fn.replace('_at_', '@').rsplit('.', 1)[0])

    print('Accounts found:', accounts)

    for acc in accounts:
        print('Processing account', acc)
        try:
            service = g.load_service_for_account(acc)
        except Exception as e:
            print('Failed to load service for', acc, e)
            continue

        folders = find_folder(service, args.folder)
        if not folders:
            print('Folder', args.folder, 'not found for', acc)
            continue

        for fd in folders:
            fid = fd['id']
            print('Found folder', fd['name'], 'id', fid)
            out_base = os.path.join(outdir, acc.replace('@', '_at_'), fd['name'])
            os.makedirs(out_base, exist_ok=True)
            walk_and_download(service, fid, out_base)

    print('All done')


if __name__ == '__main__':
    main()
