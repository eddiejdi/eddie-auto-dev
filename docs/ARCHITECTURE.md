# 🏗️ Arquitetura do Eddie Auto-Dev System

## Visão Geral da Arquitetura

O sistema é composto por múltiplas camadas que trabalham em conjunto para fornecer uma plataforma completa de auto-desenvolvimento.

## Diagrama de Componentes

┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE INTERFACE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────┐         ┌───────────────┐         ┌───────────────┐   │
│   │   Telegram    │         │   Dashboard   │         │   API REST    │   │
│   │     Bot       │         │   Streamlit   │         │   FastAPI     │   │
│   │   (async)     │         │   :8502       │         │    :8503      │   │
│   └───────┬───────┘         └───────┬───────┘         └───────┬───────┘   │
│           │                         │                         │           │
└───────────┼─────────────────────────┼─────────────────────────┼───────────┘
            │                         │                         │
            ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CAMADA DE ORQUESTRAÇÃO                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐ │
│   │                        Agent Manager                                  │ │
│   │   - Gerencia ciclo de vida dos agentes                              │ │
│   │   - Roteia requisições para agentes apropriados                     │ │
│   │   - Coordena recursos compartilhados                                 │ │
│   └─────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │ AutoDeveloper │    │  RAG Manager  │    │ Web Search    │           │
│   │   (Bot)       │    │  (ChromaDB)   │    │ (DuckDuckGo)  │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │                         │                         │
            ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE AGENTES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│   │ Python  │ │   JS    │ │   TS    │ │   Go    │ │  Rust   │ │  Java   │ │
│   │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │ │
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │
│        │           │           │           │           │           │       │
│        └───────────┴───────────┴─────┬─────┴───────────┴───────────┘       │
│                                      │                                      │
│                         ┌────────────▼────────────┐                        │
│                         │     Base Agent Class     │                        │
│                         │  - Geração de código    │                        │
│                         │  - Testes automáticos   │                        │
│                         │  - RAG específico       │                        │
│                         └─────────────────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │                         │                         │
            ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CAMADA DE INFRAESTRUTURA                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │    Ollama     │    │    Docker     │    │    GitHub     │           │
│   │  192.168.15.2 │    │  Orchestrator │    │    Actions    │           │
│   │    :11434     │    │               │    │               │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │   ChromaDB    │    │   File        │    │   Cleanup     │           │
│   │   RAG Store   │    │   Manager     │    │   Service     │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │  PostgreSQL   │    │   Prometheus  │    │    Grafana    │           │
│   │    :5433      │    │    :9090      │    │    :3002      │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
            │                         │                         │
            ▼                         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CAMADA DE SERVIÇOS HOMELAB                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │  Authentik    │    │  Cloudflare   │    │   WireGuard   │           │
│   │  SSO :9000    │    │    Tunnel     │    │   VPN :51820  │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │ Mailserver    │    │  Roundcube    │    │   Nextcloud   │           │
│   │ @rpa4all.com  │    │  Webmail:9080 │    │    :8880      │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
│   ┌───────────────┐    ┌───────────────┐    ┌───────────────┐           │
│   │   Pi-hole     │    │    Nginx      │    │  AlertManager │           │
│   │  DNS :53      │    │   :80/:443    │    │    :9093      │           │
│   └───────────────┘    └───────────────┘    └───────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
## Fluxo de Dados

### 1. Fluxo de Requisição Normal

┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│ Usuário │─────▶│Telegram │─────▶│   Bot   │─────▶│ Ollama  │
└─────────┘      │   API   │      │ Python  │      │   LLM   │
                 └─────────┘      └─────────┘      └────┬────┘
                                                        │
                                                        ▼
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│ Usuário │◀─────│Telegram │◀─────│   Bot   │◀─────│Resposta │
└─────────┘      │   API   │      │ Python  │      │  LLM    │
                 └─────────┘      └─────────┘      └─────────┘
### 2. Fluxo de Auto-Desenvolvimento

┌─────────┐      ┌─────────┐      ┌─────────┐
│ Usuário │─────▶│   Bot   │─────▶│ Ollama  │
└─────────┘      └─────────┘      └────┬────┘
                      │                 │
                      │    ┌────────────▼────────────┐
                      │    │ Detecta que não sabe    │
                      │    │ responder (patterns)   │
                      │    └────────────┬────────────┘
                      │                 │
                      ▼                 ▼
              ┌───────────────────────────────────┐
              │        Auto-Developer             │
              │  1. Analisa requisição            │
              │  2. Busca na web (se necessário)  │
              │  3. Consulta RAG                  │
              │  4. Detecta linguagem             │
              │  5. Chama agente especializado    │
              └─────────────────┬─────────────────┘
                                │
                                ▼
              ┌───────────────────────────────────┐
              │        Agente Especializado        │
              │  1. Gera código                    │
              │  2. Cria projeto estruturado      │
              │  3. Executa testes                │
              │  4. Push para GitHub              │
              └─────────────────┬─────────────────┘
                                │
                                ▼
              ┌───────────────────────────────────┐
              │         GitHub Actions            │
              │  1. CI pipeline executa           │
              │  2. Testes rodam                  │
              │  3. Notifica resultado            │
              └─────────────────┬─────────────────┘
                                │
                                ▼
              ┌───────────────────────────────────┐
              │       Post-Deploy Test            │
              │  1. Aguarda 30 segundos           │
              │  2. Testa com requisição original │
              │  3. Indexa solução no RAG         │
              │  4. Notifica usuário              │
              └───────────────────────────────────┘
### 3. Fluxo RAG (Retrieval Augmented Generation)

