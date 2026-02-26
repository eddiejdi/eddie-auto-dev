"""
Home Assistant Adapter para Eddie Auto-Dev.

Permite controlar dispositivos smart home via Home Assistant REST API.
Substitui a integração direta com SDM (que requer $5 + só suporta Nest).

Uso:
    from specialized_agents.home_automation.ha_adapter import HomeAssistantAdapter

    ha = HomeAssistantAdapter("http://192.168.15.2:8123", "YOUR_HA_TOKEN")
    devices = await ha.get_devices()
    await ha.call_service("switch", "turn_on", {"entity_id": "switch.ventilador_escritorio"})
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

logger = logging.getLogger(__name__)

HA_URL = os.getenv("HOME_ASSISTANT_URL", "http://192.168.15.2:8123")
HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")


class HomeAssistantAdapter:
    """Adapter para controlar dispositivos via Home Assistant REST API."""

    # Connect timeout agressivo (3s) para fast-fail quando HA offline.
    # Read timeout mais generoso (10s) para comandos que demoram.
    _TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=3.0) if httpx else None
    _ha_reachable: Optional[bool] = None  # cache de health
    _ha_reachable_ts: float = 0.0        # timestamp do último check

    def __init__(self, url: str = "", token: str = ""):
        self.url = (url or HA_URL).rstrip("/")
        self.token = token or HA_TOKEN
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Any:
        """Faz request à API do Home Assistant."""
        if httpx is None:
            raise ImportError("httpx não disponível — pip install httpx")
        # Fast-fail: se HA ficou unreachable nos últimos 60s, nem tenta
        import time as _time
        now = _time.monotonic()
        if self._ha_reachable is False and (now - self._ha_reachable_ts) < 60:
            raise ConnectionError("HA unreachable (cached, retry in <60s)")
        url = f"{self.url}/api{path}"
        try:
            async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
                if method == "GET":
                    resp = await client.get(url, headers=self._headers)
                elif method == "POST":
                    resp = await client.post(url, headers=self._headers, json=data or {})
                else:
                    raise ValueError(f"Método não suportado: {method}")
                resp.raise_for_status()
                HomeAssistantAdapter._ha_reachable = True
                HomeAssistantAdapter._ha_reachable_ts = now
                return resp.json() if resp.content else {}
        except (httpx.ConnectError, httpx.ConnectTimeout, ConnectionError, OSError) as exc:
            HomeAssistantAdapter._ha_reachable = False
            HomeAssistantAdapter._ha_reachable_ts = now
            raise ConnectionError(f"HA unreachable: {exc}") from exc

    # ------------------------------------------------------------------
    # Dispositivos
    # ------------------------------------------------------------------

    async def get_states(self) -> List[Dict]:
        """Lista todos os estados (entidades) do HA."""
        return await self._request("GET", "/states")

    async def get_devices(self, domain_filter: Optional[str] = None) -> List[Dict]:
        """Lista dispositivos filtrados por domínio (switch, light, fan, etc.)."""
        states = await self.get_states()
        devices = []
        for s in states:
            entity_id = s.get("entity_id", "")
            # Filtrar entidades internas do HA
            if entity_id.startswith(("automation.", "script.", "scene.", "zone.",
                                      "person.", "sun.", "weather.", "input_",
                                      "persistent_notification.", "update.")):
                continue
            if domain_filter and not entity_id.startswith(f"{domain_filter}."):
                continue
            devices.append({
                "entity_id": entity_id,
                "name": s.get("attributes", {}).get("friendly_name", entity_id),
                "state": s.get("state", "unknown"),
                "domain": entity_id.split(".")[0],
                "attributes": s.get("attributes", {}),
            })
        return devices

    async def get_entity_state(self, entity_id: str) -> Dict:
        """Obtém estado de uma entidade específica."""
        return await self._request("GET", f"/states/{entity_id}")

    # ------------------------------------------------------------------
    # Controle
    # ------------------------------------------------------------------

    async def call_service(self, domain: str, service: str, data: Dict) -> Dict:
        """
        Chama um serviço do HA.

        Exemplos:
            call_service("switch", "turn_on", {"entity_id": "switch.ventilador"})
            call_service("light", "turn_on", {"entity_id": "light.sala", "brightness": 200})
            call_service("fan", "turn_off", {"entity_id": "fan.quarto"})
            call_service("climate", "set_temperature", {"entity_id": "climate.ac", "temperature": 22})
        """
        path = f"/services/{domain}/{service}"
        logger.info("HA call_service: %s/%s → %s", domain, service, data)
        result = await self._request("POST", path, data)
        return {"success": True, "result": result}

    async def turn_on(self, entity_id: str, **kwargs) -> Dict:
        """Liga um dispositivo."""
        domain = entity_id.split(".")[0]
        data = {"entity_id": entity_id, **kwargs}
        return await self.call_service(domain, "turn_on", data)

    async def turn_off(self, entity_id: str) -> Dict:
        """Desliga um dispositivo."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "turn_off", {"entity_id": entity_id})

    async def toggle(self, entity_id: str) -> Dict:
        """Alterna estado de um dispositivo."""
        domain = entity_id.split(".")[0]
        return await self.call_service(domain, "toggle", {"entity_id": entity_id})

    # ------------------------------------------------------------------
    # Matching por nome (fuzzy)
    # ------------------------------------------------------------------

    async def find_device_by_name(self, name: str) -> Optional[Dict]:
        """Encontra dispositivo por nome (fuzzy match)."""
        devices = await self.get_devices()
        name_lower = name.lower().strip()

        # Exact match
        for d in devices:
            if d["name"].lower() == name_lower or d["entity_id"].lower() == name_lower:
                return d

        # Partial match (name in device name or device name in name)
        for d in devices:
            d_name = d["name"].lower()
            d_eid = d["entity_id"].lower()
            if name_lower in d_name or name_lower in d_eid:
                return d
            if d_name in name_lower or d_eid.split(".")[-1] in name_lower:
                return d

        # Word match — any word from query matches device name
        words = name_lower.split()
        best_match = None
        best_score = 0
        for d in devices:
            d_name = d["name"].lower()
            d_eid = d["entity_id"].split(".")[-1].replace("_", " ")
            combined = f"{d_name} {d_eid}"
            score = sum(1 for w in words if w in combined and len(w) > 2)
            if score > best_score:
                best_score = score
                best_match = d

        if best_match and best_score > 0:
            return best_match

        return None

    # ------------------------------------------------------------------
    # Comando em linguagem natural
    # ------------------------------------------------------------------

    async def execute_natural_command(self, command: str) -> Dict:
        """
        Processa comando em linguagem natural e executa no HA.
        Ex: "ligar ventilador do escritório", "desligar luz da sala"
        """
        import re as _re
        cmd_lower = command.lower().strip()

        # Determinar ação — primeiro detectar pedidos de porcentagem/velocidade
        action = None
        pct_value = None

        # Expressões explícitas de porcentagem: "50%", "50 por cento", "50 porcento"
        m = _re.search(r"(\d{1,3})\s*(?:%|por\s*cento|porcento)", cmd_lower)
        if m:
            try:
                pct_value = int(m.group(1))
                pct_value = max(0, min(100, pct_value))
                action = "set_percentage"
                cmd_lower = cmd_lower[: m.start()] + cmd_lower[m.end() :]
            except Exception:
                pct_value = None

        # Termos qualitativos: baixa/média/alta/max
        if not action:
            qualitative = {
                "baixa": 25,
                "baixo": 25,
                "média": 50,
                "media": 50,
                "médio": 50,
                "medio": 50,
                "alta": 75,
                "alto": 75,
                "máxima": 100,
                "maxima": 100,
                "máximo": 100,
                "maximo": 100,
                "mínima": 10,
                "minima": 10,
            }
            for word, val in qualitative.items():
                if _re.search(r'\b' + _re.escape(word) + r'\b', cmd_lower):
                    pct_value = val
                    action = "set_percentage"
                    cmd_lower = _re.sub(r'\b' + _re.escape(word) + r'\b', '', cmd_lower).strip()
                    break

        # Se não for set_percentage, detectar ligar/desligar/toggle
        if not action:
            # OFF actions first (desligar contains ligar)
            for word in ["desligar", "desligue", "desliga", "desativar", "desative", "apagar", "apague"]:
                if _re.search(r'\b' + _re.escape(word) + r'\b', cmd_lower):
                    action = "turn_off"
                    cmd_lower = _re.sub(r'\b' + _re.escape(word) + r'\b', '', cmd_lower).strip()
                    break
            # ON actions
            if not action:
                for word in ["ligar", "ligue", "liga", "ativar", "ative", "acender", "acenda"]:
                    if _re.search(r'\b' + _re.escape(word) + r'\b', cmd_lower):
                        action = "turn_on"
                        cmd_lower = _re.sub(r'\b' + _re.escape(word) + r'\b', '', cmd_lower).strip()
                        break
            if not action:
                for word in ["alternar", "toggle"]:
                    if word in cmd_lower:
                        action = "toggle"
                        cmd_lower = cmd_lower.replace(word, "").strip()
                        break

        if not action:
            return {"success": False, "error": f"Ação não reconhecida no comando: {command}"}

        # Limpar preposições/artigos (longer patterns first to avoid partial matches)
        import re
        # Remove common PT-BR prepositions, articles, and contractions
        cmd_lower = re.sub(r'\b(dos|das|do|da|de|nos|nas|no|na|os|as|um|uma|o|a)\b', ' ', cmd_lower)
        target_name = " ".join(cmd_lower.split())  # normalizar espaços

        # Encontrar dispositivo
        device = await self.find_device_by_name(target_name)
        if not device:
            return {
                "success": False,
                "error": f"Dispositivo '{target_name}' não encontrado no Home Assistant",
                "command": command,
            }

        # Executar
        entity_id = device["entity_id"]
        if action == "turn_on":
            result = await self.turn_on(entity_id)
        elif action == "turn_off":
            result = await self.turn_off(entity_id)
        elif action == "set_percentage":
            # Prefer call to fan.set_percentage; if entity domain isn't fan, attempt domain-specific service
            domain = entity_id.split(".")[0]
            params = {"entity_id": entity_id, "percentage": pct_value}
            try:
                if domain == "fan":
                    result = await self.call_service("fan", "set_percentage", params)
                else:
                    # fallback: try to call set_percentage on the domain
                    result = await self.call_service(domain, "set_percentage", params)
            except Exception as exc:
                return {"success": False, "error": f"Falha ao setar porcentagem: {exc}"}
        else:
            result = await self.toggle(entity_id)

        return {
            "success": True,
            "command": command,
            "action": action,
            "device": device["name"],
            "entity_id": entity_id,
            "previous_state": device["state"],
            "result": result,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> Dict:
        """Verifica conectividade com HA."""
        try:
            result = await self._request("GET", "/")
            return {"healthy": True, "message": result.get("message", "ok")}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
