"""Agente autônomo Nextcloud com planejamento via Ollama.

Fluxo de autonomia:
    1. Usuário envia texto em linguagem natural para POST /nextcloud/chat
    2. Ollama (GPU0) interpreta e gera um plano JSON estruturado
    3. O agente executa o(s) passo(s): WebDAV, OCS API ou docker-exec occ
    4. Resultado consolidado é retornado ao chamador

Operações suportadas:
    - files.list          — listar arquivos/pastas (WebDAV PROPFIND)
    - files.mkdir         — criar pasta (WebDAV MKCOL)
    - files.upload        — enviar arquivo (WebDAV PUT, sem limite de tamanho via URL interna)
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
    - vpn.provision       — provisiona peer WireGuard para novo usuário (gera keypair + registra)
    - vpn.config          — retorna config WireGuard de cliente com escopo Nextcloud
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import unquote, urlparse

import aiohttp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── Configuração ─────────────────────────────────────────────────────────────

_NC_URL = os.getenv("NEXTCLOUD_URL", "https://nextcloud.rpa4all.com").rstrip("/")
# URL interna: agente roda no homelab → acessa Nextcloud direto via nginx local,
# bypassando Cloudflare e eliminando timeouts 502/524 para arquivos grandes.
_NC_INTERNAL_URL = os.getenv("NEXTCLOUD_INTERNAL_URL", "http://127.0.0.1:8880").rstrip("/")
_NC_ADMIN = os.getenv("NEXTCLOUD_ADMIN_USER", "admin")
_NC_PASS = os.getenv("NEXTCLOUD_ADMIN_PASSWORD", "")
_NC_CONTAINER = os.getenv("NEXTCLOUD_CONTAINER", "nextcloud-app")
_NC_CONTAINER_CANDIDATES = tuple(
    dict.fromkeys(
        filter(
            None,
            [
                _NC_CONTAINER,
                *(
                    item.strip()
                    for item in os.getenv(
                        "NEXTCLOUD_CONTAINER_CANDIDATES",
                        "nextcloud-app,nextcloud-rpa4all",
                    ).split(",")
                ),
            ],
        )
    )
)
_NC_RESOLVED_CONTAINER: str | None = None

_OLLAMA_GPU0 = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
_OLLAMA_GPU1 = os.getenv("OLLAMA_HOST_GPU1", "http://192.168.15.2:11435")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
_OLLAMA_SMALL = os.getenv("OLLAMA_SMALL_MODEL", "gemma3:1b")
_OLLAMA_TIMEOUT = int(os.getenv("NEXTCLOUD_OLLAMA_TIMEOUT", "60"))

# Mantem limite defensivo no endpoint do agente para evitar payloads enormes em JSON/base64.
_MAX_UPLOAD_BYTES = 35 * 1024 * 1024
_TRANSFER_TIMEOUT = 3600              # 1 hora — permite arquivos de vários GB
_UPLOAD_RETRIES = 3
_UPLOAD_RETRY_SLEEP = 10

_LTO_EXTERNAL_DEST = "/var/www/html/external/LTO"
_LTO_STAGING_BIND = "/mnt/lto6-nc"
_LTO_UNSAFE_SOURCES: tuple[str, ...] = (
    "/mnt/tape/lto6",
    "/run/ltfs-export/lto6",
    "/srv/nextcloud/external/LTO",
    "/home/homelab/nextcloud/external_local/LTO",
)

# WireGuard: config servidor para provisionamento de peers Nextcloud
_WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
_WG_CONF = os.getenv("WG_CONF_PATH", "/etc/wireguard/wg0.conf")
_WG_SERVER_PUBKEY = os.getenv("WG_SERVER_PUBKEY", "RJTM75HsZRGG2Jcr2ylA/wC1rcT1QE4POOB/hw3PIWA=")
_WG_SERVER_ENDPOINT = os.getenv("WG_SERVER_ENDPOINT", "185.239.149.54:51824")
# IP alocado para clientes Nextcloud: 10.66.66.100–10.66.66.200
_WG_PEER_RANGE_START = int(os.getenv("WG_PEER_RANGE_START", "100"))
_WG_PEER_RANGE_END = int(os.getenv("WG_PEER_RANGE_END", "200"))

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


class NextcloudFilesListResponse(BaseModel):
    items: list[dict[str, str]]
    total_items: int


class NextcloudFileUploadRequest(BaseModel):
    username: str = Field(max_length=200)
    path: str = Field(min_length=1, max_length=1000)
    content_b64: str = Field(description="Conteúdo do arquivo codificado em base64")
    content_type: str = Field(default="application/octet-stream", max_length=200)


class NextcloudShareCreateRequest(BaseModel):
    username: str = Field(max_length=200)
    path: str = Field(min_length=1, max_length=1000)
    share_type: int = Field(default=3, description="3=link público, 0=usuário, 1=grupo")
    permissions: int = Field(default=1, description="1=read, 17=read+share")
    password: str | None = Field(default=None, max_length=200)
    expire_date: str | None = Field(default=None, description="YYYY-MM-DD")


# ─── Cliente auxiliares ───────────────────────────────────────────────────────

def _webdav_url(username: str, path: str) -> str:
    """Monta URL WebDAV usando URL interna (bypass Cloudflare, sem timeout)."""
    clean = path.lstrip("/")
    return f"{_NC_INTERNAL_URL}/remote.php/dav/files/{username}/{clean}"


def _ocs_url(endpoint: str) -> str:
    return f"{_NC_INTERNAL_URL}/ocs/v2.php/{endpoint}"


def _normalize_webdav_path(value: str) -> str:
    """Normaliza caminho/href WebDAV para comparação estável."""
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme else value
    decoded = unquote(path).rstrip("/")
    return decoded or "/"


def _is_same_webdav_resource(request_url: str, href: str) -> bool:
    """Indica se o href do PROPFIND representa o próprio recurso consultado."""
    return _normalize_webdav_path(request_url) == _normalize_webdav_path(href)


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
        "  files.upload    {username, path, content_b64}\n"
        "  files.download  {username, path}\n"
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
        "  admin.storage_diagnostics {}\n"
        "  admin.brute_reset {ip}\n"
        "  vpn.provision   {username, comment}  — gera keypair WireGuard e registra peer\n"
        "  vpn.config      {peer_ip, privkey}   — retorna config cliente WireGuard\n\n"
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


async def _run_command(*cmd: str) -> tuple[int, str, str]:
    """Executa um comando e retorna (rc, stdout, stderr)."""
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


def _container_not_found(stderr: str, stdout: str = "") -> bool:
    """Identifica erro de container Docker inexistente."""
    text = f"{stderr}\n{stdout}".lower()
    return "no such container" in text or "not found" in text


async def _resolve_nc_container(force_refresh: bool = False) -> str:
    """Resolve nome real do container Nextcloud com fallback para aliases conhecidos."""
    global _NC_RESOLVED_CONTAINER

    if _NC_RESOLVED_CONTAINER and not force_refresh:
        return _NC_RESOLVED_CONTAINER

    last_error = "container não encontrado"
    for candidate in _NC_CONTAINER_CANDIDATES:
        rc, out, err = await _run_command("docker", "inspect", candidate, "--format", "{{.Name}}")
        if rc == 0:
            _NC_RESOLVED_CONTAINER = candidate
            return candidate
        last_error = err or out or last_error

    raise RuntimeError(
        f"Nenhum container Nextcloud disponível entre {_NC_CONTAINER_CANDIDATES}. Último erro: {last_error}"
    )


async def _run_occ(*args: str) -> tuple[int, str, str]:
    """Executa `docker exec -u www-data <container> php occ <args>` e retorna (rc, stdout, stderr)."""
    container = await _resolve_nc_container()
    rc, out, err = await _run_command("docker", "exec", "-u", "www-data", container, "php", "occ", *args)
    if rc != 0 and _container_not_found(err, out):
        container = await _resolve_nc_container(force_refresh=True)
        rc, out, err = await _run_command("docker", "exec", "-u", "www-data", container, "php", "occ", *args)
    return rc, out, err


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
        if _is_same_webdav_resource(url, href):
            # O primeiro item do PROPFIND depth=1 costuma ser o próprio diretório consultado.
            continue
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


async def _webdav_upload(
    username: str,
    path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> int:
    """PUT WebDAV via URL interna — sem limite de tamanho, timeout 1h, 3 tentativas."""
    if _MAX_UPLOAD_BYTES > 0 and len(data) > _MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Arquivo excede limite de {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB: {len(data)} bytes"
        )
    url = _webdav_url(username, path)
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    tc = aiohttp.ClientTimeout(total=_TRANSFER_TIMEOUT)
    last_status = 0
    for attempt in range(1, _UPLOAD_RETRIES + 1):
        try:
            async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
                async with session.put(url, data=data, headers={"Content-Type": content_type}) as resp:
                    last_status = resp.status
                    if resp.status in (200, 201, 204):
                        return resp.status
                    logger.warning("Upload tentativa %d/%d: HTTP %d", attempt, _UPLOAD_RETRIES, resp.status)
        except Exception as exc:
            logger.warning("Upload tentativa %d/%d erro: %s", attempt, _UPLOAD_RETRIES, exc)
        if attempt < _UPLOAD_RETRIES:
            await asyncio.sleep(_UPLOAD_RETRY_SLEEP)
    return last_status


async def _webdav_download(username: str, path: str) -> bytes:
    """GET WebDAV — timeout 120s, retorna bytes do arquivo."""
    url = _webdav_url(username, path)
    auth = aiohttp.BasicAuth(_NC_ADMIN, _NC_PASS)
    tc = aiohttp.ClientTimeout(total=_TRANSFER_TIMEOUT)
    async with aiohttp.ClientSession(auth=auth, timeout=tc) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=resp.status,
                    detail=f"WebDAV GET falhou: HTTP {resp.status}",
                )
            return await resp.read()


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


async def _wg_keygen() -> tuple[str, str]:
    """Gera par de chaves WireGuard (privada, pública) via subprocess."""
    p1 = await asyncio.create_subprocess_exec(
        "wg", "genkey",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    priv_b, _ = await p1.communicate()
    privkey = priv_b.decode().strip()

    p2 = await asyncio.create_subprocess_exec(
        "wg", "pubkey",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    pub_b, _ = await p2.communicate(input=privkey.encode() + b"\n")
    pubkey = pub_b.decode().strip()
    return privkey, pubkey


def _wg_next_ip() -> str:
    """Lê peers ativos via 'wg show wg0 allowed-ips' e retorna próximo IP disponível."""
    import subprocess
    result = subprocess.run(
        ["sudo", "wg", "show", _WG_INTERFACE, "allowed-ips"],
        capture_output=True, text=True, timeout=5,
    )
    used: set[int] = set()
    for line in result.stdout.splitlines():
        for m in re.finditer(r"10\.66\.66\.(\d+)/32", line):
            used.add(int(m.group(1)))
    for i in range(_WG_PEER_RANGE_START, _WG_PEER_RANGE_END + 1):
        if i not in used:
            return f"10.66.66.{i}"
    raise RuntimeError(f"Sem IPs disponíveis em 10.66.66.{_WG_PEER_RANGE_START}-{_WG_PEER_RANGE_END}")


async def _wg_register_peer(pubkey: str, peer_ip: str, comment: str = "") -> None:
    """Registra peer no WireGuard em tempo real e persiste no wg0.conf."""
    # Ativa peer na interface em execução
    proc = await asyncio.create_subprocess_exec(
        "sudo", "wg", "set", _WG_INTERFACE,
        "peer", pubkey, "allowed-ips", f"{peer_ip}/32",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"wg set falhou: {err.decode().strip()}")

    # Persiste no wg0.conf
    block = f"\n[Peer]\n# {comment}\nPublicKey = {pubkey}\nAllowedIPs = {peer_ip}/32\n"
    append_proc = await asyncio.create_subprocess_exec(
        "sudo", "tee", "-a", _WG_CONF,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, err2 = await append_proc.communicate(input=block.encode())
    if append_proc.returncode != 0:
        raise RuntimeError(f"Falha ao persistir wg0.conf: {err2.decode().strip()}")


def _wg_client_config(privkey: str, peer_ip: str) -> str:
    """Gera config WireGuard para cliente, sem PersistentKeepalive (watchdog gerencia ciclo de vida)."""
    return (
        f"[Interface]\n"
        f"PrivateKey = {privkey}\n"
        f"Address = {peer_ip}/32\n\n"
        f"[Peer]\n"
        f"PublicKey = {_WG_SERVER_PUBKEY}\n"
        f"Endpoint = {_WG_SERVER_ENDPOINT}\n"
        f"# Escopo: só tráfego ao Nextcloud passa pelo túnel\n"
        f"AllowedIPs = 192.168.15.2/32\n"
        f"# Sem PersistentKeepalive — watchdog desliga em idle e reconecta sob demanda\n"
    )


def _wg_watchdog_script(interface: str = "homelab-nc", idle_timeout: int = 300) -> str:
    """Gera script que desliga VPN após idle e reconecta ao detectar o sync client ativo."""
    return f"""\
