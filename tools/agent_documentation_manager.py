#!/usr/bin/env python3
"""
Agent Documentation Manager
Levanta agentes não documentados, cria documentação e extrai secrets
"""

import asyncio
import json
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configurações
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
AGENTS_DIR = PROJECT_ROOT / "specialized_agents"
TOOLS_DIR = PROJECT_ROOT / "tools"

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "shared-coder")
SECRETS_AGENT_URL = os.getenv("SECRETS_AGENT_URL", "http://localhost:8200")

# Padrões para extrair secrets
SECRET_PATTERNS = {
    "api_key": r"['\"]?(?:api_key|apikey|API_KEY)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
    "secret": r"['\"]?(?:secret|SECRET)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
    "token": r"['\"]?(?:token|TOKEN|TELEGRAM_TOKEN|GITHUB_TOKEN)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
    "password": r"['\"]?(?:password|PASSWORD)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
    "url": r"['\"]?(?:url|URL|host|HOST)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
    "key": r"['\"]?(?:key|KEY)['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]",
}

@dataclass
class AgentInfo:
    """Informações sobre um agente"""
    name: str
    file_path: Path
    doc_exists: bool
    doc_path: Path
    has_main: bool
    functions: List[str]
    secrets_found: Dict[str, List[str]]
    class_name: str = ""
    description: str = ""

