# WHATSAPP_TOOL_CALLING

## Propósito
Kill-switch do tool-calling MCP do bot do WhatsApp (modelo `shared-homelab`). Quando ligado, o modelo recebe o schema das 33 ferramentas do `homelab_mcp_server.py` e pode chamá-las sozinho; quando desligado, o bot volta ao caminho conversacional anterior (+ atalhos determinísticos de calendário/gmail/relatórios).

## Escopo
- **Consumidor**: `scripts/misc/whatsapp_bot.py` (`TOOL_CALLING_ENABLED`).
- **Default**: `0` (desligado).
- **Ligar**: `WHATSAPP_TOOL_CALLING=1` no drop-in `systemd/eddie-whatsapp-bot.service.d/env.conf`.

## Por que o default é desligado
Medido em produção em 2026-07-29: o `llama3.1:8b` **sem fine-tune** escolhe a ferramenta errada mesmo recebendo o schema completo. Num pedido de *"crie um evento no meu Google Calendar"* ele chamou `bus_publish` (publicar no bus interno de agentes), que é classificada como risco alto — o turno virou "🔒 aguardando aprovação no Telegram" e expirou 11 min depois sem resposta útil. Isso é pior que o comportamento anterior (resposta conversacional direta).

Só religar depois que o candidato treinado (`scripts/whatsapp_toolcall_finetune_peft.py`) passar no shadow-eval (`scripts/whatsapp_toolcall_shadow_eval.py`) com taxa aceitável de acerto de ferramenta e de falso-positivo — especialmente nas ferramentas de risco alto/crítico.

## Relacionadas
- [[HOMELAB_URL]], [[API_BASE_URL]], [[MAX_TOOL_ROUNDS]]
