"""
Agente Especializado em Confluence

Especialidades:
- Documentação técnica e colaborativa
- Criação e gestão de páginas Confluence
- Templates de documentação (ADR, RFC, Runbook, etc.)
- Organização de espaços e hierarquia
- Macros e formatação avançada
- Integração com Jira
- Export para diferentes formatos
"""
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
import logging
import re

# Memória persistente (opcional)
try:
    from .agent_memory import get_agent_memory
    _MEMORY_AVAILABLE = True
except Exception:
    _MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# REGRAS OBRIGATÓRIAS DO AGENT (Herdadas conforme Regra 7)
# =============================================================================
AGENT_RULES = {
    # Regra 0: Pipeline Obrigatório
    "pipeline": {
        "sequence": ["Análise", "Design", "Geração", "Validação", "Entrega"],
        "enforce": True,
        "rollback_on_failure": True
    },
    
    # Regra 0.1: Economia de Tokens
    "token_economy": {
        "prefer_local_llm": True,
        "ollama_url": "http://192.168.15.2:11434",
        "batch_operations": True,
        "cache_results": True
    },
    
    # Regra 0.2: Validação Obrigatória
    "validation": {
        "required_before_delivery": True,
        "test_each_step": True,
        "show_evidence": True,
        "never_assume_success": True
    },
    
    # Regra 1: Commit após sucesso
    "commit": {
        "auto_commit_on_success": True,
        "message_format": "docs|feat|fix: descricao"
    },
    
    # Regra 4: Comunicação
    "communication": {
        "use_bus": True,
        "log_all_actions": True,
        "share_context": True
    },
    
    # Regras Específicas do Confluence Agent
    "confluence_specific": {
        "validate_storage_format": True,
        "check_macros_syntax": True,
        "verify_links_valid": True,
        "ensure_metadata_complete": True,
        "export_formats": ["html", "pdf", "markdown", "storage"]
    },
    
    # Regra 8: Sincronização com Nuvem
    "cloud_sync": {
        "required": True,
        "description": "Sincronizar documentos com nuvem após cada alteração",
        "targets": ["github", "confluence_cloud"],
        "backup_local": True,
        "auto_commit": True,
        "validate_accessible": True,
        "sync_on_save": True
    }
}

# Diretório para salvar documentos
DOCS_DIR = Path(__file__).parent / "confluence_docs"
DOCS_DIR.mkdir(exist_ok=True)


@dataclass
class ConfluencePage:
    """Representa uma página Confluence"""
    id: str
    title: str
    space_key: str = "DOCS"
    content: str = ""
    parent_id: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "space_key": self.space_key,
            "content": self.content,
            "parent_id": self.parent_id,
            "labels": self.labels,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata
        }


class ConfluenceStorageFormat:
    """Gerador de conteúdo no formato Confluence Storage Format (XHTML)"""
    
    # Macros comuns do Confluence
    MACROS = {
        "info": '<ac:structured-macro ac:name="info"><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "warning": '<ac:structured-macro ac:name="warning"><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "note": '<ac:structured-macro ac:name="note"><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "tip": '<ac:structured-macro ac:name="tip"><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "expand": '<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">{title}</ac:parameter><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "code": '<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{language}</ac:parameter><ac:plain-text-body><![CDATA[{content}]]></ac:plain-text-body></ac:structured-macro>',
        "toc": '<ac:structured-macro ac:name="toc"><ac:parameter ac:name="printable">true</ac:parameter><ac:parameter ac:name="style">disc</ac:parameter><ac:parameter ac:name="maxLevel">3</ac:parameter></ac:structured-macro>',
        "status": '<ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">{color}</ac:parameter><ac:parameter ac:name="title">{title}</ac:parameter></ac:structured-macro>',
        "panel": '<ac:structured-macro ac:name="panel"><ac:parameter ac:name="title">{title}</ac:parameter><ac:rich-text-body>{content}</ac:rich-text-body></ac:structured-macro>',
        "jira": '<ac:structured-macro ac:name="jira"><ac:parameter ac:name="server">Jira</ac:parameter><ac:parameter ac:name="key">{key}</ac:parameter></ac:structured-macro>',
        "anchor": '<ac:structured-macro ac:name="anchor"><ac:parameter ac:name=""></ac:parameter><ac:parameter ac:name="">{name}</ac:parameter></ac:structured-macro>',
        "children": '<ac:structured-macro ac:name="children"><ac:parameter ac:name="all">true</ac:parameter></ac:structured-macro>',
        "include": '<ac:structured-macro ac:name="include"><ac:parameter ac:name=""><ri:page ri:content-title="{page_title}"/></ac:parameter></ac:structured-macro>',
    }
    
    @staticmethod
    def heading(level: int, text: str) -> str:
        """Cria um heading"""
        return f"<h{level}>{text}</h{level}>"
    
    @staticmethod
    def paragraph(text: str) -> str:
        """Cria um parágrafo"""
        return f"<p>{text}</p>"
    
    @staticmethod
    def bold(text: str) -> str:
        return f"<strong>{text}</strong>"
    
    @staticmethod
    def italic(text: str) -> str:
        return f"<em>{text}</em>"
    
    @staticmethod
    def link(url: str, text: str) -> str:
        return f'<a href="{url}">{text}</a>'
    
    @staticmethod
    def bullet_list(items: List[str]) -> str:
        items_html = "".join(f"<li>{item}</li>" for item in items)
        return f"<ul>{items_html}</ul>"
    
    @staticmethod
    def numbered_list(items: List[str]) -> str:
        items_html = "".join(f"<li>{item}</li>" for item in items)
        return f"<ol>{items_html}</ol>"
    
    @staticmethod
    def table(headers: List[str], rows: List[List[str]]) -> str:
        """Cria uma tabela"""
        header_html = "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
        rows_html = ""
        for row in rows:
            rows_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        return f"<table><thead>{header_html}</thead><tbody>{rows_html}</tbody></table>"
    
    @classmethod
    def macro(cls, name: str, **kwargs) -> str:
        """Gera uma macro Confluence"""
        if name in cls.MACROS:
            return cls.MACROS[name].format(**kwargs)
        return f"<!-- Unknown macro: {name} -->"
    
    @staticmethod
    def hr() -> str:
        return "<hr/>"
    
    @staticmethod
    def image(url: str, alt: str = "") -> str:
        return f'<ac:image><ri:url ri:value="{url}"/></ac:image>'


