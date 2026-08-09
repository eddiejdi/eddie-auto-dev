"""
LLM Optimizer Proxy — Eddie Auto-Dev (v4.0)
Pipeline Multi-Agente Colaborativo Integrado

v4.0 — Multi-Agent Collaborative Reasoning:
  - Novo nível "collaborative" em classify_complexity():
    queries de raciocínio complexo (explain, compare, architect, review, debug why)
    acionam pipeline paralelo com GPU0+GPU1+Agentes do workspace
  - collaborative_reasoning(): 3 tracks paralelos:
    Track A: GPU0 qwen3:8b (análise profunda)
    Track B: GPU1 qwen3:1.7b (hipótese rápida)
    Track C: Agentes especializados via API 8503 (RAG, Security, Performance, etc.)
  - Síntese final por GPU0 combinando todas as fontes
  - 24 agentes do workspace disponíveis via AGENT_REGISTRY
  - Bus de comunicação: publica TASK_START/TASK_END/COORDINATOR no bus
  - Fallback gracioso: se API 8503 offline → degrada para heavy (GPU0-only)

v3.0 — Pipeline Dual-GPU 2-Estágios (mantido):
  - light → GPU1 (qwen3:1.7b) → evaluate → fallback GPU0
  - medium → GPU1 (qwen3:0.6b) → Strategy B
  - heavy → GPU0 (qwen3:8b) direto
  - mapreduce → Strategy C MAP+REDUCE

v2.0 — Melhorias CLINE/tool-calling (mantido):
  - Smart truncation, tool defs preservation, sanitização

Port: 8512
"""
import asyncio
import hashlib
import httpx
import json
import re
import time
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("llm-optimizer")

OLLAMA_BASE = "http://localhost:11434"   # GPU0 — RTX 2060 SUPER (8GB)
OLLAMA_GPU1 = "http://localhost:11435"   # GPU1 — GTX 1050 (2GB)

# Modelos que devem rodar na GPU1 (leves, cabem em 2GB VRAM)
GPU1_MODELS = {"qwen3:0.6b", "qwen3:1.7b"}


def get_ollama_url(model: str) -> str:
    """Roteia para GPU1 se o modelo for leve, senão GPU0."""
    if model in GPU1_MODELS:
        return OLLAMA_GPU1
    return OLLAMA_BASE


# Limites de tokens (aproximação: 1 token ≈ 4 chars)
THRESHOLD_SMALL  = 2000   # < 2000 → Strategy A: modelo padrão
THRESHOLD_MEDIUM = 6000   # 2000-6000 → Strategy B: modelo leve
# > 6000 → Strategy C: map-reduce paralelo

# Modelos por estratégia
MODEL_FAST    = "qwen3:4b"    # qualidade/velocidade padrão — Strategy A
MODEL_LIGHT   = "qwen3:0.6b"  # ultra-rápido para Strategy B (3k-6k tokens)
MODEL_MICRO   = "qwen3:0.6b"  # ultra-rápido para sumarização paralela MAP
MODEL_SYNTH   = "qwen3:4b"    # síntese REDUCE — modelo maior para qualidade (v2.0)

# Timeout por request Ollama (segundos) — aumentado para Strategy C
TIMEOUT_EACH  = 1200

# Número máximo de workers paralelos no map-reduce
MAX_WORKERS   = 4

# Limites de truncamento (v2.0 — aumentados)
MAX_SYSTEM_CHARS       = 12000  # system prompt: até 12k chars (~3k tokens)
MAX_LAST_MSG_CHARS     = 6000   # última mensagem do user
REDUCE_SYSTEM_CHARS    = 8000   # system no REDUCE (era 3k, agora 8k)
REDUCE_LAST_MSG_CHARS  = 4000   # última msg no REDUCE (era 3k, agora 4k)

STATS = {"total": 0, "strategy_a": 0, "strategy_b": 0, "strategy_c": 0,
         "errors": 0, "tokens_saved": 0, "dedup_hits": 0,
         "tool_call_detected": 0, "smart_truncations": 0,
         "collaborative": 0, "agents_invoked": 0, "collaborative_fallbacks": 0}

# In-flight deduplication: evita múltiplas chamadas Ollama para o mesmo request
_in_flight: dict[str, asyncio.Future] = {}

# Histograma simples de duração por strategy
_durations: dict[str, list] = {"A": [], "B": [], "C": [], "COLLAB": []}

# ── Multi-Agent Collaborative Config (v4.0) ──────────────────────────

AGENT_API_BASE = "http://localhost:8503"   # API de agentes do workspace
AGENT_TIMEOUT  = 60.0                     # Timeout para chamadas à API
MAX_AGENTS_PER_REQUEST = 5                # Máx agentes por request colaborativo

# Registro completo dos 24 agentes do workspace
AGENT_REGISTRY = {
    # ── Agentes de Linguagem ──
    "python":      {"type": "language", "endpoint": "/code/generate", "keywords": ["python", "fastapi", "flask", "django", "pip", "pandas", "numpy", "async", "pytest", ".py"], "weight": 10},
    "javascript":  {"type": "language", "endpoint": "/code/generate", "keywords": ["javascript", "node", "express", "react", "vue", "npm", "jest", "dom", ".js"], "weight": 8},
    "typescript":  {"type": "language", "endpoint": "/code/generate", "keywords": ["typescript", "ts", "next.js", "nestjs", "angular", "interface", "generic", ".ts"], "weight": 8},
    "go":          {"type": "language", "endpoint": "/code/generate", "keywords": ["golang", "go ", "goroutine", "channel", "grpc", "concurren", ".go"], "weight": 7},
    "rust":        {"type": "language", "endpoint": "/code/generate", "keywords": ["rust", "cargo", "tokio", "ownership", "borrow", "wasm", ".rs"], "weight": 7},
    "java":        {"type": "language", "endpoint": "/code/generate", "keywords": ["java", "spring", "maven", "gradle", "jpa", "hibernate", "junit", ".java"], "weight": 7},
    "csharp":      {"type": "language", "endpoint": "/code/generate", "keywords": ["c#", "csharp", ".net", "asp.net", "blazor", "entity framework", "unity", ".cs"], "weight": 7},
    "php":         {"type": "language", "endpoint": "/code/generate", "keywords": ["php", "laravel", "symfony", "wordpress", "composer", ".php"], "weight": 6},
    # ── Agentes Especializados ──
    "security":    {"type": "specialized", "endpoint": "/security/capabilities", "keywords": ["security", "segurança", "vulnerab", "owasp", "cwe", "injection", "xss", "secret", "credential", "auth"], "weight": 9},
    "performance": {"type": "specialized", "endpoint": "/performance/capabilities", "keywords": ["performance", "benchmark", "load test", "latência", "throughput", "profil", "otimiz", "lento", "slow"], "weight": 8},
    "review":      {"type": "specialized", "endpoint": "/review/capabilities", "keywords": ["review", "code review", "qualidade", "quality gate", "approve", "reject", "duplication", "complex"], "weight": 8},
    "data":        {"type": "specialized", "endpoint": "/data/capabilities", "keywords": ["data", "etl", "pipeline", "analytics", "csv", "json", "transform", "dados"], "weight": 7},
    "bpm":         {"type": "specialized", "endpoint": "/bpm/templates", "keywords": ["bpmn", "processo", "fluxo", "workflow", "diagram", "drawio", "arquitetura"], "weight": 6},
    "confluence":  {"type": "specialized", "endpoint": "/confluence/capabilities", "keywords": ["document", "docs", "adr", "rfc", "runbook", "wiki", "confluence"], "weight": 6},
    "opensearch":  {"type": "specialized", "endpoint": "/opensearch/health", "keywords": ["search", "opensearch", "elastic", "index", "semantic", "embedding"], "weight": 7},
    "homelab":     {"type": "specialized", "endpoint": "/homelab/server-health", "keywords": ["homelab", "servidor", "server", "ssh", "systemd", "systemctl", "docker", "container"], "weight": 8},
    "banking":     {"type": "specialized", "endpoint": "/banking/status", "keywords": ["bank", "banco", "saldo", "extrato", "pix", "cartão", "financ"], "weight": 5},
    "home_auto":   {"type": "specialized", "endpoint": "/home/devices", "keywords": ["home", "automação", "luz", "smart", "google assistant", "dispositivo", "rotina"], "weight": 5},
    "po_agent":    {"type": "specialized", "endpoint": "/jira/board", "keywords": ["jira", "backlog", "sprint", "ticket", "story", "epic", "kanban", "scrum"], "weight": 6},
    "instructor":  {"type": "specialized", "endpoint": "/instructor/status", "keywords": ["treinar", "train", "instructor", "aprendizado", "learning"], "weight": 5},
    # ── RAG (sempre incluído em collaborative) ──
    "rag":         {"type": "infra", "endpoint": "/rag/search", "keywords": [], "weight": 15},
}

