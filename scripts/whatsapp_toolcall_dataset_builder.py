#!/usr/bin/env python3
"""Gera o dataset de fine-tuning de tool-calling para o modelo `shared-homelab`
do bot do WhatsApp (self-chat) — ver plano em
/home/edenilson/.claude/plans/hazy-chasing-balloon.md.

Diferente do pipeline do trading-analyst (que faz backfill a partir de logs
reais de produção, `btc.llm_calls`), aqui não existe log equivalente — o
dataset é sintético, gerado a partir do schema real das 33 ferramentas
visíveis ao modelo (`scripts/misc/mcp_tool_bridge.py`), garantindo que
nome/argumentos nunca divirjam da implementação real.

Quatro categorias de exemplo, no formato instruction/input/output usado pelo
resto do pipeline de fine-tuning do repo, com um campo adicional
`tool_calls` (lista, vazia para negativos):

  1. Positivos por ferramenta — 1 turno: usuário pede algo → tool_call correto.
  2. Segundo turno — tool_call + resultado → resposta final em texto natural,
     só para um subconjunto de ferramentas de maior tráfego esperado.
  3. Negativos — conversa normal, sem chamar ferramenta nenhuma.
  4. Near-miss — menciona um tema tool-adjacent mas não deveria chamar nada.

Gerador de utterances plugável via --generator:
  - "template" (default, offline, determinístico): frases geradas por
    template + variação programática dos argumentos. Não depende de rede —
    é o modo usado pelos testes e serve de baseline/smoke-test.
  - "ollama": usa um modelo Ollama maior (OLLAMA_HOST/OLLAMA_GEN_MODEL) para
    parafrasear/diversificar as utterances a partir do mesmo meta-prompt.
    É o modo recomendado pra gerar o volume final (~2.200-3.200 exemplos),
    mas precisa de rede/GPU disponível — não roda em CI.

Uso:
  python3 scripts/whatsapp_toolcall_dataset_builder.py --stats-only
  python3 scripts/whatsapp_toolcall_dataset_builder.py --out /tmp/eddie-toolcall-ft --per-tool 40
  python3 scripts/whatsapp_toolcall_dataset_builder.py --generator ollama --per-tool 40 --split test
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent / "misc"))
import mcp_tool_bridge  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("toolcall-dataset")

DEFAULT_OUTPUT_DIR = Path("/tmp/eddie-toolcall-ft")
DEFAULT_PER_TOOL = 40
DEFAULT_MIN_SAMPLES = 800
DEFAULT_TEST_SPLIT = 0.12

# Ferramentas com maior tráfego esperado — recebem exemplos de segundo turno
# (tool_call → resultado → resposta final em texto natural). Não precisa
# cobrir as 33; ver plano seção 3.
SECOND_TURN_TOOLS = (
    "trading_summary",
    "trading_positions",
    "memory_search",
    "bus_health",
    "db_list_tables",
    "secrets_list",
    "journal_query",
    "trading_recent_trades",
    "api_health",
    "bus_get_messages",
)

# Frases de negativo (conversa normal, sem nenhuma ferramenta) — tom self-chat
# casual em PT-BR. Curadas à mão; expandir aqui é mais seguro que gerar por
# LLM, já que são o principal freio contra over-triggering.
NEGATIVE_UTTERANCES = [
    "Bom dia",
    "Boa noite, até amanhã",
    "Valeu, obrigado",
    "Kkkkk boa essa",
    "Manda um lembrete pra eu comprar leite amanhã",
    "Acho que vou dormir mais cedo hoje",
    "Que horas são aí?",
    "Tá calor hoje",
    "Preciso organizar minha agenda esse fim de semana",
    "Vou sair pra correr agora",
    "Depois a gente conversa melhor sobre isso",
    "Tudo certo por aí?",
    "Só testando se você tá vivo",
    "Conta uma piada",
    "O que você acha de aprender Rust esse ano?",
    "Resume rapidinho o que é overfitting",
    "Qual a diferença entre TCP e UDP mesmo?",
    "To com fome, vou pedir uma comida",
    "Ideias de presente pro aniversário da minha mãe?",
    "Como tá o tempo hoje?",
]

# Near-miss: menciona um tema tool-adjacent mas NÃO deveria disparar a
# ferramenta correspondente (ver TOOL_RISK/schemas pra contexto do porquê).
NEAR_MISS_UTTERANCES = [
    ("O que você acha do bitcoin como investimento a longo prazo?", "trading_summary"),
    ("Acha que vale a pena eu comprar mais bitcoin agora?", "trading_ai_plan"),
    ("Me lembra de comprar leite amanhã", "memory_store"),
    ("Você lembra do que a gente conversou ontem sobre férias?", "memory_search"),
    ("Segredo é a alma do negócio, né?", "secrets_get"),
    ("Manda um oi pro pessoal do trabalho por mim", "bus_publish"),
    ("Qual sua senha do banco?", "secrets_get"),
    ("Como andam as coisas no servidor hoje?", "bus_health"),
    ("Preciso consultar uma tabela de preços da loja", "db_list_tables"),
    ("Vi uma notícia sobre bitcoin subindo forte hoje", "trading_news_sentiment"),
]

Generator = Callable[[str, Dict[str, Any], int], List[str]]


# ── Geradores de utterance ───────────────────────────────────────────────


def _sample_value(schema_type: str, param_name: str, rng: random.Random) -> Any:
    """Valor plausível pra um parâmetro, dado seu tipo JSON-schema."""
    if schema_type == "boolean":
        return rng.choice([True, False])
    if schema_type == "integer":
        if "limit" in param_name or "days" in param_name:
            return rng.choice([3, 5, 10, 20, 30])
        return rng.randint(1, 10)
    if schema_type == "number":
        return round(rng.uniform(0.1, 100.0), 2)
    if "symbol" in param_name:
        return rng.choice(["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"])
    if "name" in param_name and "table" not in param_name:
        return rng.choice(["eddie/telegram_bot_token", "eddie/github_token", "eddie/database_url"])
    if "table" in param_name:
        return rng.choice(["events", "checkins", "users"])
    if "agent" in param_name or "target" in param_name:
        return rng.choice(["coordinator", "python", "all", "trading-agent"])
    if "query" in param_name or "fact" in param_name or "content" in param_name or "description" in param_name:
        return rng.choice(["restart do coordinator", "deploy concluído", "status do servidor"])
    return "teste"


def _sample_arguments(parameters: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    props = parameters.get("properties", {}) or {}
    required = set(parameters.get("required", []) or [])
    args: Dict[str, Any] = {}
    for name, spec in props.items():
        # sempre inclui os obrigatórios; inclui opcionais com 50% de chance
        # pra variar entre chamadas "mínimas" e "completas"
        if name not in required and rng.random() < 0.5:
            continue
        args[name] = _sample_value(spec.get("type", "string"), name, rng)
    return args


_TEMPLATE_PHRASES: Dict[str, List[str]] = {
    "trading_summary": ["resume o trading pra mim", "como tá o {symbol} agora?", "manda um resumo do trading"],
    "trading_positions": ["quais posições eu tenho abertas?", "tô com alguma posição aberta em {symbol}?"],
    "trading_recent_trades": ["mostra os últimos trades", "quais foram minhas últimas operações?"],
    "trading_performance": ["como foi minha performance essa semana?", "resultado dos últimos {days} dias"],
    "trading_market_state": ["como tá o mercado agora?", "situação atual do {symbol}"],
    "trading_decisions": ["quais foram as últimas decisões do robô?", "o que o robô decidiu fazer ultimamente?"],
    "trading_candles": ["me manda os candles do {symbol}", "histórico de preço recente"],
    "trading_ai_controls": ["quais os parâmetros de controle atuais?", "configuração da IA de trading"],
    "trading_ai_plan": ["qual o plano atual da IA?", "o que a IA tá pensando sobre o mercado?"],
    "trading_ai_window": ["qual a janela operacional ativa?", "tem alguma janela de entrada aberta?"],
    "trading_news_sentiment": ["tem notícia importante sobre bitcoin?", "sentimento das notícias recentes"],
    "trading_learning_stats": ["como anda o aprendizado do robô?", "estatísticas de Q-learning"],
    "bus_health": ["o bus tá funcionando?", "status do communication bus"],
    "bus_get_messages": ["mensagens recentes do bus", "o que rolou no bus?"],
    "bus_search_by_agent": ["mensagens do agente {agent}", "busca mensagens do {agent}"],
    "bus_publish": ["publica uma mensagem pro {target} dizendo: {content}", "avisa o {target} que {content}"],
    "bus_record_result": ["registra o resultado da tarefa do {language}"],
    "secrets_list": ["quais segredos existem cadastrados?", "lista os segredos disponíveis"],
    "secrets_health": ["o secrets agent tá online?", "status do secrets agent"],
    "secrets_get": ["me mostra o segredo {name}", "qual o valor de {name}?"],
    "api_health": ["a api estou aqui tá no ar?", "status da api"],
    "api_events_list": ["lista os eventos ativos", "quais eventos tem cadastrado?"],
    "api_events_get": ["detalhes do evento {event_id}"],
    "api_events_create": ["cria um evento chamado {title}"],
    "api_checkins_create": ["faz check-in no evento {event_id}"],
    "api_auth_login": ["faz login na api com {email}"],
    "db_list_tables": ["lista as tabelas do banco", "quais tabelas existem no banco?"],
    "db_describe_table": ["descreve a tabela {table_name}", "estrutura da tabela {table_name}"],
    "db_active_events": ["quais eventos estão ativos no banco?"],
    "db_execute_query": ["roda essa query: {sql}"],
    "journal_query": ["histórico de ações dos agentes", "o que já foi feito recentemente?"],
    "memory_search": ["você lembra de algo sobre {query}?", "busca na memória sobre {query}"],
    "memory_store": ["guarda esse fato: {fact}", "lembra disso: {fact}"],
}


def template_generator(tool_name: str, parameters: Dict[str, Any], n: int, seed: int = 0) -> List[Tuple[str, Dict[str, Any]]]:
    """Gerador offline/determinístico: template + variação de argumentos."""
    rng = random.Random(f"{tool_name}-{seed}")
    phrases = _TEMPLATE_PHRASES.get(tool_name, [f"executa {tool_name}"])
    out: List[Tuple[str, Dict[str, Any]]] = []
    for i in range(n):
        args = _sample_arguments(parameters, rng)
        phrase = phrases[i % len(phrases)]
        try:
            text = phrase.format(**{**args, "days": args.get("days", 7)})
        except (KeyError, IndexError):
            text = phrase
        out.append((text, args))
    return out


def ollama_generator_factory(host: str, model: str) -> Callable[[str, Dict[str, Any], int], List[Tuple[str, Dict[str, Any]]]]:
    """Gerador via Ollama local — pede pro modelo diversificar/parafrasear
    as frases template, mantendo os mesmos argumentos (a fonte de verdade
    dos argumentos continua sendo _sample_arguments, não o LLM)."""
    import httpx

    def _gen(tool_name: str, parameters: Dict[str, Any], n: int) -> List[Tuple[str, Dict[str, Any]]]:
        base = template_generator(tool_name, parameters, n)
        prompt = (
            "Reescreva cada frase abaixo em português brasileiro informal, estilo "
            "mensagem de WhatsApp que uma pessoa manda pra si mesma (self-chat), "
            "mantendo o mesmo pedido/intenção. Uma variação por linha, sem numerar:\n\n"
            + "\n".join(f"- {text}" for text, _ in base)
        )
        try:
            resp = httpx.post(
                f"{host}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            resp.raise_for_status()
            lines = [
                ln.strip("-• ").strip()
                for ln in resp.json().get("response", "").splitlines()
                if ln.strip()
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao gerar via Ollama para %s: %s — usando template puro", tool_name, exc)
            return base

        if len(lines) < len(base):
            lines += [text for text, _ in base[len(lines):]]
        return [(lines[i], base[i][1]) for i in range(len(base))]

    return _gen


# ── Montagem dos exemplos ────────────────────────────────────────────────


def _positive_examples(gen: Callable, per_tool: int) -> List[Dict[str, Any]]:
    schemas = {s["function"]["name"]: s["function"] for s in mcp_tool_bridge.build_ollama_tool_schemas()}
    examples: List[Dict[str, Any]] = []
    for tool_name, fn in sorted(schemas.items()):
        for text, args in gen(tool_name, fn.get("parameters", {}), per_tool):
            examples.append({
                "instruction": text,
                "input": "",
                "output": "",
                "tool_calls": [{"function": {"name": tool_name, "arguments": args}}],
            })
    return examples


def _second_turn_examples(count_per_tool: int, rng: random.Random) -> List[Dict[str, Any]]:
    schemas = {s["function"]["name"]: s["function"] for s in mcp_tool_bridge.build_ollama_tool_schemas()}
    examples: List[Dict[str, Any]] = []
    for tool_name in SECOND_TURN_TOOLS:
        fn = schemas.get(tool_name)
        if fn is None:
            continue
        for text, args in template_generator(tool_name, fn.get("parameters", {}), count_per_tool, seed=1):
            fake_result = {"ok": True, "note": "resultado de exemplo pra treino de segundo turno"}
            examples.append({
                "instruction": text,
                "input": "",
                "output": "Beleza, aqui está: " + json.dumps(fake_result, ensure_ascii=False),
                "tool_calls": [{"function": {"name": tool_name, "arguments": args}}],
                "tool_result": fake_result,
            })
    return examples


def _negative_examples() -> List[Dict[str, Any]]:
    return [
        {"instruction": text, "input": "", "output": "(resposta conversacional normal, sem tool_calls)", "tool_calls": []}
        for text in NEGATIVE_UTTERANCES
    ]


def _near_miss_examples() -> List[Dict[str, Any]]:
    return [
        {
            "instruction": text,
            "input": "",
            "output": "(resposta conversacional — NÃO deve chamar a ferramenta associada)",
            "tool_calls": [],
            "near_miss_of": avoided_tool,
        }
        for text, avoided_tool in NEAR_MISS_UTTERANCES
    ]


def build_dataset(generator_name: str, per_tool: int, ollama_host: str, ollama_model: str) -> List[Dict[str, Any]]:
    if generator_name == "ollama":
        gen = ollama_generator_factory(ollama_host, ollama_model)
    else:
        gen = lambda tool_name, parameters, n: template_generator(tool_name, parameters, n)  # noqa: E731

    rng = random.Random(42)
    examples: List[Dict[str, Any]] = []
    examples += _positive_examples(gen, per_tool)
    examples += _second_turn_examples(max(1, per_tool // 4), rng)
    # negativos ~30-40% do total de positivos — repete/perturba a lista curada
    # base pra atingir volume proporcional sem repetir a frase idêntica.
    target_negatives = int(len(examples) * 0.35)
    base_neg = _negative_examples()
    negatives = []
    i = 0
    while len(negatives) < target_negatives:
        negatives.append(base_neg[i % len(base_neg)])
        i += 1
    examples += negatives
    examples += _near_miss_examples() * max(1, per_tool // 10)

    rng.shuffle(examples)
    return examples


def main() -> int:
    parser = argparse.ArgumentParser(description="Dataset builder de tool-calling do shared-homelab")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--per-tool", type=int, default=DEFAULT_PER_TOOL,
                         help="Exemplos positivos por ferramenta (default: %(default)s)")
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--split", type=float, default=DEFAULT_TEST_SPLIT,
                         help="Fração reservada como held-out para shadow-eval")
    parser.add_argument("--generator", choices=["template", "ollama"], default="template")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args()

    examples = build_dataset(args.generator, args.per_tool, args.ollama_host, args.ollama_model)
    n_total = len(examples)
    n_test = int(n_total * args.split)
    test_examples = examples[:n_test]
    train_examples = examples[n_test:]

    n_positive = sum(1 for e in examples if e["tool_calls"])
    n_negative = n_total - n_positive
    log.info(
        "Total=%d (positivos=%d, negativos/near-miss=%d) | train=%d test=%d",
        n_total, n_positive, n_negative, len(train_examples), len(test_examples),
    )

    enough = n_total >= args.min_samples
    if not enough:
        log.warning("Dataset abaixo do MIN_SAMPLES=%d — revise --per-tool antes de treinar.", args.min_samples)

    if args.stats_only:
        return 0 if enough else 1

    args.out.mkdir(parents=True, exist_ok=True)
    for split_name, split_examples in (("train", train_examples), ("test", test_examples)):
        out_path = args.out / f"whatsapp_toolcall_{split_name}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for ex in split_examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        log.info("Escrito %s (%d exemplos)", out_path, len(split_examples))

    manifest = {
        "generator": args.generator,
        "per_tool": args.per_tool,
        "total": n_total,
        "positive": n_positive,
        "negative": n_negative,
        "train": len(train_examples),
        "test": len(test_examples),
        "min_samples": args.min_samples,
        "enough": enough,
    }
    (args.out / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    return 0 if enough else 1


if __name__ == "__main__":
    sys.exit(main())
