# Runbook: Retirada Manual de STORJ para KuCoin

**Este é um procedimento operado por humano, não automatizado.** Nenhum
serviço deste repositório tem, ou terá, custódia da chave privada da
carteira de payout do nó Storj (`0x4787E8bA11d9D32f8A51336a1844e663105a7d24`).
A assinatura de qualquer transferência real é sempre feita à mão, com um
hardware wallet (Ledger ou Trezor) fisicamente conectado.

## Contexto

- O token STORJ é um ERC-20 nativo do **Ethereum L1**
  (`0xB64ef51C888972c908CFacf59B47C1AfBC0Ab8aC`).
- O saldo do nó é pago e fica representado no **zkSync Era (L2)**.
- A Storj retém pagamentos por ~2 períodos (meses) antes de liberá-los como
  saldo gasto ("disposed") — `tools/homelab/storj_payout_monitor.py` avisa
  via Telegram quando isso acontece.
- Caminho oficial documentado pela Storj para mover fundos para uma exchange:
  **bridge L2→L1**, depois **transfer ERC-20 padrão em L1**.

## Pré-requisitos (uma vez)

1. **Hardware wallet** (Ledger ou Trezor) com a carteira que controla
   `0x4787E8bA11d9D32f8A51336a1844e663105a7d24` já configurada nele —
   confirmar que o endereço mostrado no device bate exatamente com esse.
2. **Regras udev** no host onde o device for conectado (não precisa ser o
   homelab — pode ser qualquer máquina do operador):
   - Ledger: `20-hw1.rules` (repositório oficial LedgerHQ/udev-rules)
   - Trezor: `51-trezor.rules` (repositório oficial trezor/trezor-common)
3. Navegador atualizado para acessar `https://portal.zksync.io/bridge`
   (interface oficial da zkSync Era, não deste repositório).
4. Conta KuCoin com STORJ habilitado para depósito (rede ERC20/L1).

## Passo a passo

### 1. Ver o plano de transferência (seguro, sem device conectado)

```bash
ssh homelab@192.168.15.2
python3 /usr/local/bin/storj_withdraw.py
```

Isso imprime: saldo atual na carteira, endereço de depósito STORJ da KuCoin
(rede ERC20), e o plano em duas etapas. **Não executa nada, não precisa do
hardware wallet conectado.**

### 2. Etapa 1 — Bridge L2 (zkSync Era) → L1 (Ethereum)

1. Conectar o hardware wallet ao computador.
2. Abrir `https://portal.zksync.io/bridge`.
3. Conectar a carteira (WalletConnect ou USB direto, conforme o device).
4. Selecionar token **STORJ**, rede origem **zkSync Era**, destino **Ethereum
   Mainnet (L1)**, endereço destino = a mesma carteira
   (`0x4787E8bA11d9D32f8A51336a1844e663105a7d24`).
5. Selecionar **pagar taxa em STORJ** (meta-transação gasless — não precisa
   de ETH).
6. **Confirmar fisicamente no hardware wallet.**
7. Aguardar confirmação on-chain (pode levar alguns minutos).

### 3. Etapa 2 — Transfer ERC-20 L1 → KuCoin

1. Com o saldo já em L1, usar a mesma carteira/hardware wallet num app que
   suporte envio ERC-20 padrão (MetaMask conectado ao Ledger/Trezor, ou o
   próprio app do device).
2. Endereço destino = o endereço de depósito impresso pelo
   `storj_withdraw.py` no passo 1 (rede ERC20).
3. **Conferir 3x o endereço e a rede antes de confirmar** — é irreversível.
4. **Confirmar fisicamente no hardware wallet.**

### 4. Teste obrigatório com valor pequeno primeiro

**Antes de mover o saldo total**, repita as etapas 2–3 com um valor pequeno
(equivalente a $1–2 em STORJ). Só prossiga com o valor total depois de:
- Confirmar que o valor pequeno chegou corretamente na conta KuCoin.
- Confirmar que a rede/endereço usados foram exatamente os certos.

## Troubleshooting

- **Ledger não assina a transação de bridge (tx type 113 / EIP-712):**
  verificar se o app Ethereum do Ledger está atualizado; alguns fluxos de
  bridge zkSync exigem o "blind signing" habilitado nas configurações do
  app Ethereum do device.
- **KuCoin não credita o depósito:** confirmar que a rede usada foi
  exatamente `ERC20` (não zkSync Era) — a KuCoin pode não suportar
  depósito direto via L2 para STORJ.
- **API da KuCoin retorna "currency does not exist" para STORJ/erc20:** a
  KuCoin expõe a rede ERC20 do STORJ com `chainId=eth` na API (mesmo com
  `chainName` exibido como "ERC20" na UI) — confirmado via
  `GET https://api.kucoin.com/api/v3/currencies/STORJ` (público, sem auth).
  `storj_withdraw.py` já usa `chain="eth"` por padrão; se voltar a falhar,
  reconferir esse endpoint (a KuCoin pode mudar o chainId).
- **Depósito mínimo:** a KuCoin exige `depositMinSize=2` STORJ — valores
  abaixo disso na Etapa 2 não são creditados.
- **Saldo não aparece após o bridge:** o bridge L2→L1 pode levar de minutos
  a horas dependendo da carga da rede; conferir o hash da transação no
  explorer do zkSync Era antes de assumir falha.

## Fora de Escopo (por design)

- **Automação da assinatura.** `storj_withdraw.py --i-am-present` levanta
  `NotImplementedError` de propósito — não existe, e não deve ser criado,
  código neste repositório que assine transações reais.
- **Custódia de chave privada por qualquer serviço deste repositório** —
  nenhuma secret com chave privada da carteira Storj deve ser criada em
  `tools/secrets_agent_client.py` ou em qualquer outro lugar.
- **Config de trading STORJ-USDT** no `btc_trading_agent` — decisão
  separada, a ser tomada depois que o saldo já estiver na KuCoin, com
  revisão própria de parâmetros de risco.
