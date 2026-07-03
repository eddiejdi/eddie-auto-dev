#!/usr/bin/env python3
"""
Homelab MCP Server — Integra Cline com Communication Bus, Secrets Agent,
API Estou Aqui, PostgreSQL e Trading Agent via Model Context Protocol (stdio).

Uso:
    python3 scripts/homelab_mcp_server.py

Configuração via variáveis de ambiente:
    HOMELAB_URL           - URL do Communication Bus (default: http://192.168.15.2:8503)
    SECRETS_AGENT_URL     - URL do Secrets Agent (default: http://192.168.15.2:8088)
    SECRETS_AGENT_API_KEY - Chave de API do Secrets Agent
    API_BASE_URL          - URL da API Estou Aqui (default: http://localhost:3000)
    DATABASE_URL          - Connection string PostgreSQL (Estou Aqui / governance)
    TRADING_DATABASE_URL  - Connection string PostgreSQL do trading agent (btc_trading DB)
    CHROMA_DB_PATH        - Path do ChromaDB (default: /home/homelab/myClaude/chroma_db)
"""
import importlib.util
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

# Adiciona raiz do projeto ao path para imports de tools/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from mcp.server import FastMCP

# ── Logging para stderr (stdout é reservado para protocolo MCP) ───────────
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("homelab-mcp")

# ── Configuração ──────────────────────────────────────────────────────────
HOMELAB_URL = os.environ.get("HOMELAB_URL", "http://192.168.15.2:8503")
SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://192.168.15.2:8088")
SECRETS_AGENT_API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://192.168.15.2:3000")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
TRADING_DATABASE_URL = os.environ.get("TRADING_DATABASE_URL", "")

# Token JWT em memória para API calls autenticadas
_jwt_token: Optional[str] = None

# ── Helpers HTTP ──────────────────────────────────────────────────────────

