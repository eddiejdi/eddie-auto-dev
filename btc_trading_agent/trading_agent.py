#!/usr/bin/env python3
"""
Bitcoin Trading Agent 24/7
Agente autônomo de trading que opera continuamente
"""

import os
import sys
import time
import json
import re
import signal
import logging
import argparse
import threading
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

import httpx

# Adicionar diretório ao path
sys.path.insert(0, str(Path(__file__).parent))

from kucoin_api import (
    get_price, get_price_fast, get_orderbook, get_candles,
    get_recent_trades, get_balances, get_balance,
    place_market_order, analyze_orderbook, analyze_trade_flow,
    inner_transfer, _has_keys
)
from fast_model import FastTradingModel, MarketState, Signal
from training_db import TrainingDatabase, TrainingManager
from market_rag import MarketRAG

# ====================== CONFIGURAÇÃO ======================
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====================== CONSTANTES ======================
# Default symbol — can be overridden by config file or CLI
_config_file = os.environ.get("COIN_CONFIG_FILE", "config.json")
_config_path = Path(__file__).parent / _config_file
try:
    with open(_config_path) as _cf:
        _config = json.load(_cf)
    DEFAULT_SYMBOL = _config.get("symbol", "BTC-USDT")
except Exception:
    _config = {}
    DEFAULT_SYMBOL = "BTC-USDT"
POLL_INTERVAL = _config.get("poll_interval", 5)
MIN_TRADE_INTERVAL = _config.get("min_trade_interval", 180)  # from config (default 3min)
MIN_CONFIDENCE = _config.get("min_confidence", 0.6)  # from config (default 60%)
MIN_TRADE_AMOUNT = _config.get("min_trade_amount", 10)  # from config (default $1 minimum)
MAX_POSITION_PCT = _config.get("max_position_pct", 0.5)  # from config
TRADING_FEE_PCT = 0.001  # 0.1% por trade (KuCoin)
MAX_DAILY_TRADES = _config.get("max_daily_trades", 50)  # from config
MAX_DAILY_LOSS = _config.get("max_daily_loss", 150)  # from config (USD)
MAX_POSITIONS = _config.get("max_positions", 3)  # max BUY entries acumuladas
PROFILE = _config.get("profile", "default")  # conservative|aggressive|default

# ====================== ESTADO DO AGENTE ======================
@dataclass
class AgentState:
    """Estado atual do agente"""
    running: bool = False
    symbol: str = DEFAULT_SYMBOL
    position: float = 0.0  # BTC total em carteira (acumulado)
    position_value: float = 0.0  # Valor em USDT
    entry_price: float = 0.0  # Preço médio ponderado das entradas
    position_count: int = 0  # Número de entradas (BUYs) acumuladas
    entries: list = field(default_factory=list)  # [{price, size, ts}] por entrada
    last_trade_time: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    total_pnl: float = 0.0
    dry_run: bool = True
    last_sell_entry_price: float = 0.0  # Trava de recompra: preço médio da última venda
    trailing_high: float = 0.0  # Máxima atingida para trailing stop
    target_sell_price: float = 0.0  # Target de venda calculado pela IA no BUY
    target_sell_reason: str = ""  # Razão do cálculo do target
    sell_count: int = 0  # Total de sells executados
    daily_trades: int = 0  # Trades do dia atual
    daily_pnl: float = 0.0  # PnL acumulado do dia
    daily_date: str = ''  # Data do dia para reset
    profile: str = 'default'  # Perfil: conservative|aggressive|default
    
    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "symbol": self.symbol,
            "position_btc": self.position,
            "position_usdt": self.position_value,
            "entry_price": self.entry_price,
            "position_count": self.position_count,
            "entries": self.entries,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "dry_run": self.dry_run,
            "last_sell_entry_price": self.last_sell_entry_price,
            "target_sell_price": self.target_sell_price,
            "target_sell_reason": self.target_sell_reason,
            "profile": self.profile
        }


@dataclass
class TradeControls:
    """Controles de risco efetivos usados pelo trading loop."""
    min_confidence: float
    min_trade_interval: int
    max_position_pct: float
    max_positions_cap: int
    effective_max_positions: int
    ai_controlled: bool
    ollama_mode: str = "shadow"


@dataclass
class OllamaTradeControlSuggestion:
    """Sugestão estruturada do Ollama para parâmetros de risco."""
    min_confidence: float
    min_trade_interval: int
    max_position_pct: float
    max_positions: int
    rationale: str
    raw: str

