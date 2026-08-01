# MAX_TOOL_ROUNDS

## Propósito
Teto de rodadas do loop de tool-calling do bot do WhatsApp (`shared-homelab`) — quantas vezes o ciclo "modelo chama ferramenta → resultado volta como mensagem `tool` → modelo é chamado de novo" pode repetir antes de desistir e responder com uma mensagem de timeout, evitando loop infinito se o modelo insistir em chamar ferramentas.

## Escopo
- **Consumidor**: `scripts/misc/whatsapp_bot.py` (`WhatsAppBot._process_with_tools`).
- **Type**: integer, default `3`.
- **Não confundir com** `INTENT_EXP_MIN` (minutos até uma aprovação pendente expirar — trava humana via Telegram) nem com `MAX_ROUNDS`/similares de outros pipelines do repo — este é local ao loop de tool-calling do WhatsApp bot.

## Relacionadas
- [[HOMELAB_URL]], [[API_BASE_URL]]
