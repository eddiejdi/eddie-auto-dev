"""
Google Assistant Agent — controla automações residenciais via Google Home.

Funcionalidades:
- Integração com Google Home Device Access API (SDM)
- Controle de luzes, tomadas, termostatos, câmeras, fechaduras, etc.
- Cenas e rotinas (schedule / evento)
- Comandos por linguagem natural (via LLM local)
- Publicação de eventos no Communication Bus
- Persistência de estado e histórico
"""
import asyncio
import json
import logging
import os
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

from .device_manager import (
    Device,
    DeviceManager,
    DeviceState,
    DeviceType,
    Routine,
    Scene,
)

# Communication Bus integration
try:
    from specialized_agents.agent_communication_bus import (
        MessageType,
        get_communication_bus,
        log_error,
        log_request,
        log_response,
        log_task_end,
        log_task_start,
    )
    _BUS_OK = True
except ImportError:
    _BUS_OK = False

# Agent Memory integration
try:
    from specialized_agents.agent_memory import get_agent_memory
    _MEMORY_OK = True
except ImportError:
    _MEMORY_OK = False

# Home Assistant adapter
try:
    from specialized_agents.home_automation.ha_adapter import HomeAssistantAdapter
    _HA_OK = True
except ImportError:
    _HA_OK = False

# Google Home adapter (token refresh + local discovery + Google Home control)
try:
    from specialized_agents.home_automation.google_home_adapter import (
        GoogleHomeAdapter,
        get_google_home_adapter,
    )
    _GHOME_OK = True
except ImportError:
    _GHOME_OK = False


# LLM config
try:
    from specialized_agents.config import LLM_CONFIG
except ImportError:
    LLM_CONFIG = {"base_url": "http://192.168.15.2:11434", "model": "qwen2.5-coder:1.5b"}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "google_assistant"

GOOGLE_HOME_API_BASE = "https://homegraph.googleapis.com/v1"
GOOGLE_SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"

# Mapeamento tipo SDM → DeviceType
SDM_TYPE_MAP: Dict[str, DeviceType] = {
    "sdm.devices.types.LIGHT": DeviceType.LIGHT,
    "sdm.devices.types.THERMOSTAT": DeviceType.THERMOSTAT,
    "sdm.devices.types.CAMERA": DeviceType.CAMERA,
    "sdm.devices.types.DOORBELL": DeviceType.DOORBELL,
    "sdm.devices.types.LOCK": DeviceType.LOCK,
    "sdm.devices.types.DISPLAY": DeviceType.TV,
    "sdm.devices.types.SPEAKER": DeviceType.SPEAKER,
}

# Mapeamento de comandos em linguagem natural → ações
COMMAND_MAP: Dict[str, Dict[str, Any]] = {
    "ligar": {"state": "on"},
    "ligue": {"state": "on"},
    "liga": {"state": "on"},
    "ativar": {"state": "on"},
    "ative": {"state": "on"},
    "desligar": {"state": "off"},
    "desligue": {"state": "off"},
    "desliga": {"state": "off"},
    "desativar": {"state": "off"},
    "desative": {"state": "off"},
    "acender": {"state": "on"},
    "acenda": {"state": "on"},
    "apagar": {"state": "off"},
    "apague": {"state": "off"},
    "aumentar": {"action": "increase"},
    "aumente": {"action": "increase"},
    "diminuir": {"action": "decrease"},
    "diminua": {"action": "decrease"},
    "trancar": {"state": "on", "device_type": "lock"},
    "tranque": {"state": "on", "device_type": "lock"},
    "destrancar": {"state": "off", "device_type": "lock"},
    "destranque": {"state": "off", "device_type": "lock"},
    "abrir": {"state": "on", "device_type": "curtain"},
    "abra": {"state": "on", "device_type": "curtain"},
    "fechar": {"state": "off", "device_type": "curtain"},
    "feche": {"state": "off", "device_type": "curtain"},
}

# ---------------------------------------------------------------------------
# Agent rules
# ---------------------------------------------------------------------------

