"""Agente autônomo Nextcloud com planejamento via Ollama.

Fluxo de autonomia:
    1. Usuário envia texto em linguagem natural para POST /nextcloud/chat
    2. Ollama (GPU0) interpreta e gera um plano JSON estruturado
    3. O agente executa o(s) passo(s): WebDAV, OCS API ou docker-exec occ
    4. Resultado consolidado é retornado ao chamador

Operações suportadas:
    - files.list          — listar arquivos/pastas (WebDAV PROPFIND)
    - files.mkdir         — criar pasta (WebDAV MKCOL)
    - files.upload        — enviar arquivo (WebDAV PUT)
    - files.download      — baixar arquivo (WebDAV GET)
    - files.delete        — remover arquivo (WebDAV DELETE)
    - files.scan          — occ files:scan
    - share.create        — criar link de compartilhamento (OCS API)
    - share.list          — listar compartilhamentos (OCS API)
    - admin.status        — occ status
    - admin.user_list     — occ user:list
    - admin.user_info     — occ user:info
    - admin.brute_reset   — occ security:bruteforce:reset
    - admin.maintenance   — occ maintenance:mode --on/--off
    - admin.repair        — occ maintenance:repair
    - admin.app_list      — occ app:list
    - admin.logs          — últimas linhas do nextcloud.log
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────

_NC_URL = os.getenv("NEXTCLOUD_URL", "https://nextcloud.rpa4all.com").rstrip("/")
_NC_ADMIN = os.getenv("NEXTCLOUD_ADMIN_USER", "admin")
_NC_PASS = os.getenv("NEXTCLOUD_ADMIN_PASSWORD", "")
_NC_CONTAINER = os.getenv("NEXTCLOUD_CONTAINER", "nextcloud-rpa4all")

_OLLAMA_GPU0 = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
_OLLAMA_GPU1 = os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
_OLLAMA_SMALL = os.getenv("OLLAMA_SMALL_MODEL", "qwen3:0.6b")
_OLLAMA_TIMEOUT = int(os.getenv("NEXTCLOUD_OLLAMA_TIMEOUT", "60"))

# occ commands permitidos (allowlist de segurança)
_OCC_ALLOWLIST: frozenset[str] = frozenset({
    "status",
    "user:list",
    "user:info",
    "user:report",
    "user:disable",
    "user:enable",
    "user:resetpassword",
    "security:bruteforce:attempts",
    "security:bruteforce:reset",
    "maintenance:mode",
    "maintenance:repair",
    "maintenance:mimetype:update-db",
    "maintenance:update:htaccess",
    "files:scan",
    "files_external:list",
    "app:list",
    "app:enable",
    "app:disable",
    "app:update",
    "groupfolders:list",
    "groupfolders:create",
    "groupfolders:group",
    "group:list",
    "group:add",
    "group:adduser",
    "group:removeuser",
    "db:add-missing-indices",
    "log:watch",
    "update:check",
    "background:list",
    "trashbin:cleanup",
    "versions:cleanup",
})

# ─── Schemas ──────────────────────────────────────────────────────────────────

class NextcloudChatRequest(BaseModel):
    """Comando em linguagem natural para o agente autônomo."""
    message: str = Field(min_length=1, max_length=2000)
    username: str = Field(default=_NC_ADMIN, max_length=200)
    dry_run: bool = Field(default=False)


class NextcloudChatResponse(BaseModel):
    ok: bool
    action: str
    result: Any
    reasoning: str
    gpu_used: str
    model_used: str


class NextcloudOccRequest(BaseModel):
    """Execução direta de comando occ (restrições aplicadas)."""
    args: list[str] = Field(min_length=1, max_length=20)


class NextcloudFilesListRequest(BaseModel):
    username: str = Field(max_length=200)
    path: str = Field(default="/", max_length=1000)
    depth: int = Field(default=1, ge=0, le=3)


class NextcloudShareCreateRequest(BaseModel):
    username: str = Field(max_length=200)
    path: str = Field(min_length=1, max_length=1000)
    share_type: int = Field(default=3, description="3=link público, 0=usuário, 1=grupo")
    permissions: int = Field(default=1, description="1=read, 17=read+share")
    password: str | None = Field(default=None, max_length=200)
    expire_date: str | None = Field(default=None, description="YYYY-MM-DD")


# ─── Cliente auxiliares ───────────────────────────────────────────────────────

def _webdav_url(username: str, path: str) -> str:
    """Monta URL WebDAV para o usuário e caminho dados."""
    clean = path.lstrip("/")
    return f"{_NC_URL}/remote.php/dav/files/{username}/{clean}"


def _ocs_url(endpoint: str) -> str:
    return f"{_NC_URL}/ocs/v2.php/{endpoint}"


async def _ollama_chat(
    system: str,
    user: str,
    *,
    gpu: str = "gpu0",
    timeout: int = _OLLAMA_TIMEOUT,
) -> tuple[str, str, str]:
    """Chama /api/chat no Ollama e retorna (texto, host, modelo)."""
    host = _OLLAMA_GPU0 if gpu == "gpu0" else _OLLAMA_GPU1
    model = _OLLAMA_MODEL if gpu == "gpu0" else _OLLAMA_SMALL
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    tc = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=tc) as session:
        async with session.post(f"{host}/api/chat", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
    text: str = data.get("message", {}).get("content", "").strip()
    return text, host, model


async def _ollama_plan(message: str) -> dict[str, Any]:
    """Interpreta comando em linguagem natural e retorna plano JSON via Ollama.

    Plano esperado:
        {
          "action": "<category.operation>",
          "params": { ... },
          "reasoning": "<1 frase>"
        }
    """
    system = (
        "Você é o planejador do agente Nextcloud RPA4All. "
        "Interprete o comando do usuário e retorne APENAS um JSON válido com:\n"
        '  "action": uma das ações abaixo\n'
        '  "params": parâmetros específicos da ação\n'
        '  "reasoning": uma frase explicando a ação escolhida\n\n'
        "Ações disponíveis:\n"
        "  files.list      {username, path}\n"
        "  files.mkdir     {username, path}\n"
        "  files.delete    {username, path}\n"
        "  files.scan      {username}\n"
        "  share.create    {username, path, share_type}\n"
        "  share.list      {username, path}\n"
        "  admin.status    {}\n"
        "  admin.user_list {}\n"
        "  admin.user_info {username}\n"
        "  admin.logs      {lines}\n"
        "  admin.maintenance {mode}  — mode: on ou off\n"
        "  admin.repair    {}\n"
        "  admin.app_list  {}\n"
        "  admin.brute_reset {ip}\n\n"
        "Retorne apenas JSON, sem markdown."
    )
    raw, host, model = await _ollama_chat(system, message, gpu="gpu0")
    # extrair JSON mesmo que venha com cerca de markdown
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        plan: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Ollama retornou JSON inválido: %s", raw[:200])
        plan = {
            "action": "admin.status",
            "params": {},
            "reasoning": "Fallback para status — JSON inválido recebido do Ollama",
        }
    plan.setdefault("gpu_used", host)
    plan.setdefault("model_used", model)
    return plan


async def _run_occ(*args: str) -> tuple[int, str, str]:
    """Executa `docker exec -u www-data <container> php occ <args>` e retorna (rc, stdout, stderr)."""
    cmd = ["docker", "exec", "-u", "www-data", _NC_CONTAINER, "php", "occ", *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_b.decode("utf-8", errors="replace").strip(),
        stderr_b.decode("utf-8", errors="replace").strip(),
    )


def _occ_cmd_allowed(args: list[str]) -> bool:
    """Verifica se o comando occ está na allowlist."""
    if not args:
        return False
    base = args[0]
    return base in _OCC_ALLOWLIST


async def _webdav_propfind(username: str, path: str, depth: int = 1) -> list[dict[str, str]]:
    """PROPFIND no WebDAV e retorna lista de {href, displayname, type, size, modified}."""
    url = _webdav_url(username, path)
    body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:displayname/><d:getcontentlength/><d:getlastmodified/><d:resourcetype/></d:prop></d:propfind>'
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    headers = {"Depth": str(depth), "Content-Type": "application/xml"}
    tc = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.request("PROPFIND", url, data=body, headers=headers) as resp:
            if resp.status not in (207, 200):
                raise HTTPException(
                    status_code=resp.status,
                    detail=f"WebDAV PROPFIND falhou: HTTP {resp.status}",
                )
            xml_body = await resp.text()

    ns = {"d": "DAV:"}
    root = ET.fromstring(xml_body)
    items: list[dict[str, str]] = []
    for response in root.findall("d:response", ns):
        href_el = response.find("d:href", ns)
        href = href_el.text or "" if href_el is not None else ""
        prop = response.find(".//d:prop", ns)
        if prop is None:
            continue
        display_el = prop.find("d:displayname", ns)
        size_el = prop.find("d:getcontentlength", ns)
        mod_el = prop.find("d:getlastmodified", ns)
        rt_el = prop.find("d:resourcetype", ns)
        is_dir = rt_el is not None and rt_el.find("d:collection", ns) is not None
        items.append({
            "href": href,
            "name": display_el.text or href.split("/")[-1] if display_el is not None else href.split("/")[-1],
            "type": "directory" if is_dir else "file",
            "size": size_el.text or "0" if size_el is not None else "0",
            "modified": mod_el.text or "" if mod_el is not None else "",
        })
    return items


async def _webdav_mkdir(username: str, path: str) -> int:
    url = _webdav_url(username, path)
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    tc = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.request("MKCOL", url) as resp:
            return resp.status


async def _webdav_delete(username: str, path: str) -> int:
    url = _webdav_url(username, path)
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    tc = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.delete(url) as resp:
            return resp.status


async def _ocs_share_create(
    username: str,
    path: str,
    share_type: int = 3,
    permissions: int = 1,
    password: str | None = None,
    expire_date: str | None = None,
) -> dict[str, Any]:
    url = _ocs_url("apps/files_sharing/api/v1/shares")
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    headers = {"OCS-APIREQUEST": "true"}
    data: dict[str, Any] = {
        "path": path,
        "shareType": share_type,
        "permissions": permissions,
    }
    if password:
        data["password"] = password
    if expire_date:
        data["expireDate"] = expire_date
    tc = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.post(url, data=data, headers=headers) as resp:
            body = await resp.json(content_type=None)
    return body


async def _ocs_share_list(username: str, path: str) -> dict[str, Any]:
    url = _ocs_url(f"apps/files_sharing/api/v1/shares?path={path}&reshares=true")
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    headers = {"OCS-APIREQUEST": "true"}
    tc = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json(content_type=None)


async def _read_nc_logs(lines: int = 50) -> str:
    """Lê as últimas N linhas do nextcloud.log via docker exec."""
    cmd = [
        "docker", "exec", _NC_CONTAINER,
        "tail", f"-n{lines}", "/var/www/html/data/nextcloud.log",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return out.decode("utf-8", errors="replace").strip() or err.decode("utf-8", errors="replace").strip()


# ─── Dispatcher de ações ──────────────────────────────────────────────────────

async def _dispatch(action: str, params: dict[str, Any], dry_run: bool) -> Any:
    """Despacha uma ação planejada para o executor correto."""
    username = params.get("username", _NC_ADMIN)

    if action == "files.list":
        return await _webdav_propfind(
            username,
            params.get("path", "/"),
            int(params.get("depth", 1)),
        )

    if action == "files.mkdir":
        if dry_run:
            return {"dry_run": True, "url": _webdav_url(username, params.get("path", ""))}
        status = await _webdav_mkdir(username, params.get("path", ""))
        return {"status": status, "created": status in (201, 405)}

    if action == "files.delete":
        if dry_run:
            return {"dry_run": True, "url": _webdav_url(username, params.get("path", ""))}
        status = await _webdav_delete(username, params.get("path", ""))
        return {"status": status, "deleted": status == 204}

    if action == "files.scan":
        if dry_run:
            return {"dry_run": True, "command": ["files:scan", username]}
        rc, out, err = await _run_occ("files:scan", username)
        return {"rc": rc, "output": out or err}

    if action == "share.create":
        if dry_run:
            return {"dry_run": True, "path": params.get("path")}
        return await _ocs_share_create(
            username,
            params.get("path", "/"),
            int(params.get("share_type", 3)),
            int(params.get("permissions", 1)),
            params.get("password"),
            params.get("expire_date"),
        )

    if action == "share.list":
        return await _ocs_share_list(username, params.get("path", "/"))

    if action == "admin.status":
        rc, out, err = await _run_occ("status")
        return {"rc": rc, "output": out or err}

    if action == "admin.user_list":
        rc, out, err = await _run_occ("user:list", "--output=json")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"rc": rc, "raw": out or err}

    if action == "admin.user_info":
        user = params.get("username", "")
        if not user:
            return {"error": "username obrigatório"}
        rc, out, err = await _run_occ("user:info", user, "--output=json")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"rc": rc, "raw": out or err}

    if action == "admin.brute_reset":
        ip = params.get("ip", "")
        if not ip:
            return {"error": "ip obrigatório"}
        if dry_run:
            return {"dry_run": True, "ip": ip}
        rc, out, err = await _run_occ("security:bruteforce:reset", ip)
        return {"rc": rc, "output": out or err}

    if action == "admin.maintenance":
        mode = params.get("mode", "off")
        if mode not in ("on", "off"):
            return {"error": "mode deve ser 'on' ou 'off'"}
        if dry_run:
            return {"dry_run": True, "mode": mode}
        rc, out, err = await _run_occ("maintenance:mode", f"--{mode}")
        return {"rc": rc, "output": out or err}

    if action == "admin.repair":
        if dry_run:
            return {"dry_run": True}
        rc, out, err = await _run_occ("maintenance:repair")
        return {"rc": rc, "output": out or err}

    if action == "admin.app_list":
        rc, out, err = await _run_occ("app:list", "--output=json")
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"rc": rc, "raw": out or err}

    if action == "admin.logs":
        lines = int(params.get("lines", 50))
        return {"log": await _read_nc_logs(lines)}

    return {"error": f"Ação desconhecida: {action}"}


# ─── Agente principal ─────────────────────────────────────────────────────────

class NextcloudAgent:
    """Agente autônomo Nextcloud com planejamento via Ollama."""

    async def chat(self, req: NextcloudChatRequest) -> NextcloudChatResponse:
        """Interpreta linguagem natural, planeja e executa via Ollama."""
        try:
            plan = await _ollama_plan(req.message)
        except Exception as exc:
            logger.error("Ollama falhou no planejamento: %s", exc)
            plan = {
                "action": "admin.status",
                "params": {},
                "reasoning": f"Fallback para status — Ollama indisponível: {exc}",
                "gpu_used": _OLLAMA_GPU0,
                "model_used": _OLLAMA_MODEL,
            }

        action: str = plan.get("action", "admin.status")
        params: dict[str, Any] = plan.get("params", {})
        reasoning: str = plan.get("reasoning", "")
        gpu_used: str = plan.get("gpu_used", _OLLAMA_GPU0)
        model_used: str = plan.get("model_used", _OLLAMA_MODEL)

        if req.username != _NC_ADMIN and "username" not in params:
            params["username"] = req.username

        logger.info("Nextcloud chat: action=%s params=%s dry_run=%s", action, params, req.dry_run)

        try:
            result = await _dispatch(action, params, req.dry_run)
            ok = True
        except Exception as exc:
            logger.error("Dispatch falhou [%s]: %s", action, exc)
            result = {"error": str(exc)}
            ok = False

        return NextcloudChatResponse(
            ok=ok,
            action=action,
            result=result,
            reasoning=reasoning,
            gpu_used=gpu_used,
            model_used=model_used,
        )

    async def run_occ(self, req: NextcloudOccRequest) -> dict[str, Any]:
        """Executa occ com verificação de allowlist."""
        if not _occ_cmd_allowed(req.args):
            raise HTTPException(
                status_code=403,
                detail=f"Comando occ não permitido: {req.args[0]}. Allowlist: {sorted(_OCC_ALLOWLIST)}",
            )
        rc, out, err = await _run_occ(*req.args)
        output = out or err
        try:
            return {"rc": rc, "result": json.loads(output)}
        except json.JSONDecodeError:
            return {"rc": rc, "result": output}

    async def health(self) -> dict[str, Any]:
        """Verifica disponibilidade do Nextcloud e das GPUs Ollama."""
        results: dict[str, Any] = {}

        # Nextcloud
        try:
            tc = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=tc) as session:
                async with session.get(f"{_NC_URL}/status.php") as resp:
                    results["nextcloud"] = {
                        "reachable": resp.status == 200,
                        "status_code": resp.status,
                        "url": _NC_URL,
                    }
        except Exception as exc:
            results["nextcloud"] = {"reachable": False, "error": str(exc)}

        # Ollama GPU0
        for label, host in [("ollama_gpu0", _OLLAMA_GPU0), ("ollama_gpu1", _OLLAMA_GPU1)]:
            try:
                tc = aiohttp.ClientTimeout(total=4)
                async with aiohttp.ClientSession(timeout=tc) as session:
                    async with session.get(f"{host}/api/tags") as resp:
                        data = await resp.json()
                        results[label] = {
                            "reachable": resp.status == 200,
                            "models": [m.get("name") for m in data.get("models", [])],
                        }
            except Exception as exc:
                results[label] = {"reachable": False, "error": str(exc)}

        # occ status (rápido)
        try:
            rc, out, _ = await asyncio.wait_for(_run_occ("status"), timeout=5)
            results["occ"] = {"reachable": rc == 0, "output": out[:200]}
        except Exception as exc:
            results["occ"] = {"reachable": False, "error": str(exc)}

        overall = all(
            results.get(k, {}).get("reachable", False)
            for k in ("nextcloud", "ollama_gpu0", "occ")
        )
        return {"ok": overall, "components": results}


# ─── Singleton ────────────────────────────────────────────────────────────────

_agent: NextcloudAgent | None = None


def get_nextcloud_agent() -> NextcloudAgent:
    global _agent
    if _agent is None:
        _agent = NextcloudAgent()
    return _agent


# ─── Router FastAPI ───────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/health")
async def nextcloud_health() -> dict[str, Any]:
    """Verifica disponibilidade do Nextcloud, Ollama GPU0/GPU1 e occ."""
    return await get_nextcloud_agent().health()


@router.post("/chat", response_model=NextcloudChatResponse)
async def nextcloud_chat(req: NextcloudChatRequest) -> NextcloudChatResponse:
    """Interface em linguagem natural: Ollama planeja e executa ação no Nextcloud.

    Exemplos de mensagem:
    - "liste os arquivos da pasta /Documents do usuário edenilson"
    - "crie a pasta /Projetos/2026 para o usuário admin"
    - "mostre o status do sistema"
    - "quantos usuários existem no sistema?"
    - "coloque em modo manutenção"
    - "mostre as últimas 20 linhas de log"
    """
    return await get_nextcloud_agent().chat(req)


@router.post("/occ")
async def nextcloud_occ(req: NextcloudOccRequest) -> dict[str, Any]:
    """Executa comando occ com restrição de allowlist.

    Exemplo: {"args": ["status"]}
    """
    return await get_nextcloud_agent().run_occ(req)


@router.get("/files/list")
async def nextcloud_files_list(username: str, path: str = "/", depth: int = 1) -> list[dict[str, str]]:
    """Lista arquivos e pastas via WebDAV PROPFIND."""
    return await _webdav_propfind(username, path, depth)


@router.post("/files/mkdir")
async def nextcloud_files_mkdir(req: NextcloudFilesListRequest) -> dict[str, Any]:
    """Cria pasta via WebDAV MKCOL."""
    status = await _webdav_mkdir(req.username, req.path)
    return {"status": status, "created": status in (201, 405)}


@router.post("/share/create")
async def nextcloud_share_create(req: NextcloudShareCreateRequest) -> dict[str, Any]:
    """Cria link de compartilhamento via OCS API."""
    return await _ocs_share_create(
        req.username,
        req.path,
        req.share_type,
        req.permissions,
        req.password,
        req.expire_date,
    )


@router.get("/share/list")
async def nextcloud_share_list(username: str, path: str = "/") -> dict[str, Any]:
    """Lista compartilhamentos de um caminho via OCS API."""
    return await _ocs_share_list(username, path)


@router.get("/admin/status")
async def nextcloud_admin_status() -> dict[str, Any]:
    """Retorna output de `occ status`."""
    rc, out, err = await _run_occ("status")
    return {"rc": rc, "output": out or err}


@router.get("/admin/users")
async def nextcloud_admin_users() -> dict[str, Any]:
    """Retorna lista de usuários via `occ user:list --output=json`."""
    rc, out, err = await _run_occ("user:list", "--output=json")
    try:
        return {"rc": rc, "users": json.loads(out)}
    except json.JSONDecodeError:
        return {"rc": rc, "raw": out or err}


@router.get("/admin/logs")
async def nextcloud_admin_logs(lines: int = 50) -> dict[str, str]:
    """Retorna as últimas N linhas do nextcloud.log."""
    return {"log": await _read_nc_logs(min(lines, 500))}
