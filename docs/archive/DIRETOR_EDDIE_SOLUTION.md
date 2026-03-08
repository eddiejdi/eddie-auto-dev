# Solução para Diretor Shared no Open WebUI

## Problema
A função `director_eddie` (tipo pipe) não aparece como modelo no Open WebUI, mesmo após:
- Criar a função corretamente
- Criar o modelo interno correspondente
- Fazer reload das funções

## Causa Raiz
O Open WebUI parece precisar de um **restart completo** para que novas funções pipe sejam reconhecidas como modelos. O `agent_coordinator` funciona porque foi criado quando o Open WebUI foi iniciado/reiniciado.

## Soluções Implementadas

### Solução 1: System Prompt no Modelo Ollama (ATIVA)
O modelo `diretor-shared` (baseado em qwen2.5-coder:7b) foi configurado com um system prompt completo que:
- Define as 10 regras do sistema
- Lista a equipe de agents
- Explica os comandos disponíveis
- Instrui o modelo a responder como Diretor

**Comandos disponíveis:**
- `/diretor <instrução>` - Executa como Diretor
- `/equipe` - Mostra status da equipe
- `/regras` - Lista as regras do sistema
- `/pipeline <tarefa>` - Executa pipeline completo
- `/delegar <agent> <tarefa>` - Delega para agent específico
- `/status` - Status geral do sistema
- `/autocoinbot` ou `/acb` - Relatório do AutoCoinBot

### Solução 2: Reiniciar Open WebUI (PENDENTE)
Para que a função pipe apareça como modelo, é necessário:
```bash
# No servidor ${HOMELAB_HOST}
docker restart open-webui
Após o restart, `director_eddie` deverá aparecer como modelo com `owned_by: openai`.

## Arquivos Criados
- `openwebui_director_function.py` - Código da função pipe
- `configure_diretor_model.py` - Script para configurar system prompt
- `DIRETOR_EDDIE_SOLUTION.md` - Este arquivo

## Como Testar
1. Acesse http://${HOMELAB_HOST}:3000
2. Selecione o modelo "👔 Diretor Shared"
3. Envie `/equipe` ou `/regras`
4. O modelo deve responder como Diretor

## Status
- ✅ Função `director_eddie` criada e ativa
- ✅ Modelo interno criado
- ✅ System prompt configurado no modelo Ollama
- ⏳ Aguardando restart do Open WebUI para função pipe aparecer como modelo