#!/bin/bash
# nextcloud-vpn-watchdog — gerencia {interface}: up ao detectar sync, down após {idle_timeout}s idle
set -euo pipefail

IFACE="{interface}"
IDLE_TIMEOUT={idle_timeout}
CHECK_INTERVAL=30
SYNC_PROCESS="rpa4all-files"

last_rx=0; last_tx=0
last_active=$(date +%s)

vpn_is_up() {{ ip link show "$IFACE" &>/dev/null; }}

get_transfer() {{
    sudo wg show "$IFACE" transfer 2>/dev/null \\
      | awk '{{rx+=$1; tx+=$2}} END {{print rx" "tx}}' || echo "0 0"
}}

log() {{ logger -t nextcloud-vpn "$*" && echo "$(date '+%F %T') $*"; }}

while true; do
    sleep "$CHECK_INTERVAL"

    sync_running=0
    pgrep -x "$SYNC_PROCESS" &>/dev/null && sync_running=1

    if ! vpn_is_up; then
        if [ "$sync_running" -eq 1 ]; then
            log "Sync detectado — ativando $IFACE"
            sudo wg-quick up "$IFACE" && last_active=$(date +%s) || true
        fi
        continue
    fi

    # VPN ativa: checar tráfego
    read -r cur_rx cur_tx <<< "$(get_transfer)"
    if [ "$cur_rx" != "$last_rx" ] || [ "$cur_tx" != "$last_tx" ]; then
        last_rx=$cur_rx; last_tx=$cur_tx
        last_active=$(date +%s)
    else
        idle=$(( $(date +%s) - last_active ))
        if [ "$idle" -ge "$IDLE_TIMEOUT" ]; then
            log "Idle ${{idle}}s — desligando $IFACE"
            sudo wg-quick down "$IFACE" || true
        fi
    fi
