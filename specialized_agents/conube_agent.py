"""Lightweight Conube integration routes.

This source implementation restores the public Conube endpoints used by the
site even when the original homelab module is unavailable. It focuses on:
- health and credential checks
- browser login validation
- a resilient daily summary payload for the site
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/conube", tags=["conube"])

CONUBE_BASE_URL = "https://app.conube.com.br"
CONUBE_LOGIN_URL = f"{CONUBE_BASE_URL}/login"
CONUBE_SECRET_NAME = "conube/rpa4all"
CONUBE_CHROME_BINARY = (
    os.getenv("CONUBE_CHROME_BINARY")
    or os.getenv("GOOGLE_CHROME_BIN")
    or os.getenv("CHROME_BINARY")
    or "/usr/bin/chromium-browser"
)


class ConubeActionRequest(BaseModel):
    headless: bool | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _load_local_secret(field: str) -> str | None:
    os.environ.setdefault("SECRETS_AGENT_DATA", "/var/lib/eddie/secrets_agent")
    try:
        from tools.secrets_agent.secrets_agent import local_vault  # noqa: PLC0415

        value = local_vault.get(CONUBE_SECRET_NAME, field)
        if value:
            return str(value).strip()
    except Exception:
        return None
    return None


def _load_credentials() -> tuple[str | None, str | None]:
    email = (
        os.getenv("CONUBE_EMAIL", "").strip()
        or _load_local_secret("email")
        or _load_local_secret("username")
    )
    password = (
        os.getenv("CONUBE_PASSWORD", "").strip()
        or _load_local_secret("password")
    )
    return email or None, password or None


def _credentials_configured() -> bool:
    email, password = _load_credentials()
    return bool(email and password)


def _chrome_binary() -> str | None:
    candidates = [
        CONUBE_CHROME_BINARY,
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        which("chromium-browser") or "",
        which("google-chrome") or "",
        which("google-chrome-stable") or "",
        which("chromium") or "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


class ConubePortalAgent:
    def __init__(
        self,
        email: str,
        password: str,
        *,
        headless: bool = True,
        timeout_seconds: float = 25.0,
        download_dir: str | None = None,
    ) -> None:
        self.email = email
        self.password = password
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.download_dir = download_dir or "/tmp/conube-downloads"
        self.driver = self._create_driver()
        self.session_token = ""

    def _create_driver(self):
        try:
            from selenium import webdriver
        except Exception as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("selenium nao instalado neste ambiente") from exc

        options = webdriver.ChromeOptions()
        options.page_load_strategy = "eager"
        binary = _chrome_binary()
        if binary:
            options.binary_location = binary
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1480,1200")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": str(Path(self.download_dir).resolve()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
            },
        )
        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(self.timeout_seconds)
        except Exception:
            pass
        return driver

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass

    def _body_text(self) -> str:
        try:
            return (
                self.driver.find_element("tag name", "body").text or ""
            ).strip()
        except Exception:
            return ""

    def _set_input(self, selectors: list[tuple[str, str]], value: str) -> bool:
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            for by, selector in selectors:
                try:
                    element = self.driver.find_element(by, selector)
                    try:
                        element.click()
                    except Exception:
                        pass
                    try:
                        element.clear()
                    except Exception:
                        pass
                    try:
                        element.send_keys(value)
                    except Exception:
                        pass

                    current_value = str(element.get_attribute("value") or "").strip()
                    if current_value:
                        return True

                    # Fallback para componentes controlados (React/MUI).
                    self.driver.execute_script(
                        """
                        const el = arguments[0];
                        const val = arguments[1];
                        const proto = Object.getPrototypeOf(el);
                        const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (desc && typeof desc.set === 'function') {
                          desc.set.call(el, val);
                        } else {
                          el.value = val;
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        element,
                        value,
                    )
                    current_value = str(element.get_attribute("value") or "").strip()
                    if current_value:
                        return True
                except Exception:
                    continue
            time.sleep(0.25)
        return False

    def _collect_menu_items(self) -> list[str]:
        try:
            items = self.driver.execute_script(
                """
                return Array.from(document.querySelectorAll('a,button,[role="link"]'))
                  .map((node) => (node.innerText || node.textContent || '').trim())
                  .filter(Boolean)
                  .slice(0, 20);
                """
            )
            if isinstance(items, list):
                return [str(item).strip() for item in items if str(item).strip()]
        except Exception:
            return []
        return []

    def _read_access_token(self) -> str:
        try:
            token = self.driver.execute_script(
                "return window.localStorage.getItem('access_token') || ''"
            )
        except Exception:
            return ""
        token = str(token or "").strip()
        if len(token) <= 15:
            return ""
        self.session_token = token
        return token

    def _has_login_form(self) -> bool:
        for by, selector in [
            ("css selector", "input[name='email']"),
            ("css selector", "input[name='password']"),
            ("css selector", "button[type='submit']"),
        ]:
            try:
                self.driver.find_element(by, selector)
                return True
            except Exception:
                continue
        return False

    def _is_authenticated_view(self) -> bool:
        body_text = self._body_text().lower()
        menu_items = [item.lower() for item in self._collect_menu_items()]
        strong_markers = ("olá", "ola", "início", "inicio", "minha empresa", "tarefas")
        marker_hits = sum(1 for marker in strong_markers if marker in body_text)
        menu_hits = sum(1 for marker in ("início", "inicio", "minha empresa", "tarefas") if any(marker in item for item in menu_items))
        return (marker_hits >= 2 or menu_hits >= 2) and not self._has_login_form()

    def login(self) -> dict[str, Any]:
        self.driver.get(CONUBE_LOGIN_URL)
        if self._is_authenticated_view():
            token = self._read_access_token()
            return {
                "authenticated": True,
                "token_present": bool(token),
                "current_url": getattr(self.driver, "current_url", ""),
                "title": getattr(self.driver, "title", ""),
                "menu_items": self._collect_menu_items(),
                "body_excerpt": self._body_text()[:500],
            }

        field_error: RuntimeError | None = None
        for attempt in range(2):
            self.driver.get(CONUBE_LOGIN_URL)
            # O login da Conube costuma hidratar os componentes alguns segundos
            # apos o carregamento inicial; aguardamos os inputs antes de escrever.
            form_ready = self._set_input(
                [
                    ("css selector", "input[name='email']"),
                    ("css selector", "input[type='email']"),
                    ("css selector", "input[placeholder*='e-mail']"),
                    ("css selector", "input[placeholder*='email']"),
                ],
                self.email,
            )
            email_ok = self._set_input(
                [
                    ("css selector", "input[type='email']"),
                    ("css selector", "input[name='email']"),
                    ("css selector", "input[autocomplete='username']"),
                    ("css selector", "input[placeholder*='e-mail']"),
                    ("css selector", "input[placeholder*='email']"),
                ],
                self.email,
            )
            password_ok = self._set_input(
                [
                    ("css selector", "input[type='password']"),
                    ("css selector", "input[name='password']"),
                    ("css selector", "input[autocomplete='current-password']"),
                    ("css selector", "input[placeholder*='senha']"),
                ],
                self.password,
            )
            if not (form_ready and email_ok and password_ok):
                field_error = RuntimeError("Nao foi possivel localizar os campos de login da Conube.")
                if attempt == 0:
                    continue
                raise field_error

            clicked = False
            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline and not clicked:
                for by, selector in [
                    ("css selector", "button[type='submit']"),
                    ("xpath", "//button[contains(., 'Entrar')]"),
                    ("xpath", "//button[contains(., 'Acessar')]"),
                ]:
                    try:
                        button = self.driver.find_element(by, selector)
                        self.driver.execute_script("arguments[0].click();", button)
                        clicked = True
                        break
                    except Exception:
                        continue
                if not clicked:
                    time.sleep(0.25)
            if clicked:
                break
            if attempt == 1:
                raise RuntimeError("Nao foi possivel submeter o login na Conube.")
        else:
            raise field_error or RuntimeError("Falha ao iniciar automacao de login da Conube.")

        token = ""
        authenticated = False
        wait_deadline = time.monotonic() + 18.0
        while time.monotonic() < wait_deadline:
            token = self._read_access_token()
            if token or self._is_authenticated_view():
                authenticated = True
                break
            time.sleep(0.5)

        body_text = self._body_text().lower()
        if any(
            marker in body_text
            for marker in (
                "credenciais invalidas",
                "e-mail ou senha invalidos",
                "e-mail ou senha inválidos",
                "senha incorreta",
                "nao autorizado",
            )
        ):
            raise RuntimeError("A Conube rejeitou as credenciais informadas.")
        if "token de seguranca" in body_text:
            raise RuntimeError("A Conube solicitou token adicional por email; automacao interrompida.")

        return {
            "authenticated": authenticated,
            "token_present": bool(token),
            "current_url": getattr(self.driver, "current_url", ""),
            "title": getattr(self.driver, "title", ""),
            "menu_items": self._collect_menu_items(),
            "body_excerpt": self._body_text()[:500],
        }


