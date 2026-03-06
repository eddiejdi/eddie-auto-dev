#!/usr/bin/env python3
"""Audita agentes não documentados, cria documentação e extrai secrets."""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict
import ast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Padrões de secrets
SECRET_PATTERNS = {
    'api_key': r'["\']?(?:api[_-]?key|apikey)["\']?\s*[:=]\s*["\']([^\n"\']+)["\']',
    'token': r'["\']?(?:token|auth_token|bearer|access_token)["\']?\s*[:=]\s*["\']([^\n"\']+)["\']',
    'password': r'["\']?(?:password|passwd|pwd)["\']?\s*[:=]\s*["\']([^\n"\']+)["\']',
    'secret': r'["\']?(?:secret|client_secret|api_secret)["\']?\s*[:=]\s*["\']([^\n"\']+)["\']',
    'url': r'(?:DATABASE_URL|db_url|connection_string)["\']?\s*[:=]\s*["\']([^\n"\']+)["\']',
}

@dataclass
class Agent:
    """Representa um agente do sistema."""
    name: str
    path: str
    agent_type: str  # 'specialized_agent', 'telegram_handler', etc
    description: str = ""
    documented: bool = False
    doc_path: Optional[str] = None
    secrets_found: List[Dict] = None
    last_modified: str = ""
    
    def __post_init__(self):
        if self.secrets_found is None:
            self.secrets_found = []

