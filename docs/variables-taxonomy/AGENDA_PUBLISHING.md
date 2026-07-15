# Agenda Diária — Variáveis de Publicação

Variáveis de ambiente lidas por `tools/daily_agenda_config.py` (fluxo
`tools/run_daily_agenda_broadcast.py`). Todas são opcionais: quando ausentes,
valem os defaults do `DEFAULT_CONFIG` / `panel_config.json`.

| Variável | Categoria | Propósito | Sensibilidade |
|---|---|---|---|
| `AGENDA_TELEGRAM_CHAT_ID` | integrations | Chat que recebe o resumo/preview da agenda diária no Telegram. | baixa (ID de chat) |
| `AGENDA_YOUTUBE_CHANNEL_ID` | integrations | Canal YouTube esperado para upload; usado para validar que o token OAuth pertence ao canal correto antes de publicar. | baixa (ID público) |
| `AGENDA_KWAI_HANDLE` | integrations | Handle/perfil Kwai esperado para a publicação da edição diária (`tools/kwai_agenda_publisher.py`). Informativo/validação; o login real vem do perfil Chrome persistente de `scripts/kwai/kwai_browser.py`. | baixa (handle público) |
| `KWAI_UPLOAD_URL` | integrations | Override da URL da página de upload usada pelo `KwaiPublisher` (`content_automation/publisher.py`). Default: Central do Criador (`https://m-creative.kwai.com/creator/center`); `www.kwai.com/upload` retorna 404 (validado 2026-07-15). | baixa (URL pública) |

Nenhuma dessas variáveis contém segredo; credenciais reais ficam em
`artifacts/daily_agenda/youtube/` (OAuth) e no perfil Chrome do Kwai.