def _build_degraded_report(login_result: dict[str, Any], *, refresh: bool, use_ollama: bool) -> dict[str, Any]:
    authenticated = bool(login_result.get("authenticated"))
    menu_items = login_result.get("menu_items") or []
    title = str(login_result.get("title") or "Conube").strip()
    current_url = str(login_result.get("current_url") or CONUBE_LOGIN_URL).strip()
    failure_reason = str(login_result.get("failure_reason") or "").strip()
    if authenticated:
        headline = "Sessao autenticada na Conube."
        narrative = (
            "A autenticacao na Conube foi validada com sucesso e o ambiente esta acessivel. "
            "O painel ja pode ser usado para acompanhamento operacional diario."
        )
        actions = [
            {
                "priority": "media",
                "title": "Acompanhar consistencia da coleta",
                "details": "Sessao autenticada com sucesso; monitorar estabilidade das proximas atualizacoes.",
                "owner": "automacao",
            }
        ]
    else:
        headline = "Conube acessivel, mas sem autenticacao concluida."
        narrative = (
            "As credenciais foram encontradas e a tela de login abriu corretamente, porém "
            "a Conube nao entregou token de sessao nesta tentativa automatizada. Revise se "
            "o portal exige etapa adicional ou confirmacao fora da tela principal."
        )
        if failure_reason:
            narrative = (
                "A integracao entrou em modo degradado porque a automacao nao conseguiu "
                f"concluir o fluxo de login: {failure_reason}"
            )
        actions = [
            {
                "priority": "alta",
                "title": "Validar autenticacao da Conube",
                "details": failure_reason
                or "Confirmar se houve bloqueio por etapa extra, captcha ou token adicional.",
                "owner": "operacao",
            }
        ]

    return {
        "report_date": _today_iso(),
        "generated_at": _now_iso(),
        "narrative_source": "conube-fallback",
        "ollama_model": None,
        "narrative": narrative,
        "summary": {
            "open_periods_count": 0,
            "client_actionable_items_count": 0,
            "accountant_owned_items_count": 0,
            "pending_items_count": 0,
            "overdue_items_count": 0,
            "certificate": {
                "expired": False,
                "latest_expiration": None,
            },
            "headline": headline,
            "refresh_requested": refresh,
            "use_ollama_requested": use_ollama,
        },
        "grouped_pending_items": [
            {
                "subject": "Estado atual da integracao",
                "competences": [title or "Conube"],
                "count": len(menu_items),
                "responsible": "automacao",
            }
        ],
        "recommended_actions": actions,
        "pending_items": [],
        "pending_documents": {
            "has_pending_documents": False,
            "documents_count": 0,
            "documentation_check_state": "degraded",
            "documentation_notice": f"URL atual: {current_url}",
        },
        "debug": {
            "authenticated": authenticated,
            "current_url": current_url,
            "title": title,
            "menu_items": menu_items,
            "failure_reason": failure_reason,
        },
    }


