"""
Google Home Adapter — token refresh automático + descoberta de dispositivos.

Estratégias de descoberta:
1. Google SDM API (Nest devices) — requer Device Access Console
2. Descoberta local via mDNS/Zeroconf (todos na LAN)
3. Fallback: combina ambos

Token é renovado automaticamente usando refresh_token de google_home_credentials.json.
"""
import asyncio
import json
import logging
import os
import re
import socket
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SDM_API = "https://smartdevicemanagement.googleapis.com/v1"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
CREDENTIALS_FILE = "google_home_credentials.json"

# Scopes necessários
SDM_SCOPE = "https://www.googleapis.com/auth/sdm.service"
GOOGLE_HOME_SCOPE = "https://www.googleapis.com/auth/home"
# Todos os scopes para controle completo
ALL_SCOPES = f"{SDM_SCOPE} {GOOGLE_HOME_SCOPE}"

# Google Home API (para dispositivos de terceiros vinculados ao Google Home)
GOOGLE_HOME_API_BASE = "https://home.googleapis.com"

# Tipos de dispositivo conhecidos por mDNS service type
MDNS_DEVICE_MAP = {
    "_googlecast._tcp.local.": "google_cast",
    "_hap._tcp.local.": "homekit",
    "_airplay._tcp.local.": "airplay",
    "_tplink._tcp.local.": "tplink",
    "_esphomelib._tcp.local.": "esphome",
    "_http._tcp.local.": "http_device",
}

# ---------------------------------------------------------------------------
# Token Manager
# ---------------------------------------------------------------------------

