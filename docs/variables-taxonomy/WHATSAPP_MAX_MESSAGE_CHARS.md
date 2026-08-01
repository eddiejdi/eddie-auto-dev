# WHATSAPP_MAX_MESSAGE_CHARS

## Propósito
Tamanho máximo (em caracteres) de uma mensagem de saída do bot antes de ser quebrada em várias mensagens numeradas `(i/N)`. WhatsApp aceita textos bem maiores, mas bolhas muito longas ficam ruins de ler no celular.

## Escopo
- **Consumidor**: `scripts/misc/whatsapp_bot.py` (`WAHAClient._split_message_chunks` / `WAHAClient.send_text`).
- **Default**: `3500`.
- **Mínimo efetivo**: `500` (valores menores são elevados para 500).

## Comportamento
`send_text` quebra o texto em partes ≤ `WHATSAPP_MAX_MESSAGE_CHARS`, preferindo cortar em fronteira de parágrafo (`\n\n`), depois linha (`\n`), depois espaço — só corta no meio de uma palavra como último recurso. Quando há mais de uma parte, cada uma é enviada como mensagem separada, em sequência, prefixada com `(i/N)` e com um pequeno intervalo entre envios (evita fora-de-ordem/rate-limit no WAHA).

## Relacionadas
- [[WHATSAPP_BOT_TAG]], [[WHATSAPP_TOOL_CALLING]]
