"""
Climate Monitor — Monitora temperatura/umidade e estado do ventilador.

- Consulta OpenWeatherMap periodicamente para temperature/umidade da região
- Registra histórico no PostgreSQL do homelab
- Registra estado do ventilador correlacionando com clima
- No unlock, restaura ventilador ao último estado registrado
"""
import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional

import httpx

from eddie_tray_agent.config import (
    EDDIE_API_URL,
    FAN_DEVICE_NAME,
    WEATHER_API_KEY,
    WEATHER_CITY,
    WEATHER_COUNTRY,
    WEATHER_POLL_INTERVAL,
)
from eddie_tray_agent.history_db import log_climate, log_fan_state

logger = logging.getLogger(__name__)


class ClimateMonitor:
    """Monitora clima e correlaciona com estado do ventilador."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._api = EDDIE_API_URL.rstrip("/")
        self._last_temp: float = 0.0
        self._last_humidity: float = 0.0
        self._last_weather: str = ""

    # ──────────────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────────────

    @property
    def last_temperature(self) -> float:
        return self._last_temp

    @property
    def last_humidity(self) -> float:
        return self._last_humidity

    @property
    def last_weather(self) -> str:
        return self._last_weather

    @property
    def status_text(self) -> str:
        if self._last_temp == 0:
            return "Sem dados de clima"
        return f"{self._last_temp:.1f}°C  {self._last_humidity:.0f}%  {self._last_weather}"

    # ──────────────────────────────────────────────────────
    # Start / Stop
    # ──────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="climate-monitor")
        self._thread.start()
        logger.info("🌡️  ClimateMonitor iniciado (poll=%ds, city=%s)",
                     WEATHER_POLL_INTERVAL, WEATHER_CITY)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    # ──────────────────────────────────────────────────────
    # Main loop
    # ──────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                asyncio.run(self._poll_once())
            except Exception as exc:
                logger.error("ClimateMonitor poll error: %s", exc)
            # Dormir em intervalos menores para responder rápido ao stop
            for _ in range(WEATHER_POLL_INTERVAL):
                if not self._running:
                    return
                time.sleep(1)

    async def _poll_once(self):
        """Faz uma leitura de clima + estado do ventilador."""
        # 1. Buscar clima
        weather = await self._fetch_weather()
        if weather:
            self._last_temp = weather.get("temp", 0)
            self._last_humidity = weather.get("humidity", 0)
            self._last_weather = weather.get("description", "")
            log_climate(
                temperature=self._last_temp,
                humidity=self._last_humidity,
                weather=self._last_weather,
                city=WEATHER_CITY,
            )

        # 2. Buscar estado do ventilador
        fan = await self._fetch_fan_state()
        if fan:
            log_fan_state(
                state=fan.get("state", "off"),
                speed=fan.get("speed", 0),
                mode=fan.get("mode", ""),
                temperature=self._last_temp,
                humidity=self._last_humidity,
            )
            logger.debug("🌀 Fan: state=%s speed=%s | 🌡️ %.1f°C %.0f%%",
                         fan.get("state"), fan.get("speed"),
                         self._last_temp, self._last_humidity)

    # ──────────────────────────────────────────────────────
    # Weather API
    # ──────────────────────────────────────────────────────

    async def _fetch_weather(self) -> Optional[Dict[str, Any]]:
        """Busca dados do OpenWeatherMap (free tier)."""
        if not WEATHER_API_KEY:
            logger.debug("OPENWEATHER_API_KEY não configurada, pulando clima")
            return None

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={WEATHER_CITY},{WEATHER_COUNTRY}"
            f"&appid={WEATHER_API_KEY}"
            f"&units=metric&lang=pt_br"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            main = data.get("main", {})
            weather_desc = ""
            if data.get("weather"):
                weather_desc = data["weather"][0].get("description", "")

            return {
                "temp": main.get("temp", 0),
                "feels_like": main.get("feels_like", 0),
                "humidity": main.get("humidity", 0),
                "description": weather_desc,
            }
        except Exception as exc:
            logger.warning("OpenWeatherMap falhou: %s", exc)
            return None

    # ──────────────────────────────────────────────────────
    # Fan state via Eddie API
    # ──────────────────────────────────────────────────────

    async def _fetch_fan_state(self) -> Optional[Dict[str, Any]]:
        """Busca estado atual do ventilador via API do Eddie."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._api}/home/devices")
                if resp.status_code != 200:
                    return None
                devices = resp.json()

            if isinstance(devices, list):
                for dev in devices:
                    if FAN_DEVICE_NAME in dev.get("name", "").lower():
                        state = dev.get("state", "off")
                        speed = dev.get("attributes", {}).get("speed", 0)
                        if not speed and dev.get("brightness"):
                            speed = dev["brightness"]  # Alguns ventiladores usam brightness como speed
                        mode = dev.get("attributes", {}).get("mode", "")
                        return {"state": state, "speed": speed, "mode": mode}
        except Exception as exc:
            logger.debug("Fetch fan state falhou: %s", exc)

        return None
