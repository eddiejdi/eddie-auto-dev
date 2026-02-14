# Guia Completo: Pipeline de Processamento de Vagas via WhatsApp (WAHA)

## Visão Geral

Este documento descreve o processo completo de detecção, análise e aplicação automática a vagas de emprego recebidas via WhatsApp através da API WAHA (WhatsApp HTTP API). O sistema automatiza a triagem de mensagens, análise de compatibilidade com currículo, geração de emails personalizados e envio via Gmail API.

**Data de Criação:** 12 de fevereiro de 2026  
**Última Atualização:** 12 de fevereiro de 2026  
**Versão:** 2.0 (com correções de WAHA e currículo completo)

## Pré-requisitos

### Infraestrutura
- **Homelab:** Servidor em `192.168.15.2` com acesso SSH (`homelab@192.168.15.2`)
- **Docker:** Container WAHA rodando (`devlikeapro/waha:latest`)
- **Ollama:** Serviço LLM em `http://192.168.15.2:11434` com modelo `llama3.2:3b`
- **Python:** Ambiente com dependências instaladas (ver `requirements.txt`)

### APIs e Credenciais
- **WAHA API:** `http://192.168.15.2:3001`, chave API: `757fae2686eb44479b9a34f1b62dbaf3`
- **Gmail API:** Credenciais em `/home/homelab/myClaude/gmail_data/credentials.json`
- **Google Drive API:** Para acesso ao currículo
- **Secrets DB:** `/var/lib/eddie/secrets_agent/audit.db` (SQLite com valores base64)

### Arquivos Essenciais
- `apply_real_job.py`: Script principal do pipeline
- `setup_waha.py`: Configuração da sessão WAHA
- `Curriculo_Edenilson.docx`: Currículo completo em `/home/homelab/eddie-auto-dev/`
- `WHATSAPP_BOT_README.md`: Documentação WAHA

## Processo Completo

### Fase 1: Configuração Inicial do WAHA

#### 1.1 Verificar Status do Container WAHA
```bash
# No homelab
docker ps | grep waha
# Deve mostrar: devlikeapro/waha:latest rodando na porta 3001->3000
```

#### 1.2 Criar Sessão WAHA (se necessário)
```bash
# Executar setup_waha.py no homelab
python3 setup_waha.py
# Cria sessão "default" (WAHA Core só suporta "default", não "eddie")
```

#### 1.3 Conectar WhatsApp
- Gerar QR code: `curl -X POST http://192.168.15.2:3001/api/default/auth/qr`
- Salvar em `/tmp/whatsapp_qr.txt`
- **AÇÃO MANUAL:** Escanear QR com WhatsApp no número `5511981193899`

#### 1.4 Verificar Conexão
```bash
# Status da sessão
curl -H "X-Api-Key: 757fae2686eb44479b9a34f1b62dbaf3" \
     http://192.168.15.2:3001/api/default/sessions
# Deve retornar: {"status": "WORKING"}
```

### Fase 2: Extração e Análise de Currículo

#### 2.1 Instalar Dependências
```bash
# No homelab
pip install python-docx
```

#### 2.2 Extrair Habilidades do Currículo
O script `apply_real_job.py` extrai automaticamente:
- **104 habilidades** do arquivo `Curriculo_Edenilson.docx`
- **Objetivos profissionais** para boosting
- Sistema de pontuação: +15% para match objetivo, +10% para 5+ skills, +5% para 3+

### Fase 3: Processamento de Mensagens

#### 3.1 Executar Pipeline Completo
```bash
# No homelab
python3 apply_real_job.py --process-all
```

#### 3.2 Fluxo Interno do Script
1. **Listar sessões WAHA:** GET `/api/default/sessions`
2. **Buscar chats/grupos:** GET `/api/default/chats` (filtra grupos)
3. **Extrair mensagens:** GET `/api/default/chats/{chatId}/messages`
4. **Classificar mensagens:** Rule-based + LLM para detectar vagas
5. **Analisar compatibilidade:** Jaccard Similarity com threshold 15%
6. **Gerar email:** Via Ollama (modelo `llama3.2:3b`)
7. **Enviar email:** Gmail API com anexo do currículo

