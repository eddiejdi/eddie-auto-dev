# Lições Aprendidas — 2026-02-22

> Sessão de operações homelab: limites de CPU, túnel Grafana, economia de tokens Copilot.

---

## 1. CPUQuota via systemd para Ollama

### Contexto
O processo `ollama` (PID 989983) estava consumindo **800% CPU** (8 cores) e **9,6 GiB RAM** no homelab.

### Ação
Criado drop-in `/etc/systemd/system/ollama.service.d/cpuquota.conf`:
```ini
[Service]
CPUQuota=640%
```
Isso limita a 80% do total (8 cores × 80% = 640%).

### Resultado
O limite foi aplicado com sucesso, mas **restringiu demais** — sob carga leve o processo ficou praticamente inativo.

### Lição aprendida
- `CPUQuota` do systemd funciona bem para limitar processos, mas para LLMs (Ollama) que precisam de burst de CPU durante inferência, **não é recomendável** limitar agressivamente.
- O limite foi **removido** a pedido do usuário, restaurando o uso total dos cores.
- **Recomendação**: não limitar CPU do Ollama a menos que haja contenção real com outros serviços críticos. Se necessário, usar `CPUWeight` (prioridade relativa) em vez de `CPUQuota` (limite absoluto).

### Referência
- Drop-in path: `/etc/systemd/system/ollama.service.d/`
- Drop-ins existentes: `cpuaffinity.conf`, `override.conf`
- Modelo em uso: `qwen3:14b` (9.3 GB, Q4_K_M)

---

## 2. Túnel Cloudflare para Grafana

### Contexto
O Grafana (porta 3002) estava acessível apenas via rede local. O túnel Cloudflare (`cloudflared-rpa4all.service`) não tinha regra de ingress para `grafana.rpa4all.com`.

### Ação
1. Adicionada regra de ingress em `/etc/cloudflared/config.yml`:
   ```yaml
   - hostname: grafana.rpa4all.com
     service: http://localhost:3002
     originRequest:
       connectTimeout: 30s
   ```
2. Reiniciado `cloudflared-rpa4all.service`
3. Verificado que a rota DNS já existia: `cloudflared tunnel route dns -f rpa4all-tunnel grafana.rpa4all.com`

### Resultado
Grafana acessível via túnel. Porém, o certificado TLS emitido pelo Cloudflare ainda cobre apenas `openwebui.rpa4all.com`.

### Pendência
- Configurar certificado wildcard `*.rpa4all.com` no Cloudflare (SSL/TLS → Edge Certificates) para cobrir `grafana.rpa4all.com`.
- Alternativa: usar proxy Cloudflare com certificado Universal SSL (já cobre subdomínios).

### Lição aprendida
- O nome correto do serviço systemd é `cloudflared-rpa4all.service` (não `cloudflared.service`).
- Sempre verificar com `systemctl list-units | grep cloudflared` antes de tentar restart.
- A rota DNS pode já existir mesmo sem a regra de ingress — são coisas separadas.

---

## 3. Modelos Ollama instalados no homelab

### Inventário (2026-02-22)

| Modelo | Parâmetros | Tamanho | RAM estimada |
|--------|-----------|---------|-------------|
| `qwen3:0.6b` | 751M | 500 MB | ~600 MB |
| `qwen3:1.7b` | 2.0B | 1.3 GB | ~1.5 GB |
| `qwen3:4b` | 4.0B | 2.5 GB | ~3 GB |
| `qwen3:8b` | 8.2B | 5.2 GB | ~6 GB |
| `eddie-assistant` | 8.2B | 5.2 GB | ~6 GB |
| `eddie-coder` | 8.2B | 5.2 GB | ~6 GB |
| `eddie-whatsapp` | 8.2B | 5.2 GB | ~6 GB |
| `qwen3:14b` | 14.8B | 9.3 GB | ~10 GB |
| `nomic-embed-text` | 137M | 274 MB | ~300 MB |