class AgentDocumentationManager:
    """Gerenciador de documentação de agentes"""
    
    def __init__(self):
        self.discovered_agents: Dict[str, AgentInfo] = {}
        self.secrets_extracted: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.updated_docs: List[str] = []
        
    def discover_agents(self) -> List[AgentInfo]:
        """Descobre todos os agentes no projeto"""
        agents = []
        
        # Procura em specialized_agents/
        if AGENTS_DIR.exists():
            for py_file in AGENTS_DIR.rglob("*.py"):
                if py_file.name.startswith("agent_") or "agent" in py_file.name.lower():
                    agent_info = self._analyze_agent_file(py_file)
                    if agent_info:
                        agents.append(agent_info)
                        self.discovered_agents[agent_info.name] = agent_info
        
        # Procura em tools/
        for py_file in TOOLS_DIR.rglob("*agent*.py"):
            agent_info = self._analyze_agent_file(py_file)
            if agent_info:
                agents.append(agent_info)
                self.discovered_agents[agent_info.name] = agent_info
        
        return sorted(agents, key=lambda a: a.name)
    
    def _analyze_agent_file(self, file_path: Path) -> AgentInfo:
        """Analisa um arquivo de agente"""
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Extrai nome da classe
            class_match = re.search(r'class\s+(\w+Agent\w*)\s*[\(:]', content)
            class_name = class_match.group(1) if class_match else ""
            
            # Extrai funções públicas
            functions = re.findall(r'^\s*(?:async\s+)?def\s+(\w+)\s*\(', content, re.MULTILINE)
            functions = [f for f in functions if not f.startswith('_')]
            
            # Extrai docstring
            docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            description = docstring_match.group(1).strip() if docstring_match else ""
            description = description.split('\n')[0]  # Primeira linha
            
            # Verifica se tem if __name__ == "__main__"
            has_main = '__main__' in content
            
            # Extrai secrets
            secrets = self._extract_secrets(content)
            
            # Nome do agente
            agent_name = class_name or file_path.stem
            
            # Doc existe?
            doc_path = DOCS_DIR / f"{agent_name.lower()}.md"
            doc_exists = doc_path.exists()
            
            return AgentInfo(
                name=agent_name,
                file_path=file_path,
                doc_exists=doc_exists,
                doc_path=doc_path,
                has_main=has_main,
                functions=functions,
                secrets_found=secrets,
                class_name=class_name,
                description=description
            )
        except Exception as e:
            logger.error(f"Erro ao analisar {file_path}: {e}")
            return None
    
    def _extract_secrets(self, content: str) -> Dict[str, List[str]]:
        """Extrai secrets do código usando padrões"""
        secrets = {}
        for secret_type, pattern in SECRET_PATTERNS.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                secrets[secret_type] = matches
        return secrets
    
    def generate_documentation(self, agent: AgentInfo) -> str:
        """Gera documentação para um agente"""
        content_parts = [
            f"# {agent.class_name or agent.name}",
            f"\n**Arquivo**: `{agent.file_path.relative_to(PROJECT_ROOT)}`",
            f"\n## 📋 Descrição\n\n{agent.description or 'Agent especializado do sistema Shared Auto-Dev.'}",
        ]
        
        if agent.functions:
            content_parts.append(f"\n## 🔧 Funções Públicas\n")
            for func in sorted(agent.functions)[:20]:  # Limita a 20 funções
                content_parts.append(f"- `{func}()`")
        
        if agent.has_main:
            content_parts.append(f"\n## 🚀 Execução Direta\n\nEste agente pode ser executado diretamente:\n\n```bash\npython {agent.file_path.relative_to(PROJECT_ROOT)}\n```")
        
        if agent.secrets_found:
            content_parts.append(f"\n## 🔐 Secrets Encontrados\n")
            for secret_type, values in agent.secrets_found.items():
                content_parts.append(f"\n### {secret_type.title()}\n")
                for val in values[:5]:  # Primeiros 5
                    # Oculta partes do secret
                    if len(val) > 20:
                        masked = val[:4] + "*" * (len(val) - 8) + val[-4:]
                    else:
                        masked = "*" * len(val)
                    content_parts.append(f"- `{masked}` (armazenado em Secrets Agent)")
        
        content_parts.extend([
            f"\n## 📝 Notas",
            f"- Esta documentação foi **gerada automaticamente**",
            f"- Arquivo source: {agent.file_path.relative_to(PROJECT_ROOT)}",
            f"- Padrão: `agent_documentation_manager.py`",
            f"- Data: {__import__('datetime').datetime.now().isoformat()}",
        ])
        
        return "\n".join(content_parts)
    
    def report_undocumented(self) -> Tuple[List[AgentInfo], int]:
        """Retorna agentes não documentados"""
        undocumented = [a for a in self.discovered_agents.values() if not a.doc_exists]
        return undocumented, len(undocumented)
    
    async def store_secrets(self) -> Dict[str, bool]:
        """Armazena secrets encontrados no Secrets Agent"""
        results = {}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for agent_name, secrets_dict in self.discovered_agents.items():
                    if not secrets_dict.secrets_found:
                        continue
                    
                    for secret_type, values in secrets_dict.secrets_found.items():
                        for i, value in enumerate(values):
                            # Cria nome único do secret
                            secret_name = f"shared/{agent_name.lower()}_{secret_type}_{i}"
                            
                            # Não armazena values hardcoded óbvios vazias ou muito curtas
                            if not value or len(value) < 5:
                                continue
                            
                            try:
                                # POST para Secrets Agent
                                response = await client.post(
                                    f"{SECRETS_AGENT_URL}/secrets/{secret_name}",
                                    json={"value": value},
                                    headers={"Authorization": "Bearer auto-discovery"}
                                )
                                results[secret_name] = response.status_code == 201
                                logger.info(f"✅ Secret armazenado: {secret_name}")
                            except Exception as e:
                                logger.warning(f"⚠️ Erro ao armazenar {secret_name}: {e}")
                                results[secret_name] = False
        except Exception as e:
            logger.error(f"Erro ao conectar Secrets Agent: {e}")
        
        return results
    
    async def generate_all_documentation(self) -> int:
        """Gera documentação para todos os agentes não documentados"""
        undocumented, count = self.report_undocumented()
        created = 0
        
        logger.info(f"🔍 Encontrados {count} agentes não documentados")
        
        for agent in undocumented:
            try:
                # Gera documentação
                doc_content = self.generate_documentation(agent)
                
                # Salva arquivo
                agent.doc_path.parent.mkdir(parents=True, exist_ok=True)
                agent.doc_path.write_text(doc_content, encoding="utf-8")
                
                self.updated_docs.append(str(agent.doc_path.relative_to(PROJECT_ROOT)))
                logger.info(f"✅ Documentação criada: {agent.doc_path.name}")
                created += 1
            except Exception as e:
                logger.error(f"Erro ao gerar doc para {agent.name}: {e}")
        
        return created
    
    def generate_index(self) -> str:
        """Gera índice de agentes"""
        index_content = """# 📚 Índice de Agentes e Documentação

> Gerado automaticamente por `agent_documentation_manager.py`

## Agentes Descobertos

"""
        
        # Agrupa por diretório
        by_dir = defaultdict(list)
        for agent in sorted(self.discovered_agents.values(), key=lambda a: a.name):
            dir_name = agent.file_path.parent.name
            by_dir[dir_name].append(agent)
        
        for dir_name in sorted(by_dir.keys()):
            index_content += f"\n### `{dir_name}/`\n\n"
            for agent in sorted(by_dir[dir_name], key=lambda a: a.name):
                status = "✅" if agent.doc_exists else "❌"
                doc_link = f"[{agent.name}.md]({agent.doc_path.name})" if agent.doc_exists else agent.name
                index_content += f"- {status} **{agent.class_name}** — {agent.description or '(sem desc)'}\n"
                if agent.secrets_found:
                    index_content += f"  - 🔐 Secrets: {', '.join(agent.secrets_found.keys())}\n"
        
        # Estatísticas
        total = len(self.discovered_agents)
        documented = sum(1 for a in self.discovered_agents.values() if a.doc_exists)
        
        index_content += f"\n\n## 📊 Estatísticas\n\n"
        index_content += f"- Total de agentes: **{total}**\n"
        index_content += f"- Documentados: **{documented}** ✅\n"
        index_content += f"- Não documentados: **{total - documented}** ❌\n"
        index_content += f"- Cobertura: **{(documented/total*100):.1f}%**\n"
        
        return index_content


