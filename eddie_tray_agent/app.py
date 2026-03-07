"""
Crypto Tray App — Aplicação principal na system tray.

Integra:
  - ScreenMonitor (lock/unlock)
  - DeviceController (escritório on/off)
  - ClimateMonitor (temp/umidade + ventilador)
  - VoiceAssistant (OK HOME)
  - Communication Bus

Usa pystray para Windows/Linux.
"""
from __future__ import annotations

import asyncio
import io
import logging
import sys
import threading
import time
from types import ModuleType
from typing import Any, Optional

from system_tray_agent.climate_monitor import ClimateMonitor
from system_tray_agent.config import AGENT_NAME, TRAY_TOOLTIP
from system_tray_agent.device_controller import DeviceController
from system_tray_agent.history_db import (
    get_climate_history,
    get_fan_history,
    init_db,
)
from system_tray_agent.screen_monitor import ScreenMonitor
from system_tray_agent.voice_assistant import VoiceAssistant

logger = logging.getLogger(__name__)

# Communication bus (lazy — importado sob demanda para evitar cadeia pesada)
_BUS_OK: bool | None = None
_bus_mod: ModuleType | None = None

def _ensure_bus() -> bool:
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

# pystray (cross-platform system tray)
pystray: Any = None  # type: ignore[assignment]
Image: Any = None  # type: ignore[assignment]
_TRAY_OK = False
try:
    import pystray as _pystray  # type: ignore[no-redef]
    from PIL import Image as _Image  # type: ignore[no-redef]
    pystray = _pystray
    Image = _Image
    _TRAY_OK = True
except ImportError:
    logger.warning("pystray ou Pillow não instalados — modo headless")


def _create_icon_image(color: tuple = (33, 150, 243, 255), badge_color: tuple = (76, 175, 80, 255)) -> Any:
    """Cria um ícone simples 64x64 para a tray.
    
    Args:
        color: cor de fundo RGBA (padrão: azul)
        badge_color: cor do indicador RGBA (padrão: verde)
    """
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    # Desenhar um "E" estilizado
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Fundo arredondado
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=color)
    # Letra "E"
    draw.text((18, 10), "E", fill=(255, 255, 255, 255))
    # Indicador de status
    draw.ellipse([46, 46, 58, 58], fill=badge_color)
    return img


# Cores do ícone por estado de voz
_ICON_COLORS = {
    "idle":       ((33, 150, 243, 255), (76, 175, 80, 255)),   # azul + verde
    "listening":  ((255, 152, 0, 255),  (255, 235, 59, 255)),   # laranja + amarelo
    "processing": ((33, 150, 243, 255), (255, 152, 0, 255)),    # azul + laranja
    "success":    ((76, 175, 80, 255),  (255, 255, 255, 255)),  # verde + branco
    "error":      ((244, 67, 54, 255),  (255, 255, 255, 255)),  # vermelho + branco
}