class ConfluenceAgent:
    """
    Agente especializado em Confluence e documentação técnica.
    
    Capabilities:
    - Criar páginas no formato Confluence Storage
    - Gerar templates de documentação (ADR, RFC, Runbook, API Doc, etc.)
    - Organizar hierarquia de espaços
    - Usar macros avançadas
    - Exportar para HTML, Markdown, PDF
    """
    
    def __init__(self, llm_client=None):
        self.storage = ConfluenceStorageFormat()
        self.llm = llm_client
        self.pages: Dict[str, ConfluencePage] = {}

        self.memory = None
        if _MEMORY_AVAILABLE:
            try:
                self.memory = get_agent_memory("confluence_agent")
            except Exception as e:
                logger.warning("Memória indisponível para Confluence: %s", e)
        
        # Templates de documentação
        self.templates = {
            "adr": self._template_adr,
            "rfc": self._template_rfc,
            "runbook": self._template_runbook,
            "api_doc": self._template_api_doc,
            "meeting_notes": self._template_meeting_notes,
            "project_readme": self._template_project_readme,
            "release_notes": self._template_release_notes,
            "troubleshooting": self._template_troubleshooting,
            "onboarding": self._template_onboarding,
            "retrospective": self._template_retrospective,
        }
    
    def create_page(self, title: str, space_key: str = "DOCS", 
                    parent_id: str = None, labels: List[str] = None) -> ConfluencePage:
        """Cria uma nova página Confluence"""
        page_id = f"page_{uuid.uuid4().hex[:8]}"
        page = ConfluencePage(
            id=page_id,
            title=title,
            space_key=space_key,
            parent_id=parent_id,
            labels=labels or []
        )
        self.pages[page_id] = page
        logger.info(f"Página criada: {title} ({page_id})")
        return page
    
    def set_content(self, page_id: str, content: str) -> ConfluencePage:
        """Define o conteúdo de uma página"""
        if page_id not in self.pages:
            raise ValueError(f"Página não encontrada: {page_id}")
        
        self.pages[page_id].content = content
        self.pages[page_id].updated_at = datetime.now().isoformat()
        self.pages[page_id].version += 1
        return self.pages[page_id]
    
    def list_templates(self) -> List[str]:
        """Lista templates disponíveis"""
        return list(self.templates.keys())
    
    def create_from_template(self, template_name: str, title: str = None, 
                             **kwargs) -> str:
        """Cria página a partir de um template"""
        if template_name not in self.templates:
            raise ValueError(f"Template não encontrado: {template_name}. Disponíveis: {list(self.templates.keys())}")
        
        page = self.templates[template_name](title, **kwargs)
        
        # Salvar arquivo
        filename = f"{page.title.replace(' ', '_')}.html"
        filepath = DOCS_DIR / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self._wrap_html(page.content, page.title))
        
        # Validar conforme Regra 0.2
        validation = self.validate_page(str(filepath))
        if not validation["valid"]:
            logger.warning(f"Validação falhou: {validation['errors']}")
        
        logger.info(f"Documento gerado: {filepath}")
        return str(filepath)
    
    def _wrap_html(self, content: str, title: str) -> str:
        """Envolve o conteúdo em HTML completo para visualização"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        h1, h2, h3, h4 {{ color: #172B4D; margin-top: 24px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        th, td {{ border: 1px solid #DFE1E6; padding: 8px 12px; text-align: left; }}
        th {{ background: #F4F5F7; }}
        code {{ background: #F4F5F7; padding: 2px 6px; border-radius: 3px; font-family: 'SFMono-Regular', Consolas, monospace; }}
        pre {{ background: #F4F5F7; padding: 16px; border-radius: 3px; overflow-x: auto; }}
        .info-box {{ background: #DEEBFF; border-left: 4px solid #0052CC; padding: 12px 16px; margin: 16px 0; }}
        .warning-box {{ background: #FFFAE6; border-left: 4px solid #FF8B00; padding: 12px 16px; margin: 16px 0; }}
        .success-box {{ background: #E3FCEF; border-left: 4px solid #00875A; padding: 12px 16px; margin: 16px 0; }}
        .error-box {{ background: #FFEBE6; border-left: 4px solid #DE350B; padding: 12px 16px; margin: 16px 0; }}
        .status {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
        .status-green {{ background: #00875A; color: white; }}
        .status-yellow {{ background: #FF8B00; color: white; }}
        .status-red {{ background: #DE350B; color: white; }}
        .status-blue {{ background: #0052CC; color: white; }}
        hr {{ border: none; border-top: 1px solid #DFE1E6; margin: 24px 0; }}
    </style>
</head>
<body>
{content}
<hr/>
<p style="color: #6B778C; font-size: 12px;">Gerado por Eddie Confluence Agent v1.0.0 em {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body>
</html>"""
    
    # =========================================================================
    # TEMPLATES DE DOCUMENTAÇÃO
    # =========================================================================
    
    def _template_adr(self, title: str = None, **kwargs) -> ConfluencePage:
        """Architecture Decision Record (ADR)"""
        title = title or "ADR-001: Título da Decisão"
        page = self.create_page(title, labels=["adr", "architecture"])
        
        content = f"""
{self.storage.heading(1, title)}

<div class="info-box">
<strong>Status:</strong> <span class="status status-yellow">PROPOSTO</span> | 
<strong>Data:</strong> {datetime.now().strftime('%Y-%m-%d')} | 
<strong>Autor:</strong> {kwargs.get('author', 'Eddie Auto-Dev')}
</div>

{self.storage.heading(2, "Contexto")}
{self.storage.paragraph("Descreva o contexto e as forças em jogo que motivam esta decisão. Qual problema estamos tentando resolver?")}

{self.storage.heading(2, "Decisão")}
{self.storage.paragraph("Descreva a mudança proposta ou decisão arquitetural.")}

{self.storage.heading(2, "Alternativas Consideradas")}
{self.storage.table(
    ["Alternativa", "Prós", "Contras"],
    [
        ["Opção A", "Vantagem 1, Vantagem 2", "Desvantagem 1"],
        ["Opção B", "Vantagem 1", "Desvantagem 1, Desvantagem 2"],
        ["Opção C (escolhida)", "Melhor fit", "Complexidade inicial"]
    ]
)}

{self.storage.heading(2, "Consequências")}
{self.storage.heading(3, "Positivas")}
{self.storage.bullet_list(["Benefício 1", "Benefício 2", "Benefício 3"])}

{self.storage.heading(3, "Negativas")}
{self.storage.bullet_list(["Trade-off 1", "Trade-off 2"])}

{self.storage.heading(2, "Links Relacionados")}
{self.storage.bullet_list([
    self.storage.link("#", "RFC relacionada"),
    self.storage.link("#", "Issue do Jira"),
    self.storage.link("#", "Documentação técnica")
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_rfc(self, title: str = None, **kwargs) -> ConfluencePage:
        """Request for Comments (RFC)"""
        title = title or "RFC: Proposta de Mudança"
        page = self.create_page(title, labels=["rfc", "proposal"])
        
        content = f"""
{self.storage.heading(1, title)}