# Estatísticas do pipeline colaborativo
_collab_stats = {
    "total_requests": 0,
    "total_agents_invoked": 0,
    "agent_usage": {},       # agent_name → count
    "avg_duration_s": 0.0,
    "fallback_count": 0,
    "last_request_at": None,
}


def count_tokens(messages: list) -> int:
    """Estimativa rápida de tokens."""
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    return total_chars // 4


def choose_strategy(token_count: int) -> str:
    if token_count < THRESHOLD_SMALL:
        return "A"
    elif token_count < THRESHOLD_MEDIUM:
        return "B"
    return "C"


def detect_tool_calling(system_content: str) -> bool:
    """Detecta se o system prompt contém instruções de tool-calling (CLINE, etc.)."""
    tool_patterns = [
        r"<tool_name>",
        r"execute_command",
        r"read_file",
        r"write_to_file",
        r"list_files",
        r"search_files",
        r"replace_in_file",
        r"attempt_completion",
        r"ask_followup_question",
        r"<parameter",
        r"tool_use",
        r"function_call",
    ]
    for pattern in tool_patterns:
        if re.search(pattern, system_content, re.IGNORECASE):
            return True
    return False


def sanitize_messages(messages: list) -> list:
    """
    Sanitiza mensagens para formato aceito pelo Ollama /api/chat.
    CLINE pode enviar: content como array, campos extras (tool_calls, name, etc.),
    roles inválidos (tool, function), imagens inline.
    """
    sanitized = []
    VALID_ROLES = {"system", "user", "assistant"}

    for msg in messages:
        role = msg.get("role", "user")

        # Converte roles não suportados pelo Ollama
        if role not in VALID_ROLES:
            if role in ("tool", "function"):
                role = "user"
            else:
                role = "user"

        # Converte content array para string (CLINE multimodal)
        content = msg.get("content", "")
        if isinstance(content, list):
            # Array de content parts: [{"type":"text","text":"..."}, {"type":"image_url",...}]
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        text_parts.append("[imagem omitida]")
                    else:
                        text_parts.append(str(part))
                elif isinstance(part, str):
                    text_parts.append(part)
            content = "\n".join(text_parts)
        elif not isinstance(content, str):
            content = str(content) if content is not None else ""

        # Só inclui role e content — Ollama não aceita outros campos
        sanitized.append({"role": role, "content": content})

    return sanitized


def smart_truncate_system(content: str, max_chars: int) -> str:
    """
    Truncamento inteligente de system prompt:
    1. Preserva o INÍCIO (identidade e regras gerais)
    2. Preserva TOOL DEFINITIONS se detectadas
    3. Preserva o FINAL (instruções de formato de saída)
    4. Corta o meio (exemplos, contexto detalhado)
    """
    if len(content) <= max_chars:
        return content

    STATS["smart_truncations"] += 1

    # Reserva 40% para início, 30% para tool defs, 30% para final
    head_budget = int(max_chars * 0.40)
    tool_budget = int(max_chars * 0.30)
    tail_budget = int(max_chars * 0.30)

    head = content[:head_budget]

    # Extrai tool definitions se existirem
    tool_section = ""
    tool_markers = [
        # CLINE tool markers
        (r"# Tool Use.*?(?=\n# [A-Z]|\Z)", re.DOTALL),
        (r"## Tools.*?(?=\n## [A-Z]|\Z)", re.DOTALL),
        (r"<tools>.*?</tools>", re.DOTALL),
        # Generic tool/function definitions
        (r"Available tools:.*?(?=\n\n[A-Z]|\Z)", re.DOTALL),
        (r"You have access to.*?tools.*?(?=\n\n[A-Z]|\Z)", re.DOTALL),
    ]
    for pattern, flags in tool_markers:
        match = re.search(pattern, content, flags)
        if match:
            tool_section = match.group(0)[:tool_budget]
            break

    # Se não achou tool section, tenta extrair blocos <tool_name>
    if not tool_section:
        tool_blocks = re.findall(r"<tool_name>.*?</tool_name>", content, re.DOTALL)
        if tool_blocks:
            tool_section = "\n".join(tool_blocks)[:tool_budget]

    tail = content[-tail_budget:]

    # Monta resultado
    parts = [head]
    if tool_section and tool_section not in head:
        parts.append(f"\n\n[... contexto intermediário omitido ...]\n\n{tool_section}")
    parts.append(f"\n\n[... contexto omitido ({len(content) - max_chars} chars) ...]\n\n{tail}")

    result = "".join(parts)
    # Garante que não excedemos o budget total (com margem)
    if len(result) > max_chars + 500:
        result = result[:max_chars]

    return result


# ── Pipeline Helpers (v3.0) ────────────────────────────────────────────

def classify_complexity(messages: list, token_count: int) -> str:
    """
    Classifica a complexidade do request para decidir roteamento GPU.
    Retorna: 'light' (GPU1), 'medium' (GPU1 0.6b), 'heavy' (GPU0),
             'collaborative' (multi-agent), 'mapreduce' (Strategy C)
    """
    system_content = " ".join(
        str(m.get("content", "")) for m in messages if m.get("role") == "system"
    )
    has_tool_calling = detect_tool_calling(system_content)
    msg_count = len([m for m in messages if m.get("role") != "system"])

    # Tool-calling (Cline) → sempre GPU0 para qualidade (latência importa)
    if has_tool_calling:
        if token_count > THRESHOLD_MEDIUM:
            return "mapreduce"
        return "heavy"

    # Contextos muito grandes → map-reduce
    if token_count > THRESHOLD_MEDIUM:
        return "mapreduce"

    # ── Detecção de raciocínio colaborativo (v4.0) ──
    # Queries de raciocínio complexo sem tool-calling, 200-5000 tokens
    last_content = str(messages[-1].get("content", "")).lower() if messages else ""

    if 200 <= token_count <= 5000 and not has_tool_calling:
        # Padrões de raciocínio que se beneficiam de múltiplos agentes
        collab_patterns = [
            r"\b(explain|explique|compare|comparar)\b",
            r"\b(best approach|melhor abordagem|best practice|boa prática)\b",
            r"\b(trade.?off|prós?\s*e?\s*contras?|pros?\s*and?\s*cons?)\b",
            r"\b(review|revisar|analis[ae]r|analyz[ae]|evaluate|avaliar)\b",
            r"\b(architect|arquitetur|design pattern|padrão de projeto)\b",
            r"\b(refactor|refatorar|otimiz|optimize|melhorar|improve)\b",
            r"\b(debug|depurar|why\s+(?:does|is|do)|por\s*que)\b",
            r"\b(recommend|recomendar|suggest|sugerir|qual\s+(?:usar|escolher))\b",
            r"\b(security|segurança|vulnerab|performance|benchmark)\b",
            r"\b(how\s+does|como\s+funciona|how\s+to\s+(?:build|create|implement))\b",
        ]
        collab_score = sum(1 for p in collab_patterns if re.search(p, last_content))

        # 2+ padrões detectados → collaborative
        if collab_score >= 2:
            return "collaborative"
        # 1 padrão + conversa multi-turn → collaborative
        if collab_score >= 1 and msg_count >= 3:
            return "collaborative"

    # Contextos médios → GPU1 com modelo leve
    if token_count >= THRESHOLD_SMALL:
        return "medium"

    # Detecção de tarefas complexas que precisam GPU0 mesmo com poucos tokens
    complex_patterns = [
        r"\b(implement|refactor|rewrite|redesign|architect)\b",
        r"\b(debug|fix.*bug|traceback|exception)\b",
        r"\b(create.*class|create.*module|build.*system)\b",
        r"```",  # code blocks = contexto técnico denso
    ]
    for pattern in complex_patterns:
        if re.search(pattern, last_content):
            return "heavy"

    # Multi-turn longo → GPU0
    if msg_count > 6:
        return "heavy"

    # Default: tarefas leves → GPU1
    return "light"


