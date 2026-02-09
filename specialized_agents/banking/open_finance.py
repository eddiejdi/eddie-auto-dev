"""
Open Finance Brasil — Utilitários compartilhados.

Implementa padrões OFB (Banco Central do Brasil):
  - Discovery de endpoints por ISPB
  - Geração de consent requests
  - Headers e autenticação padrão
  - Constantes e URLs de diretório

Referência: https://openfinancebrasil.atlassian.net/wiki/spaces/OF/overview
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

# ──────────── Constantes Open Finance Brasil ────────────

# Diretório de participantes (sandbox / produção)
OFB_DIRECTORY_SANDBOX = "https://data.sandbox.directory.openbankingbrasil.org.br"
OFB_DIRECTORY_PRODUCTION = "https://data.directory.openbankingbrasil.org.br"

# ISPB dos bancos suportados
BANK_ISPB = {
    "santander": "90400888",
    "itau": "60701190",
    "nubank": "18236120",
}

# Scopes padrão Open Finance
OFB_SCOPES = {
    "accounts": "accounts",
    "balances": "balances",
    "transactions": "transactions",
    "credit_cards": "credit-cards-accounts",
    "pix": "payments",
    "consent": "consents",
}

# Permissões padrão para consent
OFB_DEFAULT_PERMISSIONS = [
    "ACCOUNTS_READ",
    "ACCOUNTS_BALANCES_READ",
    "ACCOUNTS_TRANSACTIONS_READ",
    "ACCOUNTS_OVERDRAFT_LIMITS_READ",
    "CREDIT_CARDS_ACCOUNTS_READ",
    "CREDIT_CARDS_ACCOUNTS_BILLS_READ",
    "CREDIT_CARDS_ACCOUNTS_BILLS_TRANSACTIONS_READ",
    "CREDIT_CARDS_ACCOUNTS_LIMITS_READ",
    "CREDIT_CARDS_ACCOUNTS_TRANSACTIONS_READ",
    "RESOURCES_READ",
]

OFB_PAYMENT_PERMISSIONS = [
    "PAYMENTS_INITIATE",
]

# API Versions
OFB_API_VERSIONS = {
    "accounts": "v2",
    "balances": "v2",
    "transactions": "v2",
    "credit_cards": "v2",
    "consents": "v3",
    "payments": "v4",
    "pix": "v3",
}


def build_ofb_headers(
    access_token: str,
    interaction_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    content_type: str = "application/json",
) -> Dict[str, str]:
    """
    Constrói headers padrão Open Finance Brasil.
    """
    import uuid

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "x-fapi-interaction-id": interaction_id or str(uuid.uuid4()),
        "x-fapi-auth-date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
    }
    if idempotency_key:
        headers["x-idempotency-key"] = idempotency_key
    return headers


def build_consent_request(
    permissions: Optional[List[str]] = None,
    expiration_hours: int = 720,  # 30 dias
    transaction_from: Optional[str] = None,
    transaction_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gera body de criação de consentimento Open Finance Brasil.
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=expiration_hours)

    consent = {
        "data": {
            "permissions": permissions or OFB_DEFAULT_PERMISSIONS,
            "expirationDateTime": expiration.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
    }

    if transaction_from or transaction_to:
        consent["data"]["transactionFromDateTime"] = (
            transaction_from or (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00.000Z")
        )
        consent["data"]["transactionToDateTime"] = (
            transaction_to or now.strftime("%Y-%m-%dT23:59:59.000Z")
        )

    return consent


def build_pix_payment_request(
    amount: str,
    pix_key: str,
    pix_key_type: str,
    description: Optional[str] = None,
    end_to_end_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gera body de iniciação de pagamento PIX via Open Finance.
    """
    import uuid

    return {
        "data": {
            "localInstrument": "DICT",
            "payment": {
                "amount": amount,
                "currency": "BRL",
            },
            "creditorAccount": {
                "proxy": pix_key,
                "proxyType": pix_key_type.upper(),
            },
            "remittanceInformation": description or "Pagamento via Eddie Banking Agent",
            "endToEndId": end_to_end_id or f"E{uuid.uuid4().hex[:32].upper()}",
        }
    }


def get_ofb_endpoint(provider: str, resource: str, sandbox: bool = True) -> str:
    """
    Retorna URL base do endpoint Open Finance para um banco.
    Em produção, essas URLs vêm do diretório de participantes.
    """
    # URLs de sandbox / conhecidas
    SANDBOX_URLS = {
        "santander": {
            "base": "https://trust-open.api.santander.com.br",
            "auth": "https://trust-open.api.santander.com.br/auth/oauth/v2",
        },
        "itau": {
            "base": "https://secure.api.itau",
            "auth": "https://sts.itau.com.br/api/oauth",
        },
        "nubank": {
            "base": "https://open-banking.nubank.com.br",
            "auth": "https://open-banking.nubank.com.br/auth",
        },
    }

    provider_urls = SANDBOX_URLS.get(provider, {})
    if resource == "auth":
        return provider_urls.get("auth", "")
    return provider_urls.get("base", "")