# ====================== AGENTE PRINCIPAL ======================
class BitcoinTradingAgent:
    """Agente de trading de Bitcoin 24/7"""
    
    def __init__(self, symbol: str = DEFAULT_SYMBOL, dry_run: bool = True, config_name: Optional[str] = None):
        self.symbol = symbol
        self.config_name = config_name or os.environ.get("COIN_CONFIG_FILE", _config_file)
        self.config_path = Path(__file__).parent / self.config_name
        self.config = self._load_live_config()
        self.state = AgentState(
            symbol=symbol,
            dry_run=dry_run,
            profile=self.config.get("profile", PROFILE),
        )
        self.model = FastTradingModel(symbol)
        self.db = TrainingDatabase()
        
        # Market RAG — inteligência de mercado com busca de padrões
        rag_recalibrate = self.config.get("rag_recalibrate_interval", _config.get("rag_recalibrate_interval", 300))
        rag_snapshot = self.config.get("rag_snapshot_interval", _config.get("rag_snapshot_interval", 30))
        self.market_rag = MarketRAG(
            symbol=symbol,
            profile=self.config.get("profile", PROFILE),
            recalibrate_interval=rag_recalibrate,
            snapshot_interval=rag_snapshot,
        )
        self._rag_apply_cycle = 0
        
        # Threading
        self._stop_event = threading.Event()
        self._trade_lock = threading.Lock()
        self._last_trade_id = 0  # FIX #7: actual DB trade ID
        
        # Callbacks
        self._on_signal_callbacks = []
        self._on_trade_callbacks = []
        self._last_ai_plan_news_ts = 0.0
        self._last_ai_plan_trigger_ts = 0.0
        self._last_ai_trade_controls_trigger_ts = 0.0
        self._last_ai_trade_controls_regime = ""
        
        self.state.start_time = time.time()
        logger.info(
            f"🤖 Agent initialized: {symbol} (dry_run={dry_run}, profile={self.state.profile}, config={self.config_name})"
        )

    def _load_live_config(self) -> Dict:
        """Carrega o config ativo da instância; cai para o config de import em caso de falha."""
        try:
            with open(self.config_path) as cfg_file:
                return json.load(cfg_file)
        except Exception:
            return dict(_config)

    def _current_profile(self) -> str:
        """Sincroniza o profile em memória com o profile do config ativo da instância."""
        live_cfg = self._load_live_config()
        live_profile = live_cfg.get("profile") or self.state.profile or PROFILE or "default"
        if self.state.profile != live_profile:
            logger.warning(
                f"⚠️ Profile drift detected: state={self.state.profile}, config={live_profile} — syncing runtime profile"
            )
            self.state.profile = live_profile
        return self.state.profile

    def _get_runtime_risk_caps(self) -> Dict[str, Any]:
        """Retorna caps/configs ativos da instância sem depender do config de import."""
        live_cfg = self._load_live_config()
        return {
            "min_confidence": float(live_cfg.get("min_confidence", MIN_CONFIDENCE)),
            "min_trade_interval": int(live_cfg.get("min_trade_interval", MIN_TRADE_INTERVAL)),
            "min_trade_amount": float(live_cfg.get("min_trade_amount", MIN_TRADE_AMOUNT)),
            "max_position_pct": max(0.01, float(live_cfg.get("max_position_pct", MAX_POSITION_PCT))),
            "max_positions": max(1, int(live_cfg.get("max_positions", MAX_POSITIONS))),
        }

    def _resolve_trade_controls(self, rag_adj=None) -> TradeControls:
        """Resolve os controles efetivos de trade a partir de config, RAG e Ollama."""
        rag_adj = rag_adj or self.market_rag.get_current_adjustment()
        caps = self._get_runtime_risk_caps()
        ai_controlled = rag_adj.similar_count >= 3

        if ai_controlled:
            min_confidence = float(getattr(rag_adj, "applied_min_confidence", rag_adj.ai_min_confidence))
            min_trade_interval = int(getattr(rag_adj, "applied_min_trade_interval", rag_adj.ai_min_trade_interval))
            max_positions_cap = int(getattr(rag_adj, "applied_max_positions", caps["max_positions"]) or caps["max_positions"])
            effective_max_positions = min(max_positions_cap, int(rag_adj.ai_max_entries or max_positions_cap))
            max_position_pct = float(getattr(rag_adj, "applied_max_position_pct", caps["max_position_pct"]) or caps["max_position_pct"])
        else:
            min_confidence = caps["min_confidence"]
            min_trade_interval = caps["min_trade_interval"]
            max_positions_cap = caps["max_positions"]
            effective_max_positions = caps["max_positions"]
            max_position_pct = caps["max_position_pct"]

        return TradeControls(
            min_confidence=max(0.0, min_confidence),
            min_trade_interval=max(1, min_trade_interval),
            max_position_pct=max(0.01, min(max_position_pct, caps["max_position_pct"])),
            max_positions_cap=max(1, max_positions_cap),
            effective_max_positions=max(1, effective_max_positions),
            ai_controlled=ai_controlled,
            ollama_mode=str(getattr(rag_adj, "ollama_mode", "shadow") or "shadow"),
        )

    @staticmethod
    def _extract_json_object(raw: str) -> Dict[str, Any]:
        """Extrai um objeto JSON mesmo quando o modelo devolve fences ou ruído."""
        cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        candidate = match.group(0) if match else cleaned
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise ValueError("Ollama payload is not a JSON object")
        return parsed

    def _parse_ai_trade_controls(self, raw: str) -> OllamaTradeControlSuggestion:
        """Valida a resposta JSON do Ollama para controles de risco."""
        parsed = self._extract_json_object(raw)
        suggestion = OllamaTradeControlSuggestion(
            min_confidence=float(parsed.get("min_confidence", MIN_CONFIDENCE) or MIN_CONFIDENCE),
            min_trade_interval=int(round(float(parsed.get("min_trade_interval", MIN_TRADE_INTERVAL) or MIN_TRADE_INTERVAL))),
            max_position_pct=float(parsed.get("max_position_pct", MAX_POSITION_PCT) or MAX_POSITION_PCT),
            max_positions=int(round(float(parsed.get("max_positions", MAX_POSITIONS) or MAX_POSITIONS))),
            rationale=str(parsed.get("rationale", "")).strip()[:500],
            raw=raw.strip(),
        )
        return suggestion

    def _has_new_rss_since_last_plan(self) -> bool:
        """Retorna True quando entrou RSS novo relevante desde o último plano."""
        try:
            with self.db._get_conn() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT EXTRACT(EPOCH FROM MAX(timestamp))
                    FROM btc.news_sentiment
                    WHERE coin IN ('BTC', 'GENERAL')
                      AND timestamp > NOW() - INTERVAL '6 hours'
                    """
                )
                row = cur.fetchone()
                latest_ts = float(row[0] or 0.0)
                cur.close()
            if latest_ts <= 0:
                return False
            if latest_ts > self._last_ai_plan_news_ts:
                self._last_ai_plan_news_ts = latest_ts
                return True
        except Exception as e:
            logger.debug(f"RSS trigger check error: {e}")
        return False

    # ====================== STARTUP BOOTSTRAP ======================
    def _startup_bootstrap(self):
        """Rotina de bootstrap executada antes do loop de trading.
        Transfere saldos pendentes, sincroniza posição, coleta dados e auto-treina.
        """
        start_time = time.time()
        logger.info("🔄 Starting bootstrap sequence...")
        # 1. Auto-transfer saldos da conta main→trade
        if not self.state.dry_run:
            try:
                self._auto_transfer_and_sync()
            except Exception as e:
                logger.error(f"❌ Bootstrap - auto transfer failed: {e}")
        # 2. Restaurar posição do banco
        try:
            self._restore_position()
        except Exception as e:
            logger.error(f"❌ Bootstrap - restore position failed: {e}")
        # 3. Detectar depósitos externos (saldo exchange > posição DB)
        if not self.state.dry_run:
            try:
                self._detect_external_deposits()
            except Exception as e:
                logger.error(f"❌ Bootstrap - deposit detection failed: {e}")
        # 4. Coletar dados históricos e popular indicadores
        try:
            self._collect_historical_data()
        except Exception as e:
            logger.error(f"❌ Bootstrap - collect historical data failed: {e}")
        # 5. Auto-treinar modelo
        try:
            self._auto_train()
        except Exception as e:
            logger.error(f"❌ Bootstrap - auto train failed: {e}")
        elapsed = time.time() - start_time
        logger.info(f"⏱️ Bootstrap completed in {elapsed:.1f}s")

    def _auto_transfer_and_sync(self):
        """Transfere automaticamente saldos da conta main para trade.

        Depósitos na KuCoin caem na conta 'main'. O agente opera na conta
        'trade'. Esta função detecta e transfere saldos pendentes.
        """
        base_currency = self.symbol.split("-")[0]  # BTC
        quote_currency = self.symbol.split("-")[1]  # USDT

        for currency in [base_currency, quote_currency]:
            try:
                main_balances = get_balances(account_type="main")
                main_bal = 0.0
                for b in main_balances:
                    if b["currency"] == currency:
                        main_bal = b["available"]
                        break

                if main_bal <= 0:
                    continue

                # Mínimo para transferir (evitar dust)
                min_transfer = 0.00001 if currency == base_currency else 0.01
                if main_bal < min_transfer:
                    logger.debug(
                        f"💤 {currency} main balance {main_bal} below minimum transfer"
                    )
                    continue

                result = inner_transfer(
                    currency=currency,
                    amount=main_bal,
                    from_account="main",
                    to_account="trade",
                )
                if result.get("success"):
                    logger.info(
                        f"💸 Auto-transferred {main_bal:.8f} {currency} "
                        f"main → trade"
                    )
                else:
                    logger.warning(
                        f"⚠️ Failed to transfer {currency}: "
                        f"{result.get('error', 'unknown')}"
                    )
            except Exception as e:
                logger.warning(f"⚠️ Auto-transfer {currency} error: {e}")

    def _detect_external_deposits(self):
        """Detecta depósitos externos comparando saldo exchange vs posição DB.

        Se o saldo real na exchange for maior que a posição rastreada no DB,
        registra a diferença como um trade de compra (depósito externo).
        """
        base_currency = self.symbol.split("-")[0]

        try:
            profile = self._current_profile()
            real_balance = get_balance(base_currency)
            # Usar soma das entries do DB (não self.state.position que já tem saldo exchange)
            db_position = sum(e.get("size", 0) for e in self.state.entries)

            if real_balance <= 0:
                return

            # Tolerância de 0.1% para evitar falsos positivos por arredondamento
            diff = real_balance - db_position
            tolerance = max(real_balance * 0.001, 0.00000100)

            if diff <= tolerance:
                return

            # Em conta compartilhada, só atribuir saldo live ao perfil que já tem
            # posição aberta no próprio ledger. Isso evita duplicar a mesma posição
            # entre aggressive e conservative após restart.
            if not self.state.entries and profile != "default":
                logger.info(
                    f"⏭️ External deposit skipped for profile={profile}: "
                    "no profile-scoped open entries to attach live balance"
                )
                return

            # Depósito externo detectado
            price = get_price(self.symbol)
            if not price or price <= 0:
                logger.warning("⚠️ Cannot register deposit: price unavailable")
                return

            deposit_usdt = diff * price
            logger.info(
                f"📥 External deposit detected: {diff:.8f} {base_currency} "
                f"(~${deposit_usdt:.2f}) — exchange={real_balance:.8f}, "
                f"DB={db_position:.8f}"
            )

            # Registrar como trade de compra
            trade_id = self.db.record_trade(
                symbol=self.symbol,
                side="buy",
                price=price,
                size=diff,
                funds=deposit_usdt,
                dry_run=False,
                metadata={"source": "external_deposit", "auto_detected": True},
                profile=profile,
            )
            logger.info(
                f"✅ Deposit registered as trade #{trade_id}: "
                f"{diff:.8f} {base_currency} @ ${price:,.2f}"
            )

            # Atualizar estado interno
            new_entry = {"price": price, "size": diff, "ts": time.time()}
            self.state.entries.append(new_entry)
            self.state.position = real_balance
            self.state.position_count = len(self.state.entries)

            # Recalcular preço médio ponderado
            total_cost = sum(
                e["price"] * e["size"] for e in self.state.entries
            )
            total_size = sum(e["size"] for e in self.state.entries)
            if total_size > 0:
                self.state.entry_price = total_cost / total_size
                self.state.position_value = total_size * self.state.entry_price

            logger.info(
                f"📊 Position updated: {self.state.position:.8f} {base_currency} "
                f"({self.state.position_count} entries, "
                f"avg ${self.state.entry_price:,.2f})"
            )

        except Exception as e:
            logger.error(f"❌ Deposit detection error: {e}")

    # ====================== AI PLAN GENERATION (OLLAMA — GPU1) ======================
    _AI_PLAN_INTERVAL = 120  # a cada 120 ciclos (~10min com poll_interval=5s)
    _OLLAMA_PLAN_HOST = os.getenv("OLLAMA_PLAN_HOST", "http://192.168.15.2:11434")
    _OLLAMA_PLAN_MODEL = os.getenv("OLLAMA_PLAN_MODEL", "phi4-mini:latest")
    _OLLAMA_TRADE_PARAMS_HOST = os.getenv("OLLAMA_TRADE_PARAMS_HOST", _OLLAMA_PLAN_HOST)
    _OLLAMA_TRADE_PARAMS_MODEL = os.getenv("OLLAMA_TRADE_PARAMS_MODEL", _OLLAMA_PLAN_MODEL)
    _OLLAMA_TRADE_PARAMS_MODE = os.getenv("OLLAMA_TRADE_PARAMS_MODE", "shadow")
    _OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC = int(os.getenv("OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC", "300"))

    @staticmethod
    def _sanitize_ai_plan(text: str) -> str:
        """Sanitiza resposta do LLM removendo alucinações e loops repetitivos.

        Detecta padrões comuns de degeneração em modelos pequenos:
        - Tags <think>/</think> residuais
        - Loops de tokens repetitivos (ex: 'a, a, a, a')
        - Palavras repetidas 5+ vezes consecutivas
        - Conteúdo não relacionado a trading/mercado
        - Excesso de pontuação / caracteres não-alfanuméricos
        - Ausência de vocabulário mínimo de trading
        Retorna string vazia se o texto for considerado degenerado.
        """
        import re as _re

        if not text:
            return ""

        # 1. Remover blocos <think>...</think> (inclusive incompletos)
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
        text = _re.sub(r"</?think>", "", text)

        # 2. Ratio de pontuação/caracteres especiais vs alfanuméricos
        #    Gibberish típico: "ات,,, ,, . , Okay, let ,, ,"
        alpha_chars = sum(1 for c in text if c.isalpha())
        total_chars = len(text.strip())
        if total_chars > 0:
            alpha_ratio = alpha_chars / total_chars
            if alpha_ratio < 0.40:
                logger.warning(
                    f"⚠️ AI plan degenerado: ratio alfanumérico={alpha_ratio:.0%} "
                    f"(mínimo 40%)"
                )
                return ""

        # 3. Detectar loop de tokens: mesma palavra/char repetido 5+ vezes
        tokens = _re.findall(r"\b\w+\b", text.lower())
        if len(tokens) > 10:
            from collections import Counter
            freq = Counter(tokens)
            most_common_word, most_common_count = freq.most_common(1)[0]
            ratio = most_common_count / len(tokens)
            allowed_high_freq = {"de", "do", "da", "o", "a", "e", "em", "com", "para", "que", "um", "uma", "os", "as", "no", "na"}
            if ratio > 0.30 and most_common_word not in allowed_high_freq:
                logger.warning(
                    f"⚠️ AI plan degenerado: '{most_common_word}' aparece "
                    f"{most_common_count}/{len(tokens)} vezes ({ratio:.0%})"
                )
                return ""

        # 4. Detectar sequências repetitivas curtas (ex: ", a" repetido)
        if _re.search(r"(\b\w+\b[,\s]+){5,}\1", text):
            logger.warning("⚠️ AI plan com padrão repetitivo detectado")
            return ""

        # 5. Vocabulário mínimo de trading (pelo menos 3 palavras-chave)
        trading_keywords = [
            "btc", "bitcoin", "preço", "price", "mercado", "market",
            "comprar", "buy", "vender", "sell", "tendência", "trend",
            "rsi", "posição", "position", "suporte", "resistência",
            "alta", "baixa", "bullish", "bearish", "trading", "usdt",
            "volatilidade", "momentum", "regime", "risco", "risk",
            "oportunidade", "opportunity", "stop", "profit", "pnl",
        ]
        text_lower = text.lower()
        trading_hits = sum(1 for kw in trading_keywords if kw in text_lower)
        if trading_hits < 3:
            logger.warning(
                f"⚠️ AI plan sem vocabulário de trading "
                f"(apenas {trading_hits} palavras-chave encontradas, mínimo 3)"
            )
            return ""

        # 6. Detectar echo do prompt (modelo repetindo as instruções)
        prompt_echo_phrases = [
            "não use markdown headers", "responda em 3-5 parágrafos",
            "seja direto e objetivo", "não pense em voz alta",
            "resumo dos próximos passos", "analise o estado atual",
            "sintetem as opções", "let's say the summary",
        ]
        echo_hits = sum(1 for p in prompt_echo_phrases if p in text_lower)
        if echo_hits >= 2:
            logger.warning(
                f"⚠️ AI plan eco do prompt detectado ({echo_hits} frases do prompt)"
            )
            return ""

        # 7. Detectar pontuação solta excessiva (". . . , --" padrões)
        #    Conta sequências de 2+ pontuações separadas por espaço
        lone_punct = len(_re.findall(r"(?:^|[ ])[.,;:\-!?]{1,3}(?:[ ]|$)", text))
        if lone_punct > 5:
            logger.warning(
                f"⚠️ AI plan com pontuação solta excessiva ({lone_punct} ocorrências)"
            )
            return ""

        # 8. Detectar conteúdo claramente não-trading (alucinação temática)
        non_trading_keywords = [
            "trafficking", "murder", "suicide", "porn", "sex",
            "violence", "weapon", "drug", "kill", "terrorist",
        ]
        bad_hits = sum(1 for kw in non_trading_keywords if kw in text_lower)
        if bad_hits >= 2:
            logger.warning(f"⚠️ AI plan com conteúdo não-trading ({bad_hits} keywords)")
            return ""

        # 9. Detectar meta-pensamento (modelo pensando sobre a tarefa)
        meta_phrases = [
            "let me start", "let me check", "wait no", "okay!",
            "let me ", "i need to ", "i have given", "i had give",
            "the user wants", "the user in ", "check again",
            "summarize it", "of course", "let's see",
            "okay, let", "alright,", "so the user",
            "i should ", "let me think", "hmm,",
        ]
        meta_hits = sum(1 for p in meta_phrases if p in text_lower)
        if meta_hits >= 2:
            logger.warning(
                f"⚠️ AI plan meta-thinking detectado "
                f"({meta_hits} padrões de auto-reflexão)"
            )
            return ""

        # 10. Detectar resposta em inglês (prompt pede PT-BR)
        en_only_words = [
            "the", "and", "with", "this", "that", "have", "from",
            "they", "their", "what", "about", "which", "would",
            "should", "could", "been", "were", "into", "also",
        ]
        en_hits = sum(
            1 for w in en_only_words if f" {w} " in f" {text_lower} "
        )
        pt_words = [
            "que", "para", "com", "uma", "não", "mais",
            "está", "são", "como", "pelo", "pode", "será",
        ]
        pt_hits = sum(
            1 for w in pt_words if f" {w} " in f" {text_lower} "
        )
        if en_hits > 5 and pt_hits < 3:
            logger.warning(
                f"⚠️ AI plan em inglês em vez de PT-BR "
                f"(en={en_hits}, pt={pt_hits})"
            )
            return ""

        # 11. Excesso de interrogações (modelo perguntando para si)
        q_count = text.count("?")
        if q_count > 3:
            logger.warning(
                f"⚠️ AI plan com muitas interrogações ({q_count})"
            )
            return ""

        # 12. Gibberish de formato (meta-referências ao output pedido)
        format_meta = [
            "essay", "paragraph", "summarize", "anic\n",
            "write a", "here is", "as requested",
        ]
        fmt_hits = sum(1 for p in format_meta if p in text_lower)
        if fmt_hits >= 2:
            logger.warning(
                f"⚠️ AI plan com meta-referências de formato ({fmt_hits})"
            )
            return ""

        # 13. Comprimento médio de palavras (gibberish tem muitas palavras de 1 char)
        if tokens:
            avg_word_len = sum(len(t) for t in tokens) / len(tokens)
            if avg_word_len < 2.5:
                logger.warning(
                    f"⚠️ AI plan com palavras muito curtas "
                    f"(média {avg_word_len:.1f} chars)"
                )
                return ""

        # 14. Limitar tamanho máximo (evitar output explosivo)
        if len(text) > 3000:
            text = text[:3000].rsplit(".", 1)[0] + "."

        return text.strip()

    def _generate_ai_trade_controls(self, market_state: "MarketState", trigger: str = "periodic") -> None:
        """Gera sugestão estruturada do Ollama para parâmetros de risco."""
        try:
            rag_adj = self.market_rag.get_current_adjustment()
            controls = self._resolve_trade_controls(rag_adj)
            caps = self._get_runtime_risk_caps()
            profile = self._current_profile()
            rag_stats = self.market_rag.get_stats()

            indicators = self.model.indicators
            rsi = indicators.rsi()
            momentum = indicators.momentum()
            volatility = indicators.volatility()
            usdt_bal = get_balance("USDT") if not self.state.dry_run else 1000

            news_lines: list[str] = []
            try:
                with self.db._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT source, title, sentiment::float, confidence::float
                        FROM btc.news_sentiment
                        WHERE coin IN ('BTC', 'GENERAL')
                          AND timestamp > NOW() - INTERVAL '4 hours'
                          AND confidence >= 0.5
                        ORDER BY timestamp DESC
                        LIMIT 5
                    """)
                    for source, title, sentiment, confidence in cur.fetchall():
                        news_lines.append(
                            f"- [{source}] sent={sentiment:+.2f} conf={confidence:.0%} :: {title}"
                        )
                    cur.close()
            except Exception as e:
                logger.debug(f"AI controls news fetch error: {e}")

            prompt = (
                "Você é um conselheiro de risco para um bot de trading de BTC.\n"
                "Retorne apenas JSON válido, sem markdown, com as chaves:\n"
                "min_confidence, min_trade_interval, max_position_pct, max_positions, rationale.\n\n"
                "Regras obrigatórias:\n"
                f"- min_confidence deve ficar entre {max(0.40, controls.min_confidence - 0.10):.3f} e {min(0.92, controls.min_confidence + 0.10):.3f}\n"
                f"- min_trade_interval deve ficar entre {max(30, int(controls.min_trade_interval * 0.5))} e {min(900, int(controls.min_trade_interval * 1.8))}\n"
                f"- max_position_pct não pode passar de {caps['max_position_pct']:.4f}\n"
                f"- max_positions deve ficar entre 1 e {caps['max_positions']}\n"
                "- Use números simples e uma rationale curta em pt-BR.\n"
                "- Não altere target de compra/venda; foque só nos quatro parâmetros.\n"
                "- Se estiver em dúvida, fique perto do baseline do RAG.\n\n"
                f"CONTEXTO:\n"
                f"- profile={profile}\n"
                f"- trigger={trigger}\n"
                f"- regime={rag_stats['current_regime']} conf={rag_stats['regime_confidence']:.0%}\n"
                f"- price={market_state.price:.2f}\n"
                f"- rsi={rsi:.1f} momentum={momentum:.4f} volatility={volatility:.4f}\n"
                f"- orderbook_imbalance={market_state.orderbook_imbalance:.3f} spread={market_state.spread:.6f}\n"
                f"- trade_flow={market_state.trade_flow:.3f}\n"
                f"- usdt_balance={usdt_bal:.2f}\n"
                f"- position_count={self.state.position_count} position_btc={self.state.position:.8f} entry_price={self.state.entry_price:.2f}\n"
                f"- rag_baseline_min_confidence={rag_adj.ai_min_confidence:.3f}\n"
                f"- rag_baseline_min_trade_interval={rag_adj.ai_min_trade_interval}\n"
                f"- rag_ai_position_size_pct={rag_adj.ai_position_size_pct:.4f}\n"
                f"- rag_ai_max_entries={rag_adj.ai_max_entries}\n"
                f"- hard_cap_max_position_pct={caps['max_position_pct']:.4f}\n"
                f"- hard_cap_max_positions={caps['max_positions']}\n"
            )
            if news_lines:
                prompt += "\nNEWS:\n" + "\n".join(news_lines)

            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    f"{self._OLLAMA_TRADE_PARAMS_HOST}/api/generate",
                    json={
                        "model": self._OLLAMA_TRADE_PARAMS_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": 0.0,
                            "num_predict": 160,
                            "num_ctx": 3072,
                            "repeat_penalty": 1.15,
                            "top_k": 30,
                            "top_p": 0.85,
                        },
                    },
                )

            if resp.status_code != 200:
                logger.warning(f"⚠️ Ollama trade controls error: HTTP {resp.status_code}")
                return

            raw = resp.json().get("response", "").strip()
            suggestion = self._parse_ai_trade_controls(raw)
            applied_adj = self.market_rag.set_ollama_trade_controls(
                {
                    "min_confidence": suggestion.min_confidence,
                    "min_trade_interval": suggestion.min_trade_interval,
                    "max_position_pct": suggestion.max_position_pct,
                    "max_positions": suggestion.max_positions,
                    "rationale": suggestion.rationale,
                },
                mode=self._OLLAMA_TRADE_PARAMS_MODE,
                trigger=trigger,
                model=self._OLLAMA_TRADE_PARAMS_MODEL,
            )
            self._save_ai_trade_controls(
                suggestion=suggestion,
                applied_adj=applied_adj,
                trigger=trigger,
                raw=raw,
            )
            logger.info(
                "🧠 AI trade controls "
                f"[{self._OLLAMA_TRADE_PARAMS_MODE}] trigger={trigger} "
                f"suggested(conf>={suggestion.min_confidence:.0%}, cd={suggestion.min_trade_interval}s, "
                f"cap={suggestion.max_position_pct*100:.1f}%/{suggestion.max_positions}) "
                f"applied(conf>={applied_adj.applied_min_confidence:.0%}, cd={applied_adj.applied_min_trade_interval}s, "
                f"cap={applied_adj.applied_max_position_pct*100:.1f}%/{applied_adj.applied_max_positions})"
            )
        except Exception as e:
            logger.warning(f"⚠️ AI trade controls generation failed: {e}")

    def _save_ai_trade_controls(
        self,
        *,
        suggestion: OllamaTradeControlSuggestion,
        applied_adj,
        trigger: str,
        raw: str,
    ) -> None:
        """Persiste a última sugestão estruturada do Ollama para auditoria."""
        try:
            self.db.record_ai_trade_controls(
                symbol=self.symbol,
                profile=self._current_profile(),
                trigger=trigger,
                mode=str(getattr(applied_adj, "ollama_mode", self._OLLAMA_TRADE_PARAMS_MODE) or self._OLLAMA_TRADE_PARAMS_MODE),
                model=self._OLLAMA_TRADE_PARAMS_MODEL,
                suggested={
                    "min_confidence": suggestion.min_confidence,
                    "min_trade_interval": suggestion.min_trade_interval,
                    "max_position_pct": suggestion.max_position_pct,
                    "max_positions": suggestion.max_positions,
                },
                applied={
                    "min_confidence": getattr(applied_adj, "applied_min_confidence", 0.0),
                    "min_trade_interval": getattr(applied_adj, "applied_min_trade_interval", 0),
                    "max_position_pct": getattr(applied_adj, "applied_max_position_pct", 0.0),
                    "max_positions": getattr(applied_adj, "applied_max_positions", 0),
                },
                rationale=suggestion.rationale,
                metadata={
                    "baseline_min_confidence": getattr(applied_adj, "baseline_min_confidence", 0.0),
                    "baseline_min_trade_interval": getattr(applied_adj, "baseline_min_trade_interval", 0),
                    "baseline_max_position_pct": getattr(applied_adj, "baseline_max_position_pct", 0.0),
                    "baseline_max_positions": getattr(applied_adj, "baseline_max_positions", 0),
                    "raw": raw[:4000],
                },
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save AI trade controls: {e}")

    def _generate_ai_plan(self, market_state: "MarketState") -> None:
        """Gera análise dos próximos passos da IA via Ollama (GPU1) e salva no banco.

        Chamado periodicamente (~30min) do loop principal.
        Usa dados de mercado, posição e regime para gerar texto explicativo.
        Modelo phi4-mini:latest via Ollama local.
        """
        try:
            rag_adj = self.market_rag.get_current_adjustment()
            rag_stats = self.market_rag.get_stats()

            # Contexto compacto para o LLM
            indicators = self.model.indicators
            rsi = indicators.rsi()
            momentum = indicators.momentum()
            volatility = indicators.volatility()

            position_info = "Sem posição aberta"
            if self.state.position > 0:
                pnl_pct = ((market_state.price - self.state.entry_price)
                           / self.state.entry_price * 100)
                usdt_val = self.state.position * market_state.price
                position_info = (
                    f"{self.state.position:.8f} BTC ({self.state.position_count} entradas), "
                    f"preço médio ${self.state.entry_price:,.2f}, "
                    f"valor ~${usdt_val:.2f}, PnL {pnl_pct:+.2f}%"
                )

            usdt_bal = get_balance("USDT") if not self.state.dry_run else 1000

            # ── Calcular condições de venda para contexto do prompt ──
            min_sell_pnl = _config.get("min_sell_pnl", 0.015)
            _live_cfg = self._load_live_config()
            auto_sl_cfg = _live_cfg.get("auto_stop_loss", {})
            auto_tp_cfg = _live_cfg.get("auto_take_profit", {})
            trailing_cfg = _live_cfg.get("trailing_stop", {})
            sl_enabled = auto_sl_cfg.get("enabled", False)
            tp_enabled = auto_tp_cfg.get("enabled", False)
            trailing_enabled = trailing_cfg.get("enabled", False)
            sl_pct = auto_sl_cfg.get("pct", 0.025)
            # TP dinâmico da IA (se disponível) ou config fallback
            if rag_adj.similar_count >= 3:
                tp_pct = rag_adj.ai_take_profit_pct
            else:
                tp_pct = auto_tp_cfg.get("pct", 0.025)
            # FIX #14: Floor mínimo para TP
            min_tp_pct = auto_tp_cfg.get("min_pct", 0.015)
            if tp_pct < min_tp_pct:
                tp_pct = min_tp_pct
            tp_target = self.state.entry_price * (1 + tp_pct) if self.state.entry_price > 0 else 0
            sl_price = self.state.entry_price * (1 - sl_pct) if self.state.entry_price > 0 else 0
            trailing_activation = trailing_cfg.get("activation_pct", 0.015)
            trailing_trail = trailing_cfg.get("trail_pct", 0.008)
            trailing_activation_price = (
                self.state.entry_price * (1 + trailing_activation)
                if self.state.entry_price > 0 else 0
            )
            # Preço mínimo para desbloquear SELL
            if self.state.position > 0 and self.state.entry_price > 0:
                _pos = self.state.position
                _fee = TRADING_FEE_PCT
                sell_unlock_price = (
                    (min_sell_pnl + self.state.entry_price * _pos * (1 + _fee))
                    / (_pos * (1 - _fee))
                )
                current_net_pnl = (
                    (market_state.price - self.state.entry_price) * _pos
                    - (self.state.entry_price * _pos * _fee)
                    - (market_state.price * _pos * _fee)
                )
            else:
                sell_unlock_price = 0
                current_net_pnl = 0

            # ── Buscar notícias recentes para contexto e citações ──
            news_articles = []
            news_prompt_block = ""
            try:
                with self.db._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT source, title, sentiment::float, confidence::float,
                               category, url, coin
                        FROM btc.news_sentiment
                        WHERE coin IN ('BTC', 'GENERAL')
                          AND timestamp > NOW() - INTERVAL '4 hours'
                          AND confidence >= 0.5
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """)
                    news_articles = [
                        {
                            "source": r[0], "title": r[1], "sentiment": r[2],
                            "confidence": r[3], "category": r[4], "url": r[5],
                            "coin": r[6],
                        }
                        for r in cur.fetchall()
                    ]
                    cur.close()
            except Exception as e:
                logger.debug(f"📰 News fetch for plan: {e}")

            if news_articles:
                # Score agregado
                avg_sent = sum(a["sentiment"] for a in news_articles) / len(news_articles)
                sent_label = "BULLISH" if avg_sent > 0.1 else "BEARISH" if avg_sent < -0.1 else "NEUTRO"
                lines = [f"\nNOTÍCIAS RECENTES (sentimento geral: {sent_label}, score={avg_sent:+.2f}):"]
                for i, art in enumerate(news_articles[:8], 1):
                    s = "🟢" if art["sentiment"] > 0.1 else "🔴" if art["sentiment"] < -0.1 else "⚪"
                    lines.append(
                        f"  {i}. [{art['source']}] {s} {art['title']} "
                        f"(sent={art['sentiment']:+.2f}, cat={art['category']})"
                    )
                lines.append(
                    "Considere essas notícias na sua análise e mencione as mais relevantes."
                )
                news_prompt_block = "\n".join(lines) + "\n\n"

            prompt = (
                f"Você é um analista de trading de BTC. Analise o estado atual e gere um "
                f"resumo dos PRÓXIMOS PASSOS da estratégia em português do Brasil.\n\n"
                f"DADOS ATUAIS:\n"
                f"- Preço BTC: ${market_state.price:,.2f}\n"
                f"- RSI: {rsi:.1f} | Momentum: {momentum:.3f} | Volatilidade: {volatility:.4f}\n"
                f"- Regime: {rag_stats['current_regime']} (confiança {rag_stats['regime_confidence']:.0%})\n"
                f"- Orderbook: imbalance={market_state.orderbook_imbalance:.2f}, "
                f"spread={market_state.spread:.2f}\n"
                f"- Posição: {position_info}\n"
                f"- USDT disponível: ${usdt_bal:.2f}\n"
                f"- Config IA: buy_target=${rag_adj.ai_buy_target_price:,.2f}, "
                f"TP={rag_adj.ai_take_profit_pct*100:.2f}%, "
                f"sizing={rag_adj.ai_position_size_pct*100:.1f}%×{rag_adj.ai_max_entries}, "
                f"agressividade={rag_adj.ai_aggressiveness:.0%}\n"
                f"- Win rate: {self.state.winning_trades}/{self.state.total_trades} trades\n\n"
                f"{news_prompt_block}"
                f"CONDIÇÕES DE VENDA (resumo atual):\n"
                f"- Target de venda (IA): ${self.state.target_sell_price:,.2f}\n"
                f"- PnL líquido mínimo (fallback): ${min_sell_pnl:.3f}\n"
                f"- Preço mín. para desbloquear SELL: ${sell_unlock_price:,.2f} "
                f"(entry ${self.state.entry_price:,.2f} + fees + min_pnl)\n"
                f"- Auto Take-Profit: {'ATIVADO' if tp_enabled else 'DESATIVADO'}, "
                f"TP={tp_pct*100:.2f}% → alvo ${tp_target:,.2f}\n"
                f"- Auto Stop-Loss: {'ATIVADO, SL=' + f'{sl_pct*100:.1f}% → piso ${sl_price:,.2f}' if sl_enabled else 'DESATIVADO'}\n"
                f"- Trailing Stop: {'ATIVADO, ativa em +' + f'{trailing_activation*100:.1f}% (${trailing_activation_price:,.2f}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}\n"
                f"- PnL líquido atual: ${current_net_pnl:.4f}\n\n"
                f"Responda em 3-5 parágrafos curtos com:\n"
                f"1. Situação atual do mercado\n"
                f"2. O que o agente vai fazer a seguir (comprar, vender, esperar)\n"
                f"3. Cenário de saída: quando e a que preço a venda será executada\n"
                f"4. Riscos e oportunidades identificados\n"
                f"5. Cite as fontes de notícias que mais impactam a análise (ex: [CoinDesk], [CoinTelegraph])\n"
                f"Seja direto e objetivo. Não use markdown headers."
            )

            client = httpx.Client(timeout=180.0)  # 3min — offload GPU+RAM
            resp = client.post(
                f"{self._OLLAMA_PLAN_HOST}/api/generate",
                json={
                    "model": self._OLLAMA_PLAN_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 1024,
                        "num_ctx": 4096,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 128,
                        "top_k": 40,
                        "top_p": 0.9,
                    },
                },
            )
            client.close()

            if resp.status_code != 200:
                logger.warning(f"⚠️ Ollama AI plan error: HTTP {resp.status_code}")
                return

            raw_text = resp.json().get("response", "").strip()
            plan_text = self._sanitize_ai_plan(raw_text)
            if not plan_text or len(plan_text) < 30:
                logger.warning(
                    f"⚠️ AI plan rejected (len={len(raw_text)}, "
                    f"sanitized={len(plan_text)}): {raw_text[:100]}..."
                )
                return

            # ── Anexar resumo estruturado das condições de venda ──
            sell_summary_lines = [
                "",
                "━━━ CONDIÇÕES DE VENDA (dados reais) ━━━",
                f"• PnL líquido mínimo p/ vender: ${min_sell_pnl:.3f}",
                f"• Preço mín. p/ desbloquear SELL: ${sell_unlock_price:,.2f}",
            ]
            if self.state.position > 0:
                sell_summary_lines.append(
                    f"• Entry médio: ${self.state.entry_price:,.2f} | "
                    f"Posição: {self.state.position:.8f} BTC"
                )
            sell_summary_lines.append(
                f"• Auto Take-Profit: "
                f"{'ATIVADO TP=' + f'{tp_pct*100:.2f}% → alvo ${tp_target:,.2f}' if tp_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• Auto Stop-Loss: "
                f"{'ATIVADO SL=' + f'{sl_pct*100:.1f}% → piso ${sl_price:,.2f}' if sl_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• Trailing Stop: "
                f"{'ATIVADO ativa +' + f'{trailing_activation*100:.1f}% (${trailing_activation_price:,.2f}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• PnL líquido atual: ${current_net_pnl:.4f}"
            )
            plan_text += "\n" + "\n".join(sell_summary_lines)

            # ── Anexar bloco de fontes/citações ──
            if news_articles:
                cite_lines = [
                    "",
                    "━━━ FONTES DE NOTÍCIAS ━━━",
                ]
                for i, art in enumerate(news_articles[:8], 1):
                    s_icon = "🟢" if art["sentiment"] > 0.1 else "🔴" if art["sentiment"] < -0.1 else "⚪"
                    cite_lines.append(
                        f"  {i}. {s_icon} [{art['source'].upper()}] {art['title']}"
                    )
                    cite_lines.append(
                        f"     Sentimento: {art['sentiment']:+.2f} | "
                        f"Confiança: {art['confidence']:.0%} | "
                        f"Categoria: {art['category']}"
                    )
                    if art.get("url"):
                        cite_lines.append(f"     🔗 {art['url']}")
                avg_s = sum(a["sentiment"] for a in news_articles) / len(news_articles)
                cite_lines.append(
                    f"\n📊 Sentimento agregado: {avg_s:+.2f} "
                    f"({len(news_articles)} artigos analisados via eddie-sentiment)"
                )
                plan_text += "\n" + "\n".join(cite_lines)

            self._save_ai_plan(
                plan_text=plan_text,
                price=market_state.price,
                regime=rag_stats["current_regime"],
                model=self._OLLAMA_PLAN_MODEL,
                metadata={
                    "rsi": round(rsi, 1),
                    "momentum": round(momentum, 3),
                    "volatility": round(volatility, 4),
                    "position_btc": round(self.state.position, 8),
                    "position_count": self.state.position_count,
                    "entry_price": round(self.state.entry_price, 2),
                    "usdt_balance": round(usdt_bal, 2),
                    "regime_confidence": round(rag_stats["regime_confidence"], 3),
                    "buy_target": round(rag_adj.ai_buy_target_price, 2),
                    "take_profit_pct": round(rag_adj.ai_take_profit_pct, 4),
                    "sell_unlock_price": round(sell_unlock_price, 2),
                    "current_net_pnl": round(current_net_pnl, 4),
                    "tp_target": round(tp_target, 2),
                    "sl_enabled": sl_enabled,
                    "tp_enabled": tp_enabled,
                    "trailing_enabled": trailing_enabled,
                },
            )
            logger.info(
                f"🧠 AI plan generated ({len(plan_text)} chars): "
                f"regime={rag_stats['current_regime']}, price=${market_state.price:,.2f}"
            )
        except Exception as e:
            logger.warning(f"⚠️ AI plan generation failed: {e}")

    def _save_ai_plan(
        self,
        plan_text: str,
        price: float,
        regime: str,
        model: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Salva plano da IA na tabela btc.ai_plans e faz housekeeping."""
        try:
            profile = self._current_profile()
            with self.db._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO btc.ai_plans
                       (timestamp, symbol, plan_text, model, regime, price, metadata, profile)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        time.time(),
                        self.symbol,
                        plan_text,
                        model,
                        regime,
                        price,
                        json.dumps(metadata or {}),
                        profile,
                    ),
                )
                # Housekeeping: manter apenas as últimas 10 entradas por symbol
                cursor.execute(
                    """DELETE FROM btc.ai_plans
                       WHERE symbol = %s AND profile = %s AND id NOT IN (
                           SELECT id FROM btc.ai_plans
                           WHERE symbol = %s AND profile = %s
                           ORDER BY timestamp DESC LIMIT 10
                       )""",
                    (self.symbol, profile, self.symbol, profile),
                )
                if cursor.rowcount > 0:
                    logger.info(f"🧹 AI plans housekeeping: removed {cursor.rowcount} old entries")
                cursor.close()
        except Exception as e:
            logger.warning(f"⚠️ Failed to save AI plan: {e}")

    def _cleanup_garbage_plans(self) -> None:
        """Remove planos de IA com conteúdo degenerado do banco de dados.

        Aplica o sanitizador em todas as entradas existentes e remove as
        que falharem na validação. Chamado no startup do agente.
        """
        try:
            with self.db._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, plan_text FROM btc.ai_plans WHERE symbol = %s",
                    (self.symbol,),
                )
                rows = cursor.fetchall()
                garbage_ids: list[int] = []
                for row_id, text in rows:
                    sanitized = self._sanitize_ai_plan(text or "")
                    if not sanitized or len(sanitized) < 30:
                        garbage_ids.append(row_id)
                if garbage_ids:
                    cursor.execute(
                        "DELETE FROM btc.ai_plans WHERE id = ANY(%s)",
                        (garbage_ids,),
                    )
                    logger.info(
                        f"🧹 Cleaned {len(garbage_ids)} garbage AI plans from DB"
                    )
                cursor.close()
        except Exception as e:
            logger.warning(f"⚠️ AI plans cleanup failed: {e}")

    def _restore_position(self):
        """Restaura posição aberta (multi-posição) do banco de dados.
        Encontra todos os BUYs desde o último SELL para reconstruir entradas acumuladas.
        """
        base_currency = self.symbol.split("-")[0]

        # Buscar últimos trades para reconstruir multi-posição
        profile = self._current_profile()
        trades = self.db.get_recent_trades(
            symbol=self.symbol, limit=50,
            include_dry=self.state.dry_run,
            profile=profile,
        )
        if not trades:
            logger.info("📭 No previous trades found — starting fresh")
            return

        # Restaurar last_trade_time do trade mais recente
        self.state.last_trade_time = trades[0].get("timestamp", 0)

        # Encontrar todas as compras abertas (BUYs desde o último SELL)
        open_buys = []
        for t in trades:  # Ordered by timestamp DESC
            if t.get("side") == "sell":
                break  # Encontrou SELL, parar de coletar
            if t.get("side") == "buy":
                open_buys.append(t)

        if not open_buys:
            # Restaurar trava de recompra: pegar preço de entrada da última posição vendida
            last_sell = next((t for t in trades if t.get("side") == "sell"), None)
            if last_sell:
                # Buscar BUYs anteriores ao SELL para calcular preço médio de entrada
                buys_before_sell = []
                found_sell = False
                for t in trades:
                    if t.get("side") == "sell" and not found_sell:
                        found_sell = True
                        continue
                    if found_sell and t.get("side") == "buy":
                        buys_before_sell.append(t)
                    elif found_sell and t.get("side") == "sell":
                        break  # Chegou em outra venda anterior
                if buys_before_sell:
                    total_sz = sum(b.get("size", 0) or 0 for b in buys_before_sell)
                    total_ct = sum((b.get("size", 0) or 0) * (b.get("price", 0) or 0) for b in buys_before_sell)
                    if total_sz > 0:
                        self.state.last_sell_entry_price = total_ct / total_sz
                        logger.info(
                            f"🔒 Restored rebuy lock: last sell entry ${self.state.last_sell_entry_price:,.2f}"
                        )
            logger.info(f"📭 Last trade was sell — no open position")
            return

        # Reconstruir multi-posição com preço médio ponderado
        total_size = 0.0
        total_cost = 0.0
        entries = []
        for buy in reversed(open_buys):  # Ordem cronológica
            size = buy.get("size", 0) or 0
            price = buy.get("price", 0) or 0
            ts = buy.get("timestamp", 0) or 0
            if size > 0 and price > 0:
                total_size += size
                total_cost += size * price
                entries.append({"price": price, "size": size, "ts": ts})

        if total_size <= 0:
            logger.info("📭 Open buys have zero size — no position")
            return

        avg_entry = total_cost / total_size

        # Cross-check: se modo LIVE, verificar saldo real na exchange
        if not self.state.dry_run:
            try:
                real_balance = get_balance(base_currency)
                if real_balance > 0:
                    self.state.position = real_balance
                    self.state.entry_price = avg_entry
                    self.state.position_value = real_balance * avg_entry
                    self.state.position_count = len(entries)
                    self.state.entries = entries
                    logger.info(
                        f"🔄 Restored LIVE multi-position: {real_balance:.8f} {base_currency} "
                        f"({len(entries)} entries, avg ${avg_entry:,.2f})"
                    )
                else:
                    logger.info(f"📭 DB shows open BUYs but exchange balance is 0 — no position")
            except Exception as e:
                self.state.position = total_size
                self.state.entry_price = avg_entry
                self.state.position_value = total_size * avg_entry
                self.state.position_count = len(entries)
                self.state.entries = entries
                logger.warning(
                    f"⚠️ Could not check exchange ({e}), using DB: "
                    f"{total_size:.8f} ({len(entries)} entries, avg ${avg_entry:,.2f})"
                )
        else:
            self.state.position = total_size
            self.state.entry_price = avg_entry
            self.state.position_value = total_size * avg_entry
            self.state.position_count = len(entries)
            self.state.entries = entries
            logger.info(
                f"🔄 Restored DRY multi-position: {total_size:.8f} {base_currency} "
                f"({len(entries)} entries, avg ${avg_entry:,.2f})"
            )

        # 4. Restaurar métricas históricas (total_trades, winning_trades, total_pnl)
        try:
            all_trades = self.db.get_recent_trades(
                symbol=self.symbol, limit=10000,
                include_dry=self.state.dry_run,
                profile=profile,
            )
            self.state.total_trades = len(all_trades)
            sells = [t for t in all_trades if t.get("side") == "sell"]
            self.state.sell_count = len(sells)
            self.state.winning_trades = sum(
                1 for t in sells if (t.get("pnl") or 0) > 0
            )
            self.state.total_pnl = sum(
                t.get("pnl") or 0 for t in all_trades
            )
            # FIX #4/5: Restore daily counters
            today = date.today().isoformat()
            self.state.daily_date = today
            today_trades = [t for t in all_trades
                           if date.fromtimestamp(t.get("timestamp", 0)).isoformat() == today]
            self.state.daily_trades = len(today_trades)
            self.state.daily_pnl = sum(t.get("pnl") or 0 for t in today_trades)
            win_rate = self.state.winning_trades / max(self.state.sell_count, 1)
            logger.info(
                f"📊 Restored metrics: {self.state.total_trades} trades "
                f"({self.state.sell_count} sells, {self.state.winning_trades} wins, "
                f"WR={win_rate:.1%}), PnL=${self.state.total_pnl:.4f}, "
                f"today: {self.state.daily_trades} trades, PnL=${self.state.daily_pnl:.4f}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not restore metrics: {e}")

        # 5. Adiar target de venda até a primeira recalibração real do RAG
        if self.state.position > 0 and self.state.entry_price > 0:
            try:
                self.state.target_sell_price = 0.0
                self.state.target_sell_reason = ""
                logger.info(
                    "⏳ Target SELL adiado até a primeira recalibração real da IA"
                )
            except Exception as e:
                logger.warning(f"⚠️ Could not restore target_sell_price: {e}")

    def _collect_historical_data(self):
        """Coleta candles históricos da KuCoin para popular indicadores.
        Sem isso, RSI/momentum/trend começam com valores default (50/0/0).
        """
        logger.info(f"📈 Collecting historical candles for {self.symbol}...")
        candles = get_candles(self.symbol, ktype="1min", limit=500)
        if not candles:
            logger.warning("⚠️ No candles returned from KuCoin")
            return

        # Popular indicadores técnicos com dados reais
        self.model.indicators.update_from_candles(candles)
        logger.info(
            f"📊 Loaded {len(candles)} candles into indicators "
            f"(RSI={self.model.indicators.rsi():.1f}, "
            f"momentum={self.model.indicators.momentum():.3f}, "
            f"volatility={self.model.indicators.volatility():.4f})"
        )

        # Persistir candles no PostgreSQL para enriquecer dados de backtesting
        try:
            self.db.store_candles(self.symbol, "1min", candles)
            logger.info(f"💾 Stored {len(candles)} candles in database")
        except Exception as e:
            logger.warning(f"⚠️ Could not store candles: {e}")

    def _sync_target_sell_with_ai(self, reason_prefix: str = "IA") -> None:
        """Aperta o target de venda quando a IA passa a sugerir uma saída mais defensiva.

        O bootstrap pode restaurar um target com contexto incompleto. Depois que o RAG
        aquece com histórico e contexto live, aceitamos apenas ajustes para baixo
        no target vigente, preservando a disciplina de saída sem afrouxar a meta.
        """
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return

        try:
            rag_adj = self.market_rag.get_current_adjustment()
            ai_tp = rag_adj.ai_take_profit_pct
            _atp_cfg = _config.get("auto_take_profit", {})
            _min_tp = _atp_cfg.get("min_pct", 0.015)
            if ai_tp < _min_tp:
                ai_tp = _min_tp

            new_target = self.state.entry_price * (1 + ai_tp)
            old_target = self.state.target_sell_price

            if old_target <= 0:
                self.state.target_sell_price = new_target
                self.state.target_sell_reason = rag_adj.ai_take_profit_reason
                logger.info(
                    f"🎯 Target SELL inicializado pela {reason_prefix}: ${new_target:,.2f} "
                    f"(+{ai_tp*100:.2f}% sobre avg ${self.state.entry_price:,.2f}) "
                    f"— {rag_adj.ai_take_profit_reason}"
                )
                return

            if new_target + 0.01 < old_target:
                self.state.target_sell_price = new_target
                self.state.target_sell_reason = rag_adj.ai_take_profit_reason
                logger.info(
                    f"🔄 Target SELL apertado pela {reason_prefix}: ${old_target:,.2f} → "
                    f"${new_target:,.2f} (+{ai_tp*100:.2f}%) — {rag_adj.ai_take_profit_reason}"
                )
        except Exception as e:
            logger.debug(f"Target SELL sync error: {e}")

    def _analyze_signal_context(self, rag_adj, signal: Optional[Signal] = None) -> dict:
        """Resume penalidades e bonificações implícitas no texto do sinal."""
        signal_reason = (signal.reason or "").lower() if signal else ""
        regime = getattr(rag_adj, "suggested_regime", "RANGING")

        penalties: list[str] = []
        bonuses: list[str] = []
        penalty_score = 0.0
        bonus_score = 0.0

        def penalize(points: float, label: str) -> None:
            nonlocal penalty_score
            penalty_score += points
            penalties.append(label)

        def bonus(points: float, label: str) -> None:
            nonlocal bonus_score
            bonus_score += points
            bonuses.append(label)

        if regime == "BEARISH":
            penalize(1.6, "regime_bearish")
        elif regime == "BULLISH":
            bonus(1.0, "regime_bullish")

        if "[bearish]" in signal_reason or "bearish regime" in signal_reason:
            penalize(2.0, "sinal_bearish")
        if "[bullish]" in signal_reason:
            bonus(1.5, "sinal_bullish")

        if "selling pressure" in signal_reason:
            penalize(1.6, "selling_pressure")
        if "ask pressure" in signal_reason:
            penalize(1.2, "ask_pressure")
        if "negative momentum" in signal_reason:
            penalize(1.6, "negative_momentum")
        if "rsi overbought" in signal_reason:
            penalize(1.6, "rsi_overbought")
        elif "rsi high" in signal_reason:
            penalize(0.8, "rsi_high")

        if "news:bearish" in signal_reason:
            penalize(0.8, "news_bearish")
        elif "news:bullish" in signal_reason:
            bonus(0.6, "news_bullish")

        if "bid pressure" in signal_reason:
            bonus(0.85, "bid_pressure")
        if "buying pressure" in signal_reason:
            bonus(0.85, "buying_pressure")
        if "positive momentum" in signal_reason:
            bonus(1.0, "positive_momentum")
        if "rsi oversold" in signal_reason:
            bonus(1.25, "rsi_oversold")
        elif "rsi low" in signal_reason:
            bonus(0.5, "rsi_low")

        net_score = penalty_score - bonus_score
        conflict = penalty_score >= 2.2 and bonus_score >= 1.0
        hard_block_buy = net_score >= 3.4 or (conflict and net_score >= 2.2)
        strong_bearish = penalty_score >= 3.4

        return {
            "penalty_score": round(penalty_score, 2),
            "bonus_score": round(bonus_score, 2),
            "net_score": round(net_score, 2),
            "conflict": conflict,
            "hard_block_buy": hard_block_buy,
            "strong_bearish": strong_bearish,
            "penalties": penalties,
            "bonuses": bonuses,
            "reason": signal_reason,
        }

    def _get_sell_below_target_confidence(self, rag_adj, ai_controlled: bool, signal: Optional[Signal] = None) -> float:
        """Retorna a confiança mínima para vender abaixo do target da IA.

        Em BEARISH, a saída deve ser mais permissiva para não segurar posição ruim
        à toa. Em BULLISH, exigimos confirmação mais forte antes de abrir mão do
        target cheio.
        """
        if not ai_controlled:
            return 0.85

        base_conf = float(getattr(rag_adj, "applied_min_confidence", rag_adj.ai_min_confidence))
        regime = rag_adj.suggested_regime
        context = self._analyze_signal_context(rag_adj, signal)
        if context["strong_bearish"] and regime != "BULLISH":
            regime = "BEARISH"

        if regime == "BEARISH":
            threshold = min(max(base_conf - 0.02, 0.52), 0.68)
            if context["strong_bearish"]:
                threshold = max(0.50, threshold - 0.03)
            return threshold
        if regime == "BULLISH":
            return min(max(base_conf + 0.18, 0.75), 0.88)
        return min(max(base_conf + 0.10, 0.65), 0.80)

    def _get_buy_extra_discount_pct(self, rag_adj, signal: Optional[Signal] = None) -> float:
        """Retorna desconto adicional exigido para BUY em contexto fraco.

        A ideia é evitar entradas de reversão rasa quando o próprio sinal já carrega
        pressão vendedora ou regime bearish. O alvo de compra da IA continua sendo a
        base; este método só exige um preço melhor nesses cenários.
        """
        context = self._analyze_signal_context(rag_adj, signal)
        extra_discount = 0.0

        if rag_adj.suggested_regime == "BEARISH":
            extra_discount = max(extra_discount, 0.0015)
        if context["conflict"]:
            extra_discount = max(extra_discount, 0.0020)
        if context["strong_bearish"]:
            extra_discount = max(extra_discount, 0.0035)
        if context["bonus_score"] >= 2.0:
            extra_discount = max(0.0, extra_discount - 0.0004)

        return max(extra_discount, 0.0)

    def _get_buy_target_tolerance_pct(self, rag_adj, signal: Optional[Signal] = None) -> float:
        """Retorna tolerância pequena acima do alvo de compra em cenários neutros/fortes.

        A meta é evitar perder apenas as entradas marginais com melhor histórico.
        A tolerância é separada por perfil e só aparece quando o sinal mostra
        qualidade suficiente; em contexto BEARISH forte ou contraditório, a
        tolerância continua nula.
        """
        context = self._analyze_signal_context(rag_adj, signal)
        regime = getattr(rag_adj, "suggested_regime", "RANGING")
        profile = self._current_profile()
        reason = (signal.reason or "").lower() if signal else ""
        confidence = float(getattr(signal, "confidence", 0.0) or 0.0)
        has_bid_buy = "bid pressure" in reason and "buying pressure" in reason
        has_news_bull = "news:bullish" in reason
        is_oversold = "rsi oversold" in reason or "rsi low" in reason
        clean_context = (
            "selling pressure" not in reason
            and "ask pressure" not in reason
            and "bearish" not in reason
        )

        if context["strong_bearish"] or regime == "BEARISH":
            return 0.0

        if context["conflict"]:
            return 0.0

        if profile == "aggressive":
            # Histórico favorece entradas com news bullish e contexto limpo.
            if confidence >= 0.62 and has_news_bull and clean_context and (has_bid_buy or regime == "BULLISH"):
                return 0.0008
            return 0.0

        if profile == "conservative":
            # Conservador só afrouxa quando o sinal tem reversão limpa e confiança alta.
            if confidence >= 0.66 and clean_context and is_oversold:
                return 0.0008
            return 0.0

        if regime == "BULLISH" and confidence >= 0.64 and clean_context and has_news_bull:
            return 0.0006

        return 0.0

    def _auto_train(self):
        """Auto-treinamento batch do Q-learning usando market_states históricos.
        Complementa o treinamento online (tick-a-tick) com replay offline.
        """
        logger.info(f"🎓 Starting auto-training for {self.symbol}...")
        manager = TrainingManager(self.db)
        batch = manager.generate_training_batch(self.symbol, batch_size=500)

        if len(batch) < 10:
            logger.warning(
                f"⚠️ Insufficient training data ({len(batch)} samples). "
                f"Need at least 10. Skipping auto-train."
            )
            return

        trained = 0
        total_reward = 0.0
        import numpy as np
        for sample in batch:
            try:
                current = sample["state"]
                next_st = sample["next_state"]
                price_change = sample["price_change"]

                # Construir features do estado atual
                features = []
                for key in ["rsi", "momentum", "volatility", "trend",
                            "orderbook_imbalance", "trade_flow", "price", "volume"]:
                    val = current.get(key)
                    features.append(float(val) if val is not None else 0.0)
                features_arr = np.array(features, dtype=np.float32)

                # Construir features do próximo estado
                next_features = []
                for key in ["rsi", "momentum", "volatility", "trend",
                            "orderbook_imbalance", "trade_flow", "price", "volume"]:
                    val = next_st.get(key)
                    next_features.append(float(val) if val is not None else 0.0)
                next_features_arr = np.array(next_features, dtype=np.float32)

                best_action = int(sample.get("best_action", -1))
                reward = sample.get("retro_reward")

                if reward is None or best_action not in (0, 1, 2):
                    fee_drag = TRADING_FEE_PCT * 2.0
                    actionable_edge = abs(price_change) - fee_drag
                    trend_value = float(current.get("trend") or 0.0)
                    regime_guess = (
                        "BULLISH" if trend_value > 0.12 else
                        "BEARISH" if trend_value < -0.12 else
                        "RANGING"
                    )

                    if price_change > fee_drag:
                        best_action = 1
                        reward = actionable_edge * (
                            50 if regime_guess == "BULLISH" else 34 if regime_guess == "RANGING" else 30
                        )
                    elif price_change < -fee_drag:
                        best_action = 2
                        reward = actionable_edge * (
                            50 if regime_guess == "BEARISH" else 34 if regime_guess == "RANGING" else 30
                        )
                    else:
                        best_action = 0
                        reward = 0.05 if regime_guess == "RANGING" else 0.015

                self.model.q_model.update(
                    features_arr, best_action, reward, next_features_arr
                )
                total_reward += reward
                trained += 1
            except Exception as e:
                logger.debug(f"⚠️ Training sample error: {e}")
                continue

        # Salvar modelo atualizado
        self.model.save()
        logger.info(
            f"🎓 Auto-trained on {trained}/{len(batch)} samples, "
            f"total_reward={total_reward:.2f}, "
            f"episodes={self.model.q_model.episodes}"
        )

    def _get_market_state(self) -> Optional[MarketState]:
        """Coleta estado atual do mercado"""
        try:
            # Preço
            price = get_price_fast(self.symbol, timeout=2)
            if price is None:
                logger.warning("⚠️ Price unavailable")
                return None
            
            # Order book
            ob_analysis = analyze_orderbook(self.symbol)
            
            # Trade flow
            flow_analysis = analyze_trade_flow(self.symbol)
            
            # Indicadores do modelo
            self.model.indicators.update(price)
            rsi = self.model.indicators.rsi()
            momentum = self.model.indicators.momentum()
            volatility = self.model.indicators.volatility()
            trend = self.model.indicators.trend()
            
            state = MarketState(
                price=price,
                bid=ob_analysis.get("bid_volume", 0),
                ask=ob_analysis.get("ask_volume", 0),
                spread=ob_analysis.get("spread", 0),
                orderbook_imbalance=ob_analysis.get("imbalance", 0),
                trade_flow=flow_analysis.get("flow_bias", 0),
                volume_ratio=flow_analysis.get("total_volume", 1),
                rsi=rsi,
                momentum=momentum,
                volatility=volatility,
                trend=trend
            )
            
            # Registrar estado (incluindo bid/ask/spread/volume do orderbook)
            self.db.record_market_state(
                symbol=self.symbol,
                price=price,
                bid=state.bid,
                ask=state.ask,
                spread=state.spread,
                volume=state.volume_ratio,
                orderbook_imbalance=state.orderbook_imbalance,
                trade_flow=state.trade_flow,
                rsi=rsi,
                momentum=momentum,
                volatility=volatility,
                trend=trend
            )
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Error getting market state: {e}")
            return None
    
    def _check_can_trade(self, signal: Signal) -> bool:
        """Verifica se pode executar trade — controlado pela IA via RAG.

        Os parâmetros de gating (confiança mínima, cooldown, preço alvo)
        são calculados dinamicamente pelo MarketRAG baseado no regime
        de mercado detectado, ao invés de valores fixos no config.
        """
        # ── Obter parâmetros da IA (RAG) ou usar fallback do config ──
        rag_adj = self.market_rag.get_current_adjustment()
        controls = self._resolve_trade_controls(rag_adj)
        ai_controlled = controls.ai_controlled

        context = self._analyze_signal_context(rag_adj, signal)
        min_confidence = controls.min_confidence
        min_interval = controls.min_trade_interval

        if signal.action == "BUY":
            min_confidence = min(0.92, min_confidence + min(context["penalty_score"] * 0.02, 0.10))
            if context["bonus_score"] >= 2.0:
                min_confidence = max(0.45, min_confidence - 0.02)
            if context["strong_bearish"]:
                min_interval = int(min_interval * 1.20)
        elif signal.action == "SELL" and context["strong_bearish"]:
            min_confidence = max(0.45, min_confidence - 0.05)

        # ── Intervalo mínimo (cooldown dinâmico) ──
        elapsed = time.time() - self.state.last_trade_time
        if elapsed < min_interval:
            logger.debug(
                f"⏳ Trade cooldown: {min_interval - elapsed:.0f}s remaining "
                f"(AI: {min_interval}s)"
            )
            return False

        # ── Confiança mínima (dinâmica pela IA) ──
        if signal.confidence < min_confidence:
            logger.debug(
                f"📉 Low confidence: {signal.confidence:.1%} < {min_confidence:.1%} "
                f"({'AI+' + controls.ollama_mode if ai_controlled else 'config'})"
            )
            return False

        # ── Preço alvo de compra (calculado pela IA) ──
        if signal.action == "BUY":
            if context["hard_block_buy"]:
                logger.info(
                    f"🧱 BUY blocked (context penalty): net={context['net_score']:.2f} "
                    f"penalties={','.join(context['penalties']) or '-'} "
                    f"bonuses={','.join(context['bonuses']) or '-'}"
                )
                return False
            ai_buy_target = rag_adj.ai_buy_target_price
            extra_discount_pct = self._get_buy_extra_discount_pct(rag_adj, signal)
            effective_buy_target = ai_buy_target * (1 - extra_discount_pct) if ai_buy_target > 0 else 0
            tolerance_pct = 0.0
            if extra_discount_pct <= 0:
                tolerance_pct = self._get_buy_target_tolerance_pct(rag_adj, signal)
            effective_buy_ceiling = effective_buy_target * (1 + tolerance_pct) if effective_buy_target > 0 else 0
            if effective_buy_target > 0 and signal.price > effective_buy_ceiling:
                diff_pct = ((signal.price - effective_buy_target) / effective_buy_target) * 100
                if extra_discount_pct > 0:
                    logger.info(
                        f"🔒 BUY blocked (bearish filter): preço ${signal.price:,.2f} > "
                        f"alvo defensivo ${effective_buy_target:,.2f} (+{diff_pct:.2f}%) "
                        f"[base ${ai_buy_target:,.2f}, desconto {extra_discount_pct*100:.2f}%] — "
                        f"{rag_adj.ai_buy_target_reason}"
                    )
                else:
                    logger.info(
                        f"🔒 BUY blocked (AI target): preço ${signal.price:,.2f} > "
                        f"alvo ${effective_buy_target:,.2f} (+{diff_pct:.2f}%) "
                        f"[tol {tolerance_pct*100:.2f}%] — "
                        f"{rag_adj.ai_buy_target_reason}"
                    )
                return False
            elif effective_buy_target > 0 and signal.price <= effective_buy_ceiling:
                target_label = (
                    f"alvo defensivo ${effective_buy_target:,.2f}"
                    if extra_discount_pct > 0 else
                    f"alvo ${effective_buy_target:,.2f}"
                )
                if tolerance_pct > 0 and signal.price > effective_buy_target:
                    target_label += f" + tolerância {tolerance_pct*100:.2f}%"
                logger.info(
                    f"🔓 BUY permitido pela IA: preço ${signal.price:,.2f} <= "
                    f"{target_label} ({rag_adj.ai_buy_target_reason})"
                )
                self.state.last_sell_entry_price = 0.0

        # ── Multi-posição: verificar se atingiu limite de entradas ──
        max_positions = controls.effective_max_positions
        if signal.action == "BUY" and self.state.position_count >= max_positions:
            logger.info(
                f"📦 Max positions reached ({self.state.position_count}/{max_positions}) "
                f"[entries:{rag_adj.ai_max_entries}, cap:{controls.max_positions_cap}, mode:{controls.ollama_mode}]"
            )
            return False

        if signal.action == "SELL" and self.state.position <= 0:
            logger.debug("📭 No position to sell")
            return False

        # ── Trava: Target de Lucro por Cota (IA) ou fallback min_sell_pnl ──
        if signal.action == "SELL" and self.state.position > 0 and self.state.entry_price > 0:
            # Reconciliar com o ajuste mais recente do RAG no exato momento da decisão.
            # Isso evita bloquear SELL com target restaurado/obsoleto quando a IA já
            # recalibrou para um TP mais defensivo em background.
            self._sync_target_sell_with_ai("IA/venda")
            if self.state.target_sell_price > 0:
                # ── Novo gate: target_sell_price da IA ──
                if signal.price < self.state.target_sell_price:
                    # Preço abaixo do target — verificar confiança
                    sell_conf_threshold = self._get_sell_below_target_confidence(
                        rag_adj, ai_controlled, signal
                    )
                    if signal.confidence >= sell_conf_threshold:
                        logger.info(
                            f"⚡ SELL below target allowed: confidence {signal.confidence:.0%} "
                            f"≥ {sell_conf_threshold:.0%} "
                            f"(${signal.price:,.2f} < target ${self.state.target_sell_price:,.2f})"
                        )
                    else:
                        pct_to_target = ((self.state.target_sell_price / signal.price) - 1) * 100
                        logger.info(
                            f"🎯 SELL blocked by target: ${signal.price:,.2f} < "
                            f"target ${self.state.target_sell_price:,.2f} (+{pct_to_target:.2f}% away) "
                            f"| conf={signal.confidence:.0%} < {sell_conf_threshold:.0%} "
                            f"| reason: {self.state.target_sell_reason}"
                        )
                        return False
            else:
                # ── Fallback: min_sell_pnl para posições legacy sem target ──
                min_sell_pnl = _config.get("min_sell_pnl", 0.015)
                estimated_pnl = (signal.price - self.state.entry_price) * self.state.position
                sell_fee = signal.price * self.state.position * TRADING_FEE_PCT
                buy_fee = self.state.entry_price * self.state.position * TRADING_FEE_PCT
                net_pnl = estimated_pnl - sell_fee - buy_fee
                if net_pnl < min_sell_pnl:
                    logger.info(
                        f"🔒 SELL blocked (legacy): net PnL ${net_pnl:.4f} < min ${min_sell_pnl:.3f} "
                        f"(entry ${self.state.entry_price:,.2f} → ${signal.price:,.2f})"
                    )
                    return False

        # ── Limite diário de trades (config: max_daily_trades) ──
        max_daily = _config.get("max_daily_trades", 10)
        if signal.action == "BUY":  # Só limitar BUYs (SELLs devem poder fechar posição)
            try:
                today_start = time.time() - (time.time() % 86400)  # Início do dia UTC
                today_trades = self.db.count_trades_since(
                    symbol=self.symbol, since=today_start, dry_run=self.state.dry_run,
                    profile=self._current_profile()
                )
                if today_trades >= max_daily * 2:  # *2 porque cada ciclo = buy+sell
                    logger.info(f"🚫 Daily trade limit reached: {today_trades} trades today (max {max_daily} cycles)")
                    return False
            except Exception as e:
                logger.debug(f"Daily limit check error: {e}")
        
        # ── Limite diário de perda (config: max_daily_loss) ──
        max_daily_loss = _config.get("max_daily_loss", 150)
        if signal.action == "BUY":
            try:
                today_start = time.time() - (time.time() % 86400)
                today_pnl = self.db.get_pnl_since(
                    symbol=self.symbol, since=today_start, dry_run=self.state.dry_run,
                    profile=self._current_profile()
                )
                if today_pnl < -max_daily_loss:
                    logger.warning(f"🛑 Daily loss limit reached: ${today_pnl:.2f} (max -${max_daily_loss})")
                    return False
            except Exception as e:
                logger.debug(f"Daily loss check error: {e}")
        
        return True
    

    def _apply_profile_allocation(self, total_balance: float) -> float:
        """Aplica alocação de saldo baseada no perfil.

        Lê a última alocação da tabela btc.profile_allocations.
        Retorna o saldo alocado para o perfil deste agente.
        """
        profile = self._current_profile()
        if profile == "default":
            return total_balance

        try:
            with self.db._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT conservative_pct, aggressive_pct
                    FROM btc.profile_allocations
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (self.symbol,))
                row = cur.fetchone()
                if row:
                    cons_pct, aggr_pct = row
                    my_pct = cons_pct if profile == "conservative" else aggr_pct
                    allocated = total_balance * my_pct
                    logger.debug(
                        f"Profile allocation: {profile} gets "
                        f"{my_pct*100:.0f}% of ${total_balance:.2f} = ${allocated:.2f}"
                    )
                    return allocated
        except Exception as e:
            logger.warning(f"Profile allocation lookup failed: {e}")

        # Fallback: split 50/50
        return total_balance * 0.5

    def _calculate_trade_size(self, signal: Signal, price: float, force: bool = False) -> float:
        """Calcula tamanho do trade.

        Args:
            signal: Sinal de trading (BUY/SELL)
            price: Preço atual
            force: Se True, bypass fee-check (usado por auto-exit SL/TP)
        """
        if signal.action == "BUY":
            caps = self._get_runtime_risk_caps()
            usdt_balance = get_balance("USDT") if not self.state.dry_run else 1000
            # Profile allocation: aplicar % do saldo alocado ao perfil
            usdt_balance = self._apply_profile_allocation(usdt_balance)
            rag_adj = self.market_rag.get_current_adjustment()
            controls = self._resolve_trade_controls(rag_adj)
            ai_controlled = controls.ai_controlled
            max_positions = controls.effective_max_positions
            # Verificar entradas restantes
            remaining_entries = max_positions - self.state.position_count
            if remaining_entries <= 0:
                return 0

            # AI-controlled sizing: a IA define % do saldo por entrada
            if ai_controlled:
                ai_size_pct = rag_adj.ai_position_size_pct
                max_amount = usdt_balance * ai_size_pct
                context = self._analyze_signal_context(rag_adj, signal)
                size_multiplier = 1.0
                if context["penalty_score"] > 0:
                    size_multiplier *= max(0.50, 1.0 - context["penalty_score"] * 0.07)
                if context["bonus_score"] >= 2.0:
                    size_multiplier *= 1.03
                max_amount *= size_multiplier
                logger.debug(
                    f"💰 AI sizing: {ai_size_pct*100:.1f}% de ${usdt_balance:.2f} "
                    f"= ${max_amount:.2f} ({rag_adj.ai_position_size_reason}; "
                    f"ctx_pen={context['penalty_score']:.2f}, ctx_bonus={context['bonus_score']:.2f})"
                )
            else:
                # Fallback: dividir igualmente (sem histórico suficiente)
                per_entry_pct = controls.max_position_pct / max_positions
                max_amount = usdt_balance * per_entry_pct

            open_exposure = max(self.state.position * price, 0.0)
            exposure_base = max(usdt_balance + open_exposure, 0.0)
            max_total_exposure = exposure_base * controls.max_position_pct
            remaining_exposure = max(max_total_exposure - open_exposure, 0.0)
            if remaining_exposure <= 0:
                logger.info(
                    f"🧱 BUY blocked (max exposure): open=${open_exposure:.2f} "
                    f">= cap=${max_total_exposure:.2f} ({controls.max_position_pct*100:.1f}%)"
                )
                return 0
            max_amount = min(max_amount, remaining_exposure)

            # Escalar pelo confidence
            amount = max_amount * signal.confidence
            min_trade_amount = caps["min_trade_amount"]
            if amount < min_trade_amount:
                logger.info(
                    f"📏 BUY floored to min trade: AI size ${amount:.2f} -> "
                    f"${min_trade_amount:.2f} (max ${max_amount:.2f}, conf={signal.confidence:.1%})"
                )
                amount = min_trade_amount

            return min(amount, remaining_exposure, usdt_balance * 0.95)  # Deixar margem
        
        elif signal.action == "SELL":
            size = self.state.position
            if size <= 0:
                return 0

            # Auto-exit (SL/TP) bypasses fee check — always sell
            if force:
                return self.state.position

            # Fee check: estimar taxas antes de enviar ordem de venda
            gross_sell = price * size
            sell_fee = gross_sell * TRADING_FEE_PCT
            buy_fee_approx = self.state.entry_price * size * TRADING_FEE_PCT
            total_fees = sell_fee + buy_fee_approx

            pnl = (price - self.state.entry_price) * size
            net_profit = pnl - total_fees

            # Min net profit: lucro líquido mínimo (após fees)
            mnp_cfg = _config.get("min_net_profit", {"usd": 0.01, "pct": 0.0005})
            min_usd = mnp_cfg.get("usd", 0.01)
            min_pct_val = gross_sell * mnp_cfg.get("pct", 0.0005)
            min_required = max(min_usd, min_pct_val)

            # Se lucro positivo mas líquido < mínimo: LOG mas PERMITIR a venda
            # (antes bloqueava, o que prendia posições indefinidamente)
            stop_loss_pct = _config.get("stop_loss_pct", 0.02)
            stop_loss_price = self.state.entry_price * (1 - stop_loss_pct)
            if pnl > 0 and net_profit < min_required and price > stop_loss_price:
                logger.info(
                    f"ℹ️ SELL with low net profit ${net_profit:.4f} < min ${min_required:.4f} "
                    f"(gross ${pnl:.4f}, fees ${total_fees:.4f}) — proceeding anyway"
                )
                # Previously returned 0 here — BUG FIX: allow the sell

            # Vender posicao inteira
            return self.state.position
        
        return 0
    
    def _execute_trade(self, signal: Signal, price: float, force: bool = False) -> bool:
        """Executa trade.

        Args:
            force: bypass fee-check (used by auto-exit SL/TP)
        """
        with self._trade_lock:
            try:
                if signal.action == "BUY":
                    amount_usdt = self._calculate_trade_size(signal, price)
                    min_trade_amount = self._get_runtime_risk_caps()["min_trade_amount"]
                    if amount_usdt < min_trade_amount:
                        logger.warning(f"⚠️ Trade amount too small: ${amount_usdt:.2f}")
                        return False
                    order_id = None
                    trade_metadata = None

                    if self.state.dry_run:
                        # Simulação (desconta fee como no trade real)
                        size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                        logger.info(f"🔵 [DRY] BUY #{self.state.position_count+1} {size:.6f} BTC @ ${price:,.2f} (${amount_usdt:.2f}, fee={TRADING_FEE_PCT*100:.1f}%)")
                    else:
                        # Trade real
                        result = place_market_order(self.symbol, "buy", funds=amount_usdt)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        order_id = result.get("orderId")
                        if order_id:
                            trade_metadata = {"source": "kucoin_live", "orderId": order_id}
                        
                        # Atualizar posição (aproximado)
                        size = amount_usdt / price * (1 - TRADING_FEE_PCT)
                        logger.info(f"🟢 BUY #{self.state.position_count+1} {size:.6f} BTC @ ${price:,.2f}")
                    
                    # Multi-posição: acumular com preço médio ponderado
                    old_pos = self.state.position
                    old_entry = self.state.entry_price
                    self.state.position += size
                    if old_pos > 0 and old_entry > 0:
                        self.state.entry_price = (old_pos * old_entry + size * price) / self.state.position
                    else:
                        self.state.entry_price = price
                    self.state.position_count += 1
                    self.state.entries.append({"price": price, "size": size, "ts": time.time()})
                    
                    logger.info(f"📊 Position: {self.state.position:.6f} BTC ({self.state.position_count} entries, avg ${self.state.entry_price:,.2f})")
                    
                    # ── Target de Lucro por Cota (IA) ──
                    rag_adj = self.market_rag.get_current_adjustment()
                    ai_tp = rag_adj.ai_take_profit_pct
                    # Aplicar floor mínimo (config auto_take_profit.min_pct)
                    _atp_cfg = _config.get("auto_take_profit", {})
                    _min_tp = _atp_cfg.get("min_pct", 0.015)
                    if ai_tp < _min_tp:
                        ai_tp = _min_tp
                    old_target = self.state.target_sell_price
                    tp_target = self.state.entry_price * (1 + ai_tp)
                    self.state.target_sell_price = tp_target
                    self.state.target_sell_reason = rag_adj.ai_take_profit_reason
                    if old_target > 0 and self.state.position_count > 1:
                        logger.info(
                            f"🔄 Target SELL recalculado: ${old_target:,.2f} → "
                            f"${tp_target:,.2f} (+{ai_tp*100:.2f}%) [DCA #{self.state.position_count}]"
                        )
                    else:
                        logger.info(
                            f"🎯 Target SELL fixado: ${tp_target:,.2f} "
                            f"(+{ai_tp*100:.2f}% sobre avg ${self.state.entry_price:,.2f}) "
                            f"— {rag_adj.ai_take_profit_reason}"
                        )
                    
                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        order_id=order_id,
                        dry_run=self.state.dry_run,
                        metadata=trade_metadata,
                        profile=self._current_profile()
                    )
                    self._last_trade_id = trade_id  # FIX #7: Salvar trade_id real
                    # FIX #1: Reset trailing high on new position
                    self.state.trailing_high = price
                    
                elif signal.action == "SELL":
                    # Use _calculate_trade_size for fee check (force bypasses)
                    size = self._calculate_trade_size(signal, price, force=force)
                    if size <= 0:
                        return False
                    order_id = None
                    trade_metadata = None

                    # Calcular PnL líquido (descontando fees de compra e venda)
                    gross_pnl = (price - self.state.entry_price) * size
                    sell_fee = price * size * TRADING_FEE_PCT
                    buy_fee = self.state.entry_price * size * TRADING_FEE_PCT
                    pnl = gross_pnl - sell_fee - buy_fee
                    net_sell_price = price * (1 - TRADING_FEE_PCT)
                    net_buy_price = self.state.entry_price * (1 + TRADING_FEE_PCT)
                    pnl_pct = ((net_sell_price / net_buy_price) - 1) * 100 if net_buy_price > 0 else 0
                    
                    if self.state.dry_run:
                        logger.info(f"🔴 [DRY] SELL {size:.6f} BTC @ ${price:,.2f} "
                                  f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}% net, fees=${sell_fee+buy_fee:.4f})")
                    else:
                        result = place_market_order(self.symbol, "sell", size=size)
                        if not result.get("success"):
                            logger.error(f"❌ Order failed: {result}")
                            return False
                        order_id = result.get("orderId")
                        if order_id:
                            trade_metadata = {"source": "kucoin_live", "orderId": order_id}
                        logger.info(f"🔴 SELL {size:.6f} BTC @ ${price:,.2f} "
                                  f"(PnL: ${pnl:.2f} / {pnl_pct:.2f}% net, fees=${sell_fee+buy_fee:.4f})")
                    
                    # Registrar
                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        funds=round(price * size, 2),  # FIX #9: Record sell funds
                        order_id=order_id,
                        dry_run=self.state.dry_run,
                        metadata=trade_metadata,
                        profile=self._current_profile()
                    )
                    self.db.update_trade_pnl(trade_id, pnl, pnl_pct)
                    self._last_trade_id = trade_id  # FIX #7: Salvar trade_id real
                    
                    # Atualizar estado
                    self.state.total_pnl += pnl
                    if pnl > 0:
                        self.state.winning_trades += 1
                    
                    # Trava de recompra: salvar preço de entrada antes de zerar
                    self.state.last_sell_entry_price = self.state.entry_price
                    logger.info(
                        f"🔒 Rebuy lock set: next BUY only when price < "
                        f"${self.state.entry_price:,.2f}"
                    )
                    
                    self.state.position = 0
                    self.state.entry_price = 0
                    self.state.position_count = 0
                    self.state.entries = []
                    self.state.target_sell_price = 0.0
                    self.state.target_sell_reason = ""
                
                # Atualizar estado
                self.state.total_trades += 1
                self.state.daily_trades += 1  # FIX #4: Daily counter
                self.state.last_trade_time = time.time()
                
                # Callbacks
                for cb in self._on_trade_callbacks:
                    try:
                        cb(signal, price)
                    except Exception as e:
                        logger.warning(f"⚠️ Trade callback error: {e}")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Trade execution error: {e}")
                return False
    

    def _check_trailing_stop(self, price: float) -> bool:
        """FIX #1: Trailing stop implementation.
        Activates when price rises activation_pct above entry,
        then triggers SELL if price drops trail_pct from the high.
        Returns True if a trailing stop exit was executed."""
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = self.config

        ts_cfg = live_cfg.get("trailing_stop", {})
        if not ts_cfg.get("enabled", False):
            return False

        activation_pct = ts_cfg.get("activation_pct", 0.015)  # 1.5%
        trail_pct = ts_cfg.get("trail_pct", 0.008)  # 0.8%

        # Update trailing high
        if price > self.state.trailing_high:
            self.state.trailing_high = price

        # Check if activation threshold was reached
        pnl_pct = (self.state.trailing_high / self.state.entry_price) - 1
        if pnl_pct < activation_pct:
            return False  # Not yet activated

        # Trailing stop activated — check if price dropped from high
        drop_from_high = (self.state.trailing_high - price) / self.state.trailing_high
        if drop_from_high >= trail_pct:
            net_pnl_pct = (price / self.state.entry_price) - 1
            logger.warning(
                f"📉 TRAILING STOP triggered! High=${self.state.trailing_high:,.2f}, "
                f"now=${price:,.2f} (drop={drop_from_high*100:.2f}% >= trail={trail_pct*100:.1f}%), "
                f"net PnL={net_pnl_pct*100:.2f}% from entry ${self.state.entry_price:,.2f}"
            )
            forced_signal = Signal(
                action="SELL", confidence=1.0,
                reason=f"TRAILING_STOP (drop {drop_from_high*100:.2f}% from ${self.state.trailing_high:,.2f})",
                price=price, features={}
            )
            self.state.last_trade_time = 0  # bypass cooldown
            result = self._execute_trade(forced_signal, price, force=True)
            # FIX #15: Registrar decision para trailing stop
            if result:
                try:
                    dec_id = self.db.record_decision(
                        symbol=self.symbol, action="SELL", confidence=1.0,
                        price=price, reason=forced_signal.reason,
                        profile=self._current_profile(),
                        features={"trigger": "trailing_stop", "trailing_high": round(self.state.trailing_high, 2), "drop_pct": round(drop_from_high * 100, 2)}
                    )
                    self.db.mark_decision_executed(dec_id, getattr(self, '_last_trade_id', 0))
                except Exception as e:
                    logger.debug(f"Decision log error: {e}")
            return result

        return False

    def _check_auto_exit(self, price: float) -> bool:
        """Verifica auto stop-loss e take-profit dinâmico (IA).

        O take-profit é calculado dinamicamente pelo MarketRAG a cada
        recalibração (~5min), baseado em regime, volatilidade, momentum
        e padrões históricos. O valor do config.json é usado apenas como
        fallback quando a IA não tem dados suficientes.

        Returns:
            True se uma saída forçada foi executada.
        """
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return False

        # Reload config each cycle for hot-toggle via Grafana
        try:
            live_cfg = self._load_live_config()
        except Exception:
            live_cfg = self.config

        auto_sl = live_cfg.get("auto_stop_loss", {})
        auto_tp = live_cfg.get("auto_take_profit", {})

        sl_enabled = auto_sl.get("enabled", False)
        tp_enabled = auto_tp.get("enabled", False)

        if not sl_enabled and not tp_enabled:
            return False

        pnl_pct = (price / self.state.entry_price) - 1  # e.g. -0.02 = -2%

        # Stop-Loss check
        if sl_enabled:
            sl_pct = auto_sl.get("pct", 0.02)
            if pnl_pct <= -sl_pct:
                logger.warning(
                    f"🛑 AUTO STOP-LOSS triggered! "
                    f"Price ${price:,.2f} is {pnl_pct*100:.2f}% below entry ${self.state.entry_price:,.2f} "
                    f"(threshold: -{sl_pct*100:.1f}%)"
                )
                forced_signal = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_STOP_LOSS ({pnl_pct*100:.2f}%)",
                    price=price, features={}
                )
                self.state.last_trade_time = 0  # bypass cooldown
                result = self._execute_trade(forced_signal, price, force=True)
                # FIX #15: Registrar decision para auto-exit
                if result:
                    try:
                        dec_id = self.db.record_decision(
                            symbol=self.symbol, action="SELL", confidence=1.0,
                            price=price, reason=forced_signal.reason,
                            profile=self._current_profile(),
                            features={"trigger": "auto_stop_loss", "pnl_pct": round(pnl_pct * 100, 2)}
                        )
                        self.db.mark_decision_executed(dec_id, getattr(self, '_last_trade_id', 0))
                    except Exception as e:
                        logger.debug(f"Decision log error: {e}")
                return result

        # Take-Profit check — TP dinâmico da IA com fallback ao config
        if tp_enabled:
            rag_adj = self.market_rag.get_current_adjustment()
            ai_has_data = rag_adj.similar_count >= 3

            if ai_has_data:
                tp_pct = rag_adj.ai_take_profit_pct
                tp_source = f"AI:{rag_adj.ai_take_profit_reason}"
            else:
                tp_pct = auto_tp.get("pct", 0.025)
                tp_source = "config_fallback"

            # FIX #14: Floor mínimo para TP — IA não pode sugerir TP muito baixo
            min_tp_pct = auto_tp.get("min_pct", 0.015)
            if tp_pct < min_tp_pct:
                logger.debug(
                    f"📏 TP floor applied: AI suggested {tp_pct*100:.2f}%, "
                    f"using min {min_tp_pct*100:.2f}%"
                )
                tp_pct = min_tp_pct
                tp_source += f" (floored to {min_tp_pct*100:.1f}%)"

            if pnl_pct >= tp_pct:
                target_price = self.state.entry_price * (1 + tp_pct)
                logger.info(
                    f"🎯 AUTO TAKE-PROFIT triggered! "
                    f"Price ${price:,.2f} is +{pnl_pct*100:.2f}% above entry ${self.state.entry_price:,.2f} "
                    f"(threshold: +{tp_pct*100:.2f}% = ${target_price:,.2f}, source: {tp_source})"
                )
                forced_signal = Signal(
                    action="SELL", confidence=1.0,
                    reason=f"AUTO_TAKE_PROFIT (+{pnl_pct*100:.2f}%, TP={tp_pct*100:.2f}% [{tp_source}])",
                    price=price, features={}
                )
                self.state.last_trade_time = 0  # bypass cooldown
                result = self._execute_trade(forced_signal, price, force=True)
                # FIX #15: Registrar decision para auto-exit
                if result:
                    try:
                        dec_id = self.db.record_decision(
                            symbol=self.symbol, action="SELL", confidence=1.0,
                            price=price, reason=forced_signal.reason,
                            profile=self._current_profile(),
                            features={"trigger": "auto_take_profit", "pnl_pct": round(pnl_pct * 100, 2), "tp_pct": round(tp_pct * 100, 2), "tp_source": tp_source}
                        )
                        self.db.mark_decision_executed(dec_id, getattr(self, '_last_trade_id', 0))
                    except Exception as e:
                        logger.debug(f"Decision log error: {e}")
                return result

        return False

    def _write_heartbeat(self):
        """Escreve arquivo de heartbeat para detecção de stall pelo self-healer"""
        try:
            # Use symbol from config or env
            symbol_safe = self.symbol.replace("-", "_").replace(".", "_").upper()
            heartbeat_file = Path(f"/tmp/crypto_agent_{symbol_safe}_heartbeat")
            heartbeat_file.write_text(str(time.time()))
        except Exception as e:
            logger.debug(f"Heartbeat write error: {e}")

    def _run_loop(self):
        """Loop principal do agente"""
        logger.info("🚀 Starting trading loop...")
        
        cycle = 0
        while not self._stop_event.is_set():
            try:
                cycle += 1
                start_time = time.time()
                
                # Coletar estado do mercado
                market_state = self._get_market_state()
                if market_state is None:
                    time.sleep(POLL_INTERVAL)
                    continue
                
                # Atualizar valor da posição
                if self.state.position > 0:
                    self.state.position_value = self.state.position * market_state.price
                
                # Check trailing stop FIRST, then auto SL/TP
                if self.state.position > 0:
                    if self._check_trailing_stop(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue
                    if self._check_auto_exit(market_state.price):
                        time.sleep(POLL_INTERVAL)
                        continue
                
                # ===== MARKET RAG: alimentar e aplicar ajustes =====
                try:
                    self.market_rag.feed_snapshot(
                        price=market_state.price,
                        indicators=self.model.indicators,
                        ob_analysis={
                            "imbalance": market_state.orderbook_imbalance,
                            "spread": market_state.spread,
                            "bid_volume": market_state.bid,
                            "ask_volume": market_state.ask,
                        },
                        flow_analysis={
                            "flow_bias": market_state.trade_flow,
                            "buy_volume": 0,
                            "sell_volume": 0,
                            "total_volume": market_state.volume_ratio,
                        },
                    )
                    # Aplicar ajuste de regime do RAG a cada 60 ciclos (~5min)
                    self._rag_apply_cycle += 1
                    if self._rag_apply_cycle % 60 == 0:
                        rag_adj = self.market_rag.get_current_adjustment()
                        self.model.apply_rag_adjustment(rag_adj)

                    # Atualizar contexto de trading para sizing dinâmico da IA
                    if self._rag_apply_cycle % 30 == 0:  # ~2.5min
                        usdt_bal = get_balance("USDT") if not self.state.dry_run else 1000
                        risk_caps = self._get_runtime_risk_caps()
                        self.market_rag.set_trading_context(
                            avg_entry_price=self.state.entry_price,
                            position_count=self.state.position_count,
                            usdt_balance=usdt_bal,
                            max_position_pct=risk_caps["max_position_pct"],
                            max_positions=risk_caps["max_positions"],
                            profile=self._current_profile(),
                        )

                    self._sync_target_sell_with_ai("IA")
                except Exception as e:
                    logger.debug(f"RAG feed error: {e}")
                
                # Gerar sinal
                explore = (cycle % 10 == 0)  # Explorar a cada 10 ciclos
                signal = self.model.predict(market_state, explore=explore)
                
                # Registrar decisão
                decision_id = self.db.record_decision(
                    symbol=self.symbol,
                    action=signal.action,
                    confidence=signal.confidence,
                    price=signal.price,
                    reason=signal.reason,
                    profile=self._current_profile(),
                    features=signal.features
                )
                
                # Callbacks
                for cb in self._on_signal_callbacks:
                    try:
                        cb(signal)
                    except Exception as e:
                        logger.warning(f"⚠️ Signal callback error: {e}")
                
                # Verificar se deve executar
                if signal.action != "HOLD" and self._check_can_trade(signal):
                    executed = self._execute_trade(signal, market_state.price)
                    if executed:
                        self.db.mark_decision_executed(decision_id, getattr(self, '_last_trade_id', self.state.total_trades))
                
                # Log periódico
                if cycle % 60 == 0:  # A cada ~5 minutos
                    pos_info = (f"Position: {self.state.position:.6f} BTC ({self.state.position_count} entries, avg ${self.state.entry_price:,.2f})"
                                if self.state.position > 0 else "No position")
                    rag_stats = self.market_rag.get_stats()
                    rag_info = (
                        f" | RAG: {rag_stats['current_regime']} "
                        f"({rag_stats['regime_confidence']:.0%}), "
                        f"snaps={rag_stats['store_size']}"
                    )
                    # AI gating info
                    rag_adj = self.market_rag.get_current_adjustment()
                    controls = self._resolve_trade_controls(rag_adj)
                    ai_tp_target = (
                        f"${self.state.entry_price * (1 + rag_adj.ai_take_profit_pct):,.2f}"
                        if self.state.position > 0 and self.state.entry_price > 0
                        else "N/A"
                    )
                    target_info = (
                        f", SELL_TARGET=${self.state.target_sell_price:,.2f}"
                        if self.state.target_sell_price > 0 else ""
                    )
                    ai_info = (
                        f" | AI: conf≥{controls.min_confidence:.0%}, "
                        f"cd={controls.min_trade_interval}s, "
                        f"target=${rag_adj.ai_buy_target_price:,.2f}, "
                        f"TP={rag_adj.ai_take_profit_pct*100:.2f}%→{ai_tp_target}{target_info}, "
                        f"sizing={rag_adj.ai_position_size_pct*100:.1f}%×{rag_adj.ai_max_entries}, "
                        f"risk_cap={controls.max_position_pct*100:.1f}%/{controls.effective_max_positions}, "
                        f"aggr={rag_adj.ai_aggressiveness:.0%}, "
                        f"ollama={controls.ollama_mode}"
                    )
                    logger.info(f"📊 Cycle {cycle} | ${market_state.price:,.2f} | "
                              f"{pos_info} | PnL: ${self.state.total_pnl:.2f}{rag_info}{ai_info}")
                    
                    # Salvar modelo
                    self.model.save()
                
                # Gerar plano da IA via Ollama:
                # - após warm-up
                # - periodicamente
                # - imediatamente quando entrar RSS novo relevante
                periodic_plan = cycle == 5 or (cycle > 0 and cycle % self._AI_PLAN_INTERVAL == 0)
                rss_triggered_plan = self._has_new_rss_since_last_plan()
                rag_stats = self.market_rag.get_stats()
                regime_now = rag_stats.get("current_regime", "")
                regime_changed = bool(self._last_ai_trade_controls_regime and regime_now and regime_now != self._last_ai_trade_controls_regime)
                should_generate_plan = periodic_plan or rss_triggered_plan
                if should_generate_plan and (time.time() - self._last_ai_plan_trigger_ts) >= 20:
                    self._last_ai_plan_trigger_ts = time.time()
                    if rss_triggered_plan and not periodic_plan:
                        logger.info("📰 New RSS received — triggering fresh AI plan")
                    threading.Thread(
                        target=self._generate_ai_plan,
                        args=(market_state,),
                        daemon=True,
                    ).start()

                controls_trigger = ""
                if periodic_plan:
                    controls_trigger = "periodic"
                elif rss_triggered_plan:
                    controls_trigger = "rss"
                elif regime_changed:
                    controls_trigger = "regime_change"

                if controls_trigger and (time.time() - self._last_ai_trade_controls_trigger_ts) >= self._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC:
                    self._last_ai_trade_controls_trigger_ts = time.time()
                    if controls_trigger == "regime_change":
                        logger.info(
                            f"🧭 Market regime changed {self._last_ai_trade_controls_regime or '-'} → {regime_now} — refreshing AI trade controls"
                        )
                    elif controls_trigger == "rss":
                        logger.info("📰 New RSS received — refreshing AI trade controls")
                    threading.Thread(
                        target=self._generate_ai_trade_controls,
                        args=(market_state, controls_trigger),
                        daemon=True,
                    ).start()
                if regime_now:
                    self._last_ai_trade_controls_regime = regime_now

                # Heartbeat write (for self-healing watchdog detection)
                self._write_heartbeat()
                
                # Sleep
                elapsed = time.time() - start_time
                sleep_time = max(POLL_INTERVAL - elapsed, 0.1)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"❌ Loop error: {e}")
                time.sleep(POLL_INTERVAL)
        
        logger.info("🛑 Trading loop stopped")
    
    def start(self):
        """Inicia o agente"""
        if self.state.running:
            logger.warning("⚠️ Agent already running")
            return
        
        self.state.running = True
        self._stop_event.clear()
        
        # Bootstrap: restaurar posição, coletar dados, auto-treinar
        self._startup_bootstrap()
        
        # Iniciar Market RAG (thread de inteligência de mercado)
        try:
            self.market_rag.start()
            logger.info("🧠 Market RAG started")
        except Exception as e:
            logger.warning(f"⚠️ Market RAG start failed (non-critical): {e}")

        # Forçar primeiro contexto de trading e snapshot para IA operar desde o início
        try:
            usdt_bal = get_balance("USDT") if not self.state.dry_run else 1000
            risk_caps = self._get_runtime_risk_caps()
            self.market_rag.set_trading_context(
                avg_entry_price=self.state.entry_price,
                position_count=self.state.position_count,
                usdt_balance=usdt_bal,
                max_position_pct=risk_caps["max_position_pct"],
                max_positions=risk_caps["max_positions"],
                profile=self._current_profile(),
            )
            # Primeiro snapshot + recalibração para popular indicadores RAG
            price = get_price_fast(self.symbol, timeout=3)
            if price:
                ob = analyze_orderbook(self.symbol)
                flow = analyze_trade_flow(self.symbol)
                self.market_rag.feed_snapshot(
                    price=price,
                    indicators=self.model.indicators,
                    ob_analysis=ob,
                    flow_analysis=flow,
                )
                rag_adj = self.market_rag.force_recalibrate()
                self.model.apply_rag_adjustment(rag_adj)
                self._sync_target_sell_with_ai("IA/bootstrap")
                logger.info(
                    f"📊 Initial RAG context: regime={rag_adj.suggested_regime}, "
                    f"sizing={rag_adj.ai_position_size_pct*100:.1f}%×"
                    f"{rag_adj.ai_max_entries}, "
                    f"risk_cap={rag_adj.applied_max_position_pct*100:.1f}%/{rag_adj.applied_max_positions}, "
                    f"USDT=${usdt_bal:.2f}"
                )
        except Exception as e:
            logger.warning(f"⚠️ Initial RAG context failed (non-critical): {e}")

        # Limpar planos de IA degenerados do banco
        self._cleanup_garbage_plans()

        # Thread principal
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        
        logger.info("✅ Agent started")
    
    def stop(self):
        """Para o agente"""
        if not self.state.running:
            return
        
        logger.info("🛑 Stopping agent...")
        self._stop_event.set()
        self.state.running = False
        
        # Parar Market RAG
        try:
            self.market_rag.stop()
        except Exception as e:
            logger.debug(f"RAG stop error: {e}")
        
        # Salvar modelo
        self.model.save()
        
        # Snapshot de performance
        self.db.record_performance_snapshot(self.symbol)
        
        logger.info("✅ Agent stopped")
    
    def get_status(self) -> Dict:
        """Retorna status atual"""
        return {
            **self.state.to_dict(),
            "model_stats": self.model.get_stats(),
            "market_rag": self.market_rag.get_stats(),
            "uptime_hours": (time.time() - self.state.last_trade_time) / 3600 if self.state.last_trade_time else 0
        }
    
    def on_signal(self, callback):
        """Registra callback para novos sinais"""
        self._on_signal_callbacks.append(callback)
    
    def on_trade(self, callback):
        """Registra callback para trades executados"""
        self._on_trade_callbacks.append(callback)