### Lição aprendida
- Todos os modelos `eddie-*` são variantes do `qwen3:8b` (mesma família, mesmo tamanho).
- Para economia de recursos, `qwen3:1.7b` é o melhor custo-benefício (1.5 GB RAM, boa qualidade).
- `qwen3:0.6b` é muito limitado para tarefas reais; serve apenas para classificação simples.

---

## 4. Economia de tokens — Copilot Pro+

### Descobertas

| Modelo Copilot | Tipo | Custo |
|----------------|------|-------|
| GPT-4o-mini | Base | **Grátis** (ilimitado) |
| Copilot (default) | Base | **Grátis** (ilimitado) |
| GPT-4o | Premium | 1× request |
| Claude Sonnet 4 | Premium | 1× request |
| Claude Opus 4 | Premium | 1× request |
| GPT-4.1 | Premium | 1× request |
| o3-mini | Premium | 1× request |

### Compatibilidade com Agent Mode
- **Completo**: Claude Opus 4, Claude Sonnet 4, GPT-4o, GPT-4.1
- **Parcial**: o3-mini (tool calling limitado), GPT-4o-mini (erra em fluxos longos)
- **Básico**: Copilot default

### Estratégia adotada
- Tarefas simples → GPT-4o-mini (grátis)
- Tarefas multi-step → Claude Sonnet 4 ou GPT-4.1
- Debugging complexo → Claude Opus 4
- Economia estimada: **50-70% menos premium requests**

### Lição aprendida
- A checagem de uso do Copilot (ler/atualizar `copilot_usage.json`) também consome 1 premium request.
- Para evitar desperdício, não automatizar checagem — o alerta automático no `.md` já é suficiente.

---

## 5. Roteamento agressivo para homelab

### Contexto
A regra de roteamento homelab existia mas não era explícita sobre a estratégia agressiva de economia de tokens.

### Ação
Atualizada a regra em dois arquivos:
1. `.github/agents/agent_dev_local.agent.md` (linha 28) — regra local expandida
2. `.github/copilot-instructions.md` — nova seção global "🔴 ROTEAMENTO HOMELAB — REGRA GLOBAL E IMPERATIVA"

### Estratégia agressiva documentada
1. Verificações/logs/métricas → homelab
2. Docker/systemd/cgroups → homelab
3. Execução scripts/tests/builds → homelab
4. Queries BD → homelab
5. Trazer APENAS resumos (< 100 chars) ao local
6. Local fica com: análise docs, edição configs, orquestração, apresentação

### Lição aprendida
- API routing (`POST /distributed/route-task`) é preferível a SSH direto — menos overhead de conexão, formato padronizado.
- SSH direto reservado para: conectividade crítica, autenticação cloudflared, fallback.
- Objetivo quantificado: **reduzir tokens Copilot em 30-50%**.

---

## 6. Formato de relatório de consumo

### Mudança
Adicionado percentual de economia ao cabeçalho obrigatório:
- **Antes**: `[YYYY-MM-DDTHH:MM UTC | Gasto: R$ X,XX | Saldo: R$ X,XX]`
- **Depois**: `[YYYY-MM-DDTHH:MM UTC | Gasto: R$ X,XX | Saldo: R$ X,XX | Econ: Y,YY%]`
- Fórmula: `econ_percent = (remaining_brl / monthly_budget_brl) * 100`

### Lição aprendida
- Transparência no consumo é fundamental para decisões de uso do plano Pro+.
- O percentual dá visibilidade rápida sem precisar fazer cálculos mentais.

---

## Resumo de alterações no repositório

| Arquivo | Alteração |
|---------|----------|
| `.github/agents/agent_dev_local.agent.md` | Regra roteamento agressivo (L28) + formato header com % (L12) |
| `.github/copilot-instructions.md` | Nova seção 🔴 ROTEAMENTO HOMELAB global |
| `.github/copilot_usage.json` | Contadores atualizados (8 requests) |
| `/etc/cloudflared/config.yml` (homelab) | Adicionada regra ingress grafana.rpa4all.com |