class AgentAuditor:
    """Audita e documenta agentes não documentados."""
    
    def __init__(self, workspace_root: str):
        self.workspace = Path(workspace_root)
        self.docs_dir = self.workspace / "docs" / "agents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.agents: Dict[str, Agent] = {}
        self.discovered_secrets: Dict[str, List[str]] = {}
        
    def discover_agents(self) -> Dict[str, Agent]:
        """Descobre todos os agentes no workspace."""
        logger.info("🔍 Descobrindo agentes...")
        
        # Procura em specialized_agents/
        agents_dir = self.workspace / "specialized_agents"
        if agents_dir.exists():
            for py_file in agents_dir.glob("*.py"):
                if not py_file.name.startswith("_"):
                    agent = self._parse_agent_file(py_file, "specialized_agent")
                    if agent:
                        self.agents[agent.name] = agent
        
        # Procura em handlers de telegram
        handlers_dir = self.workspace / "handlers"
        if handlers_dir.exists():
            for py_file in handlers_dir.glob("*.py"):
                agent = self._parse_agent_file(py_file, "telegram_handler")
                if agent:
                    self.agents[agent.name] = agent
        
        # Procura agents específicos
        for pattern in ["agent_*.py", "*_agent.py"]:
            for py_file in self.workspace.glob(f"**/{pattern}"):
                if py_file.is_file() and not self._is_venv_or_hidden(py_file):
                    agent = self._parse_agent_file(py_file, "agent")
                    if agent:
                        self.agents[agent.name] = agent
        
        logger.info(f"✅ {len(self.agents)} agentes descobertos")
        return self.agents
    
    def _is_venv_or_hidden(self, path: Path) -> bool:
        """Verifica se arquivo está em venv ou pastas ocultas."""
        parts = path.parts
        return any(
            p in {".venv", "venv", "__pycache__", ".git", "node_modules", "."}
            for p in parts
        )
    
    def _parse_agent_file(self, file_path: Path, agent_type: str) -> Optional[Agent]:
        """Extrai informações de um arquivo de agente."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extrai docstring/comentários
            description = self._extract_docstring(content)
            
            # Extrai secrets
            secrets = self._extract_secrets(content)
            
            # Obtém data de modificação
            mtime = os.path.getmtime(file_path)
            last_modified = datetime.fromtimestamp(mtime).isoformat()
            
            # Verifica documentação existente
            doc_file = self.docs_dir / f"{file_path.stem}.md"
            documented = doc_file.exists()
            
            agent = Agent(
                name=file_path.stem,
                path=str(file_path.relative_to(self.workspace)),
                agent_type=agent_type,
                description=description,
                documented=documented,
                doc_path=str(doc_file) if documented else None,
                secrets_found=secrets,
                last_modified=last_modified,
            )
            
            return agent
        except Exception as e:
            logger.warning(f"⚠️  Erro ao parser {file_path}: {e}")
            return None
    
    def _extract_docstring(self, content: str) -> str:
        """Extrai docstring ou comentários iniciais."""
        lines = content.split('\n')
        docstring = ""
        
        # Tenta extrair docstring
        try:
            tree = ast.parse(content)
            docstring = ast.get_docstring(tree) or ""
        except:
            # Fallback: pega comentários iniciais
            for line in lines[:10]:
                if line.strip().startswith('#'):
                    docstring += line.lstrip('#').strip() + " "
        
        return docstring.strip()[:200]
    
    def _extract_secrets(self, content: str) -> List[Dict]:
        """Extrai secrets do código."""
        secrets = []
        
        for secret_type, pattern in SECRET_PATTERNS.items():
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                value = match.group(1)
                # Filtra valores comuns não-secret
                if value and len(value) > 3 and not self._is_false_positive(value):
                    secrets.append({
                        'type': secret_type,
                        'pattern': secret_type,
                        'detected': True,
                        'value_length': len(value),
                    })
        
        return secrets
    
    def _is_false_positive(self, value: str) -> bool:
        """Verifica se é um falso positivo."""
        false_positives = {
            'password', 'token', 'secret', 'api_key', 'your_',
            'example', 'test', 'demo', 'fake', 'placeholder',
            '${', '{{', 'YOUR_', 'REPLACE_', 'INSERT_'
        }
        return any(fp in value.lower() for fp in false_positives)
    
    def check_documentation(self) -> Dict[str, List[str]]:
        """Verifica quais agentes não têm documentação."""
        undocumented = {}
        
        for agent_type in {'specialized_agent', 'telegram_handler', 'agent'}:
            agents = [a for a in self.agents.values() if a.agent_type == agent_type]
            undoc = [a.name for a in agents if not a.documented]
            if undoc:
                undocumented[agent_type] = undoc
        
        return undocumented
    
    def generate_documentation(self) -> int:
        """Gera documentação para agentes não documentados."""
        logger.info("📝 Gerando documentação...")
        created = 0
        
        for agent in self.agents.values():
            if not agent.documented:
                doc_content = self._create_doc_template(agent)
                doc_path = self.docs_dir / f"{agent.name}.md"
                
                try:
                    with open(doc_path, 'w', encoding='utf-8') as f:
                        f.write(doc_content)
                    created += 1
                    logger.info(f"✅ Documentação criada: {doc_path.relative_to(self.workspace)}")
                except Exception as e:
                    logger.error(f"❌ Erro ao criar {doc_path}: {e}")
        
        return created
    
    def _create_doc_template(self, agent: Agent) -> str:
        """Cria template de documentação."""
        template = f"""# {agent.name.replace('_', ' ').title()}

## Informações Básicas
- **Tipo**: {agent.agent_type}
- **Arquivo**: `{agent.path}`
- **Última modificação**: {agent.last_modified}
- **Status**: ⚠️ _Documentação gerada automaticamente_

## Descrição
{agent.description if agent.description else "_(Adicione uma descrição detalhada aqui)_"}

## Funcionalidades
- _(Listar funcionalidades principais)_

## Configuração
### Variáveis de Ambiente
```bash
# Configure as variáveis necessárias
export AGENT_CONFIG="value"
```

### Parâmetros
_(Documente os parâmetros de entrada/saída)_

## Uso
```python
from {agent.path.replace('/', '.').replace('.py', '')} import {agent.name.title().replace('_', '')}

# Exemplo de uso
```