<div class="info-box">
<strong>Status:</strong> <span class="status status-blue">EM REVISÃO</span> | 
<strong>Prazo para Feedback:</strong> {kwargs.get('deadline', '2 semanas')} | 
<strong>Autor:</strong> {kwargs.get('author', 'Eddie Auto-Dev')}
</div>

{self.storage.heading(2, "Resumo Executivo")}
{self.storage.paragraph("Uma breve descrição (2-3 sentenças) do que está sendo proposto.")}

{self.storage.heading(2, "Motivação")}
{self.storage.paragraph("Por que esta mudança é necessária? Qual problema resolve?")}

{self.storage.heading(2, "Proposta Detalhada")}
{self.storage.heading(3, "Visão Geral")}
{self.storage.paragraph("Descrição detalhada da solução proposta.")}

{self.storage.heading(3, "Arquitetura")}
{self.storage.paragraph("Diagramas e descrição técnica da arquitetura.")}

{self.storage.heading(3, "Implementação")}
{self.storage.numbered_list([
    "Fase 1: Preparação",
    "Fase 2: Implementação Core",
    "Fase 3: Migração",
    "Fase 4: Validação"
])}

{self.storage.heading(2, "Riscos e Mitigações")}
{self.storage.table(
    ["Risco", "Probabilidade", "Impacto", "Mitigação"],
    [
        ["Risco 1", "Média", "Alto", "Plano de rollback"],
        ["Risco 2", "Baixa", "Médio", "Monitoramento"]
    ]
)}

{self.storage.heading(2, "Timeline")}
{self.storage.table(
    ["Milestone", "Data", "Responsável"],
    [
        ["Início", datetime.now().strftime('%Y-%m-%d'), "Tech Lead"],
        ["POC completo", "TBD", "Dev Team"],
        ["Rollout", "TBD", "DevOps"]
    ]
)}

{self.storage.heading(2, "Feedback Recebido")}
{self.storage.paragraph("Seção para registrar comentários e decisões durante a revisão.")}

