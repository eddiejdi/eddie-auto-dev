#!/usr/bin/env python3
"""QLoRA fine-tune (transformers + peft + bitsandbytes, sem unsloth) do modelo
de tool-calling do `shared-homelab` — fork de `trading_analyst_finetune_peft.py`
adaptado pro domínio de chamadas de ferramentas MCP em vez de análise de trading.

Fork em vez de parametrizar o script original: os dois domínios têm formato
de exemplo (tool_calls, segundo turno com role=tool) e prompt de sistema
diferentes o bastante pra não valer acoplar; a migração do pipeline de
trading está fora de escopo aqui.

Fonte = os JSONL do `whatsapp_toolcall_dataset_builder.py` (split "train";
"test" fica reservado pro shadow-eval, nunca entra no treino). Treina um
adapter LoRA 4-bit e, com --merge, salva também o modelo fp16 merged (pra
depois converter a GGUF). NÃO promove nada pra produção.

Verificação crítica embutida (também em --dry-run): confirma que o
chat_template do tokenizer do BASE_MODEL suporta nativamente `tool_calls`
no turno do assistente — treinar com `apply_chat_template(..., tools=...)`
só faz sentido se o mesmo template for usado depois pelo Ollama ao servir.

Uso:
  python3 scripts/whatsapp_toolcall_finetune_peft.py --dry-run
  python3 scripts/whatsapp_toolcall_finetune_peft.py                 # treina adapter
  python3 scripts/whatsapp_toolcall_finetune_peft.py --merge         # + modelo fp16 merged
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("whatsapp-toolcall-finetune")

sys.path.insert(0, str(Path(__file__).resolve().parent / "misc"))
import mcp_tool_bridge  # noqa: E402

# Mesmo repo HF pré-quantizado 4-bit já usado (e comprovado no mesmo venv/GPU)
# pelo pipeline de fine-tuning do trading-analyst — casa com o `FROM llama3.1:8b`
# de ollama/modelfiles/shared-homelab.Modelfile.
BASE_MODEL = os.environ.get("FT_BASE_MODEL_HF", "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit")
DATASET_DIR = Path(os.environ.get("FT_DATASET_DIR", "/home/homelab/finetune/data-toolcall"))
OUTPUT_DIR = Path(os.environ.get("FT_OUTPUT_DIR", "/home/homelab/finetune/work-toolcall"))
LORA_OUTPUT = OUTPUT_DIR / "lora_adapters"
MERGED_OUTPUT = OUTPUT_DIR / "merged_model"

DATASET_FILE = os.environ.get("FT_DATASET_FILE", "whatsapp_toolcall_train.jsonl")

MAX_SEQ_LENGTH = int(os.environ.get("FT_MAX_SEQ", "3072"))  # schemas de tool ocupam mais contexto
EPOCHS = float(os.environ.get("FT_EPOCHS", "2"))
BATCH_SIZE = int(os.environ.get("FT_BATCH", "1"))
GRAD_ACCUM = int(os.environ.get("FT_GRAD_ACCUM", "8"))
LORA_RANK = int(os.environ.get("FT_LORA_RANK", "16"))
LORA_ALPHA = int(os.environ.get("FT_LORA_ALPHA", "32"))
LR = float(os.environ.get("FT_LR", "2e-4"))
WARMUP = int(os.environ.get("FT_WARMUP", "10"))
MIN_SAMPLES = int(os.environ.get("FT_MIN_SAMPLES", "800"))

# Versão condensada da persona homelab — a instrução detalhada de
# tool-calling propriamente dita fica embutida nos pesos pelo treino, não
# repetida aqui em detalhe (evita competir por contexto com os schemas).
SYSTEM = (
    "Você é o assistente pessoal de infraestrutura do Edenilson (self-chat "
    "no WhatsApp). Quando o pedido exigir dados ou ação sobre o homelab "
    "(trading, banco, bus de comunicação, segredos, memória compartilhada), "
    "chame a ferramenta certa em vez de inventar a resposta. Para conversa "
    "normal, responda direto em português, sem chamar ferramenta nenhuma."
)


def load_examples(dataset_dir: Path, filename: str) -> list[dict]:
    path = dataset_dir / filename
    if not path.exists():
        log.error("Dataset ausente: %s (rode whatsapp_toolcall_dataset_builder.py antes)", path)
        return []
    examples: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("instruction"):
            examples.append(obj)
    log.info("%s: %d exemplos", path, len(examples))
    return examples


def _verify_tool_call_template(tokenizer) -> bool:
    """Confirma que o chat_template do tokenizer sabe renderizar tool_calls.

    Sem isso, treinar com apply_chat_template(tools=...) não teria relação
    com o formato real que o Ollama usa ao servir com tools= — o fine-tune
    ensinaria um formato que nunca é o que roda em produção.
    """
    template = getattr(tokenizer, "chat_template", "") or ""
    if "tool_calls" in template or "tool_call" in template:
        log.info("chat_template do tokenizer suporta tool_calls — OK.")
        return True
    log.error(
        "O chat_template de %s NÃO parece suportar tool_calls nativamente "
        "('tool_call'/'tool_calls' não encontrado no template). Treinar assim "
        "ensinaria um formato divorciado do que o Ollama realmente serve. "
        "Revise BASE_MODEL antes de continuar (ver plano seção 4).",
        BASE_MODEL,
    )
    return False


def train(dry_run: bool, do_merge: bool) -> int:
    examples = load_examples(DATASET_DIR, DATASET_FILE)
    log.info("Total de exemplos de treino: %d", len(examples))
    if len(examples) < MIN_SAMPLES:
        log.error("Dataset insuficiente: %d < %d (MIN_SAMPLES)", len(examples), MIN_SAMPLES)
        return 1

    tool_schemas = mcp_tool_bridge.build_ollama_tool_schemas()
    log.info("Schema de %d ferramentas carregado da bridge.", len(tool_schemas))

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if not _verify_tool_call_template(tokenizer):
        return 1

    if dry_run:
        log.info("DRY-RUN: %d exemplos + template OK (não treina)", len(examples))
        return 0

    import torch
    from transformers import (AutoModelForCausalLM,
                              DataCollatorForLanguageModeling, Trainer, TrainingArguments)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from datasets import Dataset

    if not torch.cuda.is_available():
        log.error("CUDA indisponível!")
        return 1
    log.info("GPU: %s (%dMB livres)", torch.cuda.get_device_name(0),
             torch.cuda.mem_get_info(0)[0] // (1024 * 1024))

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, device_map={"": 0}, torch_dtype=torch.float16,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=LORA_RANK, lora_alpha=LORA_ALPHA, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    def to_text(ex: dict) -> str:
        user = (ex["instruction"] + (ex.get("input") or "")).strip()
        tool_calls = ex.get("tool_calls") or []
        tool_result = ex.get("tool_result")

        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]

        if tool_calls and tool_result is not None:
            # segundo turno: chama a ferramenta, recebe o resultado, responde em texto
            messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            messages.append({
                "role": "tool",
                "name": tool_calls[0]["function"]["name"],
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
            messages.append({"role": "assistant", "content": ex.get("output") or ""})
        elif tool_calls:
            # turno único: só a chamada de ferramenta
            messages.append({"role": "assistant", "content": ex.get("output") or "", "tool_calls": tool_calls})
        else:
            # negativo/near-miss: resposta conversacional normal, sem tool_calls
            messages.append({"role": "assistant", "content": ex.get("output") or "Certo."})

        return tokenizer.apply_chat_template(messages, tools=tool_schemas or None, tokenize=False)

    texts = [to_text(ex) for ex in examples]
    ds = Dataset.from_dict({"text": texts})

    def tokenize(batch: dict) -> dict:
        return tokenizer(batch["text"], truncation=True, max_length=MAX_SEQ_LENGTH)

    ds = ds.map(tokenize, batched=True, remove_columns=["text"])
    log.info("Dataset tokenizado: %d exemplos", len(ds))

    args = TrainingArguments(
        output_dir=str(LORA_OUTPUT), per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM, num_train_epochs=EPOCHS,
        learning_rate=LR, warmup_steps=WARMUP, fp16=True, logging_steps=5,
        save_strategy="no", optim="paged_adamw_8bit", seed=42, report_to="none",
    )
    trainer = Trainer(
        model=model, args=args, train_dataset=ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    log.info("Treinando...")
    result = trainer.train()
    log.info("Loss final: %.4f | steps: %d", result.training_loss, result.global_step)

    LORA_OUTPUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(LORA_OUTPUT))
    tokenizer.save_pretrained(str(LORA_OUTPUT))
    log.info("LoRA salvo em %s", LORA_OUTPUT)

    if do_merge:
        log.info("Merge LoRA → fp16 (RAM-heavy)...")
        merged = model.merge_and_unload()
        MERGED_OUTPUT.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(MERGED_OUTPUT), safe_serialization=True)
        tokenizer.save_pretrained(str(MERGED_OUTPUT))
        log.info("Merged fp16 salvo em %s", MERGED_OUTPUT)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="QLoRA tool-calling shared-homelab (peft puro, sem unsloth)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", action="store_true", help="Também salva o modelo fp16 merged")
    args = parser.parse_args()
    return train(args.dry_run, args.merge)


if __name__ == "__main__":
    sys.exit(main())
