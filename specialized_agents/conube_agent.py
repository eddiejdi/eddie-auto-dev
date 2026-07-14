"""Lightweight Conube integration routes.

This source implementation restores the public Conube endpoints used by the
site even when the original homelab module is unavailable. It focuses on:
- health and credential checks
- browser login validation
- a resilient daily summary payload for the site
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from shutil import which
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["conube"])

CONUBE_BASE_URL = "https://app.conube.com.br"
CONUBE_LOGIN_URL = f"{CONUBE_BASE_URL}/login"
CONUBE_SECRET_NAME = "conube/rpa4all"
CONUBE_REPORT_CACHE = Path(
    os.getenv("CONUBE_REPORT_CACHE", "/var/lib/eddie/conube/daily-summary-latest.json")
)
CONUBE_CHROME_BINARY = (
    os.getenv("CONUBE_CHROME_BINARY")
    or os.getenv("GOOGLE_CHROME_BIN")
    or os.getenv("CHROME_BINARY")
    or "/usr/bin/chromium-browser"
)
CONUBE_ACTION_TOKEN = os.getenv("CONUBE_ACTION_TOKEN", "").strip()
CONUBE_HEADLESS = os.getenv("CONUBE_HEADLESS", "1").lower() not in {"0", "false", "off", "no"}


class ConubeActionRequest(BaseModel):
    headless: bool | None = None


class ConubeRunRemediationRequest(BaseModel):
    headless: bool | None = None
    close_periods_limit: int = Field(default=12, ge=1, le=24)
    run_client_tasks: bool = True
    run_selenium_balances: bool = True
    run_selenium_tasks: bool = True
    selenium_balances_limit: int = Field(default=12, ge=1, le=24)
    selenium_tasks_limit: int = Field(default=20, ge=1, le=50)


class ConubeCloseBalancesRequest(BaseModel):
    headless: bool | None = None
    limit: int = Field(default=12, ge=1, le=24)


class ConubeSeleniumTasksRequest(BaseModel):
    headless: bool | None = None
    limit: int = Field(default=20, ge=1, le=50)


class ConubeClosePeriodsRequest(BaseModel):
    headless: bool | None = None
    limit: int = Field(default=12, ge=1, le=24)


class ConubePayBillingRequest(BaseModel):
    headless: bool | None = None
    dry_run: bool = False
    limit: int = Field(default=3, ge=1, le=10)


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


def load_conube_credentials() -> tuple[str, str]:
    email, password = _load_credentials()
    if not (email and password):
        raise RuntimeError(
            "Credenciais da Conube nao configuradas. Defina CONUBE_EMAIL/CONUBE_PASSWORD "
            "ou armazene email/password no secret conube/rpa4all."
        )
    return email, password


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


def _read_cached_report() -> dict[str, Any] | None:
    try:
        if CONUBE_REPORT_CACHE.is_file():
            payload = json.loads(CONUBE_REPORT_CACHE.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        return None
    return None


def write_cached_report(payload: dict[str, Any]) -> Path:
    CONUBE_REPORT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    CONUBE_REPORT_CACHE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return CONUBE_REPORT_CACHE


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
        service = None
        for chromedriver in (
            os.getenv("CHROMEDRIVER_PATH"),
            "/usr/bin/chromedriver",
            which("chromedriver") or "",
        ):
            if chromedriver and Path(chromedriver).is_file():
                from selenium.webdriver.chrome.service import Service

                service = Service(chromedriver)
                break
        driver = webdriver.Chrome(service=service, options=options) if service else webdriver.Chrome(options=options)
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

    def __enter__(self) -> "ConubePortalAgent":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_access_token(self) -> str:
        if self.session_token and len(self.session_token) > 15:
            return self.session_token
        token = self._read_access_token()
        if not token:
            raise RuntimeError("Sessao autenticada sem access token disponivel.")
        return token

    def _authenticated_api_get(self, path: str, *, api_version: str = "client", timeout: float = 25) -> Any:
        import requests

        token = self._get_access_token()
        base_url = f"{CONUBE_BASE_URL}/api/{api_version}".rstrip("/")
        response = requests.get(
            f"{base_url}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _authenticated_api_post(
        self,
        path: str,
        *,
        api_version: str = "client",
        timeout: float = 25,
        json_body: Any | None = None,
    ) -> Any:
        import requests

        token = self._get_access_token()
        base_url = f"{CONUBE_BASE_URL}/api/{api_version}".rstrip("/")
        response = requests.post(
            f"{base_url}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {token}"},
            json=json_body,
            timeout=timeout,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def get_period_status(self, period_end: str) -> dict[str, Any]:
        date = f"15-{period_end[5:7]}-{period_end[:4]}"
        payload = self._authenticated_api_get(f"checkPeriodo?date={date}")
        return payload if isinstance(payload, dict) else {}

    def get_period_close_preview(self, period_id: str) -> dict[str, Any]:
        payload = self._authenticated_api_get(f"tryToClosePeriodo?periodoId={period_id}")
        return payload if isinstance(payload, dict) else {}

    def close_period(self, period_id: str) -> dict[str, Any]:
        payload = self._authenticated_api_get(f"closePeriodo?periodoId={period_id}")
        return payload if isinstance(payload, dict) else {}

    def conclude_task(self, task: dict[str, Any]) -> dict[str, Any]:
        from specialized_agents.conube_remediation import _task_conclude_params

        task_id = str(task.get("_id") or task.get("id") or "").strip()
        if not task_id:
            raise RuntimeError("Tarefa sem identificador para conclusao.")
        query = _task_conclude_params(task)
        payload = self._authenticated_api_post(f"tarefas/{task_id}/concluir?{query}")
        return payload if isinstance(payload, dict) else {}

    def request_task_recalculation(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._authenticated_api_post(
            f"tarefas/{task_id}/solicitar-recalculo",
            json_body=payload or {},
        )
        return response if isinstance(response, dict) else {}

    def _body_text(self) -> str:
        try:
            return (
                self.driver.find_element("tag name", "body").text or ""
            ).strip()
        except Exception:
            return ""

    def _set_input(self, selectors: list[tuple[str, str]], value: str) -> bool:
        deadline = time.monotonic() + 30.0
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

    def _login_success_payload(self, *, authenticated: bool) -> dict[str, Any]:
        token = self._read_access_token()
        return {
            "authenticated": authenticated,
            "token_present": bool(token),
            "current_url": getattr(self.driver, "current_url", ""),
            "title": getattr(self.driver, "title", ""),
            "menu_items": self._collect_menu_items(),
            "body_excerpt": self._body_text()[:500],
        }

    def login(self) -> dict[str, Any]:
        self.driver.get(CONUBE_LOGIN_URL)
        time.sleep(1.5)
        cached_token = self._read_access_token()
        if cached_token:
            return self._login_success_payload(authenticated=True)

        if self._is_authenticated_view():
            return self._login_success_payload(authenticated=True)

        field_error: RuntimeError | None = None
        for attempt in range(3):
            self.driver.get(CONUBE_LOGIN_URL)
            time.sleep(2.0 + attempt)
            cached_token = self._read_access_token()
            if cached_token:
                return self._login_success_payload(authenticated=True)
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
                if attempt < 2:
                    continue
                return {
                    **self._login_success_payload(authenticated=False),
                    "failure_reason": str(field_error),
                }

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
            if attempt == 2:
                return {
                    **self._login_success_payload(authenticated=False),
                    "failure_reason": "Nao foi possivel submeter o login na Conube.",
                }
        else:
            return {
                **self._login_success_payload(authenticated=False),
                "failure_reason": str(field_error or "Falha ao iniciar automacao de login da Conube."),
            }

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
            return {
                **self._login_success_payload(authenticated=False),
                "failure_reason": "A Conube rejeitou as credenciais informadas.",
            }
        if "token de seguranca" in body_text:
            return {
                **self._login_success_payload(authenticated=False),
                "failure_reason": "A Conube solicitou token adicional por email; automacao interrompida.",
            }

        return self._login_success_payload(authenticated=authenticated)


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


def _require_action_token(request: Request, explicit_token: str | None = None) -> None:
    expected = CONUBE_ACTION_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="CONUBE_ACTION_TOKEN nao configurado para acoes de remediacao.",
        )
    provided = (explicit_token or request.headers.get("x-conube-action-token") or "").strip()
    if provided != expected:
        raise HTTPException(status_code=403, detail="Token de acao invalido para remediacao da Conube.")


def _execute_remediation(
    *,
    headless: bool | None,
    close_periods_limit: int,
    run_client_tasks: bool,
    run_selenium_balances: bool = True,
    run_selenium_tasks: bool = True,
    selenium_balances_limit: int = 12,
    selenium_tasks_limit: int = 20,
) -> dict[str, Any]:
    from specialized_agents.conube_remediation import run_remediation

    agent = _build_agent(headless)
    try:
        return run_remediation(
            agent,
            close_periods_limit=close_periods_limit,
            run_client_tasks=run_client_tasks,
            run_selenium_balances=run_selenium_balances,
            run_selenium_tasks=run_selenium_tasks,
            selenium_balances_limit=selenium_balances_limit,
            selenium_tasks_limit=selenium_tasks_limit,
        )
    finally:
        agent.close()


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


def _conube_langgraph():
    """Retorna ConubeAgentLangraph se CONUBE_AGENT_VERSION=v2, None caso contrário."""
    if os.getenv("CONUBE_AGENT_VERSION", "v1") == "v2":
        from specialized_agents.conube_agent_langgraph import get_conube_agent_langgraph
        return get_conube_agent_langgraph()
    return None


@router.post("/session/test-login")
def conube_test_login(payload: ConubeActionRequest | None = None) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.test_login(payload)
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


@router.get("/reports/daily-summary/cached")
def conube_daily_summary_cached() -> dict[str, Any]:
    payload = _read_cached_report()
    if payload is None:
        raise HTTPException(status_code=404, detail="Nenhum relatório em cache.")
    return payload


@router.get("/reports/daily-summary")
def conube_daily_summary_report(
    headless: bool | None = None,
    refresh: bool = False,
    use_ollama: bool = True,
) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.daily_summary(headless=headless, refresh=refresh, use_ollama=use_ollama)
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


@router.get("/dashboard/operational-summary")
def conube_operational_summary(headless: bool | None = None) -> dict[str, Any]:
    from specialized_agents.conube_remediation import fetch_operational_summary

    agent = _build_agent(headless)
    try:
        return fetch_operational_summary(agent)
    finally:
        agent.close()


@router.post("/tasks/remediate-client-pending")
def conube_remediate_client_pending(payload: ConubeActionRequest | None = None) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.remediate_client_pending(payload)
    from specialized_agents.conube_remediation import remediate_client_pending_tasks

    agent = _build_agent(payload.headless if payload else None)
    try:
        return remediate_client_pending_tasks(agent)
    finally:
        agent.close()


@router.post("/company/close-overdue-balances")
def conube_close_overdue_balances(payload: ConubeCloseBalancesRequest) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.close_overdue_balances(payload)
    from specialized_agents.conube_selenium import close_overdue_balances_without_movement

    agent = _build_agent(payload.headless)
    try:
        return close_overdue_balances_without_movement(agent, limit=payload.limit)
    finally:
        agent.close()


@router.post("/company/close-open-financial-periods")
def conube_close_open_financial_periods(payload: ConubeClosePeriodsRequest) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.close_open_financial_periods(payload)
    from specialized_agents.conube_remediation import close_open_financial_periods

    agent = _build_agent(payload.headless)
    try:
        return close_open_financial_periods(agent, limit=payload.limit)
    finally:
        agent.close()


@router.post("/actions/run-remediation")
def conube_run_remediation(payload: ConubeRunRemediationRequest, request: Request) -> dict[str, Any]:
    _require_action_token(request)
    if lg := _conube_langgraph():
        return lg.run_remediation(payload)
    return _execute_remediation(
        headless=payload.headless,
        close_periods_limit=payload.close_periods_limit,
        run_client_tasks=payload.run_client_tasks,
        run_selenium_balances=payload.run_selenium_balances,
        run_selenium_tasks=payload.run_selenium_tasks,
        selenium_balances_limit=payload.selenium_balances_limit,
        selenium_tasks_limit=payload.selenium_tasks_limit,
    )


@router.get("/actions/run-remediation")
def conube_run_remediation_get(
    request: Request,
    headless: bool | None = None,
    close_periods_limit: int = 12,
    run_client_tasks: bool = True,
    token: str | None = None,
) -> dict[str, Any]:
    _require_action_token(request, explicit_token=token)
    if lg := _conube_langgraph():
        payload = ConubeRunRemediationRequest(
            headless=headless,
            close_periods_limit=close_periods_limit,
            run_client_tasks=run_client_tasks,
        )
        return lg.run_remediation(payload)
    return _execute_remediation(
        headless=headless,
        close_periods_limit=close_periods_limit,
        run_client_tasks=run_client_tasks,
    )


@router.get("/billing/pending")
def conube_billing_pending(headless: bool | None = None, with_payment_data: bool = True) -> dict[str, Any]:
    """Cobranças pendentes (faturas Vindi) — somente leitura."""
    from specialized_agents.conube_billing import fetch_pending_billing

    agent = _build_agent(headless)
    try:
        return fetch_pending_billing(agent, with_payment_data=with_payment_data)
    finally:
        agent.close()


@router.post("/billing/pay-pending")
def conube_billing_pay_pending(payload: ConubePayBillingRequest, request: Request) -> dict[str, Any]:
    """Paga boletos pendentes via Mercado Pago (dinheiro real — exige token de ação).

    Com CONUBE_AGENT_VERSION=v2 o pagamento vira intent risk=high com
    aprovação Telegram; em v1 executa direto (protegido pelo token).
    """
    _require_action_token(request)
    if lg := _conube_langgraph():
        return lg.pay_billing_boleto(payload)
    from specialized_agents.conube_billing import pay_pending_charges

    agent = _build_agent(payload.headless)
    try:
        return pay_pending_charges(agent, dry_run=payload.dry_run, limit=payload.limit)
    finally:
        agent.close()


@router.post("/tasks/remediate-pending-selenium")
def conube_remediate_pending_selenium(payload: ConubeSeleniumTasksRequest) -> dict[str, Any]:
    if lg := _conube_langgraph():
        return lg.remediate_pending_selenium(payload)
    from specialized_agents.conube_selenium import remediate_pending_tasks_selenium

    agent = _build_agent(payload.headless)
    try:
        return remediate_pending_tasks_selenium(agent, limit=payload.limit)
    finally:
        agent.close()