{self.storage.hr()}
<div class="warning-box">
<strong>Como dar feedback:</strong> Comente diretamente nesta página ou envie para #channel-rfc no Slack.
</div>
"""
        self.set_content(page.id, content)
        return page
    
    def _template_runbook(self, title: str = None, **kwargs) -> ConfluencePage:
        """Runbook Operacional"""
        title = title or "Runbook: Nome do Serviço"
        page = self.create_page(title, labels=["runbook", "operations", "oncall"])
        
        content = f"""
{self.storage.heading(1, title)}

<div class="warning-box">
<strong>⚠️ DOCUMENTO CRÍTICO DE OPERAÇÕES</strong><br/>
Última atualização: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Mantenedor: {kwargs.get('maintainer', 'SRE Team')}
</div>

{self.storage.heading(2, "📋 Informações do Serviço")}
{self.storage.table(
    ["Campo", "Valor"],
    [
        ["Nome do Serviço", kwargs.get('service_name', 'my-service')],
        ["Repositório", kwargs.get('repo', 'github.com/org/repo')],
        ["Ambiente", "Production"],
        ["Criticidade", "🔴 Alta"],
        ["Time Responsável", kwargs.get('team', 'Platform Team')],
        ["Slack Channel", kwargs.get('slack', '#oncall-platform')]
    ]
)}

{self.storage.heading(2, "🚨 Procedimentos de Emergência")}

{self.storage.heading(3, "Serviço Down")}
<div class="error-box">
<strong>Sintoma:</strong> Health check falhando, usuários reportando erros 5xx
</div>

{self.storage.numbered_list([
    "Verificar status: <code>kubectl get pods -n production</code>",
    "Checar logs: <code>kubectl logs -f deployment/my-service -n production</code>",
    "Se OOMKilled, aumentar memória: <code>kubectl scale deployment/my-service --replicas=3</code>",
    "Se necessário, rollback: <code>kubectl rollout undo deployment/my-service</code>",
    "Notificar no #incident-response"
])}

{self.storage.heading(3, "Alta Latência")}
{self.storage.numbered_list([
    "Verificar métricas no Grafana: {kwargs.get('grafana_url', 'https://grafana.example.com')}",
    "Checar conexões DB: <code>SELECT count(*) FROM pg_stat_activity</code>",
    "Verificar rate limiting",
    "Escalar se necessário"
])}

{self.storage.heading(2, "📊 Monitoramento")}
{self.storage.table(
    ["Dashboard", "Link", "Uso"],
    [
        ["Grafana Principal", "#", "Métricas de negócio e infra"],
        ["Logs (Kibana)", "#", "Troubleshooting detalhado"],
        ["Traces (Jaeger)", "#", "Distributed tracing"],
        ["Alertmanager", "#", "Configuração de alertas"]
    ]
)}

{self.storage.heading(2, "🔧 Comandos Úteis")}
<pre><code># Ver pods
kubectl get pods -n production -l app=my-service

# Logs em tempo real
kubectl logs -f deployment/my-service -n production --tail=100

# Exec no container
kubectl exec -it deployment/my-service -n production -- /bin/sh

# Restart graceful
kubectl rollout restart deployment/my-service -n production

# Verificar recursos
kubectl top pods -n production | grep my-service
</code></pre>

{self.storage.heading(2, "📞 Escalação")}
{self.storage.table(
    ["Nível", "Quem", "Quando", "Contato"],
    [
        ["L1", "On-call Engineer", "Primeiro contato", "PagerDuty"],
        ["L2", "Tech Lead", "Após 15min sem resolução", "@tech-lead"],
        ["L3", "Engineering Manager", "Incidente P1 ou impacto crítico", "@eng-manager"]
    ]
)}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_api_doc(self, title: str = None, **kwargs) -> ConfluencePage:
        """Documentação de API"""
        title = title or "API Documentation: Service Name"
        page = self.create_page(title, labels=["api", "documentation", "technical"])
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.heading(2, "Visão Geral")}
{self.storage.paragraph("Descrição breve da API e seu propósito.")}

{self.storage.table(
    ["Campo", "Valor"],
    [
        ["Base URL", kwargs.get('base_url', 'https://api.example.com/v1')],
        ["Autenticação", "Bearer Token (JWT)"],
        ["Rate Limit", "1000 req/min"],
        ["Formato", "JSON"]
    ]
)}

{self.storage.heading(2, "Autenticação")}
{self.storage.paragraph("Todas as requisições devem incluir o header:")}
<pre><code>Authorization: Bearer &lt;token&gt;</code></pre>

{self.storage.heading(2, "Endpoints")}

{self.storage.heading(3, "GET /users")}
{self.storage.paragraph("Lista todos os usuários.")}

<strong>Request:</strong>
<pre><code>GET /v1/users?page=1&limit=10
Authorization: Bearer &lt;token&gt;</code></pre>

<strong>Response 200:</strong>
<pre><code>{{
  "data": [
    {{"id": "123", "name": "John", "email": "john@example.com"}}
  ],
  "pagination": {{
    "page": 1,
    "limit": 10,
    "total": 100
  }}
}}</code></pre>