def _build_agent(headless: bool | None) -> ConubePortalAgent:
    email, password = _load_credentials()
    if not (email and password):
        raise HTTPException(
            status_code=503,
            detail=(
                "Credenciais da Conube nao configuradas. Defina CONUBE_EMAIL/CONUBE_PASSWORD "
                "ou armazene email/password no secret conube/rpa4all."
            ),
        )
    return ConubePortalAgent(email, password, headless=True if headless is None else headless)


@router.get("/health")
def conube_health() -> dict[str, Any]:
    return {
        "status": "ok",
        "base_url": CONUBE_BASE_URL,
        "login_url": CONUBE_LOGIN_URL,
        "headless_default": True,
        "credentials_configured": _credentials_configured(),
        "secret_names": [CONUBE_SECRET_NAME],
        "chrome_binary": _chrome_binary(),
    }


@router.post("/session/test-login")
def conube_test_login(payload: ConubeActionRequest | None = None) -> dict[str, Any]:
    agent = _build_agent(payload.headless if payload else None)
    try:
        result = agent.login()
        return {"status": "ok", **result}
    except HTTPException:
        raise
    except Exception as exc:
        return {
            "status": "error",
            "authenticated": False,
            "token_present": False,
            "current_url": CONUBE_LOGIN_URL,
            "title": "Conube",
            "menu_items": [],
            "error": str(exc),
        }
    finally:
        agent.close()


@router.get("/reports/daily-summary")
def conube_daily_summary_report(
    headless: bool | None = None,
    refresh: bool = False,
    use_ollama: bool = True,
) -> dict[str, Any]:
    agent = _build_agent(headless)
    try:
        login_result = agent.login()
        return _build_degraded_report(login_result, refresh=refresh, use_ollama=use_ollama)
    except HTTPException:
        raise
    except Exception as exc:
        return _build_degraded_report(
            {
                "authenticated": False,
                "token_present": False,
                "current_url": CONUBE_LOGIN_URL,
                "title": "Conube",
                "menu_items": [],
                "failure_reason": str(exc),
            },
            refresh=refresh,
            use_ollama=use_ollama,
        )
    finally:
        agent.close()
