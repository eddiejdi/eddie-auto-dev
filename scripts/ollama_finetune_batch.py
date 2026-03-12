#!/usr/bin/env python3
"""Fine-tuning batch do eddie-sentiment via QLoRA/Unsloth.

Executa em horário de baixo uso (via systemd timer, padrão Dom 03:00).
Para o Ollama GPU0, treina adaptadores LoRA no phi4-mini,
exporta para GGUF e reimporta no Ollama.

Pipeline:
  1. Backup do modelo atual
  2. Exporta dados de btc.training_samples → JSONL
  3. Para Ollama GPU0 (libera 8GB VRAM)
  4. QLoRA fine-tuning com Unsloth
  5. Merge LoRA → Export GGUF
  6. Reinicia Ollama GPU0
  7. Importa GGUF via ollama create
  8. Valida com prompts de teste
  9. Limpa backups antigos se modelo estável

Requisitos:
  - venv /opt/finetune-env com unsloth + torch
  - RTX 2060 SUPER 8GB livre
  - Dados em btc.training_samples (PostgreSQL)

Uso:
  /opt/finetune-env/bin/python3 scripts/ollama_finetune_batch.py
  /opt/finetune-env/bin/python3 scripts/ollama_finetune_batch.py --dry-run
  /opt/finetune-env/bin/python3 scripts/ollama_finetune_batch.py --skip-stop
  /opt/finetune-env/bin/python3 scripts/ollama_finetune_batch.py --cleanup-only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Configuração ───────────────────────────────────────────────────────────────

OLLAMA_HOST_GPU0 = os.environ.get("OLLAMA_HOST", "http://192.168.15.2:11434")
OLLAMA_HOST_GPU1 = os.environ.get("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
SECRETS_API = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
SECRETS_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "")

BASE_MODEL_HF = "microsoft/Phi-4-mini-instruct"
BASE_MODEL_OLLAMA = "phi4-mini"
TARGET_MODEL = "eddie-sentiment"
OUTPUT_DIR = Path("/tmp/eddie-finetune")
GGUF_OUTPUT = OUTPUT_DIR / "eddie-sentiment-finetuned.gguf"
LORA_OUTPUT = OUTPUT_DIR / "lora_adapters"
MERGED_OUTPUT = OUTPUT_DIR / "merged_model"
MODELFILE_OUTPUT = OUTPUT_DIR / "Modelfile.finetuned"
BACKUP_DIR = Path("/mnt/raid1/ollama/finetune_backups")

# Treinamento
MAX_SAMPLES = 2000
MIN_SAMPLES = 50
EPOCHS = 3
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
LORA_RANK = 16
LORA_ALPHA = 32
LEARNING_RATE = 2e-4
MAX_SEQ_LENGTH = 512
WARMUP_STEPS = 10

# Limpeza de backups
VALIDATION_PROMPTS_REQUIRED = 3
BACKUP_RETENTION_COUNT = 3
BACKUP_MAX_AGE_DAYS = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("finetune-batch")


# ── Funções auxiliares ─────────────────────────────────────────────────────────


def _fetch_secret(name: str, field: str = "password") -> str:
    """Busca secret no Secrets Agent via HTTP."""
    encoded = urllib.parse.quote(name, safe="")
    url = f"{SECRETS_API}/secrets/local/{encoded}?field={field}"
    req = urllib.request.Request(url, headers={"X-API-KEY": SECRETS_KEY})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    value = data.get("value", "")
    if not value:
        raise ValueError(f"Secret '{name}' (field={field}) retornou vazio")
    return value


def _get_database_url() -> str:
    """Obtém DATABASE_URL do env ou do Secrets Agent."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    try:
        return _fetch_secret("eddie/database_url", field="url")
    except Exception as e:
        log.error("Falha ao obter DATABASE_URL do Secrets Agent: %s", e)
        raise


