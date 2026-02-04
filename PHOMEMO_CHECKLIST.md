# ✅ Checklist: Conectar Phomemo Q30 USB

## Pré-requisitos
- [ ] Phomemo Q30 disponível
- [ ] Cabo USB para impressora
- [ ] Acesso SSH ao servidor (homelab@192.168.15.2)
- [ ] Acesso ao navegador para Open WebUI (http://192.168.15.2:8002)

---

## Fase 1: Conexão Física ⚡

- [ ] **1.1** Desligar impressora Phomemo Q30
- [ ] **1.2** Conectar cabo USB na Phomemo
- [ ] **1.3** Conectar outra ponta do USB no servidor
- [ ] **1.4** Ligar a Phomemo
- [ ] **1.5** Verificar que a Phomemo está pronta (luz indicadora)

---

## Fase 2: Detecção do Hardware 🔍

### No seu computador:

```bash
# 2.1 - Conectar ao servidor
ssh homelab@192.168.15.2

# 2.2 - Verificar se Phomemo aparece em lsusb
lsusb | grep -i phomemo
# OU procure por VID 2e8d:
lsusb | grep 2e8d
```

**Esperado:** Algo como:
```
Bus 001 Device 005: ID 2e8d:000c
```

- [ ] **2.3** Phomemo detectada em lsusb
- [ ] **2.4** Verificar porta serial:
```bash
ls -la /dev/ttyUSB*
```
**Esperado:** `/dev/ttyUSB0` ou semelhante

- [ ] **2.5** Porta serial identificada: `_________________` (ex: /dev/ttyUSB0)

---

## Fase 3: Teste via CLI 💻

No servidor:

```bash
# 3.1 - Listar todas as portas conhecidas
python3 /app/phomemo_print.py --list
```

- [ ] **3.2** Comando executado com sucesso

```bash
# 3.3 - Enviar teste simples de impressão
python3 /app/phomemo_print.py --text "TESTE"
```

- [ ] **3.4** Mensagem recebida: "Trabalho enviado!"
- [ ] **3.5** Verificar impressora: etiqueta impressa com "TESTE"

**Se não imprimiu, execute diagnóstico:**
```bash
python3 /app/check_phomemo.py
```
- [ ] **3.6** Diagnóstico compartilhado e analisado

---

## Fase 4: Teste via Open WebUI 🌐

1. Abrir navegador e acessar:
   ```
   http://192.168.15.2:8002
   ```
   - [ ] **4.1** Open WebUI carregado

2. Procurar pela função "printer_etiqueta":
   - [ ] **4.2** Função está no menu de seleção
   - [ ] **4.3** Status mostra como ATIVO ✅

3. No campo de chat, digitar:
   ```
   Imprima: Teste de Conexão
   ```
   - [ ] **4.4** Chat respondeu com "✅ Impresso com sucesso!"
   - [ ] **4.5** Impressora imprimiu etiqueta com "Teste de Conexão"

---

## Fase 5: Testes Avançados 🚀

### Teste com dados reais:
```
Imprima: Júlia Teixeira - 19/01/2026 - 123456
```
- [ ] **5.1** Etiqueta impressa com dados corretos

### Teste com imagem (opcional):
```bash
# No servidor:
python3 /app/phomemo_print.py --image /tmp/test.png
```
- [ ] **5.2** Imagem impressa corretamente

### Teste com múltiplas impressões:
```
Imprima: Produto 1
Imprima: Produto 2
Imprima: Produto 3
```
- [ ] **5.3** Todas as 3 etiquetas impressas

---

## Fase 6: Solução de Problemas 🆘

**Se encontrou problemas na Fase 3 ou 4:**

### Problema 1: Phomemo não aparece em lsusb

- [ ] **6.1.1** Verificar conexão USB física
- [ ] **6.1.2** Tentar outro cabo USB
- [ ] **6.1.3** Desligar e ligar impressora
- [ ] **6.1.4** Executar: `dmesg | tail -50` (procurar por erros USB)
- [ ] **6.1.5** Se USB aparece em dmesg mas não em lsusb: driver issue

### Problema 2: Porta não aparece em /dev/ttyUSB*

- [ ] **6.2.1** Executer: `python3 /app/phomemo_print.py --list`
- [ ] **6.2.2** Se lista algo em "Serial Ports": usar a porta listada
- [ ] **6.2.3** Se lista vazio: verificar conexão USB

### Problema 3: Permission Denied em /dev/ttyUSB0

```bash
sudo chmod 666 /dev/ttyUSB0
```
- [ ] **6.3.1** Permissões corrigidas
- [ ] **6.3.2** Tentar impressão novamente

### Problema 4: Comando executa mas não imprime

- [ ] **6.4.1** Verificar papel/tinta na Phomemo
- [ ] **6.4.2** Resetar impressora: pressionar botão físico
- [ ] **6.4.3** Testar envio direto: `echo "TEST" > /dev/ttyUSB0`
- [ ] **6.4.4** Executar diagnóstico completo: `python3 /app/check_phomemo.py`

---

## ✨ Resultado Final

Se completou tudo:

- [ ] **✅ Phomemo Q30 detectada pelo servidor**
- [ ] **✅ Impressão via CLI funcionando**
- [ ] **✅ Impressão via Open WebUI funcionando**
- [ ] **✅ Etiquetas impressas com dados corretos**

---

## 📋 Notas e Observações

Escreva aqui qualquer observação ou problema encontrado:

```
_________________________________________________________________

_________________________________________________________________

_________________________________________________________________
```

---

## 📞 Próximas Ações (após sucesso)

- [ ] Testar com dados reais da aplicação
- [ ] Configurar tamanho padrão de etiqueta
- [ ] Adicionar validação de tamanho de texto
- [ ] Criar templates de etiquetas personalizadas
- [ ] Configurar alertas de papel/tinta baixos

---

## 🎯 Status Geral

**Iniciado em:** _______________

**Concluído em:** _______________

**Resultado:** `[ ] Sucesso  [ ] Parcial  [ ] Falha`

**Observações Finais:**

```
_________________________________________________________________

_________________________________________________________________
```

---

**Bom trabalho! 🖨️**
