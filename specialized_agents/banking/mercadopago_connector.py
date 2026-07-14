"""
Conector Mercado Pago — API REST proprietária.

Suporta saldo (com fallback), movimentações via payments/search e
rendimento de cofrinhos (partition_transfer / POTS_*).
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

from .models import (
    Balance,
    BankProvider,
    CofrinhoCredit,
    CofrinhoSummary,
    CofrinhoYieldReport,
)

logger = logging.getLogger("eddie.banking.mercadopago")

MP_API_BASE = "https://api.mercadopago.com"
POTS_PREFIX = "POTS_"
DEFAULT_YIELD_MAX_AMOUNT = Decimal("10.00")


class BankAuthError(Exception):
    pass


class BankConnectionError(Exception):
    def __init__(self, provider: str, message: str, status_code: int | None = None):
        self.provider = provider
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class MercadoPagoConnector:
    """Conector Mercado Pago via access_token ou OAuth2."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        sandbox: bool = False,
        known_balance: Decimal | None = None,
        yield_max_amount: Decimal = DEFAULT_YIELD_MAX_AMOUNT,
    ):
        self.access_token = access_token or os.getenv("BANK_MERCADOPAGO_ACCESS_TOKEN", "")
        self.client_id = client_id or os.getenv("BANK_MERCADOPAGO_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("BANK_MERCADOPAGO_CLIENT_SECRET", "")
        self.sandbox = sandbox or os.getenv("BANK_MERCADOPAGO_ENV", "production") == "sandbox"
        self.known_balance = self._parse_known_balance(known_balance)
        self.yield_max_amount = yield_max_amount
        self._authenticated = False

    @staticmethod
    def _parse_known_balance(value: Decimal | None) -> Decimal | None:
        if value is not None:
            return value
        raw = os.getenv("BANK_MERCADOPAGO_KNOWN_BALANCE", "").strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except Exception:
            logger.warning("BANK_MERCADOPAGO_KNOWN_BALANCE inválido: %s", raw)
            return None

    async def authenticate(self) -> bool:
        if self.access_token:
            self._authenticated = True
            logger.info("Mercado Pago: token permanente configurado")
            return True
        if self.client_id and self.client_secret:
            status, body = await self._request(
                "POST",
                "/oauth/token",
                require_auth=False,
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            if status == 200 and isinstance(body, dict) and body.get("access_token"):
                self.access_token = body["access_token"]
                self._authenticated = True
                logger.info("Mercado Pago: OAuth2 client_credentials OK")
                return True
        raise BankAuthError(
            "Credenciais não encontradas. Configure BANK_MERCADOPAGO_ACCESS_TOKEN"
        )

    async def get_balance(self) -> Balance:
        await self.authenticate()
        status, body = await self._request("GET", "/users/me/mercadopago_account/balance")
        if status == 200 and isinstance(body, dict):
            available = Decimal(str(body.get("available_balance", 0)))
            blocked = Decimal(str(body.get("unavailable_balance", 0)))
            total = Decimal(str(body.get("total_amount", available + blocked)))
            return Balance(
                provider=BankProvider.MERCADOPAGO,
                account_id="main",
                available=available,
                blocked=blocked,
                total=total,
                source="balance_api",
            )

        logger.warning("Mercado Pago: Balance API indisponível (%s), usando fallback", status)
        available = await self._calculate_balance_from_payments()
        return Balance(
            provider=BankProvider.MERCADOPAGO,
            account_id="main",
            available=available,
            blocked=Decimal("0"),
            total=available,
            source="payments_fallback",
        )

    async def get_cofrinho_yield(
        self,
        *,
        months: int = 6,
        limit_per_page: int = 100,
        max_pages: int = 30,
    ) -> CofrinhoYieldReport:
        """
        Estima rendimento dos cofrinhos via partition_transfer (POTS_*).

        Créditos <= yield_max_amount são classificados como rendimento;
        valores maiores são tratados como aportes.
        """
        await self.authenticate()
        payments = await self._search_partition_transfers(
            limit_per_page=limit_per_page,
            max_pages=max_pages,
        )
        credits = self._parse_cofrinho_credits(payments)
        report = self._build_cofrinho_report(credits, months=months)
        report.notes.append(
            "Rendimento inferido de partition_transfer com referência POTS_*. "
            "A API pública não expõe endpoint dedicado de cofrinho."
        )
        if not credits:
            report.notes.append("Nenhum crédito POTS_ encontrado no período consultado.")
        return report

    async def _calculate_balance_from_payments(self) -> Decimal:
        if self.known_balance is None:
            logger.warning("Mercado Pago: sem BANK_MERCADOPAGO_KNOWN_BALANCE para fallback")
            return Decimal("0")

        offset = 0
        limit = 100
        delta = Decimal("0")
        pages = 0
        while pages < 20:
            status, body = await self._request(
                "GET",
                "/v1/payments/search",
                params={
                    "limit": limit,
                    "offset": offset,
                    "sort": "date_created",
                    "criteria": "desc",
                },
            )
            if status != 200 or not isinstance(body, dict):
                break
            results = body.get("results", [])
            if not results:
                break
            for payment in results:
                delta += self._payment_balance_delta(payment)
            total = int(body.get("paging", {}).get("total", 0))
            offset += limit
            pages += 1
            if offset >= total:
                break
        return self.known_balance + delta

    def _payment_balance_delta(self, payment: dict[str, Any]) -> Decimal:
        amount = Decimal(str(payment.get("transaction_amount", 0)))
        op = payment.get("operation_type", "")
        status = payment.get("status", "")
        if status != "approved":
            return Decimal("0")
        payer_id = str((payment.get("payer") or {}).get("id", ""))
        collector_id = str(payment.get("collector_id", ""))
        if op in {"money_transfer", "account_fund"}:
            return amount
        if op == "partition_transfer":
            ext = payment.get("external_reference") or ""
            if ext.startswith(POTS_PREFIX):
                return amount
        if op == "regular_payment" and payer_id and payer_id == collector_id:
            return -amount
        if op in {"money_exchange"}:
            desc = (payment.get("description") or "").upper()
            if desc.startswith("EARN_"):
                return amount
        return Decimal("0")

    async def _search_partition_transfers(
        self,
        *,
        limit_per_page: int,
        max_pages: int,
    ) -> list[dict[str, Any]]:
        return await self._search_payments(
            params={"operation_type": "partition_transfer"},
            limit_per_page=limit_per_page,
            max_pages=max_pages,
        )

    async def _search_payments(
        self,
        *,
        params: dict[str, Any],
        limit_per_page: int,
        max_pages: int,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        pages = 0
        while pages < max_pages:
            query = {
                **params,
                "limit": limit_per_page,
                "offset": offset,
                "sort": "date_created",
                "criteria": "desc",
            }
            status, body = await self._request("GET", "/v1/payments/search", params=query)
            if status != 200 or not isinstance(body, dict):
                raise BankConnectionError(
                    BankProvider.MERCADOPAGO.value,
                    f"Falha ao consultar payments/search: HTTP {status}",
                    status,
                )
            batch = body.get("results", [])
            items.extend(batch)
            total = int(body.get("paging", {}).get("total", 0))
            offset += limit_per_page
            pages += 1
            if offset >= total or not batch:
                break
        return items

    def _parse_cofrinho_credits(self, payments: list[dict[str, Any]]) -> list[CofrinhoCredit]:
        credits: list[CofrinhoCredit] = []
        for payment in payments:
            ext = payment.get("external_reference") or ""
            if not ext.startswith(POTS_PREFIX):
                continue
            parts = ext.split("_", 2)
            pots_id = parts[1] if len(parts) > 1 else "unknown"
            amount = Decimal(str(payment.get("transaction_amount", 0)))
            created = self._parse_mp_datetime(payment.get("date_created"))
            kind = "yield" if amount <= self.yield_max_amount else "deposit"
            credits.append(
                CofrinhoCredit(
                    payment_id=int(payment.get("id", 0)),
                    date=created,
                    amount=amount,
                    pots_id=pots_id,
                    external_reference=ext,
                    kind=kind,
                )
            )
        credits.sort(key=lambda item: item.date, reverse=True)
        return credits

    def _build_cofrinho_report(
        self,
        credits: list[CofrinhoCredit],
        *,
        months: int,
    ) -> CofrinhoYieldReport:
        today = date.today()
        current_month = today.strftime("%Y-%m")
        cutoff = today - timedelta(days=30)
        monthly_map: dict[tuple[str, str], CofrinhoSummary] = {}

        current_month_yield = Decimal("0")
        current_month_deposits = Decimal("0")
        last_30_days_yield = Decimal("0")
        pots_ids = sorted({credit.pots_id for credit in credits})

        for credit in credits:
            month = credit.date.strftime("%Y-%m")
            key = (credit.pots_id, month)
            if key not in monthly_map:
                monthly_map[key] = CofrinhoSummary(
                    pots_id=credit.pots_id,
                    month=month,
                    yield_total=Decimal("0"),
                    deposit_total=Decimal("0"),
                    credit_count=0,
                )
            summary = monthly_map[key]
            summary.credit_count += 1
            if credit.kind == "yield":
                summary.yield_total += credit.amount
                if month == current_month:
                    current_month_yield += credit.amount
                if credit.date.date() >= cutoff:
                    last_30_days_yield += credit.amount
            else:
                summary.deposit_total += credit.amount
                if month == current_month:
                    current_month_deposits += credit.amount

        month_keys = sorted({month for _, month in monthly_map}, reverse=True)[:months]
        monthly = [
            monthly_map[(pots_id, month)]
            for month in month_keys
            for pots_id in pots_ids
            if (pots_id, month) in monthly_map
        ]

        return CofrinhoYieldReport(
            pots_ids=pots_ids,
            current_month=current_month,
            current_month_yield=current_month_yield,
            current_month_deposits=current_month_deposits,
            last_30_days_yield=last_30_days_yield,
            monthly=monthly,
            latest_credit=credits[0] if credits else None,
            credits=credits[:50],
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        require_auth: bool = True,
        timeout: float = 30.0,
    ) -> tuple[int, dict[str, Any] | str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if require_auth:
            if not self.access_token:
                raise BankAuthError("Access token ausente")
            headers["Authorization"] = f"Bearer {self.access_token}"
        url = f"{MP_API_BASE}{path}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, headers=headers, params=params, json=json)
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, response.text[:500]

    @staticmethod
    def _parse_mp_datetime(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)