done
"""


def _wg_watchdog_service(interface: str = "homelab-nc") -> str:
    """Gera unit systemd do watchdog VPN no cliente."""
    return f"""\
[Unit]
Description=Nextcloud VPN Watchdog ({interface}) — auto up/down por idle
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/nextcloud-vpn-watchdog.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def _wg_watchdog_sudoers(interface: str = "homelab-nc") -> str:
    """Regra sudoers mínima para o watchdog no cliente."""
    return (
        f"# Nextcloud VPN watchdog — permite wg e wg-quick sem senha\n"
        f"$USER ALL=(root) NOPASSWD: /usr/bin/wg show {interface} transfer, "
        f"/usr/bin/wg-quick up {interface}, /usr/bin/wg-quick down {interface}\n"
    )


def _wg_install_script(
    privkey: str,
    peer_ip: str,
    interface: str = "homelab-nc",
    idle_timeout: int = 300,
) -> str:
    """Gera script instalador completo: executa com 'sudo bash' no cliente.

    O script detecta o usuário real (SUDO_USER), escreve todos os arquivos,
    configura sudoers, registra e inicia o watchdog systemd em uma única execução.
    """
    wg_conf = _wg_client_config(privkey, peer_ip)
    watchdog = _wg_watchdog_script(interface, idle_timeout)
    service = _wg_watchdog_service(interface)

    return f"""\
#!/bin/bash
# nextcloud-vpn-install — instalação automática VPN Nextcloud + watchdog idle
# Uso: sudo bash nextcloud-vpn-install.sh
set -euo pipefail

IFACE="{interface}"
REAL_USER="${{SUDO_USER:-$USER}}"

echo "==> Instalando VPN Nextcloud para usuário: $REAL_USER"

# 1. Dependências
if ! command -v wg-quick &>/dev/null; then
    echo "==> Instalando wireguard-tools..."
    apt-get install -y wireguard-tools
fi

# 2. Config WireGuard
install -m 600 /dev/null /etc/wireguard/$IFACE.conf
cat > /etc/wireguard/$IFACE.conf << 'WG_EOF'
{wg_conf}
WG_EOF
echo "==> /etc/wireguard/$IFACE.conf criado"

# 3. Watchdog script
cat > /usr/local/bin/nextcloud-vpn-watchdog.sh << 'WATCHDOG_EOF'
{watchdog}
WATCHDOG_EOF
chmod +x /usr/local/bin/nextcloud-vpn-watchdog.sh
echo "==> /usr/local/bin/nextcloud-vpn-watchdog.sh criado"

# 4. Systemd service
cat > /etc/systemd/system/nextcloud-vpn-watchdog.service << 'SVC_EOF'
{service}
SVC_EOF
echo "==> nextcloud-vpn-watchdog.service registrado"

# 5. Sudoers (usa usuário real, não root)
SUDOERS_FILE=/etc/sudoers.d/nextcloud-vpn-$REAL_USER
cat > "$SUDOERS_FILE" << EOF
# Nextcloud VPN watchdog — $REAL_USER pode gerenciar $IFACE sem senha
$REAL_USER ALL=(root) NOPASSWD: /usr/bin/wg show $IFACE transfer
$REAL_USER ALL=(root) NOPASSWD: /usr/bin/wg-quick up $IFACE
$REAL_USER ALL=(root) NOPASSWD: /usr/bin/wg-quick down $IFACE
EOF
chmod 440 "$SUDOERS_FILE"
visudo -c -f "$SUDOERS_FILE"
echo "==> Sudoers configurado em $SUDOERS_FILE"

# 6. Habilitar e iniciar watchdog
systemctl daemon-reload
systemctl enable --now nextcloud-vpn-watchdog.service
echo "==> Watchdog ativo"

# 7. Teste de conectividade (sobe VPN manualmente uma vez para validar)
echo "==> Testando handshake WireGuard..."
wg-quick up "$IFACE" 2>/dev/null || true
sleep 3
if ping -c 1 -W 4 192.168.15.2 &>/dev/null; then
    echo "==> Nextcloud acessível via VPN (192.168.15.2)"
else
    echo "AVISO: ping a 192.168.15.2 falhou — verifique firewall ou endpoint"
fi
wg-quick down "$IFACE" 2>/dev/null || true

echo ""
echo "Instalação concluída. O watchdog gerencia a VPN automaticamente:"
echo "  UP   → quando rpa4all-files está ativo"
echo "  DOWN → após {idle_timeout}s sem transferência"
echo "Status: systemctl status nextcloud-vpn-watchdog"
"""


