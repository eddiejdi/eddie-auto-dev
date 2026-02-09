"""
Nubank Web Scraper — Extração de dados via automação browser.

Usa Playwright para fazer login no app web do Nubank (app.nubank.com.br)
e extrair transações, faturas, saldos e dados do cartão de crédito.

Fluxo:
  1ª vez — Login interativo: abre browser visível, usuário digita CPF/senha
           e aprova 2FA pelo app do celular. Sessão é salva.
  Próximas vezes — Reutiliza sessão salva (cookies). Se expirada, pede login novamente.

Variáveis de ambiente:
  NUBANK_CPF       — CPF do usuário (11 dígitos, sem pontuação)
  NUBANK_PASSWORD  — Senha do app web

Requisitos:
  pip install playwright
  playwright install chromium
"""

import os
import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from .models import (
    BankAccount, Balance, Transaction, CreditCard, Invoice,
    BankProvider, AccountType, TransactionType, CardBrand,
)
from .security import BankingSecurityManager

logger = logging.getLogger("eddie.banking.nubank_scraper")

# ──────────── Constantes ────────────

NUBANK_WEB_URL = "https://app.nubank.com.br/"
NUBANK_STATE_DIR = Path("agent_data/banking/nubank_state")
NUBANK_STATE_FILE = NUBANK_STATE_DIR / "browser_state.json"

# Seletores CSS do app web Nubank
SEL_CPF_INPUT = "#inputtext_cpf"
SEL_PASSWORD_INPUT = "input[type='password']"
SEL_ACESSAR_BTN = "button:has-text('Acessar')"
SEL_CONTINUAR_BTN = "button:has-text('Continuar')"
SEL_LOGIN_BTN = "button:has-text('Entrar'), button:has-text('Login')"

# Padrões de URL para detectar estado
URL_LOGIN = "/beta/"
URL_DASHBOARD = "/dashboard"
URL_BILLS = "/bills"
URL_CREDIT_CARD = "/credit-card"
URL_ACCOUNT = "/account"


class NubankScraperError(Exception):
    """Erro no scraper Nubank."""
    pass