def is_ollama_running(host: str) -> bool:
    """Verifica se o Ollama está respondendo."""
    try:
        req = urllib.request.Request(f"{host}/api/tags")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def stop_ollama_gpu0() -> bool:
    """Para o serviço Ollama da GPU0 para liberar VRAM."""
    log.info("Parando Ollama GPU0...")
    try:
        subprocess.run(
            ["sudo", "systemctl", "stop", "ollama"],
            check=True, timeout=30,
        )
        subprocess.run(
            ["sudo", "systemctl", "stop", "ollama-warmup.timer"],
            check=False, timeout=10,
        )
        time.sleep(5)

        if is_ollama_running(OLLAMA_HOST_GPU0):
            log.error("Ollama GPU0 ainda rodando após stop!")
            return False

        log.info("Ollama GPU0 parado. VRAM liberada.")
        return True
    except subprocess.TimeoutExpired:
        log.error("Timeout parando Ollama GPU0")
        return False
    except subprocess.CalledProcessError as e:
        log.error("Erro parando Ollama: %s", e)
        return False


def start_ollama_gpu0() -> bool:
    """Reinicia o serviço Ollama da GPU0."""
    log.info("Reiniciando Ollama GPU0...")
    try:
        subprocess.run(
            ["sudo", "systemctl", "start", "ollama"],
            check=True, timeout=30,
        )
        subprocess.run(
            ["sudo", "systemctl", "start", "ollama-warmup.timer"],
            check=False, timeout=10,
        )
        for attempt in range(12):
            time.sleep(5)
            if is_ollama_running(OLLAMA_HOST_GPU0):
                log.info("Ollama GPU0 online após %ds", (attempt + 1) * 5)
                return True
        log.error("Ollama GPU0 não voltou após 60s!")
        return False
    except Exception as e:
        log.error("Erro reiniciando Ollama: %s", e)
        return False


