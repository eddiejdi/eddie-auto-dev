"""
Screen Lock/Unlock Monitor.

Detecta quando o computador bloqueia/desbloqueia a tela.
- Linux: D-Bus (org.freedesktop.ScreenSaver / org.gnome.ScreenSaver / logind)
- Windows: ctypes + WTSRegisterSessionNotification

Dispara callbacks:
  on_lock()   → desliga dispositivos do escritório
  on_unlock() → reativa dispositivos do escritório
"""
import logging
import platform
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Callbacks type
LockCallback = Callable[[], None]


class ScreenMonitor:
    """Observa eventos de lock/unlock da sessão do usuário."""

    def __init__(
        self,
        on_lock: Optional[LockCallback] = None,
        on_unlock: Optional[LockCallback] = None,
    ):
        self._on_lock = on_lock
        self._on_unlock = on_unlock
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._system = platform.system()

    # ──────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────

    def start(self):
        """Inicia a monitoramento em thread separada."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="screen-monitor")
        self._thread.start()
        logger.info("🖥️  ScreenMonitor iniciado (%s)", self._system)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("🖥️  ScreenMonitor parado")

    # ──────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────

    def _run(self):
        if self._system == "Linux":
            self._run_linux()
        elif self._system == "Windows":
            self._run_windows()
        else:
            logger.warning("Sistema %s não suportado para lock monitor, usando polling", self._system)
            self._run_polling()

    # ─── Linux (D-Bus) ──────────────────────────────────────

    def _run_linux(self):
        """Usa D-Bus para escutar sinais de lock/unlock."""
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
        except ImportError:
            logger.warning("dbus-python ou PyGObject não disponível, caindo para polling")
            self._run_polling()
            return

        DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()

        def _on_signal(locked: bool):
            if locked:
                logger.info("🔒 Tela bloqueada (D-Bus)")
                if self._on_lock:
                    threading.Thread(target=self._on_lock, daemon=True).start()
            else:
                logger.info("🔓 Tela desbloqueada (D-Bus)")
                if self._on_unlock:
                    threading.Thread(target=self._on_unlock, daemon=True).start()

        # Tentar vários provedores de sinal
        signal_interfaces = [
            ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver", "ActiveChanged"),
            ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver", "ActiveChanged"),
            ("org.kde.screensaver", "/ScreenSaver", "ActiveChanged"),
        ]

        connected = False
        for iface, path, signal in signal_interfaces:
            try:
                bus.add_signal_receiver(
                    _on_signal,
                    signal_name=signal,
                    dbus_interface=iface,
                    path=path,
                )
                logger.info("📡 Conectado a %s (%s)", iface, signal)
                connected = True
                break
            except Exception as exc:
                logger.debug("Não conectou a %s: %s", iface, exc)

        # Tentar logind como fallback
        if not connected:
            try:
                system_bus = dbus.SystemBus()

                def _logind_signal(locked: bool):
                    _on_signal(locked)

                system_bus.add_signal_receiver(
                    _logind_signal,
                    signal_name="Lock",
                    dbus_interface="org.freedesktop.login1.Session",
                )
                system_bus.add_signal_receiver(
                    lambda: _logind_signal(False),
                    signal_name="Unlock",
                    dbus_interface="org.freedesktop.login1.Session",
                )
                logger.info("📡 Conectado via logind (Lock/Unlock)")
                connected = True
            except Exception as exc:
                logger.debug("logind fallback falhou: %s", exc)

        if not connected:
            logger.warning("Nenhum D-Bus provider encontrado, usando polling")
            self._run_polling()
            return

        loop = GLib.MainLoop()
        try:
            while self._running:
                ctx = loop.get_context()
                ctx.iteration(False)
                time.sleep(0.2)
        except Exception:
            pass

    # ─── Windows ─────────────────────────────────────────────

    def _run_windows(self):
        """Monitora WTS session notifications no Windows."""
        try:
            import ctypes
            import ctypes.wintypes
        except ImportError:
            self._run_polling()
            return

        WTS_SESSION_LOCK = 0x7
        WTS_SESSION_UNLOCK = 0x8
        NOTIFY_FOR_THIS_SESSION = 0

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.wintypes.HWND,
            ctypes.wintypes.UINT,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        )

        WM_WTSSESSION_CHANGE = 0x02B1
        last_state = [None]

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_WTSSESSION_CHANGE:
                if wparam == WTS_SESSION_LOCK:
                    logger.info("🔒 Tela bloqueada (Windows)")
                    if self._on_lock:
                        threading.Thread(target=self._on_lock, daemon=True).start()
                elif wparam == WTS_SESSION_UNLOCK:
                    logger.info("🔓 Tela desbloqueada (Windows)")
                    if self._on_unlock:
                        threading.Thread(target=self._on_unlock, daemon=True).start()
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wndclass = ctypes.wintypes.WNDCLASSW()
        wndclass.lpfnWndProc = WNDPROC(wnd_proc)
        wndclass.lpszClassName = "CryptoTrayLockMonitor"
        wndclass.hInstance = kernel32.GetModuleHandleW(None)

        class_atom = user32.RegisterClassW(ctypes.byref(wndclass))
        if not class_atom:
            logger.error("Falha ao registrar window class")
            self._run_polling()
            return

        hwnd = user32.CreateWindowExW(
            0, class_atom, "CryptoTrayLockMonitor", 0,
            0, 0, 0, 0, None, None, wndclass.hInstance, None,
        )

        try:
            wtsapi32 = ctypes.windll.wtsapi32
            wtsapi32.WTSRegisterSessionNotification(hwnd, NOTIFY_FOR_THIS_SESSION)
        except Exception:
            pass

        msg = ctypes.wintypes.MSG()
        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg), hwnd, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.2)

        user32.DestroyWindow(hwnd)

    # ─── Polling fallback ────────────────────────────────────

    def _run_polling(self):
        """
        Fallback: verifica periodicamente se a tela está bloqueada.
        Linux: xdg-screensaver status / loginctl
        """
        import subprocess

        was_locked = False
        logger.info("📡 Usando polling para detectar lock/unlock")

        while self._running:
            locked = False
            try:
                if self._system == "Linux":
                    # Tentar xdg-screensaver
                    r = subprocess.run(
                        ["xdg-screensaver", "status"],
                        capture_output=True, text=True, timeout=5,
                    )
                    if r.returncode == 0 and "enabled" in r.stdout.lower():
                        locked = True

                    # Fallback: loginctl
                    if not locked:
                        r2 = subprocess.run(
                            ["loginctl", "show-session", "auto", "-p", "LockedHint"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if "yes" in r2.stdout.lower():
                            locked = True

                elif self._system == "Windows":
                    # Não há polling confiável no Windows, já tratado no _run_windows
                    pass

            except Exception as exc:
                logger.debug("Polling check falhou: %s", exc)

            if locked and not was_locked:
                logger.info("🔒 Tela bloqueada (polling)")
                if self._on_lock:
                    threading.Thread(target=self._on_lock, daemon=True).start()
            elif not locked and was_locked:
                logger.info("🔓 Tela desbloqueada (polling)")
                if self._on_unlock:
                    threading.Thread(target=self._on_unlock, daemon=True).start()

            was_locked = locked
            time.sleep(2)
