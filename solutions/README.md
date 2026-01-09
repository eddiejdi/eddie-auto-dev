# Soluções Auto-Desenvolvidas

Este diretório contém soluções desenvolvidas automaticamente pelo sistema de Auto-Desenvolvimento.

## Estrutura

```
solutions/
├── DEV_YYYYMMDDHHMMSS/     # ID único do desenvolvimento
│   ├── README.md           # Documentação da solução
│   ├── main.py             # Código principal
│   ├── requirements.txt    # Dependências
│   ├── tests/              # Testes
│   └── deploy.sh           # Script de deploy
```

## Deploy Automático

Quando uma nova solução é commitada neste diretório, o GitHub Actions automaticamente:

1. **Valida** - Verifica sintaxe e dependências
2. **Testa** - Executa testes automatizados
3. **Deploya** - Envia para o servidor (192.168.15.2)
4. **Notifica** - Envia mensagem no Telegram

## Como Usar

As soluções são criadas automaticamente pelo bot Telegram quando detecta que não consegue responder uma pergunta. O sistema:

1. Analisa os requisitos
2. Desenvolve o código
3. Cria testes
4. Faz commit no GitHub
5. O CI/CD faz o deploy

## Configuração

Secrets necessários no GitHub:
- `DEPLOY_SSH_KEY` - Chave SSH para acesso ao servidor
- `TELEGRAM_BOT_TOKEN` - Token do bot Telegram
- `TELEGRAM_CHAT_ID` - Chat ID para notificações