AGENT_RULES = {
    "pipeline": {
        "sequence": ["Receber comando", "Interpretar", "Validar dispositivo", "Executar", "Confirmar"],
        "enforce": True,
        "rollback_on_failure": True,
    },
    "token_economy": {
        "prefer_local_llm": True,
        "ollama_url": LLM_CONFIG.get("base_url", "http://192.168.15.2:11434"),
        "cache_results": True,
    },
    "validation": {
        "required_before_delivery": True,
        "never_assume_success": True,
    },
    "communication": {
        "use_bus": True,
        "log_all_actions": True,
    },
    "home_specific": {
        "confirm_destructive_actions": True,  # ex.: destrancar porta
        "log_security_events": True,          # câmeras, fechaduras
        "max_retry_on_failure": 3,
        "timeout_seconds": 15,
    },
}


# ---------------------------------------------------------------------------
# Google Assistant Agent
# ---------------------------------------------------------------------------

class GoogleAssistantAgent:
    """
    Agente especializado em automação residencial via Google Assistant/Home.

    Características:
    - Controle de dispositivos smart home (Google Home ecossistema)
    - Interpretação de comandos em linguagem natural via LLM
    - Cenas e rotinas (schedule / trigger)
    - Publicação de eventos no Communication Bus
    - Memória de decisões para aprendizado
    """

    def __init__(self):
        self.agent_type = AGENT_NAME
        self.device_manager = DeviceManager()
        self._google_token: Optional[str] = os.getenv("GOOGLE_HOME_TOKEN")
        self._google_project_id: Optional[str] = os.getenv("GOOGLE_SDM_PROJECT_ID")
        self._ollama_url = LLM_CONFIG.get("base_url", "http://192.168.15.2:11434")
        self._ollama_model = LLM_CONFIG.get("model", "qwen2.5-coder:1.5b")
        try:
            self._memory = get_agent_memory(AGENT_NAME) if _MEMORY_OK else None
        except Exception:
            self._memory = None
        self._bus = get_communication_bus() if _BUS_OK else None
        self._initialized = False

        # Google Home adapter (apenas para discovery/sync de inventário, não para controle)
        self._ghome: Optional[GoogleHomeAdapter] = None
        if _GHOME_OK:
            self._ghome = get_google_home_adapter()
            logger.info("🏠 Google Home adapter configurado (credentials=%s)", self._ghome.has_google_auth)

        # Home Assistant — backend ÚNICO para controle de dispositivos
        self._ha: Optional[HomeAssistantAdapter] = None
        if _HA_OK:
            ha_token = os.getenv("HOME_ASSISTANT_TOKEN", "")
            if ha_token:
                self._ha = HomeAssistantAdapter()
                logger.info("🏠 Home Assistant adapter configurado (url=%s)",
                            os.getenv("HOME_ASSISTANT_URL", "http://192.168.15.2:8123"))
            else:
                logger.warning("⚠️  HOME_ASSISTANT_TOKEN não definido — controle de dispositivos indisponível")

        logger.info("🏠 GoogleAssistantAgent criado (devices: %d, ha=%s, ghome=%s)",
                 len(self.device_manager.devices), self._ha is not None,
                 self._ghome is not None)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Google Assistant Home Agent"

    @property
    def capabilities(self) -> List[str]:
        return [
            "Controle de luzes (ligar/desligar, brilho, temperatura de cor)",
            "Controle de tomadas/plugs inteligentes",
            "Termostatos e ar-condicionado",
            "Fechaduras inteligentes (trancar/destrancar)",
            "Câmeras e doorbells (snapshot, stream)",
            "Speakers e TVs (volume, reproduzir, pausar)",
            "Ventiladores e cortinas",
            "Cenas (ex.: 'Boa noite', 'Filme', 'Saindo de casa')",
            "Rotinas agendadas (cron / trigger por evento)",
            "Comandos por linguagem natural (PT-BR)",
            "Integração Google Home / Smart Device Management API",
            "Histórico de comandos e estados",
        ]

    # ------------------------------------------------------------------
    # Init / Sync
    # ------------------------------------------------------------------

    async def initialize(self):
        """Inicializa o agente e sincroniza dispositivos."""
        if self._initialized:
            return
        # Descoberta via Google Home adapter (SDM + local)
        if self._ghome:
            await self.sync_devices_from_google()
        elif self._google_token and self._google_project_id:
            await self._sync_sdm_legacy()
        self._initialized = True
        logger.info("🏠 GoogleAssistantAgent inicializado — %d dispositivos",
                     len(self.device_manager.devices))

    async def sync_devices_from_google(self) -> List[Device]:
        """
        Sincroniza dispositivos dinamicamente:
        1. Google SDM API (Nest) com token auto-refresh
        2. Descoberta local via mDNS/Zeroconf (todos na LAN)
        3. Google Cast devices (speakers, displays, Chromecasts)
        """
        if not self._ghome:
            logger.warning("Google Home adapter não disponível")
            return await self._sync_sdm_legacy()

        try:
            # Se temos credenciais, renova token antes
            if self._ghome.has_google_auth:
                token = await self._ghome.token_manager.get_access_token()
                if token:
                    self._google_token = token

            raw_devices = await self._ghome.discover_all_devices()
            synced: List[Device] = []

            for raw in raw_devices:
                dev = self._raw_to_device(raw)
                if dev:
                    self.device_manager.register_device(dev)
                    synced.append(dev)

            self._bus_publish("sync_complete", {
                "devices_synced": len(synced),
                "timestamp": datetime.utcnow().isoformat(),
                "sources": {
                    "sdm": sum(1 for r in raw_devices if r.get("category") == "google_nest"),
                    "cast": sum(1 for r in raw_devices if r.get("category") == "google_cast"),
                    "local": sum(1 for r in raw_devices if r.get("category") not in ("google_nest", "google_cast")),
                },
            })
            logger.info("✅ Sincronizados %d dispositivos", len(synced))
            return synced

        except Exception as exc:
            logger.error("Erro ao sincronizar dispositivos: %s", exc)
            self._bus_publish("sync_error", {"error": str(exc)})
            return []

    def _raw_to_device(self, raw: Dict[str, Any]) -> Optional[Device]:
        """Converte dispositivo descoberto (qualquer fonte) para modelo Device."""
        name = raw.get("name", "Unknown")
        category = raw.get("category", "unknown")
        host = raw.get("host")

        # Gerar ID único baseado no host ou nome
        dev_id = raw.get("google_device_id")
        if not dev_id:
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            dev_id = f"{slug}_{host}" if host else slug

        # Mapear tipo
        type_map = {
            "google_nest": self._infer_nest_type(raw),
            "google_cast": self._infer_cast_type(raw),
            "homekit": DeviceType.CUSTOM,
            "airplay": DeviceType.SPEAKER,
            "tplink": DeviceType.PLUG,
            "esphome": DeviceType.CUSTOM,
            "http_device": DeviceType.CUSTOM,
        }
        device_type = type_map.get(category, DeviceType.CUSTOM)
        if isinstance(device_type, str):
            try:
                device_type = DeviceType(device_type)
            except ValueError:
                device_type = DeviceType.CUSTOM

        # Estado
        state_str = raw.get("state", "unknown")
        try:
            state = DeviceState(state_str)
        except ValueError:
            state = DeviceState.UNKNOWN

        room = raw.get("room", "default")

        # Atributos base
        attrs: Dict[str, Any] = {
            "host": host,
            "port": raw.get("port"),
            "model": raw.get("model"),
            "manufacturer": raw.get("manufacturer"),
            "category": category,
            "properties": raw.get("properties", {}),
        }

        # ...expurgado: suporte Tuya removido...

        return Device(
            id=dev_id,
            name=name,
            device_type=device_type,
            room=room,
            state=state,
            brightness=raw.get("brightness"),
            temperature=raw.get("temperature"),
            attributes=attrs,
            google_device_id=raw.get("google_device_id"),
        )

    def _infer_nest_type(self, raw: Dict[str, Any]) -> DeviceType:
        """Infere DeviceType para SDM/Nest."""
        dtype = raw.get("device_type", "custom")
        try:
            return DeviceType(dtype)
        except ValueError:
            return DeviceType.CUSTOM

    def _infer_cast_type(self, raw: Dict[str, Any]) -> DeviceType:
        """Infere DeviceType para Google Cast."""
        cast_type = raw.get("cast_type", "cast")
        cast_map = {
            "speaker": DeviceType.SPEAKER,
            "display": DeviceType.TV,
            "chromecast": DeviceType.TV,
            "tv": DeviceType.TV,
            "cast": DeviceType.SPEAKER,
        }
        return cast_map.get(cast_type, DeviceType.SPEAKER)

    # ...expurgado: suporte Tuya removido...

    async def _sync_sdm_legacy(self) -> List[Device]:
        """Sync legado via SDM direto (sem Google Home adapter)."""
        if not self._google_token or not self._google_project_id:
            logger.warning("Google Home token ou project ID não configurados")
            return []

        url = f"{GOOGLE_SDM_API_BASE}/enterprises/{self._google_project_id}/devices"
        headers = {"Authorization": f"Bearer {self._google_token}"}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            synced: List[Device] = []
            for raw_device in data.get("devices", []):
                dev = self._parse_google_device(raw_device)
                if dev:
                    self.device_manager.register_device(dev)
                    synced.append(dev)

            self._bus_publish("sync_complete", {
                "devices_synced": len(synced),
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.info("Sincronizados %d dispositivos do Google Home", len(synced))
            return synced

        except Exception as exc:
            logger.error("Erro ao sincronizar Google Home: %s", exc)
            self._bus_publish("sync_error", {"error": str(exc)})
            return []

    def _parse_google_device(self, raw: Dict[str, Any]) -> Optional[Device]:
        """Converte device da API Google SDM para modelo interno."""
        device_name = raw.get("name", "")
        device_type_str = raw.get("type", "")
        traits = raw.get("traits", {})
        parent_relations = raw.get("parentRelations", [])

        room = "default"
        if parent_relations:
            room_name = parent_relations[0].get("displayName", "default")
            room = room_name

        display_name = traits.get("sdm.devices.traits.Info", {}).get("customName", device_name.split("/")[-1])
        device_type = SDM_TYPE_MAP.get(device_type_str, DeviceType.CUSTOM)

        # Extrair estado
        state = DeviceState.UNKNOWN
        brightness = None
        temperature = None

        if "sdm.devices.traits.OnOff" in traits:
            on = traits["sdm.devices.traits.OnOff"].get("on", False)
            state = DeviceState.ON if on else DeviceState.OFF

        if "sdm.devices.traits.Brightness" in traits:
            brightness = int(traits["sdm.devices.traits.Brightness"].get("brightness", 0))

        if "sdm.devices.traits.Temperature" in traits:
            temperature = traits["sdm.devices.traits.Temperature"].get("ambientTemperatureCelsius")

        return Device(
            id=device_name.split("/")[-1],
            name=display_name,
            device_type=device_type,
            room=room,
            state=state,
            brightness=brightness,
            temperature=temperature,
            google_device_id=device_name,
        )

    # ------------------------------------------------------------------
    # Natural Language Command Processing
    # ------------------------------------------------------------------

    async def process_command(self, command: str) -> Dict[str, Any]:
        """
        Processa um comando em linguagem natural delegando ao Home Assistant.
        O HA é o backend único — ele sabe encontrar e controlar os dispositivos.
        Ex.: 'Apagar as luzes da sala', 'Ligar ar-condicionado do quarto a 22 graus'
        """
        task_id = f"home_{uuid.uuid4().hex[:8]}"
        if _BUS_OK:
            log_task_start(AGENT_NAME, task_id, f"home_command: {command[:80]}")

        try:
            # Home Assistant é o backend obrigatório
            if not self._ha:
                error_msg = ("Home Assistant não configurado. "
                             "Defina HOME_ASSISTANT_URL e HOME_ASSISTANT_TOKEN.")
                logger.error(error_msg)
                if _BUS_OK:
                    log_error(AGENT_NAME, error_msg, command=command)
                return {"success": False, "error": error_msg, "command": command}

            result = await self._ha.execute_natural_command(command)

            if _BUS_OK:
                log_task_end(AGENT_NAME, task_id, result.get("success", False))
            self._bus_publish("command_executed", result)

            # Registrar na memória
            if self._memory and result.get("success"):
                try:
                    self._memory.record_decision(
                        agent_name=AGENT_NAME,
                        application="home_automation",
                        component=result.get("device", "unknown"),
                        error_type="",
                        error_message="",
                        decision_type="command",
                        decision=command,
                        confidence=0.9,
                        context={"result": result},
                    )
                except Exception:
                    pass

            return result

        except Exception as exc:
            logger.error("Erro ao processar comando '%s': %s", command, exc)
            if _BUS_OK:
                log_error(AGENT_NAME, str(exc), {"command": command})
            return {"success": False, "error": str(exc), "command": command}

    async def _interpret_command(self, command: str) -> Dict[str, Any]:
        """
        Usa LLM local para interpretar comando em linguagem natural.
        Retorna JSON com: action, target (dispositivo/room), params.
        """
        # Tentativa rápida com regras locais
        quick = self._quick_parse(command)
        if quick:
            return quick

        # Fallback: LLM
        prompt = f"""Interprete o comando de automação residencial abaixo e retorne APENAS JSON válido.

Comando: "{command}"

Retorne JSON com:
- "action": string (on, off, set_brightness, set_temperature, lock, unlock, open, close, set_volume, activate_scene)
- "target": string (nome do dispositivo ou cômodo)
- "device_type": string (light, switch, thermostat, lock, camera, speaker, tv, fan, plug, curtain, ac, vacuum)
- "params": object (brightness: 0-100, temperature: number, volume: 0-100, color: string, scene: string)
- "confidence": float 0-1

Responda APENAS com JSON, sem explicações."""

        try:
            if httpx is None:
                raise ImportError("httpx not available")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._ollama_url}/api/generate",
                    json={
                        "model": self._ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 200},
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("response", "")

            # Extrair JSON do texto
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)

        except Exception as exc:
            logger.warning("LLM interpretation falhou: %s — usando parse simples", exc)
            return self._quick_parse(command) or {}

    def _quick_parse(self, command: str) -> Optional[Dict[str, Any]]:
        """Parse rápido baseado em regras para comandos simples."""
        cmd_lower = command.lower().strip()

        action = None
        # Ordenar keywords por tamanho decrescente para que "desligar" case
        # antes de "ligar" (evita substring match).
        for keyword, mapping in sorted(COMMAND_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(keyword) + r'\b', cmd_lower):
                action = mapping.get("state") or mapping.get("action")
                break

        if not action:
            return None

        # Tentar encontrar o dispositivo pela menção
        def _strip_accents(s: str) -> str:
            return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()

        cmd_norm = _strip_accents(cmd_lower)
        # Remover palavras de ação do comando para isolar alvo
        action_words = set()
        for kw in COMMAND_MAP:
            action_words.update(kw.split())
        # Palavras auxiliares comuns em pt-BR
        noise = {"o", "a", "os", "as", "do", "da", "dos", "das", "de", "no", "na",
                 "nos", "nas", "um", "uma", "uns", "umas", "para", "por", "em",
                 "que", "meu", "minha", "todos", "todas", "por favor", "favor"}
        target_words = [w for w in cmd_norm.split() if w not in action_words and w not in noise and len(w) > 1]
        target_phrase = " ".join(target_words)

        target = None
        device_type = None
        best_score = 0

        for dev in self.device_manager.devices.values():
            dev_norm = _strip_accents(dev.name)

            # Match exato: nome completo do dispositivo no comando ou vice-versa
            if dev_norm in cmd_norm or cmd_norm in dev_norm:
                target = dev.name
                device_type = dev.device_type.value
                best_score = 100
                break

            # Match bidirecional: target_phrase parcial no nome ou vice-versa
            if target_phrase and (target_phrase in dev_norm or dev_norm in target_phrase):
                target = dev.name
                device_type = dev.device_type.value
                best_score = 90
                break

            # Match por qualquer palavra significativa do target_phrase no nome
            if target_phrase:
                words_match = sum(1 for w in target_words if w in dev_norm)
                if words_match > best_score:
                    best_score = words_match
                    target = dev.name
                    device_type = dev.device_type.value

            # Match por palavra individual do nome no comando
            dev_words = [w for w in dev_norm.split() if len(w) > 2]
            for dw in dev_words:
                if dw in cmd_norm and len(dw) > best_score:
                    best_score = len(dw)
                    target = dev.name
                    device_type = dev.device_type.value

        # Tentar encontrar por room
        if not target:
            for room in self.device_manager.list_rooms():
                if _strip_accents(room) in cmd_norm:
                    target = room
                    break

        # Extrair parâmetros numéricos
        params: Dict[str, Any] = {}
        numbers = re.findall(r"(\d+)", cmd_lower)
        if numbers:
            val = int(numbers[-1])
            if "grau" in cmd_lower or "temperatura" in cmd_lower or "°" in cmd_lower:
                params["temperature"] = val
                action = "set_temperature" if action in ("on", "off") else action
            elif "brilho" in cmd_lower or "%" in cmd_lower:
                params["brightness"] = min(val, 100)
                action = "set_brightness" if action in ("on", "off") else action
            elif "volume" in cmd_lower:
                params["volume"] = min(val, 100)
                action = "set_volume" if action in ("on", "off") else action

        return {
            "action": action,
            "target": target or "desconhecido",
            "device_type": device_type,
            "params": params,
            "confidence": 0.7 if target else 0.4,
        }

    @staticmethod
    def _norm(text: str) -> str:
        """Remove acentos e normaliza texto para comparação."""
        nfkd = unicodedata.normalize("NFKD", text.lower())
        return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()

    def _resolve_devices(self, parsed: Dict[str, Any]) -> List[Device]:
        """Resolve quais dispositivos afetados pelo comando."""
        target = self._norm(parsed.get("target") or "")
        dtype_str = parsed.get("device_type")

        if not target:
            logger.debug("_resolve_devices: target vazio, parsed=%s", parsed)
            return []

        # Match exato por nome (normalizado)
        for dev in self.device_manager.devices.values():
            if self._norm(dev.name) == target or dev.id.lower() == target:
                return [dev]

        # Match por room (normalizado)
        room_devices = [d for d in self.device_manager.devices.values() if self._norm(d.room) == target]
        if room_devices:
            if dtype_str:
                try:
                    dtype = DeviceType(dtype_str)
                    filtered = [d for d in room_devices if d.device_type == dtype]
                    if filtered:
                        return filtered
                except ValueError:
                    pass
            return room_devices

        # Match parcial por nome (normalizado)
        for dev in self.device_manager.devices.values():
            dev_norm = self._norm(dev.name)
            if target in dev_norm or dev_norm in target:
                return [dev]

        # Match parcial por room
        for dev in self.device_manager.devices.values():
            room_norm = self._norm(dev.room)
            if target in room_norm or room_norm in target:
                return [dev]

        logger.debug("_resolve_devices: nenhum match para %r — inventário: %s",
                     target,
                     [f"{d.name}({d.room})" for d in self.device_manager.devices.values()])
        return []

    async def _execute_action(self, device: Device, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Executa ação em um dispositivo com cadeia de fallback.

                Ordem de tentativas:
                    1. Google SDM API (Nest) — se tem google_device_id
                    2. Google Home API — para dispositivos vinculados (Tuya/Smart Life, etc.)
                    3. Fallback: atualização de estado local somente
        """
        action = parsed.get("action", "")
        params = parsed.get("params", {})

        # Determinar backend Google SDM
        has_google_sdm = device.google_device_id and self._google_token
        has_google_home = self._ghome is not None

        async def _send_to_backend(act: str, prm: Dict) -> tuple:
            """Tenta enviar comando ao backend real. Retorna (ok, error_msg)."""
            # 1) Google SDM (Nest devices)
            if has_google_sdm:
                try:
                    await self._send_google_command(device, act, prm)
                    return True, ""
                except Exception as e:
                    logger.warning("SDM falhou para %s: %s — tentando Google Home API", device.name, e)

            # 2) Google Home API (qualquer dispositivo vinculado ao Google Home)
            if has_google_home:
                try:
                    result = await self._send_google_home_command(device, act, prm)
                    if result.get("success"):
                        return True, ""
                    err = result.get("error", "Google Home API falhou")
                    logger.warning("Google Home API falhou para %s: %s", device.name, err)
                    return False, err
                except Exception as e:
                    logger.warning("Google Home API exception para %s: %s", device.name, e)
                    return False, str(e)

            # Nenhum backend externo — atualizar apenas estado local
            logger.info("Sem backend externo para %s — atualização de estado local apenas", device.name)
            return True, ""

        try:
            # Ações que alteram estado
            if action in ("on", "off"):
                new_state = DeviceState.ON if action == "on" else DeviceState.OFF

                backend_ok, backend_error = await _send_to_backend(action, params)

                # Só atualizar estado local se backend confirmou
                if backend_ok:
                    self.device_manager.set_device_state(device.id, new_state)

                return {
                    "success": backend_ok,
                    "device": device.name,
                    "action": action,
                    "new_state": new_state.value if backend_ok else device.state.value if hasattr(device.state, 'value') else str(device.state),
                    **(({"error": backend_error}) if not backend_ok else {}),
                }

            elif action == "set_brightness":
                brightness = params.get("brightness", 50)
                backend_ok, backend_error = await _send_to_backend(action, {"brightness": brightness})
                if backend_ok:
                    self.device_manager.set_device_state(
                        device.id, DeviceState.ON, brightness=brightness
                    )
                return {"success": backend_ok, "device": device.name, "action": action, "brightness": brightness, **(({"error": backend_error}) if not backend_ok else {})}

            elif action == "set_temperature":
                temp = params.get("temperature", 22)
                backend_ok, backend_error = await _send_to_backend(action, {"temperature": temp})
                if backend_ok:
                    self.device_manager.set_device_state(
                        device.id, DeviceState.ON, target_temperature=temp
                    )
                return {"success": backend_ok, "device": device.name, "action": action, "temperature": temp, **(({"error": backend_error}) if not backend_ok else {})}

            elif action == "set_volume":
                vol = params.get("volume", 50)
                backend_ok, backend_error = await _send_to_backend(action, {"volume": vol})
                if backend_ok:
                    self.device_manager.set_device_state(
                        device.id, DeviceState.ON, volume=vol
                    )
                return {"success": backend_ok, "device": device.name, "action": action, "volume": vol, **(({"error": backend_error}) if not backend_ok else {})}

            elif action in ("lock", "unlock"):
                new_state = DeviceState.ON if action == "lock" else DeviceState.OFF
                backend_ok, backend_error = await _send_to_backend(action, {})
                if backend_ok:
                    self.device_manager.set_device_state(device.id, new_state)
                return {"success": backend_ok, "device": device.name, "action": action, **(({"error": backend_error}) if not backend_ok else {})}

            elif action in ("open", "close"):
                new_state = DeviceState.ON if action == "open" else DeviceState.OFF
                backend_ok, backend_error = await _send_to_backend(action, {})
                if backend_ok:
                    self.device_manager.set_device_state(device.id, new_state)
                return {"success": backend_ok, "device": device.name, "action": action, **(({"error": backend_error}) if not backend_ok else {})}

            elif action == "activate_scene":
                scene_name = params.get("scene", "")
                for s in self.device_manager.scenes.values():
                    if s.name.lower() == scene_name.lower():
                        results = self.device_manager.activate_scene(s.id)
                        return {"success": True, "scene": s.name, "results": results}
                return {"success": False, "error": f"Cena '{scene_name}' não encontrada"}

            else:
                return {"success": False, "device": device.name, "error": f"Ação desconhecida: {action}"}

        except Exception as exc:
            logger.error("Erro ao executar %s em %s: %s", action, device.name, exc)
            return {"success": False, "device": device.name, "error": str(exc)}

    async def _send_google_home_command(self, device: Device, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Envia comando via Google Home API."""
        if not self._ghome:
            return {"success": False, "error": "Google Home adapter não disponível"}

        result = await self._ghome.send_google_home_command(device.name, action, params)
        if result.get("success"):
            logger.info("🏠 Google Home OK: %s → %s", action, device.name)
        else:
            logger.warning("🏠 Google Home falhou: %s → %s: %s", action, device.name, result.get("error"))
        return result

    async def _send_google_command(self, device: Device, action: str, params: Dict[str, Any]):
        """Envia comando para Google SDM API (com auto-refresh de token)."""
        if not device.google_device_id:
            return

        # Usar adapter se disponível (auto token refresh)
        if self._ghome:
            ok = await self._ghome.send_sdm_command(device.google_device_id, action, params)
            if ok:
                logger.info("Google SDM command OK via adapter: %s → %s", action, device.name)
            else:
                logger.warning("Google SDM command falhou via adapter: %s → %s", action, device.name)
            return

        # Fallback legado
        if not self._google_token:
            return

        # Mapeamento de ações para traits SDM
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
            logger.warning("Ação '%s' não mapeada para SDM commands", action)
            return

        command_name, command_params = trait_commands[action]
        url = f"{GOOGLE_SDM_API_BASE}/{device.google_device_id}:executeCommand"
        headers = {"Authorization": f"Bearer {self._google_token}"}
        body = {"command": command_name, "params": command_params}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                logger.info("Google SDM command OK: %s → %s", action, device.name)
        except Exception as exc:
            logger.error("Google SDM command falhou: %s → %s: %s", action, device.name, exc)

    # ------------------------------------------------------------------
    # Scene & Routine helpers
    # ------------------------------------------------------------------

    async def create_scene(self, name: str, actions: List[Dict[str, Any]]) -> Scene:
        scene = Scene(id=f"scene_{uuid.uuid4().hex[:8]}", name=name, actions=actions)
        self.device_manager.create_scene(scene)
        self._bus_publish("scene_created", {"scene": name, "actions_count": len(actions)})
        return scene

    async def activate_scene(self, scene_id: str) -> List[Dict[str, Any]]:
        results = self.device_manager.activate_scene(scene_id)
        self._bus_publish("scene_activated", {"scene_id": scene_id, "results": results})
        return results

    async def create_routine(self, name: str, trigger: str,
                             actions: List[Dict[str, Any]]) -> Routine:
        routine = Routine(
            id=f"routine_{uuid.uuid4().hex[:8]}",
            name=name,
            trigger=trigger,
            actions=actions,
        )
        self.device_manager.create_routine(routine)
        self._bus_publish("routine_created", {"routine": name, "trigger": trigger})
        return routine

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Retorna status geral do sistema de automação."""
        stats = self.device_manager.stats()
        stats["agent"] = self.name
        stats["google_connected"] = bool(self._google_token and self._google_project_id)
        stats["google_home_adapter"] = bool(self._ghome)
        stats["google_home_api"] = bool(self._ghome and self._ghome.home_controller.is_available)
        stats["google_token_refresh"] = bool(self._ghome and self._ghome.has_google_auth)
        stats["ha_connected"] = bool(self._ha)
        stats["capabilities"] = self.capabilities
        return stats

    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        dev = self.device_manager.get_device(device_id)
        return dev.to_dict() if dev else None

    def get_room_status(self, room: str) -> List[Dict[str, Any]]:
        devices = self.device_manager.list_devices(room=room)
        return [d.to_dict() for d in devices]

    def get_command_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.device_manager.command_history[-limit:]

    # ------------------------------------------------------------------
    # Bus publish helper
    # ------------------------------------------------------------------

    def _bus_publish(self, event_type: str, data: Dict[str, Any]):
        if self._bus:
            try:
                self._bus.publish(
                    MessageType.REQUEST,
                    AGENT_NAME,
                    "broadcast",
                    {"event": event_type, **data},
                    metadata={"agent": AGENT_NAME},
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_agent_instance: Optional[GoogleAssistantAgent] = None


def get_google_assistant_agent() -> GoogleAssistantAgent:
    """Retorna instância singleton do Google Assistant Agent."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GoogleAssistantAgent()
    return _agent_instance
