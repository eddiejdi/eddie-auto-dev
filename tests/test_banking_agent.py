"""
Testes unitários para o Banking Integration Agent.

Testa models, security, conectores (mock) e agent orquestrador.
"""

import pytest
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


# ──────────── Models ────────────

class TestModels:
    """Testes dos modelos de dados bancários."""

    def test_bank_account_creation(self):
        from specialized_agents.banking.models import BankAccount, BankProvider, AccountType
        acc = BankAccount(
            id="acc-123",
            provider=BankProvider.NUBANK,
            account_type=AccountType.PAGAMENTO,
            branch="0001",
            number="12345678",
            holder_name="Eddie Dev",
            holder_document="123.456.789-00",
        )
        assert acc.provider == BankProvider.NUBANK
        assert acc.display_name == "Nubank - Ag 0001 / CC 12345678"
        d = acc.to_dict()
        assert d["provider"] == "nubank"

    def test_balance(self):
        from specialized_agents.banking.models import Balance, BankProvider
        bal = Balance(
            account_id="acc-1",
            provider=BankProvider.ITAU,
            available=Decimal("1500.50"),
            blocked=Decimal("200.00"),
        )
        assert bal.total == Decimal("1700.50")
        d = bal.to_dict()
        assert d["available"] == "1500.50"

    def test_transaction_is_credit(self):
        from specialized_agents.banking.models import Transaction, BankProvider, TransactionType
        tx_credit = Transaction(
            id="tx-1",
            account_id="acc-1",
            provider=BankProvider.SANTANDER,
            type=TransactionType.PIX_RECEIVED,
            amount=Decimal("500.00"),
            description="PIX Recebido",
            date=datetime.now(),
        )
        assert tx_credit.is_credit is True

        tx_debit = Transaction(
            id="tx-2",
            account_id="acc-1",
            provider=BankProvider.SANTANDER,
            type=TransactionType.PIX_SENT,
            amount=Decimal("100.00"),
            description="PIX Enviado",
            date=datetime.now(),
        )
        assert tx_debit.is_credit is False

    def test_pix_transfer(self):
        from specialized_agents.banking.models import PixTransfer, PixKeyType
        pix = PixTransfer(
            id="pix-1",
            source_account_id="acc-1",
            destination_key="12345678901",
            destination_key_type=PixKeyType.CPF,
            amount=Decimal("250.00"),
        )
        assert pix.status == "PENDING"
        d = pix.to_dict()
        assert d["destination_key_type"] == "CPF"

    def test_consolidated_view(self):
        from specialized_agents.banking.models import (
            ConsolidatedView, Balance, BankProvider, BankAccount, AccountType
        )
        view = ConsolidatedView(
            balances=[
                Balance("acc-1", BankProvider.NUBANK, Decimal("1000")),
                Balance("acc-2", BankProvider.ITAU, Decimal("2500.50")),
            ],
            accounts=[
                BankAccount("acc-1", BankProvider.NUBANK, AccountType.PAGAMENTO, "0001", "123", "Eddie", "***"),
            ],
        )
        assert view.total_available == Decimal("3500.50")
        text = view.summary_text()
        assert "R$" in text
        assert "Multi-Banco" in text

    def test_consent_validity(self):
        from specialized_agents.banking.models import Consent, BankProvider, ConsentStatus
        valid = Consent(
            id="c-1",
            provider=BankProvider.SANTANDER,
            status=ConsentStatus.AUTHORISED,
            permissions=["ACCOUNTS_READ"],
            expiration_datetime=datetime.now() + timedelta(days=30),
        )
        assert valid.is_valid is True

        expired = Consent(
            id="c-2",
            provider=BankProvider.SANTANDER,
            status=ConsentStatus.AUTHORISED,
            permissions=["ACCOUNTS_READ"],
            expiration_datetime=datetime.now() - timedelta(days=1),
        )
        assert expired.is_valid is False

    def test_credit_card_used_limit(self):
        from specialized_agents.banking.models import CreditCard, BankProvider, CardBrand
        card = CreditCard(
            id="card-1",
            provider=BankProvider.NUBANK,
            last_four_digits="1234",
            brand=CardBrand.MASTERCARD,
            holder_name="Eddie",
            credit_limit=Decimal("5000"),
            available_limit=Decimal("3000"),
            closing_day=3,
            due_day=10,
        )
        assert card.used_limit == Decimal("2000")