class GoogleTokenManager:
    """Gerencia access/refresh tokens OAuth2 do Google."""

    def __init__(self, credentials_path: Optional[str] = None):
        self._creds_path = credentials_path or self._find_credentials()
        self._client_id: Optional[str] = None
        self._client_secret: Optional[str] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._sdm_project_id: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._load_credentials()

    def _find_credentials(self) -> str:
        """Procura google_home_credentials.json no projeto."""
        candidates = [
            Path(os.getenv("EDDIE_ROOT", "")) / CREDENTIALS_FILE,
            Path.cwd() / CREDENTIALS_FILE,
            Path(__file__).resolve().parent.parent.parent / CREDENTIALS_FILE,
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return str(Path.cwd() / CREDENTIALS_FILE)

    def _load_credentials(self):
        """Carrega credenciais do arquivo JSON."""
        try:
            with open(self._creds_path) as f:
                creds = json.load(f)
            self._client_id = creds.get("client_id")
            self._client_secret = creds.get("client_secret")
            self._access_token = creds.get("access_token")
            self._refresh_token = creds.get("refresh_token")
            self._sdm_project_id = creds.get("sdm_project_id")
            logger.info("Google credentials carregadas de %s", self._creds_path)
        except FileNotFoundError:
            logger.warning("google_home_credentials.json não encontrado em %s", self._creds_path)
        except Exception as exc:
            logger.error("Erro ao carregar Google credentials: %s", exc)

        # Fallback para .env
        if not self._access_token:
            self._access_token = os.getenv("GOOGLE_HOME_TOKEN")
        if not self._refresh_token:
            self._refresh_token = os.getenv("GOOGLE_HOME_REFRESH_TOKEN")
        if not self._sdm_project_id:
            self._sdm_project_id = os.getenv("GOOGLE_SDM_PROJECT_ID")

    @property
    def has_credentials(self) -> bool:
        return bool(self._client_id and self._client_secret and self._refresh_token)

    @property
    def sdm_project_id(self) -> Optional[str]:
        return self._sdm_project_id

    async def get_access_token(self) -> Optional[str]:
        """Retorna access token válido, renovando se necessário."""
        if self._token_expiry and datetime.utcnow() < self._token_expiry:
            return self._access_token

        if not self.has_credentials:
            logger.warning("Sem credenciais para refresh — usando token do .env")
            return self._access_token

        try:
            refreshed = await self._refresh_access_token()
            if refreshed:
                return self._access_token
        except Exception as exc:
            logger.error("Falha ao renovar token: %s", exc)

        return self._access_token

    async def _refresh_access_token(self) -> bool:
        """Renova access token via refresh_token."""
        try:
            import httpx
        except ImportError:
            logger.error("httpx não disponível para refresh de token")
            return False

        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=data)
            resp.raise_for_status()
            tokens = resp.json()

        self._access_token = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)
        self._token_expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)

        # Salvar token atualizado no arquivo e no .env
        self._persist_token(tokens)
        logger.info("🔑 Google token renovado (expira em %ds)", expires_in)
        return True

    def _persist_token(self, tokens: Dict[str, Any]):
        """Salva novo access_token no credentials JSON e .env."""
        # Atualiza google_home_credentials.json
        try:
            with open(self._creds_path) as f:
                creds = json.load(f)
            creds["access_token"] = tokens["access_token"]
            if tokens.get("refresh_token"):
                creds["refresh_token"] = tokens["refresh_token"]
                self._refresh_token = tokens["refresh_token"]
            with open(self._creds_path, "w") as f:
                json.dump(creds, f, indent=2)
        except Exception as exc:
            logger.warning("Não foi possível salvar credentials JSON: %s", exc)

        # Atualiza .env
        env_path = Path(self._creds_path).parent / ".env"
        if not env_path.exists():
            env_path = Path.cwd() / ".env"
        try:
            if env_path.exists():
                lines = env_path.read_text().splitlines(keepends=True)
                new_lines = []
                found = False
                for line in lines:
                    if line.startswith("GOOGLE_HOME_TOKEN="):
                        new_lines.append(f"GOOGLE_HOME_TOKEN={tokens['access_token']}\n")
                        found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f"GOOGLE_HOME_TOKEN={tokens['access_token']}\n")
                env_path.write_text("".join(new_lines))
        except Exception as exc:
            logger.warning("Não foi possível atualizar .env: %s", exc)

    def generate_auth_url(self, redirect_uri: str = "http://localhost:8085", include_home_scope: bool = False) -> Optional[str]:
        """Gera URL de autorização OAuth2. Se include_home_scope=True, inclui scope Google Home."""
        if not self._client_id:
            return None
        scope = ALL_SCOPES if include_home_scope else SDM_SCOPE
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{qs}"

    async def exchange_code(self, code: str, redirect_uri: str = "http://localhost:8085") -> Dict[str, Any]:
        """Troca authorization code por access + refresh tokens."""
        try:
            import httpx
        except ImportError:
            return {"error": "httpx não disponível"}

        data = {
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data=data)
            resp.raise_for_status()
            tokens = resp.json()

        self._access_token = tokens["access_token"]
        self._refresh_token = tokens.get("refresh_token", self._refresh_token)
        self._token_expiry = datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600) - 60)
        self._persist_token(tokens)
        return tokens


# ---------------------------------------------------------------------------
# Local Device Discovery (mDNS / Zeroconf)
# ---------------------------------------------------------------------------

