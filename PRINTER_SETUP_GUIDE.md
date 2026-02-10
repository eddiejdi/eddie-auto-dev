# 🖨️ Impressora de Etiquetas - Guia Rápido

**Data de Instalação:** 2 de fevereiro de 2026  
**Versão:** 1.0  
**Status:** ✅ Ativo no Open WebUI

---

## 🚀 Acesso Rápido

**Open WebUI URL:** http://${HOMELAB_HOST}:8002  
**Função:** 🖨️ Impressora de Etiquetas (`printer_etiqueta`)

---

## 📝 Como Usar

### 1. Abrir o Open WebUI

http://${HOMELAB_HOST}:8002
### 2. Ir para Settings → Functions → "🖨️ Impressora de Etiquetas"

### 3. Usar em um Chat

#### **Opção A: Texto Simples**
Escreva na conversa:
Imprima uma etiqueta com o texto: PEDIDO #123
A função vai:
- ✅ Validar se o texto cabe na etiqueta (384px largura)
- ⚠️ Avisar se for muito grande
- 🖨️ Enviar para o Phomemo Q30

#### **Opção B: Validar Antes de Imprimir**
```json
{
  "action": "print",
  "content": "ETIQUETA GRANDE TESTE",
  "validate_only": true
}
Resultado: Mostra estimativa de tamanho sem imprimir

#### **Opção C: Imprimir Imagem**
```json
{
  "action": "print",
  "content": "/home/homelab/label.png",
  "type": "image"
}
---

## 📋 Arquivos Instalados

| Arquivo | Localização | Descrição |
|---------|------------|-----------|
| `phomemo_print.py` | `/home/homelab/agents_workspace/` | Driver da impressora |
| `openwebui_printer_function.py` | `/home/homelab/agents_workspace/` | Função Open WebUI |
| `install_printer_function.py` | `/home/homelab/agents_workspace/` | Script de instalação |

---

## ⚙️ Configuração

### Porta Serial (Auto-detecção)
A função detecta automaticamente a porta do Phomemo. Se necessário configurar manualmente:

1. Listar portas disponíveis:
```bash
python3 /home/homelab/agents_workspace/phomemo_print.py --list
2. Editar função no Open WebUI → Valves:
PRINTER_PORT = "/dev/ttyUSB0"  # ou a porta detectada
BAUDRATE = 9600  # velocidade padrão
---

## 🎯 Características

✨ **Validação Automática** - Calcula se o texto/imagem cabe  
✨ **Feedback em Tempo Real** - Status de cada operação  
✨ **Suporte a Texto e Imagem** - Ambos os formatos  
✨ **Porta Serial Bluetooth** - Comunicação via Phomemo  
✨ **Tratamento de Erros** - Mensagens claras se algo der errado  

---

## 📏 Limites da Etiqueta

- **Largura máxima:** 384 pixels
- **Altura máxima:** 600 pixels
- **Baudrate:** 9600 bps
- **Conexão:** Bluetooth Serial (Phomemo Q30)

---

## 🔧 Troubleshooting

### ❌ "Impressora não encontrada"
```bash
# Verificar conexão Bluetooth
ls /dev/tty*

# Testar com comando direto
python3 /home/homelab/agents_workspace/phomemo_print.py --list
### ❌ "Erro de tamanho"
- Texto deve caber em ~48 caracteres por linha
- Máximo ~20 linhas de altura

### ❌ "Timeout"
- Verificar se Phomemo está emparelhado
- Reiniciar a impressora
- Verificar bateria

---

## 📞 Suporte

**Servidor:** homelab@${HOMELAB_HOST}  
**Usuário Admin:** homelab  
**Diretório de trabalho:** `/home/homelab/agents_workspace`

Para logs:
```bash
ssh homelab@${HOMELAB_HOST}
cd /home/homelab/agents_workspace
python3 phomemo_print.py --list
---

## 🔄 Exemplos Práticos

### Imprimir Código de Barras (texto)
Imprima uma etiqueta: 
PRODUTO: SKU-12345
PRECO: R$ 49,90
### Validar Múltiplas Linhas
```json
{
  "action": "print",
  "content": "LINHA 1\nLINHA 2\nLINHA 3",
  "validate_only": true
}
### Imprimir QR Code (como imagem)
```json
{
  "action": "print",
  "content": "/tmp/qrcode.png",
  "type": "image"
}
---

**Criado por:** Eddie Auto-Dev  
**Última atualização:** 2 de fevereiro de 2026
