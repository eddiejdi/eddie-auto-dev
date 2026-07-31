# FT_* (pipeline de fine-tuning QLoRA)

## Propósito
Família de variáveis de configuração dos scripts de fine-tuning QLoRA (transformers+peft+bitsandbytes, sem unsloth) do repo. Todas têm defaults sensatos embutidos no código — só precisam ser setadas para desviar do padrão.

## Consumidores
- `scripts/trading_analyst_finetune_peft.py` (original — trading-analyst)
- `scripts/whatsapp_toolcall_finetune_peft.py` (fork — tool-calling MCP do `shared-homelab`, 2026-07-29)

## Variáveis

| Nome | Tipo | Default | Descrição |
|---|---|---|---|
| `FT_BASE_MODEL_HF` | string | `unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit` | Repo HF do modelo base pré-quantizado 4-bit |
| `FT_DATASET_DIR` | path | varia por script | Diretório com os JSONL de treino |
| `FT_DATASET_FILE` | string | `whatsapp_toolcall_train.jsonl` | Nome do arquivo JSONL de treino (só no fork de tool-calling — o original usa múltiplos arquivos por `call_type`) |
| `FT_OUTPUT_DIR` | path | varia por script | Diretório de saída (adapter LoRA + modelo merged) |
| `FT_MAX_SEQ` | int | `2048` | Tamanho máximo de sequência na tokenização |
| `FT_EPOCHS` | float | `2` | Épocas de treino |
| `FT_BATCH` | int | `1` | Batch size por device |
| `FT_GRAD_ACCUM` | int | `8` | Passos de gradient accumulation |
| `FT_LORA_RANK` | int | `16` | Rank do LoRA |
| `FT_LORA_ALPHA` | int | `32` | Alpha do LoRA |
| `FT_LR` | float | `2e-4` | Learning rate |
| `FT_WARMUP` | int | `10` | Passos de warmup |
| `FT_MIN_SAMPLES` | int | `120` (trading) / `800` (tool-calling) | Piso de exemplos no dataset antes de liberar treino |
| `FT_TOOLS_PER_EXAMPLE` | int | `6` (só tool-calling) | Quantas ferramentas incluir no schema de cada exemplo de treino (a certa + distratoras) em vez das 33 completas — a schema completa sozinha já custa ~4.8k tokens (medido em produção), maior que qualquer `FT_MAX_SEQ` viável nesta GPU (RTX 3060 12GB estoura memória no cast fp32 dos logits do llama3.1, vocab=128k). Em produção o Ollama continua recebendo o schema completo; o modelo só precisa aprender o padrão de selecionar a ferramenta certa dentro do que for oferecido. |
| `FT_TIME_BUDGET_SECONDS` | int | `0` = sem limite (`600` no systemd) | Orçamento de tempo de parede de UM pacote de treino. Ao estourar, salva checkpoint e sai com sucesso; a invocação seguinte retoma do último checkpoint. Existe porque a GPU de treino é a mesma do Ollama de produção — treinar em pacotes de 10min de hora em hora evita segurar produção parada por ~7h seguidas. |
| `FT_SAVE_STEPS` | int | `2` | Frequência de checkpoint (em passos) quando `FT_TIME_BUDGET_SECONDS` está ativo. Baixo de propósito: cada passo já leva dezenas de segundos nesta GPU, então precisa salvar cedo pra garantir progresso dentro de um pacote de 10min. |

## Variáveis do orquestrador de pacotes (`scripts/whatsapp_toolcall_chunked_train.sh`)

| Nome | Tipo | Default | Descrição |
|---|---|---|---|
| `WHATSAPP_TOOLCALL_REPO` | path | `/home/homelab/myClaude` | Checkout do repo no host de treino |
| `WHATSAPP_TOOLCALL_FT_BASE` | path | `/home/homelab/finetune` | Raiz do ambiente de fine-tuning (venv, dados, saída) |

## Nota sobre o scanner automático
`tools/catalog_variables.py` só varre arquivos Python com nome `*config*`/`*settings*` — nenhum dos dois scripts acima bate esse padrão, então essas variáveis nunca são descobertas automaticamente pelo scanner apesar de serem reais e usadas em produção. Catalogadas manualmente aqui.

## Relacionadas
- [[HOMELAB_URL]], [[API_BASE_URL]]
