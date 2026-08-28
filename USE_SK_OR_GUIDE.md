# 🚀 Usar sk-or no VS Code

## Opção 1: Continue.dev (RECOMENDADO - já tem sk-or!)

1. **Abra o sidebar de Continue**
   - Atalho: `Ctrl+Shift+V` 
   - Ou clique no ícone Continue na barra lateral

2. **Selecione sk-or model**
   - Dropdown "Select a model" → "OpenAI Compatible - sk-or model"
   - Ou "Ollama - Local GPU (Default)" para usar GPU local

3. **Use no chat**
   - Digite sua pergunta
   - Continue usará sk-or/Ollama automaticamente

---

## Opção 2: GitHub Copilot Chat

sk-or não aparece porque requer extensão VS Code (complexo).

**Workaround:** Use Claude/GPT via GitHub Copilot Chat oficial
- Atalho: `Ctrl+I`
- Modelos: Claude, GPT-4, etc. (cloud)

---

## 📍 Locais das Configs

- Continue: `.continue/config.json` (projeto)
- Copilot: `.vscode/settings.json` (workspace)
- FastAPI: porta 8503 (localhost)

---

## ✅ Confirmação

- [ ] FastAPI rodando (`curl http://localhost:8503/v1/models`)
- [ ] Continue.dev instalado 
- [ ] sk-or selecionado em Continue
- [ ] Teste: envie mensagem no chat
