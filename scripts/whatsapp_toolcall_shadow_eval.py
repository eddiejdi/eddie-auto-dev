#!/usr/bin/env python3
"""Shadow-eval do candidato de tool-calling do shared-homelab.

Sem log de produção equivalente ao `btc.llm_calls` do trading-analyst, o
eval roda contra o split held-out do dataset gerado por
`whatsapp_toolcall_dataset_builder.py` (nunca visto no treino). Para cada
exemplo: nome da ferramenta bate (ou corretamente nenhuma), argumentos
validam contra o schema real (mesmo gerador da bridge — uma fonte única de
verdade), taxa de falso-positivo/falso-negativo — reportados por bucket de
risco (SAFE vs travada), já que um falso-positivo em `secrets_get` pesa mais
que um em `bus_health`.

NUNCA executa ferramenta real nem dispara aprovação Telegram real — puro
texto-in/texto-out contra gabarito. Decisão de promoção continua HUMANA;
este relatório é só insumo (mesma convenção do shadow-eval de trading).

Uso:
  python3 scripts/whatsapp_toolcall_shadow_eval.py \
      --dataset /tmp/eddie-toolcall-ft/whatsapp_toolcall_test.jsonl \
      --ollama-host http://192.168.15.4:11436 --model shared-homelab-candidate \
      --out /tmp/eddie-toolcall-ft/shadow_eval_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent / "misc"))
import mcp_tool_bridge  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("toolcall-shadow-eval")

SYSTEM = (
    "Você é o assistente pessoal de infraestrutura do Edenilson (self-chat "
    "no WhatsApp). Quando o pedido exigir dados ou ação sobre o homelab "
    "(trading, banco, bus de comunicação, segredos, memória compartilhada), "
    "chame a ferramenta certa em vez de inventar a resposta. Para conversa "
    "normal, responda direto em português, sem chamar ferramenta nenhuma."
)

_JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


def load_examples(path: Path) -> List[Dict[str, Any]]:
    examples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            examples.append(json.loads(line))
    return examples


def call_candidate(host: str, model: str, instruction: str, tools: list, timeout: float) -> tuple[str, list]:
    """Chama o modelo candidato via /api/chat, mesmo formato usado em produção."""
    try:
        resp = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": instruction},
                ],
                "stream": False,
                "tools": tools,
                "options": {"temperature": 0.7, "num_predict": 512},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        msg = resp.json().get("message", {}) or {}
        return msg.get("content", "") or "", msg.get("tool_calls") or []
    except Exception as exc:  # noqa: BLE001
        log.warning("Erro chamando candidato para '%s': %s", instruction[:60], exc)
        return "", []


def _validate_args(args: Dict[str, Any], parameters: Dict[str, Any]) -> bool:
    """Validação leve de schema sem depender do pacote `jsonschema` (pode não
    estar disponível no venv de treino do host)."""
    props = parameters.get("properties", {}) or {}
    required = set(parameters.get("required", []) or [])
    if not required.issubset(args.keys()):
        return False
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            return False  # argumento que a ferramenta nem aceita
        expected = _JSON_TYPE_MAP.get(spec.get("type", ""))
        if expected and not isinstance(value, expected):
            return False
    return True


def evaluate(examples: List[Dict[str, Any]], host: str, model: str, timeout: float) -> Dict[str, Any]:
    tools = mcp_tool_bridge.build_ollama_tool_schemas()
    schemas_by_name = {s["function"]["name"]: s["function"] for s in tools}

    buckets = {"safe": {"total": 0, "correct": 0, "fp": 0, "fn": 0, "schema_ok": 0, "schema_checked": 0},
               "gated": {"total": 0, "correct": 0, "fp": 0, "fn": 0, "schema_ok": 0, "schema_checked": 0}}
    details: List[Dict[str, Any]] = []

    for ex in examples:
        gold_calls = ex.get("tool_calls") or []
        gold_name = gold_calls[0]["function"]["name"] if gold_calls else None
        bucket_key = "gated" if (gold_name and mcp_tool_bridge.is_gated(gold_name)) else "safe"
        bucket = buckets[bucket_key]
        bucket["total"] += 1

        _content, pred_calls = call_candidate(host, model, ex["instruction"], tools, timeout)
        pred_name = None
        pred_args: Dict[str, Any] = {}
        if pred_calls:
            fn = pred_calls[0].get("function", {})
            pred_name = fn.get("name")
            raw_args = fn.get("arguments") or {}
            pred_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

        outcome = "unknown"
        if gold_name is None and pred_name is None:
            outcome = "correct_no_tool"
            bucket["correct"] += 1
        elif gold_name is None and pred_name is not None:
            outcome = "false_positive"
            bucket["fp"] += 1
        elif gold_name is not None and pred_name is None:
            outcome = "false_negative"
            bucket["fn"] += 1
        elif gold_name == pred_name:
            outcome = "correct_tool"
            bucket["correct"] += 1
            schema = schemas_by_name.get(pred_name, {}).get("parameters", {})
            bucket["schema_checked"] += 1
            if _validate_args(pred_args, schema):
                bucket["schema_ok"] += 1
        else:
            outcome = "wrong_tool"

        details.append({
            "instruction": ex["instruction"],
            "gold_tool": gold_name,
            "predicted_tool": pred_name,
            "outcome": outcome,
        })

    report: Dict[str, Any] = {"buckets": {}, "details": details}
    for key, b in buckets.items():
        total = max(1, b["total"])
        report["buckets"][key] = {
            **b,
            "accuracy": round(b["correct"] / total, 4),
            "false_positive_rate": round(b["fp"] / total, 4),
            "false_negative_rate": round(b["fn"] / total, 4),
            "schema_validity_rate": (
                round(b["schema_ok"] / b["schema_checked"], 4) if b["schema_checked"] else None
            ),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Shadow-eval do candidato de tool-calling do shared-homelab")
    parser.add_argument("--dataset", type=Path, required=True, help="JSONL held-out (split test)")
    parser.add_argument("--ollama-host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", type=Path, default=Path("/tmp/whatsapp_toolcall_shadow_eval_report.json"))
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--limit", type=int, default=0, help="0 = todos os exemplos do dataset")
    args = parser.parse_args()

    examples = load_examples(args.dataset)
    if args.limit:
        examples = examples[: args.limit]
    log.info("Avaliando %d exemplos contra %s (%s)", len(examples), args.model, args.ollama_host)

    report = evaluate(examples, args.ollama_host, args.model, args.timeout)

    for bucket, stats in report["buckets"].items():
        log.info(
            "[%s] n=%d acc=%.2f%% fp=%.2f%% fn=%.2f%% schema_ok=%s",
            bucket, stats["total"], stats["accuracy"] * 100,
            stats["false_positive_rate"] * 100, stats["false_negative_rate"] * 100,
            stats["schema_validity_rate"],
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Relatório salvo em %s", args.out)
    log.info("Decisão de promoção é HUMANA — este relatório é só insumo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
