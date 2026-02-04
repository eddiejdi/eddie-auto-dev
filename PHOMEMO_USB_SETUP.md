# Como Conectar e Imprimir com Phomemo Q30 via USB no Servidor

## 📊 Situação Atual
- ✅ Software 100% completo (função Open WebUI criada, ativada, global)
- ✅ Código correto com suporte a USB e Bluetooth
- ✅ Todas as dependências instaladas (pyserial, Pillow)
- ⏳ **AGUARDANDO**: Conectar impressora Phomemo Q30 via USB no servidor

---

## 🔧 Passo 1: Conectar Phomemo Q30 via USB no Servidor

### No Servidor (homelab@192.168.15.2)

1. **Conecte a Phomemo Q30 ao cabo USB**
   ```bash
   # A impressora deve estar conectada via USB
   # Verifique fisicamente a conexão USB ao servidor
   ```

2. **Verifique se aparece em lsusb:**
   ```bash
   ssh homelab@192.168.15.2
   lsusb | grep -i phomemo
   # OU
   lsusb | grep 2e8d  # VID comum da Phomemo
   ```

3. **Procure pela porta serial da impressora:**
   ```bash
   ls -la /dev/ttyUSB*
   # Comum: /dev/ttyUSB0, /dev/ttyUSB1, etc
   ```

   **OU**
   
   ```bash
   dmesg | tail -50 | grep -i usb
   # Procure por mensagens do kernel sobre novo dispositivo USB
   ```

---

## 🔍 Passo 2: Identificar a Porta Correta

### Método Automático (Python)
```bash
ssh homelab@192.168.15.2 'python3 /app/phomemo_print.py --list'
```

**Esperado:**
```
/dev/ttyUSB0 - USB Serial Device
/dev/ttyUSB1 - n/a
...
```

### Método Manual
```bash
# No servidor:
for port in /dev/ttyUSB*; do
    echo "Testando $port..."
    echo -e '\x1b@TESTE\n\n\x0c' > "$port" 2>/dev/null && echo "✅ Resposta de $port" || echo "❌ Erro em $port"
done
```

---

## 🖨️ Passo 3: Testar Impressão via CLI

### Teste 1: Usando o script diretamente
```bash
ssh homelab@192.168.15.2
python3 /app/phomemo_print.py --text "TESTE 123"
```

**Esperado:**
```
Conectando-se à porta /dev/ttyUSB0 (baud=9600)
Imprimindo texto simples
Trabalho enviado!
```

### Teste 2: Especificar porta manualmente
```bash
ssh homelab@192.168.15.2
python3 /app/phomemo_print.py --port /dev/ttyUSB0 --text "TESTE COM PORTA"
```

### Teste 3: Testar com imagem
```bash
# Criar teste simples
ssh homelab@192.168.15.2 << 'EOF'
python3 -c "
from PIL import Image, ImageDraw
img = Image.new('1', (384, 300), color='white')
draw = ImageDraw.Draw(img)
draw.text((50, 100), 'TESTE IMAGEM', fill='black')
img.save('/tmp/test_label.png')
"
python3 /app/phomemo_print.py --image /tmp/test_label.png
EOF
```

---

## 💬 Passo 4: Testar via Open WebUI

1. **Acesse Open WebUI:**
   ```
   http://192.168.15.2:8002
   ```

2. **No chat, diga:**
   ```
   Imprima: Teste de Conexão USB
   ```

3. **Ou simplesmente:**
   ```
   Imprima TESTE
   ```

4. **Esperado:**
   - ✅ Chat responde: "✅ Impresso com sucesso!"
   - 🖨️ Phomemo imprime a etiqueta

---

## ⚠️ Solução de Problemas

### Erro: "Nenhuma porta serial compatível com o Phomemo foi encontrada"

**Causas possíveis:**
1. ❌ Phomemo não conectada via USB
2. ❌ Driver USB-Serial não instalado no servidor
3. ❌ Permissões insuficientes em `/dev/ttyUSB*`

**Soluções:**

```bash
# 1. Verificar conexão física
ssh homelab@192.168.15.2 'lsusb'

# 2. Instalar drivers (se necessário)
ssh homelab@192.168.15.2 'sudo apt-get update && sudo apt-get install -y brltty'
# brltty pode ocupar /dev/ttyUSB* - desinstale se houver conflito

# 3. Dar permissões
ssh homelab@192.168.15.2 'sudo usermod -aG dialout $USER && sudo systemctl restart'

# 4. Listar todas as portas
ssh homelab@192.168.15.2 'python3 /app/phomemo_print.py --list'
```

### Erro: "Permission denied" em /dev/ttyUSB*

```bash
# No servidor:
sudo chmod 666 /dev/ttyUSB0
# OU adicionar ao grupo dialout
sudo usermod -aG dialout homelab
```

### Impressora conectada mas não imprime

```bash
# Testar comunicação serial:
ssh homelab@192.168.15.2 << 'EOF'
python3 << 'PY'
import serial
ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
ser.write(b'\x1b@')  # Reset ESC/POS
ser.write(b'TESTE\n\n')
ser.write(b'\x0c')  # Form feed
ser.close()
print("Comando enviado!")
PY
EOF
```

---

## 📝 Resumo do Workflow

```
┌─────────────────────────────────────┐
│  1. Conectar Phomemo via USB        │
│     ao servidor homelab             │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  2. Identificar porta (/dev/ttyUSB0)│
│     com: ls /dev/ttyUSB*            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  3. Testar CLI:                     │
│     python3 /app/phomemo_print.py   │
│     --text "TESTE"                  │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  4. Testar Open WebUI:              │
│     Diga "Imprima TESTE"            │
│     no chat                         │
└──────────────┬──────────────────────┘
               ↓
        ✅ FUNCIONAL!
```

---

## 🔗 Arquivos Relevantes

- **Código da Phomemo:** `/app/phomemo_print.py` (no container)
- **Função Open WebUI:** Ativa em `printer_etiqueta`
- **Diagnóstico:** `python3 diagnose_phomemo_connection.py --all --test`
- **Guia anterior:** Este documento

---

## 📞 Próximos Passos

1. ✅ Conecte a Phomemo Q30 via USB no servidor
2. ✅ Verifique com `ls /dev/ttyUSB*`
3. ✅ Teste com `python3 /app/phomemo_print.py --text "TESTE"`
4. ✅ Se funcionar, teste no Open WebUI
5. ✅ Se não funcionar, siga a seção "Solução de Problemas"

**Status:** Aguardando conexão USB da impressora! 🖨️