async def main():
    """Executa o gerenciador"""
    manager = AgentDocumentationManager()
    
    # Etapa 1: Descobrir agentes
    logger.info("🔍 Etapa 1: Descobrindo agentes...")
    agents = manager.discover_agents()
    logger.info(f"✅ {len(agents)} agentes encontrados")
    
    # Etapa 2: Extrair secrets
    logger.info("🔐 Etapa 2: Extraindo secrets...")
    total_secrets = sum(len(a.secrets_found) for a in agents)
    logger.info(f"✅ {total_secrets} tipos de secrets encontrados")
    
    # Etapa 3: Armazenar secrets
    logger.info("💾 Etapa 3: Armazenando secrets no Secrets Agent...")
    try:
        results = await manager.store_secrets()
        stored = sum(1 for v in results.values() if v)
        logger.info(f"✅ {stored} secrets armazenados")
    except Exception as e:
        logger.warning(f"⚠️ Erro ao armazenar secrets: {e}")
    
    # Etapa 4: Gerar documentação
    logger.info("📚 Etapa 4: Gerando documentação...")
    created = await manager.generate_all_documentation()
    logger.info(f"✅ {created} arquivos de documentação criados")
    
    # Etapa 5: Gerar índice
    logger.info("📑 Etapa 5: Gerando índice de agentes...")
    index = manager.generate_index()
    index_path = DOCS_DIR / "AGENTS_INDEX.md"
    index_path.write_text(index, encoding="utf-8")
    logger.info(f"✅ Índice salvo em: {index_path.relative_to(PROJECT_ROOT)}")
    
    # Relatório final
    logger.info("\n" + "="*60)
    logger.info("📊 RELATÓRIO FINAL")
    logger.info("="*60)
    logger.info(f"Total de agentes: {len(agents)}")
    logger.info(f"Documentação criada: {created}")
    logger.info(f"Arquivos atualizados: {len(manager.updated_docs)}")
    
    if manager.updated_docs:
        logger.info("\n📄 Arquivos criados:")
        for doc in sorted(manager.updated_docs):
            logger.info(f"  - {doc}")
    
    # Agentes não documentados
    undocumented, _ = manager.report_undocumented()
    if undocumented:
        logger.warning(f"\n⚠️ Ainda faltam {len(undocumented)} agentes documentar:")
        for agent in undocumented:
            logger.warning(f"  - {agent.name}")
    
    logger.info("\n✅ Processamento concluído!")


if __name__ == "__main__":
    asyncio.run(main())
