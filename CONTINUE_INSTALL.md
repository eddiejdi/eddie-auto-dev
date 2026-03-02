# 🎯 CONTINUE.DEV — Instalação Passo a Passo

## Fase 1️⃣: Instalação (2-3 minutos)

### VS Code
```
┌─────────────────────────────────────────────┐
│ [ ] 1. Abra VS Code                          │
│ [ ] 2. Ctrl+Shift+X (Extensões)              │
│ [ ] 3. Pesquise: continue                    │
│ [ ] 4. Clique em "Continue"                  │
│ [ ] 5. Clique em "Install"                   │
│ [ ] 6. Espere completar                      │
│ [ ] 7. Clique em "Reload" (se aparecer)      │
│                                              │
│ ✅ Pronto! Extensão instalada.               │
└─────────────────────────────────────────────┘
```

### PyCharm
```
┌─────────────────────────────────────────────┐
│ [ ] 1. Abra PyCharm                          │
│ [ ] 2. Settings → Plugins (Cmd+,)            │
│ [ ] 3. Clique em "Marketplace"               │
│ [ ] 4. Pesquise: continue                    │
│ [ ] 5. Clique em "Continue" →  "Install"     │
│ [ ] 6. Espere completar                      │
│ [ ] 7. Clique em "Restart IDE" (se pedir)    │
│                                              │
│ ✅ Pronto! Plugin instalado.                 │
└─────────────────────────────────────────────┘
```

---

## Fase 2️⃣: Verificação (1 minuto)

### Verificar Config
```bash
# Verifique se config existe
ls ~/.continue/config.yaml

# Deve retornar: /home/edenilson/.continue/config.yaml
```

### Verifique Ollama
```bash
# Na máquina homelab
ssh homelab@192.168.15.2
curl http://localhost:11434/api/tags

# Deve retornar lista de modelos (qwen3:*, qwen2.5-coder, etc.)
```

---

## Fase 3️⃣: Teste imediato (30 segundos)

### VS Code Test
```
1. Pressione: Ctrl+Shift+V (abre Continue)
2. Na caixa de chat, tipo: /health
3. Aperte Enter

ESPERADO:
"System Status:
 • CPU: 45% (4 cores)
 • RAM: 12 GB / 16 GB
 • Disk: 50 GB / 200 GB
 • Uptime: 42 dias"

❌ Se receber instruções de texto: veja troubleshooting
```

### PyCharm Test
```
1. Vá em: Tools → Continue (lado direito da IDE)
2. Na caixa de chat, tipo: /health
3. Aperte Enter

ESPERADO: Mesmo resultado VS Code acima
```

---

## 📊 Checklist de Funcionalidade

Após testes, execute isto em ambas IDEs:

```bash
Teste 1 - System Info
Pergunta: "/health"
Esperado: CPU/RAM/Disk/Uptime (números reais)

Teste 2 - File Read
Pergunta: "mostra as primeiras 5 linhas de ~/.bashrc"
Esperado: Conteúdo real do arquivo (não instruções)

Teste 3 - Docker (se instalado)
Pergunta: "quais containers docker estão rodando?"
Esperado: Lista de docker ps (CONTAINER ID, IMAGE, STATUS)

Teste 4 - Command (qualquer)
Pergunta: "qual é a versão do Python instalada?"
Esperado: Python X.X.X (saída real de python --version)
```

Marque conforme funciona:
- [ ] Teste 1 — /health ✅
- [ ] Teste 2 — file read ✅
- [ ] Teste 3 — docker ✅
- [ ] Teste 4 — Python version ✅

---

## 🚨 Problemas Comuns

| Problema | Solução |
|----------|---------|
| **"API não respondeu"** | `bash setup_continue.sh` (rerun setup) |
| **"Ollama offline"** | SSH: `ssh homelab@192.168.15.2 "systemctl status ollama"` |
| **Continue não aparece** | Restart IDE (Cmd+Q ou File → Exit, reabra) |
| **Comando não executa** | Verifique em Tools → Logs se há erro API |
| **Port 8503 já em uso** | `lsof -i :8503` e depois `kill -9 <PID>` |

---

## ✅ Status Atual

```
[✅] Ollama         → Rodando em 192.168.15.2:11434
[✅] API Tools      → Configurado para localhost:8503
[✅] VS Code Config → Criado em ~/.continue/config.yaml
[✅] PyCharm Config → Criado em ~/.idea/continue/config.yaml
[⏳] Seu teste      → Aguardando você executar Fase 3
```

---

## 📚 Documentação Relacionada

| Arquivo | Propósito | Tempo |
|---------|-----------|-------|
| [CONTINUE_README.md](CONTINUE_README.md) | Resumo executivo | 5 min |
| [CONTINUE_QUICKSTART.md](CONTINUE_QUICKSTART.md) | Exemplos práticos | 10 min |
| [CONTINUE_SETUP.md](CONTINUE_SETUP.md) | Setup detalhado | 20 min |
| [docs/LLM_TOOL_CALLING.md](docs/LLM_TOOL_CALLING.md) | Arquitetura completa | 30 min |

---

## 🎁 Dica Pro

Depois de instalar, experimente os slash commands:

```yaml
Comandos disponíveis:
  /health    → CPU/RAM/Disk/Uptime
  /docker    → docker ps (containers)
  /logs      → Últimos 10 logs do sistema
  /git       → Status git do projeto
  /btc       → Status do BTC trading agent
```

Tipo simplesmente `/@docker` e Continue completa automaticamente!

---

## 🎯 Objetivo Final

Depois de completar tudo:

✅ **VS Code** executa comandos via `Ctrl+Shift+V` + Continue
✅ **PyCharm** executa comandos via `Tools → Continue`
✅ **Sem instruções de texto** — Resultados reais
✅ **Comandos agendados** — Docker, git, logs, system info
✅ **Seguro** — Whitelist + Path restrictions

---

## 💬 Próxima Ação

👉 **Siga as 3 fases acima** (5 minutos no total)

Depois que confirmar que `/health` funciona, estará pronto! 🎉

---

**Última atualização**: 2026-02-27  
**Status**: ✅ Ready for user testing  
**Tempo estimado**: 5 minutos (instalação + teste)  
**Próximo**: Leia [CONTINUE_README.md](CONTINUE_README.md)
