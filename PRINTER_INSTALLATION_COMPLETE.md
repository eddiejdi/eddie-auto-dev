# ✅ INSTALAÇÃO CONCLUÍDA - Impressora de Etiquetas Phomemo Q30

## 📊 Resumo da Instalação

**Data:** 2 de fevereiro de 2026  
**Servidor:** homelab@${HOMELAB_HOST}  
**Status:** ✅ Ativo e Pronto para Uso

---

## 🎯 O que foi instalado

### 1. Driver da Impressora
- **Arquivo:** `phomemo_print.py`
- **Local:** `/home/homelab/agents_workspace/phomemo_print.py`
- **Funcionalidade:** 
  - Comunicação serial com Phomemo Q30
  - Suporte a impressão de texto e imagens
  - Auto-detecção de porta Bluetooth
  - Protocolo ESC/POS

### 2. Função Open WebUI
- **ID:** `printer_etiqueta`
- **Nome:** 🖨️ Impressora de Etiquetas
- **Local:** Open WebUI em `http://${HOMELAB_HOST}:8002`
- **Funcionalidades:**
  - Validação automática de tamanho
  - Impressão de texto com múltiplas linhas
  - Impressão de imagens PNG/BMP
  - Feedback em tempo real
  - Tratamento de erros robusto

### 3. Dependências Instaladas
- `python3-serial` - Comunicação serial
- `python3-pil` - Processamento de imagens (Pillow)

---

## 🚀 Como Usar

### Método 1: Via Chat no Open WebUI (Recomendado)

1. Acesse: **http://${HOMELAB_HOST}:8002**
2. Faça login com suas credenciais
3. Clique em qualquer chat
4. **Digite uma mensagem natural:**
   ```
   Imprima uma etiqueta com o texto: PEDIDO 12345
   ```

### Método 2: Usando JSON (Avançado)

1. Crie um chat novo
2. Use a função `printer_etiqueta` com JSON:

**Validar tamanho antes de imprimir:**
```json
{
  "action": "print",
  "content": "ETIQUETA GRANDE TESTE",
  "validate_only": true
}
**Imprimir texto simples:**
```json
{
  "action": "print",
  "content": "PRODUTO SKU-123\nPRECO: R$ 49,90",
  "type": "text"
}
**Imprimir imagem:**
```json
{
  "action": "print",
  "content": "/tmp/qrcode.png",
  "type": "image"
}
### Método 3: Linha de Comando (Servidor)

```bash
ssh homelab@${HOMELAB_HOST}

# Imprimir texto
python3 /home/homelab/agents_workspace/phomemo_print.py --text "TESTE"

# Listar portas
python3 /home/homelab/agents_workspace/phomemo_print.py --list

# Imprimir imagem
python3 /home/homelab/agents_workspace/phomemo_print.py --image /path/to/label.png
---

## 📏 Especificações Técnicas

| Parâmetro | Valor |
|-----------|-------|
| **Modelo** | Phomemo Q30 |
| **Conexão** | Bluetooth Serial |
| **Baudrate** | 9600 bps |
| **Largura Máxima** | 384 pixels |
| **Altura Máxima** | 600 pixels |
| **Formatos Suportados** | Texto UTF-8, PNG, BMP |
| **Protocolo** | ESC/POS |

---

## ✨ Características Implementadas

✅ **Validação de Tamanho**
- Calcula automaticamente se o texto cabe
- Avisa se exceder limites
- Estimativa em pixels

✅ **Suporte a Múltiplas Linhas**
- Use `\n` para quebras de linha
- Validação de altura total

✅ **Impressão de Imagens**
- Converte automaticamente para bitmap monocromático
- Redimensiona se necessário
- Até 384px de largura

✅ **Detecção Automática de Porta**
- Encontra Phomemo automaticamente
- Suporta porta manual se necessário
- Fallback para portas padrão

✅ **Feedback em Tempo Real**
- Status de cada operação
- Mensagens de erro descritivas
- Contagem de caracteres

---

## 🔧 Configuração Avançada

### Mudar Porta Serial Manualmente

Se a auto-detecção não funcionar:

1. Acesse: http://${HOMELAB_HOST}:8002
2. Vá para: **Settings → Functions → 🖨️ Impressora de Etiquetas**
3. Edite os **Valves:**
   ```python
   PRINTER_PORT = "/dev/ttyUSB0"  # sua porta
   BAUDRATE = 9600
   MAX_WIDTH = 384
   MAX_HEIGHT = 600
   ```

### Listar Portas Disponíveis

```bash
ssh homelab@192.168.15.2
python3 /home/homelab/agents_workspace/phomemo_print.py --list
---

## 📝 Exemplos de Uso

### Exemplo 1: Etiqueta de Produto
Imprima uma etiqueta com:
PRODUTO XYZ
SKU: 12345
PREÇO: R$ 99,90
### Exemplo 2: Validar Antes de Imprimir
```json
{
  "action": "print",
  "content": "LINHA 1\nLINHA 2\nLINHA 3\nLINHA 4\nLINHA 5",
  "validate_only": true
}
**Resposta esperada:**
✅ Validação da Etiqueta

✅ Texto: 44 caracteres
📏 Estimativa:
   - Largura: 64px / 384px
   - Altura: 80px / 600px

Status: ✅ VÁLIDO - Pronto para imprimir
### Exemplo 3: Imprimir com Imagem
```json
{
  "action": "print",
  "content": "/home/homelab/qrcode_pedido123.png",
  "type": "image"
}
---

## 🆘 Troubleshooting

### ❌ "Impressora não encontrada"

**Solução:**
1. Verifique se Phomemo está emparelhado via Bluetooth
2. Reinicie a impressora
3. Execute: `python3 phomemo_print.py --list`
4. Se ainda não aparecer, configure manualmente em Valves

### ❌ "Texto não cabe na etiqueta"

**Solução:**
- Máximo ~48 caracteres por linha
- Máximo ~20 linhas
- Use `validate_only: true` para verificar antes
- Considere quebrar em múltiplas etiquetas

### ❌ "Timeout ao imprimir"

**Solução:**
- Verifique conexão Bluetooth
- Reinicie a impressora
- Tente novamente após 5 segundos
- Aumente timeout em Valves se necessário

### ❌ "Imagem não imprime"

**Solução:**
- Certifique-se que é PNG ou BMP
- Reduza tamanho se > 384px de largura
- Converta para escala de cinza se colorida

---

## 📁 Arquivos Criados

/home/homelab/agents_workspace/
├── phomemo_print.py              # Driver principal
├── openwebui_printer_function.py # Função OpenWebUI
├── install_printer_function.py   # Script de instalação
└── test_printer_function.py      # Testes
---

## 🔐 Segurança

- Função não armazena dados
- Nenhuma senha é registrada
- Comunicação local apenas
- Sem acesso à internet necessário

---

## 📞 Suporte

**Servidor:** `homelab@${HOMELAB_HOST}`  
**Open WebUI:** `http://${HOMELAB_HOST}:8002`  
**Espaço de trabalho:** `/home/homelab/agents_workspace`

---

## ✅ Próximos Passos

1. ✅ Conectar Phomemo Q30 via Bluetooth
2. ✅ Acessar http://192.168.15.2:8002
3. ✅ Testar com mensagem: "Imprima TESTE"
4. ✅ Validar impressão física
5. ✅ Usar em produção

---

**Instalação realizada com sucesso!**  
**Versão:** 1.0  
**Data:** 2 de fevereiro de 2026
