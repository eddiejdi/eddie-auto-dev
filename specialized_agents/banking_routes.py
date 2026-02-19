"""
Banking Agent — Rotas FastAPI.

Expõe endpoints REST para o Banking Agent na porta 8503:
  GET  /banking/status       — Status dos conectores
  GET  /banking/balance      — Saldo consolidado
  GET  /banking/statement    — Extrato unificado
  GET  /banking/cards        — Cartões de crédito
  GET  /banking/alerts       — Alertas de gastos
  GET  /banking/report       — Relatório mensal
  POST /banking/initialize   — Inicializar conectores
  POST /banking/pix          — Enviar PIX
  POST /banking/threshold    — Definir limite de gasto
  GET  /banking/metrics      — Métricas Prometheus do banking
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("eddie.banking.routes")

router = APIRouter(prefix="/banking", tags=["banking"])

# ──────────── Helpers ────────────

def _get_agent():
    """Obtém instância singleton do BankingAgent."""
    from specialized_agents.banking_agent import get_banking_agent
    return get_banking_agent()


def _agent_status(agent) -> dict:
    """Retorna status resumido do agent."""
    providers_connected = []
    providers_disconnected = []
    
    for p in agent.SUPPORTED_PROVIDERS:
        if p in agent._connectors:
            providers_connected.append(p.value)
        else:
            providers_disconnected.append(p.value)
    
    return {
        "initialized": agent._initialized,
        "belvo_enabled": agent._belvo_enabled,
        "connectors_active": len(agent._connectors),
        "providers_connected": providers_connected,
        "providers_disconnected": providers_disconnected,
    }


# ──────────── Pydantic Models ────────────

class InitializeRequest(BaseModel):
    providers: Optional[List[str]] = None


class PixRequest(BaseModel):
    provider: str
    key: str
    amount: float
    description: Optional[str] = None


class ThresholdRequest(BaseModel):
    category: str
    amount: float


# ──────────── Endpoints ────────────

@router.get("/status")
async def banking_status():
    """Status das conexões bancárias e do Banking Agent."""
    try:
        agent = _get_agent()
        status = _agent_status(agent)
        
        # Belvo info
        belvo_info = None
        if agent._belvo_enabled and agent._belvo:
            try:
                connected = await agent._belvo.get_connected_banks()
                belvo_info = {
                    "environment": agent._belvo.environment,
                    "connected_banks": {
                        p.value: {"status": info["status"]}
                        for p, info in connected.items()
                    }
                }
            except Exception as e:
                belvo_info = {"error": str(e)}
        
        return {
            "service": "eddie-banking-agent",
            "version": "1.0.0",
            **status,
            "belvo": belvo_info,
            "supported_providers": [p.value for p in agent.SUPPORTED_PROVIDERS],
        }
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/initialize")
async def banking_initialize(req: InitializeRequest):
    """Inicializa conectores bancários.
    
    Se providers não fornecido, tenta todos os suportados.
    Requer credenciais configuradas (Belvo e/ou Mercado Pago).
    """
    try:
        agent = _get_agent()
        
        providers = None
        if req.providers:
            from specialized_agents.banking.models import BankProvider
            providers = []
            for p in req.providers:
                try:
                    providers.append(BankProvider(p.lower()))
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Provider inválido: {p}. Válidos: santander, itau, nubank, mercadopago"
                    )
        
        results = await agent.initialize(providers)
        
        return {
            "message": "Banking Agent inicializado",
            "results": results,
            **_agent_status(agent),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Initialize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/balance")
async def banking_balance():
    """Saldo consolidado de todos os bancos conectados."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            return {
                "message": "Banking Agent não inicializado. Use POST /banking/initialize primeiro.",
                "initialized": False,
                "total_available": 0,
                "balances": [],
            }
        
        view = await agent.get_consolidated_view()
        
        return {
            "total_available": float(view.total_available),
            "balances": [
                {
                    "provider": b.provider.value,
                    "account_id": b.account_id,
                    "available": float(b.available),
                    "blocked": float(b.blocked),
                    "currency": b.currency,
                }
                for b in view.balances
            ],
            "credit_cards_count": len(view.credit_cards),
            "accounts_count": len(view.accounts),
            "updated_at": view.updated_at.isoformat() if hasattr(view, 'updated_at') else None,
        }
    except Exception as e:
        logger.error(f"Balance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statement")
