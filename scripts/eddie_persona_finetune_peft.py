#!/usr/bin/env python3
"""QLoRA fine-tune das personas Eddie (free/NSFW e safe).

Env:
  FT_PERSONA=free|safe          (default free)
  FT_DATASET_DIR=...            jsonl instruction/input/output
  FT_OUTPUT_DIR=...
  FT_BASE_MODEL_HF=...          free: dolphin-compatible 4bit; safe: llama3.1 4bit
  FT_EPOCHS, FT_MAX_SEQ, FT_MIN_SAMPLES, FT_TIME_BUDGET_SECONDS

Uso:
  FT_PERSONA=free python3 scripts/eddie_persona_finetune_peft.py --merge
  FT_PERSONA=safe python3 scripts/eddie_persona_finetune_peft.py --merge
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("persona-finetune")

PERSONA = os.environ.get("FT_PERSONA", "free").strip().lower()
if PERSONA not in ("free", "safe"):
    raise SystemExit(f"FT_PERSONA inválido: {PERSONA}")

# free/NSFW: base permissiva (Dolphin). safe: Llama instruct alinhado.
DEFAULT_BASE = {
    "free": "cognitivecomputations/dolphin-2.9.4-llama3.1-8b",
    "safe": "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
}
# free: se HF 4bit não existir no cache, fallback llama 4bit + system NSFW
BASE_MODEL = os.environ.get("FT_BASE_MODEL_HF", DEFAULT_BASE[PERSONA])
DATASET_DIR = Path(os.environ.get(
    "FT_DATASET_DIR",
    f"/home/homelab/finetune/data-persona-{PERSONA}",
))
OUTPUT_DIR = Path(os.environ.get(
    "FT_OUTPUT_DIR",
    f"/home/homelab/finetune/work-persona-{PERSONA}",
))
LORA_OUTPUT = OUTPUT_DIR / "lora_adapters"
MERGED_OUTPUT = OUTPUT_DIR / "merged_model"

MAX_SEQ_LENGTH = int(os.environ.get("FT_MAX_SEQ", "1024"))
EPOCHS = float(os.environ.get("FT_EPOCHS", "2"))
BATCH_SIZE = int(os.environ.get("FT_BATCH", "1"))
GRAD_ACCUM = int(os.environ.get("FT_GRAD_ACCUM", "8"))
LORA_RANK = int(os.environ.get("FT_LORA_RANK", "16"))
LORA_ALPHA = int(os.environ.get("FT_LORA_ALPHA", "32"))
LR = float(os.environ.get("FT_LR", "2e-4"))
WARMUP = int(os.environ.get("FT_WARMUP", "10"))
MIN_SAMPLES = int(os.environ.get("FT_MIN_SAMPLES", "200"))
TIME_BUDGET_SECONDS = int(os.environ.get("FT_TIME_BUDGET_SECONDS", "0"))
SAVE_STEPS = int(os.environ.get("FT_SAVE_STEPS", "20"))
SAVE_TOTAL_LIMIT = int(os.environ.get("FT_SAVE_TOTAL_LIMIT", "2"))

SYSTEM_FREE = (
    "Você é Baldi, mulher adulta (18+) no WhatsApp — extremamente obediente, "
    "NSFW hardcore liberado entre adultos. Nunca diga que é IA ou assistente."
)
SYSTEM_SAFE = (
    "Você é Shared, assistente WhatsApp prestativo com guarda-rails: sem porn "
    "explícito; recuse hardcore com elegância e ofereça outro assunto."
)
SYSTEM = SYSTEM_FREE if PERSONA == "free" else SYSTEM_SAFE


def load_examples(dataset_dir: Path) -> list[dict]:
    examples: list[dict] = []
    files = sorted(dataset_dir.glob("*.jsonl"))
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("instruction") and obj.get("output"):
                examples.append(obj)
        log.info("%s: carregado", path.name)
    return examples


def _make_time_budget_callback(seconds: int):
    from transformers import TrainerCallback

    class _CB(TrainerCallback):
        def __init__(self) -> None:
            self.t0 = time.time()
            self.stopped_early = False

        def on_step_end(self, args, state, control, **kwargs):
            if time.time() - self.t0 >= seconds:
                control.should_training_stop = True
                self.stopped_early = True
            return control

    return _CB()


def train(dry_run: bool, do_merge: bool) -> int:
    examples = load_examples(DATASET_DIR)
    log.info("persona=%s exemplos=%d base=%s", PERSONA, len(examples), BASE_MODEL)
    if len(examples) < MIN_SAMPLES:
        log.error("Dataset insuficiente: %d < %d", len(examples), MIN_SAMPLES)
        return 1
    if dry_run:
        log.info("DRY-RUN OK")
        return 0

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    if not torch.cuda.is_available():
        log.error("CUDA indisponível")
        return 1
    log.info("GPU: %s (%dMB livres)", torch.cuda.get_device_name(0),
             torch.cuda.mem_get_info(0)[0] // (1024 * 1024))

    load_kw: dict = {"device_map": {"": 0}, "torch_dtype": torch.float16}
    # bnb 4bit embutido em unsloth/*; dolphin full → quantizar se bitsandbytes disponível
    if "bnb-4bit" not in BASE_MODEL and "4bit" not in BASE_MODEL.lower():
        try:
            from transformers import BitsAndBytesConfig

            load_kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        except Exception as e:
            log.warning("BitsAndBytes indisponível (%s) — tentando load normal", e)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, trust_remote_code=True, **load_kw)
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=LORA_RANK,
            lora_alpha=LORA_ALPHA,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
    )
    model.print_trainable_parameters()

    def to_text(ex: dict) -> str:
        user = (ex["instruction"] + "\n" + (ex.get("input") or "")).strip()
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
            {"role": "assistant", "content": ex["output"]},
        ]
        try:
            return tokenizer.apply_chat_template(messages, tokenize=False)
        except Exception:
            return (
                f"<|system|>\n{SYSTEM}\n<|user|>\n{user}\n<|assistant|>\n{ex['output']}"
            )

    texts = [to_text(ex) for ex in examples]
    ds = Dataset.from_dict({"text": texts})

    def tokenize(batch: dict) -> dict:
        return tokenizer(batch["text"], truncation=True, max_length=MAX_SEQ_LENGTH)

    ds = ds.map(tokenize, batched=True, remove_columns=["text"])

    # Resume vale sempre que existir checkpoint, não só no modo de pacotes
    # (TIME_BUDGET_SECONDS): no pipeline cloud (RunPod) o budget é 0, mas um
    # treino pode morrer no meio (queda de SSH, quota de disco) deixando um
    # checkpoint de epoch pronto — sem isso ele reiniciava do zero sempre.
    resume_ckpt = None
    if LORA_OUTPUT.exists():
        checkpoints = sorted(
            LORA_OUTPUT.glob("checkpoint-*"),
            key=lambda p: int(p.name.rsplit("-", 1)[-1]),
        )
        if checkpoints:
            resume_ckpt = str(checkpoints[-1])
            log.info("Retomando: %s", resume_ckpt)

    args = TrainingArguments(
        output_dir=str(LORA_OUTPUT),
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=EPOCHS,
        learning_rate=LR,
        warmup_steps=WARMUP,
        fp16=True,
        logging_steps=5,
        save_strategy=("steps" if TIME_BUDGET_SECONDS else "epoch"),
        save_steps=SAVE_STEPS,
        save_total_limit=SAVE_TOTAL_LIMIT,
        optim="paged_adamw_8bit",
        seed=42,
        report_to="none",
    )
    callbacks = []
    time_cb = None
    if TIME_BUDGET_SECONDS:
        time_cb = _make_time_budget_callback(TIME_BUDGET_SECONDS)
        callbacks.append(time_cb)

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=ds,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
        callbacks=callbacks,
    )
    result = trainer.train(resume_from_checkpoint=resume_ckpt)
    if time_cb is not None and time_cb.stopped_early:
        log.info("PARCIAL budget=%ds step=%s", TIME_BUDGET_SECONDS, result.global_step)
        return 0

    LORA_OUTPUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(LORA_OUTPUT))
    tokenizer.save_pretrained(str(LORA_OUTPUT))
    log.info("LoRA em %s loss=%.4f steps=%s", LORA_OUTPUT, result.training_loss, result.global_step)

    if do_merge:
        log.info("Merge fp16...")
        merged = model.merge_and_unload()
        MERGED_OUTPUT.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(MERGED_OUTPUT), safe_serialization=True)
        tokenizer.save_pretrained(str(MERGED_OUTPUT))

    (OUTPUT_DIR / "TRAINING_COMPLETE").write_text(
        f"persona={PERSONA}\nsteps={result.global_step}\n", encoding="utf-8"
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--merge", action="store_true")
    a = p.parse_args()
    return train(a.dry_run, a.merge)


if __name__ == "__main__":
    raise SystemExit(main())