### Fase 4: Geração e Envio de Email

#### 4.1 Configuração LLM
- **Modelo:** `llama3.2:3b` (NÃO `llama3.2`)
- **Prompt:** Inclui showcase do sistema Eddie Auto-Dev
- **Temperatura:** Ajustada para consistência

#### 4.2 Gmail API Setup
- **Scopes:** `gmail.modify`, `gmail.send`, `drive`
- **Token:** Armazenado em secrets DB (refresh automático)
- **Anexo:** Currículo baixado do Google Drive

#### 4.3 Envio
```bash
# Criar rascunho
curl -X POST https://gmail.googleapis.com/gmail/v1/users/me/drafts \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"message": {...}}'

# Enviar
curl -X POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"id": "draft_id"}'
```

## Resultados Esperados

### Métricas de Sucesso
- **Taxa de Precisão:** >95% (bloqueia false positives)
- **Compatibilidade:** Score >15% para aplicação
- **Tempo de Resposta:** <5 minutos para processamento completo

### Exemplo de Output
```
✅ FASE 1: AUDITORIA DE MENSAGENS
✓ Total de grupos: 6
✓ Mensagens auditadas: 279
✓ Vagas encontradas: 1
✓ Taxa de precisão: 98.2%

✅ FASE 2: PROCESSAMENTO DA VAGA
✓ Vaga: Data Science - Thera Consulting
✓ Score: 18.7% (COMPATÍVEL)
✓ Email enviado: larissa.oliveira@theraconsulting.com.br
```

## Troubleshooting

### Problema: WAHA API 401 Unauthorized
**Solução:** Verificar chave API em secrets DB
```bash
sqlite3 /var/lib/eddie/secrets_agent/audit.db \
       "SELECT value FROM secrets WHERE key='waha_api_key';"
# Deve retornar: 757fae2686eb44479b9a34f1b62dbaf3 (base64 decoded)
```

### Problema: Sessão WAHA não existe
**Solução:** Executar setup_waha.py
```bash
python3 setup_waha.py
# Cria sessão "default" obrigatoriamente
```

### Problema: LLM retorna resposta vazia
**Solução:** Corrigir nome do modelo
```python
# Em apply_real_job.py
model = "llama3.2:3b"  # NÃO "llama3.2"
```

### Problema: Homelab offline
**Soluções:**
1. Wake-on-LAN: `etherwake d0:94:66:bb:c4:f6`
2. Aguardar ping: `ping 192.168.15.2`
3. Reboot manual se necessário

### Problema: Email não enviado
**Solução:** Verificar token Gmail
```bash
# Refresh token se expirado
python3 -c "
import google.auth.transport.requests
# ... refresh logic
"
```

## Monitoramento Contínuo

### Serviço Systemd
```bash
# Status do serviço
sudo systemctl status apply_real_job.service

# Logs
journalctl -u apply_real_job.service -f
```

### Logs de Auditoria
```bash
# No homelab
tail -f /home/homelab/message_audit_*.log
```

## Referências

- **Arquivos Principais:**
  - `apply_real_job.py`: Pipeline principal
  - `setup_waha.py`: Configuração WAHA
  - `WHATSAPP_BOT_README.md`: Docs WAHA

- **APIs:**
  - WAHA: https://waha.devlike.pro/
  - Gmail API: https://developers.google.com/gmail/api
  - Ollama: https://ollama.ai/

- **Dependências:**
  - python-docx, google-api-python-client, requests, ollama

## Histórico de Versões

- **v1.0:** Pipeline básico com DevOps skills
- **v2.0:** Currículo completo (104 skills), correções WAHA, error handling robusto

---

**Nota:** Este processo é totalmente automatizado após configuração inicial. O sistema monitora mensagens 24/7 e aplica automaticamente a vagas compatíveis.