class LocalDeviceDiscovery:
    """Descobre dispositivos smart home na rede local via mDNS/Zeroconf."""

    def __init__(self, scan_timeout: float = 8.0):
        self._timeout = scan_timeout

    async def discover(self) -> List[Dict[str, Any]]:
        """Executa scan mDNS e retorna lista de dispositivos encontrados."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scan_sync)

    def _scan_sync(self) -> List[Dict[str, Any]]:
        """Scan síncrono via Zeroconf."""
        try:
            from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange
        except ImportError:
            logger.warning("zeroconf não instalado — pip install zeroconf")
            return []

        devices: List[Dict[str, Any]] = []
        seen = set()

        class Listener:
            def add_service(self, zc, type_, name):
                try:
                    info = zc.get_service_info(type_, name)
                    if not info:
                        return
                    host = None
                    if info.addresses:
                        host = socket.inet_ntoa(info.addresses[0])
                    friendly = info.get_name() if hasattr(info, 'get_name') else name.split(".")[0]
                    key = f"{host}:{info.port}" if host else name
                    if key in seen:
                        return
                    seen.add(key)

                    dev = {
                        "name": friendly,
                        "host": host,
                        "port": info.port,
                        "service_type": type_,
                        "category": MDNS_DEVICE_MAP.get(type_, "unknown"),
                        "properties": {},
                    }
                    if info.properties:
                        dev["properties"] = {
                            k.decode("utf-8", errors="replace") if isinstance(k, bytes) else k:
                            v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
                            for k, v in info.properties.items()
                        }
                    # Enriquecer: model name, manufacturer
                    props = dev["properties"]
                    if "md" in props:
                        dev["model"] = props["md"]
                    if "fn" in props:
                        dev["name"] = props["fn"]
                    devices.append(dev)
                except Exception as exc:
                    logger.debug("Erro ao processar serviço mDNS %s: %s", name, exc)

            def remove_service(self, zc, type_, name):
                pass

            def update_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        listener = Listener()
        browsers = []
        service_types = list(MDNS_DEVICE_MAP.keys())
        for st in service_types:
            try:
                browsers.append(ServiceBrowser(zc, st, listener))
            except Exception:
                pass

        time.sleep(self._timeout)
        zc.close()

        logger.info("🔍 Descoberta local: %d dispositivos encontrados", len(devices))
        return devices


# ---------------------------------------------------------------------------
# Google Cast Discovery (Chromecast, Google Home speakers, Nest)
# ---------------------------------------------------------------------------

class GoogleCastDiscovery:
    """Descobre Google Cast devices (speakers, displays, Chromecasts)."""

    async def discover(self) -> List[Dict[str, Any]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scan_sync)

    def _scan_sync(self) -> List[Dict[str, Any]]:
        try:
            from zeroconf import Zeroconf, ServiceBrowser
        except ImportError:
            return []

        devices = []
        seen = set()

        class CastListener:
            def add_service(self, zc, type_, name):
                try:
                    info = zc.get_service_info(type_, name)
                    if not info or not info.addresses:
                        return
                    host = socket.inet_ntoa(info.addresses[0])
                    key = host
                    if key in seen:
                        return
                    seen.add(key)

                    props = {}
                    if info.properties:
                        props = {
                            k.decode("utf-8", errors="replace") if isinstance(k, bytes) else k:
                            v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
                            for k, v in info.properties.items()
                        }

                    friendly = props.get("fn", name.split(".")[0])
                    model = props.get("md", "Google Cast")
                    manufacturer = props.get("mn", "Google")

                    # Inferir room a partir do nome
                    room = self._infer_room(friendly)

                    devices.append({
                        "name": friendly,
                        "host": host,
                        "port": info.port,
                        "model": model,
                        "manufacturer": manufacturer,
                        "category": "google_cast",
                        "cast_type": self._infer_type(model, friendly),
                        "room": room,
                        "properties": props,
                    })
                except Exception:
                    pass

            def _infer_type(self, model: str, name: str = "") -> str:
                model_l = model.lower()
                name_l = name.lower()
                if "hub" in model_l or "nest hub" in model_l or "display" in model_l:
                    return "display"
                if "mini" in model_l or "nest mini" in model_l or "home mini" in model_l:
                    return "speaker"
                if "home" in model_l or "nest" in model_l:
                    return "speaker"
                if "tv" in name_l or "television" in name_l:
                    return "tv"
                if "chromecast" in model_l:
                    # Se o nome contém "tv" ou "sala", provavelmente está numa TV
                    if any(kw in name_l for kw in ("tv", "sala", "quarto", "living")):
                        return "tv"
                    return "chromecast"
                if "tv" in model_l or "shield" in model_l:
                    return "tv"
                return "cast"

            def _infer_room(self, name: str) -> str:
                """Infere cômodo a partir do nome do dispositivo."""
                import unicodedata as _ud
                name_l = name.lower()
                name_norm = _ud.normalize("NFD", name_l)
                name_norm = "".join(c for c in name_norm if _ud.category(c) != "Mn")
                room_keywords = {
                    "sala": "Sala",
                    "living": "Sala",
                    "quarto": "Quarto",
                    "bedroom": "Quarto",
                    "cozinha": "Cozinha",
                    "kitchen": "Cozinha",
                    "escritorio": "Escritório",
                    "office": "Escritório",
                    "banheiro": "Banheiro",
                    "bathroom": "Banheiro",
                    "garagem": "Garagem",
                    "garage": "Garagem",
                    "varanda": "Varanda",
                    "area": "Área Externa",
                    "jardim": "Jardim",
                    "trailer": "Trailer",
                }
                for kw, room in room_keywords.items():
                    if kw in name_norm:
                        return room
                return "default"

            def remove_service(self, zc, type_, name):
                pass

            def update_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        listener = CastListener()
        browser = ServiceBrowser(zc, "_googlecast._tcp.local.", listener)
        time.sleep(6)
        zc.close()

        logger.info("📺 Google Cast: %d dispositivos encontrados", len(devices))
        return devices


# ---------------------------------------------------------------------------
# Google Home Controller (controle via Google Home API — todos os devices)
# ---------------------------------------------------------------------------

class GoogleHomeController:
    """
    Controla dispositivos via Google Home API (home.googleapis.com).

    Diferente do SDM (que só funciona com Nest), o Google Home API controla
    TODOS os dispositivos vinculados ao Google Home.

    Requer:
    - Google Home API habilitada no projeto GCP
    - OAuth com scope 'https://www.googleapis.com/auth/home'
    - Dispositivos vinculados no app Google Home
    """

    def __init__(self, token_manager: GoogleTokenManager):
        self._tm = token_manager
        self._structures: List[Dict[str, Any]] = []
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._device_name_map: Dict[str, str] = {}  # nome normalizado → device_id
        self._available = False
        self._last_check: Optional[datetime] = None

    @property
    def is_available(self) -> bool:
        """Retorna True se o Google Home API está disponível."""
        return self._available

    async def check_availability(self) -> bool:
        """Verifica se o Google Home API está acessível com as credenciais atuais."""
        # Evitar check repetido em menos de 5 min
        if self._last_check:
            age = (datetime.utcnow() - self._last_check).total_seconds()
            if age < 300:
                return self._available

        token = await self._tm.get_access_token()
        if not token:
            self._available = False
            return False

        try:
            import httpx
        except ImportError:
            self._available = False
            return False

        headers = {"Authorization": f"Bearer {token}"}

        # Tentar endpoint de structures (indicador de que a API está habilitada)
        for api_ver in ["v1", "v2"]:
            for endpoint in [
                f"{GOOGLE_HOME_API_BASE}/{api_ver}/structures",
                f"{GOOGLE_HOME_API_BASE}/{api_ver}/devices",
            ]:
                try:
                    async with httpx.AsyncClient(timeout=8) as client:
                        resp = await client.get(endpoint, headers=headers)
                        if resp.status_code in (200, 401, 403):
                            self._available = resp.status_code == 200
                            self._last_check = datetime.utcnow()
                            if self._available:
                                logger.info("✅ Google Home API disponível em %s", endpoint)
                            elif resp.status_code == 403:
                                logger.info("🔒 Google Home API requer scope 'home' (tem apenas 'sdm.service')")
                            return self._available
                except Exception:
                    continue

        self._available = False
        self._last_check = datetime.utcnow()
        return False

    async def list_devices(self) -> List[Dict[str, Any]]:
        """Lista todos os dispositivos via Google Home API."""
        token = await self._tm.get_access_token()
        if not token:
            return []

        try:
            import httpx
        except ImportError:
            return []

        headers = {"Authorization": f"Bearer {token}"}
        devices = []

        for api_ver in ["v1", "v2"]:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        f"{GOOGLE_HOME_API_BASE}/{api_ver}/devices",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_devices = data.get("devices", data.get("items", []))
                        for raw in raw_devices:
                            dev = self._parse_google_home_device(raw)
                            if dev:
                                devices.append(dev)
                                # Indexar por nome normalizado
                                norm = _normalize(dev["name"])
                                self._devices[dev.get("google_device_id", "")] = dev
                                self._device_name_map[norm] = dev.get("google_device_id", "")
                        logger.info("🏠 Google Home API: %d dispositivos (%s)", len(devices), api_ver)
                        return devices
            except Exception as exc:
                logger.debug("Google Home API %s error: %s", api_ver, exc)
                continue

        return devices

    def _parse_google_home_device(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Converte device do Google Home API para formato interno."""
        name = raw.get("name", raw.get("displayName", ""))
        device_id = raw.get("id", raw.get("name", ""))
        device_type = raw.get("type", raw.get("deviceType", ""))
        room = raw.get("roomHint", raw.get("room", "default"))
        traits = raw.get("traits", [])

        # Mapear tipo Google para tipo interno
        type_map = {
            "action.devices.types.LIGHT": "light",
            "action.devices.types.SWITCH": "switch",
            "action.devices.types.OUTLET": "plug",
            "action.devices.types.FAN": "fan",
            "action.devices.types.THERMOSTAT": "thermostat",
            "action.devices.types.AC_UNIT": "switch",
            "action.devices.types.TV": "tv",
            "action.devices.types.SPEAKER": "speaker",
        }

        return {
            "name": name,
            "device_type": type_map.get(device_type, "switch"),
            "room": room,
            "category": "google_home",
            "google_device_id": device_id,
            "traits": traits,
            "source": "google_home_api",
        }

    async def execute_command(
        self, device_id: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executa comando em dispositivo via Google Home API.

        Args:
            device_id: ID do dispositivo no Google Home
            action: "on", "off", "set_brightness", "set_temperature"
            params: Parâmetros extras (brightness, temperature, etc.)

        Returns:
            {"success": bool, "error": str}
        """
        token = await self._tm.get_access_token()
        if not token:
            return {"success": False, "error": "Sem token Google"}

        # Mapear ação para comando Google Home
        command_map = {
            "on": {"command": "action.devices.commands.OnOff", "params": {"on": True}},
            "off": {"command": "action.devices.commands.OnOff", "params": {"on": False}},
            "set_brightness": {
                "command": "action.devices.commands.BrightnessAbsolute",
                "params": {"brightness": (params or {}).get("brightness", 50)},
            },
            "set_temperature": {
                "command": "action.devices.commands.ThermostatTemperatureSetpoint",
                "params": {"thermostatTemperatureSetpoint": (params or {}).get("temperature", 22)},
            },
        }

        cmd = command_map.get(action)
        if not cmd:
            return {"success": False, "error": f"Ação '{action}' não suportada"}

        try:
            import httpx
        except ImportError:
            return {"success": False, "error": "httpx não disponível"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "command": cmd["command"],
            "params": cmd["params"],
        }

        for api_ver in ["v1", "v2"]:
            url = f"{GOOGLE_HOME_API_BASE}/{api_ver}/devices/{device_id}:executeCommand"
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        logger.info("✅ Google Home command %s → %s OK", action, device_id)
                        return {"success": True}
                    elif resp.status_code == 403:
                        return {
                            "success": False,
                            "error": "Google Home API requer re-autorização com scope 'home'. "
                                     "Execute: python3 setup_google_home_control.py",
                        }
                    elif resp.status_code == 404:
                        continue  # Tentar próxima versão da API
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                        }
            except Exception as exc:
                logger.debug("Google Home API %s execute error: %s", api_ver, exc)
                continue

        return {"success": False, "error": "Google Home API não disponível"}

    def find_device_by_name(self, name: str) -> Optional[str]:
        """Encontra device_id Google Home pelo nome do dispositivo."""
        norm = _normalize(name)
        # Match exato
        if norm in self._device_name_map:
            return self._device_name_map[norm]
        # Match parcial
        for dev_name, dev_id in self._device_name_map.items():
            if norm in dev_name or dev_name in norm:
                return dev_id
        return None


def _normalize(text: str) -> str:
    """Remove acentos e normaliza texto para comparação."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


# ---------------------------------------------------------------------------
# Google Home Adapter (consolida tudo)
# ---------------------------------------------------------------------------

class GoogleHomeAdapter:
    """
    Adapter unificado para descoberta e controle de dispositivos Google Home.

    Combina:
    - Google SDM API (Nest) com auto-refresh de token
    - Descoberta local via mDNS/Zeroconf
    - Google Cast discovery
    """

    def __init__(self):
        self.token_manager = GoogleTokenManager()
        self.local_discovery = LocalDeviceDiscovery()
        self.cast_discovery = GoogleCastDiscovery()
        self.home_controller = GoogleHomeController(self.token_manager)
        self._last_sync: Optional[datetime] = None
        self._cached_devices: List[Dict[str, Any]] = []
        self._cache_ttl = 300  # 5 minutos

    @property
    def has_google_auth(self) -> bool:
        return self.token_manager.has_credentials

    @property
    def sdm_project_id(self) -> Optional[str]:
        return self.token_manager.sdm_project_id

    async def discover_all_devices(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Descobre todos os dispositivos disponíveis (Google + Local + Cast).
        Usa cache de 5 minutos para evitar scans repetidos.
        Prioridade: SDM > Cast (dados ricos) > Local (genérico).
        """
        if not force and self._cached_devices and self._last_sync:
            age = (datetime.utcnow() - self._last_sync).total_seconds()
            if age < self._cache_ttl:
                logger.debug("Usando cache de dispositivos (%ds)", int(age))
                return self._cached_devices

        all_devices: List[Dict[str, Any]] = []
        seen_hosts: set = set()

        # 1. Google SDM (Nest devices) — maior prioridade
        sdm_devices = await self._discover_sdm()
        for dev in sdm_devices:
            all_devices.append(dev)
            if dev.get("host"):
                seen_hosts.add(dev["host"])

        # 2. Google Cast (speakers, TVs, Chromecasts) — dados ricos (room, tipo)
        cast_devices = await self.cast_discovery.discover()
        for dev in cast_devices:
            if dev.get("host") not in seen_hosts:
                all_devices.append(dev)
                seen_hosts.add(dev["host"])

        # 4. Descoberta local genérica (mDNS) — preenche o restante
        local_devices = await self.local_discovery.discover()
        for dev in local_devices:
            if dev.get("host") not in seen_hosts:
                all_devices.append(dev)
                seen_hosts.add(dev["host"])

        self._cached_devices = all_devices
        self._last_sync = datetime.utcnow()

        logger.info("🏠 Total de dispositivos descobertos: %d (SDM=%d, Cast=%d, Local=%d)",
                 len(all_devices), len(sdm_devices), len(cast_devices), len(local_devices))
        return all_devices

    async def _discover_sdm(self) -> List[Dict[str, Any]]:
        """Tenta descobrir devices via Google SDM API."""
        token = await self.token_manager.get_access_token()
        if not token:
            logger.debug("Sem token Google — pulando SDM")
            return []

        project_id = self.sdm_project_id
        if not project_id:
            logger.debug("Sem SDM project ID — pulando SDM")
            return []

        try:
            import httpx
        except ImportError:
            return []

        url = f"{GOOGLE_SDM_API}/enterprises/{project_id}/devices"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 401:
                    # Token inválido, tenta renovar
                    token = await self.token_manager.get_access_token()
                    if token:
                        headers = {"Authorization": f"Bearer {token}"}
                        resp = await client.get(url, headers=headers)

                if resp.status_code == 404:
                    logger.warning("SDM project '%s' não encontrado — configure em Device Access Console", project_id)
                    return []

                resp.raise_for_status()
                data = resp.json()

            devices = []
            for raw in data.get("devices", []):
                dev = self._parse_sdm_device(raw)
                if dev:
                    devices.append(dev)
            logger.info("📡 SDM: %d dispositivos Nest encontrados", len(devices))
            return devices

        except Exception as exc:
            logger.warning("SDM API indisponível: %s", exc)
            return []

    def _parse_sdm_device(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Converte device SDM para formato interno."""
        device_name = raw.get("name", "")
        device_type_str = raw.get("type", "")
        traits = raw.get("traits", {})
        parent_relations = raw.get("parentRelations", [])

        room = "default"
        if parent_relations:
            room = parent_relations[0].get("displayName", "default")

        display_name = traits.get("sdm.devices.traits.Info", {}).get(
            "customName", device_name.split("/")[-1]
        )

        # Mapear tipo SDM para tipo interno
        type_map = {
            "sdm.devices.types.LIGHT": "light",
            "sdm.devices.types.THERMOSTAT": "thermostat",
            "sdm.devices.types.CAMERA": "camera",
            "sdm.devices.types.DOORBELL": "doorbell",
            "sdm.devices.types.LOCK": "lock",
            "sdm.devices.types.DISPLAY": "tv",
            "sdm.devices.types.SPEAKER": "speaker",
        }
        device_type = type_map.get(device_type_str, "custom")

        # Estado
        state = "unknown"
        if "sdm.devices.traits.OnOff" in traits:
            state = "on" if traits["sdm.devices.traits.OnOff"].get("on") else "off"

        return {
            "name": display_name,
            "device_type": device_type,
            "room": room,
            "state": state,
            "category": "google_nest",
            "google_device_id": device_name,
            "traits": list(traits.keys()),
            "brightness": traits.get("sdm.devices.traits.Brightness", {}).get("brightness"),
            "temperature": traits.get("sdm.devices.traits.Temperature", {}).get("ambientTemperatureCelsius"),
        }

    async def send_sdm_command(self, google_device_id: str, action: str, params: Dict[str, Any]) -> bool:
        """Envia comando para dispositivo via SDM API."""
        token = await self.token_manager.get_access_token()
        if not token:
            return False

        trait_commands = {
            "on": ("sdm.devices.commands.OnOff.SetOnOff", {"on": True}),
            "off": ("sdm.devices.commands.OnOff.SetOnOff", {"on": False}),
            "set_brightness": ("sdm.devices.commands.Brightness.SetBrightness",
                               {"brightness": params.get("brightness", 50)}),
            "set_temperature": ("sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                                {"heatCelsius": params.get("temperature", 22)}),
            "lock": ("sdm.devices.commands.LockUnlock.SetLock", {"lock": True}),
            "unlock": ("sdm.devices.commands.LockUnlock.SetLock", {"lock": False}),
        }

        if action not in trait_commands:
            logger.warning("Ação '%s' não mapeada para SDM", action)
            return False

        command_name, command_params = trait_commands[action]
        url = f"{GOOGLE_SDM_API}/{google_device_id}:executeCommand"
        headers = {"Authorization": f"Bearer {token}"}
        body = {"command": command_name, "params": command_params}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
            logger.info("✅ SDM command %s → %s OK", action, google_device_id.split("/")[-1])
            return True
        except Exception as exc:
            logger.error("❌ SDM command falhou: %s", exc)
            return False

    def generate_setup_url(self) -> Optional[str]:
        """Gera URL OAuth para (re)autorização com Google SDM."""
        return self.token_manager.generate_auth_url()

    def generate_home_setup_url(self) -> Optional[str]:
        """Gera URL OAuth com scope Google Home (para controlar dispositivos de terceiros)."""
        return self.token_manager.generate_auth_url(include_home_scope=True)

    async def send_google_home_command(
        self, device_name: str, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Controla dispositivo via Google Home API (funciona com dispositivos vinculados ao Google Home).

        Args:
            device_name: Nome do dispositivo (ex: "Ventilador Escritório")
            action: "on", "off", "set_brightness", "set_temperature"
            params: Parâmetros extras

        Returns:
            {"success": bool, "error": str}
        """
        # Se não temos devices listados, tentar listar
        if not self.home_controller._devices:
            await self.home_controller.list_devices()

        # Encontrar device por nome
        device_id = self.home_controller.find_device_by_name(device_name)
        if not device_id:
            # Tentar listar novamente (cache pode estar vazio)
            await self.home_controller.list_devices()
            device_id = self.home_controller.find_device_by_name(device_name)

        if not device_id:
            return {
                "success": False,
                "error": f"Dispositivo '{device_name}' não encontrado no Google Home. "
                         "Verifique se está vinculado no app Google Home.",
            }

        return await self.home_controller.execute_command(device_id, action, params)

    async def exchange_auth_code(self, code: str) -> Dict[str, Any]:
        """Troca auth code por tokens."""
        return await self.token_manager.exchange_code(code)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_adapter_instance: Optional[GoogleHomeAdapter] = None


def get_google_home_adapter() -> GoogleHomeAdapter:
    """Retorna instância singleton do Google Home Adapter."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = GoogleHomeAdapter()
    return _adapter_instance