async def banking_statement(
    days: int = Query(default=7, ge=1, le=365, description="Dias de extrato"),
    provider: Optional[str] = Query(default=None, description="Filtrar por banco"),
):
    """Extrato unificado dos últimos N dias."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            raise HTTPException(
                status_code=400,
                detail="Banking Agent não inicializado. Use POST /banking/initialize."
            )
        
        end = date.today()
        start = end - timedelta(days=days)
        
        providers = None
        if provider:
            from specialized_agents.banking.models import BankProvider
            try:
                providers = [BankProvider(provider.lower())]
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Provider inválido: {provider}")
        
        stmt = await agent.get_unified_statement(start, end, providers)
        
        return {
            "period": {"start": start.isoformat(), "end": end.isoformat(), "days": days},
            "total_credits": float(stmt["total_credits"]),
            "total_debits": float(stmt["total_debits"]),
            "net_result": float(stmt["net_result"]),
            "transaction_count": stmt["transaction_count"],
            "by_category": {
                cat: {
                    "total_debit": float(data["total_debit"]),
                    "total_credit": float(data["total_credit"]),
                    "count": data["count"],
                }
                for cat, data in stmt.get("by_category", {}).items()
            },
            "transactions": [
                {
                    "date": str(tx.get("date", "") if isinstance(tx, dict) else tx.date),
                    "description": tx.get("description", "") if isinstance(tx, dict) else tx.description,
                    "amount": float(tx.get("amount", 0) if isinstance(tx, dict) else tx.amount),
                    "type": tx.get("type", "other") if isinstance(tx, dict) else (tx.type.value if hasattr(tx.type, 'value') else str(tx.type)),
                    "provider": tx.get("provider", None) if isinstance(tx, dict) else (tx.provider.value if hasattr(tx, 'provider') else None),
                }
                for tx in stmt.get("transactions", [])[:100]  # Limitar a 100
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Statement error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cards")
async def banking_cards():
    """Lista cartões de crédito de todos os bancos."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            return {"message": "Banking Agent não inicializado.", "cards": []}
        
        view = await agent.get_consolidated_view()
        
        return {
            "count": len(view.credit_cards),
            "cards": [
                {
                    "provider": c.provider.value,
                    "last_four": c.last_four_digits,
                    "brand": c.brand.value if hasattr(c.brand, 'value') else str(c.brand),
                    "credit_limit": float(c.credit_limit),
                    "available_limit": float(c.available_limit),
                }
                for c in view.credit_cards
            ],
        }
    except Exception as e:
        logger.error(f"Cards error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def banking_alerts():
    """Alertas de gastos ativos."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            return {"message": "Banking Agent não inicializado.", "alerts": []}
        
        alerts = await agent.check_spending_alerts()
        
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "provider": a.provider.value,
                    "category": a.category,
                    "current_amount": float(a.current_amount),
                    "threshold": float(a.threshold),
                    "severity": a.severity,
                    "message": a.message,
                }
                for a in alerts
            ],
        }
    except Exception as e:
        logger.error(f"Alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def banking_report(
    month: Optional[str] = Query(default=None, description="Mês no formato YYYY-MM"),
):
    """Relatório mensal financeiro."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            raise HTTPException(
                status_code=400,
                detail="Banking Agent não inicializado. Use POST /banking/initialize."
            )
        
        report = await agent.generate_monthly_report(month)
        
        # Converter Decimals para float
        def _to_serializable(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, dict):
                return {k: _to_serializable(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_to_serializable(i) for i in obj]
            return obj
        
        return _to_serializable(report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threshold")
async def banking_set_threshold(req: ThresholdRequest):
    """Define limite de gasto por categoria."""
    try:
        agent = _get_agent()
        agent.set_spending_threshold(req.category, Decimal(str(req.amount)))
        
        return {
            "message": f"Limite de R$ {req.amount:.2f} definido para '{req.category}'",
            "category": req.category,
            "threshold": req.amount,
        }
    except Exception as e:
        logger.error(f"Threshold error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pix")
async def banking_send_pix(req: PixRequest):
    """Envia PIX (requer autenticação ativa no banco)."""
    try:
        agent = _get_agent()
        
        if not agent._initialized:
            raise HTTPException(
                status_code=400,
                detail="Banking Agent não inicializado."
            )
        
        from specialized_agents.banking.models import BankProvider
        try:
            provider = BankProvider(req.provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Provider inválido: {req.provider}")
        
        result = await agent.send_pix(
            provider=provider,
            key=req.key,
            amount=Decimal(str(req.amount)),
            description=req.description,
        )
        
        return {
            "message": "PIX enviado com sucesso",
            "transfer": {
                "id": result.id if hasattr(result, 'id') else None,
                "status": result.status if hasattr(result, 'status') else "completed",
                "amount": req.amount,
                "key": req.key,
                "provider": req.provider,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PIX error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def banking_metrics_endpoint():
    """Métricas Prometheus do Banking Agent (texto)."""
    try:
        from specialized_agents.banking_metrics_exporter import get_banking_metrics
        exporter = get_banking_metrics()
        from fastapi.responses import Response
        return Response(
            content=exporter.get_metrics(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
