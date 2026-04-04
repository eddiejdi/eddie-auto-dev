#!/usr/bin/env python3
"""
MT5 Bridge API — FastAPI REST bridge para MetaTrader 5.

Roda em uma VM Windows com o terminal MT5 conectado à Clear Corretora.
Expõe endpoints REST que traduzem chamadas HTTP em operações MT5.
O agente de trading no Linux consome estes endpoints.

Porta padrão: 8510
Auth: API key via header X-API-KEY
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from enum import IntEnum
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ====================== MT5 IMPORT (WINDOWS ONLY) ======================
try:
    import MetaTrader5 as mt5  # type: ignore[import-untyped]
except ImportError:
    mt5 = None  # type: ignore[assignment]
    logger.warning("⚠️ MetaTrader5 package não disponível (necessário Windows + MT5)")


# ====================== CONFIGURAÇÃO ======================
API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "")
MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "ClearCorretora-Server")
MT5_PATH = os.getenv("MT5_PATH", "")  # Caminho do terminal64.exe (opcional)
BRIDGE_PORT = int(os.getenv("MT5_BRIDGE_PORT", "8510"))


# ====================== PYDANTIC MODELS ======================
class OrderRequest(BaseModel):
    """Requisição de ordem de compra/venda."""

    symbol: str = Field(..., description="Código do ativo B3 (ex: PETR4, WINFUT)")
    side: str = Field(..., pattern="^(buy|sell)$", description="buy ou sell")
    volume: float = Field(..., gt=0, description="Volume (lotes ou contratos)")
    order_type: str = Field(
        "market", pattern="^(market|limit)$", description="Tipo de ordem"
    )
    price: Optional[float] = Field(None, description="Preço limite (obrigatório se limit)")
    deviation: int = Field(20, description="Desvio máximo em pontos (slippage)")
    magic: int = Field(234000, description="Magic number para identificar ordens do bot")
    comment: str = Field("clear_agent", description="Comentário da ordem")


class OrderResponse(BaseModel):
    """Resposta de uma ordem executada."""

    success: bool
    order_id: Optional[int] = None
    retcode: Optional[int] = None
    retcode_str: Optional[str] = None
    price: Optional[float] = None
    volume: Optional[float] = None
    comment: Optional[str] = None
    error: Optional[str] = None


class PositionInfo(BaseModel):
    """Informações de uma posição aberta."""

    ticket: int
    symbol: str
    type: str  # "buy" ou "sell"
    volume: float
    price_open: float
    price_current: float
    profit: float
    swap: float
    time: int
    magic: int
    comment: str


class AccountInfo(BaseModel):
    """Informações da conta."""

    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: Optional[float] = None
    profit: float
    currency: str
    server: str
    name: str


class TickInfo(BaseModel):
    """Tick atual de um ativo."""

    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    time: int
    spread: float


class CandleInfo(BaseModel):
    """Candle OHLCV."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


class HealthResponse(BaseModel):
    """Status de saúde do bridge."""

    status: str
    mt5_connected: bool
    terminal_info: Optional[dict[str, Any]] = None
    account_login: Optional[int] = None
    server_time: Optional[str] = None
    uptime_seconds: float


class DealInfo(BaseModel):
    """Informações de um deal (trade executado) no histórico."""

    ticket: int
    order: int
    symbol: str
    type: int
    volume: float
    price: float
    profit: float
    commission: float
    swap: float
    fee: float
    time: int
    comment: str


class OrderInfo(BaseModel):
    """Informações de uma ordem ativa/pendente."""

    ticket: int
    symbol: str
    type: int
    volume_initial: float
    volume_current: float
    price_open: float
    price_current: float
    time_setup: int
    time_done: int
    state: int
    comment: str


