# 📧 Integração Gmail - Eddie Assistant

## Visão Geral

Esta integração permite que o Eddie Assistant leia, classifique e limpe seus emails automaticamente.

### Funcionalidades

- 📬 **Listar emails** - Ver últimos emails da caixa de entrada
- 📊 **Analisar inbox** - Relatório completo com classificação
- 🧹 **Limpar spam/promoções** - Move emails irrelevantes para lixeira
- 🚫 **Marcar como spam** - Marcar emails específicos
- 🗑️ **Mover para lixeira** - Excluir emails (não permanente)
- 📭 **Contar não lidos** - Ver quantos emails não lidos

## Instalação

### 1. Instalar dependências

```bash
cd /home/homelab/myClaude
source venv/bin/activate
pip install google-auth-oauthlib google-api-python-client
```

### 2. Configurar credenciais Google

Se você já configurou o Google Calendar, as credenciais serão reutilizadas automaticamente!

Caso contrário:

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto (ou use existente)
3. Ative a **Gmail API**
4. Crie credenciais OAuth 2.0 (Desktop App)
5. Baixe o arquivo `credentials.json`
6. Coloque em: `/home/homelab/myClaude/gmail_data/credentials.json`

### 3. Autenticar

```bash
python email_cleaner_runner.py --auth
```

Ou via Telegram/WhatsApp:
```
/gmail auth
```

## Uso

### Via Linha de Comando

```bash
# Menu interativo
python email_cleaner_runner.py

# Apenas analisar
python email_cleaner_runner.py --analyze

# Prévia da limpeza
python email_cleaner_runner.py --clean

# Executar limpeza
python email_cleaner_runner.py --clean --confirm
```

### Via Telegram

```
/gmail ajuda         - Ver todos os comandos
/gmail listar        - Ver últimos 20 emails
/gmail listar 50     - Ver últimos 50 emails
/gmail analisar      - Relatório completo
/gmail nao_lidos     - Contar emails não lidos
/gmail limpar        - Prévia da limpeza
/gmail limpar confirmar - Executar limpeza
```

### Via WhatsApp

Os mesmos comandos funcionam:
```
/gmail ajuda
/gmail listar
/gmail analisar
/gmail limpar
```

### Linguagem Natural

Você também pode usar linguagem natural:
- "Ver meus emails"
- "Quantos emails não lidos eu tenho?"
- "Limpar minha caixa de entrada"
- "Analisar spam"

## Como a Classificação Funciona

### Critérios de Spam/Irrelevante (score alto = spam)

- Domínios de marketing (mailchimp, sendgrid, etc.)
- Palavras-chave de spam (promoção, desconto, grátis, etc.)
- Remetente noreply
- Labels do Gmail (SPAM, PROMOTIONS)
- Emails antigos não lidos

### Critérios de Importante (score baixo = importante)

- Domínios confiáveis (gmail, github, aws, etc.)
- Menção a "Edenilson" ou "Eddie"
- Labels (IMPORTANT, STARRED, PERSONAL)
- Palavras importantes (pagamento, reunião, urgente)

### Pontuação

| Score | Classificação |
|-------|---------------|
| >= 40 | 🚫 SPAM/Irrelevante |
| >= 20 | 📢 Promocional |
| <= -20 | ⭐ Importante |
| Outros | 📧 Normal |

## Segurança

- **Não deleta permanentemente**: A limpeza move para lixeira
- **Prévia antes de limpar**: Sempre mostra o que será removido
- **Whitelist de domínios**: Domínios confiáveis não são removidos
- **Detecção inteligente**: Emails pessoais são preservados

## Arquivos

```
gmail_integration.py     - Módulo principal
email_cleaner_runner.py  - Script de execução
gmail_data/              - Diretório de dados
├── credentials.json     - Credenciais Google
└── token.pickle         - Token de acesso
```

## Troubleshooting

### "Não autenticado"
```bash
python email_cleaner_runner.py --auth
```

### "Credenciais não encontradas"
Coloque o arquivo `credentials.json` em:
`/home/homelab/myClaude/gmail_data/credentials.json`

Ou copie do Calendar:
```bash
cp calendar_data/credentials.json gmail_data/
```

### "Escopo insuficiente"
Se você já tinha autenticação do Calendar, pode precisar reautenticar:
```bash
rm gmail_data/token.pickle
python email_cleaner_runner.py --auth
```

## Integração com Bots

A integração está habilitada automaticamente nos bots:

- **Telegram Bot**: `/gmail` + detecção de linguagem natural
- **WhatsApp Bot**: `/gmail` + detecção de linguagem natural

## Customização

### Adicionar domínios à whitelist

Edite `gmail_integration.py`:
```python
WHITELIST_DOMAINS = [
    'gmail.com', 'hotmail.com',
    'seu-dominio.com.br',  # Adicione aqui
]
```

### Adicionar palavras importantes

```python
IMPORTANT_KEYWORDS = [
    'edenilson', 'eddie',
    'palavra-importante',  # Adicione aqui
]
```

## Changelog

### v1.0.0
- Integração inicial com Gmail API
- Classificação automática de emails
- Limpeza de spam e promoções
- Integração Telegram e WhatsApp
- Detecção de linguagem natural