class CryptoTrayApp:
    """Aplicação principal do Crypto Tray Agent."""

    def __init__(self):
        # Inicializar DB
        init_db()
        logger.info("📦 Banco de dados inicializado")

        # Componentes
        self._device_ctrl = DeviceController()
        self._climate = ClimateMonitor()
        self._voice = VoiceAssistant(on_state_change=self._on_voice_state)

        # Timer para reverter ícone ao idle
        self._icon_revert_timer: Optional[threading.Timer] = None

        # Screen monitor com callbacks
        self._screen = ScreenMonitor(
            on_lock=self._handle_lock,
            on_unlock=self._handle_unlock,
        )

        # Bus (lazy — não inicializar aqui)
        self._bus = None

        # Tray icon
        self._icon: Any = None
        self._running = False

    # ──────────────────────────────────────────────────────
    # Voice state → tray icon color
    # ──────────────────────────────────────────────────────

    def _on_voice_state(self, state: str):
        """Callback chamado pelo VoiceAssistant em cada mudança de estado."""
        if not self._icon or not _TRAY_OK:
            return

        colors = _ICON_COLORS.get(state, _ICON_COLORS["idle"])
        try:
            self._icon.icon = _create_icon_image(color=colors[0], badge_color=colors[1])
        except Exception as exc:
            logger.debug("Falha ao atualizar ícone: %s", exc)
            return

        # Cancelar timer anterior
        if self._icon_revert_timer:
            self._icon_revert_timer.cancel()

        # Reverter ao idle após success/error (3s)
        if state in ("success", "error"):
            self._icon_revert_timer = threading.Timer(
                3.0, self._revert_icon_to_idle,
            )
            self._icon_revert_timer.daemon = True
            self._icon_revert_timer.start()

    def _revert_icon_to_idle(self):
        """Reverte ícone da tray para a cor padrão (idle)."""
        if not self._icon or not _TRAY_OK:
            return
        try:
            colors = _ICON_COLORS["idle"]
            self._icon.icon = _create_icon_image(color=colors[0], badge_color=colors[1])
        except Exception as exc:
            logger.debug("Falha ao reverter ícone: %s", exc)

    # ──────────────────────────────────────────────────────
    # Tray menu
    # ──────────────────────────────────────────────────────

    def _build_menu(self):
        """Constrói menu da tray."""
        if not _TRAY_OK:
            return None

        _noop = lambda *_a, **_kw: None

        return pystray.Menu(
            pystray.MenuItem(
                "Crypto Tray Agent",
                _noop,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: f"🌡️ {self._climate.status_text}",
                _noop,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Escritório ON",
                self._menu_office_on,
            ),
            pystray.MenuItem(
                "Escritório OFF",
                self._menu_office_off,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"🎙️ Voz: {'ON' if self._voice.enabled else 'OFF'}",
                self._menu_toggle_voice,
                checked=lambda item: self._voice.enabled,
            ),
            pystray.MenuItem(
                "🎙️ Acionar manualmente",
                self._menu_trigger_voice,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "📊 Histórico clima",
                self._menu_show_climate,
            ),
            pystray.MenuItem(
                "🌀 Histórico ventilador",
                self._menu_show_fan,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Sair",
                self._menu_quit,
            ),
        )

    # ──────────────────────────────────────────────────────
    # Menu actions
    # ──────────────────────────────────────────────────────

    def _menu_office_on(self, icon=None, item=None):
        def _do():
            try:
                asyncio.run(self._device_ctrl.office_on())
                logger.info("\u2705 Escrit\u00f3rio ligado via menu")
            except Exception as exc:
                logger.error("Erro ao ligar escrit\u00f3rio: %s", exc)
        threading.Thread(target=_do, daemon=True).start()

    def _menu_office_off(self, icon=None, item=None):
        def _do():
            try:
                asyncio.run(self._device_ctrl.office_off())
                logger.info("\u2705 Escrit\u00f3rio desligado via menu")
            except Exception as exc:
                logger.error("Erro ao desligar escrit\u00f3rio: %s", exc)
        threading.Thread(target=_do, daemon=True).start()

    def _menu_toggle_voice(self, icon=None, item=None):
        self._voice.enabled = not self._voice.enabled
        logger.info("🎙️ Voice assistant: %s", "ON" if self._voice.enabled else "OFF")

    def _menu_trigger_voice(self, icon=None, item=None):
        """Aciona a escuta de voz manualmente (sem precisar do wake word)."""
        logger.info("🎙️ Acionamento manual de voz via menu")
        self._voice.trigger_listen()

    def _menu_show_climate(self, icon=None, item=None):
        history = get_climate_history(10)
        if not history:
            logger.info("📊 Sem dados de clima")
            return
        for h in history[:5]:
            logger.info("  📊 %.1f°C %.0f%% %s",
                        h["temperature"], h["humidity"], h["weather"])

    def _menu_show_fan(self, icon=None, item=None):
        history = get_fan_history(10)
        if not history:
            logger.info("🌀 Sem dados do ventilador")
            return
        for h in history[:5]:
            logger.info("  🌀 %s speed=%s mode=%s (%.1f°C)",
                        h["state"], h["speed"], h["mode"], h["temperature"])

    def _menu_quit(self, icon=None, item=None):
        logger.info("👋 Encerrando Crypto Tray Agent...")
        # stop() em thread separada para não bloquear o GTK main loop
        threading.Thread(target=self.stop, daemon=True).start()

    # ──────────────────────────────────────────────────────
    # Lock / Unlock handlers
    # ──────────────────────────────────────────────────────

    def _handle_lock(self):
        """Callback do ScreenMonitor quando tela bloqueia."""
        logger.info("🔒 Tela bloqueada — desligando escritório")
        try:
            asyncio.run(self._device_ctrl.on_screen_lock())
        except Exception as exc:
            logger.error("Erro no lock handler: %s", exc)

    def _handle_unlock(self):
        """Callback do ScreenMonitor quando tela desbloqueia."""
        logger.info("🔓 Tela desbloqueada — restaurando escritório")
        try:
            asyncio.run(self._device_ctrl.on_screen_unlock())
        except Exception as exc:
            logger.error("Erro no unlock handler: %s", exc)

    # ──────────────────────────────────────────────────────
    # Start / Stop
    # ──────────────────────────────────────────────────────

    def _get_bus(self) -> Any:
        """Retorna bus (lazy init)."""
        if self._bus is None and _ensure_bus() and _bus_mod is not None:
            self._bus = _bus_mod.get_communication_bus()
        return self._bus

    def _bus_publish(self, event: str) -> None:
        """Publica no bus em background thread (evita bloquear startup)."""
        def _do() -> None:
            bus = self._get_bus()
            if bus and _bus_mod is not None:
                try:
                    bus.publish(
                        _bus_mod.MessageType.REQUEST,
                        AGENT_NAME,
                        "broadcast",
                        {"event": event},
                        metadata={"agent": AGENT_NAME},
                    )
                except Exception:
                    pass
        threading.Thread(target=_do, daemon=True).start()

    def start(self):
        """Inicia todos os componentes e mostra o ícone na tray."""
        self._running = True

        # Bus announce (lazy)
        self._bus_publish("tray_agent_started")

        # Iniciar componentes
        self._screen.start()
        self._climate.start()
        self._voice.start()

        logger.info("✅ Crypto Tray Agent iniciado")
        logger.info("   🖥️  Screen Monitor: ativo")
        logger.info("   🌡️  Climate Monitor: ativo")
        logger.info("   🎙️  Voice Assistant: %s",
                     "ativo" if self._voice.is_available else "indisponível")

        # Tray icon (bloqueia na thread principal)
        if _TRAY_OK and pystray is not None:
            try:
                icon_image = _create_icon_image()
                icon = pystray.Icon(
                    "system_tray",
                    icon=icon_image,
                    title=TRAY_TOOLTIP,
                    menu=self._build_menu(),
                )
                self._icon = icon
                icon.run()
            except Exception as exc:
                logger.warning("Tray icon falhou: %s — rodando headless", exc)
                self._run_headless()
        else:
            self._run_headless()

    def _run_headless(self) -> None:
        """Modo sem tray (servidor/SSH)."""
        logger.info("🖥️  Rodando em modo headless (Ctrl+C para sair)")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Para todos os componentes. Idempotente."""
        if not self._running:
            return
        self._running = False
        self._screen.stop()
        self._climate.stop()
        self._voice.stop()

        self._bus_publish("tray_agent_stopped")

        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

        logger.info("👋 Crypto Tray Agent encerrado")