# ====================== MT5 RETCODE MAPPING ======================
_MT5_RETCODES: dict[int, str] = {
    10004: "TRADE_RETCODE_REQUOTE",
    10006: "TRADE_RETCODE_REJECT",
    10007: "TRADE_RETCODE_CANCEL",
    10008: "TRADE_RETCODE_PLACED",
    10009: "TRADE_RETCODE_DONE",
    10010: "TRADE_RETCODE_DONE_PARTIAL",
    10011: "TRADE_RETCODE_ERROR",
    10012: "TRADE_RETCODE_TIMEOUT",
    10013: "TRADE_RETCODE_INVALID",
    10014: "TRADE_RETCODE_INVALID_VOLUME",
    10015: "TRADE_RETCODE_INVALID_PRICE",
    10016: "TRADE_RETCODE_INVALID_STOPS",
    10017: "TRADE_RETCODE_TRADE_DISABLED",
    10018: "TRADE_RETCODE_MARKET_CLOSED",
    10019: "TRADE_RETCODE_NO_MONEY",
    10020: "TRADE_RETCODE_PRICE_CHANGED",
    10021: "TRADE_RETCODE_PRICE_OFF",
    10022: "TRADE_RETCODE_INVALID_EXPIRATION",
    10023: "TRADE_RETCODE_ORDER_CHANGED",
    10024: "TRADE_RETCODE_TOO_MANY_REQUESTS",
    10025: "TRADE_RETCODE_NO_CHANGES",
    10026: "TRADE_RETCODE_SERVER_DISABLES_AT",
    10027: "TRADE_RETCODE_CLIENT_DISABLES_AT",
    10028: "TRADE_RETCODE_LOCKED",
    10029: "TRADE_RETCODE_FROZEN",
    10030: "TRADE_RETCODE_INVALID_FILL",
    10031: "TRADE_RETCODE_CONNECTION",
    10032: "TRADE_RETCODE_ONLY_REAL",
    10033: "TRADE_RETCODE_LIMIT_ORDERS",
    10034: "TRADE_RETCODE_LIMIT_VOLUME",
    10035: "TRADE_RETCODE_INVALID_ORDER",
    10036: "TRADE_RETCODE_POSITION_CLOSED",
}

# ====================== STARTUP / SHUTDOWN ======================
_start_time = time.time()


def _init_mt5() -> bool:
    """Inicializa conexão com o terminal MetaTrader 5."""
    if mt5 is None:
        logger.error("❌ MetaTrader5 package não disponível")
        return False

    kwargs: dict[str, Any] = {}
    if MT5_PATH:
        kwargs["path"] = MT5_PATH
    if MT5_LOGIN:
        kwargs["login"] = MT5_LOGIN
    if MT5_PASSWORD:
        kwargs["password"] = MT5_PASSWORD
    if MT5_SERVER:
        kwargs["server"] = MT5_SERVER

    if not mt5.initialize(**kwargs):
        error = mt5.last_error()
        logger.error("❌ MT5 initialize falhou: %s", error)
        return False

    info = mt5.terminal_info()
    if info:
        logger.info(
            "✅ MT5 conectado: %s (build %s)",
            info.name if hasattr(info, "name") else "MT5",
            info.build if hasattr(info, "build") else "?",
        )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida: connect MT5 no startup, shutdown no final."""
    logger.info("🚀 MT5 Bridge iniciando na porta %s", BRIDGE_PORT)
    if not _init_mt5():
        logger.warning("⚠️ MT5 não conectado — bridge iniciará em modo degradado")
    yield
    if mt5 is not None:
        mt5.shutdown()
        logger.info("🛑 MT5 desconectado")


# ====================== APP ======================
app = FastAPI(
    title="MT5 Bridge API — Clear Corretora",
    description="REST bridge para MetaTrader 5 conectado à Clear Corretora (B3)",
    version="1.0.0",
    lifespan=lifespan,
)


# ====================== AUTH ======================

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura exceções não tratadas sem expor detalhes internos ou secrets."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Valida API key do header."""
    if not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MT5_BRIDGE_API_KEY não configurada no servidor",
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida",
        )
    return x_api_key


def _check_mt5() -> None:
    """Verifica se MT5 está disponível e conectado."""
    if mt5 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MetaTrader5 package não disponível (necessário Windows)",
        )
    info = mt5.terminal_info()
    if info is None or not info.connected:
        if not _init_mt5():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MT5 terminal não conectado",
            )


