# Phomemo Q30 USB - Informações Técnicas Completas

## 📌 Resumo Executivo

**Você quer:** Impressora Phomemo Q30 funcionar via USB no servidor e integrada ao Open WebUI através de chat.

**Situação:** 
- ✅ Software 100% pronto
- ⏳ Aguardando conexão USB da impressora

---

## ✅ O que já foi concluído:

### 1. Função Open WebUI criada e ativada
- Nome: `printer_etiqueta`
- Status: **ATIVO e GLOBAL** ✅
- Aparece no menu de seleção

### 2. Código atualizado para detectar USB + Bluetooth
- Procura por: `"PHOMEMO"` na descrição/fabricante
- Também procura por: VID `2e8d` (USB ID da Phomemo)
- Suporta: `/dev/ttyUSB*`, `/dev/ttyACM*`, `/dev/rfcomm*`

### 3. Dependências instaladas no container
- `pyserial` (para comunicação serial)
- `Pillow` (para processamento de imagens)

### 4. Arquivo correto no lugar certo
- Localização: `/app/phomemo_print.py` (dentro container)
- Protocolo: ESC/POS sobre serial
- Baudrate: 9600 bps

### 5. Ferramentas de diagnóstico criadas
- `diagnose_phomemo_connection.py`
- `check_phomemo_server.py`
- `PHOMEMO_USB_SETUP.md` (guia completo)

---

## 🔧 O que fazer agora:

### **PASSO 1: Conectar a Phomemo Q30 via USB no servidor**

Conecte a Phomemo Q30 via cabo USB na máquina `homelab@192.168.15.2`

### **PASSO 2: Verificar detecção**

```bash
ssh homelab@192.168.15.2
lsusb | grep -E "phomemo|2e8d"
```

Esperado: Algo como `2e8d:000c` ou `Phomemo Q30`

### **PASSO 3: Identificar a porta**

```bash
ls -la /dev/ttyUSB*
```

Esperado: `/dev/ttyUSB0` ou `/dev/ttyUSB1`

### **PASSO 4: Testar CLI**

```bash
python3 /app/phomemo_print.py --text "TESTE"
```

Esperado na impressora: Etiqueta impressa com "TESTE"

### **PASSO 5: Testar no Open WebUI**

1. Acesse: `http://192.168.15.2:8002`
2. No chat, digite: `Imprima: TESTE 123`
3. Veja a impressora responder!

---

## 🆘 Se não funcionar:

### 1. Phomemo não aparece em lsusb
- Verifique conexão USB física
- Tente outro cabo USB
- Execute: `dmesg | tail -50` (procure por erros USB)

### 2. Porta não aparece em /dev/ttyUSB*
- Pode ser `/dev/ttyACM0` ou `/dev/ttyACM1`
- Execute: `python3 /app/phomemo_print.py --list`

### 3. "Permission denied" em /dev/ttyUSB0
- Execute: `sudo chmod 666 /dev/ttyUSB0`
- Ou: `sudo usermod -aG dialout $USER`

### 4. Comando executa mas não imprime
- Verifique papel na impressora
- Teste envio direto: `echo "TEST" > /dev/ttyUSB0`
- Verifique baudrate (padrão: 9600)

---

## 📱 Identificadores USB da Phomemo Q30

| Item | Valor |
|------|-------|
| Vendor ID (VID) | 2e8d (Phomemo) |
| Product ID (PID) | 000c (comum) / 0004 (variante) |
| Classe | Communication / Miscellaneous |
| Driver | ch341 (chipset comum) |

---

## 💻 Comandos Úteis

### Listar todas as portas e procurar Phomemo:
```bash
python3 /app/phomemo_print.py --list
```

### Testar impressão direta:
```bash
python3 /app/phomemo_print.py --text "TESTE" --port /dev/ttyUSB0
```

### Diagnóstico completo no servidor:
```bash
python3 /app/check_phomemo.py
```

### Ver logs de detecção USB:
```bash
dmesg | tail -50 | grep -E "usb|tty|ch341"
```

### Forçar permissões:
```bash
sudo chown root:dialout /dev/ttyUSB0 && sudo chmod 666 /dev/ttyUSB0
```

### Resetar impressora via serial:
```python
import serial
ser = serial.Serial('/dev/ttyUSB0', 9600)
ser.write(b'\x1b@')  # Reset ESC/POS
ser.close()
print("Reset enviado")
```

---

## 📊 Protocolo de Comunicação

| Parâmetro | Valor |
|-----------|-------|
| Tipo | ESC/POS (baseado em comandos de impressora térmica) |
| Velocidade | 9600 baud |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None (sem paridade) |
| Flow control | None |
| Timeout | 1 segundo |

### Comandos principais:
- `\x1b@` - Reset/Inicializar impressora
- `\x1d\x76\x30\x00` - Comando de imagem raster (GS v 0)
- `\x0c` - Form Feed (avanço de papel)
- Texto simples (UTF-8)

---

## 🎯 Objetivo Final

```
✨ Chat no Open WebUI:
   Você: "Imprima: Júlia Teixeira - 19/01/2026 - 123456"
   Bot: "✅ Impresso com sucesso!"
   🖨️  Impressora: Etiqueta sai com os dados
```

---

## 📞 Próximo Passo

**CONECTE A IMPRESSORA VIA USB E TESTE!** 🖨️

Se tiver algum erro, execute:
```bash
python3 /app/check_phomemo.py
```

E compartilhe o resultado!
