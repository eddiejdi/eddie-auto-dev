"""Modelos de dados do Banking Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class BankProvider(str, Enum):
    SANTANDER = "santander"
    ITAU = "itau"
    NUBANK = "nubank"
    MERCADOPAGO = "mercadopago"


@dataclass
class Balance:
    provider: BankProvider
    account_id: str
    available: Decimal
    blocked: Decimal = Decimal("0")
    total: Decimal | None = None
    currency: str = "BRL"
    as_of: datetime = field(default_factory=datetime.utcnow)
    source: str = "api"

    def __post_init__(self) -> None:
        if self.total is None:
            self.total = self.available + self.blocked


@dataclass
class CofrinhoCredit:
    payment_id: int
    date: datetime
    amount: Decimal
    pots_id: str
    external_reference: str
    kind: str  # yield | deposit


@dataclass
class CofrinhoSummary:
    pots_id: str
    month: str
    yield_total: Decimal
    deposit_total: Decimal
    credit_count: int


@dataclass
class CofrinhoYieldReport:
    provider: BankProvider = BankProvider.MERCADOPAGO
    pots_ids: list[str] = field(default_factory=list)
    current_month: str = ""
    current_month_yield: Decimal = Decimal("0")
    current_month_deposits: Decimal = Decimal("0")
    last_30_days_yield: Decimal = Decimal("0")
    monthly: list[CofrinhoSummary] = field(default_factory=list)
    latest_credit: CofrinhoCredit | None = None
    credits: list[CofrinhoCredit] = field(default_factory=list)
    source: str = "payments_search"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider.value,
            "pots_ids": self.pots_ids,
            "current_month": self.current_month,
            "current_month_yield": float(self.current_month_yield),
            "current_month_deposits": float(self.current_month_deposits),
            "last_30_days_yield": float(self.last_30_days_yield),
            "monthly": [
                {
                    "pots_id": item.pots_id,
                    "month": item.month,
                    "yield_total": float(item.yield_total),
                    "deposit_total": float(item.deposit_total),
                    "credit_count": item.credit_count,
                }
                for item in self.monthly
            ],
            "latest_credit": (
                {
                    "payment_id": self.latest_credit.payment_id,
                    "date": self.latest_credit.date.isoformat(),
                    "amount": float(self.latest_credit.amount),
                    "pots_id": self.latest_credit.pots_id,
                    "external_reference": self.latest_credit.external_reference,
                    "kind": self.latest_credit.kind,
                }
                if self.latest_credit
                else None
            ),
            "source": self.source,
            "notes": self.notes,
        }