┌─────────────────────────────────────────────────────────────┐
│                    RAG Pipeline                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────┐                                          │
│   │   Input     │ "como criar API REST com FastAPI"        │
│   └──────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                          │
│   │  Embedding  │  Converte texto em vetor                 │
│   │   Model     │  [0.12, -0.45, 0.89, ...]               │
│   └──────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                          │
│   │  ChromaDB   │  Busca vetores similares                 │
│   │   Search    │  Top K resultados                        │
│   └──────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────────────────────────────────────────────┐ │
│   │  Resultados (ordenados por similaridade)             │ │
│   │  1. [0.95] Exemplo de CRUD FastAPI                   │ │
│   │  2. [0.89] Documentação FastAPI                      │ │
│   │  3. [0.84] Projeto anterior similar                  │ │
│   └──────┬──────────────────────────────────────────────┘ │
│          │                                                  │
│          ▼                                                  │
│   ┌─────────────┐                                          │
│   │   Prompt    │  Contexto + Pergunta → LLM              │
│   │  Augmented  │                                          │
│   └─────────────┘                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
## Componentes Detalhados

### TelegramAPI Class

class TelegramAPI:
    """Interface completa com Telegram Bot API"""
    
    # Mensagens
    send_message()      # Envia texto
    forward_message()   # Encaminha
    edit_message_text() # Edita
    delete_message()    # Deleta
    
    # Mídia
    send_photo()        # Foto
    send_document()     # Documento
    send_audio()        # Áudio
    send_video()        # Vídeo
    send_voice()        # Voz
    send_sticker()      # Sticker
    
    # Localização
    send_location()     # GPS
    send_venue()        # Estabelecimento
    send_contact()      # Contato
    
    # Interatividade
    send_poll()         # Enquete
    send_quiz()         # Quiz
    answer_callback_query()  # Callback buttons
    
    # Updates
    get_updates()       # Long polling
    get_me()            # Info do bot
### EddieBot Class

class EddieBot:
    """Bot principal com processamento de mensagens"""
    
    # Atributos
    api: TelegramAPI
    auto_dev: AutoDeveloper
    conversation_history: Dict
    offset: int
    
    # Métodos principais
    async start()           # Loop principal
    async handle_update()   # Processa update
    async handle_message()  # Processa mensagem
    async handle_command()  # Processa comando
    async query_llm()       # Consulta Ollama
### AutoDeveloper Class

class AutoDeveloper:
    """Sistema de auto-desenvolvimento"""
    
    # Atributos
    agents_api: str
    pending_tests: Dict  # {thread_id: original_request}
    web_search: WebSearchEngine
    
    # Detecção
    check_inability()           # Detecta se não consegue
    detect_language()           # Detecta linguagem
    
    # Desenvolvimento
    trigger_development()       # Inicia processo
    _create_with_agent()        # Usa agente especializado
    _push_to_github()           # Push automático
    
    # Testes
    _delayed_post_deploy_test() # Teste após deploy
    _test_with_original_request()  # Testa com pedido original
    _notify_test_result()       # Notifica resultado
    
    # Web
    _search_web_for_context()   # Busca contexto web
### AgentManager Class

class AgentManager:
    """Gerenciador central de agentes"""
    
    # Lifecycle
    async initialize()      # Inicializa sistema
    async shutdown()        # Desliga sistema
    
    # Agentes
    get_or_create_agent()   # Obtém/cria agente
    list_active_agents()    # Lista ativos
    
    # Projetos
    create_project()        # Cria projeto
    execute_code()          # Executa código
    download_project()      # Download ZIP
    
    # GitHub
    push_to_github()        # Push código
    
    # RAG
    search_rag()            # Busca
    index_to_rag()          # Indexa
    
    # Cleanup
    run_cleanup()           # Limpeza
    get_system_status()     # Status
## Tecnologias Utilizadas

### Core
- **Python 3.11+** - Linguagem principal
- **asyncio** - Programação assíncrona
- **httpx** - Cliente HTTP async

### Backend
- **FastAPI** - Framework API REST
- **uvicorn** - ASGI server
- **pydantic** - Validação de dados

### IA/ML
- **Ollama** - Servidor LLM local
- **ChromaDB** - Banco vetorial
- **sentence-transformers** - Embeddings

### Infraestrutura
- **Docker** - Containers isolados
- **systemd** - Gerenciamento de serviços
- **GitHub Actions** - CI/CD

### Integrações
- **Telegram Bot API** - Interface usuário
- **DuckDuckGo** - Busca web
- **GitHub API** - Repositórios

### Serviços Homelab
- **Authentik SSO** - Autenticação centralizada (OAuth2/OIDC)
- **Cloudflare Tunnel** - Exposição segura de serviços
- **WireGuard VPN** - Acesso remoto seguro
- **Pi-hole** - DNS/Ad-blocking
- **Nginx** - Reverse proxy
- **docker-mailserver** - Email @rpa4all.com (Postfix+Dovecot+Rspamd)
- **Roundcube** - Webmail
- **Nextcloud** - Cloud privada
- **Grafana + Prometheus** - Monitoramento
- **AlertManager** - Alertas para Telegram

## Escalabilidade

### Horizontal
- Múltiplos agentes podem rodar em paralelo
- Containers Docker escalam independentemente
- RAG pode ser distribuído

### Vertical
- Ollama suporta modelos maiores
- ChromaDB escala com mais dados
- Recursos de container ajustáveis

## Segurança

### Autenticação
- Token Telegram validado
- GitHub token para operações
- Admin chat ID para comandos sensíveis

### Isolamento
- Containers Docker por projeto
- Volumes isolados por linguagem
- Rede Docker isolada

### Dados
- Tokens em variáveis de ambiente
- .gitignore para arquivos sensíveis
- Logs sem dados sensíveis