# ====================== DAEMON MODE ======================
class AgentDaemon:
    """Daemon para executar agente em background"""
    
    def __init__(self, agent: BitcoinTradingAgent):
        self.agent = agent
        self._setup_signals()
    
    def _setup_signals(self):
        """Configura handlers de sinais"""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """Handler para sinais de sistema"""
        logger.info(f"📡 Received signal {signum}, stopping...")
        self.agent.stop()
        sys.exit(0)
    
    def run(self):
        """Executa daemon"""
        logger.info("🤖 Starting daemon mode...")
        self.agent.start()
        
        try:
            while self.agent.state.running:
                time.sleep(60)
                
                # Log status a cada minuto
                status = self.agent.get_status()
                logger.debug(f"Status: {json.dumps(status, indent=2)}")
                
        except KeyboardInterrupt:
            pass
        finally:
            self.agent.stop()

# ====================== CLI ======================
def main():
    parser = argparse.ArgumentParser(description="Bitcoin Trading Agent 24/7")
    parser.add_argument("--symbol", default=None, help="Trading pair (overrides config)")
    parser.add_argument("--config", default=None, help="Config file name (e.g. config_ETH_USDT.json)")
    parser.add_argument("--api-port", type=int, default=None, help="Engine API port")
    parser.add_argument("--metrics-port", type=int, default=None, help="Prometheus metrics port")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Dry run mode (no real trades)")
    parser.add_argument("--live", action="store_true",
                       help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon")
    
    args = parser.parse_args()
    
    # Set config file env var for multi-coin
    if args.config:
        os.environ["COIN_CONFIG_FILE"] = args.config
    
    # Load config to get symbol
    config_name = args.config or os.environ.get("COIN_CONFIG_FILE", "config.json")
    config_path = Path(__file__).parent / config_name
    _loaded_cfg = {}
    if config_path.exists():
        try:
            with open(config_path) as _f:
                _loaded_cfg = json.load(_f)
        except Exception:
            pass
    
    # Symbol: CLI overrides config, config overrides default
    if args.symbol is None:
        args.symbol = _loaded_cfg.get("symbol", "BTC-USDT")
    
    # API port env
    if args.api_port:
        os.environ["BTC_ENGINE_API_PORT"] = str(args.api_port)
    
    # Metrics port env
    if args.metrics_port:
        os.environ["METRICS_PORT"] = str(args.metrics_port)
    
    # Verificar credenciais para modo live
    dry_run = not args.live
    if not dry_run and not _has_keys():
        logger.error("❌ API credentials required for live trading!")
        logger.error("Set KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE")
        sys.exit(1)
    
    print("=" * 60)
    print("🤖 Bitcoin Trading Agent 24/7")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Profile: {_loaded_cfg.get('profile', 'default')}")
    print(f"Mode: {'🔴 LIVE TRADING' if not dry_run else '🟢 DRY RUN'}")
    print(f"API Keys: {'✅ Configured' if _has_keys() else '❌ Missing'}")
    print("=" * 60)
    
    if not dry_run:
        print("\n⚠️  WARNING: LIVE TRADING MODE!")
        print("Real money will be used. Press Ctrl+C within 10s to cancel.")
        time.sleep(10)
    
    # Criar agente
    agent = BitcoinTradingAgent(symbol=args.symbol, dry_run=dry_run, config_name=config_name)
    
    # Callback para sinais
    def on_signal(sig: Signal):
        if sig.action != "HOLD":
            logger.info(f"📍 {sig.action} signal @ ${sig.price:,.2f} "
                       f"({sig.confidence:.1%}) - {sig.reason}")
    
    agent.on_signal(on_signal)
    
    if args.daemon:
        daemon = AgentDaemon(agent)
        daemon.run()
    else:
        agent.start()
        
        try:
            while True:
                time.sleep(10)
                status = agent.get_status()
                print(f"\r💹 Running | Trades: {status['total_trades']} | "
                     f"PnL: ${status['total_pnl']:.2f} | "
                     f"Win Rate: {status['win_rate']:.1%}", end="")
        except KeyboardInterrupt:
            print("\n")
            agent.stop()

if __name__ == "__main__":
    main()