async def _read_nc_logs(lines: int = 50) -> str:
    """Lê as últimas N linhas do nextcloud.log via docker exec."""
    container = await _resolve_nc_container()
    _, out, err = await _run_command(
        "docker",
        "exec",
        container,
        "tail",
        f"-n{lines}",
        "/var/www/html/data/nextcloud.log",
    )
    return out or err


def _is_unsafe_lto_source(source: str) -> bool:
    normalized = source.rstrip("/") or "/"
    return any(
        normalized == unsafe or normalized.startswith(f"{unsafe}/")
        for unsafe in _LTO_UNSAFE_SOURCES
    )


def _classify_lto_mount(mounts: list[dict[str, Any]]) -> dict[str, Any]:
    """Classifica a montagem do storage /LTO com base no histórico de incidentes."""
    mount = next(
        (item for item in mounts if item.get("Destination") == _LTO_EXTERNAL_DEST),
        None,
    )
    if mount is None:
        return {
            "ok": False,
            "configured": False,
            "destination": _LTO_EXTERNAL_DEST,
            "warnings": [f"Mount {_LTO_EXTERNAL_DEST} não encontrado no container {_NC_CONTAINER}"],
        }

    source = str(mount.get("Source", "")).rstrip("/")
    unsafe = _is_unsafe_lto_source(source)
    expected = source == _LTO_STAGING_BIND
    warnings: list[str] = []
    if unsafe:
        warnings.append(
            "Fonte do /LTO aponta para LTFS/export direto. O incidente de 2026-04-23 exige staging em disco antes do flush para fita."
        )
    elif not expected:
        warnings.append(
            f"Fonte do /LTO difere do bind staging esperado ({_LTO_STAGING_BIND}): {source or '<vazio>'}"
        )

    return {
        "ok": not unsafe and bool(source),
        "configured": True,
        "expected_staging_bind": expected,
        "unsafe_source": unsafe,
        "source": source,
        "destination": mount.get("Destination"),
        "mode": mount.get("Mode", ""),
        "warnings": warnings,
    }


