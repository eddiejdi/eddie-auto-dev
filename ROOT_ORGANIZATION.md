# Organização da Raiz do Projeto

## Estrutura de Diretórios

```
eddie-auto-dev/
├── .git/                          # Controle de versão
├── .github/                       # GitHub Actions, configurações e instruções
├── .venv/                         # Virtual environment
│
├── specialized_agents/            # Agentes especializados (bus, coordenador, etc)
├── dev_agent/                     # Agente de desenvolvimento
├── ad_interceptor/                # Interceptor de conversas
│
├── scripts/                       # Scripts e utilitários
│   ├── automation/               # Scripts de automação (Selenium, RPA, etc)
│   ├── utils/                    # Utilitários reutilizáveis
│   └── legacy/                   # Scripts legados/deprecados
│
├── tests/                         # Testes unitários e integração
├── tools/                         # Ferramentas e helpers
├── docker/                        # Docker Compose e Dockerfiles
├── systemd/                       # Serviços systemd e timers
│
├── assets/                        # Mídia e recursos estáticos
│   ├── images/                   # Screenshots, imagens
│   └── documents/                # PDFs, documentação estática
│
├── docs/                          # Documentação
│   ├── api/                      # Documentação de API
│   ├── architecture/             # Diagramas e design
│   ├── setup/                    # Guias de setup/deployment
│   └── archive/                  # Docs históricas/deprecated
│
├── config/                        # Arquivos de configuração
│   ├── grafana/                  # Dashboards Grafana
│   ├── prometheus/               # Configurações Prometheus
│   └── systemd/                  # Configs systemd
│
├── data/                          # Dados (não sincronizados via git)
│   ├── agent_data/               # Dados de agentes
│   ├── rag/                      # Vector stores RAG
│   ├── models/                   # Modelos de ML
│   └── cache/                    # Cache e temporários
│
├── deploy/                        # Scripts e configs de deployment
├── monitoring/                    # Monitoramento e alertas
├── ollama/                        # Ollama modelfiles e configs
│
├── training_data/                 # Dados de treinamento (não sincronizados)
├── whatsapp_data/                # Integração WhatsApp
├── email_training_data/          # Dados de treinamento Email
│
├── requirements.txt               # Dependências Python
├── pytest.ini                     # Configuração pytest
├── README.md                      # Documentação principale
└── eddie-auto-dev.code-workspace # Workspace VS Code
```

## Regras de Organização

### Não Versionados (adicionar a .gitignore)
- `data/**/*.cache`
- `training_data/**`
- `*.pkl`, `*.joblib`
- `__pycache__/`, `*.pyc`
- `logs/**`

### Onde Colocar Arquivos

| Tipo | Localização |
|------|-------------|
| Scripts Python utilitários | `scripts/utils/` |
| Scripts de automação | `scripts/automation/` |
| Scripts de deployment | `deploy/` |
| Configurações docker | `docker/` |
| Services systemd | `systemd/` |
| Documentação .md | `docs/archive/` |
| Imagens/screenshots | `assets/images/` |
| Modelfiles Ollama | `ollama/` |
| Configuração JSON | `config/` |
| Logs e temporários | `data/logs/` ou `tmp/` |

