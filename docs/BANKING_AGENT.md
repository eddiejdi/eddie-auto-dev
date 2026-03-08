# Banking Integration Agent — Shared Auto-Dev

Agent de integração multi-banco para finanças pessoais e empresariais.

## Bancos Suportados

| Banco | Protocolo | Funcionalidades |
|-------|-----------|----------------|
| 🔴 **Santander** | Open Finance Brasil | Contas, saldo, transações, cartões, PIX |
| 🟠 **Itaú Unibanco** | Open Finance Brasil | Contas, saldo, transações, cartões, faturas |
| 🟣 **Nubank** | Open Finance Brasil | NuConta, saldo, transações, cartão Roxinho |
| 🔵 **Mercado Pago** | API REST proprietária | Conta, saldo, payments, PIX QR Code |

## Arquitetura

┌──────────────────────────────────────────┐
│           BankingAgent (Orquestrador)     │
│  ┌─────────────┐  ┌──────────────────┐   │
│  │  Security    │  │  Communication   │   │
│  │  Manager     │  │  Bus Integration │   │
│  └─────────────┘  └──────────────────┘   │
│                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌───┐ │
│  │Santander│ │  Itaú  │ │ Nubank │ │MP │ │
│  │Connector│ │Connector│ │Connector│ │  │ │
│  └────┬───┘ └────┬───┘ └────┬───┘ └─┬─┘ │
└───────┼──────────┼──────────┼────────┼───┘
        │          │          │        │
   Open Finance Brasil APIs     MP REST API
## Configuração

### 1. Credenciais Bancárias

Credenciais podem ser configuradas via **variáveis de ambiente** ou pelo **vault** integrado:

```bash
# Santander
export BANK_SANTANDER_CLIENT_ID="seu_client_id"
export BANK_SANTANDER_CLIENT_SECRET="seu_client_secret"
export BANK_SANTANDER_REDIRECT_URI="https://seu-dominio/callback/santander"

# Itaú
export BANK_ITAU_CLIENT_ID="seu_client_id"
export BANK_ITAU_CLIENT_SECRET="seu_client_secret"

# Nubank
export BANK_NUBANK_CLIENT_ID="seu_client_id"
export BANK_NUBANK_CLIENT_SECRET="seu_client_secret"

# Mercado Pago (mais simples — usar access_token direto)
export BANK_MERCADOPAGO_ACCESS_TOKEN="APP_USR-xxxxx"
# ou OAuth2:
export BANK_MERCADOPAGO_CLIENT_ID="seu_client_id"
export BANK_MERCADOPAGO_CLIENT_SECRET="seu_client_secret"
### 2. Certificados mTLS (Open Finance)

Santander, Itaú e Nubank exigem certificados mTLS:

agent_data/banking/certs/santander/
  ├── client.pem   # Certificado do cliente
  ├── client.key   # Chave privada
  └── ca.pem       # CA (opcional)

agent_data/banking/certs/itau/
  └── ...

agent_data/banking/certs/nubank/
  └── ...
### 3. Via vault

from specialized_agents.banking.security import BankingSecurityManager

sec = BankingSecurityManager()
sec.store_credentials("santander", {
    "client_id": "abc",
    "client_secret": "xyz",
    "redirect_uri": "https://...",
})
## Uso

### Inicialização

from specialized_agents.banking_agent import get_banking_agent
from specialized_agents.banking.models import BankProvider

agent = get_banking_agent()

# Conectar todos os bancos configurados
results = await agent.initialize()
# {'santander': 'OK', 'itau': 'Auth Error: ...', 'nubank': 'OK', 'mercadopago': 'OK'}

# Ou apenas bancos específicos
results = await agent.initialize([BankProvider.NUBANK, BankProvider.MERCADOPAGO])
### Visão consolidada

view = await agent.get_consolidated_view()

print(f"Total disponível: R$ {view.total_available:,.2f}")
print(f"Limite crédito: R$ {view.total_credit_limit:,.2f}")
print(f"Contas: {len(view.accounts)}")

# Resumo para chat/Telegram
print(view.summary_text())
### Extrato unificado

from datetime import date, timedelta

stmt = await agent.get_unified_statement(
    start_date=date.today() - timedelta(days=30),
    end_date=date.today(),
)

print(f"Entradas: R$ {stmt['total_credits']}")
print(f"Saídas: R$ {stmt['total_debits']}")
print(f"Resultado: R$ {stmt['net_result']}")

# Por categoria
for cat, data in stmt['by_category'].items():
    print(f"  {cat}: R$ {data['total_debit']} ({data['count']} transações)")
### PIX

from decimal import Decimal
from specialized_agents.banking.models import BankProvider

# Enviar PIX via Nubank
result = await agent.send_pix(
    from_provider=BankProvider.NUBANK,
    pix_key="email@destino.com",
    amount=Decimal("150.00"),
    description="Pagamento serviço",
)
print(f"Status: {result.status}")
print(f"E2E ID: {result.end_to_end_id}")

# Gerar QR Code PIX (Mercado Pago)
from specialized_agents.banking import MercadoPagoConnector
mp = MercadoPagoConnector()
qr = await mp.generate_pix_qr(Decimal("99.90"), "Cobrança PIX")
print(f"QR Code: {qr['qr_code']}")
### Alertas de gastos

from decimal import Decimal

# Definir limites
agent.set_spending_threshold("Alimentação", Decimal("800"))
agent.set_spending_threshold("Transporte", Decimal("300"))
agent.set_spending_threshold("Lazer", Decimal("200"))

# Verificar alertas
alerts = await agent.check_spending_alerts()
for alert in alerts:
    print(f"⚠️ {alert.message}")
### Relatório mensal

report = await agent.generate_monthly_report("2026-02")
print(json.dumps(report, indent=2, ensure_ascii=False))
## Comandos Telegram

O agent se integra ao `telegram_bot.py` via bus de comunicação:

| Comando | Descrição |
|---------|-----------|
| `/saldo` | Saldo consolidado de todos os bancos |
| `/extrato [dias]` | Extrato unificado dos últimos N dias |
| `/cartoes` | Cartões de crédito ativos |
| `/relatorio [YYYY-MM]` | Relatório mensal consolidado |
| `/alertas` | Alertas de gastos acima do limite |

## Segurança

- **Criptografia**: Todas as credenciais são criptografadas em repouso (Fernet/AES-128-CBC)
- **mTLS**: Comunicação com Open Finance usa certificados mTLS
- **PKCE**: OAuth2 com Proof Key for Code Exchange
- **Tokens**: Cache em memória com expiração automática
- **Auditoria**: Todos os acessos são logados (LGPD)
- **Mascaramento**: CPF/CNPJ e contas sempre mascarados em logs
- **Vault**: Integração com `tools/simple_vault/` para segredos

## Categorização Automática

O agent categoriza transações automaticamente usando regras baseadas na descrição:

| Categoria | Exemplos |
|-----------|----------|
| Alimentação | iFood, Rappi, supermercados, padarias |
| Transporte | Uber, 99, postos, pedágio |
| Moradia | Aluguel, condomínio, energia, internet |
| Saúde | Farmácias, hospitais, planos de saúde |
| Educação | Cursos, faculdade, Udemy, Alura |
| Lazer | Netflix, Spotify, cinema |
| Compras | Amazon, Mercado Livre, Shopee |
| Tarifas | Taxas bancárias, IOF, anuidade |

## Open Finance Brasil

Este agent segue os padrões do **Open Finance Brasil** regulado pelo Banco Central:

- **Fase 2**: Dados de contas, cartões e transações (leitura)
- **Fase 3**: Iniciação de pagamentos (PIX)
- **Consentimento**: Exige autorização explícita do titular
- **Certificados**: Registro no Diretório de Participantes

### Fluxo de Consentimento

1. Agent cria pedido de consentimento → POST /consents
2. Banco retorna URL de autorização → redirect_url
3. Usuário autoriza no app do banco
4. Banco retorna authorization_code → callback
5. Agent troca code por access_token
6. Agent acessa dados (até expiração do consent)
## Testes

```bash
# Rodar testes do banking agent
pytest tests/test_banking_agent.py -v

# Todos os testes que não precisam de serviços externos
pytest tests/test_banking_agent.py -v -k "not integration"
## Estrutura de Arquivos

specialized_agents/
├── banking_agent.py              # Agent orquestrador
├── banking/
│   ├── __init__.py
│   ├── models.py                 # Modelos de dados (Account, Transaction, etc.)
│   ├── base_connector.py         # Classe base dos conectores
│   ├── security.py               # OAuth2, criptografia, auditoria
│   ├── open_finance.py           # Utilitários Open Finance Brasil
│   ├── santander_connector.py    # Conector Santander
│   ├── itau_connector.py         # Conector Itaú
│   ├── nubank_connector.py       # Conector Nubank
│   └── mercadopago_connector.py  # Conector Mercado Pago
tests/
└── test_banking_agent.py         # Testes unitários
docs/
└── BANKING_AGENT.md              # Esta documentação
## Próximos Passos

- [ ] Integração com dashboard Streamlit (gráficos de gastos)
- [ ] Webhook para notificação de transações em tempo real
- [ ] Reconciliação automática entre bancos
- [ ] Suporte a Banco do Brasil e Bradesco
- [ ] Exportação OFX/CSV
- [ ] Machine Learning para detecção de anomalias
