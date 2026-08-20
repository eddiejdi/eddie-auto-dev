#!/usr/bin/env python3
"""
Script para buscar e processar PDFs recentes do WhatsApp
"""
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Diretório de dados do WhatsApp
DATA_DIR = Path(__file__).parent / "whatsapp_data"
DB_PATH = DATA_DIR / "conversations.db"

def get_waha_config():
    """Obtém configuração do WAHA"""
    # Tentar diferentes portas
    ports = [3000, 3001]
    for port in ports:
        try:
            resp = requests.get(f"http://localhost:{port}/health", timeout=2)
            print(f"✓ WAHA encontrado na porta {port}")
            return f"http://localhost:{port}"
        except:
            continue
    return None

def check_recent_messages():
    """Verifica mensagens recentes no banco de dados local"""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return []
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Buscar mensagens das últimas 24 horas
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        SELECT chat_id, sender, content, timestamp 
        FROM messages 
        WHERE timestamp > ? AND (
            lower(content) LIKE '%pdf%' OR 
            lower(content) LIKE '%documento%' OR
            lower(content) LIKE '%arquivo%'
        )
        ORDER BY timestamp DESC
        LIMIT 10
    ''', (yesterday,))
    
    messages = cursor.fetchall()
    conn.close()
    
    return messages

def download_from_telegram():
    """Tenta buscar PDF do Telegram como alternativa"""
    print("\n📱 Tentando buscar do Telegram...")
    
    # Verificar se há credenciais do Telegram
    try:
        from telegram_bot import TelegramBot
        bot = TelegramBot()
        
        # Buscar atualizações recentes
        updates = bot.get_updates(limit=20)
        
        for update in updates:
            if 'message' in update and 'document' in update['message']:
                doc = update['message']['document']
                if doc.get('mime_type') == 'application/pdf':
                    print(f"📄 PDF encontrado: {doc.get('file_name', 'sem nome')}")
                    
                    # Baixar arquivo
                    file_id = doc['file_id']
                    file_path = bot.download_file(file_id)
                    
                    if file_path:
                        print(f"✓ PDF baixado: {file_path}")
                        return file_path
        
        print("❌ Nenhum PDF recente encontrado no Telegram")
        return None
        
    except Exception as e:
        print(f"❌ Erro ao buscar do Telegram: {e}")
        return None

def list_recent_files():
    """Lista arquivos PDF recentes no sistema"""
    print("\n📂 Procurando PDFs recentes no sistema...")
    
    # Diretórios comuns de download
    search_dirs = [
        Path.home() / "Downloads",
        Path.home() / "Documentos",
        Path.home() / "Desktop",
        Path("/tmp"),
        DATA_DIR
    ]
    
    pdfs = []
    for directory in search_dirs:
        if directory.exists():
            for pdf in directory.glob("*.pdf"):
                # Verificar se foi modificado nas últimas 24 horas
                mtime = datetime.fromtimestamp(pdf.stat().st_mtime)
                if datetime.now() - mtime < timedelta(days=1):
                    pdfs.append((pdf, mtime))
    
    # Ordenar por data de modificação (mais recente primeiro)
    pdfs.sort(key=lambda x: x[1], reverse=True)
    
    if pdfs:
        print(f"\n✓ Encontrados {len(pdfs)} PDFs recentes:")
        for i, (pdf, mtime) in enumerate(pdfs[:10], 1):
            print(f"  {i}. {pdf.name} ({mtime.strftime('%Y-%m-%d %H:%M')})")
            print(f"     {pdf}")
        
        return pdfs
    else:
        print("❌ Nenhum PDF recente encontrado")
        return []

def extract_text_from_pdf(pdf_path):
    """Extrai texto de um PDF"""
    try:
        # Tentar com PyPDF2
        import PyPDF2
        
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            return text
    except ImportError:
        print("⚠️  PyPDF2 não está instalado. Tentando pdftotext...")
        
        # Tentar com pdftotext (CLI)
        try:
            result = subprocess.run(
                ['pdftotext', str(pdf_path), '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"❌ Erro ao extrair texto: {result.stderr}")
                return None
        except FileNotFoundError:
            print("❌ pdftotext não encontrado. Instale com: sudo apt install poppler-utils")
            return None
        except Exception as e:
            print(f"❌ Erro ao extrair texto: {e}")
            return None
    except Exception as e:
        print(f"❌ Erro ao processar PDF: {e}")
        return None

def main():
    print("🔍 Buscando PDF recente do WhatsApp...\n")
    
    # 1. Verificar WAHA
    waha_url = get_waha_config()
    if waha_url:
        print(f"✓ WAHA disponível: {waha_url}")
    else:
        print("⚠️  WAHA não está rodando")
    
    # 2. Verificar mensagens recentes no DB
    messages = check_recent_messages()
    if messages:
        print(f"\n✓ Encontradas {len(messages)} mensagens relacionadas a documentos:")
        for msg in messages[:5]:
            chat_id, sender, content, timestamp = msg
            print(f"  • {timestamp}: {content[:100]}...")
    
    # 3. Listar PDFs recentes no sistema
    pdfs = list_recent_files()
    
    if pdfs:
        print("\n" + "="*60)
        print("📄 PDF mais recente encontrado:")
        pdf_path, mtime = pdfs[0]
        print(f"   Arquivo: {pdf_path}")
        print(f"   Data: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Extrair texto
        print("\n📖 Extraindo texto do PDF...")
        text = extract_text_from_pdf(pdf_path)
        
        if text:
            print(f"\n✓ Texto extraído ({len(text)} caracteres)")
            print("\n" + "="*60)
            print("PREVIEW DO CONTEÚDO:")
            print("="*60)
            print(text[:2000])
            if len(text) > 2000:
                print("\n... (conteúdo truncado) ...")
            print("="*60)
            
            # Salvar em arquivo
            output_file = Path("/tmp/whatsapp_pdf_content.txt")
            output_file.write_text(text)
            print(f"\n✓ Conteúdo completo salvo em: {output_file}")
            
            return str(pdf_path)
        else:
            print("❌ Não foi possível extrair o texto")
    else:
        print("\n❌ Nenhum PDF recente encontrado no sistema")
        print("\nDicas:")
        print("  • Verifique se o PDF foi realmente baixado")
        print("  • Confira a pasta Downloads")
        print("  • Execute: python3 fetch_whatsapp_pdf.py")
    
    return None

if __name__ == "__main__":
    result = main()
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
