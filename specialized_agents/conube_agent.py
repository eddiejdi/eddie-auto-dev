"""Agente de automacao para operacoes basicas no portal da Conube."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from calendar import monthrange
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests

from tools.secrets_agent_client import get_secrets_agent_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conube", tags=["conube"])

CONUBE_BASE_URL = os.getenv("CONUBE_BASE_URL", "https://app.conube.com.br").rstrip("/")
CONUBE_LOGIN_URL = os.getenv("CONUBE_LOGIN_URL", f"{CONUBE_BASE_URL}/login")
CONUBE_DASHBOARD_URL = os.getenv("CONUBE_DASHBOARD_URL", "https://dynamo.conube.com.br/").rstrip("/") + "/"
CONUBE_FECHAMENTOS_URL = os.getenv(
    "CONUBE_FECHAMENTOS_URL",
    f"{CONUBE_BASE_URL}/contabil/fechamentos-contabeis?&cd=0",
)
CONUBE_EMITIR_NF_URL = os.getenv(
    "CONUBE_EMITIR_NF_URL",
    f"{CONUBE_BASE_URL}/notas-fiscais/emitir-nota-fiscal?&cd=0",
)
CONUBE_TODAS_NOTAS_URL = os.getenv(
    "CONUBE_TODAS_NOTAS_URL",
    f"{CONUBE_BASE_URL}/notas-fiscais/todas-as-notas?&cd=0",
)
CONUBE_EMAIL = os.getenv("CONUBE_EMAIL", "").strip()
CONUBE_PASSWORD = os.getenv("CONUBE_PASSWORD", "").strip()
CONUBE_SECRET_NAME = os.getenv("CONUBE_SECRET_NAME", "conube/rpa4all").strip()
CONUBE_HEADLESS = os.getenv("CONUBE_HEADLESS", "1").lower() not in {"0", "false", "off", "no"}
CONUBE_TIMEOUT_SECONDS = float(os.getenv("CONUBE_TIMEOUT_SECONDS", "25"))


class ConubeActionRequest(BaseModel):
    headless: bool | None = None


class ConubeCloseBalancesRequest(BaseModel):
    headless: bool | None = None
    limit: int = 12


class ConubeClosePeriodsRequest(BaseModel):
    headless: bool | None = None
    limit: int = 12


class ConubeFinancialPeriodsRequest(BaseModel):
    headless: bool | None = None
    months_back: int = 12


def _candidate_secret_names() -> list[str]:
    names = [item.strip() for item in os.getenv("CONUBE_SECRET_NAMES", "").split(",") if item.strip()]
    if CONUBE_SECRET_NAME:
        names.append(CONUBE_SECRET_NAME)
    unique: list[str] = []
    for name in names:
        if name not in unique:
            unique.append(name)
    return unique


def load_conube_credentials() -> tuple[str, str]:
    """Resolve credenciais via env vars ou Secrets Agent."""
    if CONUBE_EMAIL and CONUBE_PASSWORD:
        return CONUBE_EMAIL, CONUBE_PASSWORD

    client = get_secrets_agent_client()
    try:
        for secret_name in _candidate_secret_names():
            email = (
                client.get_local_secret(secret_name, field="email")
                or client.get_secret_field(secret_name, "email")
                or client.get_local_secret(secret_name, field="username")
                or client.get_secret_field(secret_name, "username")
            )
            password = (
                client.get_local_secret(secret_name, field="password")
                or client.get_secret_field(secret_name, "password")
            )
            if email and password:
                return email.strip(), password.strip()
    finally:
        client.close()

    raise RuntimeError(
        "Credenciais da Conube nao configuradas. Defina CONUBE_EMAIL/CONUBE_PASSWORD "
        "ou armazene email/password no secret conube/rpa4all."
    )


@dataclass
class ConubeSessionResult:
    success: bool
    current_url: str
    title: str
    menu_items: list[str]
    visible_text: str
    document_links: list[dict[str, str]]
    service_items: list[str]


@dataclass
class ConubeBalanceCloseResult:
    competence: str
    status: str
    message: str


class ConubePortalAgent:
    """Automacao Selenium para tarefas administrativas na Conube."""

    def __init__(
        self,
        email: str,
        password: str,
        *,
        headless: bool = CONUBE_HEADLESS,
        timeout_seconds: float = CONUBE_TIMEOUT_SECONDS,
        download_dir: str | None = None,
    ) -> None:
        self.email = email
        self.password = password
        self.headless = headless
        self.timeout_seconds = timeout_seconds
        self.download_dir = download_dir or tempfile.mkdtemp(prefix="conube-agent-")
        self.driver = None
        self.session_token: str = ""

    def __enter__(self) -> "ConubePortalAgent":
        self.driver = self._create_driver()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                logger.debug("Falha ao encerrar webdriver da Conube", exc_info=True)

    def _create_driver(self):
        try:
            from selenium import webdriver
        except ImportError as exc:
            raise RuntimeError("selenium nao instalado neste ambiente") from exc

        options = webdriver.ChromeOptions()
        options.page_load_strategy = "eager"
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1480,1200")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        prefs = {
            "download.default_directory": str(Path(self.download_dir).resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        }
        options.add_experimental_option("prefs", prefs)
        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(self.timeout_seconds)
        except Exception:
            logger.debug("Nao foi possivel configurar page load timeout da Conube", exc_info=True)
        return driver

    def _wait(self, condition):
        from selenium.webdriver.support.ui import WebDriverWait

        return WebDriverWait(self.driver, self.timeout_seconds).until(condition)

    def _wait_for_document_ready(self) -> None:
        self._wait(lambda driver: driver.execute_script("return document.readyState") == "complete")

    def _find_visible_elements(self, xpath: str) -> list[Any]:
        from selenium.webdriver.common.by import By

        elements = self.driver.find_elements(By.XPATH, xpath)
        return [element for element in elements if element.is_displayed()]

    def _click_first_text(self, *texts: str) -> bool:
        normalized_texts = [text.strip() for text in texts if text.strip()]
        if not normalized_texts:
            return False

        for text in normalized_texts:
            xpath = (
                "//*[self::a or self::button or @role='button' or self::span or self::div]"
                f"[normalize-space(.)=\"{text}\" or contains(normalize-space(.), \"{text}\")]"
            )
            for element in self._find_visible_elements(xpath):
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    continue
        return False

    def _set_input(self, selectors: list[tuple[str, str]], value: str) -> bool:
        from selenium.webdriver.common.by import By

        for by, locator in selectors:
            try:
                element = self.driver.find_element(getattr(By, by), locator)
            except Exception:
                continue
            if not element.is_displayed():
                continue
            element.clear()
            element.send_keys(value)
            return True
        return False

    def login(self) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        self.driver.get(CONUBE_LOGIN_URL)
        self._wait_for_document_ready()
        self._wait(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='email']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")),
            )
        )

        email_ok = self._set_input(
            [
                ("CSS_SELECTOR", "input[type='email']"),
                ("CSS_SELECTOR", "input[name='email']"),
                ("CSS_SELECTOR", "input[autocomplete='username']"),
                ("XPATH", "//input[contains(@placeholder, 'mail') or contains(@placeholder, 'E-mail')]"),
            ],
            self.email,
        )
        password_ok = self._set_input(
            [
                ("CSS_SELECTOR", "input[type='password']"),
                ("CSS_SELECTOR", "input[name='password']"),
                ("CSS_SELECTOR", "input[autocomplete='current-password']"),
                ("XPATH", "//input[contains(@placeholder, 'senha') or contains(@placeholder, 'Senha')]"),
            ],
            self.password,
        )
        if not email_ok or not password_ok:
            raise RuntimeError("Nao foi possivel localizar os campos de login da Conube.")

        try:
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].click();", submit_button)
        except Exception:
            if not self._click_first_text("Entrar", "Acessar", "Login"):
                raise RuntimeError("Nao foi possivel submeter o login na Conube.")

        def _logged_in(driver) -> bool:
            token = driver.execute_script("return window.localStorage.getItem('access_token') || ''")
            if token and len(token) > 15:
                return True
            if "login" not in (driver.current_url or "").lower():
                return True
            body_text = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
            failure_markers = [
                "credenciais invalidas",
                "e-mail ou senha invalidos",
                "e-mail ou senha inválidos",
                "senha incorreta",
                "nao autorizado",
                "token de seguranca",
            ]
            if any(marker in body_text for marker in failure_markers):
                return True
            return False

        self._wait(_logged_in)

        body_text = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
        if any(
            marker in body_text
            for marker in [
                "credenciais invalidas",
                "e-mail ou senha invalidos",
                "e-mail ou senha inválidos",
                "senha incorreta",
                "nao autorizado",
            ]
        ):
            raise RuntimeError("A Conube rejeitou as credenciais informadas.")
        if "token de seguranca" in body_text:
            raise RuntimeError("A Conube solicitou token adicional por email; automacao interrompida.")
        token = self.driver.execute_script("return window.localStorage.getItem('access_token') || ''")
        if not token or len(token) <= 15:
            raise RuntimeError("A Conube nao concluiu a autenticacao; token de acesso nao foi emitido.")
        self.session_token = token

        # A Conube pode manter a URL /login e renderizar o app de forma assíncrona.
        # Se o token existe, consideramos a sessão autenticada mesmo sem os marcadores do menu.
        try:
            self._wait(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Minha empresa')]")),
                    EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Tarefas')]")),
                    EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Notas fiscais')]")),
                )
            )
        except Exception:
            logger.info("Login autenticado por token, sem marcadores visuais estáveis da dashboard.")

    def _get_access_token(self) -> str:
        token = self.driver.execute_script("return window.localStorage.getItem('access_token') || ''")
        if token and len(token) > 15:
            self.session_token = token
            return token
        token = self.session_token
        if not token or len(token) <= 15:
            raise RuntimeError("Sessao autenticada sem access token disponivel.")
        return token

    def _authenticated_api_get(self, path: str, *, api_version: str = "client", timeout: float = 25) -> Any:
        token = self._get_access_token()
        base_url = f"{CONUBE_BASE_URL}/api/{api_version}".rstrip("/")
        response = requests.get(
            f"{base_url}/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    def _collect_menu_items(self) -> list[str]:
        from selenium.webdriver.common.by import By

        items: list[str] = []
        selectors = [
            (By.CSS_SELECTOR, "aside a"),
            (By.CSS_SELECTOR, "nav a"),
            (By.XPATH, "//aside//*[self::a or self::button or self::span]"),
        ]
        for by, selector in selectors:
            for element in self.driver.find_elements(by, selector):
                text = (element.text or "").strip()
                if text and text not in items:
                    items.append(text)
        return items[:20]

    def _collect_links(self) -> list[dict[str, str]]:
        from selenium.webdriver.common.by import By

        links: list[dict[str, str]] = []
        for element in self.driver.find_elements(By.TAG_NAME, "a"):
            text = (element.text or "").strip()
            href = (element.get_attribute("href") or "").strip()
            if href and text:
                links.append({"label": text, "href": href})
        return links

    def _visible_text(self) -> str:
        from selenium.webdriver.common.by import By

        body = self.driver.find_element(By.TAG_NAME, "body").text or ""
        return " ".join(body.split())

    def _open_authenticated_route(self, url: str, markers: list[str], sleep_seconds: float = 8.0) -> str:
        self.driver.get(url)
        self._wait_for_document_ready()
        if sleep_seconds > 0:
            import time

            time.sleep(sleep_seconds)
        self._wait(
            lambda driver: any(
                marker.lower() in (driver.find_element("tag name", "body").text or "").lower()
                for marker in markers
            )
        )
        return self._visible_text()

    def _collect_dashboard_periods(self, visible_text: str) -> list[dict[str, str]]:
        months = {
            "janeiro",
            "fevereiro",
            "março",
            "marco",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        }
        lines = [" ".join(line.split()) for line in visible_text.splitlines() if line.strip()]
        items: list[dict[str, str]] = []
        for index, line in enumerate(lines):
            if line.split(" ", 1)[0].lower() not in months:
                continue
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            merged = f"{line} {next_line}".lower()
            status = "desconhecido"
            if "em atraso" in merged:
                status = "em_atraso"
            elif "próximo do encerramento" in merged or "proximo do encerramento" in merged:
                status = "proximo_do_encerramento"
            elif "pago" in merged:
                status = "pago"
            items.append({"label": line, "details": next_line, "status": status})
        return items

    def _normalize_pending_docs(self, docs: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in docs:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "source": source,
                    "id": item.get("_id") or item.get("id"),
                    "subject": item.get("Assunto") or item.get("assunto") or item.get("nome"),
                    "status": item.get("Status") or item.get("status"),
                    "due_date": item.get("Vencimento") or item.get("vencimento"),
                    "month": item.get("mesCompetencia"),
                    "year": item.get("anoCompetencia"),
                    "responsible": item.get("Responsavel") or item.get("responsavel"),
                }
            )
        return items

    def _normalize_last_periods(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("_id") or item.get("id"),
                    "status": item.get("status"),
                    "period_end": item.get("dataFimPeriodo"),
                }
            )
        return normalized

    def _summarize_certificate(self, certificates: list[dict[str, Any]]) -> dict[str, Any]:
        if not certificates:
            return {"present": False, "expired": None, "latest_expiration": None}
        expirations = []
        for item in certificates:
            if not isinstance(item, dict):
                continue
            expiration = item.get("fimValidade")
            if expiration:
                expirations.append(expiration)
        latest_expiration = max(expirations) if expirations else None
        expired = None
        if latest_expiration:
            try:
                expired = datetime.fromisoformat(latest_expiration.replace("Z", "+00:00")) < datetime.now(timezone.utc)
            except ValueError:
                expired = None
        return {
            "present": True,
            "expired": expired,
            "latest_expiration": latest_expiration,
        }

    def _period_key_from_date(self, value: str | None) -> tuple[int, int] | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.year, parsed.month

    def _open_period_keys(self, periods: list[dict[str, Any]]) -> set[tuple[int, int]]:
        keys: set[tuple[int, int]] = set()
        for item in periods:
            if str(item.get("status") or "").lower() != "aberto":
                continue
            key = self._period_key_from_date(item.get("period_end"))
            if key:
                keys.add(key)
        return keys

    def _dedupe_pending_items(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        preferred_source_rank = {"tarefas": 0, "impostos": 1, "impostos_obrigacoes": 2}
        deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for item in items:
            key = (
                item.get("subject"),
                item.get("due_date"),
                item.get("month"),
                item.get("year"),
                item.get("responsible"),
            )
            current = deduped.get(key)
            if current is None:
                deduped[key] = item
                continue
            current_rank = preferred_source_rank.get(str(current.get("source")), 99)
            new_rank = preferred_source_rank.get(str(item.get("source")), 99)
            if new_rank < current_rank:
                deduped[key] = item
        return list(deduped.values())

    def _filter_items_for_open_periods(
        self,
        items: list[dict[str, Any]],
        period_keys: set[tuple[int, int]],
    ) -> list[dict[str, Any]]:
        if not period_keys:
            return items
        filtered = []
        for item in items:
            year = item.get("year")
            month = item.get("month")
            if isinstance(year, int) and isinstance(month, int) and (year, month) in period_keys:
                filtered.append(item)
        return filtered

    def _format_period_label(self, period_end: str | None) -> str:
        key = self._period_key_from_date(period_end)
        if not key:
            return period_end or "periodo-desconhecido"
        year, month = key
        return f"{year:04d}-{month:02d}"

    def _period_key_from_blocker(self, item: dict[str, Any]) -> tuple[int, int] | None:
        month_value = str(item.get("mes") or "").strip().lower()
        year_value = item.get("ano")
        month_map = {
            "janeiro": 1,
            "fevereiro": 2,
            "marco": 3,
            "março": 3,
            "abril": 4,
            "maio": 5,
            "junho": 6,
            "julho": 7,
            "agosto": 8,
            "setembro": 9,
            "outubro": 10,
            "novembro": 11,
            "dezembro": 12,
        }
        month = month_map.get(month_value)
        try:
            year = int(year_value)
        except (TypeError, ValueError):
            return None
        if not month:
            return None
        return year, month

    def _sorted_open_periods(self, periods: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
            key = self._period_key_from_date(item.get("period_end"))
            if key:
                return key[0], key[1], ""
            return (9999, 12, str(item.get("period_end") or ""))

        open_periods = [item for item in periods if str(item.get("status") or "").lower() == "aberto"]
        open_periods.sort(key=sort_key)
        return open_periods

    def _previous_period_end(self, period_end: str) -> str | None:
        key = self._period_key_from_date(period_end)
        if not key:
            return None
        year, month = key
        if month == 1:
            year -= 1
            month = 12
        else:
            month -= 1
        last_day = monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-{last_day:02d}T23:59:59.999Z"

    def _expand_with_historical_open_periods(self, periods: list[dict[str, Any]], max_months: int = 12) -> list[dict[str, Any]]:
        open_periods = self._sorted_open_periods(periods)
        if not open_periods:
            return open_periods

        earliest = open_periods[0].get("period_end")
        current = earliest if isinstance(earliest, str) else None
        known_keys = {self._period_key_from_date(item.get("period_end")) for item in open_periods}
        extra: list[dict[str, Any]] = []
        consecutive_closed = 0

        for _ in range(max_months):
            current = self._previous_period_end(current or "")
            if not current:
                break
            status = self.get_period_status(current)
            item = {
                "id": status.get("_id"),
                "status": status.get("Status"),
                "period_end": current,
            }
            key = self._period_key_from_date(current)
            if key in known_keys:
                continue
            known_keys.add(key)
            if str(status.get("Status") or "").lower() == "aberto":
                extra.append(item)
                consecutive_closed = 0
            else:
                consecutive_closed += 1
                if consecutive_closed >= 2:
                    break

        return self._sorted_open_periods(open_periods + extra)

    def financial_periods_audit(self, months_back: int = 12) -> dict[str, Any]:
        if months_back < 1:
            raise RuntimeError("months_back precisa ser maior que zero.")

        self.login()
        raw_periods = self._authenticated_api_get("transactions/last-periods", api_version="client/v2")
        periods = self._normalize_last_periods(raw_periods if isinstance(raw_periods, list) else [])
        expanded = self._expand_with_historical_open_periods(periods, max_months=months_back)
        if not expanded:
            return {"status": "ok", "periods": [], "open_periods_count": 0, "closed_periods_count": 0}

        earliest = expanded[0].get("period_end")
        current = earliest if isinstance(earliest, str) else None
        audited: list[dict[str, Any]] = []
        seen: set[tuple[int, int] | None] = set()

        for _ in range(months_back):
            if not current:
                break
            key = self._period_key_from_date(current)
            if key in seen:
                current = self._previous_period_end(current)
                continue
            seen.add(key)
            status = self.get_period_status(current)
            logs = status.get("logs") or []
            audited.append(
                {
                    "period": f"{int(status.get('Ano', 0)):04d}-{int(status.get('Mes', 0)):02d}",
                    "period_end": current,
                    "period_id": status.get("_id"),
                    "status": status.get("Status"),
                    "updated_at": status.get("updatedAt"),
                    "attachments_count": len(status.get("_anexos") or []),
                    "logs_count": len(logs),
                    "last_log": logs[-1] if logs else None,
                }
            )
            current = self._previous_period_end(current)

        open_count = len([item for item in audited if str(item.get("status") or "").lower() == "aberto"])
        closed_count = len([item for item in audited if str(item.get("status") or "").lower() == "fechado"])
        return {
            "status": "ok",
            "periods": audited,
            "open_periods_count": open_count,
            "closed_periods_count": closed_count,
        }

    def get_period_status(self, period_end: str) -> dict[str, Any]:
        date = f"15-{period_end[5:7]}-{period_end[:4]}"
        return self._authenticated_api_get(f"checkPeriodo?date={date}")

    def get_period_close_preview(self, period_id: str) -> dict[str, Any]:
        return self._authenticated_api_get(f"tryToClosePeriodo?periodoId={period_id}")

    def close_period(self, period_id: str) -> dict[str, Any]:
        return self._authenticated_api_get(f"closePeriodo?periodoId={period_id}")

    def close_open_financial_periods(self, limit: int = 12) -> dict[str, Any]:
        if limit < 1:
            raise RuntimeError("O limite informado para fechamento de periodos precisa ser maior que zero.")

        self.login()
        raw_periods = self._authenticated_api_get("transactions/last-periods", api_version="client/v2")
        periods = self._normalize_last_periods(raw_periods if isinstance(raw_periods, list) else [])
        open_periods = self._expand_with_historical_open_periods(periods)

        results: list[dict[str, Any]] = []
        for period in open_periods[:limit]:
            period_end = str(period.get("period_end") or "").strip()
            if not period_end:
                results.append(
                    {
                        "period": self._format_period_label(period_end),
                        "status": "error",
                        "message": "Periodo sem data final.",
                    }
                )
                continue

            status_before = self.get_period_status(period_end)
            period_id = str(status_before.get("_id") or period.get("id") or "").strip()
            if not period_id:
                results.append(
                    {
                        "period": self._format_period_label(period_end),
                        "status": "error",
                        "message": "Periodo sem identificador resolvido pelo checkPeriodo.",
                    }
                )
                continue
            if str(status_before.get("Status") or "").lower() == "fechado":
                results.append(
                    {
                        "period": self._format_period_label(period_end),
                        "period_id": period_id,
                        "status": "already_closed",
                        "blockers": blocker_labels,
                    }
                )
                continue

            preview = self.get_period_close_preview(period_id)
            blockers = preview if isinstance(preview, list) else preview.get("message") if isinstance(preview, dict) else []
            blockers = blockers if isinstance(blockers, list) else []
            current_key = self._period_key_from_date(period_end)
            blocker_labels = [
                f"{item.get('mes')} - {item.get('ano')}"
                for item in blockers
                if isinstance(item, dict) and item.get("mes") and item.get("ano")
            ]
            blocker_keys = {key for item in blockers if isinstance(item, dict) for key in [self._period_key_from_blocker(item)] if key}
            has_external_blockers = bool(current_key and any(key != current_key for key in blocker_keys))
            if has_external_blockers:
                results.append(
                    {
                        "period": self._format_period_label(period_end),
                        "period_id": period_id,
                        "status": "blocked",
                        "blockers": blocker_labels,
                    }
                )
                continue

            close_response = self.close_period(period_id)
            status_after = self.get_period_status(period_end)
            final_status = str(status_after.get("Status") or "")
            results.append(
                {
                    "period": self._format_period_label(period_end),
                    "period_id": period_id,
                    "status": "closed" if final_status.lower() == "fechado" else "unknown",
                    "status_before": status_before.get("Status"),
                    "status_after": final_status,
                    "blockers": blocker_labels,
                    "close_response": close_response,
                }
            )

        processed = len([item for item in results if item.get("status") == "closed"])
        blocked = len([item for item in results if item.get("status") == "blocked"])
        return {
            "status": "ok" if processed or not blocked else "warning",
            "processed": processed,
            "blocked": blocked,
            "results": results,
        }

    def _collect_pending_balance_rows(self) -> list[Any]:
        from selenium.webdriver.common.by import By

        selectors = [
            "//tr[.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
            "//*[contains(@class, 'pend') or contains(@class, 'late')]",
            "//div[.//*[contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'atras') or contains(translate(., 'ATRASOPENDENTE', 'atrasopendente'), 'pendent')]]",
        ]
        rows: list[Any] = []
        for xpath in selectors:
            try:
                found = self.driver.find_elements(By.XPATH, xpath)
            except Exception:
                continue
            for item in found:
                if item.is_displayed() and item not in rows:
                    rows.append(item)
        return rows

    def _extract_competence_label(self, element: Any) -> str:
        text = " ".join((element.text or "").split())
        if not text:
            return "competencia-sem-identificacao"
        return text[:120]

    def _mark_current_balance_without_movement(self) -> None:
        from selenium.webdriver.common.by import By

        if not self._click_first_text(
            "Sem movimentacao",
            "Sem movimentação",
            "Nao houve movimentacao",
            "Não houve movimentação",
            "Inativa",
            "Sem movimento",
        ):
            checkbox_selectors = [
                "//input[@type='checkbox' and (contains(@name, 'mov') or contains(@id, 'mov'))]",
                "//label[contains(., 'Sem moviment')]/preceding::input[1]",
                "//label[contains(., 'Nao houve moviment')]/preceding::input[1]",
            ]
            toggled = False
            for xpath in checkbox_selectors:
                for element in self._find_visible_elements(xpath):
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                        toggled = True
                        break
                    except Exception:
                        continue
                if toggled:
                    break
            if not toggled:
                raise RuntimeError("Nao foi possivel localizar a opcao sem movimentacao.")

        if not self._click_first_text(
            "Encerrar balanco",
            "Encerrar balanço",
            "Fechar balanco",
            "Fechar balanço",
            "Salvar",
            "Confirmar",
        ):
            try:
                self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            except Exception as exc:
                raise RuntimeError("Nao foi possivel confirmar o encerramento do balanco.") from exc

    def close_overdue_balances_without_movement(self, limit: int = 12) -> dict[str, Any]:
        if limit < 1:
            raise RuntimeError("O limite informado para fechamento precisa ser maior que zero.")

        self.login()
        self.driver.get(CONUBE_FECHAMENTOS_URL)
        self._wait(lambda driver: driver.execute_script("return document.readyState") == "complete")
        self._wait(
            lambda driver: any(
                marker in (driver.find_element("tag name", "body").text or "").lower()
                for marker in [
                    "fechamentos contábeis",
                    "fechamentos contabeis",
                    "não há nada por aqui",
                    "nao ha nada por aqui",
                    "competência",
                    "competencia",
                ]
            )
        )

        body_text = (self.driver.find_element("tag name", "body").text or "").lower()
        if "não há nada por aqui" in body_text or "nao ha nada por aqui" in body_text:
            return {
                "status": "ok",
                "processed": 0,
                "results": [],
                "message": "Nenhum fechamento contábil pendente encontrado.",
            }

        results: list[dict[str, str]] = []
        pending_rows = self._collect_pending_balance_rows()
        if not pending_rows:
            return {
                "status": "ok",
                "processed": 0,
                "results": [],
                "message": "Nenhum balanco pendente encontrado.",
            }

        for row in pending_rows[:limit]:
            competence = self._extract_competence_label(row)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
                try:
                    row.click()
                except Exception:
                    action_clicked = False
                    for xpath in [
                        ".//*[self::a or self::button][contains(., 'Abrir') or contains(., 'Editar') or contains(., 'Tratar')]",
                        ".//*[self::a or self::button][contains(., 'Pend') or contains(., 'Atras')]",
                    ]:
                        try:
                            action = row.find_element("xpath", xpath)
                            self.driver.execute_script("arguments[0].click();", action)
                            action_clicked = True
                            break
                        except Exception:
                            continue
                    if not action_clicked:
                        raise RuntimeError("Nao foi possivel abrir a competencia pendente.")

                self._mark_current_balance_without_movement()
                results.append(
                    ConubeBalanceCloseResult(
                        competence=competence,
                        status="closed",
                        message="Encerrado como sem movimentacao.",
                    ).__dict__
                )
            except Exception as exc:
                results.append(
                    ConubeBalanceCloseResult(
                        competence=competence,
                        status="error",
                        message=str(exc),
                    ).__dict__
                )

        processed = len([item for item in results if item["status"] == "closed"])
        return {
            "status": "ok" if processed else "warning",
            "processed": processed,
            "results": results,
        }

    def snapshot(self) -> ConubeSessionResult:
        menu_items = self._collect_menu_items()
        visible_text = self._visible_text()
        return ConubeSessionResult(
            success=True,
            current_url=self.driver.current_url,
            title=self.driver.title,
            menu_items=menu_items,
            visible_text=visible_text[:4000],
            document_links=[],
            service_items=[],
        )

    def company_overview(self) -> dict[str, Any]:
        self.login()
        self._click_first_text("Minha empresa")
        self._click_first_text("Dados gerais")
        result = self.snapshot()
        return {
            "status": "ok",
            "current_url": result.current_url,
            "title": result.title,
            "menu_items": result.menu_items,
            "summary": result.visible_text,
        }

    def company_documents(self) -> dict[str, Any]:
        self.login()
        self._click_first_text("Minha empresa")
        self._click_first_text("Dados gerais")
        self._click_first_text("Documentos")
        links = self._collect_links()
        filtered = [
            link
            for link in links
            if any(marker in link["label"].lower() for marker in ["cnpj", "contrato", "simples", "inscricao", "certificado"])
        ]
        result = self.snapshot()
        return {
            "status": "ok",
            "current_url": result.current_url,
            "title": result.title,
            "menu_items": result.menu_items,
            "documents": filtered,
            "summary": result.visible_text,
        }

    def contracted_services(self) -> dict[str, Any]:
        self.login()
        self._click_first_text("Minha empresa")
        self._click_first_text("Servicos contratados", "Serviços contratados")
        self._click_first_text("Contrato", "contrato")
        result = self.snapshot()
        service_items = [
            line.strip()
            for line in result.visible_text.split("  ")
            if line.strip() and any(token in line.lower() for token in ["contrato", "servic", "plano", "assin"])
        ]
        return {
            "status": "ok",
            "current_url": result.current_url,
            "title": result.title,
            "menu_items": result.menu_items,
            "services": service_items[:30],
            "summary": result.visible_text,
        }

    def billing_diagnostic(self) -> dict[str, Any]:
        self.login()

        routes = [
            ("emit_invoice", CONUBE_EMITIR_NF_URL, ["nota fiscal", "certificado", "e-cnpj", "emitir nota fiscal"]),
            ("list_invoices", CONUBE_TODAS_NOTAS_URL, ["nota fiscal", "certificado", "e-cnpj", "todas as notas"]),
        ]

        checks: list[dict[str, Any]] = []
        blocked_by_certificate = False

        for label, url, markers in routes:
            body_text = self._open_authenticated_route(url, markers)
            lower_text = body_text.lower()
            status = "ok"
            blocker = None
            if "certificado digital (e-cnpj) venceu" in lower_text or "certificado digital" in lower_text:
                status = "blocked"
                blocker = "expired_certificate"
                blocked_by_certificate = True
            if "não há nada por aqui" in lower_text or "nao ha nada por aqui" in lower_text:
                status = "empty"
            checks.append(
                {
                    "step": label,
                    "url": self.driver.current_url,
                    "status": status,
                    "blocker": blocker,
                    "summary": body_text[:2500],
                }
            )

        return {
            "status": "blocked" if blocked_by_certificate else "ok",
            "blocked_by_certificate": blocked_by_certificate,
            "certificate_message_detected": blocked_by_certificate,
            "checks": checks,
        }

    def dashboard_pending_items(self) -> dict[str, Any]:
        self.login()

        dashboard_text = ""
        dashboard_periods: list[dict[str, str]] = []
        dashboard_error: str | None = None
        try:
            dashboard_text = self._open_authenticated_route(
                CONUBE_DASHBOARD_URL,
                [
                    "contas & movimentações",
                    "contas e movimentações",
                    "seu certificado digital",
                    "emissão de nota fiscal",
                    "não há tarefas no momento",
                    "nao ha tarefas no momento",
                ],
                sleep_seconds=10.0,
            )
            dashboard_periods = self._collect_dashboard_periods(dashboard_text)
        except Exception as exc:
            dashboard_error = str(exc)

        api_checks: dict[str, Any] = {}
        api_errors: dict[str, str] = {}
        endpoints = {
            "transactions_last_periods": ("client/v2", "transactions/last-periods"),
            "tarefas": ("client", "tarefas?concluida=false&responsavel=&limit=20&sort=vencimento:asc"),
            "impostos": ("client", "impostos?concluida=false&limit=20&sort=vencimento:asc"),
            "impostos_obrigacoes": (
                "client",
                "impostos-obrigacoes-acessorias?concluida=false&responsavel=&limit=20&sort=vencimento:asc",
            ),
            "certificados": ("client", "empresa/certificados-digitais"),
        }
        for key, (version, path) in endpoints.items():
            try:
                api_checks[key] = self._authenticated_api_get(path, api_version=version)
            except Exception as exc:
                api_errors[key] = str(exc)

        normalized_pending_items: list[dict[str, Any]] = []
        for key in ("tarefas", "impostos", "impostos_obrigacoes"):
            payload = api_checks.get(key)
            if isinstance(payload, dict) and isinstance(payload.get("docs"), list):
                normalized_pending_items.extend(self._normalize_pending_docs(payload["docs"], key))

        return {
            "status": "ok",
            "dashboard_url": CONUBE_DASHBOARD_URL,
            "dashboard_loaded": bool(dashboard_text),
            "dashboard_error": dashboard_error,
            "certificate_alert": "certificado digital (e-cnpj) venceu" in dashboard_text.lower(),
            "dashboard_periods": dashboard_periods,
            "dashboard_summary": dashboard_text[:4000],
            "normalized_pending_items": normalized_pending_items,
            "api_checks": api_checks,
            "api_errors": api_errors,
        }

    def operational_summary(self) -> dict[str, Any]:
        pending = self.dashboard_pending_items()
        api_checks = pending.get("api_checks", {})

        periods = self._normalize_last_periods(api_checks.get("transactions_last_periods", []))
        pending_items = self._dedupe_pending_items(pending.get("normalized_pending_items", []))
        open_period_keys = self._open_period_keys(periods)

        overdue_items = [
            item
            for item in pending_items
            if str(item.get("status") or "").lower() in {"pendente", "atrasado", "aberto"}
        ]
        overdue_items.sort(key=lambda item: item.get("due_date") or "")
        relevant_items = self._filter_items_for_open_periods(overdue_items, open_period_keys)

        certificate = self._summarize_certificate(api_checks.get("certificados", []))

        summary = {
            "status": "ok",
            "open_periods_count": len(periods),
            "open_periods": periods[:12],
            "pending_items_count": len(pending_items),
            "overdue_items_count": len(overdue_items),
            "relevant_items_count": len(relevant_items),
            "relevant_open_period_items": relevant_items[:12],
            "top_overdue_items": overdue_items[:12],
            "certificate": certificate,
            "dashboard_loaded": pending.get("dashboard_loaded", False),
            "dashboard_error": pending.get("dashboard_error"),
        }
        return summary


def _run_agent(action: str, headless: bool | None = None) -> dict[str, Any]:
    email, password = load_conube_credentials()
    headless_mode = CONUBE_HEADLESS if headless is None else headless

    with ConubePortalAgent(email, password, headless=headless_mode) as agent:
        if action == "test-login":
            agent.login()
            result = agent.snapshot()
            return {
                "status": "ok",
                "current_url": result.current_url,
                "title": result.title,
                "menu_items": result.menu_items,
            }
        if action == "company-overview":
            return agent.company_overview()
        if action == "company-documents":
            return agent.company_documents()
        if action == "contracted-services":
            return agent.contracted_services()
        if action == "billing-diagnostic":
            return agent.billing_diagnostic()
        if action == "dashboard-pending-items":
            return agent.dashboard_pending_items()
        if action == "operational-summary":
            return agent.operational_summary()
        if action == "financial-periods-audit":
            raise RuntimeError("Acao financial-periods-audit requer months_back explicito.")
        if action == "close-open-financial-periods":
            raise RuntimeError("Acao close-open-financial-periods requer limit explicito.")
        if action == "close-overdue-balances":
            raise RuntimeError("Acao close-overdue-balances requer limit explicito.")
    raise RuntimeError(f"Acao desconhecida: {action}")


@router.get("/health")
def conube_health() -> dict[str, Any]:
    secret_names = _candidate_secret_names()
    credentials_ready = bool(CONUBE_EMAIL and CONUBE_PASSWORD)
    if not credentials_ready and secret_names:
        credentials_ready = True
    return {
        "status": "ok",
        "base_url": CONUBE_BASE_URL,
        "login_url": CONUBE_LOGIN_URL,
        "headless_default": CONUBE_HEADLESS,
        "credentials_configured": credentials_ready,
        "secret_names": secret_names,
    }


@router.post("/session/test-login")
def conube_test_login(payload: ConubeActionRequest | None = None) -> dict[str, Any]:
    try:
        return _run_agent("test-login", headless=payload.headless if payload else None)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/company/overview")
def conube_company_overview(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("company-overview", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/company/documents")
def conube_company_documents(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("company-documents", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/company/contracted-services")
def conube_contracted_services(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("contracted-services", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/billing/diagnostic")
def conube_billing_diagnostic(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("billing-diagnostic", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/dashboard/pending-items")
def conube_dashboard_pending_items(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("dashboard-pending-items", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/dashboard/operational-summary")
def conube_operational_summary(headless: bool | None = None) -> dict[str, Any]:
    try:
        return _run_agent("operational-summary", headless=headless)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/financial-periods")
def conube_financial_periods(payload: ConubeFinancialPeriodsRequest) -> dict[str, Any]:
    try:
        email, password = load_conube_credentials()
        headless_mode = CONUBE_HEADLESS if payload.headless is None else payload.headless
        with ConubePortalAgent(email, password, headless=headless_mode) as agent:
            return agent.financial_periods_audit(months_back=payload.months_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/close-overdue-balances")
def conube_close_overdue_balances(payload: ConubeCloseBalancesRequest) -> dict[str, Any]:
    try:
        email, password = load_conube_credentials()
        headless_mode = CONUBE_HEADLESS if payload.headless is None else payload.headless
        with ConubePortalAgent(email, password, headless=headless_mode) as agent:
            return agent.close_overdue_balances_without_movement(limit=payload.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/company/close-open-financial-periods")
def conube_close_open_financial_periods(payload: ConubeClosePeriodsRequest) -> dict[str, Any]:
    try:
        email, password = load_conube_credentials()
        headless_mode = CONUBE_HEADLESS if payload.headless is None else payload.headless
        with ConubePortalAgent(email, password, headless=headless_mode) as agent:
            return agent.close_open_financial_periods(limit=payload.limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