# ──────────── Security ────────────

class TestSecurity:
    """Testes do gerenciador de segurança."""

    def test_mask_cpf(self):
        from specialized_agents.banking.security import BankingSecurityManager
        assert BankingSecurityManager.mask_document("12345678901") == "123.***.**01"

    def test_mask_cnpj(self):
        from specialized_agents.banking.security import BankingSecurityManager
        assert BankingSecurityManager.mask_document("12345678000190") == "12.***.***/****-90"

    def test_mask_account(self):
        from specialized_agents.banking.security import BankingSecurityManager
        assert BankingSecurityManager.mask_account("12345678") == "****5678"
        assert BankingSecurityManager.mask_account("1234") == "****"

    def test_pkce_generation(self):
        from specialized_agents.banking.security import BankingSecurityManager
        verifier, challenge = BankingSecurityManager.generate_pkce()
        assert len(verifier) > 40
        assert len(challenge) > 20
        # Deve gerar valores diferentes a cada chamada
        v2, c2 = BankingSecurityManager.generate_pkce()
        assert verifier != v2

    def test_state_generation(self):
        from specialized_agents.banking.security import BankingSecurityManager
        state1 = BankingSecurityManager.generate_state()
        state2 = BankingSecurityManager.generate_state()
        assert state1 != state2
        assert len(state1) > 20

    def test_encrypt_decrypt(self, tmp_path):
        from specialized_agents.banking.security import BankingSecurityManager
        sec = BankingSecurityManager(data_dir=tmp_path)
        encrypted = sec.encrypt("minha_senha_secreta")
        assert encrypted != "minha_senha_secreta"
        decrypted = sec.decrypt(encrypted)
        assert decrypted == "minha_senha_secreta"

    def test_store_load_credentials(self, tmp_path):
        from specialized_agents.banking.security import BankingSecurityManager
        sec = BankingSecurityManager(data_dir=tmp_path)
        creds = {"client_id": "abc123", "client_secret": "secret456"}
        sec.store_credentials("test_bank", creds)
        loaded = sec.load_credentials("test_bank")
        assert loaded == creds

    def test_delete_credentials(self, tmp_path):
        from specialized_agents.banking.security import BankingSecurityManager
        sec = BankingSecurityManager(data_dir=tmp_path)
        sec.store_credentials("to_delete", {"key": "val"})
        assert sec.delete_credentials("to_delete") is True
        assert sec.load_credentials("to_delete") is None

    def test_audit_log(self, tmp_path):
        from specialized_agents.banking.security import BankingSecurityManager
        sec = BankingSecurityManager(data_dir=tmp_path)
        sec.store_credentials("bank_x", {"a": "b"})
        logs = sec.get_audit_log("bank_x")
        assert len(logs) >= 1
        assert logs[0]["provider"] == "bank_x"

    def test_webhook_validation(self):
        from specialized_agents.banking.security import BankingSecurityManager
        payload = b'{"amount": 100}'
        import hashlib, hmac
        secret = "test_secret"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert BankingSecurityManager.validate_webhook_signature(payload, sig, secret) is True
        assert BankingSecurityManager.validate_webhook_signature(payload, "wrong", secret) is False

    def test_oauth_token_expiry(self):
        from specialized_agents.banking.security import OAuthToken
        token = OAuthToken(
            access_token="abc",
            expires_in=3600,
            issued_at=datetime.now() - timedelta(hours=2),
        )
        assert token.is_expired is True

        fresh = OAuthToken(
            access_token="xyz",
            expires_in=3600,
        )
        assert fresh.is_expired is False


# ──────────── Open Finance Utils ────────────

class TestOpenFinance:
    """Testes dos utilitários Open Finance Brasil."""

    def test_build_headers(self):
        from specialized_agents.banking.open_finance import build_ofb_headers
        headers = build_ofb_headers("my_token", interaction_id="int-123")
        assert headers["Authorization"] == "Bearer my_token"
        assert headers["x-fapi-interaction-id"] == "int-123"

    def test_build_consent_request(self):
        from specialized_agents.banking.open_finance import build_consent_request
        body = build_consent_request(permissions=["ACCOUNTS_READ"])
        assert "ACCOUNTS_READ" in body["data"]["permissions"]
        assert "expirationDateTime" in body["data"]

    def test_build_pix_request(self):
        from specialized_agents.banking.open_finance import build_pix_payment_request
        body = build_pix_payment_request("100.00", "12345678901", "CPF", "Pagamento teste")
        assert body["data"]["payment"]["amount"] == "100.00"
        assert body["data"]["creditorAccount"]["proxyType"] == "CPF"

    def test_get_endpoint(self):
        from specialized_agents.banking.open_finance import get_ofb_endpoint
        url = get_ofb_endpoint("santander", "base")
        assert "santander" in url
        auth_url = get_ofb_endpoint("itau", "auth")
        assert "itau" in auth_url


