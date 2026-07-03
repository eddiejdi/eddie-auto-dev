# Migração de modelos LLM chineses → aprovados — 2026-07-03

Política de soberania e privacidade de dados (2026-07-01): Qwen, DeepSeek, ERNIE,
ChatGLM, InternLM e Baichuan banidos do homelab. Alternativas aprovadas: Mistral,
Llama, Gemma, Phi.

## Mapa de substituição

| Anterior | Novo | Onde |
|---|---|---|
| `qwen3:0.6b` | `gemma3:1b` | GPU1 orquestração, fallbacks trade params/window, warmup, selfheal |
| `qwen3-fast:gpu1` | `gemma3-fast:gpu1` | plano do perfil aggressive, MCP LLM_GPU1_MODEL (Modelfile novo em `models/Modelfile.gemma3-fast`) |
| `qwen3:1.7b` | `phi4-mini:latest` (geral) / `gemma3:1b` (GPU1) | sentiment exporter, offloader, OCR |
| `qwen2.5:3b` | `phi4-mini:latest` | planner trading, NAS, telegram MCP, ollama_client |
| `qwen2.5:1.5b*` | `gemma3:1b` / `llama3.2:1b` | bn_acervo, TTS fallback |
| `qwen2.5-coder:7b` | `mistral:7b` | dev_agent, eddie-* Modelfiles, selfheal exporter, copilot router |
| `deepseek-coder:6.7b` | `phi4-mini:latest` | fallback dev_agent |
| `deepseek-coder-v2:16b` | `mistral-nemo:12b` | heavy_model specialized_agents |
| `qwen3:8b` | `mistral:7b` | wiki_bulk_publish |
| trading-analyst (base qwen3:14b) | rebuild `FROM llama3.1:8b` (Modelfile já no repo) | **produção ainda roda a versão qwen3 14.8B** |

Escopo: código/configs de runtime, systemd, Modelfiles, scripts e testes.
Relatórios e docs históricos (`VALIDATION_REPORT_*`, `CONVERSAS_*` etc.) foram
mantidos como registro. `tools/proxy_tool_interceptor.py` teve as famílias qwen
removidas da lista de tool-capable.

## Regressão (2026-07-03)

Grupos afetados: 66 passed + 174 passed. 11 falhas restantes são idênticas ao
baseline HEAD (poluição de `sys.modules` entre testes, pré-existente) — zero
regressões introduzidas. Atenção: `tests/test_rss_llm_trainer.py` regenera
`grafana/exporters/Modelfile.trading-sentiment` ao rodar; conferir `FROM` após
rodar a suíte.

## Deploy — EXECUTADO em 2026-07-03 ~13h30

Todas as etapas abaixo foram concluídas: pulls (mistral:7b, llama3.1:8b,
mistral-nemo:12b, phi4-mini na NAS), gemma3-fast:gpu1 e trading-sentiment
criados, trading-analyst reconstruído FROM llama3.1:8b (8B Q4_K_M, ~4.6GB VRAM),
~20 units systemd do host migradas (backups `.bak.<ts>`), código de produção em
/apps/crypto-trader e /home/homelab/myClaude migrado in-place (backups idem),
watchdog GPU1 agora pina gemma3:1b. Serviços reiniciados e validados: agentes
retomaram ciclo com posições intactas, AI plan/window gerando via trading-analyst
novo, gemma3-fast respondendo em ~0.8s. VRAM sem nenhum modelo chinês.

**Pendências**: (1) `ollama rm` dos modelos qwen/deepseek no disco — mantidos
para rollback até validar o comportamento do trading-analyst novo por alguns
dias; (2) commitar/mergear esta branch para o runner CI/CD reconciliar o deploy
manual; (3) qwen2.5:3b ainda no disco da NAS (não carregado).

Etapas originais do plano (referência):

1. **Pulls**: `ollama pull mistral:7b` (GPU0) e `mistral-nemo:12b` (GPU0);
   `phi4-mini`/`gemma3:1b`/`llama3.2:1b` já baixados.
2. **Criar gemma3-fast:gpu1** na instância GPU1:
   `OLLAMA_HOST=127.0.0.1:11435 ollama create gemma3-fast:gpu1 -f models/Modelfile.gemma3-fast`
3. **Recriar trading-sentiment**: `ollama create trading-sentiment -f grafana/exporters/Modelfile.trading-sentiment`
4. **Rebuild trading-analyst** (`FROM llama3.1:8b`) — ⚠️ trading ao vivo com
   dinheiro real; exige validação/backtest antes de trocar (feedback_btc_trading_safety).
5. **Sync dos systemd** (drop-ins crypto-agent@*, ollama-gpu1, ollama-warmup,
   rss-sentiment-exporter, post-boot-check) + `daemon-reload` + restart na janela adequada.
6. **Checar env files no host** (`/etc/default/eddie-common` e afins): overrides
   `OLLAMA_*MODEL*` podem ainda apontar para qwen e vencem os defaults do código.
7. **Remover os modelos banidos** (`ollama rm qwen* deepseek*` em GPU0/GPU1/NAS)
   somente após todos os serviços validados com os substitutos.
