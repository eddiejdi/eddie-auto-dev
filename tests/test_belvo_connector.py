"""
Testes do Conector Belvo — Eddie Banking Agent.

Cobre:
  - Inicialização e configuração
  - HTTP client e autenticação
  - Gerenciamento de links
  - Conversão de dados Belvo → modelos Eddie
  - Métodos de alto nível (all_accounts, all_balances, all_transactions)
  - Health check
  - Classificação de transações
  - Singleton
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from decimal import Decimal

from specialized_agents.banking.belvo_connector import (
    BelvoConnector,
    BelvoConnectionError,
    get_belvo_connector,
    BELVO_INSTITUTION_MAP,
    PROVIDER_TO_BELVO,
)
from specialized_agents.banking.models import (
    BankProvider, AccountType, TransactionType,
)


# ──────────── Fixtures ────────────

@pytest.fixture
def belvo():
    """Conector Belvo com credenciais de testes."""
    return BelvoConnector(
        secret_id="test-secret-id",
        secret_password="test-secret-password",
        environment="sandbox",
    )


@pytest.fixture
def mock_response():
    """Factory para criar mock httpx responses."""
    def _make(json_data=None, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return resp
    return _make


# Dados de amostra Belvo
SAMPLE_LINK = {
    "id": "link-123-abc",
    "institution": "nubank_br_ofda",
    "status": "valid",
    "access_mode": "recurrent",
    "created_at": "2026-01-15T10:00:00Z",
    "last_accessed_at": "2026-02-01T12:00:00Z",
}

SAMPLE_ACCOUNT = {
    "id": "acc-456-def",
    "type": "CHECKING",
    "name": "Conta Corrente",
    "number": "12345-6",
    "agency": "0001",
    "currency": "BRL",
    "status": "ACTIVE",
    "institution": {"name": "Nu Pagamentos S.A."},
    "category": "CHECKING_ACCOUNT",
}

SAMPLE_BALANCE = {
    "id": "bal-789",
    "account": {"id": "acc-456-def"},
    "current_balance": 5432.10,
    "blocked_balance": 0,
    "currency": "BRL",
    "collected_at": "2026-02-01T12:00:00Z",
}

SAMPLE_TRANSACTION = {
    "id": "tx-001",
    "account": {"id": "acc-456-def"},
    "type": "INFLOW",
    "amount": 3500.00,
    "description": "PIX recebido - Salário",
    "category": "Income",
    "subcategory": "Salary",
    "value_date": "2026-02-01",
    "balance": 8932.10,
    "status": "PROCESSED",
    "reference": "E123456",
    "merchant": {"name": "Empresa XYZ"},
}

SAMPLE_TRANSACTION_OUTFLOW = {
    "id": "tx-002",
    "account": "acc-456-def",
    "type": "OUTFLOW",
    "amount": -150.00,
    "description": "IFOOD *LANCHONETE",
    "category": "Food and Drink",
    "subcategory": "Restaurant",
    "value_date": "2026-02-02",
    "balance": 8782.10,
    "status": "PROCESSED",
    "reference": "",
    "merchant": {"name": "iFood"},
}


# ──────────── Tests: Configuração ────────────

class TestBelvoConfiguration:

    def test_is_configured_true(self, belvo):
        assert belvo.is_configured is True

    def test_is_configured_false(self):
        b = BelvoConnector(secret_id="", secret_password="")
        assert b.is_configured is False

    def test_sandbox_url(self, belvo):
        assert belvo.base_url == "https://sandbox.belvo.com"

    def test_production_url(self):
        b = BelvoConnector(
            secret_id="x", secret_password="y", environment="production"
        )
        assert b.base_url == "https://api.belvo.com"

    def test_env_var_fallback(self):
        with patch.dict("os.environ", {
            "BELVO_SECRET_ID": "env-id",
            "BELVO_SECRET_PASSWORD": "env-pw",
            "BELVO_ENV": "production",
        }):
            b = BelvoConnector()
            assert b.secret_id == "env-id"
            assert b.secret_password == "env-pw"
            assert b.environment == "production"
            assert b.base_url == "https://api.belvo.com"


# ──────────── Tests: Institution Mapping ────────────

class TestInstitutionMapping:

    def test_map_nubank(self):
        assert BELVO_INSTITUTION_MAP["nubank_br_ofda"] == BankProvider.NUBANK

    def test_map_itau(self):
        assert BELVO_INSTITUTION_MAP["itau_br_ofda"] == BankProvider.ITAU

    def test_map_santander(self):
        assert BELVO_INSTITUTION_MAP["santander_br_ofda"] == BankProvider.SANTANDER

    def test_reverse_map(self):
        assert PROVIDER_TO_BELVO[BankProvider.NUBANK] == "nubank_br_ofda"
        assert PROVIDER_TO_BELVO[BankProvider.ITAU] == "itau_br_ofda"
        assert PROVIDER_TO_BELVO[BankProvider.SANTANDER] == "santander_br_ofda"


# ──────────── Tests: Data Conversion ────────────

class TestDataConversion:

    def test_to_bank_account(self, belvo):
        account = belvo._to_bank_account(SAMPLE_ACCOUNT, BankProvider.NUBANK)
        assert account.provider == BankProvider.NUBANK
        assert account.account_type == AccountType.CONTA_CORRENTE
        assert account.branch == "0001"
        assert account.number == "12345-6"
        assert account.currency == "BRL"
        assert account.status == "ACTIVE"
        assert account.metadata["belvo_id"] == "acc-456-def"

    def test_to_bank_account_closed(self, belvo):
        acc = {**SAMPLE_ACCOUNT, "status": "CLOSED"}
        account = belvo._to_bank_account(acc, BankProvider.ITAU)
        assert account.status == "CLOSED"

    def test_to_bank_account_savings(self, belvo):
        acc = {**SAMPLE_ACCOUNT, "type": "SAVINGS"}
        account = belvo._to_bank_account(acc, BankProvider.SANTANDER)
        assert account.account_type == AccountType.POUPANCA

    def test_to_balance(self, belvo):
        balance = belvo._to_balance(SAMPLE_BALANCE, "acc-456-def", BankProvider.NUBANK)
        assert balance.provider == BankProvider.NUBANK
        assert balance.available == Decimal("5432.1")
        assert balance.blocked == Decimal("0")
        assert balance.currency == "BRL"
        assert balance.account_id == "acc-456-def"

    def test_to_transaction_inflow(self, belvo):
        tx = belvo._to_transaction(SAMPLE_TRANSACTION, BankProvider.NUBANK)
        assert tx.provider == BankProvider.NUBANK
        assert tx.amount == Decimal("3500.0")
        assert tx.type == TransactionType.PIX_RECEIVED  # "PIX" in description + amount > 0
        assert tx.description == "PIX recebido - Salário"
        assert tx.counterpart_name == "Empresa XYZ"

    def test_to_transaction_outflow(self, belvo):
        tx = belvo._to_transaction(SAMPLE_TRANSACTION_OUTFLOW, BankProvider.NUBANK)
        assert tx.amount == Decimal("150.0")  # abs()
        assert tx.type == TransactionType.DEBIT  # OUTFLOW
        assert tx.account_id == "acc-456-def"  # string account


# ──────────── Tests: Transaction Classification ────────────

class TestTransactionClassification:

    def test_classify_pix_received(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("100"), "PIX recebido - Fulano") == TransactionType.PIX_RECEIVED

    def test_classify_pix_sent(self, belvo):
        assert belvo._classify_transaction("OUTFLOW", Decimal("-50"), "Pix enviado p/ Ciclano") == TransactionType.PIX_SENT

    def test_classify_ted_received(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("1000"), "TED recebida") == TransactionType.TED_RECEIVED

    def test_classify_ted_sent(self, belvo):
        assert belvo._classify_transaction("OUTFLOW", Decimal("-500"), "TED enviada") == TransactionType.TED_SENT

    def test_classify_boleto(self, belvo):
        assert belvo._classify_transaction("OUTFLOW", Decimal("-200"), "PGTO BOLETO ELETRICO") == TransactionType.BOLETO_PAYMENT

    def test_classify_fee(self, belvo):
        assert belvo._classify_transaction("OUTFLOW", Decimal("-10"), "Tarifa mensal") == TransactionType.FEE

    def test_classify_interest(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("5"), "Juros poupança") == TransactionType.INTEREST

    def test_classify_salary(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("5000"), "Salário ref 01/2026") == TransactionType.SALARY

    def test_classify_refund(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("99"), "Estorno compra Amazon") == TransactionType.REFUND

    def test_classify_generic_debit(self, belvo):
        assert belvo._classify_transaction("OUTFLOW", Decimal("-30"), "Compra no debito") == TransactionType.DEBIT

    def test_classify_generic_credit(self, belvo):
        assert belvo._classify_transaction("INFLOW", Decimal("100"), "Deposito em dinheiro") == TransactionType.CREDIT

    def test_classify_other(self, belvo):
        assert belvo._classify_transaction("", Decimal("0"), "") == TransactionType.OTHER


# ──────────── Tests: Link Management ────────────

class TestLinkManagement:

    @pytest.mark.asyncio
    async def test_list_links(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": [SAMPLE_LINK]}
            links = await belvo.list_links()
            assert len(links) == 1
            assert links[0]["id"] == "link-123-abc"
            assert belvo.get_link_for_provider(BankProvider.NUBANK) == "link-123-abc"

    @pytest.mark.asyncio
    async def test_create_link(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = SAMPLE_LINK
            result = await belvo.create_link("nubank_br_ofda")
            assert result["id"] == "link-123-abc"
            mock_req.assert_called_once_with(
                "POST", "/api/links/",
                json_data={"institution": "nubank_br_ofda", "access_mode": "recurrent"}
            )

    @pytest.mark.asyncio
    async def test_delete_link(self, belvo):
        belvo._links["link-123"] = {}
        belvo._link_by_provider[BankProvider.NUBANK] = "link-123"
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = None
            await belvo.delete_link("link-123")
            assert "link-123" not in belvo._links
            assert BankProvider.NUBANK not in belvo._link_by_provider


# ──────────── Tests: Accounts ────────────

class TestAccounts:

    @pytest.mark.asyncio
    async def test_retrieve_accounts(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_ACCOUNT]
            accounts = await belvo.retrieve_accounts("link-123")
            assert len(accounts) == 1
            assert accounts[0]["id"] == "acc-456-def"

    @pytest.mark.asyncio
    async def test_list_accounts(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"results": [SAMPLE_ACCOUNT]}
            accounts = await belvo.list_accounts("link-123")
            assert len(accounts) == 1


# ──────────── Tests: Balances ────────────

class TestBalances:

    @pytest.mark.asyncio
    async def test_retrieve_balances(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_BALANCE]
            balances = await belvo.retrieve_balances("link-123")
            assert len(balances) == 1
            assert balances[0]["current_balance"] == 5432.10


# ──────────── Tests: Transactions ────────────

class TestTransactions:

    @pytest.mark.asyncio
    async def test_retrieve_transactions(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [SAMPLE_TRANSACTION]
            txs = await belvo.retrieve_transactions("link-123", "2026-02-01")
            assert len(txs) == 1

    @pytest.mark.asyncio
    async def test_list_transactions_paginated(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = [
                {"results": [SAMPLE_TRANSACTION], "next": "page2"},
                {"results": [SAMPLE_TRANSACTION_OUTFLOW], "next": None},
            ]
            txs = await belvo.list_transactions(link_id="link-123")
            assert len(txs) == 2


# ──────────── Tests: High-level Methods ────────────

class TestHighLevel:

    @pytest.mark.asyncio
    async def test_get_all_accounts(self, belvo):
        with patch.object(belvo, 'list_links', new_callable=AsyncMock) as mock_links, \
             patch.object(belvo, 'list_accounts', new_callable=AsyncMock) as mock_accounts:
            mock_links.return_value = [SAMPLE_LINK]
            belvo._link_by_provider = {BankProvider.NUBANK: "link-123-abc"}
            mock_accounts.return_value = [SAMPLE_ACCOUNT]

            accounts = await belvo.get_all_accounts()
            assert len(accounts) == 1
            assert accounts[0].provider == BankProvider.NUBANK

    @pytest.mark.asyncio
    async def test_get_all_balances(self, belvo):
        with patch.object(belvo, 'list_links', new_callable=AsyncMock) as mock_links, \
             patch.object(belvo, 'list_balances', new_callable=AsyncMock) as mock_bal:
            mock_links.return_value = [SAMPLE_LINK]
            belvo._link_by_provider = {BankProvider.NUBANK: "link-123-abc"}
            mock_bal.return_value = [SAMPLE_BALANCE]

            balances = await belvo.get_all_balances()
            assert len(balances) == 1
            assert balances[0].available == Decimal("5432.1")

    @pytest.mark.asyncio
    async def test_get_all_transactions(self, belvo):
        with patch.object(belvo, 'list_links', new_callable=AsyncMock) as mock_links, \
             patch.object(belvo, 'list_transactions', new_callable=AsyncMock) as mock_txs:
            mock_links.return_value = [SAMPLE_LINK]
            belvo._link_by_provider = {BankProvider.NUBANK: "link-123-abc"}
            mock_txs.return_value = [SAMPLE_TRANSACTION, SAMPLE_TRANSACTION_OUTFLOW]

            txs = await belvo.get_all_transactions()
            assert len(txs) == 2
            assert txs[0].date >= txs[1].date  # ordenado por data


# ──────────── Tests: Health Check ────────────

class TestHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self):
        b = BelvoConnector(secret_id="", secret_password="")
        result = await b.health_check()
        assert result["belvo_configured"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_ok(self, belvo):
        with patch.object(belvo, 'get_connected_banks', new_callable=AsyncMock) as mock_banks:
            mock_banks.return_value = {
                BankProvider.NUBANK: {
                    "link_id": "link-123",
                    "status": "valid",
                    "last_accessed_at": "2026-02-01T12:00:00Z",
                }
            }
            result = await belvo.health_check()
            assert result["belvo_configured"] is True
            assert result["environment"] == "sandbox"
            assert result["total_connected"] == 1
            assert result["banks"]["nubank"]["connected"] is True


# ──────────── Tests: Error Handling ────────────

class TestErrorHandling:

    def test_belvo_connection_error_with_status(self):
        err = BelvoConnectionError("test error", 401)
        assert "401" in str(err)
        assert err.status_code == 401

    def test_belvo_connection_error_without_status(self):
        err = BelvoConnectionError("network failed")
        assert "network failed" in str(err)
        assert err.status_code is None


# ──────────── Tests: Singleton ────────────

class TestSingleton:

    def test_get_belvo_connector_returns_same_instance(self):
        # Reset singleton
        import specialized_agents.banking.belvo_connector as mod
        mod._belvo_connector = None

        c1 = get_belvo_connector()
        c2 = get_belvo_connector()
        assert c1 is c2

        # Cleanup
        mod._belvo_connector = None


# ──────────── Tests: Widget Token ────────────

class TestWidgetToken:

    @pytest.mark.asyncio
    async def test_create_widget_token(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {
                "access": "eyJ-token-access",
                "refresh": "eyJ-token-refresh",
                "link": None,
            }
            result = await belvo.create_widget_token()
            assert "access" in result
            mock_req.assert_called_once()


# ──────────── Tests: Bills ────────────

class TestBills:

    @pytest.mark.asyncio
    async def test_retrieve_bills(self, belvo):
        with patch.object(belvo, '_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [{"id": "bill-1", "total": 500.00}]
            bills = await belvo.retrieve_bills("link-123")
            assert len(bills) == 1


# ──────────── Tests: Client lifecycle ────────────

class TestClientLifecycle:

    @pytest.mark.asyncio
    async def test_close(self, belvo):
        # Force client creation
        mock_client = MagicMock()
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        belvo._client = mock_client
        await belvo.close()
        mock_client.aclose.assert_called_once()
        assert belvo._client is None