def _http_get(url: str, headers: dict | None = None, timeout: float = 15) -> dict:
    """GET request com tratamento de erro padronizado."""
    try:
        resp = requests.get(url, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")
        if "json" not in ct and resp.text.strip().startswith("<"):
            return {"ok": False, "error": f"Resposta HTML em vez de JSON (Content-Type: {ct}). A rota pode estar sendo interceptada pelo serve estático da app Flutter."}
        return {"ok": True, "status": resp.status_code, "data": resp.json()}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"Conexão recusada: {e}"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"Timeout após {timeout}s"}
    except requests.exceptions.HTTPError as e:
        try:
            body = e.response.json()
        except Exception:
            body = e.response.text[:500]
        return {"ok": False, "status": e.response.status_code, "error": str(body)}
    except json.JSONDecodeError:
        return {"ok": False, "error": "Resposta não é JSON válido."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _http_post(url: str, payload: dict, headers: dict | None = None, timeout: float = 15) -> dict:
    """POST request com tratamento de erro padronizado."""
    try:
        resp = requests.post(url, json=payload, headers=headers or {}, timeout=timeout)
        resp.raise_for_status()
        return {"ok": True, "status": resp.status_code, "data": resp.json()}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "error": f"Conexão recusada: {e}"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"Timeout após {timeout}s"}
    except requests.exceptions.HTTPError as e:
        try:
            body = e.response.json()
        except Exception:
            body = e.response.text
        return {"ok": False, "status": e.response.status_code, "error": str(body)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _api_headers() -> dict:
    """Headers para API Estou Aqui (inclui JWT se disponível)."""
    h = {"Content-Type": "application/json"}
    if _jwt_token:
        h["Authorization"] = f"Bearer {_jwt_token}"
    return h


def _secrets_headers() -> dict:
    """Headers para Secrets Agent."""
    h = {}
    if SECRETS_AGENT_API_KEY:
        h["X-API-KEY"] = SECRETS_AGENT_API_KEY
    return h


# ══════════════════════════════════════════════════════════════════════════
# MCP Server
# ══════════════════════════════════════════════════════════════════════════

mcp = FastMCP(
    name="homelab",
    instructions=(
        "MCP Server para integração com o homelab Eddie. "
        "Fornece acesso ao: Communication Bus (bus_*), Secrets Agent (secrets_*), "
        "API Estou Aqui (api_*), PostgreSQL genérico (db_*), "
        "Agent Governance (intent_*, journal_*), Memória compartilhada (memory_*) "
        "e Trading Agent BTC (trading_*). "
        "Para análise de mercado use trading_summary() como ponto de entrada. "
        "Dados de trading são somente-leitura do schema btc.* no PostgreSQL."
    ),
)

# ═══════════════════════════  COMMUNICATION BUS  ══════════════════════════

@mcp.tool()
def bus_health() -> str:
    """Verifica o status do Communication Bus do homelab (192.168.15.2:8503)."""
    result = _http_get(f"{HOMELAB_URL}/health")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def bus_get_messages(limit: int = 20) -> str:
    """Obtém mensagens recentes do Communication Bus.

    Args:
        limit: Número máximo de mensagens (default: 20).
    """
    result = _http_get(f"{HOMELAB_URL}/communication/messages?limit={limit}")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def bus_publish(target: str, content: str, message_type: str = "request") -> str:
    """Publica uma mensagem no Communication Bus do homelab.

    Args:
        target: Agente destino (ex: 'coordinator', 'python', 'all').
        content: Conteúdo da mensagem.
        message_type: Tipo da mensagem (request, response, error).
    """
    payload = {
        "message_type": message_type,
        "source": "copilot-mcp",
        "target": target,
        "content": content,
        "metadata": {
            "origin": "cline-mcp",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    result = _http_post(f"{HOMELAB_URL}/communication/publish", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def bus_record_result(language: str, success: bool, execution_time: float = 0.0, details: str = "") -> str:
    """Registra resultado de uma tarefa no Distributed Coordinator.

    Args:
        language: Linguagem/agente (ex: 'python', 'flutter', 'node').
        success: Se a tarefa foi bem-sucedida.
        execution_time: Tempo de execução em segundos.
        details: Detalhes adicionais.
    """
    payload = {
        "language": language,
        "success": success,
        "execution_time": execution_time,
        "details": details,
        "source": "copilot-mcp",
    }
    result = _http_post(f"{HOMELAB_URL}/distributed/record-result", payload)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def bus_search_by_agent(agent: str = "copilot") -> str:
    """Busca mensagens de um agente específico no interceptor.

    Args:
        agent: Nome do agente (default: copilot).
    """
    result = _http_get(f"{HOMELAB_URL}/interceptor/search/by-agent?agent={agent}")
    return json.dumps(result, ensure_ascii=False, indent=2)


# ═══════════════════════════  SECRETS AGENT  ══════════════════════════════

@mcp.tool()
def secrets_list() -> str:
    """Lista todos os secrets disponíveis no Secrets Agent."""
    result = _http_get(f"{SECRETS_AGENT_URL}/secrets", headers=_secrets_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def secrets_get(name: str) -> str:
    """Obtém um secret pelo nome.

    Args:
        name: Nome do secret (ex: 'eddie/telegram_bot_token', 'eddie/github_token').
    """
    result = _http_get(f"{SECRETS_AGENT_URL}/secrets/{name}", headers=_secrets_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def secrets_health() -> str:
    """Verifica se o Secrets Agent está online e saudável."""
    result = _http_get(f"{SECRETS_AGENT_URL}/secrets", headers=_secrets_headers())
    if result.get("ok"):
        count = len(result.get("data", []))
        return json.dumps({"ok": True, "status": "online", "secrets_count": count}, indent=2)
    return json.dumps({"ok": False, "status": "offline", "error": result.get("error", "")}, indent=2)


# ═══════════════════════════  API ESTOU AQUI  ═════════════════════════════

@mcp.tool()
def api_health() -> str:
    """Verifica o status da API Estou Aqui (backend Express)."""
    result = _http_get(f"{API_BASE_URL}/health")
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def api_auth_login(email: str, password: str) -> str:
    """Faz login na API Estou Aqui e armazena JWT para chamadas subsequentes.

    Args:
        email: E-mail do usuário.
        password: Senha do usuário.
    """
    global _jwt_token
    result = _http_post(f"{API_BASE_URL}/api/auth/login", {"email": email, "password": password})
    if result.get("ok") and "data" in result:
        token = result["data"].get("token")
        if token:
            _jwt_token = token
            result["data"]["token"] = token[:20] + "...[armazenado]"
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def api_events_list(
    lat: float = 0, lng: float = 0, radius: float = 0,
    category: str = "", city: str = "", status: str = ""
) -> str:
    """Lista eventos da plataforma Estou Aqui.

    Args:
        lat: Latitude para busca geográfica (0 = sem filtro).
        lng: Longitude para busca geográfica (0 = sem filtro).
        radius: Raio em km (0 = sem filtro).
        category: Filtrar por categoria (manifestacao, protesto, marcha, etc.).
        city: Filtrar por cidade.
        status: Filtrar por status (active, scheduled, completed).
    """
    params = []
    if lat and lng:
        params.extend([f"lat={lat}", f"lng={lng}"])
    if radius:
        params.append(f"radius={radius}")
    if category:
        params.append(f"category={category}")
    if city:
        params.append(f"city={city}")
    if status:
        params.append(f"status={status}")

    qs = "&".join(params)
    url = f"{API_BASE_URL}/api/events" + (f"?{qs}" if qs else "")
    result = _http_get(url, headers=_api_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def api_events_get(event_id: str) -> str:
    """Obtém detalhes de um evento específico.

    Args:
        event_id: UUID do evento.
    """
    result = _http_get(f"{API_BASE_URL}/api/events/{event_id}", headers=_api_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def api_events_create(
    title: str, description: str, category: str,
    latitude: float, longitude: float,
    city: str = "", state: str = "", scheduled_date: str = ""
) -> str:
    """Cria um novo evento na plataforma (requer login prévio via api_auth_login).

    Args:
        title: Título do evento.
        description: Descrição do evento.
        category: Categoria (manifestacao, protesto, marcha, ato, greve, ocupacao, vigilia, passeata, reuniao).
        latitude: Latitude do local.
        longitude: Longitude do local.
        city: Cidade.
        state: Estado (UF).
        scheduled_date: Data agendada (ISO 8601).
    """
    if not _jwt_token:
        return json.dumps({"ok": False, "error": "Login necessário. Use api_auth_login primeiro."}, indent=2)

    payload: dict[str, Any] = {
        "title": title,
        "description": description,
        "category": category,
        "latitude": latitude,
        "longitude": longitude,
    }
    if city:
        payload["city"] = city
    if state:
        payload["state"] = state
    if scheduled_date:
        payload["scheduledDate"] = scheduled_date

    result = _http_post(f"{API_BASE_URL}/api/events", payload, headers=_api_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def api_checkins_create(event_id: str, latitude: float, longitude: float) -> str:
    """Faz check-in em um evento (requer login prévio).

    Args:
        event_id: UUID do evento.
        latitude: Latitude atual do usuário.
        longitude: Longitude atual do usuário.
    """
    if not _jwt_token:
        return json.dumps({"ok": False, "error": "Login necessário. Use api_auth_login primeiro."}, indent=2)

    payload = {"eventId": event_id, "latitude": latitude, "longitude": longitude}
    result = _http_post(f"{API_BASE_URL}/api/checkins", payload, headers=_api_headers())
    return json.dumps(result, ensure_ascii=False, indent=2)


# ═══════════════════════════  POSTGRESQL  ═════════════════════════════════

@mcp.tool()
def db_execute_query(sql: str, params: str = "[]") -> str:
    """Executa uma query SQL no PostgreSQL do Estou Aqui.

    ATENÇÃO: Use apenas queries SELECT para leitura. Queries de escrita são bloqueadas.

    Args:
        sql: Query SQL (apenas SELECT permitido).
        params: Parâmetros da query como JSON array (default: []).
    """
    if not DATABASE_URL:
        return json.dumps({"ok": False, "error": "DATABASE_URL não configurada."}, indent=2)

    # Bloquear queries de escrita
    sql_upper = sql.strip().upper()
    blocked = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for kw in blocked:
        if sql_upper.startswith(kw):
            return json.dumps({"ok": False, "error": f"Operação {kw} bloqueada. Apenas SELECT permitido."}, indent=2)

    try:
        import psycopg2
        import psycopg2.extras

        parsed_params = json.loads(params) if params != "[]" else []

        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # LIMIT de segurança
        if "LIMIT" not in sql_upper:
            sql = sql.rstrip(";") + " LIMIT 100"

        cur.execute(sql, parsed_params or None)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        cur.close()
        conn.close()

        # Converter rows para serializable
        serialized = []
        for row in rows:
            serialized.append({k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in dict(row).items()})

        return json.dumps({
            "ok": True,
            "rows": serialized,
            "count": len(serialized),
            "columns": columns,
        }, ensure_ascii=False, indent=2, default=str)
    except ImportError:
        return json.dumps({"ok": False, "error": "psycopg2 não instalado."}, indent=2)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, indent=2)


@mcp.tool()
def db_list_tables() -> str:
    """Lista todas as tabelas do banco de dados Estou Aqui."""
    return db_execute_query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )


@mcp.tool()
def db_describe_table(table_name: str) -> str:
    """Descreve a estrutura de uma tabela (colunas, tipos, constraints).

    Args:
        table_name: Nome da tabela.
    """
    sql = """
        SELECT column_name, data_type, is_nullable, column_default,
               character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """
    return db_execute_query(sql, json.dumps([table_name]))


@mcp.tool()
def db_active_events() -> str:
    """Lista eventos ativos com contagem de check-ins."""
    sql = """
        SELECT e.id, e.title, e.category, e.city, e.status,
               e."createdAt", COUNT(c.id) as checkin_count
        FROM events e
        LEFT JOIN checkins c ON c."eventId" = e.id
        WHERE e.status = 'active'
        GROUP BY e.id
        ORDER BY e."createdAt" DESC
        LIMIT 50
    """
    return db_execute_query(sql)


# ═══════════════════════  AGENT GOVERNANCE  ═══════════════════════════════
#
# Ferramentas do Agent Governance Layer (Fase 0).
# Requerem DATABASE_URL configurado no ambiente.
# Documentação: docs/AGENT_GOVERNANCE_MIGRATION_PLAN.md

# Ações com risk_level >= medium ficam pendentes até aprovação humana (Fase 1).
# Ações none/low são auto-aprovadas imediatamente.
_AUTO_APPROVE_LEVELS = {"none", "low"}
_VALID_RISK_LEVELS   = {"none", "low", "medium", "high", "critical"}
_VALID_ACTION_TYPES  = {"restart", "deploy", "modify", "delete", "create", "query", "config", "other"}
_VALID_STATUSES      = {"pending", "approved", "rejected", "in_progress", "done", "failed", "expired"}


def _db_write(sql: str, params: tuple) -> dict:
    """Executa SQL de escrita no PostgreSQL do homelab (INSERT/UPDATE)."""
    if not DATABASE_URL:
        return {"ok": False, "error": "DATABASE_URL não configurada."}
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
        conn.commit()
        cur.close()
        conn.close()
        return {
            "ok": True,
            "rows": [dict(r) for r in rows],
        }
    except ImportError:
        return {"ok": False, "error": "psycopg2 não instalado."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _db_read_one(sql: str, params: tuple) -> dict:
    """Executa SELECT e retorna a primeira linha como dict (ou None)."""
    if not DATABASE_URL:
        return {"ok": False, "error": "DATABASE_URL não configurada."}
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return {"ok": True, "row": dict(row) if row else None}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _db_read_many(sql: str, params: tuple = ()) -> dict:
    """Executa SELECT e retorna todas as linhas."""
    if not DATABASE_URL:
        return {"ok": False, "error": "DATABASE_URL não configurada."}
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"ok": True, "rows": [dict(r) for r in rows]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def intent_declare(
    agent_id: str,
    action_type: str,
    description: str,
    target: str = "",
    risk_level: str = "medium",
    context: str = "{}",
) -> str:
    """Declara a intenção de executar uma ação antes de realizá-la.

    Deve ser chamado ANTES de qualquer ação que modifique o ambiente.
    Retorna intent_id para uso posterior em intent_check_status() e intent_complete().

    Ações com risk_level 'none' ou 'low' são auto-aprovadas imediatamente.
    Ações com risk_level 'medium', 'high' ou 'critical' ficam em status 'pending'
    até aprovação humana via Telegram (Fase 1 do Governance Layer).

    Args:
        agent_id:    Identificador do agente (ex: 'nextcloud_agent', 'claude_code').
        action_type: Tipo da ação — restart | deploy | modify | delete | create | query | config | other
        description: Descrição legível do que será feito e por quê.
        target:      Recurso afetado — serviço, arquivo, host, URL (opcional).
        risk_level:  Nível de risco — none | low | medium | high | critical (default: medium)
        context:     JSON com contexto adicional — estado atual, motivação, etc. (default: {})
    """
    if risk_level not in _VALID_RISK_LEVELS:
        return json.dumps({"ok": False, "error": f"risk_level inválido: '{risk_level}'. Use: {sorted(_VALID_RISK_LEVELS)}"}, ensure_ascii=False)

    if action_type not in _VALID_ACTION_TYPES:
        return json.dumps({"ok": False, "error": f"action_type inválido: '{action_type}'. Use: {sorted(_VALID_ACTION_TYPES)}"}, ensure_ascii=False)

    try:
        ctx = json.loads(context) if context else {}
    except json.JSONDecodeError:
        return json.dumps({"ok": False, "error": "context não é JSON válido."}, ensure_ascii=False)

    intent_id = f"intent-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    initial_status = "approved" if risk_level in _AUTO_APPROVE_LEVELS else "pending"

    result = _db_write(
        """
        INSERT INTO agent_actions
            (intent_id, agent_id, action_type, description, target,
             risk_level, status, context_snapshot,
             resolved_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING intent_id, status, created_at
        """,
        (
            intent_id, agent_id, action_type, description,
            target or None,
            risk_level, initial_status,
            json.dumps(ctx),
            datetime.now(timezone.utc) if initial_status == "approved" else None,
        ),
    )

    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)

    row = result["rows"][0] if result["rows"] else {}
    return json.dumps({
        "ok": True,
        "intent_id": intent_id,
        "status": initial_status,
        "auto_approved": initial_status == "approved",
        "message": (
            "Auto-aprovado — pode prosseguir." if initial_status == "approved"
            else "Aguardando aprovação humana. Chame intent_check_status() antes de executar."
        ),
        "created_at": str(row.get("created_at", "")),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def intent_check_status(intent_id: str) -> str:
    """Verifica o status de aprovação de uma intenção declarada.

    Retorna o status atual: pending | approved | rejected | expired.
    O agente deve verificar este status antes de executar qualquer ação
    que tenha sido declarada com risk_level >= medium.

    Fluxo recomendado:
        1. intent_declare(...)  → obtém intent_id
        2. intent_check_status(intent_id)  → verifica aprovação
        3. Se approved → executa a ação
        4. Se pending  → aguarda e tenta novamente (backoff sugerido: 30s)
        5. Se rejected | expired → aborta

    Args:
        intent_id: ID retornado por intent_declare().
    """
    result = _db_read_one(
        """
        SELECT intent_id, agent_id, action_type, description, target,
               risk_level, status, approved_by,
               created_at, resolved_at
        FROM agent_actions
        WHERE intent_id = %s
        """,
        (intent_id,),
    )

    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)

    if result["row"] is None:
        return json.dumps({"ok": False, "error": f"intent_id não encontrado: {intent_id}"}, ensure_ascii=False)

    row = {k: str(v) if v is not None and not isinstance(v, (str, int, float, bool)) else v
           for k, v in result["row"].items()}

    can_proceed = row["status"] == "approved"
    should_abort = row["status"] in ("rejected", "expired")

    return json.dumps({
        "ok": True,
        "intent_id": intent_id,
        "status": row["status"],
        "can_proceed": can_proceed,
        "should_abort": should_abort,
        "approved_by": row.get("approved_by"),
        "risk_level": row["risk_level"],
        "created_at": row.get("created_at"),
        "resolved_at": row.get("resolved_at"),
        "message": (
            "Aprovado — pode executar agora."          if can_proceed else
            "Rejeitado ou expirado — aborte a ação."  if should_abort else
            "Ainda aguardando aprovação humana."
        ),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def intent_complete(
    intent_id: str,
    outcome: str,
    success: bool = True,
    error_detail: str = "",
) -> str:
    """Registra a conclusão de uma intenção após executar a ação.

    Deve ser chamado SEMPRE após a execução, independente do resultado (sucesso ou falha).
    Atualiza o status para 'done' (sucesso) ou 'failed' (falha) e registra o resultado.

    Args:
        intent_id:    ID retornado por intent_declare().
        outcome:      Descrição do que aconteceu (ex: 'Serviço reiniciado com sucesso').
        success:      True se a execução foi bem-sucedida, False se falhou.
        error_detail: Detalhes do erro em caso de falha (opcional).
    """
    final_status = "done" if success else "failed"
    now = datetime.now(timezone.utc)

    result = _db_write(
        """
        UPDATE agent_actions
        SET status        = %s,
            outcome       = %s,
            error_detail  = %s,
            executed_at   = COALESCE(executed_at, %s),
            completed_at  = %s
        WHERE intent_id = %s
        RETURNING intent_id, status, outcome, completed_at
        """,
        (
            final_status,
            outcome,
            error_detail or None,
            now, now,
            intent_id,
        ),
    )

    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)

    if not result["rows"]:
        return json.dumps({"ok": False, "error": f"intent_id não encontrado: {intent_id}"}, ensure_ascii=False)

    row = result["rows"][0]
    return json.dumps({
        "ok": True,
        "intent_id": intent_id,
        "status": final_status,
        "outcome": outcome,
        "completed_at": str(row.get("completed_at", "")),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def journal_query(
    agent_id: str = "",
    action_type: str = "",
    target: str = "",
    status: str = "",
    risk_level: str = "",
    limit: int = 20,
) -> str:
    """Consulta o Action Journal — histórico persistente de ações dos agentes.

    Use antes de agir para saber o que já foi feito no mesmo target ou por outros agentes.
    Todos os parâmetros são opcionais e combinados como filtros AND.

    Args:
        agent_id:    Filtrar por agente específico (ex: 'nextcloud_agent').
        action_type: Filtrar por tipo — restart | deploy | modify | delete | create | query | config | other
        target:      Filtrar por target (busca parcial, case-insensitive).
        status:      Filtrar por status — pending | approved | rejected | done | failed | expired
        risk_level:  Filtrar por risco — none | low | medium | high | critical
        limit:       Máximo de registros (default: 20, máximo: 100).
    """
    limit = min(max(1, limit), 100)

    conditions = ["1=1"]
    params: list = []

    if agent_id:
        conditions.append("agent_id = %s")
        params.append(agent_id)
    if action_type:
        conditions.append("action_type = %s")
        params.append(action_type)
    if target:
        conditions.append("target ILIKE %s")
        params.append(f"%{target}%")
    if status:
        conditions.append("status = %s")
        params.append(status)
    if risk_level:
        conditions.append("risk_level = %s")
        params.append(risk_level)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT intent_id, agent_id, action_type, description, target,
               risk_level, status, approved_by, outcome,
               created_at, completed_at
        FROM agent_audit_log
        WHERE {where}
        LIMIT %s
    """
    params.append(limit)

    result = _db_read_many(sql, tuple(params))
    if not result["ok"]:
        return json.dumps(result, ensure_ascii=False)

    rows = [
        {k: str(v) if v is not None and not isinstance(v, (str, int, float, bool)) else v
         for k, v in row.items()}
        for row in result["rows"]
    ]

    return json.dumps({
        "ok": True,
        "count": len(rows),
        "actions": rows,
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════  RESOURCES  ══════════════════════════════════

@mcp.resource("homelab://bus/status")
def resource_bus_status() -> str:
    """Status atual do Communication Bus do homelab."""
    return bus_health()


@mcp.resource("homelab://secrets/status")
def resource_secrets_status() -> str:
    """Status do Secrets Agent."""
    return secrets_health()


@mcp.resource("estouaqui://api/routes")
def resource_api_routes() -> str:
    """Lista de rotas disponíveis na API Estou Aqui."""
    routes = {
        "auth": ["POST /api/auth/login", "POST /api/auth/register", "POST /api/auth/google", "GET /api/auth/profile"],
        "events": ["GET /api/events", "GET /api/events/:id", "POST /api/events", "PUT /api/events/:id", "DELETE /api/events/:id"],
        "checkins": ["POST /api/checkins", "DELETE /api/checkins/:id", "GET /api/checkins/event/:eventId"],
        "chat": ["GET /api/chat/:eventId", "POST /api/chat/:eventId"],
        "estimates": ["GET /api/estimates/:eventId", "POST /api/estimates/:eventId"],
        "notifications": ["POST /api/notifications/subscribe", "POST /api/notifications/send"],
        "alerts": ["GET /api/alerts/active", "GET /api/alerts/history", "POST /api/alerts/webhook"],
        "coalitions": ["GET /api/coalitions", "POST /api/coalitions", "PUT /api/coalitions/:id"],
        "webchat": ["GET /api/webchat/messages", "POST /api/webchat/send"],
        "health": ["GET /health"],
    }
    return json.dumps(routes, ensure_ascii=False, indent=2)


@mcp.resource("estouaqui://db/models")
def resource_db_models() -> str:
    """Modelos Sequelize do banco de dados Estou Aqui."""
    models = {
        "User": {"table": "Users", "id": "UUID", "fields": ["name", "email", "password", "googleId", "role", "avatar"]},
        "Event": {"table": "Events", "id": "UUID", "fields": ["title", "description", "category", "latitude", "longitude", "city", "state", "status", "organizer"]},
        "Checkin": {"table": "Checkins", "id": "UUID", "fields": ["userId", "eventId", "latitude", "longitude"]},
        "ChatMessage": {"table": "ChatMessages", "id": "UUID", "fields": ["userId", "eventId", "content"]},
        "CrowdEstimate": {"table": "CrowdEstimates", "id": "UUID", "fields": ["eventId", "userId", "estimate", "density", "area"]},
        "Coalition": {"table": "Coalitions", "id": "UUID", "fields": ["name", "description", "cause", "creatorId"]},
        "Notification": {"table": "Notifications", "id": "UUID", "fields": ["userId", "title", "body", "type"]},
        "TelegramGroup": {"table": "TelegramGroups", "id": "UUID", "fields": ["eventId", "groupId", "title"]},
        "BetaSignup": {"table": "BetaSignups", "id": "UUID", "fields": ["name", "email", "city", "phone", "motivation"]},
        "WebChatMessage": {"table": "WebChatMessages", "id": "UUID", "fields": ["content", "sender", "sessionId"]},
    }
    return json.dumps(models, ensure_ascii=False, indent=2)


# ═══════════════════════════  SHARED MEMORY  ══════════════════════════════

def _get_mem():
    """Importa agent_memory lazily para não atrasar startup do MCP server."""
    try:
        from tools.memory_layer import agent_memory
        return agent_memory
    except ImportError:
        return None


@mcp.tool()
def memory_search(query: str, sources: str = "", limit: int = 5) -> str:
    """Busca semântica na memória compartilhada do homelab.

    Retorna fatos de commits git, wiki pages, action journal e agentes.
    Use ANTES de agir para saber o que já foi feito e evitar duplicação de trabalho.

    sources: CSV de fontes para filtrar — "git,wiki,journal,alert,agent" (vazio = todas)
    limit:   máximo de resultados (default: 5)

    Exemplo: memory_search("trading agent restart", sources="journal,git", limit=3)
    """
    mem = _get_mem()
    if mem is None:
        return json.dumps({"error": "ChromaDB não disponível. Verifique CHROMA_DB_PATH."})
    try:
        src_list = [s.strip() for s in sources.split(",") if s.strip()] or None
        results  = mem.search(query, sources=src_list, limit=max(1, limit))
        return json.dumps({"results": results, "count": len(results)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def memory_store(fact: str, source: str = "agent", tags: str = "", ttl_days: int = 0) -> str:
    """Armazena um fato na memória compartilhada do homelab.

    Use para registrar descobertas importantes que outros agentes devem saber.
    Fatos repetidos com mesmo source+fact são deduplicados (upsert por hash).

    source:   categoria — "agent", "git", "wiki", "journal", "alert"
    tags:     CSV de tags — "trading,btc,critico"
    ttl_days: dias até expirar (0 = sem expiração)
    """
    mem = _get_mem()
    if mem is None:
        return json.dumps({"error": "ChromaDB não disponível. Verifique CHROMA_DB_PATH."})
    try:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        mem_id   = mem.store(
            fact,
            source=source,
            tags=tag_list,
            ttl_days=ttl_days,
        )
        return json.dumps({"ok": True, "memory_id": mem_id}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ═══════════════════════════  TRADING AGENT  ══════════════════════════════
#
# Ferramentas do BTC Trading Agent — leitura somente do schema btc.*
# DB connection: env TRADING_DATABASE_URL ou secrets agent eddie/database_url

_trading_db_url_cache: Optional[str] = None


def _get_trading_db_url() -> Optional[str]:
    """Resolve a connection string do trading DB sem hardcodar credenciais."""
    global _trading_db_url_cache
    if _trading_db_url_cache:
        return _trading_db_url_cache

    # 1. Variável de ambiente injetada pelo deploy/YAML
    url = TRADING_DATABASE_URL
    if url:
        _trading_db_url_cache = url
        return url

    # 2. Secrets agent — mesmo padrão do secrets_helper.py do trading agent
    for secret_name in ("eddie/database_url", "shared/database_url", "crypto/database_url"):
        result = _http_get(
            f"{SECRETS_AGENT_URL}/secrets/local/{secret_name}?field=url",
            headers=_secrets_headers(),
        )
        if result.get("ok"):
            val = (result.get("data") or {}).get("value", "")
            if val:
                _trading_db_url_cache = val
                return val

    logger.warning("⚠️ TRADING_DATABASE_URL não configurado e secret não encontrado")
    return None


def _btc_query(sql: str, params: tuple = ()) -> dict:
    """Executa SELECT read-only no schema btc.* do trading DB."""
    url = _get_trading_db_url()
    if not url:
        return {"ok": False, "error": "Trading DB não configurado (TRADING_DATABASE_URL ou eddie/database_url)."}
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(url)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params or None)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        cur.close()
        conn.close()
        serialized = [
            {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
             for k, v in dict(r).items()}
            for r in rows
        ]
        return {"ok": True, "rows": serialized, "count": len(serialized), "columns": cols}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool()
def trading_performance(symbol: str = "BTC-USDT", days: int = 7, profile: str = "") -> str:
    """Retorna estatísticas de performance do trading agent para o símbolo/período.

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        days:    Período em dias (default: 7).
        profile: Perfil do agente (default: todos).
    """
    import time
    cutoff = time.time() - days * 86400
    base_sql = """
        SELECT
            COUNT(*) AS total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
            COALESCE(SUM(pnl), 0) AS total_pnl,
            COALESCE(AVG(pnl), 0) AS avg_pnl,
            COALESCE(AVG(pnl_pct), 0) AS avg_pnl_pct,
            MAX(created_at) AS last_trade_at
        FROM btc.trades
        WHERE symbol = %s AND timestamp > %s AND dry_run = FALSE
    """
    params: list = [symbol, cutoff]
    if profile:
        base_sql += " AND profile = %s"
        params.append(profile)

    result = _btc_query(base_sql, tuple(params))
    if not result["ok"] or not result["rows"]:
        return json.dumps(result, ensure_ascii=False, indent=2)

    row = result["rows"][0]
    total = int(row.get("total_trades") or 0)
    wins  = int(row.get("winning_trades") or 0)
    win_rate = round(wins / total, 3) if total > 0 else 0.0
    return json.dumps({
        "ok": True,
        "symbol": symbol,
        "days": days,
        "profile": profile or "all",
        "total_trades": total,
        "winning_trades": wins,
        "win_rate": win_rate,
        "total_pnl": round(float(row.get("total_pnl") or 0), 4),
        "avg_pnl": round(float(row.get("avg_pnl") or 0), 4),
        "avg_pnl_pct": round(float(row.get("avg_pnl_pct") or 0), 4),
        "last_trade_at": str(row.get("last_trade_at") or ""),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_recent_trades(
    symbol: str = "BTC-USDT", limit: int = 10,
    profile: str = "", include_dry: bool = False,
) -> str:
    """Lista os trades mais recentes do trading agent.

    Args:
        symbol:      Par de trading (default: BTC-USDT).
        limit:       Número máximo de trades (default: 10).
        profile:     Perfil do agente (vazio = todos).
        include_dry: Incluir trades em dry_run (default: False).
    """
    sql = """
        SELECT id, side, price, size, funds, pnl, pnl_pct, dry_run,
               profile, servidor, status, created_at
        FROM btc.trades
        WHERE symbol = %s AND dry_run = %s
    """
    params: list = [symbol, include_dry]
    if profile:
        sql += " AND profile = %s"
        params.append(profile)
    sql += f" ORDER BY timestamp DESC LIMIT {max(1, min(limit, 100))}"

    result = _btc_query(sql, tuple(params))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_positions(symbol: str = "BTC-USDT", profile: str = "") -> str:
    """Retorna posições abertas (buys sem close correspondente) do trading agent.

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        profile: Perfil do agente (vazio = todos).
    """
    sql = """
        SELECT id, price, size, funds, profile, servidor, created_at,
               metadata
        FROM btc.trades
        WHERE symbol = %s AND side = 'buy' AND status != 'closed' AND dry_run = FALSE
    """
    params: list = [symbol]
    if profile:
        sql += " AND profile = %s"
        params.append(profile)
    sql += " ORDER BY timestamp DESC LIMIT 50"

    result = _btc_query(sql, tuple(params))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_market_state(symbol: str = "BTC-USDT", limit: int = 5) -> str:
    """Retorna os estados de mercado mais recentes registrados pelo trading agent.

    Inclui preço, RSI, momentum, volatilidade, orderbook e trade flow.

    Args:
        symbol: Par de trading (default: BTC-USDT).
        limit:  Número de registros (default: 5).
    """
    sql = f"""
        SELECT price, bid, ask, spread, orderbook_imbalance, trade_flow,
               rsi, momentum, volatility, trend, volume, created_at
        FROM btc.market_states
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT {max(1, min(limit, 50))}
    """
    result = _btc_query(sql, (symbol,))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_decisions(
    symbol: str = "BTC-USDT", limit: int = 10, profile: str = "",
) -> str:
    """Lista as decisões recentes do modelo de trading (comprar/vender/manter).

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        limit:   Número máximo de decisões (default: 10).
        profile: Perfil do agente (vazio = todos).
    """
    sql = """
        SELECT action, confidence, price, reason, executed, profile, servidor, created_at
        FROM btc.decisions
        WHERE symbol = %s
    """
    params: list = [symbol]
    if profile:
        sql += " AND profile = %s"
        params.append(profile)
    sql += f" ORDER BY timestamp DESC LIMIT {max(1, min(limit, 100))}"

    result = _btc_query(sql, tuple(params))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_candles(
    symbol: str = "BTC-USDT", ktype: str = "1min", limit: int = 60,
) -> str:
    """Retorna candles OHLCV armazenados pelo trading agent.

    Args:
        symbol: Par de trading (default: BTC-USDT).
        ktype:  Timeframe (default: 1min).
        limit:  Número de candles (default: 60).
    """
    sql = f"""
        SELECT timestamp, open, high, low, close, volume
        FROM btc.candles
        WHERE symbol = %s AND ktype = %s
        ORDER BY timestamp DESC
        LIMIT {max(1, min(limit, 1000))}
    """
    result = _btc_query(sql, (symbol, ktype))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_ai_controls(
    symbol: str = "BTC-USDT", profile: str = "default", limit: int = 3,
) -> str:
    """Retorna os últimos parâmetros de controle sugeridos pela IA para o trading.

    Inclui min_confidence, min_trade_interval, max_position_pct, max_positions.

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        profile: Perfil do agente (default: default).
        limit:   Número de registros (default: 3).
    """
    sql = f"""
        SELECT trigger, mode, model,
               suggested_min_confidence, suggested_min_trade_interval,
               suggested_max_position_pct, suggested_max_positions,
               applied_min_confidence, applied_min_trade_interval,
               applied_max_position_pct, applied_max_positions,
               rationale, created_at
        FROM btc.ai_trade_controls
        WHERE symbol = %s AND profile = %s
        ORDER BY timestamp DESC
        LIMIT {max(1, min(limit, 20))}
    """
    result = _btc_query(sql, (symbol, profile))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_ai_plan(
    symbol: str = "BTC-USDT", profile: str = "default", limit: int = 1,
) -> str:
    """Retorna o(s) último(s) plano(s) gerado(s) pela IA para o trading.

    O plano é uma análise textual em português com a estratégia atual do agente.

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        profile: Perfil do agente (default: default).
        limit:   Número de planos (default: 1).
    """
    sql = f"""
        SELECT plan_text, model, regime, price, profile, created_at
        FROM btc.ai_plans
        WHERE symbol = %s AND profile = %s
        ORDER BY timestamp DESC
        LIMIT {max(1, min(limit, 5))}
    """
    result = _btc_query(sql, (symbol, profile))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_ai_window(
    symbol: str = "BTC-USDT", profile: str = "default",
) -> str:
    """Retorna a janela operacional ativa calculada pela IA (entry_low/high, target_sell, TTL).

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        profile: Perfil do agente (default: default).
    """
    sql = """
        SELECT regime, reference_price, entry_low, entry_high, target_sell,
               min_confidence, min_trade_interval, ttl_seconds,
               to_timestamp(valid_until) AS valid_until,
               rationale, model, mode, created_at
        FROM btc.ai_trade_windows
        WHERE symbol = %s AND profile = %s
          AND valid_until > extract(epoch FROM now())
        ORDER BY timestamp DESC
        LIMIT 1
    """
    result = _btc_query(sql, (symbol, profile))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_news_sentiment(limit: int = 10, coin: str = "BTC") -> str:
    """Retorna notícias recentes com sentimento para BTC/GENERAL.

    Args:
        limit: Número máximo de notícias (default: 10).
        coin:  Moeda a filtrar (BTC, GENERAL ou vazio = todas).
    """
    sql = """
        SELECT source, title, sentiment, confidence, category, coin, created_at
        FROM btc.news_sentiment
        WHERE timestamp > NOW() - INTERVAL '24 hours'
          AND confidence >= 0.30
    """
    params: list = []
    if coin:
        sql += " AND coin = ANY(%s)"
        params.append([coin, "GENERAL"])
    sql += f" ORDER BY timestamp DESC LIMIT {max(1, min(limit, 50))}"

    result = _btc_query(sql, tuple(params))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_learning_stats(symbol: str = "BTC-USDT") -> str:
    """Retorna estatísticas de Q-learning do trading agent (rewards acumulados).

    Args:
        symbol: Par de trading (default: BTC-USDT).
    """
    sql = """
        SELECT
            COUNT(*) AS total_episodes,
            COALESCE(SUM(reward), 0) AS total_reward,
            COALESCE(AVG(reward), 0) AS avg_reward,
            COALESCE(MAX(reward), 0) AS max_reward,
            COALESCE(MIN(reward), 0) AS min_reward,
            SUM(CASE WHEN action = 0 THEN 1 ELSE 0 END) AS hold_count,
            SUM(CASE WHEN action = 1 THEN 1 ELSE 0 END) AS buy_count,
            SUM(CASE WHEN action = 2 THEN 1 ELSE 0 END) AS sell_count
        FROM btc.learning_rewards
        WHERE symbol = %s
    """
    result = _btc_query(sql, (symbol,))
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def trading_summary(symbol: str = "BTC-USDT", profile: str = "default") -> str:
    """Resumo completo do estado atual do trading agent — ideal para análise por LLM.

    Combina performance 7d, posições abertas, último estado de mercado,
    último plano IA e janela operacional ativa em uma única chamada.

    Args:
        symbol:  Par de trading (default: BTC-USDT).
        profile: Perfil do agente (default: default).
    """
    import json as _json

    perf   = _json.loads(trading_performance(symbol, 7, profile))
    market = _json.loads(trading_market_state(symbol, 1))
    plan   = _json.loads(trading_ai_plan(symbol, profile, 1))
    window = _json.loads(trading_ai_window(symbol, profile))
    pos    = _json.loads(trading_positions(symbol, profile))
    ctrl   = _json.loads(trading_ai_controls(symbol, profile, 1))

    return json.dumps({
        "symbol": symbol,
        "profile": profile,
        "performance_7d": perf,
        "open_positions": pos.get("rows", []),
        "latest_market_state": (market.get("rows") or [{}])[0],
        "latest_ai_plan": (plan.get("rows") or [{}])[0],
        "active_trade_window": (window.get("rows") or [{}])[0],
        "latest_ai_controls": (ctrl.get("rows") or [{}])[0],
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════  ENTRYPOINT  ═════════════════════════════════

if __name__ == "__main__":
    logger.info(f"Homelab MCP Server iniciando — Bus: {HOMELAB_URL} | Secrets: {SECRETS_AGENT_URL} | API: {API_BASE_URL}")
    logger.info(f"DB configurado: {'Sim' if DATABASE_URL else 'Não'}")
    mcp.run(transport="stdio")
