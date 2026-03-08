# Solução: Erro OSError no Pyodide

## Problema Reportado
OSError: [Errno 29] I/O error
Erro ao executar código Python no IDE em `http://localhost:8080`.

## Causa Raiz

1. **Code Runner não estava acessível** da máquina local (porta 2000 timeouts)
2. **IDE caía para Pyodide** (WebAssembly) como fallback
3. **Pyodide não suporta operações I/O** seguramente, causando o erro

## Solução Implementada

### 1. Atualizar `site/ide.js`

✅ **Desabilitado Pyodide** como fallback inseguro
- Removido `runCodePyodide()` que causava erros
- Força uso do backend via `/code/run`
- Melhorado tratamento de erros com mensagens claras

✅ **Melhorado `checkBackend()`**
- Verifica 3 endpoints em ordem: API Pública > API Local > Code Runner Direto
- Registra qual backend está disponível
- Define `backendAvailable` flag antes de permitir execução

✅ **Erro explícito se backend indisponível**
```javascript
if (!backendAvailable) {
  throw new Error('🔴 Backend não disponível. Verifique a conexão com o servidor.\n\nTente:\n1. Verificar se http://${HOMELAB_HOST}:2000 está acessível\n2. Recarregar a página\n3. Contatar suporte...');
}
### 2. Atualizar `specialized_agents/api.py`

✅ **Endpoints agora disponíveis:**
- `POST /code/run` - Executa código Python via Code Runner
- `GET /code/runtimes` - Lista runtimes disponíveis
- `POST /code/generate` - Gera código com IA (single request)
- `POST /code/generate-stream` - Gera código com streaming

### 3. Sincronizar com Servidor

```bash
git add -A
git commit -m "fix: API endpoints for code execution"
git push origin main

# No servidor:
ssh homelab@${HOMELAB_HOST}
cd /home/homelab/shared-auto-dev
git pull
sudo systemctl restart specialized-agents-api
## Validação

✅ Code Runner health: `http://${HOMELAB_HOST}:2000/health`
```json
{
  "max_execution_time": 30,
  "max_memory_mb": 512,
  "service": "rpa4all-code-runner",
  "status": "healthy",
  "version": "1.0.0"
}
✅ API `/code/run` endpoint:
```bash
curl -X POST http://${HOMELAB_HOST}:8503/code/run \
  -H 'Content-Type: application/json' \
  -d '{"code":"print(\"OK\")","language":"python"}'

# Response:
{
  "success": true,
  "stdout": "OK\n",
  "stderr": "",
  "exit_code": 0,
  "language": "python",
  "version": "3.11"
}
✅ Pandas execution:
import pandas as pd
data = {'A': [1,2,3], 'B': [4,5,6]}
df = pd.DataFrame(data)
print(df)
# Output: 3 linhas x 2 colunas ✅
## Próximos Passos

### 1. **Testar Frontend** (Imediato)
- Acessar `http://localhost:8080` (ou `http://${HOMELAB_HOST}/ide`)
- Clicar em "Executar"
- Deve conectar ao servidor e executar sem erro Pyodide

### 2. **Deploy para Produção** (Hoje)
```bash
# Fazer push do IDE atualizado
git push origin main

# Sincronizar site no servidor
rsync -av site/ homelab@${HOMELAB_HOST}:/path/to/web/root/

# Ou via Git no servidor:
cd /home/homelab/webb && git pull
### 3. **Adicionar Logs de Debug** (Opcional)
```javascript
// Em site/ide.js, na função checkBackend()
console.log(`✅ Backend disponível: ${name} (${url})`);
console.log(`❌ ${name} não disponível: ${e.message}`);
### 4. **Melhorar Feedback Viusal** (Futuro)
- Mostrar statusbar com "✅ Servidor Conectado / ❌ Desconectado"
- Adicionar retry automático com exponential backoff
- Implementar health check periódico

## Arquivos Modificados

1. `site/ide.js` - Removido Pyodide fallback, melhorado erro handling
2. `specialized_agents/api.py` - (Já tinha endpoints, apenas sincronizado)
3. Commit: `3a40a52` - Fix: API endpoints for code execution

## Linha de Comando para Testar

```bash
# Terminal 1: Iniciar IDE local se não estiver rodando
cd /home/edenilson/shared-auto-dev/site
python3 -m http.server 8080

# Terminal 2: Testar backend está acessível
curl -s http://${HOMELAB_HOST}:8503/health

# Terminal 3: Abrir navegador
open http://localhost:8080
# Ou:
firefox http://localhost:8080
## Observações de Segurança

⚠️ **Por que Pyodide foi desabilitado:**
- Pyodide não tem acesso seguro ao sistema de arquivos
- Algumas bibliotecas (paramiko, requests) não funcionam em WASM
- Backend (Code Runner) fornece isolamento verdadeiro via Docker

✅ **Alternativa segura:**
- Code Runner em Docker isolado com timeouts e memory limits
- Suporta todas as bibliotecas Python
- Pode ser escalado horizontalmente

## Referências

- Code Runner: `site/code_runner/app.py`
- Client: `specialized_agents/code_runner_client.py`
- API Spec: `specialized_agents/api.py` linhas 698-727
