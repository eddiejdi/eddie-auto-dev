#!/usr/bin/env python3
"""QLoRA fine-tune do trading-analyst SEM unsloth (transformers + peft + bitsandbytes).

Robusto a versões: usa APIs nativas do transformers (que lê o tokenizer.json em
formato novo) + peft + bitsandbytes, evitando o acoplamento frágil do unsloth com
versões específicas do transformers (que causou impasse: unsloth 2024.9 exige
transformers<4.45, mas <4.45 traz tokenizers 0.19 que não lê o tokenizer do modelo).

Fonte = os JSONL do dataset builder / backfill (instruction/input/output). Treina um
adapter LoRA 4-bit e, com --merge, também salva o modelo fp16 merged (para depois
converter a GGUF na Fase 5). NÃO promove nada para produção.

Uso:
  python3 scripts/trading_analyst_finetune_peft.py --dry-run
  python3 scripts/trading_analyst_finetune_peft.py                 # treina adapter
  python3 scripts/trading_analyst_finetune_peft.py --merge         # + modelo fp16 merged
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
log = logging.getLogger("finetune-peft")

# Base pré-quantizada 4-bit (cacheada). transformers lê o quantization_config embutido.
BASE_MODEL = os.environ.get("FT_BASE_MODEL_HF", "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit")
DATASET_DIR = Path(os.environ.get("FT_DATASET_DIR", "/home/homelab/finetune/data"))
OUTPUT_DIR = Path(os.environ.get("FT_OUTPUT_DIR", "/home/homelab/finetune/work"))
LORA_OUTPUT = OUTPUT_DIR / "lora_adapters"
MERGED_OUTPUT = OUTPUT_DIR / "merged_model"

CALL_TYPES = ("controls", "window", "plan")

MAX_SEQ_LENGTH = int(os.environ.get("FT_MAX_SEQ", "2048"))
EPOCHS = float(os.environ.get("FT_EPOCHS", "2"))
BATCH_SIZE = int(os.environ.get("FT_BATCH", "1"))
GRAD_ACCUM = int(os.environ.get("FT_GRAD_ACCUM", "8"))
LORA_RANK = int(os.environ.get("FT_LORA_RANK", "16"))
LORA_ALPHA = int(os.environ.get("FT_LORA_ALPHA", "32"))
LR = float(os.environ.get("FT_LR", "2e-4"))
WARMUP = int(os.environ.get("FT_WARMUP", "10"))
MIN_SAMPLES = int(os.environ.get("FT_MIN_SAMPLES", "120"))

SYSTEM = (
    "Você é o trading-analyst. Responda EXATAMENTE no formato pedido em cada "
    "instrução (JSON compacto para controls/window; análise em PT-BR para plan)."
)


def load_examples(dataset_dir: Path) -> list[dict]:
    """Concatena os JSONL disponíveis (instruction/input/output)."""
    examples: list[dict] = []
    for call_type in CALL_TYPES:
        path = dataset_dir / f"trading_analyst_{call_type}.jsonl"
        if not path.exists():
            log.warning("Ausente: %s", path)
            continue
        n = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("instruction") and obj.get("output"):
                examples.append(obj)
                n += 1
        log.info("call_type=%s: %d exemplos", call_type, n)
    return examples


def train(dry_run: bool, do_merge: bool) -> int:
    examples = load_examples(DATASET_DIR)
    log.info("Total de exemplos: %d", len(examples))
    if len(examples) < MIN_SAMPLES:
        log.error("Dataset insuficiente: %d < %d", len(examples), MIN_SAMPLES)
        return 1
    if dry_run:
        log.info("DRY-RUN: %d exemplos OK (não treina)", len(examples))
        return 0

    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              DataCollatorForLanguageModeling, Trainer, TrainingArguments)
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from datasets import Dataset

    if not torch.cuda.is_available():
        log.error("CUDA indisponível!")
        return 1
    log.info("GPU: %s (%dMB livres)", torch.cuda.get_device_name(0),
             torch.cuda.mem_get_info(0)[0] // (1024 * 1024))

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Modelo pré-quantizado 4-bit (config embutida) na GPU 0.
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
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": ex["output"]},
        ]
        return tokenizer.apply_chat_template(messages, tokenize=False)

    def tokenize(batch: dict) -> dict:
        return tokenizer([to_text({"instruction": i, "input": inp, "output": o})
                          for i, inp, o in zip(batch["instruction"], batch["input"], batch["output"])],
                         truncation=True, max_length=MAX_SEQ_LENGTH)

    ds = Dataset.from_list(examples).map(
        tokenize, batched=True, remove_columns=["instruction", "input", "output"])
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
    parser = argparse.ArgumentParser(description="QLoRA trading-analyst (peft puro, sem unsloth)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", action="store_true", help="Também salva o modelo fp16 merged")
    args = parser.parse_args()
    return train(args.dry_run, args.merge)


if __name__ == "__main__":
    sys.exit(main())