## Secrets/Credenciais
"""
        
        if agent.secrets_found:
            template += f"\n⚠️ **Detectados {len(agent.secrets_found)} padrões de secret:**\n"
            for secret in agent.secrets_found:
                template += f"- `{secret['pattern']}` (comprimento: {secret['value_length']} chars)\n"
            template += "\n**IMPORTANTE**: Mova todas as credenciais para o Secrets Agent!\n"
        else:
            template += "\nNenhum secret detectado automaticamente.\n"
        
        template += """
## Integração com Message Bus
_(Documente como este agente se comunica com o message bus)_

```python
# Publicar mensagem
self.bus.publish('agent_name', 'channel', {'data': 'value'})

# Escutar mensagens
self.bus.register_listener('agent_name', self.on_message)
```

## Troubleshooting
_(Soluções para problemas comuns)_

## Referências
- [Agent Communication Bus](../ARCHITECTURE.md#message-bus)
- [Secrets Agent](../SECRETS_MANAGEMENT.md)
"""
        
        return template.strip()
    
    def report_summary(self) -> None:
        """Exibe relatório resumido."""
        logger.info("\n" + "="*70)
        logger.info("📊 RELATÓRIO DE AUDITORIA DE AGENTES")
        logger.info("="*70)
        
        # Total de agentes
        total = len(self.agents)
        documented = sum(1 for a in self.agents.values() if a.documented)
        undocumented = total - documented
        
        logger.info(f"\n📈 RESUMO GERAL:")
        logger.info(f"  • Total de agentes: {total}")
        logger.info(f"  • Documentados: {documented} ({100*documented//total}%)")
        logger.info(f"  • Não documentados: {undocumented} ({100*undocumented//total}%)")
        
        # Por tipo
        by_type = {}
        for agent in self.agents.values():
            by_type.setdefault(agent.agent_type, []).append(agent)
        
        if by_type:
            logger.info(f"\n📂 POR TIPO:")
            for agent_type, agents in sorted(by_type.items()):
                doc_count = sum(1 for a in agents if a.documented)
                logger.info(
                    f"  • {agent_type}: {len(agents)} "
                    f"({doc_count} documentados)"
                )
        
        # Secrets detectados
        total_secrets = sum(len(a.secrets_found) for a in self.agents.values())
        if total_secrets > 0:
            logger.warning(f"\n🔐 SECRETS DETECTADOS: {total_secrets}")
            for agent in sorted(
                [a for a in self.agents.values() if a.secrets_found],
                key=lambda a: len(a.secrets_found),
                reverse=True
            ):
                logger.warning(
                    f"  • {agent.name}: {len(agent.secrets_found)} padrão(ões)"
                )
    
    def export_report(self, output_file: str) -> None:
        """Exporta relatório em JSON."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_agents": len(self.agents),
                "documented": sum(1 for a in self.agents.values() if a.documented),
                "undocumented": sum(1 for a in self.agents.values() if not a.documented),
                "total_secrets_patterns": sum(len(a.secrets_found) for a in self.agents.values()),
            },
            "agents": [asdict(a) for a in sorted(
                self.agents.values(),
                key=lambda a: a.name
            )]
        }
        
        output_path = self.workspace / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📄 Relatório exportado: {output_path.relative_to(self.workspace)}")

def main():
    """Executa auditoria completa."""
    import sys
    
    workspace = sys.argv[1] if len(sys.argv) > 1 else "/home/edenilson/eddie-auto-dev"
    
    auditor = AgentAuditor(workspace)
    
    # 1. Descobre agentes
    auditor.discover_agents()
    
    # 2. Verifica documentação
    undocumented = auditor.check_documentation()
    
    # 3. Gera documentação
    created = auditor.generate_documentation()
    
    # 4. Relatório
    auditor.report_summary()
    
    # 5. Exporta relatório
    auditor.export_report("tools/audit_agents_report.json")
    
    logger.info(f"\n✨ Documentação criada/atualizada: {created} arquivo(s)")
    logger.info("📚 Documentação em: docs/agents/")

if __name__ == "__main__":
    main()