async def _nextcloud_storage_diagnostics() -> dict[str, Any]:
    """Executa checks baseados no histórico de falhas de storage do Nextcloud."""
    container = await _resolve_nc_container()
    diagnostics: dict[str, Any] = {
        "container": container,
        "historical_incident": "docs/INCIDENTS/NEXTCLOUD_TANK_LTO_UPLOAD_2026-04-23.md",
    }

    try:
        rc, out, err = await _run_command(
            "docker",
            "inspect",
            container,
            "--format",
            "{{json .Mounts}}",
        )
        if rc != 0:
            raise RuntimeError(err or out or "docker inspect falhou")
        mounts = json.loads(out or "[]")
        diagnostics["lto_mount"] = _classify_lto_mount(mounts)
    except Exception as exc:
        diagnostics["lto_mount"] = {"ok": False, "error": str(exc)}

    try:
        rc, out, err = await _run_command(
            "docker",
            "exec",
            "-u",
            "www-data",
            container,
            "sh",
            "-lc",
            f'p={_LTO_EXTERNAL_DEST}/.agent_probe_$$; date > "$p"; stat -c "%u:%g %a" "$p"; rm -f "$p"',
        )
        diagnostics["write_probe"] = {
            "ok": rc == 0,
            "details": out or err,
        }
    except Exception as exc:
        diagnostics["write_probe"] = {"ok": False, "error": str(exc)}

    try:
        rc, out, err = await _run_occ("files_external:list")
        diagnostics["files_external"] = {
            "ok": rc == 0,
            "output": (out or err)[:2000],
        }
    except Exception as exc:
        diagnostics["files_external"] = {"ok": False, "error": str(exc)}

    diagnostics["ok"] = all(
        diagnostics.get(section, {}).get("ok", False)
        for section in ("lto_mount", "write_probe", "files_external")
    )
    return diagnostics


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

    if action == "admin.storage_diagnostics":
        return await _nextcloud_storage_diagnostics()

    if action == "admin.logs":
        lines = int(params.get("lines", 50))
        return {"log": await _read_nc_logs(lines)}

    if action == "files.upload":
        path = params.get("path", "")
        content_b64 = params.get("content_b64", "")
        if not path or not content_b64:
            return {"error": "path e content_b64 são obrigatórios"}
        if dry_run:
            return {"dry_run": True, "url": _webdav_url(username, path)}
        try:
            data = base64.b64decode(content_b64, validate=True)
        except Exception:
            return {"error": "content_b64 inválido"}
        try:
            status = await _webdav_upload(username, path, data, params.get("content_type", "application/octet-stream"))
        except ValueError as exc:
            return {"error": str(exc)}
        return {"status": status, "uploaded": status in (200, 201, 204)}

    if action == "files.download":
        path = params.get("path", "")
        if not path:
            return {"error": "path é obrigatório"}
        content = await _webdav_download(username, path)
        return {"size_bytes": len(content), "content_b64": base64.b64encode(content).decode()}

    if action == "vpn.provision":
        # Provisiona peer WireGuard para novo usuário Nextcloud
        comment = params.get("comment", f"nextcloud-user:{username}")
        if dry_run:
            return {"dry_run": True, "would_allocate_ip": "10.66.66.X/32"}
        try:
            privkey, pubkey = await _wg_keygen()
            peer_ip = _wg_next_ip()
            await _wg_register_peer(pubkey, peer_ip, comment=comment)
            return {
                "peer_ip": peer_ip,
                "public_key": pubkey,
                "client_config": _wg_client_config(privkey, peer_ip),
                "watchdog_script": _wg_watchdog_script(),
                "watchdog_service": _wg_watchdog_service(),
                "watchdog_sudoers": _wg_watchdog_sudoers(),
                "setup_instructions": (
                    "1. Salve client_config em /etc/wireguard/homelab-nc.conf\n"
                    "2. Salve watchdog_script em /usr/local/bin/nextcloud-vpn-watchdog.sh && chmod +x\n"
                    "3. Salve watchdog_service em /etc/systemd/system/nextcloud-vpn-watchdog.service\n"
                    "4. Aplique watchdog_sudoers em /etc/sudoers.d/nextcloud-vpn (substitua $USER pelo usuário)\n"
                    "5. systemctl enable --now nextcloud-vpn-watchdog\n"
                    "A VPN sobe automaticamente quando rpa4all-files está ativo "
                    "e desce após 5 minutos sem transferência."
                ),
            }
        except Exception as exc:
            return {"error": str(exc)}

    if action == "vpn.config":
        # Retorna config de cliente para peer já provisionado (usuário deve ter peer_ip e privkey)
        peer_ip = params.get("peer_ip", "")
        privkey = params.get("privkey", "")
        if not peer_ip or not privkey:
            return {"error": "peer_ip e privkey são obrigatórios para vpn.config"}
        return {"client_config": _wg_client_config(privkey, peer_ip)}

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

        # Nextcloud interno (critério principal para operação do agente)
        try:
            tc = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=tc) as session:
                async with session.get(f"{_NC_INTERNAL_URL}/status.php") as resp:
                    results["nextcloud_internal"] = {
                        "reachable": resp.status == 200,
                        "status_code": resp.status,
                        "url": _NC_INTERNAL_URL,
                    }
        except Exception as exc:
            results["nextcloud_internal"] = {"reachable": False, "error": str(exc)}

        # Nextcloud público (informativo; pode falhar por Cloudflare/proxy)
        try:
            tc = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=tc) as session:
                async with session.get(f"{_NC_URL}/status.php") as resp:
                    results["nextcloud_external"] = {
                        "reachable": resp.status == 200,
                        "status_code": resp.status,
                        "url": _NC_URL,
                    }
        except Exception as exc:
            results["nextcloud_external"] = {"reachable": False, "error": str(exc)}

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

        try:
            storage = await asyncio.wait_for(_nextcloud_storage_diagnostics(), timeout=10)
            results["storage"] = storage
        except Exception as exc:
            results["storage"] = {"ok": False, "error": str(exc)}

        overall = all(
            [
                results.get("nextcloud_internal", {}).get("reachable", False),
                results.get("ollama_gpu0", {}).get("reachable", False),
                results.get("occ", {}).get("reachable", False),
                results.get("storage", {}).get("ok", False),
            ]
        )
        return {"ok": overall, "components": results}


