# 📋 RESUMO DO PROJETO - HABILITAR GPU NO HOMELAB

**Data:** 26/02/2026  
**Objetivo:** Aumentar performance do LLM shared-whatsapp:latest de ~0.5 tokens/s para ~5-10 tokens/s

---

## 📁 Arquivos Criados

### 1. **HOMELAB_HARDWARE_ANALYSIS.md** ✅
- Análise completa do seu computador (i9-9900T + H370 + RTX 2060)
- Especificações técnicas detalhadas
- Compatibilidade PCIe NVMe com adaptadores
- Roadmap de upgrades futuros

### 2. **GPU_INSTALLATION_GUIDE.md** ✅
- **Instruções passo-a-passo** para instalar drivers NVIDIA
- Solução automatizada (fácil)
- Solução manual (em caso de problemas)
- Troubleshooting completo
- Validação se funcionou

### 3. **install_nvidia_cuda.sh** ✅
- Script bash para instalação automática
- Já copiado para `/tmp/` no homelab
- Pronto para executar

### 4. **measure_ollama_latency.py** ✅
- Script para medir performance do LLM
- Testa antes vs depois da instalação

---

## 🎯 Próximos Passos (Para Você Executar)

### PASSO 1: Ler o Guide
```bash
# Leia em seu navegador ou terminal:
cat GPU_INSTALLATION_GUIDE.md
```

### PASSO 2: Escolher Método de Instalação

**Opção A (Recomendada):** Instalação Automática
```bash
# No homelab via SSH:
ssh homelab@192.168.15.2
sudo bash /tmp/install_nvidia_cuda.sh
```

**Opção B:** Instalação Manual
```bash
# Siga os passos em GPU_INSTALLATION_GUIDE.md
# Copie e cole cada comando no terminal homelab
```

### PASSO 3: Validar Instalação
```bash
# Dentro do homelab:
nvidia-smi
# Deve mostrar: GeForce RTX 2060 SUPER

curl -s http://localhost:11434/api/ps | python3 -m json.tool
# Deve mostrar: "size_vram": 6000
```

### PASSO 4: Medir Performance (Após GPU ativa)
```bash
# Localmente (seu computador):
python3 measure_ollama_latency.py
# Esperado: 5-10 tokens/s (comparado aos 0.5 atuais)
```

---

## ⚡ Status Atual vs Esperado

| Métrica | Atual (CPU) | Esperado (GPU) | Melhoria |
|---------|-------------|---|----------|
| **Tokens/seg** | 0.5-1.0 | 5-10 | ✅ 10x |
| **Latência prompt curto** | 20-30s | 2-5s | ✅ 6-10x |
| **CPU Load** | 516% | 5-10% | ✅ 50x menos |
| **Temperatura** | Normal | Mais baixa | ✅ Melhor |

---

## 📊 Resumo Técnico

```
Hardware Disponível:
├── CPU: Intel i9-9900T (8 cores @ 2.1GHz) ✅
├── RAM: 31 GB DDR4-2666 ✅
├── GPU: NVIDIA RTX 2060 SUPER (6GB VRAM) ❌ [Detectada mas inativa]
├── Drivers NVIDIA: Não instalados ❌
└── CUDA Toolkit: Não instalado ❌

Após Instalação:
├── ✅ nvidia-driver-545 (ou 550)
├── ✅ CUDA Toolkit 12.x
├── ✅ Ollama configurado para CUDA
└── ✅ Performance 10x+ melhor
```

---

## 🔗 Arquivos de Referência

```
/home/edenilson/shared-auto-dev/
├── HOMELAB_HARDWARE_ANALYSIS.md      ← Análise técnica
├── GPU_INSTALLATION_GUIDE.md         ← Instruções de instalação
├── install_nvidia_cuda.sh             ← Script automático
├── measure_ollama_latency.py          ← Teste de performance
├── HOMELAB_HARDWARE_ANALYSIS.md      ← Análise de compatibilidade
└── measure_whatsapp_llm_latency.py   ← Teste anterior (referência)
```

---

## ⚠️ Cuidados Importantes

1. **Backup:** Nenhum arquivo crítico será alterado
2. **Reboot:** Sistema pode reiniciar durante instalação
3. **Tempo:** Mais de 20-30 minutos esperado
4. **Sudo:** Pode pedir senha durante `sudo apt`
5. **Conexão:** Mantenha SSH conectado durante installação

---

## 🚀 TL;DR (Resumo Executivo)

```bash
# Execute NO homelab:
ssh homelab@192.168.15.2

# Instalação automática:
sudo bash /tmp/install_nvidia_cuda.sh

# Aguarde ~30 min, sistema pode reiniciar
# Teste:
nvidia-smi

# De volta no seu PC:
python3 measure_ollama_latency.py
# Antes: 0.5 tokens/s
# Depois: 5-10 tokens/s ✅
```

---

**Status:** ✅ Tudo pronto para execução!  
**Próximo passo:** Ler `GPU_INSTALLATION_GUIDE.md` e executar instalação
