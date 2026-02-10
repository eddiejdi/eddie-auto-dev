"""
Banking Integration Agent — Eddie Auto-Dev
Integração com bancos brasileiros via Open Finance Brasil e APIs proprietárias.

Bancos suportados:
  - Santander Brasil
  - Itaú Unibanco
  - Nubank
  - Mercado Pago (Mercado Livre)

Conformidade: Open Finance Brasil (BCB), LGPD, PCI-DSS
"""

from .models import (
    BankAccount,
    Transaction,
    Balance,
    PixKey,
    PixTransfer,
    BankStatement,
    CreditCard,
    Invoice,
    Consent,
    ConsentStatus,
    TransactionType,
    AccountType,
    BankProvider,
)
from .base_connector import BaseBankConnector, BankConnectionError, BankAuthError
from .santander_connector import SantanderConnector
from .itau_connector import ItauConnector
from .nubank_connector import NubankConnector
from .mercadopago_connector import MercadoPagoConnector
from .belvo_connector import BelvoConnector, BelvoConnectionError, get_belvo_connector
from .pluggy_connector import PluggyConnector, PluggyConnectionError
from .security import BankingSecurityManager

__all__ = [
    # Models
    "BankAccount", "Transaction", "Balance", "PixKey", "PixTransfer",
    "BankStatement", "CreditCard", "Invoice", "Consent", "ConsentStatus",
    "TransactionType", "AccountType", "BankProvider",
    # Connectors
    "BaseBankConnector", "BankConnectionError", "BankAuthError",
    "SantanderConnector", "ItauConnector", "NubankConnector", "MercadoPagoConnector",
    # Belvo (Open Finance aggregator)
    "BelvoConnector", "BelvoConnectionError", "get_belvo_connector",
    # Pluggy (Open Finance aggregator)
    "PluggyConnector", "PluggyConnectionError",
    # Security
    "BankingSecurityManager",
]
