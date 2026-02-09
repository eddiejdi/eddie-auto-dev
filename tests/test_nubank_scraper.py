"""
Testes do NubankScraper — Eddie Banking Agent.

Cobre:
  - Configuração e inicialização
  - Formatação de CPF
  - Parse de datas
  - Classificação de transações
  - Gerenciamento de sessão
  - Parse de transações API
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

from specialized_agents.banking.nubank_scraper import (
    NubankScraper,
    NubankScraperError,
    NUBANK_WEB_URL,
)
from specialized_agents.banking.models import (
    BankProvider, TransactionType, CardBrand,
)


# ──────────── Fixtures ────────────

@pytest.fixture
def scraper(tmp_path):
    """Scraper Nubank com credenciais de teste."""
    return NubankScraper(
        cpf="12345678901",
        password="SenhaTest123",
        headless=True,
        state_dir=tmp_path / "nubank_state",
    )


@pytest.fixture
def scraper_unconfigured(tmp_path):
    """Scraper sem credenciais."""
    return NubankScraper(
        cpf="",
        password="",
        state_dir=tmp_path / "nubank_state",
    )


# ══════════════════════════════════════════════════════
#  Tests: Configuração
# ══════════════════════════════════════════════════════

class TestNubankScraperConfig:

    def test_is_configured_true(self, scraper):
        assert scraper.is_configured is True

    def test_is_configured_false(self, scraper_unconfigured):
        assert scraper_unconfigured.is_configured is False

    def test_has_saved_session_false(self, scraper):
        assert scraper.has_saved_session is False

    def test_has_saved_session_true(self, scraper):
        scraper._state_file.parent.mkdir(parents=True, exist_ok=True)
        scraper._state_file.write_text("{}")
        assert scraper.has_saved_session is True

    def test_repr_configured(self, scraper):
        r = repr(scraper)
        assert "✓" in r
        assert "NubankScraper" in r

    def test_repr_unconfigured(self, scraper_unconfigured):
        r = repr(scraper_unconfigured)
        assert "✗" in r

    def test_clear_session(self, scraper):
        scraper._state_file.parent.mkdir(parents=True, exist_ok=True)
        scraper._state_file.write_text("{}")
        assert scraper.has_saved_session is True
        scraper.clear_session()
        assert scraper.has_saved_session is False

    def test_clear_session_no_file(self, scraper):
        # Should not raise
        scraper.clear_session()

    def test_env_fallback(self, tmp_path):
        with patch.dict("os.environ", {
            "NUBANK_CPF": "98765432100",
            "NUBANK_PASSWORD": "EnvPassword",
        }):
            s = NubankScraper.__new__(NubankScraper)
            s._cpf = None
            s._password = None
            s._state_dir = tmp_path
            s._state_file = tmp_path / "state.json"
            s._headless = True
            s._browser = None
            s._context = None
            s._page = None
            s._logged_in = False
            s._security = MagicMock()
            s._security.load_credentials.side_effect = Exception("no vault")
            s._load_credentials()
            assert s._cpf == "98765432100"
            assert s._password == "EnvPassword"


# ══════════════════════════════════════════════════════
#  Tests: Format CPF
# ══════════════════════════════════════════════════════

class TestFormatCPF:

    def test_format_11_digits(self):
        assert NubankScraper._format_cpf("12345678901") == "123.456.789-01"

    def test_format_already_formatted(self):
        # Se já tem pontos, vai limpar e reformatar
        assert NubankScraper._format_cpf("123.456.789-01") == "123.456.789-01"

    def test_format_short(self):
        # CPF incompleto retorna como está (sem pontuação)
        assert NubankScraper._format_cpf("123") == "123"

    def test_format_with_spaces(self):
        assert NubankScraper._format_cpf("123 456 789 01") == "123.456.789-01"


# ══════════════════════════════════════════════════════
#  Tests: Parse Date
# ══════════════════════════════════════════════════════

class TestParseDate:

    def test_iso_millis(self):
        d = NubankScraper._parse_date("2026-02-15T10:00:00.000Z")
        assert d == datetime(2026, 2, 15, 10, 0, 0)

    def test_iso(self):
        d = NubankScraper._parse_date("2026-02-15T10:00:00Z")
        assert d == datetime(2026, 2, 15, 10, 0, 0)

    def test_date_only(self):
        d = NubankScraper._parse_date("2026-02-15")
        assert d == datetime(2026, 2, 15, 0, 0, 0)

    def test_br_format(self):
        d = NubankScraper._parse_date("15/02/2026")
        assert d == datetime(2026, 2, 15, 0, 0, 0)

    def test_none(self):
        assert NubankScraper._parse_date(None) is None

    def test_invalid(self):
        assert NubankScraper._parse_date("not-a-date") is None


# ══════════════════════════════════════════════════════
#  Tests: Classify Transaction
# ══════════════════════════════════════════════════════

class TestClassifyTx:

    def test_pix_received(self):
        assert NubankScraper._classify_tx("PIX recebido", Decimal("500")) == TransactionType.PIX_RECEIVED

    def test_pix_sent(self):
        assert NubankScraper._classify_tx("PIX enviado", Decimal("-200")) == TransactionType.PIX_SENT

    def test_ted_received(self):
        assert NubankScraper._classify_tx("TED recebido", Decimal("1000")) == TransactionType.TED_RECEIVED

    def test_ted_sent(self):
        assert NubankScraper._classify_tx("TED enviado", Decimal("-500")) == TransactionType.TED_SENT

    def test_boleto(self):
        assert NubankScraper._classify_tx("Pagamento BOLETO", Decimal("-200")) == TransactionType.BOLETO_PAYMENT

    def test_estorno(self):
        assert NubankScraper._classify_tx("ESTORNO compra", Decimal("100")) == TransactionType.REFUND

    def test_tarifa(self):
        assert NubankScraper._classify_tx("TARIFA mensal", Decimal("-15")) == TransactionType.FEE

    def test_anuidade(self):
        assert NubankScraper._classify_tx("ANUIDADE cartão", Decimal("-200")) == TransactionType.FEE

    def test_juros(self):
        assert NubankScraper._classify_tx("JUROS sobre atraso", Decimal("-50")) == TransactionType.INTEREST

    def test_salario(self):
        assert NubankScraper._classify_tx("SALARIO empresa", Decimal("5000")) == TransactionType.SALARY

    def test_card_purchase(self):
        assert NubankScraper._classify_tx("Amazon.com.br", Decimal("-150")) == TransactionType.CARD_PURCHASE


# ══════════════════════════════════════════════════════
#  Tests: Parse API Transaction
# ══════════════════════════════════════════════════════

class TestParseApiTransaction:

    def test_parse_normal(self, scraper):
        item = {
            "id": "tx-001",
            "description": "IFOOD *LANCHONETE",
            "amount": 15090,  # centavos
            "time": "2026-02-15T12:00:00.000Z",
            "category": "food",
        }
        tx = scraper._parse_api_transaction(item)
        assert tx is not None
        assert tx.description == "IFOOD *LANCHONETE"
        assert tx.amount == Decimal("150.90")
        assert tx.provider == BankProvider.NUBANK

    def test_parse_float_amount(self, scraper):
        item = {
            "description": "Test",
            "amount": 99.50,
            "time": "2026-02-15",
        }
        tx = scraper._parse_api_transaction(item)
        assert tx is not None
        assert tx.amount == Decimal("99.50")

    def test_parse_missing_description(self, scraper):
        item = {
            "title": "Pagamento via PIX",
            "value": 500,
            "date": "2026-02-15",
        }
        tx = scraper._parse_api_transaction(item)
        assert tx is not None
        assert tx.description == "Pagamento via PIX"

    def test_parse_empty_item(self, scraper):
        tx = scraper._parse_api_transaction({})
        # Pode retornar None ou transação com valores default
        # Ambos são aceitáveis
        if tx:
            assert tx.amount == Decimal("0")

    def test_parse_with_installments(self, scraper):
        item = {
            "description": "Notebook Dell",
            "amount": 120000,  # R$ 1200 em centavos
            "time": "2026-02-15T12:00:00.000Z",
            "charges": 12,
            "charge_amount": 10000,
        }
        tx = scraper._parse_api_transaction(item)
        assert tx is not None
        assert tx.metadata.get("installments") == 12
        assert tx.metadata.get("charge_amount") == 10000


# ══════════════════════════════════════════════════════
#  Tests: Login Guard
# ══════════════════════════════════════════════════════

class TestLoginGuard:

    @pytest.mark.asyncio
    async def test_login_not_configured_raises(self, scraper_unconfigured):
        with pytest.raises(NubankScraperError, match="não configurados"):
            await scraper_unconfigured.login()


# ══════════════════════════════════════════════════════
#  Tests: NubankScraperError
# ══════════════════════════════════════════════════════

class TestNubankScraperError:

    def test_error_message(self):
        err = NubankScraperError("test error")
        assert "test error" in str(err)

    def test_inherits_exception(self):
        err = NubankScraperError("boom")
        assert isinstance(err, Exception)


# ══════════════════════════════════════════════════════
#  Tests: Close
# ══════════════════════════════════════════════════════

class TestNubankScraperClose:

    @pytest.mark.asyncio
    async def test_close_no_browser(self, scraper):
        # Should not raise
        await scraper.close()