def evaluate_response_quality(response: str, messages: list) -> tuple[bool, str]:
    """
    Avalia se a resposta de GPU1 é boa o suficiente.
    Retorna (is_ok, reason).
    """
    if not response or not response.strip():
        return False, "empty"

    clean = response.strip()

    # Muito curta (< 15 chars para qualquer pergunta razoável)
    if len(clean) < 15:
        return False, f"too_short ({len(clean)} chars)"

    # Padrões de falha/confusão
    fail_patterns = [
        r"^(I don'?t know|I'?m not sure|I cannot|I can'?t)\b",
        r"^(Sorry|Desculpe|Não sei|Não consigo|Não posso)",
        r"^(As an AI|Como uma IA|Sou um modelo)",
        r"(\w+\s+){1,3}\1{3,}",  # repetição excessiva
    ]
    for pattern in fail_patterns:
        if re.search(pattern, clean, re.IGNORECASE):
            return False, f"fail_pattern: {pattern[:30]}"

    # Proporção: resposta deve ter pelo menos 10% do tamanho da pergunta
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = str(m.get("content", ""))
            break
    if last_user and len(last_user) > 100 and len(clean) < len(last_user) * 0.1:
        return False, f"ratio_low ({len(clean)}/{len(last_user)})"

    return True, "ok"


# ── Multi-Agent Collaborative Functions (v4.0) ─────────────────────────

def select_relevant_agents(messages: list, complexity_hints: dict = None) -> list[dict]:
    """
    Analisa mensagens e seleciona até MAX_AGENTS_PER_REQUEST agentes relevantes.
    RAG sempre incluído. Pontuação por keyword matching + weight.
    Retorna: [{agent_name, agent_info, score}] ordenado por score desc.
    """
    # Extrai texto da última mensagem do user + system prompt
    last_user_content = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_content = str(m.get("content", "")).lower()
            break

    system_content = " ".join(
        str(m.get("content", "")).lower() for m in messages if m.get("role") == "system"
    )
    search_text = f"{last_user_content} {system_content}"

    scored = []
    for agent_name, info in AGENT_REGISTRY.items():
        if agent_name == "rag":
            # RAG sempre incluído com score máximo
            scored.append({"agent_name": agent_name, "agent_info": info, "score": 100})
            continue

        score = 0
        for kw in info["keywords"]:
            if kw.lower() in search_text:
                score += info["weight"]

        if score > 0:
            scored.append({"agent_name": agent_name, "agent_info": info, "score": score})

    # Ordena por score descendente e limita
    scored.sort(key=lambda x: x["score"], reverse=True)
    selected = scored[:MAX_AGENTS_PER_REQUEST]

    # Garante RAG está incluído
    rag_present = any(s["agent_name"] == "rag" for s in selected)
    if not rag_present:
        rag_info = AGENT_REGISTRY["rag"]
        selected.insert(0, {"agent_name": "rag", "agent_info": rag_info, "score": 100})
        if len(selected) > MAX_AGENTS_PER_REQUEST:
            selected = selected[:MAX_AGENTS_PER_REQUEST]

    log.info(f"[COLLAB] Agentes selecionados: {[s['agent_name'] for s in selected]}")
    return selected


async def invoke_agent(client: httpx.AsyncClient, agent_name: str,
                       endpoint: str, payload: dict) -> dict | None:
    """
    Invoca um agente via HTTP POST na API 8503.
    Retorna dict com resultado ou None se falhar.
    """
    url = f"{AGENT_API_BASE}{endpoint}"
    start = time.time()
    try:
        resp = await client.post(url, json=payload, timeout=AGENT_TIMEOUT)
        elapsed = time.time() - start
        if resp.status_code == 200:
            data = resp.json()
            log.info(f"[COLLAB] Agent {agent_name} OK ({elapsed:.1f}s) → {len(str(data))} chars")
            return {"agent": agent_name, "status": "ok", "data": data, "duration": elapsed}
        else:
            log.warning(f"[COLLAB] Agent {agent_name} HTTP {resp.status_code} ({elapsed:.1f}s)")
            return None
    except httpx.TimeoutException:
        log.warning(f"[COLLAB] Agent {agent_name} TIMEOUT ({time.time()-start:.1f}s)")
        return None
    except httpx.ConnectError:
        log.warning(f"[COLLAB] Agent {agent_name} CONNECTION REFUSED")
        return None
    except Exception as e:
        log.warning(f"[COLLAB] Agent {agent_name} ERROR: {type(e).__name__}: {e}")
        return None


async def invoke_agents_parallel(messages: list, agents_list: list[dict]) -> dict:
    """
    Invoca todos os agentes selecionados em paralelo via asyncio.gather.
    Retorna {agent_name: result_data} para agentes que responderam.
    """
    # Extrai query da última mensagem do user
    query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            query = str(m.get("content", ""))[:2000]
            break

    async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
        tasks = []
        task_names = []
        for agent in agents_list:
            name = agent["agent_name"]
            info = agent["agent_info"]
            endpoint = info["endpoint"]

            # Constrói payload específico por tipo de agente
            if name == "rag":
                payload = {"query": query, "n_results": 5}
                endpoint = "/rag/search"
            elif info["type"] == "language":
                payload = {"language": name, "description": query, "context": ""}
                endpoint = "/code/generate"
            else:
                # Agentes especializados: endpoint GET → passamos query via params
                # Para endpoints GET, fazemos GET com query param
                payload = {"query": query}

            tasks.append(invoke_agent(client, name, endpoint, payload))
            task_names.append(name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filtra resultados válidos
    valid = {}
    for name, result in zip(task_names, results):
        if isinstance(result, Exception):
            log.warning(f"[COLLAB] Agent {name} exception: {result}")
        elif result is not None:
            valid[name] = result

    STATS["agents_invoked"] += len(valid)
    log.info(f"[COLLAB] {len(valid)}/{len(agents_list)} agentes responderam")
    return valid


def build_synthesis_prompt(question: str, gpu0_response: str, gpu1_response: str,
                           agent_results: dict) -> list[dict]:
    """
    Constrói o prompt de síntese combinando todas as fontes.
    Retorna lista de messages para alimentar o sintetizador (GPU0).
    """
    sections = []

    # Seção 1: Análise Principal (GPU0)
    if gpu0_response:
        sections.append(f"## 🔬 Análise Principal (GPU0 — qwen3:8b)\n{gpu0_response[:3000]}")

    # Seção 2: Hipótese Rápida (GPU1)
    if gpu1_response:
        sections.append(f"## ⚡ Hipótese Rápida (GPU1 — qwen3:1.7b)\n{gpu1_response[:1500]}")

    # Seção 3: Resultados dos Agentes
    for agent_name, result in agent_results.items():
        if result and isinstance(result, dict):
            data = result.get("data", result)
            # Extrai texto útil do resultado
            if isinstance(data, dict):
                # Tenta extrair campos comuns
                text = (data.get("code", "") or data.get("content", "") or
                        data.get("results", "") or data.get("message", "") or
                        str(data))[:1200]
            elif isinstance(data, list):
                text = "\n".join(str(item)[:300] for item in data[:4])
            else:
                text = str(data)[:1200]

            if text and text.strip():
                icon = {"rag": "📚", "security": "🔒", "performance": "📈",
                        "review": "✅", "data": "📊", "homelab": "🖥️",
                        "opensearch": "🔍"}.get(agent_name, "🤖")
                agent_label = agent_name.replace("_", " ").title()
                sections.append(f"## {icon} {agent_label} Agent\n{text}")

    # Limita tamanho total do contexto de síntese
    combined_context = "\n\n".join(sections)
    if len(combined_context) > 6000:
        combined_context = combined_context[:6000] + "\n\n[... truncado para síntese ...]"

    system_prompt = (
        "Você é um Sintetizador Inteligente do Sistema Multi-Agente Eddie. "
        "Múltiplos agentes especialistas analisaram a mesma questão em paralelo. "
        "Sua tarefa é:\n"
        "1. Combinar as análises em uma resposta COESA, PRECISA e COMPLETA\n"
        "2. Resolver conflitos entre fontes — priorize informações corroboradas por múltiplas fontes\n"
        "3. Citar qual agente forneceu cada insight relevante (quando aplicável)\n"
        "4. Se algum agente encontrou problemas de segurança ou performance, DESTAQUE-os\n"
        "5. Mantenha a resposta PRÁTICA e ACIONÁVEL\n"
        "6. Responda no mesmo idioma da pergunta original\n"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"## Pergunta Original\n{question[:2000]}\n\n"
            f"## Análises dos Especialistas\n{combined_context}\n\n"
            "Sintetize uma resposta completa e coesa combinando todos os insights acima."
        )}
    ]


