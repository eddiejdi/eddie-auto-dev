"""
Modelos de dados para integração bancária.
Segue padrões Open Finance Brasil (OFB) + extensões para Mercado Pago.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any


# ──────────────────────────── Enums ────────────────────────────

class BankProvider(str, Enum):
    """Bancos/provedores suportados"""
    SANTANDER = "santander"
    ITAU = "itau"
    NUBANK = "nubank"
    MERCADOPAGO = "mercadopago"


class AccountType(str, Enum):
    """Tipos de conta bancária (Open Finance Brasil)"""
    CONTA_CORRENTE = "CONTA_DEPOSITO_A_VISTA"
    POUPANCA = "CONTA_POUPANCA"
    PAGAMENTO = "CONTA_PAGAMENTO_PRE_PAGA"
    SALARIO = "CONTA_SALARIO"


class TransactionType(str, Enum):
    """Tipos de transação"""
    CREDIT = "CREDITO"
    DEBIT = "DEBITO"
    PIX_SENT = "PIX_ENVIADO"
    PIX_RECEIVED = "PIX_RECEBIDO"
    TED_SENT = "TED_ENVIADO"
    TED_RECEIVED = "TED_RECEBIDO"
    BOLETO_PAYMENT = "PAGAMENTO_BOLETO"
    CARD_PURCHASE = "COMPRA_CARTAO"
    TRANSFER = "TRANSFERENCIA"
    FEE = "TARIFA"
    TAX = "IMPOSTO"
    INTEREST = "JUROS"
    REFUND = "ESTORNO"
    SALARY = "SALARIO"
    OTHER = "OUTRO"


class ConsentStatus(str, Enum):
    """Status do consentimento Open Finance"""
    AWAITING_AUTHORISATION = "AWAITING_AUTHORISATION"
    AUTHORISED = "AUTHORISED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class PixKeyType(str, Enum):
    """Tipos de chave PIX"""
    CPF = "CPF"
    CNPJ = "CNPJ"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    EVP = "EVP"  # Chave aleatória


class CardBrand(str, Enum):
    """Bandeiras de cartão"""
    VISA = "VISA"
    MASTERCARD = "MASTERCARD"
    ELO = "ELO"
    AMEX = "AMEX"
    HIPERCARD = "HIPERCARD"
    OTHER = "OTHER"


# ──────────────────────────── Dataclasses ────────────────────────────

@dataclass
class BankAccount:
    """Conta bancária"""
    id: str
    provider: BankProvider
    account_type: AccountType
    branch: str  # Agência
    number: str  # Número da conta
    holder_name: str
    holder_document: str  # CPF/CNPJ (mascarado)
    currency: str = "BRL"
    status: str = "ACTIVE"
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider.value,
            "account_type": self.account_type.value,
            "branch": self.branch,
            "number": self.number,
            "holder_name": self.holder_name,
            "holder_document": self.holder_document,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def display_name(self) -> str:
        return f"{self.provider.value.title()} - Ag {self.branch} / CC {self.number}"


@dataclass
class Balance:
    """Saldo de conta"""
    account_id: str
    provider: BankProvider
    available: Decimal  # Saldo disponível
    blocked: Decimal = Decimal("0")  # Saldo bloqueado
    scheduled: Decimal = Decimal("0")  # Lançamentos futuros
    overdraft_limit: Decimal = Decimal("0")  # Limite de cheque especial
    currency: str = "BRL"
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "provider": self.provider.value,
            "available": str(self.available),
            "blocked": str(self.blocked),
            "scheduled": str(self.scheduled),
            "overdraft_limit": str(self.overdraft_limit),
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
        }

    @property
    def total(self) -> Decimal:
        return self.available + self.blocked


@dataclass
class Transaction:
    """Transação bancária"""
    id: str
    account_id: str
    provider: BankProvider
    type: TransactionType
    amount: Decimal
    description: str
    date: datetime
    counterpart_name: Optional[str] = None
    counterpart_document: Optional[str] = None  # Mascarado
    counterpart_bank: Optional[str] = None
    category: Optional[str] = None
    balance_after: Optional[Decimal] = None
    reference: Optional[str] = None  # End-to-end ID (PIX) ou NSU
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "provider": self.provider.value,
            "type": self.type.value,
            "amount": str(self.amount),
            "description": self.description,
            "date": self.date.isoformat(),
            "counterpart_name": self.counterpart_name,
            "counterpart_bank": self.counterpart_bank,
            "category": self.category,
            "balance_after": str(self.balance_after) if self.balance_after else None,
            "reference": self.reference,
        }

    @property
    def is_credit(self) -> bool:
        return self.type in (
            TransactionType.CREDIT, TransactionType.PIX_RECEIVED,
            TransactionType.TED_RECEIVED, TransactionType.REFUND,
            TransactionType.SALARY,
        )


@dataclass
class PixKey:
    """Chave PIX"""
    key: str
    key_type: PixKeyType
    account_id: str
    provider: BankProvider
    holder_name: str
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "key_type": self.key_type.value,
            "account_id": self.account_id,
            "provider": self.provider.value,
            "holder_name": self.holder_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class PixTransfer:
    """Transferência PIX"""
    id: str
    source_account_id: str
    destination_key: str
    destination_key_type: PixKeyType
    amount: Decimal
    description: Optional[str] = None
    end_to_end_id: Optional[str] = None
    status: str = "PENDING"  # PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_account_id": self.source_account_id,
            "destination_key": self.destination_key,
            "destination_key_type": self.destination_key_type.value,
            "amount": str(self.amount),
            "description": self.description,
            "end_to_end_id": self.end_to_end_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class CreditCard:
    """Cartão de crédito"""
    id: str
    provider: BankProvider
    last_four_digits: str
    brand: CardBrand
    holder_name: str
    credit_limit: Decimal
    available_limit: Decimal
    closing_day: int  # Dia de fechamento
    due_day: int  # Dia de vencimento
    is_virtual: bool = False
    status: str = "ACTIVE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider.value,
            "last_four_digits": self.last_four_digits,
            "brand": self.brand.value,
            "holder_name": self.holder_name,
            "credit_limit": str(self.credit_limit),
            "available_limit": str(self.available_limit),
            "closing_day": self.closing_day,
            "due_day": self.due_day,
            "is_virtual": self.is_virtual,
            "status": self.status,
        }

    @property
    def used_limit(self) -> Decimal:
        return self.credit_limit - self.available_limit


@dataclass
class Invoice:
    """Fatura do cartão de crédito"""
    id: str
    card_id: str
    provider: BankProvider
    reference_month: str  # "2026-02"
    total_amount: Decimal
    minimum_payment: Decimal
    due_date: date
    status: str = "OPEN"  # OPEN, CLOSED, OVERDUE, PAID
    transactions: List[Transaction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "card_id": self.card_id,
            "provider": self.provider.value,
            "reference_month": self.reference_month,
            "total_amount": str(self.total_amount),
            "minimum_payment": str(self.minimum_payment),
            "due_date": self.due_date.isoformat(),
            "status": self.status,
            "transaction_count": len(self.transactions),
        }


@dataclass
class BankStatement:
    """Extrato bancário consolidado"""
    account_id: str
    provider: BankProvider
    start_date: date
    end_date: date
    opening_balance: Decimal
    closing_balance: Decimal
    transactions: List[Transaction] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        total_credits = sum(
            t.amount for t in self.transactions if t.is_credit
        )
        total_debits = sum(
            t.amount for t in self.transactions if not t.is_credit
        )
        return {
            "account_id": self.account_id,
            "provider": self.provider.value,
            "period": f"{self.start_date.isoformat()} a {self.end_date.isoformat()}",
            "opening_balance": str(self.opening_balance),
            "closing_balance": str(self.closing_balance),
            "total_credits": str(total_credits),
            "total_debits": str(total_debits),
            "transaction_count": len(self.transactions),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class Consent:
    """Consentimento Open Finance Brasil"""
    id: str
    provider: BankProvider
    status: ConsentStatus
    permissions: List[str]
    expiration_datetime: datetime
    creation_datetime: datetime = field(default_factory=datetime.now)
    status_update_datetime: Optional[datetime] = None
    redirect_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider.value,
            "status": self.status.value,
            "permissions": self.permissions,
            "expiration": self.expiration_datetime.isoformat(),
            "created": self.creation_datetime.isoformat(),
        }

    @property
    def is_valid(self) -> bool:
        return (
            self.status == ConsentStatus.AUTHORISED
            and self.expiration_datetime > datetime.now()
        )


@dataclass
class ConsolidatedView:
    """Visão consolidada multi-banco"""
    accounts: List[BankAccount] = field(default_factory=list)
    balances: List[Balance] = field(default_factory=list)
    recent_transactions: List[Transaction] = field(default_factory=list)
    credit_cards: List[CreditCard] = field(default_factory=list)
    pix_keys: List[PixKey] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_available(self) -> Decimal:
        return sum((b.available for b in self.balances), Decimal("0"))

    @property
    def total_credit_limit(self) -> Decimal:
        return sum((c.available_limit for c in self.credit_cards), Decimal("0"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_available": str(self.total_available),
            "total_credit_limit": str(self.total_credit_limit),
            "accounts_count": len(self.accounts),
            "accounts": [a.to_dict() for a in self.accounts],
            "balances": [b.to_dict() for b in self.balances],
            "recent_transactions": [t.to_dict() for t in self.recent_transactions[:20]],
            "credit_cards": [c.to_dict() for c in self.credit_cards],
            "pix_keys": [p.to_dict() for p in self.pix_keys],
            "generated_at": self.generated_at.isoformat(),
        }

    def summary_text(self) -> str:
        """Gera resumo textual para Telegram / chat"""
        lines = [
            "💰 **Visão Consolidada Multi-Banco**",
            f"📅 Atualizado: {self.generated_at.strftime('%d/%m/%Y %H:%M')}",
            "",
        ]
        # Saldos por banco
        for b in self.balances:
            emoji = {"santander": "🔴", "itau": "🟠", "nubank": "🟣", "mercadopago": "🔵"}.get(
                b.provider.value, "🏦"
            )
            lines.append(f"{emoji} **{b.provider.value.title()}**: R$ {b.available:,.2f}")

        lines.append(f"\n💵 **Total Disponível**: R$ {self.total_available:,.2f}")

        if self.credit_cards:
            lines.append(f"💳 **Limite Crédito Disponível**: R$ {self.total_credit_limit:,.2f}")

        # Últimas transações
        if self.recent_transactions:
            lines.append("\n📊 **Últimas Transações:**")
            for t in self.recent_transactions[:5]:
                sign = "+" if t.is_credit else "-"
                lines.append(
                    f"  {sign}R$ {t.amount:,.2f} — {t.description[:40]}"
                )

        return "\n".join(lines)