# ─── Singleton ────────────────────────────────────────────────────────────────

_agent: NextcloudAgent | None = None


def get_nextcloud_agent():
    """Retorna NextcloudAgent (v1 ou v2 conforme NEXTCLOUD_AGENT_VERSION)."""
    global _agent
    if os.getenv("NEXTCLOUD_AGENT_VERSION", "v1") == "v2":
        from specialized_agents.nextcloud_agent_langgraph import get_nextcloud_agent_langgraph
        return get_nextcloud_agent_langgraph()
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


@router.post("/files/list", response_model=NextcloudFilesListResponse)
async def nextcloud_files_list_post(req: NextcloudFilesListRequest) -> NextcloudFilesListResponse:
    """Lista arquivos e pastas via body JSON (compatível com chamadas legadas)."""
    items = await _webdav_propfind(req.username, req.path, req.depth)
    return NextcloudFilesListResponse(items=items, total_items=len(items))


@router.post("/files/mkdir")
async def nextcloud_files_mkdir(req: NextcloudFilesListRequest) -> dict[str, Any]:
    """Cria pasta via WebDAV MKCOL."""
    status = await _webdav_mkdir(req.username, req.path)
    return {"status": status, "created": status in (201, 405)}


@router.post("/files/upload")
async def nextcloud_files_upload(req: NextcloudFileUploadRequest) -> dict[str, Any]:
    """Envia arquivo via WebDAV PUT (máx 35 MB, 3 tentativas com backoff).

    O conteúdo deve ser enviado em base64 no campo `content_b64`.
    """
    try:
        data = base64.b64decode(req.content_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="content_b64 inválido")
    try:
        status = await _webdav_upload(req.username, req.path, data, req.content_type)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    return {"status": status, "uploaded": status in (200, 201, 204)}


