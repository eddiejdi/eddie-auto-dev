#!/usr/bin/env python3
"""Fine-tuning QLoRA do trading-analyst na NAS (RTX 2060 SUPER), multi-task.

Adaptado de scripts/ollama_finetune_batch.py (que fine-tuna o trading-sentiment
na RTX 3060 do homelab). Diferenças essenciais:

  - Roda NA NAS (192.168.15.4), na RTX 2060 SUPER 8GB — NUNCA para o Ollama de
    produção da GPU0 (a 3060 continua servindo trading-analyst o tempo todo).
  - Base = llama3.1:8b (mesma base do trading-analyst atual, ver
    docs/MIGRACAO_MODELOS_CHINESES_2026-07-03.md e models/Modelfile.trading-analyst).
  - Fonte = os 3 JSONL gerados pelo dataset builder (controls/window/plan),
    treinados juntos como multi-task no MESMO adapter.
  - Tag alvo = trading-analyst-candidate (NUNCA sobrescreve trading-analyst:latest).

Este script produz um MODELO CANDIDATO para shadow mode. Ele NÃO promove nada para
produção — a troca da tag em produção é uma decisão humana separada, feita via env
var em drop-in systemd por profile, depois de avaliar os números do shadow.

Pré-requisitos na NAS:
  - venv com unsloth + torch (ex: /opt/finetune-env) e CUDA para a 2060.
  - Ollama servindo na NAS (Fase 5) para importar o GGUF (OLLAMA_NAS_HOST).
  - Dataset em DATASET_DIR (copiado do builder da Fase 2).

Uso:
  python3 scripts/trading_analyst_finetune_batch.py --dataset-dir /mnt/tank/finetune/data
  python3 scripts/trading_analyst_finetune_batch.py --dry-run   # só valida o dataset
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# ── Configuração ────────────────────────────────────────────────────────────────
import os

OLLAMA_NAS_HOST = os.environ.get("OLLAMA_NAS_HOST", "http://192.168.15.4:11436")

BASE_MODEL_HF = os.environ.get("FT_BASE_MODEL_HF", "meta-llama/Llama-3.1-8B-Instruct")
TARGET_MODEL = os.environ.get("FT_TARGET_MODEL", "trading-analyst-candidate")

DATASET_DIR = Path(os.environ.get("FT_DATASET_DIR", "/mnt/tank/finetune/data"))
OUTPUT_DIR = Path(os.environ.get("FT_OUTPUT_DIR", "/mnt/tank/finetune/work"))
GGUF_OUTPUT = OUTPUT_DIR / "trading-analyst-candidate.gguf"
LORA_OUTPUT = OUTPUT_DIR / "lora_adapters"
MERGED_OUTPUT = OUTPUT_DIR / "merged_model"
MODELFILE_OUTPUT = OUTPUT_DIR / "Modelfile.candidate"

CALL_TYPES = ("controls", "window", "plan")

# Treinamento — RTX 2060 SUPER 8GB: batch pequeno + seq curto (o gargalo é VRAM
# no 8B 4-bit e a CPU i3-3220 no dataloader).
MAX_SEQ_LENGTH = int(os.environ.get("FT_MAX_SEQ", "2048"))
EPOCHS = int(os.environ.get("FT_EPOCHS", "2"))
BATCH_SIZE = int(os.environ.get("FT_BATCH", "1"))
GRADIENT_ACCUMULATION = int(os.environ.get("FT_GRAD_ACCUM", "8"))
LORA_RANK = int(os.environ.get("FT_LORA_RANK", "16"))
LORA_ALPHA = int(os.environ.get("FT_LORA_ALPHA", "32"))
LEARNING_RATE = float(os.environ.get("FT_LR", "2e-4"))
WARMUP_STEPS = int(os.environ.get("FT_WARMUP", "10"))
MIN_SAMPLES = int(os.environ.get("FT_MIN_SAMPLES", "150"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("trading-analyst-finetune")


# ── Dataset ─────────────────────────────────────────────────────────────────────

def load_dataset_files(dataset_dir: Path) -> Path:
    """Concatena os JSONL por call_type num único arquivo multi-task e valida o mínimo."""
    combined = OUTPUT_DIR / "combined_training.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    with combined.open("w", encoding="utf-8") as out:
        for call_type in CALL_TYPES:
            path = dataset_dir / f"trading_analyst_{call_type}.jsonl"
            if not path.exists():
                log.warning("Ausente: %s (call_type=%s não terá exemplos)", path, call_type)
                continue
            n = 0
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                out.write(line + "\n")
                n += 1
                total += 1
            log.info("call_type=%s: %d exemplos", call_type, n)

    if total < MIN_SAMPLES:
        log.error(
            "Dataset insuficiente: %d < %d exemplos. Rode a Fase 1 (log) mais tempo "
            "e a Fase 2 (builder) antes de treinar.", total, MIN_SAMPLES,
        )
        return Path("")

    log.info("Dataset combinado: %d exemplos → %s", total, combined)
    return combined


# ── Treino QLoRA (Unsloth) ──────────────────────────────────────────────────────

def run_qlora_training(data_path: Path) -> bool:
    """Fine-tuning QLoRA multi-task. Mesma mecânica do pipeline do trading-sentiment."""
    log.info("=" * 60)
    log.info("QLoRA trading-analyst-candidate | base=%s | rank=%d | epochs=%d",
             BASE_MODEL_HF, LORA_RANK, EPOCHS)
    log.info("=" * 60)
    try:
        from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        from datasets import load_dataset  # type: ignore[import-untyped]
        from trl import SFTTrainer  # type: ignore[import-untyped]
        from transformers import TrainingArguments  # type: ignore[import-untyped]
        import torch

        if not torch.cuda.is_available():
            log.error("CUDA não disponível na NAS!")
            return False
        log.info("GPU: %s (%dMB livres)", torch.cuda.get_device_name(0),
                 torch.cuda.mem_get_info(0)[0] // (1024 * 1024))

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=BASE_MODEL_HF, max_seq_length=MAX_SEQ_LENGTH,
            dtype=None, load_in_4bit=True,
        )
        model = FastLanguageModel.get_peft_model(
            model, r=LORA_RANK, lora_alpha=LORA_ALPHA, lora_dropout=0.05,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                            "gate_proj", "up_proj", "down_proj"],
            bias="none", use_gradient_checkpointing="unsloth",
        )

        # Template Llama-3: system fixo do trading-analyst + instruction/output.
        system = (
            "Você é o trading-analyst. Responda EXATAMENTE no formato pedido em cada "
            "instrução (JSON compacto para controls/window; análise em PT-BR para plan)."
        )
        prompt_template = (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            "{instruction}{input}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n{output}<|eot_id|>"
        )

        def format_prompts(examples: dict) -> dict:
            texts = [
                prompt_template.format(instruction=i, input=inp, output=o)
                for i, inp, o in zip(examples["instruction"], examples["input"], examples["output"])
            ]
            return {"text": texts}

        dataset = load_dataset("json", data_files=str(data_path), split="train")
        dataset = dataset.map(format_prompts, batched=True)
        log.info("Dataset: %d exemplos", len(dataset))

        training_args = TrainingArguments(
            output_dir=str(LORA_OUTPUT),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION,
            num_train_epochs=EPOCHS, learning_rate=LEARNING_RATE,
            warmup_steps=WARMUP_STEPS, fp16=True, logging_steps=10,
            save_strategy="epoch", optim="adamw_8bit", seed=42, report_to="none",
        )
        trainer = SFTTrainer(
            model=model, tokenizer=tokenizer, train_dataset=dataset,
            dataset_text_field="text", max_seq_length=MAX_SEQ_LENGTH, args=training_args,
        )
        log.info("Treinando...")
        result = trainer.train()
        log.info("Loss final: %.4f, steps: %d", result.training_loss, result.global_step)

        trainer.save_model(str(LORA_OUTPUT))
        log.info("Merge LoRA → modelo completo...")
        model.save_pretrained_merged(str(MERGED_OUTPUT), tokenizer, save_method="merged_16bit")
        log.info("Export GGUF (Q4_K_M)...")
        model.save_pretrained_gguf(str(OUTPUT_DIR / "gguf"), tokenizer, quantization_method="q4_k_m")

        gguf_files = list((OUTPUT_DIR / "gguf").glob("*.gguf"))
        if not gguf_files:
            log.error("Nenhum GGUF gerado!")
            return False
        shutil.move(str(gguf_files[0]), str(GGUF_OUTPUT))
        log.info("GGUF: %s (%.1fMB)", GGUF_OUTPUT, GGUF_OUTPUT.stat().st_size / (1024 * 1024))

        del model, tokenizer, trainer
        torch.cuda.empty_cache()
        return True
    except Exception as e:
        log.error("Erro no fine-tuning: %s", e, exc_info=True)
        return False


def generate_modelfile() -> Path:
    """Modelfile do candidato — parâmetros conservadores para saída determinística."""
    system_prompt = (
        "Você é o trading-analyst (candidato fine-tuned). Responda EXATAMENTE no "
        "formato pedido: JSON compacto para trade controls/window; análise objetiva "
        "em PT-BR para o plano. Use apenas os números fornecidos no contexto."
    )
    content = (
        f"FROM {GGUF_OUTPUT}\n\n"
        f'SYSTEM """{system_prompt}"""\n\n'
        "PARAMETER temperature 0.0\n"
        "PARAMETER top_p 0.7\n"
        "PARAMETER top_k 20\n"
        "PARAMETER repeat_penalty 1.05\n"
    )
    MODELFILE_OUTPUT.write_text(content, encoding="utf-8")
    log.info("Modelfile: %s", MODELFILE_OUTPUT)
    return MODELFILE_OUTPUT


def import_to_ollama(modelfile_path: Path) -> bool:
    """Importa o GGUF como trading-analyst-candidate no Ollama DA NAS (Fase 5)."""
    log.info("Importando %s no Ollama da NAS (%s)...", TARGET_MODEL, OLLAMA_NAS_HOST)
    payload = json.dumps({
        "name": f"{TARGET_MODEL}:latest",
        "modelfile": modelfile_path.read_text(encoding="utf-8"),
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_NAS_HOST}/api/create", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            log.info("Importado: %s", json.loads(resp.read()))
            return True
    except Exception as e:
        log.error("Erro importando: %s", e)
        return False


def write_run_report(success: bool, samples: int, elapsed_sec: float) -> None:
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success, "training_samples": samples,
        "elapsed_minutes": round(elapsed_sec / 60, 1),
        "target_model": TARGET_MODEL, "base_model": BASE_MODEL_HF,
        "lora_rank": LORA_RANK, "epochs": EPOCHS, "host": OLLAMA_NAS_HOST,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "last_candidate_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Relatório: %s", OUTPUT_DIR / "last_candidate_report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tuning QLoRA do trading-analyst-candidate (NAS)")
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Só valida o dataset, não treina")
    parser.add_argument("--skip-import", action="store_true", help="Treina mas não importa no Ollama")
    args = parser.parse_args()

    start = time.time()
    data_path = load_dataset_files(args.dataset_dir)
    if not data_path or not data_path.exists():
        return 1
    samples = sum(1 for _ in data_path.open())

    if args.dry_run:
        log.info("DRY-RUN: %d amostras válidas em %s", samples, data_path)
        return 0

    if not run_qlora_training(data_path):
        write_run_report(False, samples, time.time() - start)
        return 1

    modelfile = generate_modelfile()
    if not args.skip_import and not import_to_ollama(modelfile):
        write_run_report(False, samples, time.time() - start)
        return 1

    write_run_report(True, samples, time.time() - start)
    log.info("CONCLUÍDO em %.1f min — candidato: %s (NÃO promovido para produção)",
             (time.time() - start) / 60, TARGET_MODEL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