async def collaborative_reasoning(messages: list, body: dict,
                                   token_count: int) -> str:
    """
    Pipeline Multi-Agente Colaborativo (v4.0):
    1. Seleciona agentes relevantes por keyword matching
    2. Lança 3 tracks paralelos:
       Track A: GPU0 qwen3:8b (deep analysis)
       Track B: GPU1 qwen3:1.7b (quick hypothesis) 
       Track C: Agentes API 8503 (RAG + especializados)
    3. Síntese final por GPU0 combinando todas as fontes
    4. Publica no bus de comunicação
    Retorna: string com resposta sintetizada
    """
    collab_start = time.time()
    _collab_stats["total_requests"] += 1
    _collab_stats["last_request_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Extrai pergunta original
    question = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            question = str(m.get("content", ""))
            break

    log.info(f"[COLLAB] ═══ Pipeline Colaborativo iniciado | {token_count} tokens ═══")

    # ── Passo 1: Seleciona agentes relevantes ──
    agents_list = select_relevant_agents(messages)

    # ── Passo 2: Lança 3 tracks paralelos ──
    log.info("[COLLAB] Lançando 3 tracks paralelos: GPU0 + GPU1 + Agents")

    # Publica TASK_START no bus (fire-and-forget)
    asyncio.create_task(_publish_to_bus("task_start", "llm-proxy-v4", "all",
                                       f"Collaborative reasoning: {question[:100]}",
                                       {"token_count": token_count, "agents": [a["agent_name"] for a in agents_list]}))

    # Track A: GPU0 deep analysis
    gpu0_msgs = [
        {"role": "system", "content": (
            "Você é um especialista sênior com profundo conhecimento técnico. "
            "Analise a questão de forma APROFUNDADA, considere edge cases, "
            "trade-offs, e forneça exemplos concretos quando possível. "
            "Seja detalhado e preciso."
        )}
    ] + [m for m in messages if m.get("role") != "system"]

    # Track B: GPU1 quick hypothesis
    gpu1_msgs = [
        {"role": "system", "content": (
            "Forneça uma resposta CONCISA e DIRETA à questão. "
            "Foque nos pontos-chave e na solução mais prática. "
            "Máximo 200 palavras."
        )}
    ] + [m for m in messages if m.get("role") != "system"]

    # Track C: Agentes API 8503

    # Executa em paralelo
    track_a_task = ollama_chat(gpu0_msgs, "qwen3:8b", stream=False,
                               options={"num_ctx": 8192, "num_predict": 2048, "temperature": 0.7})
    track_b_task = ollama_chat(gpu1_msgs, "qwen3:1.7b", stream=False,
                               options={"num_ctx": 4096, "num_predict": 512, "temperature": 0.7})
    track_c_task = invoke_agents_parallel(messages, agents_list)

    results = await asyncio.gather(
        track_a_task, track_b_task, track_c_task,
        return_exceptions=True
    )

    gpu0_response = results[0] if not isinstance(results[0], Exception) else ""
    gpu1_response = results[1] if not isinstance(results[1], Exception) else ""
    agent_results = results[2] if not isinstance(results[2], Exception) else {}

    if isinstance(results[0], Exception):
        log.error(f"[COLLAB] Track A (GPU0) FAILED: {results[0]}")
    if isinstance(results[1], Exception):
        log.warning(f"[COLLAB] Track B (GPU1) FAILED: {results[1]}")
    if isinstance(results[2], Exception):
        log.warning(f"[COLLAB] Track C (Agents) FAILED: {results[2]}")

    gpu0_time = time.time() - collab_start
    log.info(f"[COLLAB] Tracks concluídos em {gpu0_time:.1f}s | "
             f"GPU0={'OK' if gpu0_response else 'FAIL'} | "
             f"GPU1={'OK' if gpu1_response else 'FAIL'} | "
             f"Agents={len(agent_results)}/{len(agents_list)}")

    # Atualiza stats de uso por agente
    for agent_name in agent_results:
        _collab_stats["agent_usage"][agent_name] = _collab_stats["agent_usage"].get(agent_name, 0) + 1
    _collab_stats["total_agents_invoked"] += len(agent_results)

    # ── Passo 3: Se GPU0 falhou E sem agentes, fallback impossível ──
    if not gpu0_response and not gpu1_response and not agent_results:
        log.error("[COLLAB] Todos os tracks falharam → fallback direto GPU0")
        _collab_stats["fallback_count"] += 1
        STATS["collaborative_fallbacks"] += 1
        return await ollama_chat(messages, "qwen3:8b", stream=False,
                                 options={"num_ctx": 8192, "num_predict": 2048})

    # ── Passo 3: Síntese final por GPU0 ──
    synth_start = time.time()
    synthesis_msgs = build_synthesis_prompt(question, gpu0_response, gpu1_response, agent_results)

    log.info("[COLLAB] Síntese final → GPU0 qwen3:8b")
    try:
        final_response = await ollama_chat(
            synthesis_msgs, "qwen3:8b", stream=False,
            options={"num_ctx": 8192, "num_predict": 2048, "temperature": 0.5}
        )
    except Exception as e:
        log.error(f"[COLLAB] Síntese FAILED: {e} → usando resposta GPU0 direta")
        final_response = gpu0_response or gpu1_response or "Erro na síntese colaborativa"
        _collab_stats["fallback_count"] += 1

    synth_time = time.time() - synth_start
    total_time = time.time() - collab_start

    # Atualiza stats
    _durations["COLLAB"].append(total_time)
    recent = _durations["COLLAB"][-50:]
    _collab_stats["avg_duration_s"] = sum(recent) / len(recent)

    log.info(f"[COLLAB] ═══ Síntese concluída em {synth_time:.1f}s | "
             f"Total: {total_time:.1f}s | Agents: {list(agent_results.keys())} ═══")

    # ── Passo 4: Publica resultado no bus ──
    asyncio.create_task(_publish_to_bus(
        "coordinator", "llm-proxy-v4", "all",
        f"Collaborative reasoning concluído em {total_time:.1f}s",
        {
            "agents_used": list(agent_results.keys()),
            "gpu0_ok": bool(gpu0_response),
            "gpu1_ok": bool(gpu1_response),
            "total_duration_s": round(total_time, 2),
            "synthesis_duration_s": round(synth_time, 2),
        }
    ))

    return final_response


async def _publish_to_bus(msg_type: str, source: str, target: str,
                          content: str, metadata: dict = None):
    """Publica mensagem no bus de comunicação via API 8503 (fire-and-forget)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{AGENT_API_BASE}/communication/publish", json={
                "message_type": msg_type,
                "source": source,
                "target": target,
                "content": content,
                "metadata": metadata or {}
            })
    except Exception as e:
        log.debug(f"[BUS] Publish falhou (non-critical): {e}")



    """
    Converte string em stream Ollama NDJSON (formato /api/chat).
    Emite chunks de ~30 chars + mensagem final done=true.
    """
    chunk_size = 30
    for i in range(0, len(content), chunk_size):
        piece = content[i:i + chunk_size]
        chunk = {
            "model": model,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message": {"role": "assistant", "content": piece},
            "done": False,
        }
        yield json.dumps(chunk).encode() + b"\n"
        await asyncio.sleep(0.003)

    # Final done message
    done_chunk = {
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": "stop",
        "total_duration": 0,
        "load_duration": 0,
        "prompt_eval_count": 0,
        "prompt_eval_duration": 0,
        "eval_count": len(content) // 4,
        "eval_duration": 0,
    }
    yield json.dumps(done_chunk).encode() + b"\n"


async def ollama_chat(messages: list, model: str, stream: bool = False,
                      options: dict = None) -> dict | AsyncIterator:
    """Chamada direta ao Ollama /api/chat (v2.1: com sanitização)."""
    # Sanitiza mensagens para formato Ollama-compatible
    clean_messages = sanitize_messages(messages)

    # Remove opções não suportadas pelo Ollama  
    clean_options = options or {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.7}
    # Garante que opções são tipos básicos
    clean_options = {k: v for k, v in clean_options.items() if isinstance(v, (int, float, str, bool))}

    payload = {
        "model": model,
        "messages": clean_messages,
        "stream": stream,
        "options": clean_options,
    }
    ollama_url = get_ollama_url(model)
    if ollama_url != OLLAMA_BASE:
        log.info(f"[GPU1] Roteando {model} → {ollama_url}")
    async with httpx.AsyncClient(timeout=TIMEOUT_EACH) as client:
        if stream:
            async def _stream():
                async with client.stream("POST", f"{ollama_url}/api/chat",
                                         json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield line
            return _stream()
        else:
            resp = await client.post(f"{ollama_url}/api/chat", json=payload)
            if resp.status_code != 200:
                body = resp.text[:500]
                log.error(f"[OLLAMA] {resp.status_code} para model={model} msgs={len(clean_messages)}: {body}")
                log.error(f"[OLLAMA] Roles: {[m['role'] for m in clean_messages]} Content sizes: {[len(m['content']) for m in clean_messages]}")
                resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")


async def summarize_chunk(chunk_messages: list, chunk_idx: int, total: int,
                          is_tool_calling: bool = False) -> str:
    """Sumariza um chunk de contexto com o modelo micro (qwen3:0.6b)."""
    if is_tool_calling:
        prompt = (
            "Você é um assistente de sumarização para uma sessão de programação com tool-calling. "
            "Resuma os pontos-chave desta conversa de forma CONCISA em até 300 palavras. "
            "PRESERVE: nomes de ferramentas usadas, comandos executados, arquivos modificados, "
            "erros encontrados, e decisões tomadas. "
            "Não responda a perguntas, apenas resuma o contexto técnico.\n\n"
        )
    else:
        prompt = (
            "Você é um assistente de sumarização. "
            "Resuma os pontos-chave desta conversa de forma CONCISA em até 200 palavras. "
            "Preserve informações técnicas relevantes (código, erros, configurações). "
            "Não responda a perguntas, apenas resuma o contexto.\n\n"
        )
    summary_messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "\n".join(
            f"[{m['role'].upper()}]: {m['content'][:2000]}" for m in chunk_messages
        )},
    ]
    log.info(f"[MAP] chunk {chunk_idx+1}/{total} → {MODEL_MICRO}")
    start = time.time()
    result = await ollama_chat(summary_messages, MODEL_MICRO,
                               options={"num_ctx": 4096, "num_predict": 400, "temperature": 0.3})
    elapsed = time.time() - start
    log.info(f"[MAP] chunk {chunk_idx+1}/{total} concluído em {elapsed:.1f}s")
    return result


async def strategy_c_map_reduce(messages: list, original_model: str) -> str:
    """
    Map-Reduce (v2.0):
    1. Divide o histórico (excl. última msg do user) em N chunks
    2. Sumariza cada chunk em paralelo com qwen3:0.6b
    3. Sintetiza com qwen3:4b (modelo maior) usando os resumos + pergunta original
       com system prompt truncado inteligentemente (preserva tool defs)
    """
    log.info(f"[Strategy C] Map-Reduce iniciado — {len(messages)} msgs")

    # Separa system prompt, histórico e última mensagem
    system_msgs = [m for m in messages if m["role"] == "system"]
    user_msgs   = [m for m in messages if m["role"] != "system"]
    last_msg    = user_msgs[-1] if user_msgs else messages[-1]
    history     = user_msgs[:-1]  # histórico para comprimir

    # Detecta se é um client de tool-calling (CLINE, etc.)
    system_content_full = " ".join(str(m.get("content", "")) for m in system_msgs)
    is_tool_calling = detect_tool_calling(system_content_full)
    if is_tool_calling:
        STATS["tool_call_detected"] += 1
        log.info(f"[Strategy C] Tool-calling detectado! Usando smart truncation")

    # Trunca last_msg se maior que o limite
    last_content = str(last_msg.get('content', ''))
    if len(last_content) > MAX_LAST_MSG_CHARS:
        log.warning(f'[Strategy C] last_msg {len(last_content)} chars -> truncando para {MAX_LAST_MSG_CHARS}')
        last_msg = {**last_msg, 'content': last_content[:MAX_LAST_MSG_CHARS] + '\n\n[... truncado ...]'}

    # Trunca system_msgs — smart truncation se tool-calling detectado
    truncated_system = []
    for sm in system_msgs:
        sc = str(sm.get('content', ''))
        if len(sc) > MAX_SYSTEM_CHARS:
            if is_tool_calling:
                truncated_content = smart_truncate_system(sc, MAX_SYSTEM_CHARS)
                log.info(f'[Strategy C] system_msg {len(sc)} chars -> smart truncation para ~{len(truncated_content)} chars')
            else:
                truncated_content = sc[:MAX_SYSTEM_CHARS] + '\n\n[... contexto truncado ...]'
                log.warning(f'[Strategy C] system_msg {len(sc)} chars -> truncando para {MAX_SYSTEM_CHARS}')
            truncated_system.append({**sm, 'content': truncated_content})
        else:
            truncated_system.append(sm)

    # Edge case: sem histórico suficiente -> usa modelo micro direto com contexto truncado
    if len(history) < 2:
        # Com tool-calling, usar MODEL_SYNTH (qwen3:4b) para melhor qualidade
        fallback_model = MODEL_SYNTH if is_tool_calling else MODEL_MICRO
        fallback_ctx = 8192 if is_tool_calling else 4096
        log.info(f'[Strategy C] Histórico insuficiente -> fallback {fallback_model} direto (truncado)')
        return await ollama_chat(
            truncated_system + [last_msg], fallback_model,
            options={'num_ctx': fallback_ctx, 'num_predict': 1024, 'temperature': 0.7}
        )

    # Split do histórico em chunks
    n_workers = min(MAX_WORKERS, max(1, len(history) // 3 + 1))
    chunk_size = max(1, len(history) // n_workers)
    chunks = [history[i:i+chunk_size] for i in range(0, len(history), chunk_size)]
    chunks = chunks[:MAX_WORKERS]

    log.info(f"[MAP] {len(chunks)} chunks × {chunk_size} msgs → {MODEL_MICRO} × {len(chunks)} workers")

    # Fase MAP — paralela
    summaries = await asyncio.gather(
        *[summarize_chunk(c, i, len(chunks), is_tool_calling) for i, c in enumerate(chunks)],
        return_exceptions=True
    )

    # Trata erros de workers individuais
    valid_summaries = []
    for i, s in enumerate(summaries):
        if isinstance(s, Exception):
            log.warning(f"[MAP] chunk {i} falhou: {s}")
        else:
            valid_summaries.append(f"[Resumo {i+1}]: {s}")

    summary_block = "\n\n".join(valid_summaries)
    log.info(f"[REDUCE] {len(valid_summaries)}/{len(chunks)} chunks OK → {MODEL_SYNTH}")

    # Trunca para o REDUCE — v2.0: limites maiores, smart truncation
    reduce_system = []
    for sm in truncated_system:
        sc = str(sm.get('content', ''))
        if len(sc) > REDUCE_SYSTEM_CHARS:
            if is_tool_calling:
                reduce_system.append({**sm, 'content': smart_truncate_system(sc, REDUCE_SYSTEM_CHARS)})
            else:
                reduce_system.append({**sm, 'content': sc[:REDUCE_SYSTEM_CHARS]})
        else:
            reduce_system.append(sm)

    reduce_last_content = str(last_msg.get('content', ''))[:REDUCE_LAST_MSG_CHARS]
    reduce_last = {**last_msg, 'content': reduce_last_content}

    # Instrução de síntese — adaptada para tool-calling
    if is_tool_calling:
        reduce_instruction = (
            "RESUMOS do histórico anterior da sessão:\n\n"
            f"{summary_block}\n\n"
            "IMPORTANTE: Use as ferramentas disponíveis no system prompt para responder. "
            "Gere tool calls válidas seguindo o formato exato definido nas instruções."
        )
    else:
        reduce_instruction = (
            "RESUMOS do histórico anterior:\n\n"
            f"{summary_block}"
        )

    # Fase REDUCE — síntese final com modelo maior (v2.0: qwen3:4b, num_ctx=8192)
    reduce_messages = reduce_system + [
        {"role": "system", "content": reduce_instruction},
        reduce_last,
    ]

    start = time.time()
    result = await ollama_chat(
        reduce_messages, MODEL_SYNTH,
        options={"num_ctx": 8192, "num_predict": 1024, "temperature": 0.7}
    )
    log.info(f"[REDUCE] concluído em {time.time()-start:.1f}s com {MODEL_SYNTH}")
    return result


async def to_openai_stream(content: str, model: str, req_id: str = "chatcmpl-opt"):
    """Converte string em stream OpenAI-compatible (Server-Sent Events)."""
    chunk_size = 20
    for i in range(0, len(content), chunk_size):
        piece = content[i:i+chunk_size]
        data = {
            "id": req_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(0.005)

    # Final chunk: APENAS finish_reason, SEM delta vazio (OpenAI-compatible)
    data = {
        "id": req_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(data)}\n\n"
    yield "data: [DONE]\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("LLM Optimizer v4.0 iniciado (Multi-Agent Collaborative Pipeline) — porta 8512")
    log.info(f"Pipeline: light→GPU1(qwen3:1.7b) | medium→GPU1({MODEL_LIGHT}) | "
             f"heavy→GPU0(qwen3:8b) | collaborative→Multi-Agent | "
             f"mapreduce→MAP({MODEL_MICRO})+REDUCE({MODEL_SYNTH})")
    log.info(f"Agents API: {AGENT_API_BASE} | Max agents/req: {MAX_AGENTS_PER_REQUEST} | "
             f"Registry: {len(AGENT_REGISTRY)} agentes")
    log.info(f"Thresholds: small={THRESHOLD_SMALL} medium={THRESHOLD_MEDIUM} | "
             f"sys={MAX_SYSTEM_CHARS} last={MAX_LAST_MSG_CHARS}")
    yield
    log.info("LLM Optimizer v4.0 encerrado")


app = FastAPI(title="LLM Optimizer Proxy", version="4.0.0", lifespan=lifespan)


@app.get("/")
@app.head("/")
async def root():
    """Ollama compatibility — Cline checks this endpoint to verify server is running."""
    return PlainTextResponse("Ollama is running")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "4.0.0", "stats": STATS}


@app.get("/api/collaborative/stats")
async def collaborative_stats():
    """Estatísticas do pipeline colaborativo multi-agente."""
    return {
        "version": "4.0.0",
        "collaborative": {
            "total_requests": _collab_stats["total_requests"],
            "total_agents_invoked": _collab_stats["total_agents_invoked"],
            "agent_usage": _collab_stats["agent_usage"],
            "avg_duration_s": round(_collab_stats["avg_duration_s"], 2),
            "fallback_count": _collab_stats["fallback_count"],
            "last_request_at": _collab_stats["last_request_at"],
        },
        "agents_registry": {name: {"type": info["type"], "endpoint": info["endpoint"]}
                            for name, info in AGENT_REGISTRY.items()},
        "config": {
            "agent_api_base": AGENT_API_BASE,
            "agent_timeout_s": AGENT_TIMEOUT,
            "max_agents_per_request": MAX_AGENTS_PER_REQUEST,
        },
        "global_stats": STATS,
    }


@app.get("/metrics")
async def prometheus_metrics():
    """Endpoint Prometheus para monitoramento."""
    lines = [
        "# HELP llm_optimizer_requests_total Total de requests recebidos",
        "# TYPE llm_optimizer_requests_total counter",
        f'llm_optimizer_requests_total {{strategy="all"}} {STATS["total"]}',
        f'llm_optimizer_requests_total {{strategy="A"}} {STATS["strategy_a"]}',
        f'llm_optimizer_requests_total {{strategy="B"}} {STATS["strategy_b"]}',
        f'llm_optimizer_requests_total {{strategy="C"}} {STATS["strategy_c"]}',
        f'llm_optimizer_requests_total {{strategy="collaborative"}} {STATS["collaborative"]}',
        "",
        "# HELP llm_optimizer_errors_total Total de erros",
        "# TYPE llm_optimizer_errors_total counter",
        f"llm_optimizer_errors_total {STATS['errors']}",
        "",
        "# HELP llm_optimizer_tokens_saved_total Tokens salvos via otimização",
        "# TYPE llm_optimizer_tokens_saved_total counter",
        f"llm_optimizer_tokens_saved_total {STATS['tokens_saved']}",
        "",
        "# HELP llm_optimizer_dedup_hits_total Cache de deduplicação hits",
        "# TYPE llm_optimizer_dedup_hits_total counter",
        f"llm_optimizer_dedup_hits_total {STATS['dedup_hits']}",
        "",
        "# HELP llm_optimizer_tool_call_detected_total Tool-calling requests detectados",
        "# TYPE llm_optimizer_tool_call_detected_total counter",
        f"llm_optimizer_tool_call_detected_total {STATS['tool_call_detected']}",
        "",
        "# HELP llm_optimizer_smart_truncations_total Smart truncations executadas",
        "# TYPE llm_optimizer_smart_truncations_total counter",
        f"llm_optimizer_smart_truncations_total {STATS['smart_truncations']}",
        "",
        "# HELP llm_optimizer_up Service status",
        "# TYPE llm_optimizer_up gauge",
        "llm_optimizer_up 1",
        "",
        "# HELP llm_optimizer_collaborative_total Collaborative reasoning requests",
        "# TYPE llm_optimizer_collaborative_total counter",
        f"llm_optimizer_collaborative_total {STATS['collaborative']}",
        "",
        "# HELP llm_optimizer_agents_invoked_total Total agents invoked in collab",
        "# TYPE llm_optimizer_agents_invoked_total counter",
        f"llm_optimizer_agents_invoked_total {STATS['agents_invoked']}",
        "",
        "# HELP llm_optimizer_collaborative_fallbacks_total Collab fallbacks to GPU0",
        "# TYPE llm_optimizer_collaborative_fallbacks_total counter",
        f"llm_optimizer_collaborative_fallbacks_total {STATS['collaborative_fallbacks']}",
    ]

    # Adiciona duração média por strategy (se houver dados)
    lines.extend([
        "",
        "# HELP llm_optimizer_duration_seconds Duração média por strategy",
        "# TYPE llm_optimizer_duration_seconds gauge",
    ])
    for strat, durations in _durations.items():
        if durations:
            # Mantém últimas 100 amostras
            recent = durations[-100:]
            avg = sum(recent) / len(recent)
            lines.append(f'llm_optimizer_duration_seconds{{strategy="{strat}"}} {avg:.2f}')

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/v1/models")
async def list_models():
    """Lista modelos disponíveis (compatível OpenAI)."""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            models_raw = r.json().get("models", [])
        except Exception:
            models_raw = []

    return {
        "object": "list",
        "data": [
            {"id": m["name"], "object": "model", "created": 0,
             "owned_by": "ollama", "permission": [], "root": m["name"]}
            for m in models_raw
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Endpoint principal — compatível com OpenAI."""
    STATS["total"] += 1
    req_start = time.time()
    body = await request.json()
    messages  = body.get("messages", [])
    stream    = body.get("stream", False)
    req_model = body.get("model", MODEL_FAST)
    
    # PATCH: Redirecionar modelo quebrado (qwen2.5-coder:7b) para modelo estável (qwen3:8b)
    if req_model == "qwen2.5-coder:7b":
        log.info(f"[REDIRECT] {req_model} → qwen3:8b (modelo original instável)")
        req_model = "qwen3:8b"
        body["model"] = "qwen3:8b"

    token_count = count_tokens(messages)
    strategy = choose_strategy(token_count)

    log.info(f"[REQ] model={req_model} tokens≈{token_count} → Strategy {strategy}")

    # ── In-flight deduplication (somente para requests não-streaming) ─────
    req_hash = None
    if not stream:
        try:
            req_hash = hashlib.md5(
                json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]
        except Exception:
            req_hash = None

        if req_hash and req_hash in _in_flight:
            STATS["dedup_hits"] += 1
            log.info(f"[DEDUP] Request {req_hash} já em voo — aguardando resultado")
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(_in_flight[req_hash]), timeout=580
                )
                return result
            except (asyncio.TimeoutError, asyncio.CancelledError):
                log.warning(f"[DEDUP] Timeout aguardando {req_hash} — processando independente")
                req_hash = None

        if req_hash:
            loop = asyncio.get_event_loop()
            _in_flight[req_hash] = loop.create_future()

    try:
        # ── Strategy A: direto, modelo padrão ──────────────────────────────
        if strategy == "A":
            STATS["strategy_a"] += 1
            effective_model = MODEL_FAST
            if stream:
                async def _proxy_stream():
                    clean_msgs = sanitize_messages(body.get("messages", []))
                    payload = {"model": effective_model, "messages": clean_msgs,
                               "stream": True, "options": {"num_ctx": 8192, "num_predict": 2048}}
                    strat_url = get_ollama_url(effective_model)
                    async with httpx.AsyncClient(timeout=TIMEOUT_EACH) as c:
                        async with c.stream("POST", f"{strat_url}/api/chat",
                                            json=payload, timeout=TIMEOUT_EACH) as resp:
                            async for line in resp.aiter_lines():
                                if not line:
                                    continue
                                try:
                                    d = json.loads(line)
                                    delta_content = d.get("message", {}).get("content", "")
                                    done = d.get("done", False)
                                    chunk = {
                                        "id": "chatcmpl-a", "object": "chat.completion.chunk",
                                        "created": int(time.time()), "model": effective_model,
                                        "choices": [{"index": 0, "delta": {"content": delta_content},
                                                     "finish_reason": "stop" if done else None}],
                                    }
                                    yield f"data: {json.dumps(chunk)}\n\n"
                                    if done:
                                        yield "data: [DONE]\n\n"
                                        break
                                except json.JSONDecodeError:
                                    pass
                _durations["A"].append(time.time() - req_start)
                return StreamingResponse(_proxy_stream(), media_type="text/event-stream")
            else:
                content = await ollama_chat(messages, effective_model)
                _durations["A"].append(time.time() - req_start)
                resp = _openai_response(content, effective_model)
                if req_hash and req_hash in _in_flight and not _in_flight[req_hash].done():
                    _in_flight[req_hash].set_result(resp)
                    del _in_flight[req_hash]
                return resp

        # ── Strategy B: modelo leve ─────────────────────────────────────────
        elif strategy == "B":
            STATS["strategy_b"] += 1
            STATS["tokens_saved"] += token_count - THRESHOLD_SMALL
            effective_model = MODEL_LIGHT
            log.info(f"[Strategy B] Trocando {req_model} → {effective_model}")
            content = await ollama_chat(messages, effective_model,
                                        options={"num_ctx": 8192, "num_predict": 2048})
            _durations["B"].append(time.time() - req_start)
            if stream:
                return StreamingResponse(
                    to_openai_stream(content, effective_model),
                    media_type="text/event-stream"
                )
            resp = _openai_response(content, effective_model)
            if req_hash and req_hash in _in_flight and not _in_flight[req_hash].done():
                _in_flight[req_hash].set_result(resp)
                del _in_flight[req_hash]
            return resp

        # ── Strategy C: map-reduce paralelo ───────────────────────────────
        else:
            STATS["strategy_c"] += 1
            STATS["tokens_saved"] += token_count - THRESHOLD_MEDIUM
            log.info(f"[Strategy C] {token_count} tokens → map-reduce paralelo")
            content = await strategy_c_map_reduce(messages, req_model)
            _durations["C"].append(time.time() - req_start)
            if stream:
                return StreamingResponse(
                    to_openai_stream(content, MODEL_SYNTH),
                    media_type="text/event-stream"
                )
            resp = _openai_response(content, MODEL_SYNTH)
            if req_hash and req_hash in _in_flight and not _in_flight[req_hash].done():
                _in_flight[req_hash].set_result(resp)
                del _in_flight[req_hash]
            return resp

    except Exception as e:
        STATS["errors"] += 1
        log.error(f"[ERR] {e}")
        if req_hash and req_hash in _in_flight and not _in_flight[req_hash].done():
            _in_flight[req_hash].set_exception(e)
        if req_hash and req_hash in _in_flight:
            del _in_flight[req_hash]
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def api_chat(request: Request):
    """
    Ollama native endpoint — Pipeline Multi-Agente Colaborativo (v4.0)

    Fluxo:
      1. Sanitização + redireção + think=false
      2. classify_complexity() → light / medium / heavy / collaborative / mapreduce
      3. light  → GPU1 (qwen3:1.7b) → evaluate_response_quality()
                  → se ok: entrega / se falhou: fallback GPU0 (qwen3:8b)
      4. medium → GPU1 (qwen3:0.6b) direto (Strategy B)
      5. heavy  → GPU0 (qwen3:8b) direto
      6. collaborative → GPU0+GPU1+Agents paralelos → síntese GPU0
      7. mapreduce → strategy_c_map_reduce() → resultado em NDJSON Ollama
    """
    body = await request.json()
    model = body.get("model", "unknown")
    original_model = model
    is_stream = body.get("stream", True)  # Ollama default = stream
    pipeline_start = time.time()

    # ── Estágio 0: Sanitização, redireção, think=false ─────────────────
    if "messages" in body:
        body["messages"] = sanitize_messages(body["messages"])

    if model == "qwen2.5-coder:7b":
        body["model"] = "qwen3:8b"
        model = "qwen3:8b"
        log.info(f"[REDIRECT] qwen2.5-coder:7b → qwen3:8b (via /api/chat)")

    messages = body.get("messages", [])
    token_count = count_tokens(messages)

    # ── Estágio 1: Classificação de complexidade ───────────────────────
    complexity = classify_complexity(messages, token_count)
    log.info(f"[PIPELINE] model={model} | {token_count} tokens | complexity={complexity}")

    # ── Helper: proxy streaming direto para Ollama ─────────────────────
    async def _proxy_stream_ollama(target_model: str, target_body: dict, target_url: str):
        """Stream direto: bytes do Ollama → cliente. Formato NDJSON nativo."""
        try:
            timeout = httpx.Timeout(connect=15.0, read=300.0, write=30.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{target_url}/api/chat",
                                         json=target_body) as resp:
                    if resp.status_code == 200:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                    else:
                        error_body = await resp.aread()
                        log.error(f"[OLLAMA-ERR] /api/chat {resp.status_code}: {error_body[:300]}")
                        yield json.dumps({"model": target_model, "message": {"role": "assistant", "content": ""},
                                         "done": True, "done_reason": "error"}).encode() + b"\n"
        except httpx.ConnectError as e:
            log.error(f"[OLLAMA-ERR] Connection failed to {target_url}: {e}")
            yield json.dumps({"model": target_model, "message": {"role": "assistant", "content": ""},
                             "done": True, "done_reason": "error"}).encode() + b"\n"
        except httpx.ReadTimeout as e:
            log.error(f"[OLLAMA-ERR] Read timeout from {target_url}: {e}")
            yield json.dumps({"model": target_model, "message": {"role": "assistant", "content": ""},
                             "done": True, "done_reason": "error"}).encode() + b"\n"
        except Exception as e:
            log.error(f"[OLLAMA-ERR] Unexpected: {type(e).__name__}: {e}")
            yield json.dumps({"model": target_model, "message": {"role": "assistant", "content": ""},
                             "done": True, "done_reason": "error"}).encode() + b"\n"

    # ── Helper: build body para um modelo específico ───────────────────
    def _build_body(target_model: str, extra_options: dict = None) -> dict:
        b = {**body, "model": target_model}
        if target_model.startswith("qwen3"):
            b["think"] = False
        if extra_options:
            b.setdefault("options", {})
            b["options"].update(extra_options)
        return b

    # ══════════════════════════════════════════════════════════════════════
    # Estágio 2: HEAVY — GPU0 direto (qwen3:8b)
    # ══════════════════════════════════════════════════════════════════════
    if complexity == "heavy":
        STATS["strategy_a"] += 1
        target_body = _build_body(model)  # mantém qwen3:8b
        target_url = get_ollama_url(model)
        log.info(f"[PIPELINE] heavy → GPU0 {model} (direto)")
        return StreamingResponse(
            _proxy_stream_ollama(model, target_body, target_url),
            media_type="application/x-ndjson",
        )

    # ══════════════════════════════════════════════════════════════════════
    # Estágio 2: COLLABORATIVE — Multi-Agent Pipeline (v4.0)
    # ══════════════════════════════════════════════════════════════════════
    if complexity == "collaborative":
        STATS["collaborative"] += 1
        log.info(f"[PIPELINE] collaborative → Multi-Agent ({token_count} tokens)")
        try:
            result = await collaborative_reasoning(messages, body, token_count)
            elapsed = time.time() - pipeline_start
            log.info(f"[PIPELINE] collaborative concluído em {elapsed:.1f}s")

            if is_stream:
                return StreamingResponse(
                    to_ollama_ndjson_stream(result, original_model),
                    media_type="application/x-ndjson",
                )
            else:
                return JSONResponse({
                    "model": original_model,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "message": {"role": "assistant", "content": result},
                    "done": True, "done_reason": "stop",
                })
        except Exception as e:
            log.error(f"[PIPELINE] collaborative FAILED: {e} → fallback GPU0 direto")
            STATS["collaborative_fallbacks"] += 1
            target_body = _build_body("qwen3:8b")
            return StreamingResponse(
                _proxy_stream_ollama("qwen3:8b", target_body, OLLAMA_BASE),
                media_type="application/x-ndjson",
            )

    # ══════════════════════════════════════════════════════════════════════
    # Estágio 2: MAPREDUCE — Strategy C (GPU1 MAP + GPU0 REDUCE)
    # ══════════════════════════════════════════════════════════════════════
    if complexity == "mapreduce":
        STATS["strategy_c"] += 1
        log.info(f"[PIPELINE] mapreduce → Strategy C ({token_count} tokens)")
        try:
            result = await strategy_c_map_reduce(messages, model)
            elapsed = time.time() - pipeline_start
            log.info(f"[PIPELINE] mapreduce concluído em {elapsed:.1f}s")
            _durations["C"].append(elapsed)

            if is_stream:
                return StreamingResponse(
                    to_ollama_ndjson_stream(result, model),
                    media_type="application/x-ndjson",
                )
            else:
                return JSONResponse({
                    "model": model,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "message": {"role": "assistant", "content": result},
                    "done": True, "done_reason": "stop",
                })
        except Exception as e:
            log.error(f"[PIPELINE] mapreduce FAILED: {e} → fallback GPU0 direto")
            target_body = _build_body("qwen3:8b")
            return StreamingResponse(
                _proxy_stream_ollama("qwen3:8b", target_body, OLLAMA_BASE),
                media_type="application/x-ndjson",
            )

    # ══════════════════════════════════════════════════════════════════════
    # Estágio 2: MEDIUM — GPU1 com qwen3:0.6b (Strategy B)
    # ══════════════════════════════════════════════════════════════════════
    if complexity == "medium":
        STATS["strategy_b"] += 1
        medium_model = MODEL_LIGHT  # qwen3:0.6b
        target_body = _build_body(medium_model, {"num_ctx": 4096, "num_predict": 2048})
        target_url = get_ollama_url(medium_model)
        log.info(f"[PIPELINE] medium → GPU1 {medium_model} | {token_count} tokens")
        STATS["tokens_saved"] += token_count - THRESHOLD_SMALL
        return StreamingResponse(
            _proxy_stream_ollama(medium_model, target_body, target_url),
            media_type="application/x-ndjson",
        )

    # ══════════════════════════════════════════════════════════════════════
    # Estágio 2+3: LIGHT — GPU1 (qwen3:1.7b) → avalia → fallback GPU0
    # ══════════════════════════════════════════════════════════════════════
    # complexity == "light"
    STATS["strategy_a"] += 1
    light_model = "qwen3:1.7b"
    log.info(f"[PIPELINE] light → tentando GPU1 {light_model} primeiro")

    # Estágio 2a: tenta GPU1 non-streaming (rápido, geralmente < 3s)
    try:
        gpu1_start = time.time()
        gpu1_response = await ollama_chat(
            messages, light_model, stream=False,
            options={"num_ctx": 4096, "num_predict": 1024, "temperature": 0.7},
        )
        gpu1_elapsed = time.time() - gpu1_start

        # Estágio 2b: avalia qualidade da resposta
        is_ok, reason = evaluate_response_quality(gpu1_response, messages)

        if is_ok:
            elapsed = time.time() - pipeline_start
            log.info(f"[PIPELINE] light → GPU1 {light_model} OK ({gpu1_elapsed:.1f}s) | "
                     f"quality={reason} | total={elapsed:.1f}s")
            _durations["A"].append(elapsed)

            if is_stream:
                return StreamingResponse(
                    to_ollama_ndjson_stream(gpu1_response, original_model),
                    media_type="application/x-ndjson",
                )
            else:
                return JSONResponse({
                    "model": original_model,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "message": {"role": "assistant", "content": gpu1_response},
                    "done": True, "done_reason": "stop",
                })
        else:
            log.warning(f"[PIPELINE] light → GPU1 quality FAIL: {reason} ({gpu1_elapsed:.1f}s) "
                        f"→ fallback GPU0 {model}")

    except Exception as e:
        log.warning(f"[PIPELINE] light → GPU1 ERROR: {type(e).__name__}: {e} → fallback GPU0")

    # Estágio 3: Fallback GPU0 — streaming real com qwen3:8b
    log.info(f"[PIPELINE] fallback → GPU0 {model} (streaming)")
    target_body = _build_body(model)
    return StreamingResponse(
        _proxy_stream_ollama(model, target_body, OLLAMA_BASE),
        media_type="application/x-ndjson",
    )

