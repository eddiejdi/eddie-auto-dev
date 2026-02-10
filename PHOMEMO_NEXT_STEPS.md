# 📖 Resumo: Conectando Phomemo Q30 USB ao Open WebUI

## ✅ O que já está feito:

✅ Função "printer_etiqueta" criada no Open WebUI
✅ Status: ATIVO e GLOBAL (apareça no menu)
✅ Código atualizado para suportar USB + Bluetooth
✅ Dependências instaladas (pyserial, Pillow)
✅ Arquivo phomemo_print.py no container (/app/)
✅ Pronto para receber comandos de impressão
## 🔧 O que você precisa fazer:

### **Passo 1: Conectar a Phomemo Q30 via USB no servidor**

No servidor (homelab@${HOMELAB_HOST}):
- Conecte o cabo USB da impressora Phomemo Q30
- Verifique que está conectada

### **Passo 2: Verificar detecção da impressora**

```bash
# No seu computador:
ssh homelab@${HOMELAB_HOST}

# No servidor:
lsusb | grep -i phomemo
# OU procure por VID 2e8d:
lsusb | grep 2e8d

# Ou veja todas as portas:
ls -la /dev/ttyUSB*
**Esperado:** Algo como `/dev/ttyUSB0` ou `/dev/ttyUSB1`

### **Passo 3: Testar via linha de comando**

```bash
ssh homelab@${HOMELAB_HOST}

# Listar todas as portas conhecidas:
python3 /app/phomemo_print.py --list

# Testar impressão:
python3 /app/phomemo_print.py --text "TESTE CONEXÃO USB"
**Esperado na impressora:** Etiqueta impressa com "TESTE CONEXÃO USB"

### **Passo 4: Testar no Open WebUI**

1. Abra: `http://${HOMELAB_HOST}:8002`
2. Clique em "Chats"
3. Digite no chat: `Imprima: Seus dados aqui`
4. Veja o resultado!

---

## 🔍 Diagnósticos Úteis

Se não funcionar, execute:

```bash
# Verifica se a Phomemo aparece em lsusb:
ssh homelab@${HOMELAB_HOST} 'lsusb'

# Verifica logs do kernel para ver se foi detectada:
ssh homelab@${HOMELAB_HOST} 'dmesg | tail -50'

# Testa com o script de diagnóstico no servidor:
ssh homelab@${HOMELAB_HOST} 'python3 /app/check_phomemo.py'
---

## 📋 Resumo Rápido do Workflow

1. Conectar USB no servidor
2. ssh homelab@${HOMELAB_HOST}
3. lsusb (deve aparecer Phomemo)
4. python3 /app/phomemo_print.py --text "TESTE"
5. Se funcionar:  abra Open WebUI e diga "Imprima TESTE"
6. Se não:        verifique dmesg para erros USB
---

## 📚 Arquivos Criados/Modificados

- ✅ `phomemo_print.py` - Atualizado para suportar melhor USB
- ✅ `diagnose_phomemo_connection.py` - Diagnóstico rápido local
- ✅ `check_phomemo_server.py` - Diagnóstico no servidor
- ✅ `PHOMEMO_USB_SETUP.md` - Guia completo de setup
- ✅ `openwebui_printer_function.py` - Função pronta no Open WebUI

---

## 🎯 Próxima Ação

**Agora é com você!** Conecte a impressora Phomemo Q30 via USB no servidor e siga os passos acima.

Se tiver dúvidas, execute o diagnóstico:
```bash
python3 /app/check_phomemo.py
E me mostre o resultado! 🖨️
