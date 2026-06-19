# Fluxo X/Twitter no Bot do Telegram

## Escopo

Este documento consolida a implementação, a validação e o deploy do fluxo de download de posts do X/Twitter no bot principal do Telegram.

O objetivo da mudança foi cobrir quatro comportamentos operacionais:

1. localizar o handler do comando `/x`
2. baixar texto e todas as mídias do post
3. detectar links do X/Twitter mesmo sem o comando `/x`
4. suportar URLs do formato `x.com/i/status/<id>` em ambiente headless no homelab

## Arquivos envolvidos

- `telegram_bot.py`
- `scripts/misc/telegram_bot.py`
- `tests/test_telegram_bot_twitter_x.py`
- `deploy.sh`

## Fluxo implementado

### 1. Comando explícito `/x`

O handler principal continua sendo `_handle_twitter_download()`.

Fluxo:

1. valida a URL recebida
2. extrai `user` e `tweet_id`
3. tenta obter texto e mídias pelo fxtwitter quando a URL possui username real
4. faz fallback para `yt-dlp` quando o fxtwitter não devolve mídia
5. envia primeiro o texto do post, quando disponível
6. envia cada mídia individualmente no Telegram

### 2. Auto-detecção sem `/x`

Foi adicionada detecção de links de post do X/Twitter em mensagens livres com `_extract_twitter_status_url()`.

Critério da detecção:

- aceita apenas URLs com padrão de post: domínio `x.com` ou `twitter.com` seguido de `/status/<id>`
- remove pontuação comum no final da frase para reduzir falsos positivos de cola em texto livre

Quando uma mensagem comum contém um link válido, `handle_message()` redireciona automaticamente para `_handle_twitter_download()`.

## Estratégia de download

### fxtwitter

O fxtwitter é usado como caminho preferencial quando a URL possui username real, porque ele fornece:

- texto do post
- lista completa de mídias
- classificação de mídia por tipo

Esse caminho permite enviar texto e múltiplos anexos com melhor previsibilidade.

### yt-dlp

O `yt-dlp` é usado em dois cenários:

1. fallback quando o fxtwitter não retorna mídia
2. caminho direto para URLs `x.com/i/status/<id>` ou `x.com/web/status/<id>`

O binário preferido é o do ambiente virtual do bot:

- `/home/homelab/myClaude/.venv/bin/yt-dlp`

Se o arquivo de cookies existir, ele é usado:

- `data/twitter_cookies_filtered.txt`

O fallback `--cookies-from-browser firefox` foi removido porque o serviço roda em ambiente headless no homelab e falhava ao procurar perfis inexistentes do Firefox.

## Correção específica para `x.com/i/status/<id>`

### Problema observado

Links compartilhados pelo aplicativo móvel do X chegaram no formato:

```text
https://x.com/i/status/2055745847632044059
```

Nesse formato, o trecho capturado como usuário é `i`.

Isso causava dois problemas:

1. o fxtwitter recebia `user=i` e devolvia `HTTP 403`
2. o fallback do `yt-dlp` usava `--cookies-from-browser firefox` e falhava no servidor headless

### Solução aplicada

Foi mantido o método `_resolve_twitter_user()` como tentativa leve de resolução por redirect, mas o fluxo operacional foi ajustado para não depender disso.

Regra final:

- se o usuário extraído for `i` ou `web`, o bot pula o fxtwitter diretamente
- nesses casos, o download vai direto para o `yt-dlp`

Isso elimina a dependência de um username canônico para posts públicos compartilhados pelo app.

## Comportamento final

### URLs com username real

Exemplo:

```text
https://x.com/alguem/status/1234567890
```

Fluxo esperado:

1. tenta fxtwitter
2. envia texto do post quando houver
3. baixa e envia todas as mídias
4. se o fxtwitter não trouxer mídia, usa yt-dlp como fallback

### URLs `i/status` ou `web/status`

Exemplo:

```text
https://x.com/i/status/2055745847632044059
```

Fluxo esperado:

1. detecta link automaticamente mesmo sem `/x`
2. pula fxtwitter
3. executa `yt-dlp` diretamente
4. envia a mídia encontrada no Telegram

Observação: nesse caminho, o texto do post pode não ser enviado se vier apenas do `yt-dlp`, já que a extração textual depende do caminho do fxtwitter.

## Deploy

### Homelab

Arquivo implantado:

- `/home/homelab/myClaude/telegram_bot.py`

Serviço reiniciado:

- `eddie-telegram-bot.service`

O `deploy.sh` recebeu alvo específico para o bot:

- `bot`
- `logs-bot`

Isso permite publicar apenas o bot sem depender do fluxo completo de `deploy.sh all`.

### GitHub

As mudanças foram publicadas no branch:

- `fix/grafana-symbol-mismatch-no-data`

Commit principal do ajuste do fluxo X/Twitter:

- `9ef44696` — `fix(twitter): skip fxtwitter for i/status URLs, remove firefox cookie fallback`

## Testes adicionados

Arquivo:

- `tests/test_telegram_bot_twitter_x.py`

Cobertura funcional adicionada:

1. envia texto e múltiplas mídias quando o fxtwitter retorna conteúdo
2. usa fallback do `yt-dlp` quando o fxtwitter não retorna mídia
3. detecta link de post em texto livre sem `/x`
4. dispara o fluxo automaticamente a partir de `handle_message()`

## Validação executada

### Validação em ambiente real

Teste executado com o link:

```text
https://x.com/i/status/2055745847632044059
```

Resultado observado nos logs do serviço:

1. auto-detecção sem `/x`
2. entrada em `_handle_twitter_download()`
3. desvio correto para `yt-dlp`
4. envio concluído com sucesso

Trecho validado operacionalmente:

```text
[Twitter] URL sem username real, usando yt-dlp diretamente…
[Twitter] Conteúdo enviado com sucesso: 1 mídia(s)
```

Também foi validado manualmente no homelab que o `yt-dlp` consegue resolver a URL pública do X e baixar a mídia correspondente.

## Limitações atuais

1. o método `_resolve_twitter_user()` permanece como tentativa auxiliar, mas não deve ser tratado como mecanismo principal para URLs `i/status`
2. quando o fluxo passa direto pelo `yt-dlp`, o envio do texto do post não é garantido
3. `deploy.sh all` continua sujeito a falhas externas por testes preexistentes não relacionados a este fluxo

## Estado final

No estado atual, o bot suporta:

- comando `/x <link>`
- detecção automática de links X/Twitter em mensagens livres
- envio de texto do post quando disponível pelo fxtwitter
- envio de múltiplas mídias
- fallback funcional com `yt-dlp`
- tratamento operacional de links `x.com/i/status/<id>` em produção