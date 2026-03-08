# 🖨️ Teste de Impressora - VM Windows

## Status do Homelab (5 de março de 2026)

✅ Samba: `smbd` e `nmbd` ativos
✅ CUPS: L380 ativa e aceitando requisições  
✅ Configuração: Samba com `load printers = yes` e `printing = cups`
✅ Teste local: Job enviado com sucesso (L380-35)

---

## Na VM Windows

### 1. Abrir "Dispositivos e Impressoras"

```
Painel de Controle → Dispositivos e Impressoras
```

### 2. Adicionar Impressora via Rede (Samba)

**Opção A: Busca automática**
- Clique em **"Adicionar uma impressora"**
- **"A impressora que desejo não está listada"**
- Selecione **"Procurar uma impressora em uma rede"**
- Aguarde a descoberta de `\\HOMELAB\`

**Opção B: Manual**
```
Nome: \\192.168.15.2\L380
ou
\\homelab\L380
```

### 3. Instalar Driver

Quando o Windows pedir:
- **Modelo:** EPSON L380 Series  
- Se não encontrar, baixe em: https://epson.com/suporta/L380

### 4. Testar Impressão

```
Clique direito na impressora → "Propriedades"
Aba "Geral" → Botão "Página de teste"
```

---

## Se não encontrar a impressora

### No Windows: Adicionar manualmente

```
\\192.168.15.2\L380
```

### No Homelab: Verificar

```bash
sudo lpstat -t                   # Confirmar L380 está ativa
smbclient -L 192.168.15.2 -N     # Listar compartilhamentos
sudo testparm -s | grep -A5 "\[printers\]"  # Verificar config
```

---

## Jobs Pendentes

Ver fila atual:

```
lpstat -o
```

Cancelar job:

```
cancel L380-XX    # onde XX é o número do job
```

---

**Data:** 5 de março de 2026  
**Local do servidor:** 192.168.15.2  
**Impressora:** L380 Series (USB)

