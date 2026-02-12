#!/usr/bin/env python3
"""
Baixa (opcional) documentos do Google Drive e converte para JSONL de treinamento.

Uso:
  python3 tools/gdrive_to_training.py --out training_data/gdrive_import.jsonl \
    --download-dir /home/homelab/gdrive_docs --tokens-dir specialized_agents/gdrive_tokens \
    --folder RPA4All --download

Se `--download` for passado, o script invoca `tools/gdrive_fetch_direct.py` para baixar
os arquivos para `--download-dir` (requer tokens em `--tokens-dir`).
"""
from __future__ import annotations
import argparse
import os
import sys
import json
from pathlib import Path
import subprocess
from datetime import datetime


def extract_text_from_pdf(pdf_path: Path) -> str | None:
    try:
        import PyPDF2
        with open(pdf_path, 'rb') as fh:
            reader = PyPDF2.PdfReader(fh)
            parts = []
            for page in reader.pages:
                txt = page.extract_text() or ''
                parts.append(txt)
            return "\n".join(parts)
    except Exception:
        # fallback to pdftotext CLI
        try:
            res = subprocess.run(['pdftotext', str(pdf_path), '-'], capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                return res.stdout
        except Exception:
            return None


def extract_text_from_docx(path: Path) -> str | None:
    try:
        from docx import Document
        doc = Document(path)
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)
    except Exception:
        return None


def read_text_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return None


def generate_chunks(text: str, max_chars: int = 1000, overlap: int = 200):
    if not text:
        return []
    i = 0
    L = len(text)
    chunks = []
    while i < L:
        end = min(i + max_chars, L)
        chunk = text[i:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == L:
            break
        i = end - overlap
    return chunks


def convert_downloads_to_jsonl(download_dir: Path, out_jsonl: Path):
    exts_text = {'.txt', '.md', '.csv', '.json', '.log', '.html', '.htm'}
    exts_docx = {'.docx'}
    exts_pdf = {'.pdf'}

    out_jsonl.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_jsonl.open('w', encoding='utf-8') as out:
        for root, _, files in os.walk(download_dir):
            for fn in files:
                path = Path(root) / fn
                rel = path.relative_to(download_dir)
                text = None

                if path.suffix.lower() in exts_text:
                    text = read_text_file(path)
                elif path.suffix.lower() in exts_pdf:
                    text = extract_text_from_pdf(path)
                elif path.suffix.lower() in exts_docx:
                    text = extract_text_from_docx(path)
                else:
                    # try to read as text as a last resort
                    text = read_text_file(path)

                if not text:
                    continue

                # normalize whitespace
                text = "\n".join([ln.rstrip() for ln in text.splitlines() if ln.strip()])

                chunks = generate_chunks(text)
                for idx, chunk in enumerate(chunks):
                    entry = {
                        'prompt': f'DOCUMENT: {rel} \nTrecho {idx+1}',
                        'completion': chunk,
                        'context': f'gdrive_import {rel}'
                    }
                    out.write(json.dumps(entry, ensure_ascii=False) + '\n')
                    written += 1

    return written


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--download-dir', required=True, help='Diretório onde os arquivos do Drive serão (ou já estão)')
    p.add_argument('--out', required=True, help='Arquivo JSONL de saída (ex: training_data/gdrive_import_YYYYMMDD.jsonl)')
    p.add_argument('--tokens-dir', default=os.path.join('specialized_agents', 'gdrive_tokens'))
    p.add_argument('--folder', default='RPA4All', help='Nome da pasta a baixar (passar para o fetch)')
    p.add_argument('--download', action='store_true', help='Se presente, chama o downloader antes de converter')
    args = p.parse_args()

    download_dir = Path(args.download_dir)
    out_path = Path(args.out)

    if args.download:
        # chamar script existente para baixar
        cmd = [sys.executable, os.path.join('tools', 'gdrive_fetch_direct.py'), '--out', str(download_dir), '--folder', args.folder, '--tokens-dir', args.tokens_dir]
        print('Executando downloader:', ' '.join(cmd))
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print('Erro ao executar downloader:', e)
            sys.exit(1)

    if not download_dir.exists():
        print('Diretório de download não existe:', download_dir)
        sys.exit(1)

    print('Convertendo arquivos em', download_dir, '->', out_path)
    written = convert_downloads_to_jsonl(download_dir, out_path)
    print(f'Escritas {written} entradas em {out_path}')


if __name__ == '__main__':
    main()
