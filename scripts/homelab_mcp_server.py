#!/usr/bin/env python3
"""
Homelab MCP Server — Integra Cline com Communication Bus, Secrets Agent,
API Estou Aqui e PostgreSQL via Model Context Protocol (stdio).

Uso:
    python3 scripts/homelab_mcp_server.py

Configuração via variáveis de ambiente:
    HOMELAB_URL          - URL do Communication Bus (default: http://192.168.15.2:8503)
    SECRETS_AGENT_URL    - URL do Secrets Agent (default: http://192.168.15.2:8088)
    SECRETS_AGENT_API_KEY - Chave de API do Secrets Agent
    API_BASE_URL         - URL da API Estou Aqui (default: http://localhost:3000)
    DATABASE_URL         - Connection string PostgreSQL
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

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
API_BASE_URL = os.environ.get("API_BASE_URL", "http://192.168.15.2:3456")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

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
        "Fornece acesso ao Communication Bus (tarefas e heartbeat), "
        "Secrets Agent (credenciais), API Estou Aqui (eventos/check-ins/chat) "
        "e PostgreSQL (queries diretas)."
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


# ═══════════════════════════  ENTRYPOINT  ═════════════════════════════════

if __name__ == "__main__":
    logger.info(f"Homelab MCP Server iniciando — Bus: {HOMELAB_URL} | Secrets: {SECRETS_AGENT_URL} | API: {API_BASE_URL}")
    logger.info(f"DB configurado: {'Sim' if DATABASE_URL else 'Não'}")
    mcp.run(transport="stdio")
