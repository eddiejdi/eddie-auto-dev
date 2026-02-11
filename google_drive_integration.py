#!/usr/bin/env python3
"""
Integração Google Drive para Eddie Assistant
Permite buscar, baixar e gerenciar arquivos no Drive

Autor: Eddie Assistant
Data: 2026
"""

import os
import json
import pickle
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
import logging
import io

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('DriveIntegration')

# Diretório de dados
DATA_DIR = Path(__file__).parent / "drive_data"
DATA_DIR.mkdir(exist_ok=True)

# Arquivos de credenciais
CREDENTIALS_FILE = DATA_DIR / "credentials.json"
TOKEN_FILE = DATA_DIR / "token.pickle"

# Escopos necessários
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

@dataclass
class DriveFile:
    """Representa um arquivo no Drive"""
    id: str
    name: str
    mime_type: str
    size: int = 0
    created_time: datetime = None
    modified_time: datetime = None
    web_view_link: str = ""
    download_url: str = ""
    parents: List[str] = None
    
    @classmethod
    def from_api(cls, data: Dict) -> 'DriveFile':
        """Cria DriveFile a partir dos dados da API"""
        return cls(
            id=data['id'],
            name=data.get('name', 'Sem nome'),
            mime_type=data.get('mimeType', ''),
            size=int(data.get('size', 0)),
            created_time=datetime.fromisoformat(data['createdTime'].replace('Z', '+00:00')) if 'createdTime' in data else None,
            modified_time=datetime.fromisoformat(data['modifiedTime'].replace('Z', '+00:00')) if 'modifiedTime' in data else None,
            web_view_link=data.get('webViewLink', ''),
            download_url=data.get('downloadUrl', ''),
            parents=data.get('parents', [])
        )
    
    def __str__(self) -> str:
        size_mb = self.size / (1024 * 1024) if self.size else 0
        mod_date = self.modified_time.strftime('%d/%m/%Y %H:%M') if self.modified_time else 'N/A'
        return f"{self.name} ({size_mb:.2f} MB) - Modificado: {mod_date}"


