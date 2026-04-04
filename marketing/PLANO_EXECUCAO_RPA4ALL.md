# Plano de Execução — Campanha de Marketing Digital RPA4ALL

> **Status**: FASE 1 — SETUP CONCLUÍDO | FASE 2 — CONCLUÍDA | Aguardando APPROVE para FASE 3
> **Data**: 2026-04-01
> **Modelo**: Híbrido (Meta 50% + Google 30% + Remarketing 10% + LinkedIn 10%)
> **Orçamento mensal estimado**: R$ 3.000 – R$ 5.000 (requer APPROVE banking)

---

## 1. Visão Geral da Estratégia

| Canal | % Budget | Objetivo | KPI |
|-------|----------|----------|-----|
| Meta Lead Ads | 50% | Topo/meio funil — captura de leads | CPL < R$ 25 |
| Google Search Ads | 30% | Fundo funil — intenção de compra | CPA < R$ 80 |
| Remarketing (Meta+Google) | 10% | Reengajar visitantes | CTR > 3% |
| LinkedIn Ads | 10% | ABM decisores | CPL < R$ 60 |
| Orgânico (X, WhatsApp, Email) | R$ 0 | Nutrição + autoridade | Engagement |

**ICP**: Empresas com operações repetitivas (financeiro, atendimento, backoffice, logística, contabilidade)
**Personas**: Dono, diretor, gerente de operações, TI, financeiro
**Oferta principal**: "Diagnóstico de Automação Gratuito em 20 minutos"

---

## 2. Fases de Execução

### FASE 1 — Setup (Semana 1) 🔧

| # | Tarefa | Fluxo Existente | Status |
|---|--------|-----------------|--------|
| 1.1 | Landing page "Diagnóstico Gratuito" | `marketing/landing_diagnostico.html` | ✅ PRONTO |
| 1.2 | Formulário de captura (nome, email, empresa, cargo, telefone) | `marketing/landing_diagnostico.html` | ✅ PRONTO |
| 1.3 | Integração formulário → PostgreSQL (tabela `marketing.leads`) | `marketing/lead_capture_api.py` | ✅ PRONTO |
| 1.4 | Webhook: novo lead → Telegram notification | `marketing/lead_capture_api.py` | ✅ PRONTO |
| 1.5 | Webhook: novo lead → WhatsApp auto-message | `marketing/lead_capture_api.py` | ✅ PRONTO |
| 1.6 | Pixel Meta + Google Tag Manager na landing | Placeholders na landing | ⏳ PENDENTE IDs |
| 1.7 | Configurar contas Meta Business + Google Ads | Banking Agent (APPROVE) | 🔒 APPROVE |
| 1.8 | SMTP para email marketing (nurturing) | `marketing/email_nurturing.py` | ✅ PRONTO |

### FASE 2 — Conteúdo e Artes (Semana 1-2) 🎨

| # | Tarefa | Status |
|---|--------|--------|
| 2.1 | 5 criativos Meta Lead Ads (carrossel + imagem única) | ✅ PRONTO (13 PNGs) |
| 2.2 | 3 anúncios Google Search (headlines + descriptions) | ✅ PRONTO |
| 2.3 | 2 banners remarketing (Display) | ✅ PRONTO (300x250 + 728x90) |
| 2.4 | 1 anúncio LinkedIn (Sponsored Content) | ✅ PRONTO (2 criativos) |
| 2.5 | Sequência de 5 emails de nutrição (drip) | ✅ PRONTO |
| 2.6 | Template WhatsApp de boas-vindas ao lead | ✅ PRONTO |
| 2.7 | 10 posts orgânicos para X/Twitter (1 mês) | ✅ PRONTO |

### FASE 3 — Lançamento (Semana 3) 🚀

| # | Tarefa | Fluxo | Status |
|---|--------|-------|--------|
| 3.1 | Ativar campanhas Meta | Banking Agent (APPROVE) | 🔒 APPROVE |
| 3.2 | Ativar campanhas Google Ads | Banking Agent (APPROVE) | 🔒 APPROVE |
| 3.3 | Ativar campanha LinkedIn | Banking Agent (APPROVE) | 🔒 APPROVE |
| 3.4 | Ativar automação email (drip sequence) | `marketing-email-drip.timer` | ✅ PRONTO |
| 3.5 | Ativar posts agendados no X | `marketing-x-posts.timer` | ✅ PRONTO |
| 3.6 | Monitoramento dashboards Grafana | `marketing-daily-report.timer` | ✅ PRONTO |

### FASE 4 — Otimização Contínua (Semana 4+) 📊

| # | Tarefa | Frequência |
|---|--------|-----------|
| 4.1 | Review CPL/CPA por canal | Diário |
| 4.2 | A/B test criativos (pausar perdedores) | Semanal |
| 4.3 | Ajuste de budget entre canais | Semanal |
| 4.4 | Relatório Telegram com métricas | Diário (automático) |
| 4.5 | Follow-up leads qualificados | 48h após captura |

---

## 3. Fluxos Automatizados

### 3.1 Fluxo de Captura de Lead (NOVO)
```
[Landing Page] → [Form Submit]
    → [PostgreSQL marketing.leads]
    → [Telegram: "🔔 Novo lead: {nome} - {empresa}"]
    → [WhatsApp: Mensagem de boas-vindas]
    → [Email: Sequência drip (dia 0)]
```

### 3.2 Fluxo de Nutrição por Email (NOVO)
```
Dia 0: "Obrigado pelo interesse! Seu diagnóstico está agendado"
Dia 2: "3 sinais de que sua empresa precisa de automação"
Dia 5: "Case: Como reduzimos 70% do trabalho manual"
Dia 8: "Checklist gratuito: processos que podem ser automatizados"
Dia 12: "Última chance: agende seu diagnóstico gratuito"
```

### 3.3 Fluxo de Relatório Diário (NOVO)
```
[Cron 08:00] → Coleta métricas (Meta API + Google API + DB leads)
    → Telegram: Relatório diário com CPL, CPA, leads, custo
    → PostgreSQL: marketing.daily_metrics
```

### 3.4 Fluxo de Postagem Orgânica X/Twitter (EXISTENTE — adaptar)
```
[Cron semanal] → X Agent gera conteúdo via Ollama
    → Post no X com hashtags #RPA #automação #IA
    → Métricas Prometheus
```

---

## 4. Infraestrutura necessária (que já existe)

| Recurso | Status | Localização |
|---------|--------|-------------|
| PostgreSQL | ✅ Ativo | 192.168.15.2:5433 |
| FastAPI | ✅ Ativo | Porta 8503 |
| Telegram Bot | ✅ Ativo | systemd: shared-telegram-bot |
| WhatsApp Bot | ✅ Ativo | systemd: shared-whatsapp-bot |
| X Agent | ✅ Ativo | Porta 8515 |
| Grafana | ✅ Ativo | rpa4all.com/grafana |
| SMTP | ✅ Ativo | Postfix + Dovecot |
| Site RPA4ALL | ✅ Ativo | rpa4all.com |
| Ollama LLM | ✅ Ativo | GPU0 :11434, GPU1 :11435 |
| Banking (Mercado Pago) | ⚠️ Setup | tools/mercadopago_oauth_setup.py |

---

## 5. Itens que requerem APPROVE explícito

| # | Item | Custo estimado | Ação Banking |
|---|------|---------------|--------------|
| A1 | Conta Meta Business Manager | R$ 0 (gratuito) | Config apenas |
| A2 | Budget Meta Ads (mensal) | R$ 1.500–2.500 | 🔒 APPROVE |
| A3 | Conta Google Ads | R$ 0 (gratuito) | Config apenas |
| A4 | Budget Google Ads (mensal) | R$ 900–1.500 | 🔒 APPROVE |
| A5 | Conta LinkedIn Campaign Manager | R$ 0 (gratuito) | Config apenas |
| A6 | Budget LinkedIn Ads (mensal) | R$ 300–500 | 🔒 APPROVE |
| A7 | Domínio/SSL (se necessário) | R$ 0 (já tem) | N/A |
| **TOTAL MENSAL** | | **R$ 2.700–4.500** | |

> **Nenhum pagamento será efetuado sem APPROVE explícito via Telegram.**

---

## 6. Métricas de Sucesso (30 dias)

| Métrica | Meta |
|---------|------|
| Leads capturados | > 50 |
| CPL médio | < R$ 30 |
| Taxa de conversão landing | > 15% |
| Diagnósticos agendados | > 15 |
| CAC (custo por cliente) | < R$ 500 |
| ROI | > 3x |

---

## 7. Arquivos criados nesta execução