# ──────────── Banking Agent (mocked) ────────────

class TestBankingAgent:
    """Testes do agent orquestrador com mocks."""

    def test_detect_pix_key_cpf(self):
        from specialized_agents.banking_agent import BankingAgent
        from specialized_agents.banking.models import PixKeyType
        assert BankingAgent._detect_pix_key_type("12345678901") == PixKeyType.CPF

    def test_detect_pix_key_email(self):
        from specialized_agents.banking_agent import BankingAgent
        from specialized_agents.banking.models import PixKeyType
        assert BankingAgent._detect_pix_key_type("eddie@example.com") == PixKeyType.EMAIL

    def test_detect_pix_key_phone(self):
        from specialized_agents.banking_agent import BankingAgent
        from specialized_agents.banking.models import PixKeyType
        assert BankingAgent._detect_pix_key_type("+5511999998888") == PixKeyType.PHONE

    def test_detect_pix_key_random(self):
        from specialized_agents.banking_agent import BankingAgent
        from specialized_agents.banking.models import PixKeyType
        assert BankingAgent._detect_pix_key_type("abc-def-ghi-jkl") == PixKeyType.EVP

    def test_auto_categorize(self):
        from specialized_agents.banking_agent import BankingAgent
        from specialized_agents.banking.models import Transaction, BankProvider, TransactionType

        agent = BankingAgent()

        tx_food = Transaction(
            id="1", account_id="a", provider=BankProvider.NUBANK,
            type=TransactionType.DEBIT, amount=Decimal("50"), description="IFOOD *Restaurante",
            date=datetime.now(),
        )
        assert agent._auto_categorize(tx_food) == "Alimentação"

        tx_transport = Transaction(
            id="2", account_id="a", provider=BankProvider.NUBANK,
            type=TransactionType.DEBIT, amount=Decimal("20"), description="Uber Trip",
            date=datetime.now(),
        )
        assert agent._auto_categorize(tx_transport) == "Transporte"

        tx_streaming = Transaction(
            id="3", account_id="a", provider=BankProvider.NUBANK,
            type=TransactionType.DEBIT, amount=Decimal("40"), description="Netflix.com",
            date=datetime.now(),
        )
        assert agent._auto_categorize(tx_streaming) == "Lazer"

    def test_connected_providers(self):
        from specialized_agents.banking_agent import BankingAgent
        agent = BankingAgent()
        assert agent.connected_providers == []

    def test_set_spending_threshold(self):
        from specialized_agents.banking_agent import BankingAgent
        agent = BankingAgent()
        agent.set_spending_threshold("Alimentação", Decimal("500"))
        assert agent._spending_thresholds["Alimentação"] == Decimal("500")

    @pytest.mark.asyncio
    async def test_handle_unknown_command(self):
        from specialized_agents.banking_agent import BankingAgent
        agent = BankingAgent()
        result = await agent.handle_telegram_command("/desconhecido")
        assert "Comandos disponíveis" in result

    @pytest.mark.asyncio
    async def test_get_consolidated_no_connectors(self):
        from specialized_agents.banking_agent import BankingAgent
        agent = BankingAgent()
        view = await agent.get_consolidated_view()
        assert view.total_available == Decimal("0")
        assert len(view.accounts) == 0


# ──────────── Connector Base ────────────

class TestBaseConnector:
    """Testes do conector base."""

    def test_repr(self):
        from specialized_agents.banking.santander_connector import SantanderConnector
        conn = SantanderConnector(sandbox=True)
        assert "SantanderConnector" in repr(conn)
        assert "sandbox" in repr(conn)

    def test_generate_id(self):
        from specialized_agents.banking.santander_connector import SantanderConnector
        conn = SantanderConnector()
        id1 = conn._generate_id()
        id2 = conn._generate_id()
        assert id1 != id2
        assert len(id1) > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