# ====================== ENDPOINTS ======================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Status de saúde do bridge e do terminal MT5."""
    connected = False
    terminal_info = None
    account_login = None
    server_time = None

    if mt5 is not None:
        info = mt5.terminal_info()
        if info is not None:
            connected = bool(info.connected)
            terminal_info = {
                "name": info.name if hasattr(info, "name") else "",
                "build": info.build if hasattr(info, "build") else 0,
                "connected": connected,
                "trade_allowed": info.trade_allowed if hasattr(info, "trade_allowed") else False,
            }
        acc = mt5.account_info()
        if acc is not None:
            account_login = acc.login
            server_time = datetime.now().isoformat()

    return HealthResponse(
        status="ok" if connected else "degraded",
        mt5_connected=connected,
        terminal_info=terminal_info,
        account_login=account_login,
        server_time=server_time,
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@app.post("/order", response_model=OrderResponse, dependencies=[Depends(verify_api_key)])
async def place_order(req: OrderRequest):
    """Envia ordem de compra ou venda ao MT5."""
    _check_mt5()

    # Verificar se o símbolo existe e está visível
    symbol_info = mt5.symbol_info(req.symbol)
    if symbol_info is None:
        return OrderResponse(success=False, error=f"Símbolo {req.symbol!r} não encontrado")
    if not symbol_info.visible:
        mt5.symbol_select(req.symbol, True)

    # Montar request MT5
    order_type = mt5.ORDER_TYPE_BUY if req.side == "buy" else mt5.ORDER_TYPE_SELL
    filling = mt5.ORDER_FILLING_IOC  # Immediate-or-Cancel (padrão B3)

    tick = mt5.symbol_info_tick(req.symbol)
    if tick is None:
        return OrderResponse(success=False, error=f"Sem cotação para {req.symbol!r}")

    price = tick.ask if req.side == "buy" else tick.bid

    if req.order_type == "limit" and req.price is not None:
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if req.side == "buy" else mt5.ORDER_TYPE_SELL_LIMIT
        price = req.price

    request = {
        "action": mt5.TRADE_ACTION_DEAL if req.order_type == "market" else mt5.TRADE_ACTION_PENDING,
        "symbol": req.symbol,
        "volume": req.volume,
        "type": order_type,
        "price": price,
        "deviation": req.deviation,
        "magic": req.magic,
        "comment": req.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    logger.info("📤 Enviando ordem: %s %s %.2f x %.4f", req.side.upper(), req.symbol, req.volume, price)

    result = mt5.order_send(request)
    if result is None:
        error = mt5.last_error()
        return OrderResponse(success=False, error=f"order_send retornou None: {error}")

    retcode_str = _MT5_RETCODES.get(result.retcode, f"UNKNOWN_{result.retcode}")
    success = result.retcode in (10008, 10009, 10010)  # PLACED, DONE, DONE_PARTIAL

    if success:
        logger.info("✅ Ordem executada: ticket=%s price=%.4f vol=%.2f", result.order, result.price, result.volume)
    else:
        logger.warning("❌ Ordem rejeitada: %s (%s)", retcode_str, result.comment)

    return OrderResponse(
        success=success,
        order_id=result.order if result.order else None,
        retcode=result.retcode,
        retcode_str=retcode_str,
        price=result.price if hasattr(result, "price") else None,
        volume=result.volume if hasattr(result, "volume") else None,
        comment=result.comment if hasattr(result, "comment") else None,
        error=None if success else f"{retcode_str}: {result.comment}",
    )


@app.get("/positions", response_model=list[PositionInfo], dependencies=[Depends(verify_api_key)])
async def get_positions(symbol: Optional[str] = None):
    """Retorna posições abertas (opcionalmente filtradas por símbolo)."""
    _check_mt5()
    if symbol:
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()

    if positions is None:
        return []

    return [
        PositionInfo(
            ticket=p.ticket,
            symbol=p.symbol,
            type="buy" if p.type == 0 else "sell",
            volume=p.volume,
            price_open=p.price_open,
            price_current=p.price_current,
            profit=p.profit,
            swap=p.swap,
            time=p.time,
            magic=p.magic,
            comment=p.comment or "",
        )
        for p in positions
    ]


@app.get("/account", response_model=AccountInfo, dependencies=[Depends(verify_api_key)])
async def get_account():
    """Retorna informações da conta Clear."""
    _check_mt5()
    acc = mt5.account_info()
    if acc is None:
        raise HTTPException(status_code=503, detail="Falha ao obter info da conta")

    return AccountInfo(
        login=acc.login,
        balance=acc.balance,
        equity=acc.equity,
        margin=acc.margin,
        margin_free=acc.margin_free,
        margin_level=acc.margin_level if acc.margin_level else None,
        profit=acc.profit,
        currency=acc.currency,
        server=acc.server,
        name=acc.name,
    )


@app.get("/symbol/{symbol}/tick", response_model=TickInfo, dependencies=[Depends(verify_api_key)])
async def get_tick(symbol: str):
    """Retorna o último tick (cotação) de um ativo."""
    _check_mt5()

    # Garantir que o símbolo está visível
    info = mt5.symbol_info(symbol)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Símbolo {symbol!r} não encontrado")
    if not info.visible:
        mt5.symbol_select(symbol, True)

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise HTTPException(status_code=404, detail=f"Sem tick para {symbol!r}")

    return TickInfo(
        symbol=symbol,
        bid=tick.bid,
        ask=tick.ask,
        last=tick.last,
        volume=float(tick.volume),
        time=tick.time,
        spread=float(info.spread) if hasattr(info, "spread") else (tick.ask - tick.bid),
    )


@app.get(
    "/symbol/{symbol}/rates",
    response_model=list[CandleInfo],
    dependencies=[Depends(verify_api_key)],
)
async def get_rates(
    symbol: str,
    timeframe: str = "M1",
    count: int = 100,
):
    """Retorna candles OHLCV históricos.

    Timeframes: M1, M5, M15, M30, H1, H4, D1, W1, MN1.
    """
    _check_mt5()

    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }
    tf = tf_map.get(timeframe.upper())
    if tf is None:
        raise HTTPException(
            status_code=400,
            detail=f"Timeframe inválido: {timeframe!r}. Use: {list(tf_map.keys())}",
        )

    count = min(count, 1000)  # Limitar a 1000 candles por request

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return []

    return [
        CandleInfo(
            timestamp=int(r[0]),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            tick_volume=int(r[5]),
            spread=int(r[6]),
            real_volume=int(r[7]),
        )
        for r in rates
    ]


@app.get("/orders", response_model=list[OrderInfo], dependencies=[Depends(verify_api_key)])
async def get_orders(symbol: Optional[str] = None):
    """Retorna ordens ativas/pendentes."""
    _check_mt5()
    if symbol:
        orders = mt5.orders_get(symbol=symbol)
    else:
        orders = mt5.orders_get()

    if orders is None:
        return []

    return [
        OrderInfo(
            ticket=o.ticket,
            symbol=o.symbol,
            type=o.type,
            volume_initial=o.volume_initial,
            volume_current=o.volume_current,
            price_open=o.price_open,
            price_current=o.price_current,
            time_setup=o.time_setup,
            time_done=o.time_done,
            state=o.state,
            comment=o.comment or "",
        )
        for o in orders
    ]


@app.get(
    "/history/deals",
    response_model=list[DealInfo],
    dependencies=[Depends(verify_api_key)],
)
async def get_history_deals(
    days: int = 7,
    symbol: Optional[str] = None,
):
    """Retorna histórico de deals (trades executados).

    Args:
        days: Quantos dias de histórico (máximo 90).
        symbol: Filtrar por símbolo (opcional).
    """
    _check_mt5()

    days = min(days, 90)
    from_date = datetime.now() - __import__("datetime").timedelta(days=days)
    to_date = datetime.now()

    if symbol:
        deals = mt5.history_deals_get(from_date, to_date, group=f"*{symbol}*")
    else:
        deals = mt5.history_deals_get(from_date, to_date)

    if deals is None:
        return []

    return [
        DealInfo(
            ticket=d.ticket,
            order=d.order,
            symbol=d.symbol,
            type=d.type,
            volume=d.volume,
            price=d.price,
            profit=d.profit,
            commission=d.commission,
            swap=d.swap,
            fee=d.fee if hasattr(d, "fee") else 0.0,
            time=d.time,
            comment=d.comment or "",
        )
        for d in deals
    ]


# ====================== ENTRY POINT ======================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=BRIDGE_PORT, log_level="info")