class NubankScraper:
    """
    Extrator de dados Nubank via automação do browser web.

    Usa Playwright para navegar pelo app web do Nubank,
    faz login com CPF/senha + 2FA, e extrai dados financeiros.
    Sessão do browser é salva localmente para reutilização.
    """

    def __init__(
        self,
        cpf: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = False,
        state_dir: Optional[Path] = None,
    ):
        """
        Args:
            cpf: CPF do usuário (11 dígitos)
            password: Senha do Nubank app web
            headless: Rodar sem janela visível (True) ou com (False).
                      Primeira vez deve ser False para permitir 2FA.
            state_dir: Diretório para salvar estado do browser.
        """
        self._cpf = cpf
        self._password = password
        self._headless = headless
        self._state_dir = state_dir or NUBANK_STATE_DIR
        self._state_file = self._state_dir / "browser_state.json"
        self._security = BankingSecurityManager()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

        if not self._cpf or not self._password:
            self._load_credentials()

        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _load_credentials(self):
        """Carrega credenciais do vault ou .env."""
        try:
            creds = self._security.load_credentials("nubank_web")
            if creds:
                self._cpf = self._cpf or creds.get("cpf")
                self._password = self._password or creds.get("password")
                return
        except Exception:
            pass

        self._cpf = self._cpf or os.getenv("NUBANK_CPF", "")
        self._password = self._password or os.getenv("NUBANK_PASSWORD", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._cpf and self._password)

    @property
    def has_saved_session(self) -> bool:
        return self._state_file.exists()

    # ──────────── Browser Management ────────────

    async def _launch(self):
        """Inicia browser e contexto."""
        pw = await async_playwright().start()
        self._pw = pw
        self._browser = await pw.chromium.launch(
            headless=self._headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        ctx_kwargs = {
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1280, "height": 800},
            "locale": "pt-BR",
        }

        # Restaurar sessão anterior se existir
        if self._state_file.exists():
            try:
                ctx_kwargs["storage_state"] = str(self._state_file)
                logger.info("Restaurando sessão anterior do Nubank")
            except Exception:
                logger.warning("Sessão anterior inválida, login fresh")

        self._context = await self._browser.new_context(**ctx_kwargs)
        self._page = await self._context.new_page()

    async def close(self):
        """Fecha browser e salva estado."""
        try:
            if self._context:
                await self._save_state()
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if hasattr(self, '_pw'):
                await self._pw.stop()
        except Exception as e:
            logger.error(f"Erro ao fechar browser: {e}")

    async def _save_state(self):
        """Salva estado do browser (cookies, localStorage)."""
        try:
            if self._context:
                await self._context.storage_state(path=str(self._state_file))
                logger.info("Estado do browser salvo")
        except Exception as e:
            logger.warning(f"Erro ao salvar estado: {e}")

    # ──────────── Login ────────────

    async def login(self, timeout: int = 120) -> bool:
        """
        Faz login no Nubank web.

        Fluxo:
          1. Navega para app.nubank.com.br
          2. Preenche CPF
          3. Clica "Acessar"
          4. Preenche senha
          5. Aguarda aprovação 2FA no celular (até `timeout` segundos)
          6. Salva sessão

        Args:
            timeout: Timeout em segundos para aguardar 2FA.

        Returns:
            True se logou com sucesso.
        """
        if not self.is_configured:
            raise NubankScraperError(
                "CPF e senha não configurados. "
                "Defina NUBANK_CPF e NUBANK_PASSWORD."
            )

        if not self._page:
            await self._launch()

        page = self._page

        try:
            # 1. Navegar ao login
            await page.goto(NUBANK_WEB_URL, timeout=30000)
            await page.wait_for_timeout(3000)

            # Verificar se já está logado (sessão restaurada)
            if await self._is_logged_in():
                logger.info("Sessão anterior válida, já logado!")
                self._logged_in = True
                return True

            # 2. Preencher CPF
            cpf_input = await page.wait_for_selector(SEL_CPF_INPUT, timeout=10000)
            await cpf_input.fill("")  # Limpar
            # Digitar CPF formatado
            cpf_formatted = self._format_cpf(self._cpf)
            await cpf_input.type(cpf_formatted, delay=50)
            await page.wait_for_timeout(500)

            # 3. Clicar em Acessar
            acessar = await page.wait_for_selector(
                SEL_ACESSAR_BTN, timeout=5000
            )
            # Esperar botão ficar habilitado
            await page.wait_for_timeout(1000)
            await acessar.click()
            await page.wait_for_timeout(3000)

            # 4. Preencher senha (esperar campo aparecer)
            pwd_input = await page.wait_for_selector(
                SEL_PASSWORD_INPUT, timeout=15000
            )
            await pwd_input.fill(self._password)
            await page.wait_for_timeout(500)

            # Clicar em Continuar/Entrar/Login
            for sel in [SEL_CONTINUAR_BTN, SEL_LOGIN_BTN, "button[type='submit']"]:
                btn = await page.query_selector(sel)
                if btn:
                    enabled = await btn.is_enabled()
                    if enabled:
                        await btn.click()
                        break

            # 5. Aguardar 2FA (usuário aprova no celular)
            logger.info(
                f"Aguardando aprovação 2FA no celular (até {timeout}s)..."
            )
            print(
                f"\n🔐 NUBANK: Abra o app Nubank no celular e aprove o acesso.\n"
                f"   Aguardando até {timeout} segundos..."
            )

            # Esperar sair da página de login
            start = datetime.now()
            while (datetime.now() - start).seconds < timeout:
                if await self._is_logged_in():
                    self._logged_in = True
                    await self._save_state()
                    logger.info("Login no Nubank realizado com sucesso!")
                    print("✅ Login aprovado!")
                    return True
                await page.wait_for_timeout(2000)

            raise NubankScraperError(
                f"Timeout de {timeout}s aguardando aprovação 2FA"
            )

        except NubankScraperError:
            raise
        except Exception as e:
            raise NubankScraperError(f"Erro no login: {e}") from e

    async def _is_logged_in(self) -> bool:
        """Verifica se o usuário está logado."""
        if not self._page:
            return False
        url = self._page.url.lower()
        # Se saiu da página de login, provavelmente está logado
        if URL_LOGIN not in url and "nubank.com.br" in url:
            return True
        # Procurar elementos que só aparecem quando logado
        logged_selectors = [
            "[data-testid='dashboard']",
            "[class*='Dashboard']",
            "nav", "aside",
            "a[href*='account']",
            "a[href*='bills']",
        ]
        for sel in logged_selectors:
            el = await self._page.query_selector(sel)
            if el:
                return True
        return False

    # ──────────── Navegação ────────────

    async def _navigate_to(self, path: str, wait_selector: Optional[str] = None):
        """Navega para um caminho dentro do app."""
        if not self._logged_in:
            raise NubankScraperError("Não está logado. Chame login() primeiro.")

        url = f"https://app.nubank.com.br{path}"
        await self._page.goto(url, timeout=30000)
        await self._page.wait_for_timeout(3000)

        if wait_selector:
            try:
                await self._page.wait_for_selector(wait_selector, timeout=10000)
            except Exception:
                logger.warning(f"Seletor '{wait_selector}' não encontrado")

    async def _extract_page_data(self) -> Dict[str, Any]:
        """Extrai dados estruturados da página atual via JavaScript."""
        try:
            # Interceptar dados de requisições XHR/fetch da SPA React
            data = await self._page.evaluate("""
                () => {
                    // Tentar pegar dados do Redux/React state
                    const root = document.getElementById('root') || document.getElementById('__next');
                    if (root && root._reactRootContainer) {
                        return { type: 'react', found: true };
                    }
                    // Pegar texto visível como fallback
                    const texts = [];
                    document.querySelectorAll('p, span, h1, h2, h3, td, li').forEach(el => {
                        const text = el.innerText.trim();
                        if (text && text.length > 0 && text.length < 500) {
                            texts.push(text);
                        }
                    });
                    return { type: 'text', texts: texts.slice(0, 200) };
                }
            """)
            return data
        except Exception as e:
            logger.error(f"Erro ao extrair dados: {e}")
            return {}

    # ──────────── Interceptação de Rede ────────────

    async def _setup_network_interceptor(self) -> List[Dict]:
        """
        Configura interceptador de requisições para capturar dados da API.

        O app web do Nubank faz chamadas GraphQL/REST internas.
        Interceptamos essas respostas para obter dados estruturados.
        """
        captured_responses = []

        async def on_response(response):
            url = response.url
            if any(api in url for api in [
                "prod-s0-webapp-proxy",
                "prod-global-auth",
                "/api/proxy/",
                "graphql",
                "/api/customers/",
            ]):
                try:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        body = await response.json()
                        captured_responses.append({
                            "url": url,
                            "status": response.status,
                            "data": body,
                        })
                except Exception:
                    pass

        self._page.on("response", on_response)
        return captured_responses

    # ──────────── Extração de Dados ────────────

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Extrai dados do dashboard principal.

        Returns:
            Dict com saldo, limite do cartão, e informações gerais.
        """
        captured = await self._setup_network_interceptor()

        await self._navigate_to("/beta/")
        await self._page.wait_for_timeout(5000)

        # Extrair textos visíveis
        texts = await self._page.evaluate("""
            () => {
                const data = {};
                // Procurar valores monetários
                const allTexts = document.body.innerText;
                const moneyPattern = /R\\$\\s*[\\d.,]+/g;
                data.money_values = allTexts.match(moneyPattern) || [];
                
                // Procurar por seções conhecidas
                const sections = {};
                document.querySelectorAll('h2, h3, [class*="title"]').forEach(el => {
                    const title = el.innerText.trim();
                    const parent = el.closest('section, div, article');
                    if (parent && title) {
                        const content = parent.innerText.trim().substring(0, 500);
                        sections[title] = content;
                    }
                });
                data.sections = sections;
                return data;
            }
        """)

        return {
            "page_data": texts,
            "api_responses": captured,
            "url": self._page.url,
        }

    async def get_card_transactions(
        self,
        months_back: int = 3,
    ) -> List[Transaction]:
        """
        Extrai transações do cartão de crédito via web scraping.

        Returns:
            Lista de Transaction
        """
        captured = await self._setup_network_interceptor()
        transactions = []

        # Navegar para área de faturas/cartão
        for path in ["/beta/bills", "/beta/credit-card", "/beta/#/credit-card"]:
            try:
                await self._navigate_to(path)
                await self._page.wait_for_timeout(5000)

                if captured:
                    break
            except Exception:
                continue

        # Tentar extrair dados das respostas API capturadas
        for resp in captured:
            data = resp.get("data", {})
            if isinstance(data, dict):
                # Procurar transações em diferentes formatos de resposta
                items = (
                    data.get("bills", []) or
                    data.get("transactions", []) or
                    data.get("items", []) or
                    data.get("data", {}).get("viewer", {}).get("bills", [])
                )
                for item in items if isinstance(items, list) else []:
                    tx = self._parse_api_transaction(item)
                    if tx:
                        transactions.append(tx)

        # Fallback: scraping DOM se API não retornou dados
        if not transactions:
            transactions = await self._scrape_transactions_from_dom()

        return transactions

    async def _scrape_transactions_from_dom(self) -> List[Transaction]:
        """Extrai transações direto do DOM (fallback)."""
        transactions = []

        rows = await self._page.evaluate("""
            () => {
                const txs = [];
                // Procurar por padrões de transação no DOM
                // Nubank geralmente mostra: data, descrição, valor
                const items = document.querySelectorAll(
                    '[class*="transaction"], [class*="charge"], ' +
                    '[class*="bill-item"], [class*="event"], ' +
                    'li[class*="item"], tr'
                );
                items.forEach(item => {
                    const text = item.innerText.trim();
                    // Procurar padrão: descrição + valor monetário
                    const moneyMatch = text.match(/R\\$\\s*([\\d.,]+)/);
                    if (moneyMatch && text.length > 5 && text.length < 300) {
                        txs.push({
                            text: text,
                            amount: moneyMatch[1],
                        });
                    }
                });
                return txs;
            }
        """)

        for i, row in enumerate(rows):
            try:
                amount_str = row.get("amount", "0").replace(".", "").replace(",", ".")
                amount = Decimal(amount_str)
                text = row.get("text", "")

                # Tentar extrair data (padrões DD/MM, DD MMM, etc.)
                date_match = re.search(
                    r'(\d{1,2})[/\s](\w{3}|\d{2})[/\s]?(\d{2,4})?', text
                )
                tx_date = datetime.now()
                if date_match:
                    try:
                        raw = date_match.group(0)
                        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m"):
                            try:
                                tx_date = datetime.strptime(raw, fmt)
                                if tx_date.year < 2000:
                                    tx_date = tx_date.replace(year=datetime.now().year)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass

                # Descrição (remover a data e o valor)
                desc = re.sub(r'R\$\s*[\d.,]+', '', text).strip()
                desc = re.sub(r'\d{1,2}/\d{2}(/\d{2,4})?', '', desc).strip()
                desc = " ".join(desc.split())  # Limpar espaços extras

                if desc and amount > 0:
                    transactions.append(Transaction(
                        id=f"nubank-web-{i}",
                        account_id="nubank-web",
                        provider=BankProvider.NUBANK,
                        type=TransactionType.CARD_PURCHASE,
                        amount=amount,
                        description=desc[:200],
                        date=tx_date,
                        metadata={"source": "web_scraping", "raw_text": text[:300]},
                    ))
            except (InvalidOperation, ValueError):
                continue

        return transactions

    def _parse_api_transaction(self, item: Dict) -> Optional[Transaction]:
        """Converte transação da API interna do Nubank para nosso modelo."""
        try:
            # A API interna do Nubank pode retornar vários formatos
            description = (
                item.get("description") or
                item.get("title") or
                item.get("detail") or
                ""
            )
            amount_raw = (
                item.get("amount") or
                item.get("value") or
                item.get("totalAmount") or
                0
            )
            # Nubank API retorna centavos (int) ou reais (float)
            if isinstance(amount_raw, int) and amount_raw > 1000:
                amount = Decimal(str(amount_raw)) / 100
            else:
                amount = Decimal(str(amount_raw))

            date_str = (
                item.get("time") or
                item.get("post_date") or
                item.get("event_date") or
                item.get("date") or
                ""
            )
            tx_date = self._parse_date(date_str)

            category = item.get("category") or item.get("tags", [""])[0] if item.get("tags") else ""

            return Transaction(
                id=item.get("id", f"nubank-{hash(description)}"),
                account_id="nubank-cc",
                provider=BankProvider.NUBANK,
                type=self._classify_tx(description, amount),
                amount=abs(amount),
                description=description,
                date=tx_date or datetime.now(),
                category=category if isinstance(category, str) else str(category),
                metadata={
                    "source": "nubank_web_api",
                    "installments": item.get("charges"),
                    "charge_amount": item.get("charge_amount"),
                    "original_id": item.get("id"),
                },
            )
        except Exception as e:
            logger.debug(f"Erro ao parsear transação: {e}")
            return None

    async def get_bills_summary(self) -> List[Dict[str, Any]]:
        """
        Extrai resumo das faturas.

        Returns:
            Lista de dicts com dados das faturas.
        """
        captured = await self._setup_network_interceptor()
        await self._navigate_to("/beta/bills")
        await self._page.wait_for_timeout(5000)

        bills = []

        # Tentar capturar dos dados da API
        for resp in captured:
            data = resp.get("data", {})
            if isinstance(data, dict):
                bill_list = data.get("bills") or data.get("data", {}).get("bills", [])
                if isinstance(bill_list, list):
                    for bill in bill_list:
                        bills.append({
                            "id": bill.get("id"),
                            "state": bill.get("state"),
                            "total_amount": bill.get("totalAmount") or bill.get("total_balance"),
                            "due_date": bill.get("dueDate") or bill.get("close_date"),
                            "minimum_payment": bill.get("minimumPayment"),
                        })

        # Fallback: DOM scraping
        if not bills:
            page_bills = await self._page.evaluate("""
                () => {
                    const bills = [];
                    const items = document.querySelectorAll(
                        '[class*="bill"], [class*="fatura"], [class*="invoice"]'
                    );
                    items.forEach(item => {
                        const text = item.innerText.trim();
                        const money = text.match(/R\\$\\s*([\\d.,]+)/g) || [];
                        if (money.length > 0) {
                            bills.push({
                                text: text.substring(0, 300),
                                amounts: money,
                            });
                        }
                    });
                    return bills;
                }
            """)
            bills = page_bills

        return bills

    async def get_account_balance(self) -> Optional[Balance]:
        """
        Extrai saldo da conta Nubank.

        Returns:
            Balance ou None
        """
        captured = await self._setup_network_interceptor()
        await self._navigate_to("/beta/")
        await self._page.wait_for_timeout(5000)

        # Tentar dos dados da API
        for resp in captured:
            data = resp.get("data", {})
            if isinstance(data, dict):
                balance_val = (
                    data.get("balance") or
                    data.get("data", {}).get("viewer", {}).get("savingsAccount", {}).get("currentBalance")
                )
                if balance_val is not None:
                    return Balance(
                        account_id="nubank-conta",
                        provider=BankProvider.NUBANK,
                        available=Decimal(str(balance_val)),
                        currency="BRL",
                    )

        # Fallback: buscar no DOM
        money_values = await self._page.evaluate("""
            () => {
                const vals = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.children.length === 0) {
                        const text = el.innerText || '';
                        const match = text.match(/^R\\$\\s*([\\d.,]+)$/);
                        if (match) {
                            const section = el.closest('section, div')?.querySelector('h2, h3, [class*="title"]');
                            vals.push({
                                amount: match[1],
                                context: section?.innerText?.trim() || 'unknown',
                            });
                        }
                    }
                });
                return vals;
            }
        """)

        # O saldo da conta geralmente está na seção "Conta" ou "Saldo disponível"
        for val in money_values:
            ctx = val.get("context", "").lower()
            if any(w in ctx for w in ["conta", "saldo", "disponível", "balance"]):
                try:
                    amount_str = val["amount"].replace(".", "").replace(",", ".")
                    return Balance(
                        account_id="nubank-conta",
                        provider=BankProvider.NUBANK,
                        available=Decimal(amount_str),
                        currency="BRL",
                    )
                except (InvalidOperation, KeyError):
                    continue

        return None

    async def take_screenshot(self, name: str = "nubank") -> str:
        """Tira screenshot da página atual. Retorna caminho do arquivo."""
        path = self._state_dir / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.png"
        await self._page.screenshot(path=str(path), full_page=True)
        return str(path)

    # ──────────── Helpers ────────────

    @staticmethod
    def _format_cpf(cpf: str) -> str:
        """Formata CPF: 12345678901 → 123.456.789-01."""
        cpf = re.sub(r"\D", "", cpf)
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Parse data em vários formatos."""
        if not date_str:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d/%m/%y",
        ):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    @staticmethod
    def _classify_tx(description: str, amount: Decimal) -> TransactionType:
        """Classifica transação pelo descritor."""
        desc = description.upper()
        if "PIX" in desc:
            return TransactionType.PIX_RECEIVED if amount > 0 else TransactionType.PIX_SENT
        if "TED" in desc or "DOC" in desc:
            return TransactionType.TED_RECEIVED if amount > 0 else TransactionType.TED_SENT
        if "BOLETO" in desc:
            return TransactionType.BOLETO_PAYMENT
        if "ESTORNO" in desc:
            return TransactionType.REFUND
        if "TARIFA" in desc or "ANUIDADE" in desc:
            return TransactionType.FEE
        if "JUROS" in desc:
            return TransactionType.INTEREST
        if "SALARIO" in desc or "SALÁRIO" in desc:
            return TransactionType.SALARY
        return TransactionType.CARD_PURCHASE

    # ──────────── Configuração ────────────

    async def save_credentials(self):
        """Salva credenciais no vault Eddie."""
        self._security.store_credentials("nubank_web", {
            "cpf": self._cpf,
            "password": self._password,
        })
        logger.info("Credenciais Nubank salvas no vault")

    def clear_session(self):
        """Remove sessão salva (força re-login)."""
        if self._state_file.exists():
            self._state_file.unlink()
            logger.info("Sessão Nubank removida")

    def __repr__(self) -> str:
        configured = "✓" if self.is_configured else "✗"
        session = "✓" if self.has_saved_session else "✗"
        return f"NubankScraper(configured={configured}, session={session})"
