#!/usr/bin/env python3
"""
Baixa arquivos do Google Drive usando credenciais salvas em JSON (refresh tokens).
Espera arquivos JSON no diretório `tokens_dir` com os campos: token, refresh_token,
client_id, client_secret, token_uri, scopes.

Uso:
  python3 tools/gdrive_fetch_direct.py --out /home/homelab/gdrive_docs --folder RPA4All --tokens-dir specialized_agents/gdrive_tokens
"""
import argparse
import json
import os
import io
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def load_accounts(tokens_dir):
    accounts = []
    for fn in os.listdir(tokens_dir):
        if not fn.endswith('.json'):
            continue
        path = os.path.join(tokens_dir, fn)
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        account = fn.replace('_at_', '@').rsplit('.', 1)[0]
        data['account'] = account
        data['path'] = path
        accounts.append(data)
    return accounts


def build_service(token_data):
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes') or ['https://www.googleapis.com/auth/drive']
    )
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service


def find_folders(service, name):
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
    p.add_argument('--out', required=True)
    p.add_argument('--folder', default='RPA4All')
    p.add_argument('--tokens-dir', default=os.path.join('specialized_agents', 'gdrive_tokens'))
    args = p.parse_args()

    tokens_dir = args.tokens_dir
    outdir = args.out
    os.makedirs(outdir, exist_ok=True)

    accounts = load_accounts(tokens_dir)
    print('Accounts found:', [a['account'] for a in accounts])

    for acc in accounts:
        print('Processing account', acc['account'])
        try:
            service = build_service(acc)
        except Exception as e:
            print('Failed to build service for', acc['account'], e)
            continue

        folders = find_folders(service, args.folder)
        if not folders:
            print('Folder', args.folder, 'not found for', acc['account'])
            continue

        for fd in folders:
            fid = fd['id']
            print('Found folder', fd['name'], 'id', fid)
            out_base = os.path.join(outdir, acc['account'].replace('@', '_at_'), fd['name'])
            os.makedirs(out_base, exist_ok=True)
            walk_and_download(service, fid, out_base)

    print('All done')


if __name__ == '__main__':
    main()
