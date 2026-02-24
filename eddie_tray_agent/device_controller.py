"""
Device Controller — Controla dispositivos do grupo "escritório".

Usa a API do Eddie (specialized_agents) para enviar comandos.
Ao bloquear a tela:
  1. Salva snapshot do estado de cada dispositivo
  2. Desliga todos imediatamente, exceto aquário (delay de 10s)
Ao desbloquear:
  3. Restaura cada dispositivo ao estado salvo
"""
import asyncio
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from eddie_tray_agent.config import (
    AQUARIUM_DEVICE_NAME,
    AQUARIUM_OFF_DELAY_SECONDS,
    EDDIE_API_URL,
    FAN_DEVICE_NAME,
    OFFICE_GROUP,
)
from eddie_tray_agent.history_db import (
    get_last_fan_state,
    get_last_snapshots,
    log_fan_state,
    log_screen_event,
    save_device_snapshot,
)

logger = logging.getLogger(__name__)

# Comunicação com Bus (lazy — importado sob demanda para evitar cadeia pesada)
_BUS_OK = None  # None = ainda não tentou; True/False = resultado
_bus_mod = None

def _ensure_bus():
    """Import lazy do bus. Só executa 1x."""
    global _BUS_OK, _bus_mod
    if _BUS_OK is not None:
        return _BUS_OK
    try:
        import importlib
        _bus_mod = importlib.import_module("specialized_agents.agent_communication_bus")
        _BUS_OK = True
    except Exception:
        _BUS_OK = False
    return _BUS_OK

AGENT_NAME = "eddie_tray"


