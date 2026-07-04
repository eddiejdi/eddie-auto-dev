#!/usr/bin/env python3
"""Bot que entra em reuniões (Google Meet / Microsoft Teams) como participante.

Fase 1: entra na sala e pede admissão ("Pedir para participar").
Fase 2 (futura): captura de áudio → faster-whisper (GPU0) → gemma3-fast (GPU1)
para legenda traduzida ao vivo (ver docs/TRADING_MULTI_SYMBOL_LIVE e avaliação
do "modo reunião").
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Callable

logger = logging.getLogger("meet_bot")

BOT_NAME = "Tradutor RPA4All"
SCREENSHOT_DIR = Path("/tmp/meeting-translator")
STAY_IN_CALL_SEC = 2 * 3600  # permanece na chamada por até 2h


def detect_platform(url: str) -> str:
    """Retorna 'meet', 'teams' ou lança ValueError."""
    if re.search(r"meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}", url):
        return "meet"
    if "teams.microsoft.com" in url or "teams.live.com" in url:
        return "teams"
    raise ValueError("Link não reconhecido — cole um link do Google Meet ou do Microsoft Teams")


def _build_driver():
    from selenium import webdriver

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,900")
    opts.add_argument("--lang=pt-BR")
    opts.add_argument("--use-fake-ui-for-media-stream")   # auto-aceita prompt de mic/cam
    opts.add_argument("--use-fake-device-for-media-stream")
    opts.add_argument("--mute-audio")
    opts.add_experimental_option("prefs", {
        "intl.accept_languages": "pt-BR,pt",
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 2,
    })
    # Chrome real + chromedriver da MESMA versão baixado em bin/ (Chrome for
    # Testing). NÃO usar /usr/bin/chromedriver (wrapper do snap, confinado)
    # nem o chromium snap (não sobe sob systemd) — lições do homelab.
    from selenium.webdriver.chrome.service import Service

    opts.binary_location = "/opt/google/chrome/chrome"
    driver_path = Path(__file__).parent / "bin" / "chromedriver"
    service = Service(executable_path=str(driver_path))
    return webdriver.Chrome(service=service, options=opts)


def _click_first(driver, xpaths: list[str], timeout: float = 12) -> bool:
    """Clica no primeiro elemento clicável entre os xpaths (retorna False se nenhum)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    deadline = time.time() + timeout
    while time.time() < deadline:
        for xp in xpaths:
            try:
                els = driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed() and el.is_enabled():
                        driver.execute_script("arguments[0].click();", el)
                        return True
            except Exception:
                continue
        time.sleep(0.5)
    return False


def _type_first(driver, xpaths: list[str], text: str, timeout: float = 12) -> bool:
    from selenium.webdriver.common.by import By

    deadline = time.time() + timeout
    while time.time() < deadline:
        for xp in xpaths:
            try:
                els = driver.find_elements(By.XPATH, xp)
                for el in els:
                    if el.is_displayed():
                        el.clear()
                        el.send_keys(text)
                        return True
            except Exception:
                continue
        time.sleep(0.5)
    return False


def _screenshot(driver, job_id: str, tag: str) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{job_id}_{tag}.png"
    try:
        driver.save_screenshot(str(path))
    except Exception:
        pass
    return str(path)