| Arquivo | Descrição |
|---------|-----------|
| `marketing/PLANO_EXECUCAO_RPA4ALL.md` | Este plano |
| `marketing/lead_capture_api.py` | API de captura de leads |
| `marketing/email_nurturing.py` | Sequência de emails automática |
| `marketing/daily_report.py` | Relatório diário Telegram |
| `marketing/landing_diagnostico.html` | Landing page do diagnóstico |
| `marketing/ads/meta_ads_copy.json` | Copys dos anúncios Meta |
| `marketing/ads/google_ads_copy.json` | Copys dos anúncios Google |
| `marketing/ads/linkedin_ads_copy.json` | Copys do anúncio LinkedIn |
| `marketing/ads/email_sequences.json` | Sequência de emails |
| `marketing/ads/x_posts.json` | Posts orgânicos para X |
| `marketing/ads/whatsapp_templates.json` | Templates WhatsApp |
| `marketing/app.py` | FastAPI standalone (porta 8520) |
| `marketing/db_migrate.py` | Migração do banco (schema marketing) |
| `marketing/x_post_scheduler.py` | Agendador de posts X/Twitter |
| `marketing/deploy.sh` | Script de deploy completo |
| `marketing/generate_ad_images.py` | Gerador de imagens (Pillow) |
| `config/marketing-nginx.conf` | Snippet nginx para proxy |
| `systemd/marketing-api.service` | Serviço FastAPI marketing |
| `systemd/marketing-daily-report.service` | Relatório diário (oneshot) |
| `systemd/marketing-daily-report.timer` | Timer 08:00 diário |
| `systemd/marketing-email-drip.service` | Email drip (oneshot) |
| `systemd/marketing-email-drip.timer` | Timer 09:00 + 15:00 |
| `systemd/marketing-x-posts.service` | Post no X (oneshot) |
| `systemd/marketing-x-posts.timer` | Timer Ter/Qui/Sáb 10:30 |
| `tests/test_marketing.py` | 40 testes unitários |

---

## 8. Storage Gerenciado — Complemento de marketing (FASE 3)

> **Status**: AGUARDANDO APPROVE  
> **Produto**: Storage Empresarial LTFS — R$ 0,02/GB (10x mais barato que cloud)

### 8.1 Canais e materiais criados

| Canal | Arquivo | Peças |
|-------|---------|-------|
| Meta Ads | `marketing/ads/storage_ads_copy.json` | 4 anúncios (custo, LGPD, carrossel 4 cards, remarketing 50% OFF) |
| Google Ads | `marketing/ads/storage_ads_copy.json` | 3 grupos (custo, compliance, portal) |
| LinkedIn Ads | `marketing/ads/storage_ads_copy.json` | 2 anúncios (CTO/CIO + DPO) |
| X/Twitter | `marketing/ads/storage_x_posts.json` | 8 posts orgânicos (4 semanas) |
| WhatsApp | `marketing/ads/storage_whatsapp_templates.json` | 4 templates (boas-vindas, follow-up, onboarding, lembrete) |
| Landing Page | `marketing/landing_storage.html` | Página completa com formulário /storage |
| Imagens | `marketing/ads/images/STG-*.png` | 11 criativos (Meta, Google Display, LinkedIn) |

### 8.2 Imagens geradas (11 PNGs)

| ID | Formato | Descrição |
|----|---------|-----------|
| STG-META-01 | 1080x1080 | Comparativo 10x mais barato (barras Cloud vs LTFS) |
| STG-META-02 | 1080x1080 | LGPD Compliance (R$ 50M multa + checklist) |
| STG-META-03 x4 | 1080x1080 | Carrossel: Custo, LGPD, SLA 4h, Portal 24/7 |
| STG-META-04 | 1080x1080 | Remarketing 50% OFF (badge dourado) |
| STG-GADS 300x250 | 300x250 | Display retângulo médio |
| STG-GADS 728x90 | 728x90 | Display leaderboard |
| STG-LINKEDIN-01 | 1200x627 | Custo comparativo + bullets |
| STG-LINKEDIN-02 | 1200x627 | LGPD retenção + solução |

### 8.3 Infraestrutura (reutiliza deploy existente)

- Rota `/storage` adicionada em `marketing/app.py`
- Location `/storage` adicionada em `config/marketing-nginx.conf`
- Lead capture via `POST /marketing/leads` com `origem=landing_storage`
- X posts publicáveis via `marketing/x_post_scheduler.py` (mesmo timer)

### 8.4 Testes

- **58 testes** passando (40 originais + 18 storage)
- Cobertura: ads JSON, X posts, WhatsApp templates, landing page, imagens, rotas app