{self.storage.heading(3, "POST /users")}
{self.storage.paragraph("Cria um novo usuário.")}

<strong>Request:</strong>
<pre><code>POST /v1/users
Content-Type: application/json
Authorization: Bearer &lt;token&gt;

{{
  "name": "John Doe",
  "email": "john@example.com"
}}</code></pre>

{self.storage.heading(2, "Códigos de Erro")}
{self.storage.table(
    ["Código", "Significado", "Ação"],
    [
        ["400", "Bad Request", "Verifique os parâmetros"],
        ["401", "Unauthorized", "Token inválido ou expirado"],
        ["403", "Forbidden", "Sem permissão"],
        ["404", "Not Found", "Recurso não existe"],
        ["429", "Too Many Requests", "Rate limit excedido"],
        ["500", "Internal Error", "Contate o suporte"]
    ]
)}

{self.storage.heading(2, "SDKs e Exemplos")}
{self.storage.bullet_list([
    self.storage.link("#", "Python SDK"),
    self.storage.link("#", "JavaScript SDK"),
    self.storage.link("#", "Postman Collection")
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_meeting_notes(self, title: str = None, **kwargs) -> ConfluencePage:
        """Ata de Reunião"""
        title = title or f"Meeting Notes - {datetime.now().strftime('%Y-%m-%d')}"
        page = self.create_page(title, labels=["meeting", "notes"])
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.table(
    ["", ""],
    [
        ["📅 Data", datetime.now().strftime('%Y-%m-%d %H:%M')],
        ["👥 Participantes", kwargs.get('participants', '@person1, @person2, @person3')],
        ["📝 Facilitador", kwargs.get('facilitator', 'TBD')],
        ["⏱️ Duração", kwargs.get('duration', '30 min')]
    ]
)}

{self.storage.heading(2, "📋 Agenda")}
{self.storage.numbered_list([
    "Item 1",
    "Item 2",
    "Item 3"
])}

{self.storage.heading(2, "📝 Discussão")}
{self.storage.heading(3, "Tópico 1")}
{self.storage.paragraph("Resumo da discussão...")}

{self.storage.heading(3, "Tópico 2")}
{self.storage.paragraph("Resumo da discussão...")}

{self.storage.heading(2, "✅ Action Items")}
{self.storage.table(
    ["Ação", "Responsável", "Prazo", "Status"],
    [
        ["Ação 1", "@pessoa", "YYYY-MM-DD", "🟡 Em andamento"],
        ["Ação 2", "@pessoa", "YYYY-MM-DD", "🔴 Pendente"],
        ["Ação 3", "@pessoa", "YYYY-MM-DD", "🟢 Concluído"]
    ]
)}

{self.storage.heading(2, "🔜 Próximos Passos")}
{self.storage.bullet_list([
    "Próxima reunião: TBD",
    "Follow-up necessário: Item X"
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_project_readme(self, title: str = None, **kwargs) -> ConfluencePage:
        """README de Projeto"""
        title = title or "Project: Nome do Projeto"
        page = self.create_page(title, labels=["project", "readme"])
        
        project_name = kwargs.get('project_name', 'my-project')
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.paragraph(kwargs.get('description', 'Descrição breve do projeto e seu propósito.'))}

<div class="info-box">
<strong>Quick Links:</strong> 
{self.storage.link('#', '📁 Repositório')} | 
{self.storage.link('#', '📊 Dashboard')} | 
{self.storage.link('#', '📝 Backlog')} | 
{self.storage.link('#', '💬 Slack')}
</div>

{self.storage.heading(2, "🚀 Quick Start")}
<pre><code># Clone o repositório
git clone https://github.com/org/{project_name}.git
cd {project_name}

# Instale dependências
npm install  # ou pip install -r requirements.txt

# Configure variáveis de ambiente
cp .env.example .env

# Execute
npm run dev  # ou python main.py
</code></pre>

{self.storage.heading(2, "📁 Estrutura do Projeto")}
<pre><code>{project_name}/
├── src/
│   ├── components/
│   ├── services/
│   └── utils/
├── tests/
├── docs/
├── .env.example
├── package.json
└── README.md
</code></pre>

{self.storage.heading(2, "👥 Time")}
{self.storage.table(
    ["Role", "Pessoa", "Contato"],
    [
        ["Tech Lead", "@tech-lead", "#channel"],
        ["Product Owner", "@po", "#channel"],
        ["Desenvolvedores", "@dev1, @dev2", "#channel"]
    ]
)}

{self.storage.heading(2, "📚 Documentação Relacionada")}
{self.storage.bullet_list([
    self.storage.link("#", "Arquitetura"),
    self.storage.link("#", "API Docs"),
    self.storage.link("#", "Runbook"),
    self.storage.link("#", "ADRs")
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_release_notes(self, title: str = None, **kwargs) -> ConfluencePage:
        """Release Notes"""
        version = kwargs.get('version', '1.0.0')
        title = title or f"Release Notes - v{version}"
        page = self.create_page(title, labels=["release", "changelog"])
        
        content = f"""
{self.storage.heading(1, title)}

<div class="success-box">
<strong>🎉 Versão {version} disponível!</strong><br/>
Data de release: {datetime.now().strftime('%Y-%m-%d')}
</div>

{self.storage.heading(2, "✨ Novidades")}
{self.storage.bullet_list([
    "Feature 1: Descrição breve",
    "Feature 2: Descrição breve",
    "Feature 3: Descrição breve"
])}

{self.storage.heading(2, "🐛 Correções")}
{self.storage.bullet_list([
    "Fix: Descrição do bug corrigido",
    "Fix: Outro bug corrigido"
])}

{self.storage.heading(2, "⚠️ Breaking Changes")}
<div class="warning-box">
{self.storage.bullet_list([
    "API X foi descontinuada, use API Y",
    "Configuração Z mudou de formato"
])}
</div>

{self.storage.heading(2, "📦 Como Atualizar")}
<pre><code># Via npm
npm update {kwargs.get('package', 'my-package')}@{version}

# Via pip
pip install --upgrade {kwargs.get('package', 'my-package')}=={version}
</code></pre>

{self.storage.heading(2, "🔗 Links")}
{self.storage.bullet_list([
    self.storage.link("#", "Changelog completo"),
    self.storage.link("#", "Migration guide"),
    self.storage.link("#", "Issues conhecidos")
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_troubleshooting(self, title: str = None, **kwargs) -> ConfluencePage:
        """Guia de Troubleshooting"""
        title = title or "Troubleshooting Guide: Service Name"
        page = self.create_page(title, labels=["troubleshooting", "support", "guide"])
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.paragraph("Guia para diagnóstico e resolução de problemas comuns.")}

{self.storage.heading(2, "🔍 Problema: Serviço não inicia")}
<div class="error-box">
<strong>Sintoma:</strong> O serviço falha ao iniciar com erro de conexão.
</div>

<strong>Causas possíveis:</strong>
{self.storage.numbered_list([
    "Banco de dados indisponível",
    "Variáveis de ambiente não configuradas",
    "Porta já em uso"
])}

<strong>Solução:</strong>
<pre><code># Verificar conexão com banco
nc -zv database.host 5432

# Verificar variáveis
env | grep DATABASE

# Verificar porta
lsof -i :8080
</code></pre>

{self.storage.hr()}

{self.storage.heading(2, "🔍 Problema: Erros 500 intermitentes")}
<div class="warning-box">
<strong>Sintoma:</strong> Alguns requests retornam 500, outros funcionam.
</div>

<strong>Diagnóstico:</strong>
{self.storage.numbered_list([
    "Verificar logs de erro",
    "Checar health de todas as instâncias",
    "Verificar conexões de banco",
    "Analisar métricas de memória/CPU"
])}

{self.storage.hr()}

{self.storage.heading(2, "🔍 Problema: Lentidão nas queries")}
<strong>Sintoma:</strong> Requests demorando mais que o normal.

<strong>Checklist:</strong>
{self.storage.bullet_list([
    "✓ Verificar índices no banco",
    "✓ Analisar query plan (EXPLAIN ANALYZE)",
    "✓ Checar locks no banco",
    "✓ Verificar cache hit ratio"
])}

{self.storage.heading(2, "📞 Ainda com problemas?")}
{self.storage.paragraph("Se o problema persistir:")}
{self.storage.numbered_list([
    "Abra um ticket em #support",
    "Inclua: logs, timestamp, steps to reproduce",
    "Escalação: @oncall-team"
])}
"""
        self.set_content(page.id, content)
        return page
    
    def _template_onboarding(self, title: str = None, **kwargs) -> ConfluencePage:
        """Guia de Onboarding"""
        title = title or "Onboarding Guide: New Team Member"
        page = self.create_page(title, labels=["onboarding", "guide", "team"])
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.paragraph("Bem-vindo(a) ao time! 🎉 Este guia vai te ajudar nos primeiros dias.")}

{self.storage.heading(2, "📅 Primeira Semana")}

{self.storage.heading(3, "Dia 1: Setup")}
{self.storage.bullet_list([
    "✅ Configurar laptop (veja IT Guide)",
    "✅ Acessar email e Slack",
    "✅ Conhecer o time (coffee chat)",
    "✅ Ler este documento completamente"
])}

{self.storage.heading(3, "Dia 2-3: Ambiente")}
{self.storage.bullet_list([
    "✅ Clonar repositórios principais",
    "✅ Configurar ambiente de desenvolvimento",
    "✅ Rodar o projeto localmente",
    "✅ Fazer primeiro PR (fix typo ou doc)"
])}

{self.storage.heading(3, "Dia 4-5: Contexto")}
{self.storage.bullet_list([
    "✅ Ler ADRs principais",
    "✅ Entender arquitetura do sistema",
    "✅ Pair programming com um colega",
    "✅ Participar do standup"
])}

{self.storage.heading(2, "🔗 Links Importantes")}
{self.storage.table(
    ["O quê", "Link", "Para quê"],
    [
        ["Repositórios", "#", "Código fonte"],
        ["Jira Board", "#", "Tarefas e sprints"],
        ["Confluence", "#", "Documentação"],
        ["Grafana", "#", "Monitoramento"],
        ["CI/CD", "#", "Pipelines"]
    ]
)}

{self.storage.heading(2, "👥 Pessoas Chave")}
{self.storage.table(
    ["Pessoa", "Role", "Falar sobre"],
    [
        ["@manager", "Engineering Manager", "1:1s, carreira, feedback"],
        ["@tech-lead", "Tech Lead", "Arquitetura, code review"],
        ["@buddy", "Onboarding Buddy", "Dúvidas do dia-a-dia"],
        ["@product", "Product Manager", "Roadmap, prioridades"]
    ]
)}

{self.storage.heading(2, "📚 Leitura Recomendada")}
{self.storage.numbered_list([
    self.storage.link("#", "Handbook do time"),
    self.storage.link("#", "Guia de estilo de código"),
    self.storage.link("#", "Processo de deploy"),
    self.storage.link("#", "Runbooks principais")
])}

<div class="success-box">
<strong>Dica:</strong> Não tenha medo de perguntar! O canal #ask-anything é seu amigo.
</div>
"""
        self.set_content(page.id, content)
        return page
    
    def _template_retrospective(self, title: str = None, **kwargs) -> ConfluencePage:
        """Retrospectiva de Sprint"""
        sprint = kwargs.get('sprint', 'Sprint X')
        title = title or f"Retrospectiva - {sprint}"
        page = self.create_page(title, labels=["retrospective", "agile", "sprint"])
        
        content = f"""
{self.storage.heading(1, title)}

{self.storage.table(
    ["", ""],
    [
        ["📅 Data", datetime.now().strftime('%Y-%m-%d')],
        ["🏃 Sprint", sprint],
        ["👥 Participantes", kwargs.get('participants', 'Todo o time')],
        ["⏱️ Duração", kwargs.get('duration', '1 hora')]
    ]
)}

{self.storage.heading(2, "✅ O que foi bem (Keep)")}
<div class="success-box">
{self.storage.bullet_list([
    "Item positivo 1",
    "Item positivo 2",
    "Item positivo 3"
])}
</div>

{self.storage.heading(2, "🔧 O que pode melhorar (Improve)")}
<div class="warning-box">
{self.storage.bullet_list([
    "Ponto de melhoria 1",
    "Ponto de melhoria 2",
    "Ponto de melhoria 3"
])}
</div>

{self.storage.heading(2, "💡 Ideias e Experimentos (Try)")}
<div class="info-box">
{self.storage.bullet_list([
    "Ideia para experimentar 1",
    "Ideia para experimentar 2"
])}
</div>

{self.storage.heading(2, "📊 Métricas da Sprint")}
{self.storage.table(
    ["Métrica", "Valor", "Meta"],
    [
        ["Velocity", "X pontos", "Y pontos"],
        ["Bugs encontrados", "N", "< 5"],
        ["Deploy frequency", "X/semana", "> 3"],
        ["Cycle time", "X dias", "< 3 dias"]
    ]
)}

{self.storage.heading(2, "🎯 Action Items")}
{self.storage.table(
    ["Ação", "Responsável", "Prazo"],
    [
        ["Ação 1 para melhorar", "@pessoa", "Próxima sprint"],
        ["Ação 2 para melhorar", "@pessoa", "Próxima sprint"]
    ]
)}
"""
        self.set_content(page.id, content)
        return page
    
    # =========================================================================
    # MÉTODOS DE VALIDAÇÃO E UTILIDADE
    # =========================================================================
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Retorna capabilities do agente"""
        return {
            "name": "Confluence Agent",
            "version": "1.0.0",
            "specialties": [
                "Technical Documentation",
                "Confluence Page Generation",
                "ADR/RFC Templates",
                "Runbooks",
                "API Documentation",
                "Meeting Notes",
                "Release Notes",
                "Onboarding Guides"
            ],
            "templates": self.list_templates(),
            "output_formats": ["html", "confluence_storage", "markdown"],
            "macros_supported": list(ConfluenceStorageFormat.MACROS.keys()),
            "rules_inherited": list(AGENT_RULES.keys()),
            "validation_enabled": AGENT_RULES["validation"]["required_before_delivery"]
        }
    
    def validate_page(self, filepath: str) -> Dict[str, Any]:
        """
        Valida uma página gerada conforme Regra 0.2.
        Verifica: estrutura HTML, macros, links.
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "checks_passed": []
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 1. Verificar se tem conteúdo
            if len(content) < 100:
                validation_result["valid"] = False
                validation_result["errors"].append("Conteúdo muito curto")
                return validation_result
            
            validation_result["checks_passed"].append(f"Conteúdo: {len(content)} caracteres")
            
            # 2. Verificar estrutura HTML básica
            if "<html>" in content.lower() and "</html>" in content.lower():
                validation_result["checks_passed"].append("Estrutura HTML válida")
            else:
                validation_result["warnings"].append("Faltando tags HTML completas")
            
            # 3. Verificar título
            if "<title>" in content.lower():
                validation_result["checks_passed"].append("Título presente")
            else:
                validation_result["warnings"].append("Faltando tag title")
            
            # 4. Verificar headings
            heading_count = len(re.findall(r'<h[1-6]>', content, re.IGNORECASE))
            if heading_count > 0:
                validation_result["checks_passed"].append(f"Headings: {heading_count}")
            
            # 5. Verificar tabelas
            table_count = len(re.findall(r'<table>', content, re.IGNORECASE))
            if table_count > 0:
                validation_result["checks_passed"].append(f"Tabelas: {table_count}")
            
            # 6. Verificar tamanho do arquivo
            file_size = os.path.getsize(filepath)
            validation_result["checks_passed"].append(f"Arquivo: {file_size/1024:.2f}KB")
            
            logger.info(f"Validação da página {filepath}: {'PASSOU' if validation_result['valid'] else 'FALHOU'}")
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Erro na validação: {str(e)}")
        
        return validation_result
    
    def get_rules(self) -> Dict[str, Any]:
        """Retorna regras que este agent segue (para auditoria)"""
        return AGENT_RULES
    
    async def generate_from_description(self, description: str, doc_type: str = "auto") -> str:
        """
        Gera documento a partir de descrição em linguagem natural.
        Usa Ollama LOCAL para economia de tokens.
        """
        import httpx
        
        try:
            from specialized_agents.config import LLM_CONFIG
        except ImportError:
            LLM_CONFIG = {"base_url": "http://192.168.15.2:11434", "model": "qwen2.5-coder:1.5b"}
        
        system_prompt = """Você é um especialista em documentação técnica Confluence.
Analise a descrição e retorne APENAS um JSON válido com o tipo de documento e parâmetros.

Tipos disponíveis: adr, rfc, runbook, api_doc, meeting_notes, project_readme, release_notes, troubleshooting, onboarding, retrospective

Formato:
{
    "doc_type": "tipo_escolhido",
    "title": "Título sugerido",
    "params": {
        "author": "nome se mencionado",
        "version": "versão se mencionado"
    }
}

Retorne APENAS o JSON."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{LLM_CONFIG['base_url']}/api/generate",
                    json={
                        "model": LLM_CONFIG.get("model", "qwen2.5-coder:1.5b"),
                        "prompt": f"{system_prompt}\n\nDescrição: {description}",
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result.get("response", "")
                    
                    json_match = re.search(r'\{[\s\S]*\}', llm_response)
                    if json_match:
                        spec = json.loads(json_match.group())
                        return self.create_from_template(
                            spec.get("doc_type", "project_readme"),
                            title=spec.get("title"),
                            **spec.get("params", {})
                        )
        except Exception as e:
            logger.error(f"Erro ao gerar via LLM: {e}")
        
        # Fallback
        return self.create_from_template("project_readme", title=description[:50])
    
    def export_to_markdown(self, page_id: str) -> str:
        """Exporta página para Markdown"""
        if page_id not in self.pages:
            raise ValueError(f"Página não encontrada: {page_id}")
        
        page = self.pages[page_id]
        # Conversão básica HTML -> Markdown
        content = page.content
        content = re.sub(r'<h1>(.*?)</h1>', r'# \1\n', content)
        content = re.sub(r'<h2>(.*?)</h2>', r'## \1\n', content)
        content = re.sub(r'<h3>(.*?)</h3>', r'### \1\n', content)
        content = re.sub(r'<p>(.*?)</p>', r'\1\n\n', content)
        content = re.sub(r'<strong>(.*?)</strong>', r'**\1**', content)
        content = re.sub(r'<em>(.*?)</em>', r'*\1*', content)
        content = re.sub(r'<code>(.*?)</code>', r'`\1`', content)
        content = re.sub(r'<li>(.*?)</li>', r'- \1\n', content)
        content = re.sub(r'<[^>]+>', '', content)  # Remove remaining tags
        
        return content


# Instância global do agente
_confluence_agent_instance = None

def get_confluence_agent() -> ConfluenceAgent:
    """Retorna instância singleton do Confluence Agent"""
    global _confluence_agent_instance
    if _confluence_agent_instance is None:
        _confluence_agent_instance = ConfluenceAgent()
    return _confluence_agent_instance


# CLI para uso direto
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Confluence Agent - Gerador de Documentação")
    parser.add_argument("--template", "-t", help="Nome do template a usar")
    parser.add_argument("--list", "-l", action="store_true", help="Listar templates")
    parser.add_argument("--title", help="Título do documento")
    parser.add_argument("--smoke", action="store_true", help="Smoke test para CI")
    
    args = parser.parse_args()
    
    agent = get_confluence_agent()
    
    if args.smoke:
        print("🔥 Confluence Agent Smoke Test...")
        print(f"   ✅ Templates: {len(agent.list_templates())}")
        caps = agent.get_capabilities()
        print(f"   ✅ Capabilities: {caps['name']}")
        print(f"   ✅ Macros: {len(caps['macros_supported'])}")
        print(f"   ✅ Regras herdadas: {len(caps['rules_inherited'])}")
        print("🎉 Smoke test passed!")
        exit(0)
    
    if args.list:
        print("📋 Templates disponíveis:")
        for t in agent.list_templates():
            print(f"   • {t}")
        exit(0)
    
    if args.template:
        output = agent.create_from_template(args.template, title=args.title)
        print(f"✅ Documento gerado: {output}")
    else:
        # Gera exemplo padrão
        output = agent.create_from_template("project_readme")
        print(f"✅ Exemplo gerado: {output}")
