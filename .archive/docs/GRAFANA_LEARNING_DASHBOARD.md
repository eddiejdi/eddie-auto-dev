# Dashboard de Evolução do Aprendizado - Grafana

## 📊 Visão Geral

Dashboard criado em Grafana para monitorar o crescimento e evolução dos modelos Ollama no servidor homelab.

**URL de Acesso:** [http://${HOMELAB_HOST}:3002/grafana/d/learning-evolution](http://${HOMELAB_HOST}:3002/grafana/d/learning-evolution)

**Credenciais:**
- Usuário: `admin`
- Senha: `Shared@2026`

---

## 📈 Métricas Atuais

### Evolução de Dados de Treinamento

| Arquivo | Data | Conversas | Tamanho |
|---------|------|-----------|---------|
| training_2026-01-06.jsonl | 06/01/2026 | 92 | 185.0 KB |
| training_2026-01-09_full.jsonl | 09/01/2026 | 91 | 176.2 KB |
| training_2026-01-10_knowledge.jsonl | 10/01/2026 | 8 | 1.2 KB |
| training_2026-01-10_session.jsonl | 10/01/2026 | 9 | 2.1 KB |
| training_2026-01-31_knowledge.jsonl | 31/01/2026 | 8 | 1.2 KB |

**Total:** 208 conversas indexadas | 0.36 MB de dados

### Modelos Treinados (Shared)

| Modelo | Tamanho | Atualização | Base |
|--------|---------|-------------|------|
| shared-homelab:latest | 4466.1 MB | 10/01/2026 | qwen2.5-coder:7b |
| shared-coder:latest | 4466.1 MB | 10/01/2026 | qwen2.5-coder:7b |
| shared-assistant:latest | 4445.3 MB | 10/01/2026 | llama2-uncensored:8b |
| shared-whatsapp:latest | 4445.3 MB | 10/01/2026 | llama2-uncensored:8b |

---

## 🚀 Como Usar o Dashboard

### 1. **Acessar o Grafana**
```bash
# Via navegador na rede homelab
http://${HOMELAB_HOST}:3002/grafana/d/learning-evolution

# Via SSH com port forwarding (de fora da rede)
ssh -i ~/.ssh/shared_deploy_rsa -L 3002:127.0.0.1:3002 homelab@${HOMELAB_HOST}

# Depois acesse: http://localhost:3002/grafana/d/learning-evolution
### 2. **Interpretar os Painéis**

#### Painel 1: Crescimento de Conversas Indexadas
- **O que mostra:** Evolução temporal do número de conversas coletadas para treinamento
- **Métrica importante:** Taxa de crescimento (+1.1% no período)
- **Insights:**
  - Conversas são a base do aprendizado contínuo
  - Períodos com mais conversas indicam maior atividade de desenvolvimento

#### Painel 2: Tamanho dos Arquivos de Treinamento
- **O que mostra:** Volume de dados de cada arquivo de treinamento (em KB)
- **Métrica importante:** Correlação entre tamanho do arquivo e número de conversas
- **Insights:**
  - Arquivos maiores = mais dados de contexto
  - Permite otimizar alocação de recursos

#### Painel 3: Modelos Ollama Disponíveis
- **O que mostra:** Todos os modelos disponíveis no servidor com tamanho
- **Metric importante:** Presença de modelos "shared-*" personalizados
- **Insights:**
  - Modelos personalizados (shared-coder, shared-assistant, etc.) contêm conhecimento aprendido
  - Modelos base (qwen2.5-coder, llama2) são os fundamentos

---

## 🔄 Atualizar o Dashboard Automaticamente

### Opção 1: Agendamento Manual (via Cron)
```bash
# Adicionar ao crontab para atualizar dados a cada hora
0 * * * * /home/edenilson/shared-auto-dev/.venv/bin/python /home/edenilson/shared-auto-dev/grafana_learning_dashboard.py >> /tmp/grafana_update.log 2>&1
### Opção 2: Script de Atualização Automática
```bash
# Executar em background (systemd timer)
# Ver: /home/edenilson/shared-auto-dev/systemd/learning-metrics.timer
systemctl start learning-metrics.timer
---

## 📊 Interpretação de Tendências

### Crescimento Esperado ⬆️
- **Mais conversas:** Indica desenvolvimento ativo
- **Novos modelos:** Novos especializações sendo criadas
- **Tamanho crescente:** Mais conhecimento sendo indexado

### Estagnação 🔄
- **Sem novos arquivos:** Considere treinar novamente
- **Modelos desatualizados:** Agendar retreinamento
- **Dados antigos:** Atualizar fonte de treinamento

### Regressão ⬇️
- **Dados deletados:** Verificar integridade do backup
- **Modelos menores:** Possível limpeza ou otimização

---

## 🛠️ Personalização

### Adicionar Novo Painel

1. **No Grafana**, clique em "Add Panel"
2. **Escolha tipo:** Graph, Table, Gauge, etc.
3. **Configure datasource:** JSON API
4. **Query:** Use as métricas disponíveis

### Métricas Disponíveis (JSON API)

```json
{
  "conversas_indexadas": 208,
  "arquivos_treinamento": 5,
  "modelos_ollama": 8,
  "tamanho_total_mb": 0.36,
  "modelos": [...],
  "treinamentos": [...]
}
---

## 🔐 Segurança

- Dashboard está protegido com autenticação Grafana
- Dados são consultados via SSH com chave RSA
- Nenhuma credencial armazenada em plain text

---

## 📝 Notas Operacionais

- **Refresh Interval:** 30 segundos
- **Time Range Padrão:** Últimos 30 dias
- **Timezone:** Browser (usa horário local)
- **UID Dashboard:** `learning-evolution`

---

## 🐛 Troubleshooting

### Dashboard não carrega
```bash
# Verificar status do Grafana
ssh -i ~/.ssh/shared_deploy_rsa homelab@${HOMELAB_HOST} docker ps | grep grafana

# Verificar logs
ssh -i ~/.ssh/shared_deploy_rsa homelab@${HOMELAB_HOST} docker logs grafana | tail -20
### Métricas não aparecem
```bash
# Testar coleta de dados
/home/edenilson/shared-auto-dev/.venv/bin/python /home/edenilson/shared-auto-dev/grafana_learning_dashboard.py --test
### Autenticação falha
```bash
# Reset password do Grafana
ssh -i ~/.ssh/shared_deploy_rsa homelab@${HOMELAB_HOST} \
  docker exec grafana grafana-cli admin reset-admin-password <nova_senha>
---

## 📚 Referências

- [Grafana Documentation](https://grafana.com/docs/)
- [JSON API Plugin](https://grafana.com/grafana/plugins/grafana-json-api-datasource/)
- [Ollama Documentation](https://github.com/ollama/ollama)

---

**Última atualização:** 02/02/2026  
**Criado por:** GitHub Copilot  
**Status:** ✅ Operacional