class DeviceController:
    """Controla dispositivos via API do Eddie."""

    def __init__(self):
        self._api = EDDIE_API_URL.rstrip("/")
        self._bus = None  # inicializado lazy em _get_bus()
        self._lock = threading.Lock()

    def _get_bus(self):
        """Retorna bus (lazy init)."""
        if self._bus is None and _ensure_bus():
            self._bus = _bus_mod.get_communication_bus()
        return self._bus

    def _log_task_start(self, agent, task_id, desc):
        if _ensure_bus():
            _bus_mod.log_task_start(agent, task_id, desc)

    def _log_task_end(self, agent, task_id, success):
        if _ensure_bus():
            _bus_mod.log_task_end(agent, task_id, success)

    # ──────────────────────────────────────────────────────
    # API helpers
    # ──────────────────────────────────────────────────────

    async def _api_get(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._api}{path}")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("API GET %s falhou: %s", path, exc)
            return None

    async def _api_post(self, path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(f"{self._api}{path}", json=body)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("API POST %s falhou: %s", path, exc)
            return None

    async def send_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Envia comando em linguagem natural para o agente de home automation."""
        return await self._api_post("/home/command", {"command": command})

    # ──────────────────────────────────────────────────────
    # Fetch dispositivos do escritório
    # ──────────────────────────────────────────────────────

    async def get_office_devices(self) -> List[Dict[str, Any]]:
        """Busca dispositivos do grupo escritório via API."""
        result = await self._api_get(f"/home/rooms/{OFFICE_GROUP}")
        # A API retorna {"room": "...", "devices": [...], "count": N}
        if result and isinstance(result, dict):
            devs = result.get("devices", [])
            if devs:
                return devs
        elif result and isinstance(result, list):
            return result
        # Fallback: buscar todos e filtrar (normalizar acentos)
        all_devs = await self._api_get("/home/devices")
        if all_devs and isinstance(all_devs, list):
            return [
                d for d in all_devs
                if self._normalize(d.get("room", "")) == self._normalize(OFFICE_GROUP)
            ]
        return []

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove acentos e converte para minúscula para comparação."""
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

    # ──────────────────────────────────────────────────────
    # Menu: liga/desliga direto (sem snapshot)
    # ──────────────────────────────────────────────────────

    async def office_on(self) -> None:
        """Liga todos os dispositivos do escritório (ação direta do menu)."""
        devices = await self.get_office_devices()
        if not devices:
            logger.info("💡 Nenhum dispositivo — enviando 'ligue tudo do escritório'")
            await self.send_command("ligue tudo do escritório")
            return
        for dev in devices:
            name = dev.get("name", "")
            if dev.get("state") != "on":
                logger.info("  💡 %s → on", name)
                await self.send_command(f"ligue {name}")
            else:
                logger.info("  ⏭️  %s já está on", name)

    async def office_off(self) -> None:
        """Desliga todos os dispositivos do escritório (ação direta do menu)."""
        devices = await self.get_office_devices()
        if not devices:
            logger.info("💡 Nenhum dispositivo — enviando 'desligue tudo do escritório'")
            await self.send_command("desligue tudo do escritório")
            return
        for dev in devices:
            name = dev.get("name", "")
            if dev.get("state") != "off":
                logger.info("  💡 %s → off", name)
                await self.send_command(f"desligue {name}")
            else:
                logger.info("  ⏭️  %s já está off", name)

    # ──────────────────────────────────────────────────────
    # Lock: desligar escritório
    # ──────────────────────────────────────────────────────

    async def on_screen_lock(self):
        """Chamado quando a tela é bloqueada."""
        task_id = f"tray_lock_{int(time.time())}"
        self._log_task_start(AGENT_NAME, task_id, "screen_lock_office_off")
        log_screen_event("lock")

        devices = await self.get_office_devices()
        if not devices:
            logger.warning("Nenhum dispositivo encontrado no escritório")
            # Fallback: enviar comando genérico
            await self.send_command(f"desligue tudo do {OFFICE_GROUP}")
            self._log_task_end(AGENT_NAME, task_id, True)
            return

        logger.info("🔒 Salvando estado de %d dispositivos e desligando", len(devices))

        aquarium_device = None
        for dev in devices:
            name = dev.get("name", "").lower()
            state = dev.get("state", "unknown")
            attrs = json.dumps({
                k: v for k, v in dev.items()
                if k not in ("id", "name", "room", "device_type")
            })

            # Salvar snapshot
            save_device_snapshot(OFFICE_GROUP, dev["name"], state, attrs)

            if AQUARIUM_DEVICE_NAME in name:
                aquarium_device = dev
                continue  # Tratar depois com delay

            # Desligar imediatamente
            if state != "off":
                cmd = f"desligue {dev['name']}"
                logger.info("  💡 %s → off", dev["name"])
                await self.send_command(cmd)

        # Aquário: delay de N segundos
        if aquarium_device and aquarium_device.get("state") != "off":
            logger.info("  🐠 Aquário: desligando em %ds...", AQUARIUM_OFF_DELAY_SECONDS)
            await asyncio.sleep(AQUARIUM_OFF_DELAY_SECONDS)
            await self.send_command(f"desligue {aquarium_device['name']}")
            logger.info("  🐠 Aquário desligado")

        self._bus_publish("office_locked", {"devices_off": len(devices)})
        self._log_task_end(AGENT_NAME, task_id, True)
        logger.info("🔒 Escritório desligado (%d dispositivos)", len(devices))

    # ──────────────────────────────────────────────────────
    # Unlock: restaurar escritório
    # ──────────────────────────────────────────────────────

    async def on_screen_unlock(self):
        """Chamado quando a tela é desbloqueada."""
        task_id = f"tray_unlock_{int(time.time())}"
        self._log_task_start(AGENT_NAME, task_id, "screen_unlock_office_on")
        log_screen_event("unlock")

        # Buscar snapshots salvos
        snapshots = get_last_snapshots(OFFICE_GROUP)
        if not snapshots:
            logger.info("🔓 Nenhum snapshot para restaurar, ligando tudo")
            await self.send_command(f"ligue tudo do {OFFICE_GROUP}")
            self._log_task_end(AGENT_NAME, task_id, True)
            return

        logger.info("🔓 Restaurando %d dispositivos do escritório", len(snapshots))
        restored = 0
        for snap in snapshots:
            name = snap["device_name"]
            prev_state = snap["state"]

            if prev_state == "off":
                logger.info("  ⏭️  %s estava off, mantendo off", name)
                continue

            # Restaurar estado
            cmd = f"ligue {name}"
            try:
                attrs = json.loads(snap.get("attributes", "{}"))
                # Restaurar brilho se era luz
                if attrs.get("brightness"):
                    cmd = f"ligue {name} com brilho {attrs['brightness']}"
                # Restaurar temperatura se era AC
                if attrs.get("target_temperature"):
                    cmd = f"ligue {name} a {attrs['target_temperature']} graus"
            except (json.JSONDecodeError, KeyError):
                pass

            logger.info("  ✅ %s → %s", name, prev_state)
            await self.send_command(cmd)
            restored += 1

        # Restaurar ventilador com estado registrado
        await self.restore_fan()

        self._bus_publish("office_unlocked", {"devices_restored": restored})
        self._log_task_end(AGENT_NAME, task_id, True)
        logger.info("🔓 Escritório restaurado (%d dispositivos)", restored)

    # ──────────────────────────────────────────────────────
    # Ventilador: restaurar estado
    # ──────────────────────────────────────────────────────

    async def restore_fan(self):
        """Restaura ventilador ao último estado registrado (quando ON)."""
        last = get_last_fan_state()
        if not last:
            logger.info("🌀 Sem estado anterior do ventilador")
            return

        speed = last.get("speed", 0)
        mode = last.get("mode", "")

        if speed > 0:
            cmd = f"ligue {FAN_DEVICE_NAME} velocidade {speed}"
            if mode:
                cmd += f" modo {mode}"
            logger.info("🌀 Restaurando ventilador: speed=%d mode=%s", speed, mode)
            await self.send_command(cmd)
        else:
            logger.info("🌀 Ventilador estava desligado, não restaurando")

    # ──────────────────────────────────────────────────────
    # Bus helper
    # ──────────────────────────────────────────────────────

    def _bus_publish(self, event_type: str, data: Dict[str, Any]):
        bus = self._get_bus()
        if bus and _ensure_bus():
            try:
                bus.publish(
                    _bus_mod.MessageType.REQUEST,
                    AGENT_NAME,
                    "broadcast",
                    {"event": event_type, **data},
                    metadata={"agent": AGENT_NAME},
                )
            except Exception:
                pass