def export_training_data() -> Path:
    """Exporta dados de treinamento do PostgreSQL para JSONL."""
    import psycopg2
    import psycopg2.extras

    output_path = OUTPUT_DIR / "training_data.jsonl"
    log.info("Exportando dados de btc.training_samples...")

    conn = psycopg2.connect(_get_database_url())
    conn.autocommit = True

    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT title, description, coin,
                   ollama_sentiment, ollama_confidence,
                   ollama_direction, ollama_category,
                   ground_truth, price_change_pct
            FROM btc.training_samples
            WHERE prediction_correct = true
              AND ollama_confidence >= 0.6
              AND ground_truth IS NOT NULL
              AND title IS NOT NULL
              AND description IS NOT NULL
            ORDER BY ollama_confidence DESC, created_at DESC
            LIMIT %s
        """, (MAX_SAMPLES,))
        rows = cur.fetchall()

    conn.close()

    if len(rows) < MIN_SAMPLES:
        log.error(
            "Dados insuficientes: %d amostras (mín: %d). "
            "Execute primeiro: python3 scripts/run_sentiment_finetune.py",
            len(rows), MIN_SAMPLES,
        )
        return Path("")

    log.info("Exportados %d exemplos de treinamento", len(rows))

    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            instruction = (
                f"Analyze this crypto news and classify sentiment for trading.\n"
                f"Reply ONLY in this exact format:\n"
                f"SENTIMENT: <-1.0 to 1.0> | CONFIDENCE: <0.0 to 1.0> | "
                f"DIRECTION: <BULLISH|BEARISH|NEUTRAL> | CATEGORY: <category>\n\n"
                f"Coin: {row['coin']}\n"
                f"Title: {row['title']}\n"
                f"Summary: {(row['description'] or '')[:300]}"
            )
            output = (
                f"SENTIMENT: {row['ollama_sentiment']:.2f} | "
                f"CONFIDENCE: {row['ollama_confidence']:.2f} | "
                f"DIRECTION: {row['ollama_direction']} | "
                f"CATEGORY: {row['ollama_category']}"
            )
            entry = {
                "instruction": instruction,
                "input": "",
                "output": output,
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    log.info("Dados salvos em %s (%d amostras)", output_path, len(rows))
    return output_path


def run_qlora_training(data_path: Path) -> bool:
    """Executa fine-tuning QLoRA com Unsloth."""
    log.info("=" * 60)
    log.info("INICIANDO FINE-TUNING QLoRA")
    log.info("  Modelo base: %s", BASE_MODEL_HF)
    log.info("  LoRA rank: %d, alpha: %d", LORA_RANK, LORA_ALPHA)
    log.info("  Epochs: %d, Batch: %d x %d", EPOCHS, BATCH_SIZE, GRADIENT_ACCUMULATION)
    log.info("=" * 60)

    try:
        from unsloth import FastLanguageModel  # type: ignore[import-untyped]
        from datasets import load_dataset  # type: ignore[import-untyped]
        from trl import SFTTrainer  # type: ignore[import-untyped]
        from transformers import TrainingArguments  # type: ignore[import-untyped]
        import torch

        if not torch.cuda.is_available():
            log.error("CUDA não disponível!")
            return False
        log.info("GPU: %s (%dMB livres)",
                 torch.cuda.get_device_name(0),
                 torch.cuda.mem_get_info(0)[0] // (1024 * 1024))

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=BASE_MODEL_HF,
            max_seq_length=MAX_SEQ_LENGTH,
            dtype=None,
            load_in_4bit=True,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=LORA_RANK,
            lora_alpha=LORA_ALPHA,
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            bias="none",
            use_gradient_checkpointing="unsloth",
        )

        prompt_template = (
            "<|system|>You are eddie-sentiment, a crypto market "
            "sentiment analyzer.<|end|>\n"
            "<|user|>{instruction}{input}<|end|>\n"
            "<|assistant|>{output}<|end|>"
        )

        def format_prompts(examples: dict) -> dict:
            """Formata exemplos no template do Phi-4."""
            texts = []
            for instr, inp, out in zip(
                examples["instruction"],
                examples["input"],
                examples["output"],
            ):
                text = prompt_template.format(
                    instruction=instr, input=inp, output=out,
                )
                texts.append(text)
            return {"text": texts}

        dataset = load_dataset("json", data_files=str(data_path), split="train")
        dataset = dataset.map(format_prompts, batched=True)
        log.info("Dataset: %d exemplos", len(dataset))

        training_args = TrainingArguments(
            output_dir=str(LORA_OUTPUT),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            warmup_steps=WARMUP_STEPS,
            fp16=True,
            logging_steps=10,
            save_strategy="epoch",
            optim="adamw_8bit",
            seed=42,
            report_to="none",
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            dataset_text_field="text",
            max_seq_length=MAX_SEQ_LENGTH,
            args=training_args,
        )

        log.info("Iniciando treinamento...")
        train_result = trainer.train()
        log.info(
            "Treinamento concluído! Loss: %.4f, Steps: %d",
            train_result.training_loss,
            train_result.global_step,
        )

        trainer.save_model(str(LORA_OUTPUT))
        log.info("Adaptadores LoRA salvos em %s", LORA_OUTPUT)

        log.info("Fazendo merge LoRA → modelo completo...")
        model.save_pretrained_merged(
            str(MERGED_OUTPUT),
            tokenizer,
            save_method="merged_16bit",
        )

        log.info("Exportando para GGUF (Q4_K_M)...")
        model.save_pretrained_gguf(
            str(OUTPUT_DIR / "gguf"),
            tokenizer,
            quantization_method="q4_k_m",
        )

        gguf_files = list((OUTPUT_DIR / "gguf").glob("*.gguf"))
        if not gguf_files:
            log.error("Nenhum arquivo GGUF gerado!")
            return False

        shutil.move(str(gguf_files[0]), str(GGUF_OUTPUT))
        log.info("GGUF exportado: %s (%.1fMB)",
                 GGUF_OUTPUT,
                 GGUF_OUTPUT.stat().st_size / (1024 * 1024))

        del model, tokenizer, trainer
        torch.cuda.empty_cache()

        return True

    except Exception as e:
        log.error("Erro no fine-tuning: %s", e, exc_info=True)
        return False


def generate_modelfile() -> Path:
    """Gera Modelfile para importar o GGUF no Ollama."""
    system_prompt = (
        "Você é eddie-sentiment, especialista em análise de sentimento de "
        "mercado para criptomoedas.\n"
        "Sua função: Analisar notícias de cripto e prever o impacto no "
        "preço nas próximas 4 horas.\n"
        "FORMATO DE RESPOSTA OBRIGATÓRIO (apenas isso, sem texto extra):\n"
        "SENTIMENT: <-1.0 a +1.0> | CONFIDENCE: <0.0 a 1.0> | "
        "DIRECTION: <BULLISH|BEARISH|NEUTRAL> | "
        "CATEGORY: <categoria>\n\n"
        "CATEGORIAS: regulation | adoption | hack | price | macro | defi "
        "| technical | general\n"
        "REGRAS:\n"
        "- DIRECTION consistente com SENTIMENT\n"
        "- CONFIDENCE reflete certeza\n"
        "- Ignore ruído de mercado. Foque em fundamentais."
    )

    content = f"FROM {GGUF_OUTPUT}\n\n"
    content += f'SYSTEM """{system_prompt}"""\n\n'
    content += "PARAMETER num_predict 80\n"
    content += "PARAMETER repeat_penalty 1.1\n"
    content += "PARAMETER temperature 0.05\n"
    content += "PARAMETER top_p 0.9\n"

    MODELFILE_OUTPUT.write_text(content, encoding="utf-8")
    log.info("Modelfile gerado: %s", MODELFILE_OUTPUT)
    return MODELFILE_OUTPUT


def import_to_ollama(modelfile_path: Path) -> bool:
    """Importa modelo GGUF no Ollama via API."""
    log.info("Importando %s no Ollama...", TARGET_MODEL)

    modelfile_content = modelfile_path.read_text(encoding="utf-8")

    payload = json.dumps({
        "name": f"{TARGET_MODEL}:latest",
        "modelfile": modelfile_content,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST_GPU0}/api/create",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
            log.info("Modelo importado: %s", result)
            return True
    except Exception as e:
        log.error("Erro importando modelo: %s", e)
        return False


def validate_model() -> tuple[bool, int, int]:
    """Valida o modelo fine-tuned com prompts de teste.

    Retorna (estável, acertos, total).
    """
    test_prompts = [
        {
            "prompt": (
                "Coin: BTC\nTitle: Bitcoin ETF sees record $1.2B inflows\n"
                "Summary: BlackRock's Bitcoin ETF recorded unprecedented "
                "daily inflows signaling strong institutional demand."
            ),
            "expected_direction": "BULLISH",
        },
        {
            "prompt": (
                "Coin: BTC\nTitle: Major exchange hacked, $500M stolen\n"
                "Summary: A major cryptocurrency exchange suffered a "
                "security breach losing $500M in user funds."
            ),
            "expected_direction": "BEARISH",
        },
        {
            "prompt": (
                "Coin: ETH\nTitle: Ethereum completes major network upgrade\n"
                "Summary: Ethereum successfully deployed its latest "
                "upgrade improving scalability and reducing gas fees."
            ),
            "expected_direction": "BULLISH",
        },
        {
            "prompt": (
                "Coin: BTC\nTitle: China announces new crypto ban\n"
                "Summary: Chinese government issues sweeping ban on all "
                "cryptocurrency trading and mining activities."
            ),
            "expected_direction": "BEARISH",
        },
    ]

    log.info("Validando modelo %s com %d prompts...", TARGET_MODEL, len(test_prompts))
    passed = 0

    for test in test_prompts:
        payload = json.dumps({
            "model": TARGET_MODEL,
            "prompt": test["prompt"],
            "stream": False,
            "options": {"temperature": 0.05, "num_predict": 100},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{OLLAMA_HOST_GPU0}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                response = data.get("response", "")
                if test["expected_direction"] in response.upper():
                    log.info("  PASS: %s detectado — '%s'",
                             test["expected_direction"], response.strip()[:80])
                    passed += 1
                else:
                    log.warning("  FAIL: esperado %s, obtido: '%s'",
                                test["expected_direction"], response.strip()[:80])
        except Exception as e:
            log.error("  ERROR: %s", e)

    total = len(test_prompts)
    stable = passed >= VALIDATION_PROMPTS_REQUIRED
    log.info("Validação: %d/%d (%s)",
             passed, total,
             "ESTÁVEL" if stable else "INSTÁVEL")
    return stable, passed, total


def backup_current_model() -> Optional[Path]:
    """Faz backup do Modelfile atual antes do fine-tuning.

    Retorna caminho do backup criado ou None.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"eddie-sentiment_pre-finetune_{ts}.json"

    try:
        payload = json.dumps({"name": TARGET_MODEL}).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_HOST_GPU0}/api/show",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            backup_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            log.info("Backup do modelo atual: %s", backup_path)
            return backup_path
    except Exception as e:
        log.warning("Não foi possível fazer backup: %s", e)
        return None