class GoogleDriveClient:
    """Cliente para Google Drive API"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        self._load_credentials()
    
    def _load_credentials(self):
        """Carrega credenciais do arquivo"""
        try:
            if TOKEN_FILE.exists():
                with open(TOKEN_FILE, 'rb') as f:
                    self.credentials = pickle.load(f)
                logger.info("Credenciais Drive carregadas do cache")
        except Exception as e:
            logger.warning(f"Erro ao carregar credenciais: {e}")
            self.credentials = None
    
    def _save_credentials(self):
        """Salva credenciais no arquivo"""
        try:
            with open(TOKEN_FILE, 'wb') as f:
                pickle.dump(self.credentials, f)
            logger.info("Credenciais Drive salvas")
        except Exception as e:
            logger.error(f"Erro ao salvar credenciais: {e}")
    
    def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        return self.credentials is not None and self.credentials.valid
    
    async def authenticate(self, auth_code: str = None) -> Tuple[bool, str]:
        """Autentica com Google Drive"""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            
            # Verificar se já tem credenciais válidas
            if self.credentials and self.credentials.valid:
                return True, "Já autenticado"
            
            # Tentar refresh se expirado
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self._save_credentials()
                    return True, "Token atualizado"
                except Exception as e:
                    logger.warning(f"Erro ao atualizar token: {e}")
            
            # Autenticação nova
            if not CREDENTIALS_FILE.exists():
                return False, f"Arquivo credentials.json não encontrado em {CREDENTIALS_FILE}"
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), 
                SCOPES
            )
            
            self.credentials = flow.run_local_server(port=8080)
            self._save_credentials()
            
            return True, "Autenticação completa"
            
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            return False, f"Erro: {str(e)}"
    
    async def ensure_service(self) -> bool:
        """Garante que o serviço está inicializado"""
        if not self.is_authenticated():
            success, msg = await self.authenticate()
            if not success:
                logger.error(f"Falha na autenticação: {msg}")
                return False
        
        if not self.service:
            try:
                from googleapiclient.discovery import build
                self.service = build('drive', 'v3', credentials=self.credentials)
                logger.info("Serviço Drive inicializado")
            except Exception as e:
                logger.error(f"Erro ao inicializar serviço: {e}")
                return False
        
        return True
    
    async def search_files(self,
                          query: str = None,
                          mime_types: List[str] = None,
                          order_by: str = 'modifiedTime desc',
                          max_results: int = 20) -> Tuple[bool, str, List[DriveFile]]:
        """
        Busca arquivos no Drive
        
        Args:
            query: Termo de busca (nome do arquivo)
            mime_types: Lista de MIME types para filtrar
            order_by: Campo de ordenação (ex: 'modifiedTime desc', 'name')
            max_results: Número máximo de resultados
        """
        if not await self.ensure_service():
            return False, "Não autenticado", []
        
        try:
            # Construir query
            q_parts = []
            
            if query:
                # Busca no nome do arquivo (case insensitive)
                q_parts.append(f"name contains '{query}'")
            
            if mime_types:
                mime_conditions = [f"mimeType='{mt}'" for mt in mime_types]
                q_parts.append(f"({' or '.join(mime_conditions)})")
            
            # Excluir lixeira
            q_parts.append("trashed=false")
            
            q_string = ' and '.join(q_parts) if q_parts else None
            
            logger.info(f"Buscando arquivos: query={q_string}, order_by={order_by}")
            
            # Executar busca
            results = self.service.files().list(
                q=q_string,
                pageSize=max_results,
                orderBy=order_by,
                fields="files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, parents)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                return True, "Nenhum arquivo encontrado", []
            
            drive_files = [DriveFile.from_api(f) for f in files]
            
            logger.info(f"Encontrados {len(drive_files)} arquivo(s)")
            return True, f"Encontrados {len(drive_files)} arquivo(s)", drive_files
            
        except Exception as e:
            logger.error(f"Erro ao buscar arquivos: {e}")
            return False, f"Erro: {str(e)}", []
    
    async def search_resume(self) -> Tuple[bool, str, Optional[DriveFile]]:
        """
        Busca o currículo mais recente
        
        Procura por arquivos com nomes comuns de currículo em português/inglês
        """
        search_terms = ['curriculo', 'currículo', 'curriculum', 'cv', 'resume']
        
        # MIME types para PDF e DOCX
        doc_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
            'application/msword',  # DOC
            'application/vnd.google-apps.document'  # Google Docs
        ]
        
        all_results = []
        
        for term in search_terms:
            success, msg, files = await self.search_files(
                query=term,
                mime_types=doc_types,
                order_by='modifiedTime desc',
                max_results=5
            )
            
            if success and files:
                all_results.extend(files)
        
        if not all_results:
            return False, "Nenhum currículo encontrado", None
        
        # Remover duplicatas e ordenar por data de modificação
        unique_files = {f.id: f for f in all_results}
        sorted_files = sorted(unique_files.values(), key=lambda f: f.modified_time, reverse=True)
        
        most_recent = sorted_files[0]
        
        return True, f"Currículo encontrado: {most_recent.name}", most_recent
    
    async def download_file(self, file_id: str, destination: Path) -> Tuple[bool, str]:
        """
        Baixa um arquivo do Drive
        
        Args:
            file_id: ID do arquivo no Drive
            destination: Caminho local para salvar
        """
        if not await self.ensure_service():
            return False, "Não autenticado"
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            
            # Obter metadados do arquivo
            file_metadata = self.service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType', '')
            
            # Se for Google Docs, exportar como PDF
            if mime_type.startswith('application/vnd.google-apps'):
                if 'document' in mime_type:
                    export_mime = 'application/pdf'
                    request = self.service.files().export_media(fileId=file_id, mimeType=export_mime)
                else:
                    return False, "Tipo de arquivo Google não suportado para download"
            else:
                request = self.service.files().get_media(fileId=file_id)
            
            # Download
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    logger.info(f"Download {int(status.progress() * 100)}%")
            
            # Salvar arquivo
            with open(destination, 'wb') as f:
                f.write(fh.getvalue())
            
            logger.info(f"Arquivo salvo em: {destination}")
            return True, f"Arquivo salvo em: {destination}"
            
        except Exception as e:
            logger.error(f"Erro ao baixar arquivo: {e}")
            return False, f"Erro: {str(e)}"


async def main():
    """Teste rápido"""
    client = GoogleDriveClient()
    
    # Autenticar
    if not client.is_authenticated():
        print("🔐 Autenticando com Google Drive...")
        success, msg = await client.authenticate()
        print(f"   {msg}")
        if not success:
            return
    
    # Buscar currículo
    print("\n📄 Buscando currículo mais recente...")
    success, msg, resume_file = await client.search_resume()
    print(f"   {msg}")
    
    if success and resume_file:
        print(f"\n✅ Encontrado:")
        print(f"   Nome: {resume_file.name}")
        print(f"   Tamanho: {resume_file.size / 1024:.2f} KB")
        print(f"   Modificado: {resume_file.modified_time}")
        print(f"   Link: {resume_file.web_view_link}")
        
        # Baixar
        download_path = Path("/tmp") / resume_file.name
        print(f"\n⬇️ Baixando para {download_path}...")
        success, msg = await client.download_file(resume_file.id, download_path)
        print(f"   {msg}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
