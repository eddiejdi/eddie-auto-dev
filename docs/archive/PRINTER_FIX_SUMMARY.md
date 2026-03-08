# ⚠️ PROBLEMA IDENTIFICADO E CORRIGIDO

## 🔍 O que estava errado:

1. **Função não estava ATIVA** ❌
   - A função foi instalada mas `is_active = False`
   - Por isso não respondia quando você tentava usar

2. **Método errado no código** ❌
   - Estava usando `async def inlet()` 
   - Pipes precisam de `async def pipe()`
   
3. **Função não era Global** ❌
   - `is_global = False` significa que não aparece em todos os chats

## ✅ O que foi corrigido:

1. **Código da função reescrito:**
   - Mudado de `inlet()` para `pipe()`
   - Ajustado parsing de mensagens do chat
   - Corrigida extração de conteúdo do usuário

2. **Função reinstalada com correções**

3. **Ativação pendente** (último passo):
   - Precisa ser ativada manualmente na interface web

---

## 🎯 PRÓXIMOS PASSOS (MANUAL):

### 1. Acesse o Open WebUI
http://${HOMELAB_HOST}:8002
### 2. Vá para Settings (⚙️ canto superior direito)

### 3. Clique em "Admin Panel" → "Functions"

### 4. Procure por "🖨️ Impressora de Etiquetas"

### 5. Clique no botão de **toggle** (switch) para ATIVAR

### 6. (Opcional) Marque como "Global" se disponível

### 7. Salve as alterações

### 8. Teste em qualquer chat:
Imprima uma etiqueta com o texto: TESTE 123
---

## 🔧 Alternativa: Ativar via API (se interface não funcionar)

Execute este comando no servidor:

```bash
ssh homelab@${HOMELAB_HOST}

TOKEN=$(curl -s http://127.0.0.1:8002/api/v1/auths/signin \
  -H "Content-Type: application/json" \
   -d '{"email":"edenilson.teixeira@rpa4all.com","password":"Shared@2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Obter função atual
curl -s "http://127.0.0.1:8002/api/v1/functions/printer_etiqueta" \
  -H "Authorization: Bearer $TOKEN" > /tmp/func.json

# Modificar e atualizar
python3 << EOF
import json
with open('/tmp/func.json', 'r') as f:
    func = json.load(f)
func['is_active'] = True
func['is_global'] = True
with open('/tmp/func_update.json', 'w') as f:
    json.dump(func, f)
EOF

# Enviar update
curl -X POST "http://127.0.0.1:8002/api/v1/functions/id/printer_etiqueta/update" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/func_update.json

echo "✅ Função ativada!"
---

## 📝 Arquivos Atualizados:

- ✅ `/home/homelab/agents_workspace/openwebui_printer_function.py` (código corrigido)
- ✅ `/home/homelab/agents_workspace/reinstall_printer_function.py` (script de reinstalação)

---

## 🧪 Como Testar:

### Teste 1: Texto simples
Imprima TESTE
### Teste 2: Com validação
```json
{"action": "print", "content": "ETIQUETA TESTE", "validate_only": true}
### Teste 3: Imprimir de verdade
Imprima uma etiqueta com: PEDIDO #123
---

## ⚠️ Observação Importante:

A função agora está com o código CORRETO, mas precisa ser **ativada manualmente** 
na interface do Open WebUI porque a API não permite ativar via POST/create.

**Versão:** 1.1 (Corrigida)  
**Data:** 3 de fevereiro de 2026  
**Status:** Aguardando ativação manual