# ── Limpeza de backups ─────────────────────────────────────────────────────────

def cleanup_old_backups(force: bool = False) -> int:
    """Remove backups antigos após confirmação de estabilidade.

    Política de retenção:
      - Mantém os últimos BACKUP_RETENTION_COUNT backups
      - Remove backups mais velhos que BACKUP_MAX_AGE_DAYS
      - Só executa se force=True ou modelo validado como estável

    Retorna número de backups removidos.
    """
    if not BACKUP_DIR.exists():
        log.info("Diretório de backups não existe: %s", BACKUP_DIR)
        return 0

    backups = sorted(
        BACKUP_DIR.glob("eddie-sentiment_pre-finetune_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    removed = 0

    if backups:
        log.info("Backups encontrados: %d", len(backups))
        for i, bk in enumerate(backups):
            age_days = (time.time() - bk.stat().st_mtime) / 86400
            log.info("  [%d] %s (%.0f dias)", i, bk.name, age_days)

        to_keep = set(backups[:BACKUP_RETENTION_COUNT])
        cutoff = time.time() - (BACKUP_MAX_AGE_DAYS * 86400)

        for bk in backups:
            if bk in to_keep:
                continue

            age_days = (time.time() - bk.stat().st_mtime) / 86400

            if bk.stat().st_mtime < cutoff or force:
                try:
                    bk.unlink()
                    log.info("  REMOVIDO: %s (%.0f dias)", bk.name, age_days)
                    removed += 1
                except OSError as e:
                    log.warning("  Erro ao remover %s: %s", bk.name, e)
    else:
        log.info("Nenhum backup encontrado para limpeza")

    # Limpar artefatos temporários de treinos anteriores
    temp_dirs = [
        OUTPUT_DIR / "gguf",
        LORA_OUTPUT,
        MERGED_OUTPUT,
    ]
    for temp_dir in temp_dirs:
        if temp_dir.exists() and temp_dir.is_dir():
            try:
                shutil.rmtree(temp_dir)
                log.info("  Temp removido: %s", temp_dir)
            except OSError as e:
                log.warning("  Erro ao remover %s: %s", temp_dir, e)

    # Limpar JSONL de treino antigo (>7 dias)
    training_cutoff = time.time() - (7 * 86400)
    for jsonl in OUTPUT_DIR.glob("training_data*.jsonl"):
        if jsonl.stat().st_mtime < training_cutoff:
            try:
                jsonl.unlink()
                log.info("  JSONL antigo removido: %s", jsonl.name)
            except OSError as e:
                log.warning("  Erro ao remover %s: %s", jsonl.name, e)

    kept = len(backups) - removed if backups else 0
    log.info("Limpeza concluída: %d backups removidos, %d mantidos",
             removed, kept)
    return removed


def write_run_report(
    success: bool,
    stable: bool,
    validation_passed: int,
    validation_total: int,
    elapsed_sec: float,
    samples_count: int,
    backups_cleaned: int,
) -> None:
    """Grava relatório da execução em JSON para auditoria."""
    report_path = BACKUP_DIR / "last_finetune_report.json"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "model_stable": stable,
        "validation": f"{validation_passed}/{validation_total}",
        "training_samples": samples_count,
        "elapsed_minutes": round(elapsed_sec / 60, 1),
        "backups_cleaned": backups_cleaned,
        "target_model": TARGET_MODEL,
        "base_model": BASE_MODEL_HF,
        "lora_rank": LORA_RANK,
        "epochs": EPOCHS,
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Relatório salvo: %s", report_path)


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main() -> int:
    """Pipeline completo de fine-tuning batch."""
    parser = argparse.ArgumentParser(
        description="Fine-tuning batch eddie-sentiment via QLoRA",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas exporta dados, sem treinar")
    parser.add_argument("--skip-stop", action="store_true",
                        help="Não para o Ollama (debug)")
    parser.add_argument("--skip-export", action="store_true",
                        help="Usa dados já exportados em /tmp/eddie-finetune")
    parser.add_argument("--cleanup-only", action="store_true",
                        help="Apenas executa limpeza de backups antigos")
    args = parser.parse_args()

    start_time = time.time()
    log.info("=" * 60)
    log.info("FINE-TUNING BATCH — eddie-sentiment")
    log.info("Início: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)

    # Modo limpeza apenas
    if args.cleanup_only:
        log.info("Modo --cleanup-only: validando modelo e limpando backups")
        if not is_ollama_running(OLLAMA_HOST_GPU0):
            log.error("Ollama GPU0 offline — não é possível validar")
            return 1
        stable, passed, total = validate_model()
        cleaned = 0
        if stable:
            cleaned = cleanup_old_backups(force=False)
        else:
            log.warning("Modelo instável — backups preservados")
        write_run_report(True, stable, passed, total,
                         time.time() - start_time, 0, cleaned)
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ollama_was_running = is_ollama_running(OLLAMA_HOST_GPU0)
    samples_count = 0
    stable = False
    validation_passed = 0
    validation_total = 0
    backups_cleaned = 0

    try:
        # 1. Backup do modelo atual
        if ollama_was_running:
            backup_current_model()

        # 2. Exportar dados de treinamento
        data_path = OUTPUT_DIR / "training_data.jsonl"
        if not args.skip_export:
            data_path = export_training_data()
            if not data_path or not data_path.exists():
                log.error("Falha na exportação de dados!")
                return 1

            with data_path.open("r") as f:
                samples_count = sum(1 for _ in f)
        elif not data_path.exists():
            log.error("--skip-export mas %s não existe!", data_path)
            return 1

        if args.dry_run:
            log.info("DRY-RUN: %d amostras exportadas em %s", samples_count, data_path)
            return 0

        # 3. Parar Ollama GPU0 para liberar VRAM
        if not args.skip_stop and ollama_was_running:
            if not stop_ollama_gpu0():
                log.error("Não consegui parar Ollama GPU0!")
                return 1

        # 4. Fine-tuning QLoRA
        if not run_qlora_training(data_path):
            log.error("Fine-tuning falhou!")
            return 1

        # 5. Gerar Modelfile
        modelfile_path = generate_modelfile()

        # 6. Reiniciar Ollama GPU0
        if not args.skip_stop:
            if not start_ollama_gpu0():
                log.error("Falha ao reiniciar Ollama GPU0!")
                subprocess.run(
                    ["sudo", "systemctl", "start", "ollama"],
                    check=False,
                )
                return 1

        # 7. Importar modelo fine-tuned
        if not import_to_ollama(modelfile_path):
            log.error("Falha ao importar modelo no Ollama!")
            return 1

        # 8. Validar estabilidade
        stable, validation_passed, validation_total = validate_model()

        # 9. Limpeza condicional de backups
        if stable:
            log.info("Modelo ESTÁVEL (%d/%d) — executando limpeza de backups",
                     validation_passed, validation_total)
            backups_cleaned = cleanup_old_backups(force=False)
        else:
            log.warning(
                "Modelo INSTÁVEL (%d/%d) — backups PRESERVADOS para rollback",
                validation_passed, validation_total,
            )
            log.warning(
                "Rollback manual: restaure backup de %s e execute "
                "'ollama create eddie-sentiment -f <Modelfile>'",
                BACKUP_DIR,
            )

        elapsed = time.time() - start_time
        log.info("=" * 60)
        log.info("FINE-TUNING %s em %.1f min",
                 "CONCLUÍDO" if stable else "CONCLUÍDO (com warnings)",
                 elapsed / 60)
        log.info("  Amostras: %d | Validação: %d/%d | Backups limpos: %d",
                 samples_count, validation_passed, validation_total,
                 backups_cleaned)
        log.info("=" * 60)

        write_run_report(True, stable, validation_passed, validation_total,
                         elapsed, samples_count, backups_cleaned)
        return 0

    except Exception as e:
        log.error("Erro fatal: %s", e, exc_info=True)
        elapsed = time.time() - start_time
        write_run_report(False, False, validation_passed, validation_total,
                         elapsed, samples_count, 0)
        return 1

    finally:
        # SEMPRE garantir que Ollama volte
        if ollama_was_running and not is_ollama_running(OLLAMA_HOST_GPU0):
            log.warning("Ollama estava rodando mas parou — reiniciando...")
            start_ollama_gpu0()


if __name__ == "__main__":
    sys.exit(main())