def _join_meet(driver, url: str, status: Callable[[str], None], job_id: str) -> None:
    status("abrindo o Google Meet…")
    driver.get(url)
    time.sleep(4)

    # Desligar microfone e câmera na pré-sala (Meet: botões com aria-label)
    for label in ("microfone", "microphone"):
        _click_first(driver, [f"//div[@role='button' and contains(translate(@aria-label,'MC','mc'),'{label}') and contains(@aria-label,'esligar') or contains(@aria-label,'urn off')]"], timeout=3)

    status("informando o nome do bot…")
    named = _type_first(driver, [
        "//input[contains(@aria-label,'nome') or contains(@aria-label,'name')]",
        "//input[@type='text']",
    ], BOT_NAME, timeout=10)
    if not named:
        # Provavelmente exige login Google (reunião restrita à organização)
        shot = _screenshot(driver, job_id, "meet_sem_campo_nome")
        raise RuntimeError(
            "Meet não ofereceu entrada como convidado — a reunião pode exigir login "
            f"Google. Screenshot: {shot}"
        )

    status("pedindo para participar…")
    asked = _click_first(driver, [
        "//button[.//span[contains(text(),'Pedir para participar')]]",
        "//button[.//span[contains(text(),'Ask to join')]]",
        "//button[.//span[contains(text(),'Participar agora')]]",
        "//button[.//span[contains(text(),'Join now')]]",
        "//span[contains(text(),'Pedir para participar')]/ancestor::button",
    ], timeout=15)
    if not asked:
        shot = _screenshot(driver, job_id, "meet_sem_botao_join")
        raise RuntimeError(f"Botão de participar não encontrado. Screenshot: {shot}")

    status("⏳ aguardando o organizador admitir o Tradutor RPA4All…")
    _wait_in_call(driver, status, job_id)


def _join_teams(driver, url: str, status: Callable[[str], None], job_id: str) -> None:
    status("abrindo o Microsoft Teams (web)…")
    driver.get(url)
    time.sleep(5)

    # "Continuar neste navegador"
    _click_first(driver, [
        "//button[contains(., 'Continuar neste navegador')]",
        "//button[contains(., 'Continue on this browser')]",
        "//a[contains(@href,'launcher=false')]",
        "//button[@data-tid='joinOnWeb']",
    ], timeout=15)
    time.sleep(4)

    status("informando o nome do bot…")
    _type_first(driver, [
        "//input[@data-tid='prejoin-display-name-input']",
        "//input[contains(@placeholder,'nome') or contains(@placeholder,'name')]",
        "//input[@type='text']",
    ], BOT_NAME, timeout=20)

    # Desligar mic/câmera se toggles visíveis
    _click_first(driver, ["//div[@data-tid='toggle-video']", "//div[@data-tid='toggle-mute']"], timeout=3)

    status("pedindo para entrar na reunião…")
    asked = _click_first(driver, [
        "//button[@data-tid='prejoin-join-button']",
        "//button[contains(., 'Ingressar agora')]",
        "//button[contains(., 'Join now')]",
        "//button[contains(., 'Entrar agora')]",
    ], timeout=15)
    if not asked:
        shot = _screenshot(driver, job_id, "teams_sem_botao_join")
        raise RuntimeError(f"Botão de ingresso não encontrado. Screenshot: {shot}")

    status("⏳ aguardando o organizador admitir o Tradutor RPA4All…")
    _wait_in_call(driver, status, job_id)


def _wait_in_call(driver, status: Callable[[str], None], job_id: str) -> None:
    """Permanece na sessão até ser admitido + duração máxima (ou removido)."""
    admitted = False
    deadline = time.time() + STAY_IN_CALL_SEC
    while time.time() < deadline:
        page = ""
        try:
            page = driver.page_source[:200000]
        except Exception:
            status("sessão do navegador encerrada")
            return
        lowered = page.lower()
        if not admitted and not any(k in lowered for k in ("pedindo para participar", "asking to join", "aguardando", "waiting for")):
            if any(k in lowered for k in ("sair da chamada", "leave call", "abandonar", "hang up", "roster", "participantes")):
                admitted = True
                status("✅ admitido na reunião — presente como Tradutor RPA4All (captura de áudio: fase 2)")
                _screenshot(driver, job_id, "admitido")
        if any(k in lowered for k in ("você foi removido", "removed from", "call ended", "chamada encerrada")):
            status("reunião encerrada / bot removido")
            return
        time.sleep(10)
    status("tempo máximo de permanência atingido (2h) — saindo")


def join_meeting(url: str, status: Callable[[str], None], job_id: str) -> None:
    """Entra na reunião e permanece. Levanta exceção com diagnóstico em falha."""
    platform = detect_platform(url)
    driver = _build_driver()
    try:
        if platform == "meet":
            _join_meet(driver, url, status, job_id)
        else:
            _join_teams(driver, url, status, job_id)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
