# sk-or em Visual Studio Enterprise

## Seu Cenário Atual: Linux LMDE

**Visual Studio Enterprise NÃO roda em Linux.**

### ✅ Solução Imediata (AGORA):

**Continue.dev** no VS Code (Linux):
```bash
# 1. Abra VS Code
code /workspace/eddie-auto-dev

# 2. Abra Continue
Ctrl+Shift+V

# 3. Selecione sk-or
dropdown → "OpenAI Compatible - sk-or model"

# 4. Chat com sk-or ativo
```

---

## Se Quiser Visual Studio Enterprise:

### Opção A: VM Windows (Recomendado)

**No homelab 192.168.15.2:**

```bash
# 1. Criar VM Windows
virsh create /home/homelab/vms/windows-vs-enterprise.xml

# 2. Instalar Visual Studio Enterprise
# Baixar: https://visualstudio.microsoft.com/downloads/
# Ativar com chave: [sua chave real]

# 3. Instalar Continue.dev extension
# Extensões → Continue

# 4. Configurar config.json
~/.continue/config.json
```

**Endpoints sk-or na VM:**
```json
{
  "models": [
    {
      "title": "sk-or v1",
      "provider": "openrouter",
      "model": "sk-or-v1-...",
      "apiBase": "https://openrouter.ai/api/v1"
    }
  ]
}
```

### Opção B: Remote SSH (Simples)

**No VS Enterprise Windows:**
- Instalar: "Remote - SSH" extension
- Conectar: `homelab@192.168.15.2`
- Abrir: `/workspace/eddie-auto-dev`
- Continue.dev usa sk-or remotamente

---

## Comparação

| IDE | OS | sk-or | Recomendação |
|-----|-----|------|------|
| VS Code | Linux ✅ | Continue.dev ✅ | **USE AGORA** |
| VS Code | Windows | Continue.dev ✅ | Ótimo |
| VS Enterprise | Windows | Continue.dev ✅ | Funciona, pesado |
| VS Enterprise | Linux | ❌ | Impossível |

---

## ⚡ Próximo Passo

1. **Agora**: `Ctrl+Shift+V` no VS Code → selecione sk-or
2. **Depois** (opcional): Setup VS Enterprise em VM se precisar

sk-or está **100% funcional em Continue.dev no seu Linux**.
