# 🚀 Sistema de Monitoramento Contínuo - Landing Page RPA4ALL

**Status:** ✅ Completo e Operacional

---

## 📋 O que foi implementado

### 1. ✅ Agendador de Validações (Cron Job)
- Executa validações diárias automaticamente
- Salva histórico de resultados
- Envia alertas em caso de problemas

### 2. ✅ Alertas Telegram
- Notificações em tempo real
- Configuração segura (arquivo local)
- Testes de conexão

### 3. ✅ Dashboard Streamlit
- Visualização de histórico
- Gráficos de tendências
- Métricas agregadas

---

## 🚀 Quick Start

### 1️⃣ Configurar Alertas Telegram (Opcional)

```bash
cd /home/edenilson/shared-auto-dev
python3 setup_telegram_alerts.py setup
**O que você precisa:**
- Bot Token do Telegram (obter em @BotFather)
- Chat ID (obter em @userinfobot)

### 2️⃣ Instalar Cron Job

```bash
chmod +x setup_validation_cron.sh
./setup_validation_cron.sh "0 2 * * *"
**Schedules comuns:**
- `0 2 * * *` → Todo dia às 2 AM (padrão)
- `0 */6 * * *` → A cada 6 horas
- `*/30 * * * *` → A cada 30 minutos
- `0 9 * * 1` → Segundas às 9 AM

### 3️⃣ Visualizar Dashboard

```bash
pip install streamlit pandas plotly
streamlit run dashboard_validations.py
Acessa: http://localhost:8501

---

## 📁 Arquivos Criados

| Arquivo | Descrição | Tamanho |
|---------|-----------|---------|
| validation_scheduler.py | Agendador com alertas | 7 KB |
| setup_validation_cron.sh | Instalador cron job | 4 KB |
| setup_telegram_alerts.py | Configurador Telegram | 6 KB |
| dashboard_validations.py | Dashboard Streamlit | 6 KB |

**Total:** ~23 KB

---

## 🔧 Uso Manual

### Executar validação sob demanda

```bash
source /home/edenilson/shared-auto-dev/.venv/bin/activate
python3 validation_scheduler.py https://www.rpa4all.com/
**Output:**
🔍 Iniciando validação: 2026-02-02T15:30:45.123456
✅ Resultado salvo no histórico
================================================
Status: SUCCESS
Stats: {'total': 11, 'success': 11, 'failed': 0}
================================================
### Ver resumo de testes

```bash
python3 validation_scheduler.py summary
**Output:**
📊 Resumo de Validações
   Total de testes: 15
   Sucesso: 15
   Falhas: 0
   Taxa de sucesso: 100.0%
   Último teste: 2026-02-02T15:30:45
### Configurar Telegram (Menu Interativo)

```bash
python3 setup_telegram_alerts.py
**Opções:**
1. Setup (configurar credentials)
2. Show (mostrar configuração atual)
3. Remove (remover configuração)
4. Sair

### Gerenciar Cron Job

```bash
# Ver cron jobs
crontab -l

# Editar
crontab -e

# Remover job de validação
crontab -l | grep -v 'validate-landing-pages' | crontab -
---

## 📊 Histórico e Logs

### Arquivo de Histórico

/tmp/validation_logs/validation_history.json
**Formato:**
```json
[
  {
    "timestamp": "2026-02-02T02:15:30.123456",
    "url": "https://www.rpa4all.com/",
    "status": "success",
    "stats": {
      "total": 11,
      "success": 11,
      "failed": 0
    },
    "output": "..."
  }
]
### Logs de Cron

/var/log/rpa4all-validation/validation_2026-02-02_02-15-30.log
**Ver logs:**
```bash
tail -f /var/log/rpa4all-validation/validation_*.log
**Limpar logs antigos:**
```bash
find /var/log/rpa4all-validation -name "*.log" -mtime +30 -delete
---

## 🔐 Configuração Telegram

### Arquivo de Configuração

~/.telegram_config.json
**Conteúdo (exemplo):**
```json
{
  "token": "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef",
  "chat_id": 123456789
}
**Permissões:** 0600 (somente leitura do proprietário)

### Segurança

- ✅ Arquivo salvo em home directory (protegido)
- ✅ Permissões restritas (0600)
- ✅ Não commitado no git (adicione ao .gitignore)
- ✅ Carregado dinamicamente pela aplicação

### Adicionar ao .gitignore

```bash
echo ".telegram_config.json" >> ~/.gitignore_global
---

