# Review Quality Gate System

> Sistema de Code Review centralizado para garantir qualidade de commits e eliminar duplicação

## Quick Start

### 1. Deploy no Homelab

```bash
ssh homelab@192.168.15.2 'cd /home/homelab/eddie-auto-dev && bash specialized_agents/setup_review.sh'
### 2. Integrar com API

Em `specialized_agents/api.py`, adicione:

from specialized_agents.review_routes import router as review_router
app.include_router(review_router)
Depois reinicie a API:
```bash
ssh homelab@192.168.15.2 'sudo systemctl restart specialized-agents-api'
### 3. Iniciar Review Service

```bash
ssh homelab@192.168.15.2 'sudo systemctl start review-service'
ssh homelab@192.168.15.2 'sudo systemctl enable review-service'  # autostart
## Uso

### Agentes submetem para review (não fazem push direto)

# Agent code
import requests

response = requests.post(
    "http://localhost:8503/review/submit",
    json={
        "commit_id": "abc123...",
        "branch": "feature/python-new-cache",
        "author_agent": "python_agent",
        "diff": "...git diff...",
        "files_changed": ["src/cache.py", "tests/test_cache.py"],
        "priority": 0                # 0=normal, 1=high
    }
)

queue_id = response.json()["queue_id"]
print(f"Aguardando review: {queue_id}")
### Acompanhar status

```bash
# Ver fila
curl http://localhost:8503/review/queue

# Ver item específico
curl http://localhost:8503/review/queue/{queue_id}

# Ver métricas
curl http://localhost:8503/review/metrics
## Como funciona

### Fluxo

1. **Agent** cria branch + commits + submete via ``POST /review/submit``
2. **ReviewQueue** armazena em fila (SQLite local)
3. **ReviewService** daemon (a cada 60s):
   - Pega próximos 3 items
   - Chama **ReviewAgent** para análise
   - ReviewAgent valida:
     - Duplicação
     - Código (segurança, padrões)
     - Testes (cobertura)
     - Documentação
   - Retorna: `approve|reject|request_changes|needs_retest`
4. Se **approve** → Rodar testes Selenium → **Merge automático**
5. Se **reject** → Notificar agent com feedback = **Training**
6. A cada 10 ciclos → **Retrospectiva** dos agentes

### ReviewAgent

- **Modelo**: Claude 3.5 Sonnet (70B+ via Ollama)
- **Análise**: duplicação, segurança, padrões, testes, docs
- **Saída**: decisão + score (0-100) + recomendações
- **Treinamento**: registra padrões ruins para feedback

### Bloqueio de Push Autônomo

Agents NÃO podem fazer push para:
- `main` ❌
- `master` ❌
- `develop` ❌
- `production` ❌

Agents SÓ podem fazer push para:
- `feature/...` ✅
- `fix/...` ✅
- `chore/...` ✅
- `docs/...` ✅
- Etc

**Para chegar no main**: ReviewAgent aprova → merge automático

## Endpoints API

### POST /review/submit
Submeter commit para review
```json
{
  "commit_id": "abc123",
  "branch": "feature/xyz",
  "author_agent": "python_agent",
  "diff": "...",
  "files_changed": ["file.py"],
  "priority": 0
}
### GET /review/queue
Status geral da fila
```json
{
  "queue": {"pending": 5, "approved": 42, "merged": 38, "rejected": 4}
}
### GET /review/queue/{queue_id}
Status de um item específico

### GET /review/agent/status
Status do ReviewAgent

### GET /review/retrospective/{agent_name}
Retrospectiva: como o agent evoluiu em 7 dias

### GET /review/metrics
Métricas de review

### POST /review/action
Manual override (se ReviewAgent hesitar)

## Métricas & Monitoring

### Ver logs do service
```bash
ssh homelab@192.168.15.2 'journalctl -u review-service -f'
### Health check
```bash
curl http://localhost:8503/review/metrics
Esperado:
```json
{
  "queue": {
    "pending": 0,
    "approved": 42,
    "merged": 38,
    "rejected": 1,
    "approval_rate": 97.7
  }
}
## Benefícios

✅ **Elimina commits triviais/duplicados**  
✅ **Qualidade garantida** (só main recebe validado)  
✅ **Feedback automático** (agents aprendem com rejeições)  
✅ **Rastreabilidade** (cada merge = review_score)  
✅ **Retrospectiva** (medir evolução por agent)  
✅ **Escalável** (ReviewAgent processa fila automaticamente)

## Troubleshooting

### Service não inicia
```bash
ssh homelab@192.168.15.2 'journalctl -u review-service -n 50 --no-pager'
### Fila travada
```bash
# Manual cleanup
curl -X POST http://localhost:8503/review/cleanup?days=30
### ReviewAgent lento
- Verificar modelo LLM (Ollama 70B recomendado)
- Aumentar `REVIEW_SERVICE_BATCH` se CPU sobrando

### Testes falhando
- Verificar Selenium setup
- Aumentar `REVIEW_SERVICE_RUN_TESTS=false` para prototipar

## Configuração

Variáveis de ambiente (em `/etc/systemd/system/review-service.service`):

```bash
REVIEW_SERVICE_POLL_INTERVAL=60        # segundos entre ciclos
REVIEW_SERVICE_BATCH=3                 # items por ciclo
REVIEW_SERVICE_AUTO_MERGE=true         # merge automático após approve
REVIEW_SERVICE_RUN_TESTS=true          # rodar tests antes de merge
## Próximas fases

- [ ] Integração com Selenium para E2E testing
- [ ] Integração com Confluence para validar docs
- [ ] Dashboard Grafana com métricas de qualidade
- [ ] Alertas automáticos (Telegram) para agentes ruins
- [ ] Sistema de badges de "quality level" por agent

---

✨ **Um Quality Gate robusto = commits de alta qualidade = main branch estável** ✨
