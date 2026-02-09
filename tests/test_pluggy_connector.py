"""
Testes do Conector Pluggy — Eddie Banking Agent.

Cobre:
  - Inicialização e configuração
  - Autenticação (API key)
  - GET/POST autenticados
  - Conversão de dados Pluggy → modelos Eddie
  - Classificação de transações
  - Cartões de crédito e faturas
  - Métodos de conveniência
  - Gerenciamento de itens/credenciais
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, date, timedelta
from decimal import Decimal

from specialized_agents.banking.pluggy_connector import (
    PluggyConnector,
    PluggyConnectionError,
    PLUGGY_API_URL,
    PLUGGY_CONNECTOR_MAP,
    PLUGGY_NAME_MAP,
    PLUGGY_ACCOUNT_TYPE_MAP,
    PLUGGY_BRAND_MAP,
)
from specialized_agents.banking.models import (
    BankProvider, AccountType, TransactionType, CardBrand,
)


# ──────────── Fixtures ────────────

@pytest.fixture
def pluggy():
    """Conector Pluggy com credenciais de teste."""
    return PluggyConnector(
        client_id="test-client-id",
        client_secret="test-client-secret",
        item_ids={"nubank": "item-nubank-123", "itau": "item-itau-456"},
    )


@pytest.fixture
def pluggy_unconfigured():
    """Conector Pluggy sem credenciais."""
    return PluggyConnector(
        client_id="",
        client_secret="",
        item_ids={},
    )


@pytest.fixture
def mock_response():
    """Factory para criar mock httpx responses."""
    def _make(json_data=None, status_code=200, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = text or json.dumps(json_data or {})
        return resp
    return _make


# ──────────── Dados de amostra Pluggy ────────────

SAMPLE_AUTH_RESPONSE = {
    "apiKey": "eyJ0eXAi-test-api-key-123",
}

SAMPLE_ITEM = {
    "id": "item-nubank-123",
    "status": "UPDATED",
    "executionStatus": "SUCCESS",
    "lastUpdatedAt": "2026-02-15T10:00:00.000Z",
    "connector": {
        "id": 212,
        "name": "Nubank",
        "institutionUrl": "https://nubank.com.br",
    },
}

SAMPLE_ITEM_ITAU = {
    "id": "item-itau-456",
    "status": "UPDATED",
    "executionStatus": "SUCCESS",
    "connector": {
        "id": 201,
        "name": "Itaú Unibanco",
    },
}

SAMPLE_ACCOUNT = {
    "id": "acc-nubank-001",
    "type": "BANK",
    "subtype": "CHECKING_ACCOUNT",
    "number": "12345678",
    "name": "Conta Corrente",
    "marketingName": "Conta Nubank",
    "balance": 5432.10,
    "currencyCode": "BRL",
    "itemId": "item-nubank-123",
    "owner": "Edenilson Teixeira",
    "taxNumber": "***809",
    "bankData": {
        "transferNumber": "0001",
    },
}

SAMPLE_ACCOUNT_CREDIT = {
    "id": "acc-nubank-cc-002",
    "type": "CREDIT",
    "subtype": "CREDIT_CARD",
    "number": "****4515",
    "name": "Cartão Nubank",
    "marketingName": "Mastercard Nubank",
    "balance": -1500.00,
    "currencyCode": "BRL",
    "itemId": "item-nubank-123",
    "owner": "Edenilson Teixeira",
    "creditData": {
        "creditLimit": 10000.00,
        "availableCreditLimit": 8500.00,
        "brand": "MASTERCARD",
        "balanceCloseDate": 3,
        "balanceDueDate": 10,
    },
}

SAMPLE_TRANSACTION_PIX = {
    "id": "tx-001",
    "description": "PIX recebido - Salário",
    "amount": 3500.00,
    "date": "2026-02-01T00:00:00.000Z",
    "category": "Income",
    "type": "CREDIT",
    "status": "POSTED",
    "balance": 8932.10,
    "paymentData": {"payer": "Empresa XYZ"},
}

SAMPLE_TRANSACTION_DEBIT = {
    "id": "tx-002",
    "description": "IFOOD *LANCHONETE",
    "amount": -150.00,
    "date": "2026-02-02T00:00:00.000Z",
    "category": "Food and Drink",
    "type": "DEBIT",
    "status": "POSTED",
    "balance": 8782.10,
}

SAMPLE_TRANSACTION_CARD = {
    "id": "tx-003",
    "description": "COMPRA CARTAO Amazon.com.br",
    "amount": -299.90,
    "date": "2026-02-03T00:00:00.000Z",
    "category": "Shopping",
    "type": "DEBIT",
    "status": "POSTED",
    "creditCardMetadata": {
        "totalInstallments": 3,
        "installmentNumber": 1,
    },
}

SAMPLE_BILL = {
    "id": "bill-001",
    "totalAmount": 2500.00,
    "minimumPayment": 250.00,
    "dueDate": "2026-03-10T00:00:00.000Z",
    "closeDate": "2026-03-03T00:00:00.000Z",
    "state": "OPEN",
}

SAMPLE_IDENTITY = {
    "id": "identity-001",
    "fullName": "Edenilson Teixeira Paschoa",
    "document": "***.**.***.809-**",
    "birthDate": "1990-01-15",
    "emails": [{"value": "edenilson@example.com"}],
    "phoneNumbers": [{"value": "+5511999999999"}],
}

SAMPLE_INVESTMENT = {
    "id": "inv-001",
    "name": "CDB 110% CDI",
    "type": "FIXED_INCOME",
    "subtype": "CDB",
    "balance": 15000.00,
    "amountProfit": 1500.00,
    "amountOriginal": 13500.00,
    "currencyCode": "BRL",
    "rate": 1.10,
    "rateType": "CDI",
    "dueDate": "2027-01-15",
    "issuer": "Nubank",
    "lastUpdatedAt": "2026-02-15T10:00:00.000Z",
}

SAMPLE_LOAN = {
    "id": "loan-001",
    "name": "Empréstimo Pessoal",
    "type": "PERSONAL_LOAN",
    "contractNumber": "CON-12345",
    "principal": 10000.00,
    "outstandingBalance": 7500.00,
    "monthlyPayment": 850.00,
    "interestRate": 2.5,
    "numberOfInstallments": 12,
    "numberOfInstallmentsPaid": 3,
    "dueDate": "2027-02-01",
    "status": "ACTIVE",
}


# ══════════════════════════════════════════════════════
#  Tests: Configuração e Inicialização
# ══════════════════════════════════════════════════════

class TestPluggyConfiguration:

    def test_is_configured_true(self, pluggy):
        assert pluggy.is_configured is True

    def test_is_configured_false(self, pluggy_unconfigured):
        assert pluggy_unconfigured.is_configured is False

    def test_has_items_true(self, pluggy):
        assert pluggy.has_items is True

    def test_has_items_false(self, pluggy_unconfigured):
        assert pluggy_unconfigured.has_items is False

    def test_connected_banks(self, pluggy):
        banks = pluggy.connected_banks
        assert "nubank" in banks
        assert "itau" in banks
        assert len(banks) == 2

    def test_repr_configured(self, pluggy):
        r = repr(pluggy)
        assert "✓" in r
        assert "nubank" in r
        assert "itau" in r

    def test_repr_unconfigured(self, pluggy_unconfigured):
        r = repr(pluggy_unconfigured)
        assert "✗" in r
        assert "nenhum" in r

    def test_add_item(self, pluggy):
        pluggy.add_item("Santander", "item-san-789")
        assert "santander" in pluggy.connected_banks
        assert pluggy._item_ids["santander"] == "item-san-789"

    def test_remove_item(self, pluggy):
        pluggy.remove_item("itau")
        assert "itau" not in pluggy.connected_banks

    def test_get_item_id_exact(self, pluggy):
        assert pluggy._get_item_id("nubank") == "item-nubank-123"

    def test_get_item_id_case_insensitive(self, pluggy):
        assert pluggy._get_item_id("Nubank") == "item-nubank-123"

    def test_get_item_id_not_found(self, pluggy):
        with pytest.raises(PluggyConnectionError, match="não encontrado"):
            pluggy._get_item_id("bradesco")

    def test_env_fallback(self):
        """Testa fallback para variáveis de ambiente."""
        with patch.dict("os.environ", {
            "PLUGGY_CLIENT_ID": "env-client-id",
            "PLUGGY_CLIENT_SECRET": "env-secret",
            "PLUGGY_ITEM_IDS": '{"nubank": "env-item"}',
        }):
            c = PluggyConnector.__new__(PluggyConnector)
            c._client_id = None
            c._client_secret = None
            c._item_ids = {}
            c._api_key = None
            c._api_key_expires = None
            c._client = None
            c._security = MagicMock()
            c._security.load_credentials.side_effect = Exception("no vault")
            c._load_credentials()
            assert c._client_id == "env-client-id"
            assert c._client_secret == "env-secret"
            assert c._item_ids == {"nubank": "env-item"}


# ══════════════════════════════════════════════════════
#  Tests: Constantes e Mapeamentos
# ══════════════════════════════════════════════════════

class TestPluggyMappings:

    def test_connector_map_nubank(self):
        assert PLUGGY_CONNECTOR_MAP[212] == BankProvider.NUBANK

    def test_connector_map_itau(self):
        assert PLUGGY_CONNECTOR_MAP[201] == BankProvider.ITAU

    def test_name_map(self):
        assert PLUGGY_NAME_MAP["nubank"] == BankProvider.NUBANK
        assert PLUGGY_NAME_MAP["itau"] == BankProvider.ITAU
        assert PLUGGY_NAME_MAP["itaú"] == BankProvider.ITAU

    def test_account_type_map(self):
        assert PLUGGY_ACCOUNT_TYPE_MAP["BANK"] == AccountType.CONTA_CORRENTE
        assert PLUGGY_ACCOUNT_TYPE_MAP["SAVINGS"] == AccountType.POUPANCA
        assert PLUGGY_ACCOUNT_TYPE_MAP["CREDIT"] == AccountType.PAGAMENTO

    def test_brand_map(self):
        assert PLUGGY_BRAND_MAP["VISA"] == CardBrand.VISA
        assert PLUGGY_BRAND_MAP["MASTERCARD"] == CardBrand.MASTERCARD
        assert PLUGGY_BRAND_MAP["ELO"] == CardBrand.ELO
        assert PLUGGY_BRAND_MAP["AMEX"] == CardBrand.AMEX


# ══════════════════════════════════════════════════════
#  Tests: Provider/Brand Resolution
# ══════════════════════════════════════════════════════

class TestPluggyResolution:

    def test_resolve_provider_by_connector_id(self, pluggy):
        assert pluggy._resolve_provider(SAMPLE_ITEM) == BankProvider.NUBANK
        assert pluggy._resolve_provider(SAMPLE_ITEM_ITAU) == BankProvider.ITAU

    def test_resolve_provider_by_name(self, pluggy):
        item = {"connector": {"id": 999, "name": "Nubank S.A."}}
        assert pluggy._resolve_provider(item) == BankProvider.NUBANK

    def test_resolve_provider_fallback(self, pluggy):
        item = {"connector": {"id": 999, "name": "Unknown Bank"}}
        assert pluggy._resolve_provider(item) == BankProvider.NUBANK  # fallback

    def test_resolve_brand(self, pluggy):
        assert pluggy._resolve_brand("MASTERCARD") == CardBrand.MASTERCARD
        assert pluggy._resolve_brand("VISA") == CardBrand.VISA
        assert pluggy._resolve_brand(None) == CardBrand.OTHER
        assert pluggy._resolve_brand("UNKNOWN") == CardBrand.OTHER


# ══════════════════════════════════════════════════════
#  Tests: Classificação de Transações
# ══════════════════════════════════════════════════════

class TestPluggyTransactionClassification:

    def test_classify_pix_received(self, pluggy):
        tx = {"description": "PIX recebido - João", "amount": 500}
        assert pluggy._classify_transaction(tx) == TransactionType.PIX_RECEIVED

    def test_classify_pix_sent(self, pluggy):
        tx = {"description": "PIX enviado - Maria", "amount": -200}
        assert pluggy._classify_transaction(tx) == TransactionType.PIX_SENT

    def test_classify_ted_received(self, pluggy):
        tx = {"description": "TED recebido", "amount": 1000}
        assert pluggy._classify_transaction(tx) == TransactionType.TED_RECEIVED

    def test_classify_ted_sent(self, pluggy):
        tx = {"description": "TED enviado", "amount": -500}
        assert pluggy._classify_transaction(tx) == TransactionType.TED_SENT

    def test_classify_boleto(self, pluggy):
        tx = {"description": "Pagamento BOLETO Energia", "amount": -200}
        assert pluggy._classify_transaction(tx) == TransactionType.BOLETO_PAYMENT

    def test_classify_card_purchase(self, pluggy):
        tx = {"description": "COMPRA Amazon.com.br", "amount": -150}
        assert pluggy._classify_transaction(tx) == TransactionType.CARD_PURCHASE

    def test_classify_fee(self, pluggy):
        tx = {"description": "TARIFA mensal", "amount": -15, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.FEE

    def test_classify_interest(self, pluggy):
        tx = {"description": "JUROS sobre saldo", "amount": 5, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.INTEREST

    def test_classify_refund(self, pluggy):
        tx = {"description": "ESTORNO compra", "amount": 100, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.REFUND

    def test_classify_salary(self, pluggy):
        tx = {"description": "SALARIO empresa", "amount": 5000, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.SALARY

    def test_classify_generic_credit(self, pluggy):
        tx = {"description": "Depósito", "amount": 100, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.CREDIT

    def test_classify_generic_debit(self, pluggy):
        tx = {"description": "Débito diverso", "amount": -50, "category": ""}
        assert pluggy._classify_transaction(tx) == TransactionType.DEBIT

    def test_classify_fee_by_category(self, pluggy):
        tx = {"description": "Cobrança", "amount": -10, "category": "TAX mensal"}
        assert pluggy._classify_transaction(tx) == TransactionType.FEE


# ══════════════════════════════════════════════════════
#  Tests: Parse de Datas
# ══════════════════════════════════════════════════════

class TestPluggyDateParsing:

    def test_parse_date_iso_milliseconds(self, pluggy):
        d = pluggy._parse_date("2026-02-15T10:00:00.000Z")
        assert d == datetime(2026, 2, 15, 10, 0, 0)

    def test_parse_date_iso(self, pluggy):
        d = pluggy._parse_date("2026-02-15T10:00:00Z")
        assert d == datetime(2026, 2, 15, 10, 0, 0)

    def test_parse_date_date_only(self, pluggy):
        d = pluggy._parse_date("2026-02-15")
        assert d == datetime(2026, 2, 15, 0, 0, 0)

    def test_parse_date_none(self, pluggy):
        assert pluggy._parse_date(None) is None

    def test_parse_date_invalid(self, pluggy):
        assert pluggy._parse_date("not-a-date") is None


# ══════════════════════════════════════════════════════
#  Tests: Autenticação
# ══════════════════════════════════════════════════════

class TestPluggyAuthentication:

    @pytest.mark.asyncio
    async def test_ensure_api_key_success(self, pluggy, mock_response):
        resp = mock_response(SAMPLE_AUTH_RESPONSE)
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        await pluggy._ensure_api_key()

        assert pluggy._api_key == "eyJ0eXAi-test-api-key-123"
        assert pluggy._api_key_expires is not None
        mock_client.post.assert_called_once_with("/auth", json={
            "clientId": "test-client-id",
            "clientSecret": "test-client-secret",
        })

    @pytest.mark.asyncio
    async def test_ensure_api_key_cached(self, pluggy):
        pluggy._api_key = "cached-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        # Should not call any HTTP
        await pluggy._ensure_api_key()
        assert pluggy._api_key == "cached-key"

    @pytest.mark.asyncio
    async def test_ensure_api_key_not_configured(self, pluggy_unconfigured):
        with pytest.raises(PluggyConnectionError, match="não configuradas"):
            await pluggy_unconfigured._ensure_api_key()

    @pytest.mark.asyncio
    async def test_ensure_api_key_auth_failure(self, pluggy, mock_response):
        resp = mock_response({"error": "invalid"}, status_code=401, text="Unauthorized")
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        with pytest.raises(PluggyConnectionError, match="Falha na autenticação"):
            await pluggy._ensure_api_key()


# ══════════════════════════════════════════════════════
#  Tests: HTTP GET/POST
# ══════════════════════════════════════════════════════

class TestPluggyHTTP:

    @pytest.mark.asyncio
    async def test_get_success(self, pluggy, mock_response):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        resp = mock_response({"results": [1, 2, 3]})
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        data = await pluggy._get("/test-endpoint", params={"foo": "bar"})
        assert data == {"results": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_get_404_returns_empty(self, pluggy, mock_response):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        resp = mock_response(status_code=404)
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        data = await pluggy._get("/not-found")
        assert data == {}

    @pytest.mark.asyncio
    async def test_get_error_raises(self, pluggy, mock_response):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        resp = mock_response(status_code=500, text="Internal Server Error")
        mock_client = AsyncMock()
        mock_client.get.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        with pytest.raises(PluggyConnectionError, match="HTTP 500"):
            await pluggy._get("/error")

    @pytest.mark.asyncio
    async def test_post_success(self, pluggy, mock_response):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        resp = mock_response({"id": "new-item"})
        mock_client = AsyncMock()
        mock_client.post.return_value = resp
        mock_client.is_closed = False
        pluggy._client = mock_client

        data = await pluggy._post("/items", {"connectorId": 212})
        assert data == {"id": "new-item"}


# ══════════════════════════════════════════════════════
#  Tests: Verificação de Conexão
# ══════════════════════════════════════════════════════

class TestPluggyVerifyConnection:

    @pytest.mark.asyncio
    async def test_verify_connection(self, pluggy, mock_response):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        async def mock_get(path, **kwargs):
            if "item-nubank" in path:
                return mock_response(SAMPLE_ITEM)
            if "item-itau" in path:
                return mock_response(SAMPLE_ITEM_ITAU)
            return mock_response({})

        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.is_closed = False
        pluggy._client = mock_client

        result = await pluggy.verify_connection()
        assert result["authenticated"] is True
        assert "nubank" in result["items"]
        assert "itau" in result["items"]


# ══════════════════════════════════════════════════════
#  Tests: Contas
# ══════════════════════════════════════════════════════

class TestPluggyAccounts:

    @pytest.mark.asyncio
    async def test_get_accounts(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        responses = {
            "/accounts": {"results": [SAMPLE_ACCOUNT]},
            "/items/item-nubank-123": SAMPLE_ITEM,
        }

        mock_client = AsyncMock()
        mock_client.is_closed = False

        async def fake_get(path, headers=None, params=None):
            # Buscar pelo path sem query params
            for key, val in responses.items():
                if key in path:
                    r = MagicMock()
                    r.status_code = 200
                    r.json.return_value = val
                    return r
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {}
            return r

        mock_client.get = fake_get
        pluggy._client = mock_client

        accounts = await pluggy.get_accounts("nubank")
        assert len(accounts) >= 1
        assert accounts[0].provider == BankProvider.NUBANK
        assert accounts[0].number == "12345678"
        assert accounts[0].holder_name == "Edenilson Teixeira"


# ══════════════════════════════════════════════════════
#  Tests: Transações
# ══════════════════════════════════════════════════════

class TestPluggyTransactions:

    @pytest.mark.asyncio
    async def test_get_transactions(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        responses = {
            "/accounts/acc-001": {"id": "acc-001", "itemId": "item-nubank-123"},
            "/items/item-nubank-123": SAMPLE_ITEM,
            "/transactions": {
                "results": [SAMPLE_TRANSACTION_PIX, SAMPLE_TRANSACTION_DEBIT],
                "totalPages": 1,
            },
        }

        mock_client = AsyncMock()
        mock_client.is_closed = False

        async def fake_get(path, headers=None, params=None):
            for key, val in responses.items():
                if key in path:
                    r = MagicMock()
                    r.status_code = 200
                    r.json.return_value = val
                    return r
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {}
            return r

        mock_client.get = fake_get
        pluggy._client = mock_client

        txs = await pluggy.get_transactions("acc-001")
        assert len(txs) == 2
        # PIX recebido
        pix = [t for t in txs if t.type == TransactionType.PIX_RECEIVED]
        assert len(pix) == 1
        assert pix[0].amount == Decimal("3500")


# ══════════════════════════════════════════════════════
#  Tests: Cartões de Crédito
# ══════════════════════════════════════════════════════

class TestPluggyCreditCards:

    @pytest.mark.asyncio
    async def test_get_credit_cards(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        mock_client = AsyncMock()
        mock_client.is_closed = False

        async def fake_get(path, headers=None, params=None):
            path_str = str(path)
            r = MagicMock()
            r.status_code = 200
            # Match most specific paths first
            if "acc-nubank-cc-002" in path_str:
                r.json.return_value = SAMPLE_ACCOUNT_CREDIT
            elif "/items/" in path_str:
                r.json.return_value = SAMPLE_ITEM
            elif "/accounts" in path_str:
                r.json.return_value = {"results": [SAMPLE_ACCOUNT_CREDIT]}
            else:
                r.json.return_value = {}
            return r

        mock_client.get = fake_get
        pluggy._client = mock_client

        cards = await pluggy.get_credit_cards("nubank")
        assert len(cards) >= 1
        card = cards[0]
        assert card.brand == CardBrand.MASTERCARD
        assert card.credit_limit == Decimal("10000")
        assert card.available_limit == Decimal("8500")


# ══════════════════════════════════════════════════════
#  Tests: Faturas (Bills)
# ══════════════════════════════════════════════════════

class TestPluggyBills:

    @pytest.mark.asyncio
    async def test_get_bills(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        responses = {
            "/accounts/acc-cc/bills": {"results": [SAMPLE_BILL]},
            "/accounts/acc-cc": {"id": "acc-cc", "itemId": "item-nubank-123"},
            "/items/item-nubank-123": SAMPLE_ITEM,
        }

        mock_client = AsyncMock()
        mock_client.is_closed = False

        async def fake_get(path, headers=None, params=None):
            for key, val in responses.items():
                if key in str(path):
                    r = MagicMock()
                    r.status_code = 200
                    r.json.return_value = val
                    return r
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {}
            return r

        mock_client.get = fake_get
        pluggy._client = mock_client

        invoices = await pluggy.get_bills("acc-cc")
        assert len(invoices) == 1
        assert invoices[0].total_amount == Decimal("2500")
        assert invoices[0].status == "OPEN"


# ══════════════════════════════════════════════════════
#  Tests: Identidade
# ══════════════════════════════════════════════════════

class TestPluggyIdentity:

    @pytest.mark.asyncio
    async def test_get_identity(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        async def fake_get(path, headers=None, params=None):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"results": [SAMPLE_IDENTITY]}
            return r

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = fake_get
        pluggy._client = mock_client

        identity = await pluggy.get_identity("item-nubank-123")
        assert identity is not None
        assert identity["full_name"] == "Edenilson Teixeira Paschoa"


# ══════════════════════════════════════════════════════
#  Tests: Investimentos
# ══════════════════════════════════════════════════════

class TestPluggyInvestments:

    @pytest.mark.asyncio
    async def test_get_investments(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        async def fake_get(path, headers=None, params=None):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"results": [SAMPLE_INVESTMENT], "totalPages": 1}
            return r

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = fake_get
        pluggy._client = mock_client

        invs = await pluggy.get_investments("item-nubank-123")
        assert len(invs) == 1
        assert invs[0]["name"] == "CDB 110% CDI"
        assert invs[0]["balance"] == 15000.00


# ══════════════════════════════════════════════════════
#  Tests: Empréstimos
# ══════════════════════════════════════════════════════

class TestPluggyLoans:

    @pytest.mark.asyncio
    async def test_get_loans(self, pluggy):
        pluggy._api_key = "test-key"
        pluggy._api_key_expires = datetime.now() + timedelta(hours=1)

        async def fake_get(path, headers=None, params=None):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {"results": [SAMPLE_LOAN]}
            return r

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.get = fake_get
        pluggy._client = mock_client

        loans = await pluggy.get_loans("item-nubank-123")
        assert len(loans) == 1
        assert loans[0]["outstanding_balance"] == 7500.00
        assert loans[0]["monthly_payment"] == 850.00


# ══════════════════════════════════════════════════════
#  Tests: PluggyConnectionError
# ══════════════════════════════════════════════════════

class TestPluggyConnectionError:

    def test_error_with_status(self):
        err = PluggyConnectionError("test error", 401)
        assert "401" in str(err)
        assert "Pluggy" in str(err)
        assert err.status_code == 401

    def test_error_without_status(self):
        err = PluggyConnectionError("test error")
        assert "Pluggy" in str(err)
        assert err.status_code is None

    def test_error_inherits_exception(self):
        err = PluggyConnectionError("boom")
        assert isinstance(err, Exception)


# ══════════════════════════════════════════════════════
#  Tests: Close Client
# ══════════════════════════════════════════════════════

class TestPluggyClose:

    @pytest.mark.asyncio
    async def test_close_client(self, pluggy):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        pluggy._client = mock_client

        await pluggy.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, pluggy):
        mock_client = AsyncMock()
        mock_client.is_closed = True
        pluggy._client = mock_client

        await pluggy.close()
        mock_client.aclose.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_no_client(self, pluggy):
        pluggy._client = None
        await pluggy.close()  # Should not raise
