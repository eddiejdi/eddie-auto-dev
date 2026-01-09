# Sistema On-Demand - Agentes Especializados

## Conceito
Os componentes são iniciados **apenas quando necessário** e desligados automaticamente após período de inatividade. Isso economiza recursos do servidor.

## Componentes Gerenciados

| Componente | Timeout Padrão | Função |
|------------|----------------|--------|
| `agent_manager` | 5 min | Gerencia agentes de linguagem, RAG, projetos |
| `docker` | 10 min | Orquestra containers Docker |
| `github` | 3 min | Cliente GitHub para push/repos |

## Endpoints da API

### Status e Controle On-Demand

```bash
# Health check (leve, não inicia nada)
curl http://localhost:8503/health

# Status geral
curl http://localhost:8503/status

# Status detalhado dos componentes
curl http://localhost:8503/ondemand/status

# Iniciar componente manualmente
curl -X POST http://localhost:8503/ondemand/start/agent_manager

# Parar componente manualmente
curl -X POST http://localhost:8503/ondemand/stop/agent_manager

# Parar todos os componentes
curl -X POST http://localhost:8503/ondemand/stop-all

# Configurar timeout de um componente
curl -X POST http://localhost:8503/ondemand/configure \
  -H "Content-Type: application/json" \
  -d '{"component": "agent_manager", "timeout_seconds": 600}'
```

### Endpoints que NÃO iniciam componentes
```bash
# Listar projetos (usa apenas sistema de arquivos)
curl http://localhost:8503/projects/python

# Status GitHub (verifica token apenas)
curl http://localhost:8503/github/status

# Listar linguagens disponíveis
curl http://localhost:8503/agents
```

### Endpoints que INICIAM componentes sob demanda
```bash
# Info de agente -> Inicia AgentManager
curl http://localhost:8503/agents/python

# Gerar código -> Inicia AgentManager
curl -X POST http://localhost:8503/code/generate \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "description": "hello world"}'

# Executar código -> Inicia AgentManager + Docker
curl -X POST http://localhost:8503/code/execute \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "code": "print(1+1)"}'

# Listar containers -> Inicia Docker
curl http://localhost:8503/docker/containers
```

## Script de Controle

```bash
# Tornar executável
chmod +x ~/myClaude/specialized_agents/agents-api.sh

# Comandos disponíveis
./agents-api.sh start       # Inicia API
./agents-api.sh stop        # Para API e componentes
./agents-api.sh status      # Mostra status
./agents-api.sh restart     # Reinicia
./agents-api.sh logs        # Mostra logs
./agents-api.sh install     # Instala como serviço systemd

# Controle de componentes
./agents-api.sh components start agent_manager
./agents-api.sh components stop docker
./agents-api.sh components stop-all
```

## Instalação como Serviço Systemd

```bash
# Copiar arquivo de serviço
sudo cp ~/myClaude/specialized_agents/specialized-agents-api.service /etc/systemd/system/

# Recarregar systemd
sudo systemctl daemon-reload

# Habilitar para iniciar com o sistema
sudo systemctl enable specialized-agents-api

# Iniciar serviço
sudo systemctl start specialized-agents-api

# Verificar status
sudo systemctl status specialized-agents-api
```

## Variáveis de Ambiente

Configure em `/home/eddie/myClaude/.env` ou no serviço systemd:

```bash
# Timeouts de inatividade (segundos)
ONDEMAND_AGENT_TIMEOUT=300    # AgentManager: 5 min
ONDEMAND_DOCKER_TIMEOUT=600   # Docker: 10 min
ONDEMAND_RAG_TIMEOUT=300      # RAG: 5 min
ONDEMAND_GITHUB_TIMEOUT=180   # GitHub: 3 min

# Intervalo de verificação de componentes ociosos
ONDEMAND_CLEANUP_INTERVAL=60  # 60 segundos

# Habilitar/desabilitar modo on-demand
ONDEMAND_ENABLED=true
```

## Comportamento

1. **Startup**: API inicia rapidamente, sem carregar componentes pesados
2. **Primeiro uso**: Componente é iniciado quando necessário (pode demorar alguns segundos)
3. **Uso contínuo**: Componente permanece ativo enquanto houver requisições
4. **Inatividade**: Após timeout, componente é desligado automaticamente
5. **Próximo uso**: Componente é reiniciado sob demanda

## Logs

```bash
# Ver logs da API
tail -f /tmp/agents-api.log

# Procurar por eventos on-demand
grep OnDemand /tmp/agents-api.log
```

## Dicas

- Use `/status` para ver quais componentes estão rodando
- Componentes ociosos são desligados a cada 60s (verificação)
- Para manter um componente sempre ativo, aumente o timeout ou faça requisições periódicas
- O primeiro request que inicia um componente pode demorar alguns segundos