@app.get("/api/tags")
async def api_tags():
    """Ollama native endpoint - list available models"""
    print("[OLLAMA-COMPAT] /api/tags request")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{OLLAMA_BASE}/api/tags", timeout=30.0)
        if resp.status_code == 200:
            data = resp.json()
            if "models" in data:
                for model in data["models"]:
                    if model.get("name") == "qwen2.5-coder:7b":
                        model["name"] = "qwen3:8b"
                        model["model"] = "qwen3:8b"
            return JSONResponse(data)
        else:
            return JSONResponse({"error": f"Ollama error: {resp.status_code}"}, status_code=resp.status_code)


@app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE", "HEAD"])
async def api_passthrough(path: str, request: Request):
    """Catch-all passthrough for all other Ollama API endpoints (show, generate, pull, etc.)"""
    method = request.method
    url = f"{OLLAMA_BASE}/api/{path}"
    print(f"[OLLAMA-PASS] {method} /api/{path}")

    body = None
    if method in ("POST", "PUT"):
        try:
            body = await request.json()
            # Apply model redirection
            if isinstance(body, dict) and body.get("model") == "qwen2.5-coder:7b":
                body["model"] = "qwen3:8b"
                print(f"[REDIRECT] qwen2.5-coder:7b → qwen3:8b (via /api/{path})")
        except Exception:
            body = None

    # Streaming endpoints
    STREAMING_ENDPOINTS = {"generate", "pull", "push"}
    if path in STREAMING_ENDPOINTS:
        async def stream_gen():
            async with httpx.AsyncClient() as client:
                async with client.stream(method, url, json=body, timeout=600.0) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
        return StreamingResponse(stream_gen(), media_type="application/x-ndjson")

    # Non-streaming endpoints (show, version, ps, etc.)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(method=method, url=url, json=body, timeout=60.0)
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                return JSONResponse(content=resp.json(), status_code=resp.status_code)
            else:
                from fastapi.responses import Response
                return Response(content=resp.content, status_code=resp.status_code, media_type=ct)
        except Exception as e:
            print(f"[OLLAMA-PASS] ERROR /api/{path}: {e}")
            return JSONResponse({"error": str(e)}, status_code=502)


def _openai_response(content: str, model: str) -> JSONResponse:
    return JSONResponse({
        "id": f"chatcmpl-opt-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    })


if __name__ == "__main__":
    import uvicorn
    # timeout_keep_alive aumentado para suportar requisições longas do CLINE
    uvicorn.run(app, host="0.0.0.0", port=8512, workers=1, timeout_keep_alive=1200)
