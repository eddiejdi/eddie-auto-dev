# 📊 FASE 2 — Guia de Atualização Manual do Grafana

**Status:** ✅ Todas as 13 métricas coletadas pelo Prometheus  
**Próximo passo:** Adicionar queries aos painéis do Grafana  
**Estimado:** 5-10 minutos

---

## 🎯 Objetivo

Adicionar as PromQL queries aos 11 painéis restantes do dashboard Shared Central para que apareçam com dados.

---

## 📋 Painéis a atualizar

| # | Painel | Query PromQL | Legenda |
|----|--------|------|---------|
| 1 | Conversas (24h) | `sum(increase(conversation_count_total[24h]))` | Total 24h |
| 2 | 🤖 Copilot — Atendimentos 24h | `sum(increase(conversation_count_total{agent_type="copilot"}[24h]))` | Copilot 24h |
| 3 | 🤖 Copilot — Total Acumulado | `sum(conversation_count_total{agent_type="copilot"})` | Copilot Total |
| 4 | ⚙️ Agentes Locais — Atendimentos 24h | `sum(increase(conversation_count_total{agent_type="local_agents"}[24h]))` | Agentes Locais 24h |
| 5 | ⚙️ Agentes Locais — Total Acumulado | `sum(conversation_count_total{agent_type="local_agents"})` | Agentes Locais Total |
| 6 | Total Mensagens | `sum(message_rate_total)` | Total Msgs/s |
| 7 | Conversas | `sum(active_conversations_total)` | Conversas Ativas |
| 8 | Decisões (Memória) | `sum(agent_memory_decisions_total)` | Decisões |
| 9 | IPC Pendentes | `sum(ipc_pending_requests)` | Pendentes |
| 10 | Confiança Média | `avg(agent_confidence_score)` | Confiança |
| 11 | Feedback Médio | `avg(agent_feedback_score)` | Feedback |

---

## 🔧 Passo-a-passo: Atualizar via Interface Web

1. **Acessar o dashboard:**
   ```
   https://grafana.rpa4all.com/d/shared-central/
   ```

2. **Clicar em Edit** (ou Ctrl+E):
   ```
   [Edit] botão no canto superior direito
   ```

3. **Para CADA painel sem dados:**
   
   a. **Clicar no título do painel** (ex: "Conversas (24h)")
   
   b. **Selecionar aba "Query"**
   
   c. **Clicar em "+ Add query"** ou onde já existe a query
   
   d. **No campo "Expression"**, colar a PromQL da tabela acima
   
   e. **Nomear a legenda** (coluna "Legend Format" → `{{instance}}`)
   
   f. **Clicar fora para aplicar**
   
   g. **Voltar ao painel** clicando em outra área

4. **Após adicionar todas as queries:**
   
   a. **Clicar em "Save"** (ou Ctrl+S)
   
   b. **Adicionar mensagem:** `FASE 2: Adicionar 11 métricas estendidas`
   
   c. **Clicar em "Save changes"**

5. **Recarregar dashboard:**
   ```
   Pressionar F5 ou recarregar página
   ```

6. **Aguardar 30-60 segundos** para os dados aparecerem

---

## 🤖 Alternativa: Atualizar via API (Script Python)

Se você tiver a **API key do Grafana**, pode usar o script automatizado:

```bash
export GRAFANA_URL=https://grafana.rpa4all.com
export GRAFANA_API_KEY=seu_api_token_aqui
python3 update_grafana_dashboard_phase2.py
```

Para obter a API key:
1. Acessar: https://grafana.rpa4all.com/org/apikeys
2. Clicar em "Create API Token"
3. Nome: `shared-auto-dev`
4. Permissão: `Edit`
5. Create
6. Copiar o token
7. Usar no comando acima

---

## ✅ Validação Após Atualização

Execute o script de validação para confirmar que o Grafana recebeu os dados:

```bash
python3 validate_shared_central_api.py
```

**Resultado esperado:**
```
Total de gauges/stats: 20
✅ Válidos: 20 (ou >= 18)
❌ Inválidos: 0 (ou <= 2)
📊 Taxa de sucesso: 100% (ou >= 90%)
```

---

## 🐛 Troubleshooting

### Problema: "Sem dados no painel"

**Causa:** Query PromQL está correta, mas precisa de mais tempo para o Prometheus scrape

**Solução:**
1. Aguardar 1-2 minutos
2. Recarregar página (F5)
3. Verificar se o job `shared-central-extended-metrics` está `up`:
   ```bash
   curl http://192.168.15.2:9090/api/v1/targets | python3 -m json.tool | grep -A 5 "shared-central-extended"
   ```

### Problema: "Painel mostra 'No data'"

**Causa:** Query PromQL tem erro de sintaxe ou métrica não existe

**Solução:**
1. Copiar a query da tabela acima **exatamente**
2. Validar no Prometheus: http://192.168.15.2:9090/graph
   - Colar a query
   - Clicar em "Execute"
   - Se funcionar lá, funcionará no Grafana também

### Problema: "Valores estranhos ou zeros"

**Causa:** Métrica usa valores mockados (banco não está conectado)

**Solução:**
1. Verificar logs do exporter:
   ```bash
   ssh homelab@192.168.15.2 'sudo journalctl -u shared-central-extended-metrics -n 50'
   ```
2. Se DATABASE_URL erro:
   ```bash
   ssh homelab@192.168.15.2 'echo $DATABASE_URL'
   ```

---

## 📊 Métricas Disponíveis em Prometheus

Para consultar quais métricas estão disponíveis:

```bash
# Via linha de comando
curl http://192.168.15.2:9105/metrics | head -20
curl http://192.168.15.2:9106/metrics | head -20

# Via interface Prometheus
http://192.168.15.2:9090/graph
→ Clicar em "Metrics" 
→ Procurar por "agent_" ou "conversation_"
```

---

## 🎯 Checklist Final

- [ ] Todas as 11 queries foram adicionadas aos painéis
- [ ] Dashboard foi salvo com a mensagem "FASE 2: ..."
- [ ] Página foi recarregada (F5)
- [ ] Aguardou 1-2 minutos para dados aparecerem
- [ ] Executou: `python3 validate_shared_central_api.py`
- [ ] Todos os gauges mostram dados ou "No data" diminuiu significativamente
- [ ] Taxa de sucesso está >= 90%

---

## 📚 Referências

- **Dashboard:** https://grafana.rpa4all.com/d/shared-central/
- **Prometheus:** http://192.168.15.2:9090
- **PromQL Docs:** https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Validation Script:** `validate_shared_central_api.py`
- **Prometheus Queries:** `validate_phase2_metrics.py` (mostra todas as queries válidas)

---

## 📝 Notas

- **Duração esperada:** 5-10 minutos
- **Risco:** Baixo (tudo é reversível)
- **Backup:** Não é necessário (Grafana não salva queries automaticamente)
- **Falha em API:** Se não conseguir via API, a interface web é 100% confiável
- **Próximas fases:** Implementar queries dinâmicas baseadas em banco de dados real

---

**Concluído em:** 2026-02-24T16:30:00 UTC  
**Próximo passo:** Atualizar Grafana (manual ou via API)  
**Tempo estimado:** 5-10 minutos
