"""Factory compartilhada de Chrome/Selenium para automações Kwai."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path(
    os.getenv("KWAI_VIEWER_DATA_DIR", str(Path.home() / ".local/share/kwai-viewer"))
)
DEFAULT_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
DEFAULT_DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def chrome_profile_dir() -> Path:
    raw = (os.getenv("KWAI_CHROME_PROFILE_DIR") or "").strip()
    if raw:
        return Path(raw)
    # Chromium snap não grava perfil em /var/lib; usar home por padrão no homelab.
    if str(DEFAULT_DATA_DIR).startswith("/var/"):
        return Path.home() / ".local/share/kwai-viewer/chrome-profile"
    return DEFAULT_DATA_DIR / "chrome-profile"


def ua_for_url(url: str) -> tuple[str, str]:
    if "kwai.com" in url:
        return DEFAULT_MOBILE_UA, "390,844"
    return DEFAULT_DESKTOP_UA, "1366,768"


def _prepare_profile_dir(profile: Path) -> Path:
    profile.mkdir(parents=True, exist_ok=True)
    for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock_path = profile / lock_name
        if lock_path.exists() or lock_path.is_symlink():
            try:
                lock_path.unlink()
            except OSError:
                pass
    return profile


def build_driver(
    *,
    headless: bool,
    chrome_binary: str | None,
    start_url: str,
    profile_dir: Path | None = None,
):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    user_agent, window_size = ua_for_url(start_url)
    profile = _prepare_profile_dir(profile_dir or chrome_profile_dir())

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={window_size}")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--remote-debugging-port=0")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option(
        "prefs",
        {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1,
        },
    )
    if chrome_binary:
        options.binary_location = chrome_binary

    # Bypass explícito de proxy/VPN para domínios Kwai (evita redirecionamento 127.0.0.1)
    # O bypass real deve ser configurado no host (no_proxy / proxy ACL) — ver docs/KWAI_PROXY_BYPASS.md
    options.add_argument("--proxy-bypass-list=kwai.com,.kwai.com,m-wallet.kwai.com,m-creative.kwai.com")

    try:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except Exception:
        driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver