"""Pagamento de boleto via Mercado Pago web ("Pagar contas") com Selenium.

A API pública do Mercado Pago não expõe pagamento de boletos de terceiros;
o rail disponível é o fluxo web autenticado. Este payer usa um perfil de
Chrome persistente (cookies de sessão sobrevivem entre execuções — mesmo
padrão da rotação Selenium do Telegram), então o login com 2FA é feito UMA
vez, manualmente, via ``--bootstrap``::

    MP_WEB_PAY_HEADLESS=0 python -m specialized_agents.banking.mercadopago_payer --bootstrap

Guardas de segurança:
  - só executa com MP_WEB_PAY_ENABLED=1 (padrão: desabilitado);
  - sessão expirada/tela de login → PayerUnavailableError (nunca digita senha);
  - todo pagamento grava screenshot do comprovante em
    ``agent_data/banking/receipts/``.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("eddie.banking.mercadopago_payer")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MP_WEB_PAY_ENABLED = os.getenv("MP_WEB_PAY_ENABLED", "0").lower() in {"1", "true", "on", "yes"}
MP_WEB_PAY_URL = os.getenv("MP_WEB_PAY_URL", "https://www.mercadopago.com.br/payment-agencies/bills")
MP_WEB_HOME_URL = os.getenv("MP_WEB_HOME_URL", "https://www.mercadopago.com.br/home")
MP_WEB_PROFILE_DIR = Path(
    os.getenv("MP_WEB_PROFILE_DIR", str(PROJECT_ROOT / "agent_data" / "banking" / "mp_chrome_profile"))
)
MP_WEB_RECEIPTS_DIR = Path(
    os.getenv("MP_WEB_RECEIPTS_DIR", str(PROJECT_ROOT / "agent_data" / "banking" / "receipts"))
)
MP_WEB_TIMEOUT = float(os.getenv("MP_WEB_TIMEOUT", "40"))


class PayerUnavailableError(Exception):
    """Payer não pode operar (feature desligada, sessão expirada, Chrome ausente)."""


def _chrome_binary() -> str | None:
    from specialized_agents.conube_agent import _chrome_binary as conube_chrome

    return conube_chrome()


class MercadoPagoWebPayer:
    """Paga boletos por linha digitável no Mercado Pago web."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        profile_dir: Path | None = None,
        timeout: float = MP_WEB_TIMEOUT,
    ):
        if headless is None:
            headless = os.getenv("MP_WEB_PAY_HEADLESS", "1").lower() not in {"0", "false", "off", "no"}
        self.headless = headless
        self.profile_dir = profile_dir or MP_WEB_PROFILE_DIR
        self.timeout = timeout
        self.driver: Any = None

    # ── infra ──────────────────────────────────────────────────────────────

    def _create_driver(self) -> Any:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        binary = _chrome_binary()
        if binary:
            options.binary_location = binary
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        return webdriver.Chrome(options=options)

    def _ensure_driver(self) -> None:
        if self.driver is None:
            self.driver = self._create_driver()

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self) -> "MercadoPagoWebPayer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _wait(self, condition: Any) -> Any:
        from selenium.webdriver.support.ui import WebDriverWait

        return WebDriverWait(self.driver, self.timeout).until(condition)

    def _body_text(self) -> str:
        try:
            return (self.driver.find_element("tag name", "body").text or "").strip()
        except Exception:
            return ""

    def _is_login_wall(self) -> bool:
        url = (self.driver.current_url or "").lower()
        if "/login" in url or "registration" in url or "auth.mercado" in url:
            return True
        body = self._body_text().lower()
        return "digite seu e-mail" in body or "criar conta" in body and "entrar" in body

    def _screenshot(self, label: str) -> str | None:
        try:
            MP_WEB_RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = MP_WEB_RECEIPTS_DIR / f"mp-{label}-{stamp}.png"
            self.driver.save_screenshot(str(path))
            return str(path)
        except Exception:
            return None

    def _click_first_text(self, *texts: str) -> bool:
        for text in texts:
            xpath = (
                "//*[self::a or self::button or @role='button' or self::span]"
                f"[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÂÊÔÃÕÇ',"
                f" 'abcdefghijklmnopqrstuvwxyzáéíóúâêôãõç'), \"{text.lower()}\")]"
            )
            try:
                elements = self.driver.find_elements("xpath", xpath)
            except Exception:
                continue
            for element in elements:
                try:
                    if not element.is_displayed():
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    self.driver.execute_script("arguments[0].click();", element)
                    time.sleep(1.0)
                    return True
                except Exception:
                    continue
        return False

    # ── API pública ────────────────────────────────────────────────────────

    def session_status(self) -> dict[str, Any]:
        """Verifica (sem pagar nada) se a sessão web do Mercado Pago está válida."""
        self._ensure_driver()
        self.driver.get(MP_WEB_HOME_URL)
        time.sleep(3)
        logged_in = not self._is_login_wall()
        return {
            "logged_in": logged_in,
            "current_url": self.driver.current_url,
            "profile_dir": str(self.profile_dir),
        }

    def pay_barcode(
        self,
        linha_digitavel: str,
        *,
        amount_cents: int,
        description: str = "",
    ) -> dict[str, Any]:
        """Paga um boleto pela linha digitável usando dinheiro em conta.

        Levanta PayerUnavailableError quando o rail não está operável (feature
        desligada, sessão expirada). Retorna ``{"ok": bool, ...}`` com evidências.
        """
        if not MP_WEB_PAY_ENABLED:
            raise PayerUnavailableError(
                "MP_WEB_PAY_ENABLED!=1 — pagamento web Mercado Pago desabilitado. "
                "Habilite no drop-in banking.conf após o bootstrap da sessão."
            )
        digits = re.sub(r"\D", "", linha_digitavel or "")
        if len(digits) not in (47, 48):
            raise PayerUnavailableError(f"Linha digitável inválida ({len(digits)} dígitos).")

        self._ensure_driver()
        try:
            self.driver.get(MP_WEB_PAY_URL)
            time.sleep(3)
            if self._is_login_wall():
                raise PayerUnavailableError(
                    "Sessão Mercado Pago web expirada. Refaça o bootstrap: "
                    "MP_WEB_PAY_HEADLESS=0 python -m specialized_agents.banking.mercadopago_payer --bootstrap"
                )

            field = self._find_barcode_input()
            if field is None:
                self._screenshot("no-input")
                raise PayerUnavailableError(
                    "Campo de código de barras não encontrado na página de pagamento de contas."
                )
            field.clear()
            field.send_keys(digits)
            time.sleep(0.5)

            if not self._click_first_text("continuar", "avançar", "pagar"):
                self._screenshot("no-continue")
                raise PayerUnavailableError("Botão de continuar não encontrado após digitar o código.")

            time.sleep(4)
            review_text = self._body_text()
            expected_brl = f"{amount_cents // 100},{amount_cents % 100:02d}"
            if expected_brl not in review_text.replace(".", ""):
                self._screenshot("amount-mismatch")
                return {
                    "ok": False,
                    "error": (
                        f"Valor esperado R$ {expected_brl} não confirmado na tela de revisão; "
                        "pagamento abortado."
                    ),
                    "review_excerpt": review_text[:400],
                }

            if not self._click_first_text("confirmar pagamento", "pagar", "confirmar"):
                self._screenshot("no-confirm")
                raise PayerUnavailableError("Botão de confirmação não encontrado na revisão do pagamento.")

            time.sleep(6)
            final_text = self._body_text().lower()
            receipt = self._screenshot("receipt")
            success = any(
                marker in final_text
                for marker in ("pagamento realizado", "comprovante", "pagamento aprovado", "já estamos processando")
            )
            return {
                "ok": success,
                "description": description,
                "amount_cents": amount_cents,
                "receipt_screenshot": receipt,
                "final_url": self.driver.current_url,
                "final_excerpt": self._body_text()[:400],
            }
        finally:
            self.close()

    def _find_barcode_input(self) -> Any:
        selectors = [
            "//input[contains(translate(@placeholder, 'CÓDIGO', 'código'), 'código')]",
            "//textarea[contains(translate(@placeholder, 'CÓDIGO', 'código'), 'código')]",
            "//input[@type='text' or @type='tel' or not(@type)]",
        ]
        for xpath in selectors:
            try:
                for element in self.driver.find_elements("xpath", xpath):
                    if element.is_displayed():
                        return element
            except Exception:
                continue
        return None


def bootstrap_login() -> None:
    """Abre o Chrome com o perfil persistente para login manual (2FA) único."""
    payer = MercadoPagoWebPayer(headless=False)
    payer._ensure_driver()
    payer.driver.get("https://www.mercadopago.com.br/login")
    print(f"Perfil: {payer.profile_dir}")
    print("Faça o login (incluindo 2FA) na janela aberta. Pressione ENTER quando terminar...")
    input()
    status = payer.session_status()
    print(f"Sessão válida: {status['logged_in']} — {status['current_url']}")
    payer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mercado Pago web payer")
    parser.add_argument("--bootstrap", action="store_true", help="Login manual único no perfil persistente")
    parser.add_argument("--session-status", action="store_true", help="Verifica se a sessão web está válida")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.bootstrap:
        bootstrap_login()
    elif args.session_status:
        with MercadoPagoWebPayer() as payer:
            print(payer.session_status())
    else:
        parser.print_help()
