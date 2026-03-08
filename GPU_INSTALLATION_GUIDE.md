# 🚀 INSTRUÇÕES PARA HABILITAR GPU NVIDIA (RTX 2060) NO HOMELAB

## ⚠️ IMPORTANTE
Este processo requer acesso SSH ao homelab e pode levar **20-40 minutos** dependendo da velocidade da internet. Pode ser necessário reiniciar o sistema.

---

## 🔧 SOLUÇÃO RÁPIDA (Recomendada)

### Opção A: Instalação Automatizada (Mais fácil)

```bash
# 1. Execute localmente (seu computador):
scp /home/edenilson/shared-auto-dev/install_nvidia_cuda.sh homelab@192.168.15.2:/tmp/
ssh homelab@192.168.15.2

# 2. Execute no homelab (como homelab user):
sudo bash /tmp/install_nvidia_cuda.sh

# 3. Aguarde a conclusão (pode levar 15-30 min)
# O script mostrará "✅ INSTALLATION COMPLETE" quando terminar

# 4. Se pedido para reiniciar:
sudo reboot
```

---

## 🔨 SOLUÇÃO MANUAL (Se o automatizado não funcionar)

Execute estes comandos **no homelab** (via SSH):

### Passo 1: Atualizar sistema
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y build-essential linux-headers-$(uname -r) dkms
```

### Passo 2: Instalar drivers NVIDIA
```bash
# Tente driver 545 (recomendado para RTX 2060):
sudo apt install -y nvidia-driver-545

# Se não funcionar, tente o 550:
sudo apt install -y nvidia-driver-550

# Se nenhum funcionar, tente o mais recente:
sudo apt install -y nvidia-driver-latest-dkms
```

### Passo 3: Instalar CUDA Toolkit
```bash
sudo apt install -y nvidia-cuda-toolkit
```

### Passo 4: Criar configuração Ollama
```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
```

```bash
sudo tee /etc/systemd/system/ollama.service.d/cuda.conf > /dev/null <<'EOF'
# Enable CUDA GPU acceleration for Ollama
[Service]
Environment="PATH=/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="CUDA_HOME=/usr/local/cuda"
Environment="OLLAMA_GPU_MEMORY=6000"
EOF
```

### Passo 5: Recarregar și reiniciar Ollama
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### Passo 6: Verificar se funcionou
```bash
nvidia-smi
```

**Esperado:** Deve mostrar a RTX 2060 SUPER

```bash
curl -s http://localhost:11434/api/ps | python3 -m json.tool | head -20
```

**Esperado:** `"size_vram": 6000` (ou similar, mostrando GPU em uso)

---

## ⚠️ SOLUÇÃO DE PROBLEMAS

### nvidia-smi retorna "No devices found"

**Causa 1: Drivers não instalados/incompatíveis**
```bash
# Tente reinstalar:
sudo apt install --reinstall nvidia-driver-545
sudo reboot  # Reiniciar é importante!
```

**Causa 2: GPU desabilitada no BIOS**
```bash
# Verifique via SSH (lista PCIe):
lspci | grep NVIDIA

# Deve mostrar: "02:00.0 VGA compatible controller: NVIDIA"
# Se mostrar, o hardware está OK
```

**Causa 3: Kernel modules não compilados (DKMS)**
```bash
# Verifique status:
sudo dkms status

# Se houver erros, recompile:
sudo dkms install nvidia/545 -k $(uname -r)
sudo reboot
```

---

## ✅ COMO VALIDAR QUE FUNCIONOU

### 1. Drivers instalados?
```bash
ssh homelab@192.168.15.2 "nvidia-smi"
```

Deve aparecer:
```
+-------------------------------+
| NVIDIA-SMI 545.xx             |
| Driver Version: 545.xx        |
+-------------------------------+
| GPU  Name        Persistence| 
| 0  GeForce RTX 2060 SUPER   |
+-------------------------------+
```

### 2. CUDA disponível?
```bash
ssh homelab@192.168.15.2 "/usr/local/cuda/bin/nvcc --version"
```

### 3. Ollama usando GPU?
```bash
ssh homelab@192.168.15.2 "curl -s http://localhost:11434/api/ps | python3 -m json.tool"
```

Procure por `"size_vram": 6000` ou similar

### 4. Performance melhorou?
```bash
python3 measure_ollama_latency.py
```

**Antes (CPU):** ~0.5-2 tokens/seg  
**Depois (GPU):** ~5-10 tokens/seg

---

## 📊 Resultados Esperados

| Aspecto | Sem GPU | Com GPU |
|---------|---------|---------|
| **Latência** | 30-60s | 3-8s |
| **Tokens/s** | 0.5-1 | 5-10 |
| **CPU Load** | 516% | 5-10% |
| **MHz** | ~2000 | ~1500 |

---

## 🆘 Ainda não funciona?

Se após all steps nvidia-smi ainda mostra "No devices found":

1. **Reiniciar o sistema:**
   ```bash
   ssh homelab@192.168.15.2 "sudo reboot"
   # Aguarde 2 minutos, depois teste de novo
   ```

2. **Remover e reinstalar from scratch:**
   ```bash
   ssh homelab@192.168.15.2 "sudo apt purge nvidia* -y && sudo apt install -y nvidia-driver-545"
   ```

3. **Verificar BIOS:**
   - Acesse BIOS do homelab (enter durante boot)
   - Procure por "PCIe GPU" ou "Display"
   - Certifique que está enabled

4. **Contato técnico:**
   - Se BIOS mostra RTX 2060 OK mas drivers não, pode ser problema de firmware
   - Considerar downgrade para driver 470 ou 495

---

## 📝 Comandos Rápidos (Copy-Paste)

Execute **no homelab via SSH:**

```bash
# One-liner para toda instalação:
sudo bash -c '
apt update &&\
apt install -y build-essential linux-headers-$(uname -r) dkms nvidia-driver-545 nvidia-cuda-toolkit &&\
mkdir -p /etc/systemd/system/ollama.service.d &&\
tee /etc/systemd/system/ollama.service.d/cuda.conf <<EOF
[Service]
Environment="PATH=/usr/local/cuda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu"
Environment="CUDA_VISIBLE_DEVICES=0"
Environment="CUDA_HOME=/usr/local/cuda"
Environment="OLLAMA_GPU_MEMORY=6000"
EOF
systemctl daemon-reload &&\
systemctl restart ollama &&\
echo "✅ Instalação completa! Reiniciando..." &&\
sleep 2 &&\
reboot
'
```

---

🎯 **Próximo Passo:** Após reiniciar, execute `nvidia-smi` para confirmar!
