"""Rotas FastAPI do Banking Agent."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .mercadopago_connector import BankAuthError, BankConnectionError, MercadoPagoConnector

logger = logging.getLogger(__name__)

router = APIRouter(tags=["banking"])


def _connector() -> MercadoPagoConnector:
    return MercadoPagoConnector()


@router.get("/status")
async def banking_status() -> dict[str, Any]:
    """Status do conector Mercado Pago."""
    connector = _connector()
    try:
        await connector.authenticate()
        return {
            "initialized": True,
            "providers_connected": ["mercadopago"],
            "providers_disconnected": [],
            "connectors_active": 1,
            "mercadopago": {
                "authenticated": connector._authenticated,
                "sandbox": connector.sandbox,
                "has_known_balance": connector.known_balance is not None,
            },
        }
    except BankAuthError as exc:
        return {
            "initialized": False,
            "providers_connected": [],
            "providers_disconnected": ["mercadopago"],
            "connectors_active": 0,
            "error": str(exc),
        }


@router.get("/balance")
async def banking_balance() -> dict[str, Any]:
    """Saldo Mercado Pago (API ou fallback via pagamentos)."""
    connector = _connector()
    try:
        balance = await connector.get_balance()
        return {
            "total_available": float(balance.available),
            "balances": [
                {
                    "provider": balance.provider.value,
                    "account_id": balance.account_id,
                    "available": float(balance.available),
                    "blocked": float(balance.blocked),
                    "total": float(balance.total or balance.available),
                    "source": balance.source,
                }
            ],
        }
    except BankAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except BankConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/cofrinho")
async def banking_cofrinho_yield(
    months: int = Query(default=6, ge=1, le=24, description="Meses no histórico mensal"),
) -> dict[str, Any]:
    """Rendimento estimado dos cofrinhos Mercado Pago (partition_transfer / POTS_*)."""
    connector = _connector()
    try:
        report = await connector.get_cofrinho_yield(months=months)
        return report.to_dict()
    except BankAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except BankConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Erro ao consultar rendimento do cofrinho")
        raise HTTPException(status_code=500, detail=str(exc)) from exc