@router.get("/files/download")
async def nextcloud_files_download(username: str, path: str) -> dict[str, Any]:
    """Baixa arquivo via WebDAV GET e retorna conteúdo em base64."""
    content = await _webdav_download(username, path)
    return {"size_bytes": len(content), "content_b64": base64.b64encode(content).decode()}


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


@router.get("/admin/storage-diagnostics")
async def nextcloud_admin_storage_diagnostics() -> dict[str, Any]:
    """Valida o storage /LTO com base no incidente histórico de LTFS/Nextcloud."""
    return await _nextcloud_storage_diagnostics()


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


class NextcloudVpnProvisionRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200, description="Username Nextcloud (identifica o peer)")
    comment: str = Field(default="", max_length=200)
    idle_timeout: int = Field(default=300, ge=60, le=3600, description="Segundos de idle antes de desligar VPN")
    dry_run: bool = Field(default=False)


@router.post("/vpn/provision")
async def nextcloud_vpn_provision(req: NextcloudVpnProvisionRequest) -> dict[str, Any]:
    """Provisiona peer WireGuard + retorna instalador completo para o cliente.

    O campo `install_script` contém um bash script autocontido que, ao ser
    executado com `sudo bash`, configura automaticamente:
      - /etc/wireguard/homelab-nc.conf
      - /usr/local/bin/nextcloud-vpn-watchdog.sh
      - /etc/systemd/system/nextcloud-vpn-watchdog.service
      - /etc/sudoers.d/nextcloud-vpn-<user>
      - systemctl enable --now nextcloud-vpn-watchdog

    Uso rápido no cliente:
      curl -sX POST http://192.168.15.2:8503/nextcloud/vpn/provision \\
        -H 'Content-Type: application/json' \\
        -d '{{"username":"<user>"}}' | python3 -c "
    import sys,json; d=json.load(sys.stdin)
    open('/tmp/install-nc-vpn.sh','w').write(d['install_script'])
    " && sudo bash /tmp/install-nc-vpn.sh
    """
    comment = req.comment or f"nextcloud-user:{req.username}"
    if req.dry_run:
        return {"dry_run": True, "would_allocate_ip": "10.66.66.X/32"}
    try:
        privkey, pubkey = await _wg_keygen()
        peer_ip = _wg_next_ip()
        await _wg_register_peer(pubkey, peer_ip, comment=comment)
        return {
            "peer_ip": peer_ip,
            "public_key": pubkey,
            "install_script": _wg_install_script(privkey, peer_ip, idle_timeout=req.idle_timeout),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/vpn/install", response_class=None)
async def nextcloud_vpn_install(req: NextcloudVpnProvisionRequest):
    """Provisiona peer e devolve o script instalador como text/plain para pipe direto.

    Uso no cliente (uma linha):
      curl -sX POST http://192.168.15.2:8503/nextcloud/vpn/install \\
        -H 'Content-Type: application/json' \\
        -d '{{"username":"<user>"}}' | sudo bash
    """
    from fastapi.responses import PlainTextResponse

    comment = req.comment or f"nextcloud-user:{req.username}"
    if req.dry_run:
        return PlainTextResponse("# dry_run=true — nenhuma alteração seria feita\necho DRY_RUN\n")
    try:
        privkey, pubkey = await _wg_keygen()
        peer_ip = _wg_next_ip()
        await _wg_register_peer(pubkey, peer_ip, comment=comment)
        script = _wg_install_script(privkey, peer_ip, idle_timeout=req.idle_timeout)
        return PlainTextResponse(script, media_type="text/x-shellscript")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