## 📈 Dashboard Streamlit

### Funcionalidades

1. **Métricas Principais**
   - Total de sucessos
   - Total de erros
   - Total de testes
   - Taxa de sucesso %

2. **Gráficos**
   - Timeline de status
   - Evolução de links OK/Problemas

3. **Tabela Detalhada**
   - Cada teste com resultados
   - Taxa de sucesso por teste

4. **Alertas Recentes**
   - Últimos 5 erros
   - Detalhes expandíveis

### Executar Dashboard

```bash
# Instalação primeira vez
pip install streamlit pandas plotly

# Executar
streamlit run dashboard_validations.py

# URL padrão
http://localhost:8501
---

## ✅ Checklist de Setup

- [ ] Clonar/download dos novos scripts
- [ ] Ativar venv: `source .venv/bin/activate`
- [ ] Executar validação manual: `python3 validation_scheduler.py https://www.rpa4all.com/`
- [ ] Configurar Telegram (opcional): `python3 setup_telegram_alerts.py setup`
- [ ] Instalar cron job: `bash setup_validation_cron.sh "0 2 * * *"`
- [ ] Verificar log: `tail -f /var/log/rpa4all-validation/validation_*.log`
- [ ] Instalar Streamlit: `pip install streamlit pandas plotly`
- [ ] Iniciar dashboard: `streamlit run dashboard_validations.py`

---

## 🧪 Teste Completo

```bash
#!/bin/bash

echo "1️⃣  Executar validação..."
python3 validation_scheduler.py https://www.rpa4all.com/

echo ""
echo "2️⃣  Ver resumo..."
python3 validation_scheduler.py summary

echo ""
echo "3️⃣  Listar cron jobs..."
crontab -l | grep validate-landing

echo ""
echo "✅ Setup concluído!"
---

## 🚨 Troubleshooting

### Cron job não executa

```bash
# Verificar se está na lista
crontab -l

# Verificar logs do sistema
sudo journalctl -xe | grep cron

# Verificar permissões
ls -la /usr/local/bin/validate-landing-pages
### Telegram não envia alertas

```bash
# Verificar config
cat ~/.telegram_config.json

# Testar token
curl -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
  -d chat_id=<CHAT_ID> \
  -d text="Test"
### Dashboard não carrega

```bash
# Verificar se streamlit está instalado
python3 -c "import streamlit; print(streamlit.__version__)"

# Reinstalar
pip install streamlit pandas plotly --upgrade
---

## 📞 Próximos Passos

### Semana 1 (Crítico)
- [x] Cron job instalado
- [x] Alertas Telegram configuráveis
- [ ] **Ação:** Configurar seu bot Telegram e chat ID

### Semana 2 (Recomendado)
- [ ] Dashboard Streamlit rodando
- [ ] Histórico coletando dados
- [ ] Primeiros alertas testados

### Mês 1 (Melhorias)
- [ ] Análise de tendências no dashboard
- [ ] Otimizar schedule de cron
- [ ] Adicionar mais métricas

---

## 🎓 Exemplos de Alertas

### ✅ Sucesso
✅ Validação OK
2026-02-02 02:15:30
Total: 11 | OK: 11 | Falhas: 0
### ⚠️ Aviso
⚠️ Validação: 2/11 links com problema
Total: 11
OK: 9
Problemas: 2
### ❌ Erro Crítico
❌ Validação FALHOU
Erro: Timeout na execução (> 2 min)
---

## 📚 Documentação Relacionada

- [Bot Selenium Avançado](SELENIUM_BOTS_README.md)
- [Validação de Links](LINKS_VALIDATION_REPORT_2026-02-02.md)
- [Relatório de Deploy](DEPLOY_REPORT_LANDING_2026-02-02.md)

---

## 📧 Suporte

**Criado por:** GitHub Copilot (agente local)  
**Data:** 02/02/2026  
**Status:** ✅ Pronto para produção

---

**🎉 Sistema de Monitoramento Contínuo Implementado!**

Execute os passos acima para começar a monitorar sua landing page em tempo real.
