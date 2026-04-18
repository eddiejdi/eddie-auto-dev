#!/usr/bin/env python3
"""
Bitcoin Trading Agent 24/7
Agente autônomo de trading que opera continuamente
"""

import os
import sys
import time
import json
import ast
import re
import random
import signal
import logging
import argparse
import threading
import statistics
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


def _read_json_config(config_path: Path) -> Dict[str, Any]:
    """Lê config JSON do disco com encoding consistente."""
    with open(config_path, encoding="utf-8") as cfg_file:
        return json.load(cfg_file)


def _explicit_runtime_config_requested(config_name: Optional[str] = None) -> bool:
    """Retorna True quando o processo recebeu um config específico da instância."""
    if config_name:
        return config_name != "config.json"
    env_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
    return env_name != "config.json"


def _load_bootstrap_config(config_path: Path) -> Dict[str, Any]:
    """Carrega o config bootstrap usado na importação do módulo."""
    try:
        return _read_json_config(config_path)
    except Exception:
        return {}

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


def _resolve_process_dry_run(cli_live: bool, loaded_cfg: Optional[Dict[str, Any]] = None) -> bool:
    """Resolve o modo efetivo do processo com override seguro pelo config.

    Regras:
    - CLI em dry-run sempre prevalece (nunca forçamos live via config).
    - Se o serviço pedir live, o config ainda pode forçar dry-run com
      `dry_run=true` ou `live_mode=false`.
    """
    requested_dry_run = not cli_live
    if requested_dry_run:
        return True

    cfg = loaded_cfg or {}
    if cfg.get("dry_run") is True:
        return True
    if "live_mode" in cfg and not bool(cfg.get("live_mode")):
        return True
    return False

# ====================== CONSTANTES ======================
# Default symbol — can be overridden by config file or CLI
_config_file = os.environ.get("COIN_CONFIG_FILE", "config.json")
_config_path = Path(__file__).parent / _config_file
_config = _load_bootstrap_config(_config_path)
DEFAULT_SYMBOL = _config.get("symbol", "BTC-USDT")
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
DCA_VALLEY_BOUNCE_PCT = _config.get("dca_valley_bounce_pct", 0.004)  # 0.4% bounce mínimo do fundo para liberar DCA

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
    raw_entry_count: int = 0  # Contagem bruta de BUYs abertos
    logical_position_slots: int = 0  # Ocupação lógica da posição agregada
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
    buy_success_pressure: float = 0.0
    buy_success_factor: float = 1.0
    buy_dynamic_batch_cap_usdt: float = 0.0
    dca_valley_low: float = 0.0  # Menor preço visto desde a última entrada DCA (0 = não rastreando)

    def to_dict(self) -> Dict:
        return {
            "running": self.running,
            "symbol": self.symbol,
            "position_btc": self.position,
            "position_usdt": self.position_value,
            "entry_price": self.entry_price,
            "position_count": self.position_count,
            "raw_entry_count": self.raw_entry_count,
            "logical_position_slots": self.logical_position_slots,
            "entries": self.entries,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.winning_trades / max(self.total_trades, 1),
            "total_pnl": self.total_pnl,
            "dry_run": self.dry_run,
            "last_sell_entry_price": self.last_sell_entry_price,
            "target_sell_price": self.target_sell_price,
            "target_sell_reason": self.target_sell_reason,
            "profile": self.profile,
            "buy_success_pressure": self.buy_success_pressure,
            "buy_success_factor": self.buy_success_factor,
            "buy_dynamic_batch_cap_usdt": self.buy_dynamic_batch_cap_usdt,
            "dca_valley_low": self.dca_valley_low,
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


@dataclass
class OllamaTradeWindowSuggestion:
    """Janela operacional curta calculada pela IA para o próximo ciclo."""
    entry_low: float
    entry_high: float
    target_sell: float
    min_confidence: float
    min_trade_interval: int
    ttl_seconds: int
    rationale: str
    raw: str

# ====================== AGENTE PRINCIPAL ======================
class BitcoinTradingAgent:
    """Agente de trading de Bitcoin 24/7"""
    
    def __init__(self, symbol: str = DEFAULT_SYMBOL, dry_run: bool = True, config_name: Optional[str] = None):
        self.symbol = symbol
        self.config_name = config_name or os.environ.get("COIN_CONFIG_FILE", _config_file)
        self.config_path = Path(__file__).parent / self.config_name
        self.config = self._load_live_config(strict=_explicit_runtime_config_requested(self.config_name))
        model_scope = f"{self.symbol}__{self.config.get('profile', PROFILE or 'default')}"
        self.state = AgentState(
            symbol=symbol,
            dry_run=dry_run,
            profile=self.config.get("profile", PROFILE),
        )
        self.model = FastTradingModel(symbol, model_scope=model_scope)
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
        self._last_ai_trade_window_trigger_ts = 0.0
        self._last_ai_trade_window_regime = ""
        self._ai_trade_window_lock = threading.Lock()
        self._buy_profit_guard_cache: Dict[str, Any] = {}

        # Jitter de startup: distribui chamadas de IA entre os agentes concorrentes
        # para evitar que todos batam no Ollama simultaneamente e gerem 503.
        # Cada instância recebe um offset aleatório dentro do intervalo mínimo de
        # cada tipo de chamada, sem alterar a frequência de longo prazo.
        _jitter_plan = random.uniform(0, self._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
        _jitter_controls = random.uniform(0, self._OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC)
        _jitter_window = random.uniform(0, max(
            self._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC,
            self._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC,
        ))
        _now = time.time()
        self._last_ai_plan_trigger_ts = _now - _jitter_plan
        self._last_ai_trade_controls_trigger_ts = _now - _jitter_controls
        self._last_ai_trade_window_trigger_ts = _now - _jitter_window

        self.state.start_time = time.time()
        logger.info(
            f"🤖 Agent initialized: {symbol} (dry_run={dry_run}, profile={self.state.profile}, config={self.config_name})"
        )

    def _load_live_config(self, strict: bool = False) -> Dict:
        """Carrega o config ativo da instância; cai para o config de import em caso de falha."""
        try:
            return _read_json_config(self.config_path)
        except FileNotFoundError:
            if strict:
                raise
            if getattr(self, "config", None):
                logger.warning(
                    "⚠️ Config %s ausente; mantendo último config válido em memória",
                    self.config_path,
                )
                return dict(self.config)
        except Exception:
            if strict:
                raise
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

    def _get_runtime_trade_day_limits(self) -> Dict[str, float]:
        """Retorna limits diários ativos da instância a partir do config vivo."""
        live_cfg = self._load_live_config()
        return {
            "max_daily_trades": max(0, int(live_cfg.get("max_daily_trades", MAX_DAILY_TRADES))),
            "max_daily_loss": max(0.0, float(live_cfg.get("max_daily_loss", MAX_DAILY_LOSS))),
        }

    def _sync_position_tracking(self) -> None:
        """Mantém contagem bruta e slot lógico coerentes com a posição atual."""
        entries = list(getattr(self.state, "entries", []) or [])
        raw_entry_count = len(entries)
        position = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        entry_price = max(float(getattr(self.state, "entry_price", 0.0) or 0.0), 0.0)
        has_open_position = position > 0 and (raw_entry_count > 0 or entry_price > 0)
        self.state.position_count = raw_entry_count
        self.state.raw_entry_count = raw_entry_count
        if not has_open_position:
            self.state.logical_position_slots = 0
        elif raw_entry_count > 0:
            self.state.logical_position_slots = raw_entry_count
        else:
            self.state.logical_position_slots = 1

    @staticmethod
    def _get_rebuy_discount_pct() -> float:
        """Desconto mínimo abaixo do preço médio para liberar reforço."""
        return 0.01

    def _resolve_dynamic_buy_batch_limit(self, remaining_exposure: float) -> Dict[str, float]:
        """Resolve o cap dinâmico por lote usando a pressão recente do profile."""
        pressure = 0.0
        try:
            base_cfg = self._load_live_config().get("buy_profit_guard", {})
            performance = self._get_profile_buy_profit_guard_pressure(base_cfg)
            pressure = float(performance.get("pressure", 0.0) or 0.0)
        except Exception as e:
            logger.debug(f"Dynamic batch limit fallback: {e}")

        pressure = max(0.0, min(pressure, 1.0))
        success_factor = max(0.0, min(1.0 - pressure, 1.0))
        dynamic_batch_cap_usdt = max(0.0, remaining_exposure * (0.40 + 0.60 * success_factor))

        self.state.buy_success_pressure = pressure
        self.state.buy_success_factor = success_factor
        self.state.buy_dynamic_batch_cap_usdt = dynamic_batch_cap_usdt

        return {
            "pressure": pressure,
            "success_factor": success_factor,
            "dynamic_batch_cap_usdt": dynamic_batch_cap_usdt,
        }

    def _get_guardrail_sell_protection_cfg(self) -> Dict[str, Any]:
        """Resolve a proteção de SELL quando os guardrails estão ativos.

        O modo protegido mantém o bot negociando normalmente, mas impede a
        realização de SELL abaixo do PnL líquido mínimo exigido pelo guardrail.
        Em contrapartida, qualquer SELL acima desse piso deve ser aceito
        imediatamente para preservar lucro, mesmo se o target antigo ainda não
        tiver sido batido.
        """
        live_cfg = self._load_live_config()
        explicit_active = live_cfg.get("guardrails_active")
        if explicit_active is None:
            day_limits = self._get_runtime_trade_day_limits()
            active = day_limits["max_daily_loss"] < 1000.0
        else:
            active = bool(explicit_active)

        positive_only = bool(live_cfg.get("guardrails_positive_only_sells", active))
        min_pnl_pct = max(0.0, float(live_cfg.get("guardrails_min_sell_pnl_pct", 0.025) or 0.025))
        return {
            "active": active,
            "positive_only_sells": positive_only,
            "min_sell_pnl_pct": min_pnl_pct,
        }

    def _estimate_sell_outcome(self, price: float) -> Dict[str, float]:
        """Estima o resultado líquido de um SELL da posição atual."""
        size = max(float(getattr(self.state, "position", 0.0) or 0.0), 0.0)
        entry_price = max(float(getattr(self.state, "entry_price", 0.0) or 0.0), 0.0)
        gross_sell = price * size
        sell_fee = gross_sell * TRADING_FEE_PCT
        buy_fee = entry_price * size * TRADING_FEE_PCT
        gross_pnl = (price - entry_price) * size
        total_fees = sell_fee + buy_fee
        net_profit = gross_pnl - total_fees
        return {
            "size": size,
            "gross_sell": gross_sell,
            "gross_pnl": gross_pnl,
            "total_fees": total_fees,
            "net_profit": net_profit,
        }

    def _get_guardrail_sell_verdict(self, price: float) -> Optional[Dict[str, float | bool]]:
        """Retorna o veredito de SELL do guardrail ativo, se aplicável."""
        if self.state.position <= 0 or self.state.entry_price <= 0:
            return None

        guard_cfg = self._get_guardrail_sell_protection_cfg()
        if not guard_cfg["active"] or not guard_cfg["positive_only_sells"]:
            return None

        outcome = self._estimate_sell_outcome(price)
        gross_sell = max(outcome["gross_sell"], 0.0)
        net_pnl_pct = (outcome["net_profit"] / gross_sell) if gross_sell > 0 else -1.0
        return {
            **outcome,
            "net_pnl_pct": net_pnl_pct,
            "min_sell_pnl_pct": guard_cfg["min_sell_pnl_pct"],
            "allow": net_pnl_pct >= guard_cfg["min_sell_pnl_pct"],
            "active": True,
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
        def _balanced_object(text: str) -> str:
            start = text.find("{")
            if start < 0:
                return text
            depth = 0
            in_string = False
            escape = False
            for idx in range(start, len(text)):
                ch = text[idx]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return text[start:idx + 1]
            return text[start:]

        def _repair_candidate(text: str) -> str:
            repaired = (text or "").strip()
            repaired = repaired.replace("```json", "").replace("```", "").strip()
            repaired = repaired.replace("\ufeff", "").replace("\x00", "")
            repaired = (
                repaired
                .replace("\u201c", '"')
                .replace("\u201d", '"')
                .replace("\u2018", "'")
                .replace("\u2019", "'")
            )
            repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
            repaired = re.sub(r"[\r\t]+", " ", repaired).strip()
            if repaired.count('"') % 2 == 1 and not repaired.endswith('"'):
                repaired += '"'
            brace_gap = repaired.count("{") - repaired.count("}")
            if brace_gap > 0:
                repaired += "}" * brace_gap
            bracket_gap = repaired.count("[") - repaired.count("]")
            if bracket_gap > 0:
                repaired += "]" * bracket_gap
            return repaired

        def _load_candidate(text: str) -> Any:
            try:
                parsed_obj = json.loads(text)
            except json.JSONDecodeError:
                parsed_obj = ast.literal_eval(text)
            if isinstance(parsed_obj, str):
                return _load_candidate(parsed_obj)
            return parsed_obj

        cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
        balanced = _balanced_object(cleaned)
        candidates = []
        for candidate in (balanced, _repair_candidate(balanced), _repair_candidate(cleaned)):
            candidate = (candidate or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        last_error: Optional[Exception] = None
        for candidate in candidates:
            try:
                parsed = _load_candidate(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise last_error
        raise ValueError("Ollama payload is not a JSON object")

    @staticmethod
    def _extract_loose_numeric_fields(raw: str, field_names: tuple[str, ...]) -> Dict[str, float]:
        """Extrai campos numéricos de payloads quase-JSON quando a resposta vem truncada."""
        text = (raw or "").replace("\r", " ").replace("\n", " ")
        extracted: Dict[str, float] = {}
        for field_name in field_names:
            match = re.search(
                rf'["\']?{re.escape(field_name)}["\']?(?:\s*[:=]\s*|\s+)["\']?(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)',
                text,
            )
            if not match:
                continue
            try:
                extracted[field_name] = float(match.group(1))
            except ValueError:
                continue
        return extracted

    @classmethod
    def _resolve_numeric_field(cls, parsed: Dict[str, Any], raw: str, field_name: str, default: float) -> float:
        """Lê um campo numérico do dict parseado e recorre ao extractor flexível se necessário."""
        value = parsed.get(field_name, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            fallback = cls._extract_loose_numeric_fields(raw, (field_name,))
            if field_name in fallback:
                return float(fallback[field_name])
            return float(default)

    @staticmethod
    def _secondary_ollama_host(host: str) -> str:
        """Alterna entre os endpoints padrão quando a porta é conhecida."""
        if ":11434" in host:
            return host.replace(":11434", ":11435")
        if ":11435" in host:
            return host.replace(":11435", ":11434")
        return host

    def _resolve_profile_ollama_targets(
        self,
        *,
        primary_host_env: str,
        fallback_host_env: str,
        default_host: str,
        default_model: str,
        conservative_model: str,
        fallback_model: str,
    ) -> tuple[str, str, str, str]:
        """Resolve host+modelo por profile, preservando overrides explícitos."""
        explicit_primary_host = os.getenv(primary_host_env, "").strip()
        explicit_fallback_host = os.getenv(fallback_host_env, "").strip()
        primary_host = explicit_primary_host or default_host
        primary_model = default_model

        if not explicit_primary_host and self._current_profile() == "conservative":
            primary_host = self._secondary_ollama_host(default_host)
            primary_model = conservative_model

        fallback_host = explicit_fallback_host or self._secondary_ollama_host(primary_host)
        fallback_model_resolved = fallback_model

        if not explicit_fallback_host and self._current_profile() == "conservative":
            fallback_host = default_host
            fallback_model_resolved = default_model

        return primary_host, primary_model, fallback_host, fallback_model_resolved

    def _get_trade_window_ollama_targets(self) -> tuple[str, str, str, str]:
        """Resolve host+modelo do trade-window por profile."""
        cross_model_fallback_enabled = os.getenv(
            "OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        primary_host, primary_model, fallback_host, fallback_model = self._resolve_profile_ollama_targets(
            primary_host_env="OLLAMA_TRADE_WINDOW_HOST",
            fallback_host_env="OLLAMA_TRADE_WINDOW_FALLBACK_HOST",
            default_host=self._OLLAMA_TRADE_WINDOW_HOST,
            default_model=self._OLLAMA_TRADE_WINDOW_MODEL,
            conservative_model=self._OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL,
            fallback_model=self._OLLAMA_TRADE_WINDOW_FALLBACK_MODEL,
        )
        if not os.getenv("OLLAMA_TRADE_WINDOW_HOST", "").strip():
            qwen_host = self._secondary_ollama_host(self._OLLAMA_TRADE_WINDOW_HOST)
            qwen_model = (
                self._OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL
                or self._OLLAMA_TRADE_WINDOW_FALLBACK_MODEL
                or primary_model
            ).strip()
            if qwen_host and qwen_model:
                primary_host, primary_model = qwen_host, qwen_model
                if not os.getenv("OLLAMA_TRADE_WINDOW_FALLBACK_HOST", "").strip():
                    if cross_model_fallback_enabled:
                        fallback_host = self._OLLAMA_TRADE_WINDOW_HOST
                        fallback_model = self._OLLAMA_TRADE_WINDOW_MODEL
                    else:
                        fallback_host = ""
                        fallback_model = ""
        return primary_host, primary_model, fallback_host, fallback_model

    def _get_trade_controls_ollama_targets(self) -> tuple[str, str, str, str]:
        """Resolve host+modelo do trade-controls por profile."""
        cross_model_fallback_enabled = os.getenv(
            "OLLAMA_STRUCTURED_CROSS_MODEL_FALLBACK", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        primary_host, primary_model, fallback_host, fallback_model = self._resolve_profile_ollama_targets(
            primary_host_env="OLLAMA_TRADE_PARAMS_HOST",
            fallback_host_env="OLLAMA_TRADE_PARAMS_FALLBACK_HOST",
            default_host=self._OLLAMA_TRADE_PARAMS_HOST,
            default_model=self._OLLAMA_TRADE_PARAMS_MODEL,
            conservative_model=self._OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL,
            fallback_model=self._OLLAMA_TRADE_PARAMS_FALLBACK_MODEL,
        )
        if not os.getenv("OLLAMA_TRADE_PARAMS_HOST", "").strip():
            qwen_host = self._secondary_ollama_host(self._OLLAMA_TRADE_PARAMS_HOST)
            qwen_model = (self._OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL or primary_model).strip()
            if qwen_host and qwen_model:
                primary_host, primary_model = qwen_host, qwen_model
                if not os.getenv("OLLAMA_TRADE_PARAMS_FALLBACK_HOST", "").strip():
                    if cross_model_fallback_enabled:
                        fallback_host = self._OLLAMA_TRADE_PARAMS_HOST
                        fallback_model = self._OLLAMA_TRADE_PARAMS_MODEL
                    else:
                        fallback_host = ""
                        fallback_model = ""
        return primary_host, primary_model, fallback_host, fallback_model

    @staticmethod
    def _compact_prompt_json(payload: Dict[str, Any]) -> str:
        """Serializa contexto compacto para reduzir tokens nos prompts estruturados."""
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)

    def _request_ollama_structured(
        self,
        *,
        label: str,
        prompt: str,
        primary_host: str,
        primary_model: str,
        fallback_host: str,
        fallback_model: str,
        primary_timeout_sec: float,
        fallback_timeout_sec: float,
        options: Dict[str, Any],
        parser,
        retries_per_target: int = 1,
    ) -> tuple[Any, str, Dict[str, Any]]:
        """Executa chamada estruturada ao Ollama com retry/fallback e parser validante."""
        attempts: list[tuple[str, str, float, int, int]] = []
        seen: set[tuple[str, str]] = set()
        target_attempts = max(1, int(retries_per_target))
        for target_index, (host, model, timeout_sec) in enumerate((
            (primary_host, primary_model, primary_timeout_sec),
            (fallback_host, fallback_model, fallback_timeout_sec),
        ), start=1):
            host = (host or "").strip()
            model = (model or "").strip()
            if not host or not model:
                continue
            key = (host, model)
            if key in seen:
                continue
            seen.add(key)
            for target_attempt in range(1, target_attempts + 1):
                attempts.append((host, model, timeout_sec, target_index, target_attempt))

        errors: list[str] = []
        for attempt_no, (host, model, timeout_sec, target_index, target_attempt) in enumerate(attempts, start=1):
            started = time.time()
            try:
                with httpx.Client(timeout=float(timeout_sec)) as client:
                    resp = client.post(
                        f"{host}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt,
                            "stream": False,
                            "format": "json",
                            "options": options,
                        },
                    )
                if resp.status_code == 503:
                    # GPU sobrecarregado: backoff com jitter antes de tentar fallback
                    jitter = random.uniform(0.5, 2.0)
                    logger.debug(
                        "Ollama 503 em %s/%s — aguardando %.1fs antes do fallback",
                        host, model, jitter,
                    )
                    time.sleep(jitter)
                    raise RuntimeError(f"HTTP 503")
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                raw = resp.json().get("response", "").strip()
                parsed = parser(raw)
                latency_ms = (time.time() - started) * 1000.0
                return parsed, raw, {
                    "host": host,
                    "model": model,
                    "latency_ms": round(latency_ms, 2),
                    "attempt": attempt_no,
                    "target_attempt": target_attempt,
                    "fallback_used": target_index > 1,
                }
            except Exception as e:
                errors.append(f"{model}@{host}#{target_attempt}: {type(e).__name__}: {e}")

        raise RuntimeError(f"{label} failed after {len(attempts)} attempts: {' | '.join(errors[:4])}")

    def _parse_ai_trade_controls(self, raw: str) -> OllamaTradeControlSuggestion:
        """Valida a resposta JSON do Ollama para controles de risco."""
        try:
            parsed = self._extract_json_object(raw)
        except Exception:
            parsed = self._extract_loose_numeric_fields(
                raw,
                ("min_confidence", "min_trade_interval", "max_position_pct", "max_positions"),
            )
            if not parsed:
                raise
        suggestion = OllamaTradeControlSuggestion(
            min_confidence=self._resolve_numeric_field(parsed, raw, "min_confidence", MIN_CONFIDENCE),
            min_trade_interval=int(round(self._resolve_numeric_field(parsed, raw, "min_trade_interval", MIN_TRADE_INTERVAL))),
            max_position_pct=self._resolve_numeric_field(parsed, raw, "max_position_pct", MAX_POSITION_PCT),
            max_positions=int(round(self._resolve_numeric_field(parsed, raw, "max_positions", MAX_POSITIONS))),
            rationale=str(parsed.get("rationale", "")).strip()[:500],
            raw=raw.strip(),
        )
        return suggestion

    def _get_trade_window_settings(self) -> Dict[str, float]:
        """Retorna cadência e clamps da janela fresca por profile."""
        profile = self._current_profile()
        if profile == "aggressive":
            return {
                "min_interval_sec": max(15, self._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC),
                "ttl_seconds": max(30, self._OLLAMA_TRADE_WINDOW_TTL_AGGRESSIVE_SEC),
                "window_depth_pct": 0.0028,
                "max_chase_pct": 0.0012,
                "target_cap_pct": 0.0100,
            }
        if profile == "conservative":
            return {
                "min_interval_sec": max(20, self._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC),
                "ttl_seconds": max(45, self._OLLAMA_TRADE_WINDOW_TTL_CONSERVATIVE_SEC),
                "window_depth_pct": 0.0025,
                "max_chase_pct": 0.0009,
                "target_cap_pct": 0.0090,
            }
        return {
            "min_interval_sec": max(15, self._OLLAMA_TRADE_WINDOW_MIN_INTERVAL_SEC),
            "ttl_seconds": max(30, self._OLLAMA_TRADE_WINDOW_TTL_SEC),
            "window_depth_pct": 0.0030,
            "max_chase_pct": 0.0012,
            "target_cap_pct": 0.0100,
        }

    def _get_trade_window_file(self) -> Path:
        """Arquivo local do cache quente da janela operacional."""
        trade_dir = Path(__file__).parent / "data" / "market_rag"
        trade_dir.mkdir(parents=True, exist_ok=True)
        profile = self._current_profile()
        suffix = "" if profile == "default" else f"_{profile}"
        return trade_dir / f"trade_window{suffix}.json"

    def _parse_ai_trade_window(
        self,
        raw: str,
        market_state: "MarketState",
        rag_adj,
        controls: TradeControls,
    ) -> OllamaTradeWindowSuggestion:
        """Valida e normaliza a janela operacional retornada pelo Ollama."""
        try:
            parsed = self._extract_json_object(raw)
        except Exception:
            parsed = self._extract_loose_numeric_fields(
                raw,
                (
                    "entry_low",
                    "entry_high",
                    "target_sell",
                    "min_confidence",
                    "min_trade_interval",
                    "ttl_seconds",
                ),
            )
            if not parsed:
                raise
        settings = self._get_trade_window_settings()
        reference_price = max(float(getattr(market_state, "price", 0.0) or 0.0), 0.0)
        if reference_price <= 0:
            raise ValueError("market_state.price must be positive")

        base_buy_target = max(float(getattr(rag_adj, "ai_buy_target_price", 0.0) or 0.0), 0.0)
        floor_bound = reference_price * (1 - settings["window_depth_pct"])
        ceiling_bound = reference_price * (1 + settings["max_chase_pct"])
        default_entry_low = min(reference_price, base_buy_target) if base_buy_target > 0 else reference_price * (1 - settings["window_depth_pct"] * 0.4)
        default_entry_low = max(default_entry_low, floor_bound)
        default_entry_high = max(reference_price, base_buy_target) if base_buy_target > 0 else reference_price
        default_entry_high = min(max(default_entry_high, default_entry_low), ceiling_bound)

        entry_low = self._resolve_numeric_field(parsed, raw, "entry_low", default_entry_low)
        entry_high = self._resolve_numeric_field(parsed, raw, "entry_high", default_entry_high)
        if entry_low > entry_high:
            entry_low, entry_high = entry_high, entry_low
        entry_low = min(max(entry_low, floor_bound), ceiling_bound)
        entry_high = min(max(entry_high, max(entry_low, reference_price * (1 - 0.0002))), ceiling_bound)
        entry_low = min(entry_low, entry_high)

        fee_buffer_pct = max(TRADING_FEE_PCT * 2.4, 0.0010)
        default_target_sell = max(
            entry_high * (1 + fee_buffer_pct),
            reference_price * (1 + max(float(getattr(rag_adj, "ai_take_profit_pct", 0.0) or 0.0), fee_buffer_pct)),
        )
        target_sell_cap = reference_price * (1 + settings["target_cap_pct"])
        target_sell = self._resolve_numeric_field(parsed, raw, "target_sell", default_target_sell)
        target_sell = max(
            min(target_sell, target_sell_cap),
            max(entry_high * (1 + fee_buffer_pct), reference_price * (1 + fee_buffer_pct)),
        )

        min_confidence_floor = max(0.40, controls.min_confidence - 0.10)
        min_confidence_cap = min(0.92, controls.min_confidence + 0.08)
        min_confidence = self._resolve_numeric_field(parsed, raw, "min_confidence", controls.min_confidence)
        min_confidence = min(max(min_confidence, min_confidence_floor), min_confidence_cap)

        min_interval_floor = max(30, int(controls.min_trade_interval * 0.5))
        min_interval_cap = min(900, int(controls.min_trade_interval * 1.5))
        min_trade_interval = int(round(self._resolve_numeric_field(parsed, raw, "min_trade_interval", controls.min_trade_interval)))
        min_trade_interval = min(max(min_trade_interval, min_interval_floor), min_interval_cap)

        ttl_default = int(settings["ttl_seconds"])
        ttl_seconds = int(round(self._resolve_numeric_field(parsed, raw, "ttl_seconds", ttl_default)))
        ttl_seconds = min(max(ttl_seconds, max(20, ttl_default // 2)), max(ttl_default, ttl_default * 2))

        return OllamaTradeWindowSuggestion(
            entry_low=entry_low,
            entry_high=entry_high,
            target_sell=target_sell,
            min_confidence=min_confidence,
            min_trade_interval=min_trade_interval,
            ttl_seconds=ttl_seconds,
            rationale=str(parsed.get("rationale", "")).strip()[:500],
            raw=raw.strip(),
        )

    def _get_fresh_ai_trade_window(self) -> Optional[Dict[str, Any]]:
        """Retorna a janela operacional fresca do profile atual, se válida."""
        try:
            trade_window_file = self._get_trade_window_file()
            if not trade_window_file.exists():
                return None
            with open(trade_window_file) as tw_file:
                payload = json.load(tw_file)
            current = payload.get("current", payload)
            if not isinstance(current, dict):
                return None
            now = time.time()
            if float(current.get("valid_until", 0.0) or 0.0) <= now:
                return None
            if current.get("symbol") not in (None, self.symbol):
                return None
            if current.get("profile") not in (None, self._current_profile()):
                return None
            return current
        except Exception as e:
            logger.debug(f"Fresh trade window read error: {e}")
            return None

    def _resolve_buy_gate_limits(self, rag_adj, signal: Optional[Signal] = None) -> Dict[str, Any]:
        """Calcula alvo e teto efetivos de compra, com override de janela fresca."""
        ai_buy_target = float(getattr(rag_adj, "ai_buy_target_price", 0.0) or 0.0)
        extra_discount_pct = self._get_buy_extra_discount_pct(rag_adj, signal)
        uplift_pct = 0.0
        target_reference = ai_buy_target
        if extra_discount_pct <= 0 and ai_buy_target > 0:
            uplift_pct = self._get_buy_target_uplift_pct(rag_adj, signal)
            target_reference = ai_buy_target * (1 + uplift_pct)
        effective_buy_target = target_reference * (1 - extra_discount_pct) if target_reference > 0 else 0.0
        tolerance_pct = 0.0
        if extra_discount_pct <= 0:
            tolerance_pct = self._get_buy_target_tolerance_pct(rag_adj, signal)
        base_buy_ceiling = effective_buy_target * (1 + tolerance_pct) if effective_buy_target > 0 else 0.0
        effective_buy_ceiling = base_buy_ceiling

        trade_window = self._get_fresh_ai_trade_window()
        window_entry_low = float((trade_window or {}).get("entry_low", 0.0) or 0.0)
        window_entry_high = float((trade_window or {}).get("entry_high", 0.0) or 0.0)
        used_trade_window = False
        if trade_window and window_entry_high > 0:
            if effective_buy_target <= 0:
                effective_buy_target = window_entry_low or window_entry_high
            if effective_buy_ceiling <= 0 or window_entry_high > effective_buy_ceiling:
                effective_buy_ceiling = window_entry_high
                used_trade_window = True

        return {
            "ai_buy_target": ai_buy_target,
            "extra_discount_pct": extra_discount_pct,
            "uplift_pct": uplift_pct,
            "tolerance_pct": tolerance_pct,
            "effective_buy_target": effective_buy_target,
            "base_buy_ceiling": base_buy_ceiling,
            "effective_buy_ceiling": effective_buy_ceiling,
            "trade_window": trade_window,
            "window_entry_low": window_entry_low,
            "window_entry_high": window_entry_high,
            "used_trade_window": used_trade_window,
        }

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
            self._sync_position_tracking()

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
                f"({self.state.raw_entry_count} entries, {self.state.logical_position_slots} logical slot, "
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
    _OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL = os.getenv("OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL", "qwen3:0.6b")
    _OLLAMA_TRADE_PARAMS_FALLBACK_MODEL = os.getenv("OLLAMA_TRADE_PARAMS_FALLBACK_MODEL", "qwen3:0.6b")
    _OLLAMA_TRADE_PARAMS_MODE = os.getenv("OLLAMA_TRADE_PARAMS_MODE", "shadow")
    _OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC = int(os.getenv("OLLAMA_TRADE_PARAMS_MIN_INTERVAL_SEC", "300"))
    _OLLAMA_TRADE_PARAMS_TIMEOUT_SEC = float(os.getenv("OLLAMA_TRADE_PARAMS_TIMEOUT_SEC", "45"))
    _OLLAMA_TRADE_PARAMS_FALLBACK_TIMEOUT_SEC = float(os.getenv("OLLAMA_TRADE_PARAMS_FALLBACK_TIMEOUT_SEC", "30"))
    _OLLAMA_TRADE_WINDOW_HOST = os.getenv("OLLAMA_TRADE_WINDOW_HOST", _OLLAMA_TRADE_PARAMS_HOST)
    _OLLAMA_TRADE_WINDOW_MODEL = os.getenv("OLLAMA_TRADE_WINDOW_MODEL", _OLLAMA_TRADE_PARAMS_MODEL)
    _OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL = os.getenv("OLLAMA_TRADE_WINDOW_CONSERVATIVE_MODEL", _OLLAMA_TRADE_PARAMS_CONSERVATIVE_MODEL)
    _OLLAMA_TRADE_WINDOW_FALLBACK_MODEL = os.getenv("OLLAMA_TRADE_WINDOW_FALLBACK_MODEL", "qwen3:0.6b")
    _OLLAMA_TRADE_WINDOW_MODE = os.getenv("OLLAMA_TRADE_WINDOW_MODE", "apply")
    _OLLAMA_TRADE_WINDOW_MIN_INTERVAL_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_MIN_INTERVAL_SEC", "30"))
    _OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_MIN_INTERVAL_AGGRESSIVE_SEC", "20"))
    _OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_MIN_INTERVAL_CONSERVATIVE_SEC", "40"))
    _OLLAMA_TRADE_WINDOW_TTL_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_TTL_SEC", "60"))
    _OLLAMA_TRADE_WINDOW_TTL_AGGRESSIVE_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_TTL_AGGRESSIVE_SEC", "45"))
    _OLLAMA_TRADE_WINDOW_TTL_CONSERVATIVE_SEC = int(os.getenv("OLLAMA_TRADE_WINDOW_TTL_CONSERVATIVE_SEC", "90"))
    _OLLAMA_TRADE_WINDOW_TIMEOUT_SEC = float(os.getenv("OLLAMA_TRADE_WINDOW_TIMEOUT_SEC", "45"))
    _OLLAMA_TRADE_WINDOW_FALLBACK_TIMEOUT_SEC = float(os.getenv("OLLAMA_TRADE_WINDOW_FALLBACK_TIMEOUT_SEC", "30"))

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

        # 15. Detectar placeholders X.XXX alucinados pelo modelo
        placeholder_patterns = [
            r"\$X{2,}\.X+",          # $XX.XXXX, $XXX.XX
            r"\$X{1,},X{3}",          # $X,XXX ou $XX,XXX
            r"X\.X{4,}",              # X.XXXXX (BTC placeholder)
            r"\bX{2,}\.X{2,}\b",      # XX.XX genérico
            r"TRADING REPORT",         # formato de relatório alucinado
        ]
        placeholder_hits = sum(
            1 for pat in placeholder_patterns if _re.search(pat, text)
        )
        if placeholder_hits >= 2:
            logger.warning(
                f"⚠️ AI plan com placeholders/formato alucinado "
                f"({placeholder_hits} padrões X.XXX detectados)"
            )
            return ""

        return text.strip()

    def _generate_ai_trade_controls(self, market_state: "MarketState", trigger: str = "periodic") -> None:
        """Gera sugestão estruturada do Ollama para parâmetros de risco."""
        try:
            rag_adj = self.market_rag.get_current_adjustment()
            controls = self._resolve_trade_controls(rag_adj)
            caps = self._get_runtime_risk_caps()
            profile = self._current_profile()
            rag_stats = self.market_rag.get_stats()
            primary_host, primary_model, fallback_host, fallback_model = self._get_trade_controls_ollama_targets()

            indicators = self.model.indicators
            rsi = indicators.rsi()
            momentum = indicators.momentum()
            volatility = indicators.volatility()
            _quote_cur = self.symbol.split("-")[1]
            usdt_bal = get_balance(_quote_cur) if not self.state.dry_run else 1000

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

            controls_limits = {
                "min_confidence_min": round(max(0.40, controls.min_confidence - 0.10), 3),
                "min_confidence_max": round(min(0.92, controls.min_confidence + 0.10), 3),
                "min_trade_interval_min": max(30, int(controls.min_trade_interval * 0.5)),
                "min_trade_interval_max": min(900, int(controls.min_trade_interval * 1.8)),
                "max_position_pct_max": round(caps["max_position_pct"], 4),
                "max_positions_max": int(caps["max_positions"]),
            }
            controls_context = {
                "profile": profile,
                "trigger": trigger,
                "regime": rag_stats["current_regime"],
                "regime_confidence": round(float(rag_stats["regime_confidence"]), 4),
                "price": round(float(market_state.price), 2),
                "rsi": round(float(rsi), 2),
                "momentum": round(float(momentum), 6),
                "volatility": round(float(volatility), 6),
                "orderbook_imbalance": round(float(market_state.orderbook_imbalance), 4),
                "spread": round(float(market_state.spread), 8),
                "trade_flow": round(float(market_state.trade_flow), 4),
                "usdt_balance": round(float(usdt_bal), 2),
                "position_count": int(self.state.position_count),
                "position_btc": round(float(self.state.position), 8),
                "entry_price": round(float(self.state.entry_price), 2),
                "rag_baseline_min_confidence": round(float(rag_adj.ai_min_confidence), 3),
                "rag_baseline_min_trade_interval": int(rag_adj.ai_min_trade_interval),
                "rag_ai_position_size_pct": round(float(rag_adj.ai_position_size_pct), 4),
                "rag_ai_max_entries": int(rag_adj.ai_max_entries),
            }
            if news_lines:
                controls_context["news"] = news_lines[:3]
            prompt = (
                "Retorne somente um objeto JSON válido, sem markdown, com as chaves "
                "min_confidence,min_trade_interval,max_position_pct,max_positions.\n"
                "Use apenas números simples. Não inclua texto livre. "
                "Se houver dúvida, fique perto do baseline.\n"
                f"LIMITS={self._compact_prompt_json(controls_limits)}\n"
                f"CONTEXT={self._compact_prompt_json(controls_context)}"
            )
            suggestion, raw, request_meta = self._request_ollama_structured(
                label="trade controls",
                prompt=prompt,
                primary_host=primary_host,
                primary_model=primary_model,
                fallback_host=fallback_host,
                fallback_model=fallback_model,
                primary_timeout_sec=self._OLLAMA_TRADE_PARAMS_TIMEOUT_SEC,
                fallback_timeout_sec=self._OLLAMA_TRADE_PARAMS_FALLBACK_TIMEOUT_SEC,
                options={
                    "temperature": 0.0,
                    "num_predict": 64,
                    "num_ctx": 1536,
                    "repeat_penalty": 1.05,
                    "top_k": 20,
                    "top_p": 0.70,
                },
                parser=self._parse_ai_trade_controls,
                retries_per_target=2,
            )
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
                model=str(request_meta.get("model", primary_model)),
            )
            self._save_ai_trade_controls(
                suggestion=suggestion,
                applied_adj=applied_adj,
                trigger=trigger,
                raw=raw,
                request_meta=request_meta,
            )
            logger.info(
                "🧠 AI trade controls "
                f"[{self._OLLAMA_TRADE_PARAMS_MODE}] trigger={trigger} "
                f"suggested(conf>={suggestion.min_confidence:.0%}, cd={suggestion.min_trade_interval}s, "
                f"cap={suggestion.max_position_pct*100:.1f}%/{suggestion.max_positions}) "
                f"applied(conf>={applied_adj.applied_min_confidence:.0%}, cd={applied_adj.applied_min_trade_interval}s, "
                f"cap={applied_adj.applied_max_position_pct*100:.1f}%/{applied_adj.applied_max_positions}) "
                f"via {request_meta.get('model')}@{request_meta.get('host')} "
                f"{request_meta.get('latency_ms', 0):.0f}ms"
            )
        except Exception as e:
            log_fn = logger.info if self._OLLAMA_TRADE_PARAMS_MODE == "shadow" else logger.warning
            log_fn(f"⚠️ AI trade controls generation failed: {e}")

    def _save_ai_trade_controls(
        self,
        *,
        suggestion: OllamaTradeControlSuggestion,
        applied_adj,
        trigger: str,
        raw: str,
        request_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persiste a última sugestão estruturada do Ollama para auditoria."""
        try:
            self.db.record_ai_trade_controls(
                symbol=self.symbol,
                profile=self._current_profile(),
                trigger=trigger,
                mode=str(getattr(applied_adj, "ollama_mode", self._OLLAMA_TRADE_PARAMS_MODE) or self._OLLAMA_TRADE_PARAMS_MODE),
                model=str((request_meta or {}).get("model", self._OLLAMA_TRADE_PARAMS_MODEL) or self._OLLAMA_TRADE_PARAMS_MODEL),
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
                    "host": (request_meta or {}).get("host"),
                    "latency_ms": (request_meta or {}).get("latency_ms"),
                    "fallback_used": (request_meta or {}).get("fallback_used", False),
                    "attempt": (request_meta or {}).get("attempt", 1),
                    "raw": raw[:4000],
                },
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save AI trade controls: {e}")

    def _generate_ai_trade_window(self, market_state: "MarketState", trigger: str = "periodic") -> None:
        """Gera uma janela operacional curta em background para manter a consulta fresca."""
        if not self._ai_trade_window_lock.acquire(blocking=False):
            logger.debug("AI trade window generation already running")
            return
        try:
            rag_adj = self.market_rag.get_current_adjustment()
            controls = self._resolve_trade_controls(rag_adj)
            settings = self._get_trade_window_settings()
            profile = self._current_profile()
            rag_stats = self.market_rag.get_stats()
            primary_host, primary_model, fallback_host, fallback_model = self._get_trade_window_ollama_targets()
            indicators = self.model.indicators
            rsi = indicators.rsi()
            momentum = indicators.momentum()
            volatility = indicators.volatility()

            window_limits = {
                "entry_low_min": round(market_state.price * (1 - settings["window_depth_pct"]), 2),
                "entry_low_max": round(float(market_state.price), 2),
                "entry_high_min": round(market_state.price * 0.9998, 2),
                "entry_high_max": round(market_state.price * (1 + settings["max_chase_pct"]), 2),
                "target_sell_max": round(market_state.price * (1 + settings["target_cap_pct"]), 2),
                "min_confidence_min": round(max(0.40, controls.min_confidence - 0.10), 3),
                "min_confidence_max": round(min(0.92, controls.min_confidence + 0.08), 3),
                "min_trade_interval_min": max(30, int(controls.min_trade_interval * 0.5)),
                "min_trade_interval_max": min(900, int(controls.min_trade_interval * 1.5)),
                "ttl_min": max(20, int(settings["ttl_seconds"] // 2)),
                "ttl_max": int(settings["ttl_seconds"] * 2),
            }
            window_context = {
                "symbol": self.symbol,
                "profile": profile,
                "trigger": trigger,
                "regime": rag_stats["current_regime"],
                "regime_confidence": round(float(rag_stats["regime_confidence"]), 4),
                "price": round(float(market_state.price), 2),
                "rsi": round(float(rsi), 2),
                "momentum": round(float(momentum), 6),
                "volatility": round(float(volatility), 6),
                "orderbook_imbalance": round(float(market_state.orderbook_imbalance), 4),
                "spread": round(float(market_state.spread), 8),
                "trade_flow": round(float(market_state.trade_flow), 4),
                "position_count": int(self.state.position_count),
                "position_btc": round(float(self.state.position), 8),
                "entry_price": round(float(self.state.entry_price), 2),
                "rag_buy_target": round(float(rag_adj.ai_buy_target_price), 2),
                "rag_take_profit_pct": round(float(rag_adj.ai_take_profit_pct), 4),
                "rag_min_confidence": round(float(controls.min_confidence), 3),
                "rag_min_trade_interval": int(controls.min_trade_interval),
            }
            prompt = (
                "Retorne somente um objeto JSON válido, sem markdown, com as chaves "
                "entry_low,entry_high,target_sell,min_confidence,min_trade_interval,ttl_seconds.\n"
                "Use apenas números. Não inclua texto livre. "
                "Mantenha a janela curta e fresca. Se houver dúvida, fique perto do preço atual e do buy_target.\n"
                f"LIMITS={self._compact_prompt_json(window_limits)}\n"
                f"CONTEXT={self._compact_prompt_json(window_context)}"
            )
            suggestion, raw, request_meta = self._request_ollama_structured(
                label="trade window",
                prompt=prompt,
                primary_host=primary_host,
                primary_model=primary_model,
                fallback_host=fallback_host,
                fallback_model=fallback_model,
                primary_timeout_sec=self._OLLAMA_TRADE_WINDOW_TIMEOUT_SEC,
                fallback_timeout_sec=self._OLLAMA_TRADE_WINDOW_FALLBACK_TIMEOUT_SEC,
                options={
                    "temperature": 0.0,
                    "num_predict": 72,
                    "num_ctx": 1536,
                    "repeat_penalty": 1.05,
                    "top_k": 20,
                    "top_p": 0.70,
                },
                parser=lambda raw_text: self._parse_ai_trade_window(raw_text, market_state, rag_adj, controls),
                retries_per_target=2,
            )
            now = time.time()
            payload = {
                "current": {
                    "timestamp": now,
                    "symbol": self.symbol,
                    "profile": profile,
                    "trigger": trigger,
                    "mode": self._OLLAMA_TRADE_WINDOW_MODE,
                    "model": str(request_meta.get("model", primary_model)),
                    "host": str(request_meta.get("host", primary_host)),
                    "regime": rag_stats.get("current_regime", ""),
                    "reference_price": float(market_state.price),
                    "entry_low": suggestion.entry_low,
                    "entry_high": suggestion.entry_high,
                    "target_sell": suggestion.target_sell,
                    "min_confidence": suggestion.min_confidence,
                    "min_trade_interval": suggestion.min_trade_interval,
                    "ttl_seconds": suggestion.ttl_seconds,
                    "valid_until": now + suggestion.ttl_seconds,
                    "latency_ms": request_meta.get("latency_ms"),
                    "fallback_used": request_meta.get("fallback_used", False),
                    "rationale": suggestion.rationale,
                }
            }
            self._save_ai_trade_window(payload=payload, raw=raw)
            logger.info(
                "🪟 AI trade window "
                f"[{self._OLLAMA_TRADE_WINDOW_MODE}] trigger={trigger} "
                f"entry=${suggestion.entry_low:,.2f}-${suggestion.entry_high:,.2f} "
                f"sell=${suggestion.target_sell:,.2f} ttl={suggestion.ttl_seconds}s "
                f"via {request_meta.get('model')}@{request_meta.get('host')} "
                f"{request_meta.get('latency_ms', 0):.0f}ms"
            )
        except Exception as e:
            try:
                fallback_suggestion = self._parse_ai_trade_window("{}", market_state, rag_adj, controls)
                now = time.time()
                payload = {
                    "current": {
                        "timestamp": now,
                        "symbol": self.symbol,
                        "profile": profile,
                        "trigger": f"{trigger}:fallback",
                        "mode": self._OLLAMA_TRADE_WINDOW_MODE,
                        "model": "deterministic-fallback",
                        "host": "local",
                        "regime": rag_stats.get("current_regime", ""),
                        "reference_price": float(market_state.price),
                        "entry_low": fallback_suggestion.entry_low,
                        "entry_high": fallback_suggestion.entry_high,
                        "target_sell": fallback_suggestion.target_sell,
                        "min_confidence": fallback_suggestion.min_confidence,
                        "min_trade_interval": fallback_suggestion.min_trade_interval,
                        "ttl_seconds": fallback_suggestion.ttl_seconds,
                        "valid_until": now + fallback_suggestion.ttl_seconds,
                        "latency_ms": 0.0,
                        "fallback_used": True,
                        "rationale": "deterministic-fallback",
                    }
                }
                self._save_ai_trade_window(payload=payload, raw="{}")
                logger.info(
                    "🪟 AI trade window [fallback] "
                    f"trigger={trigger} entry=${fallback_suggestion.entry_low:,.2f}-${fallback_suggestion.entry_high:,.2f} "
                    f"sell=${fallback_suggestion.target_sell:,.2f} ttl={fallback_suggestion.ttl_seconds}s "
                    f"reason={type(e).__name__}"
                )
            except Exception as fallback_error:
                logger.warning(
                    f"⚠️ AI trade window generation failed: {e} | fallback failed: {fallback_error}"
                )
        finally:
            self._ai_trade_window_lock.release()

    def _save_ai_trade_window(self, *, payload: Dict[str, Any], raw: str) -> None:
        """Persiste a janela fresca em arquivo quente e banco para auditoria."""
        try:
            trade_window_file = self._get_trade_window_file()
            tmp_file = trade_window_file.with_suffix(f"{trade_window_file.suffix}.tmp")
            with open(tmp_file, "w") as tw_file:
                json.dump(payload, tw_file, ensure_ascii=True, indent=2)
            tmp_file.replace(trade_window_file)

            current = payload.get("current", {})
            self.db.record_ai_trade_window(
                symbol=self.symbol,
                profile=self._current_profile(),
                trigger=str(current.get("trigger", "periodic") or "periodic"),
                mode=str(current.get("mode", self._OLLAMA_TRADE_WINDOW_MODE) or self._OLLAMA_TRADE_WINDOW_MODE),
                model=str(current.get("model", self._OLLAMA_TRADE_WINDOW_MODEL) or self._OLLAMA_TRADE_WINDOW_MODEL),
                regime=str(current.get("regime", "") or ""),
                reference_price=float(current.get("reference_price", 0.0) or 0.0),
                entry_low=float(current.get("entry_low", 0.0) or 0.0),
                entry_high=float(current.get("entry_high", 0.0) or 0.0),
                target_sell=float(current.get("target_sell", 0.0) or 0.0),
                min_confidence=float(current.get("min_confidence", 0.0) or 0.0),
                min_trade_interval=int(current.get("min_trade_interval", 0) or 0),
                ttl_seconds=int(current.get("ttl_seconds", 0) or 0),
                valid_until=float(current.get("valid_until", 0.0) or 0.0),
                rationale=str(current.get("rationale", "") or ""),
                metadata={
                    "host": current.get("host"),
                    "latency_ms": current.get("latency_ms"),
                    "fallback_used": current.get("fallback_used", False),
                    "raw": raw[:4000],
                },
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to save AI trade window: {e}")

    @staticmethod
    def _format_portfolio_evo_prompt(evo: dict[str, float | int]) -> str:
        """Formata evolução patrimonial 24h como bloco para o prompt do LLM."""
        if not evo:
            return ""
        delta = evo.get("delta_usdt", 0)
        delta_pct = evo.get("delta_pct", 0)
        arrow = "📈" if delta >= 0 else "📉"
        pnl_r = evo.get("pnl_realized_24h", 0)
        brl = evo.get("brl_balance", 0)
        total_brl = evo.get("total_brl", 0)
        usdt_brl_rate = evo.get("usdt_brl_rate", 0)
        lines = [
            "EVOLUÇÃO PATRIMONIAL (últimas 24h):",
            f"- Patrimônio atual: ${evo.get('equity_now', 0):,.2f} USDT"
            f" | 24h atrás: ${evo.get('equity_24h_ago', 0):,.2f}",
            f"- Variação: {arrow} ${delta:+,.4f} ({delta_pct:+.2f}%)",
            f"- USDT: ${evo.get('usdt_now', 0):,.2f} (era ${evo.get('usdt_24h_ago', 0):,.2f})",
            f"- BTC: {evo.get('btc_now', 0):.8f} (era {evo.get('btc_24h_ago', 0):.8f})",
            f"- BRL: R${brl:,.2f}",
            f"- Total convertido em BRL: R${total_brl:,.2f} (taxa USDT/BRL: {usdt_brl_rate:.4f})",
            f"- PnL realizado 24h: ${pnl_r:+,.4f}"
            f" ({evo.get('sells_24h', 0)} sells, {evo.get('wins_24h', 0)}W/{evo.get('losses_24h', 0)}L)",
            "",
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_portfolio_evo_block(evo: dict[str, float | int]) -> str:
        """Formata evolução patrimonial 24h como bloco anexado ao plan_text."""
        if not evo:
            return ""
        delta = evo.get("delta_usdt", 0)
        delta_pct = evo.get("delta_pct", 0)
        arrow = "📈" if delta >= 0 else "📉"
        pnl_r = evo.get("pnl_realized_24h", 0)
        brl = evo.get("brl_balance", 0)
        total_brl = evo.get("total_brl", 0)
        usdt_brl_rate = evo.get("usdt_brl_rate", 0)
        lines = [
            "",
            "━━━ EVOLUÇÃO PATRIMONIAL 24H ━━━",
            f"• Patrimônio atual: ${evo.get('equity_now', 0):,.2f} USDT",
            f"• Patrimônio 24h atrás: ${evo.get('equity_24h_ago', 0):,.2f} USDT",
            f"• Variação: {arrow} ${delta:+,.4f} ({delta_pct:+.2f}%)",
            f"• USDT livre: ${evo.get('usdt_now', 0):,.2f}"
            f" (era ${evo.get('usdt_24h_ago', 0):,.2f})",
            f"• BTC em carteira: {evo.get('btc_now', 0):.8f}"
            f" (era {evo.get('btc_24h_ago', 0):.8f})",
            f"• BRL: R${brl:,.2f}",
            f"• Preço BTC: ${evo.get('btc_price', 0):,.2f}",
            f"• 💰 Total em BRL: R${total_brl:,.2f} (cotação: 1 USDT = R${usdt_brl_rate:.4f})",
            f"• PnL realizado 24h: ${pnl_r:+,.4f}"
            f" ({evo.get('sells_24h', 0)} sells,"
            f" {evo.get('wins_24h', 0)}W/{evo.get('losses_24h', 0)}L)",
        ]
        return "\n".join(lines)

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

            _quote_cur = self.symbol.split("-")[1]
            usdt_bal = get_balance(_quote_cur) if not self.state.dry_run else 1000

            # ── Evolução patrimonial últimas 24h ──
            portfolio_evo: dict[str, float | int] = {}
            try:
                with self.db._get_conn() as conn:
                    cur = conn.cursor()
                    # Equity agora vs ~23h atrás (margem para garantir dados)
                    cur.execute("""
                        WITH now_eq AS (
                            SELECT equity_usdt, usdt_balance, btc_balance, btc_price
                            FROM btc.exchange_snapshots ORDER BY timestamp DESC LIMIT 1
                        ), ago_eq AS (
                            SELECT equity_usdt, usdt_balance, btc_balance, btc_price
                            FROM btc.exchange_snapshots
                            WHERE timestamp <= EXTRACT(EPOCH FROM NOW()) - 82800
                            ORDER BY timestamp DESC LIMIT 1
                        )
                        SELECT
                            n.equity_usdt, a.equity_usdt,
                            n.usdt_balance, a.usdt_balance,
                            n.btc_balance, a.btc_balance,
                            n.btc_price
                        FROM now_eq n, ago_eq a
                    """)
                    eq_row = cur.fetchone()
                    if eq_row:
                        eq_now, eq_ago = float(eq_row[0]), float(eq_row[1])
                        portfolio_evo = {
                            "equity_now": eq_now,
                            "equity_24h_ago": eq_ago,
                            "delta_usdt": round(eq_now - eq_ago, 4),
                            "delta_pct": round((eq_now / eq_ago - 1) * 100, 2) if eq_ago else 0,
                            "usdt_now": round(float(eq_row[2]), 2),
                            "usdt_24h_ago": round(float(eq_row[3]), 2),
                            "btc_now": float(eq_row[4]),
                            "btc_24h_ago": float(eq_row[5]),
                            "btc_price": float(eq_row[6]),
                        }
                    # PnL realizado 24h
                    cur.execute("""
                        SELECT
                            COALESCE(SUM(pnl), 0),
                            COUNT(*) FILTER (WHERE side='sell'),
                            COUNT(*) FILTER (WHERE pnl > 0),
                            COUNT(*) FILTER (WHERE pnl < 0)
                        FROM btc.trades
                        WHERE dry_run = false
                          AND symbol = %s
                          AND timestamp > EXTRACT(EPOCH FROM NOW()) - 86400
                    """, (self.symbol,))
                    pnl_row = cur.fetchone()
                    if pnl_row:
                        portfolio_evo["pnl_realized_24h"] = round(float(pnl_row[0]), 4)
                        portfolio_evo["sells_24h"] = int(pnl_row[1])
                        portfolio_evo["wins_24h"] = int(pnl_row[2])
                        portfolio_evo["losses_24h"] = int(pnl_row[3])
                    # BRL via exchange_balance_snapshots + taxa USDT/BRL
                    cur.execute("""
                        SELECT available, price_usdt
                        FROM btc.exchange_balance_snapshots
                        WHERE currency = 'BRL' ORDER BY synced_at DESC LIMIT 1
                    """)
                    brl_row = cur.fetchone()
                    if brl_row:
                        portfolio_evo["brl_balance"] = round(float(brl_row[0]), 2)
                        brl_price_usdt = float(brl_row[1]) if brl_row[1] else 0
                        usdt_brl_rate = round(1 / brl_price_usdt, 4) if brl_price_usdt > 0 else 0
                        portfolio_evo["usdt_brl_rate"] = usdt_brl_rate
                        eq_now = portfolio_evo.get("equity_now", 0)
                        portfolio_evo["total_brl"] = round(eq_now * usdt_brl_rate, 2) if usdt_brl_rate else 0
                    cur.close()
            except Exception as e:
                logger.debug(f"📊 Portfolio evolution fetch: {e}")

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

            has_open_position = self.state.position > 0 and self.state.entry_price > 0
            target_sell_display = (
                f"${self.state.target_sell_price:,.2f}"
                if has_open_position and self.state.target_sell_price > 0
                else "N/A (sem posição aberta)"
            )
            sell_unlock_display = (
                f"${sell_unlock_price:,.2f} (entry ${self.state.entry_price:,.2f} + fees + min_pnl)"
                if has_open_position
                else "N/A (sem posição aberta)"
            )
            tp_target_display = (
                f"${tp_target:,.2f}"
                if has_open_position and tp_target > 0
                else "N/A (sem posição aberta)"
            )
            sl_price_display = (
                f"${sl_price:,.2f}"
                if has_open_position and sl_price > 0
                else "N/A (sem posição aberta)"
            )
            trailing_activation_display = (
                f"${trailing_activation_price:,.2f}"
                if has_open_position and trailing_activation_price > 0
                else "N/A (sem posição aberta)"
            )
            current_net_pnl_display = (
                f"${current_net_pnl:.4f}"
                if has_open_position
                else "N/A (sem posição aberta)"
            )

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
                f"{self._format_portfolio_evo_prompt(portfolio_evo)}"
                f"{news_prompt_block}"
                f"CONDIÇÕES DE VENDA (resumo atual):\n"
                f"- Target de venda (IA): {target_sell_display}\n"
                f"- PnL líquido mínimo (fallback): ${min_sell_pnl:.3f}\n"
                f"- Preço mín. para desbloquear SELL: {sell_unlock_display}\n"
                f"- Auto Take-Profit: {'ATIVADO' if tp_enabled else 'DESATIVADO'}, "
                f"TP={tp_pct*100:.2f}% → alvo {tp_target_display}\n"
                f"- Auto Stop-Loss: {'ATIVADO, SL=' + f'{sl_pct*100:.1f}% → piso {sl_price_display}' if sl_enabled else 'DESATIVADO'}\n"
                f"- Trailing Stop: {'ATIVADO, ativa em +' + f'{trailing_activation*100:.1f}% ({trailing_activation_display}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}\n"
                f"- PnL líquido atual: {current_net_pnl_display}\n\n"
                f"REGRAS OBRIGATÓRIAS:\n"
                f"- Use EXCLUSIVAMENTE os valores numéricos fornecidos acima. NUNCA substitua por placeholders como X.XXX, XX.XX, $XX,XXX ou similares.\n"
                f"- NUNCA invente dados, valores ou métricas que não foram fornecidos.\n"
                f"- NUNCA gere um 'TRADING REPORT' formatado. Gere apenas a ANÁLISE em parágrafos.\n"
                f"- NÃO inclua seções como SALDO KUCOIN, STATUS DOS AGENTES, PERFORMANCE DO DIA ou similares.\n\n"
                f"Responda em 3-5 parágrafos curtos com:\n"
                f"1. Situação atual do mercado\n"
                f"2. O que o agente vai fazer a seguir (comprar, vender, esperar)\n"
                f"3. Cenário de saída: quando e a que preço a venda será executada\n"
                f"4. Riscos e oportunidades identificados\n"
                f"5. Cite as fontes de notícias que mais impactam a análise (ex: [CoinDesk], [CoinTelegraph])\n"
                f"Seja direto e objetivo. Não use markdown headers."
            )

            plan_options = {
                "temperature": 0.4,
                "num_predict": 1024,
                "num_ctx": 4096,
                "repeat_penalty": 1.3,
                "repeat_last_n": 128,
                "top_k": 40,
                "top_p": 0.9,
            }
            # GPU1 (GTX 1050 2GB) precisa de contexto menor para caber na VRAM
            plan_options_fallback = {**plan_options, "num_ctx": 2048, "num_predict": 512}
            # GPU0 → GPU1 fallback para AI plan
            # GPU1 usa modelo menor (fallback) que já está carregado na VRAM
            _fallback_host = self._secondary_ollama_host(self._OLLAMA_PLAN_HOST)
            _fallback_model = self._OLLAMA_TRADE_PARAMS_FALLBACK_MODEL or self._OLLAMA_PLAN_MODEL
            plan_targets = [
                (self._OLLAMA_PLAN_HOST, self._OLLAMA_PLAN_MODEL, plan_options),
                (_fallback_host, _fallback_model, plan_options_fallback),
            ]
            raw_text = ""
            used_model = self._OLLAMA_PLAN_MODEL
            for host, model, opts in plan_targets:
                try:
                    client = httpx.Client(timeout=180.0)
                    resp = client.post(
                        f"{host}/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False, "options": opts},
                    )
                    client.close()
                    if resp.status_code != 200:
                        logger.warning(f"⚠️ Ollama AI plan error: HTTP {resp.status_code} from {host}")
                        continue
                    raw_text = resp.json().get("response", "").strip()
                    if raw_text:
                        used_model = model
                        logger.info(f"🧠 AI plan received from {model}@{host}")
                        break
                except Exception as plan_err:
                    logger.warning(f"⚠️ Ollama AI plan request failed ({host}): {plan_err}")
                    continue
            if not raw_text:
                logger.warning("⚠️ AI plan generation failed: all Ollama hosts unavailable")
                return
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
                f"• Preço mín. p/ desbloquear SELL: {sell_unlock_display}",
            ]
            if self.state.position > 0:
                sell_summary_lines.append(
                    f"• Entry médio: ${self.state.entry_price:,.2f} | "
                    f"Posição: {self.state.position:.8f} BTC"
                )
            sell_summary_lines.append(
                f"• Auto Take-Profit: "
                f"{'ATIVADO TP=' + f'{tp_pct*100:.2f}% → alvo {tp_target_display}' if tp_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• Auto Stop-Loss: "
                f"{'ATIVADO SL=' + f'{sl_pct*100:.1f}% → piso {sl_price_display}' if sl_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• Trailing Stop: "
                f"{'ATIVADO ativa +' + f'{trailing_activation*100:.1f}% ({trailing_activation_display}), trail {trailing_trail*100:.1f}%' if trailing_enabled else 'DESATIVADO'}"
            )
            sell_summary_lines.append(
                f"• PnL líquido atual: {current_net_pnl_display}"
            )
            plan_text += "\n" + "\n".join(sell_summary_lines)

            # ── Anexar bloco de evolução patrimonial 24h ──
            if portfolio_evo:
                plan_text += "\n" + self._format_portfolio_evo_block(portfolio_evo)

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
                    f"({len(news_articles)} artigos analisados via trading-sentiment)"
                )
                plan_text += "\n" + "\n".join(cite_lines)

            self._save_ai_plan(
                plan_text=plan_text,
                price=market_state.price,
                regime=rag_stats["current_regime"],
                model=used_model,
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
                    "portfolio_evolution": portfolio_evo or {},
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
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
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
                inserted_id = cursor.fetchone()[0]
                logger.info(f"📝 AI plan saved to DB: id={inserted_id}, profile={profile}")
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
            logger.warning(f"⚠️ Failed to save AI plan: {e}", exc_info=True)

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
                    self.state.entries = entries
                    self._sync_position_tracking()
                    logger.info(
                        f"🔄 Restored LIVE multi-position: {real_balance:.8f} {base_currency} "
                        f"({self.state.raw_entry_count} entries, {self.state.logical_position_slots} logical slot, "
                        f"avg ${avg_entry:,.2f})"
                    )
                else:
                    logger.info(f"📭 DB shows open BUYs but exchange balance is 0 — no position")
            except Exception as e:
                self.state.position = total_size
                self.state.entry_price = avg_entry
                self.state.position_value = total_size * avg_entry
                self.state.entries = entries
                self._sync_position_tracking()
                logger.warning(
                    f"⚠️ Could not check exchange ({e}), using DB: "
                    f"{total_size:.8f} ({self.state.raw_entry_count} entries, "
                    f"{self.state.logical_position_slots} logical slot, avg ${avg_entry:,.2f})"
                )
        else:
            self.state.position = total_size
            self.state.entry_price = avg_entry
            self.state.position_value = total_size * avg_entry
            self.state.entries = entries
            self._sync_position_tracking()
            logger.info(
                f"🔄 Restored DRY multi-position: {total_size:.8f} {base_currency} "
                f"({self.state.raw_entry_count} entries, {self.state.logical_position_slots} logical slot, "
                f"avg ${avg_entry:,.2f})"
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
                self._stamp_latest_open_buy_target()
                logger.info(
                    f"🎯 Target SELL inicializado pela {reason_prefix}: ${new_target:,.2f} "
                    f"(+{ai_tp*100:.2f}% sobre avg ${self.state.entry_price:,.2f}) "
                    f"— {rag_adj.ai_take_profit_reason}"
                )
                return

            if new_target + 0.01 < old_target:
                self.state.target_sell_price = new_target
                self.state.target_sell_reason = rag_adj.ai_take_profit_reason
                self._stamp_latest_open_buy_target()
                logger.info(
                    f"🔄 Target SELL apertado pela {reason_prefix}: ${old_target:,.2f} → "
                    f"${new_target:,.2f} (+{ai_tp*100:.2f}%) — {rag_adj.ai_take_profit_reason}"
                )
        except Exception as e:
            logger.debug(f"Target SELL sync error: {e}")

    def _serialize_target_sell_metadata(self) -> Dict[str, Any]:
        """Serializa o target SELL atual para persistência em metadata."""
        if self.state.target_sell_price <= 0:
            return {}

        metadata: Dict[str, Any] = {
            "target_sell_price": round(float(self.state.target_sell_price), 2),
            "target_sell_trigger_price": round(float(self.state.target_sell_price), 2),
        }
        if self.state.target_sell_reason:
            metadata["target_sell_reason"] = self.state.target_sell_reason
        return metadata

    def _build_trade_metadata(
        self,
        base_metadata: Optional[Dict[str, Any]] = None,
        *,
        signal: Optional[Signal] = None,
        include_exit_reason: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Monta metadata persistida por trade com target e motivo de saída."""
        metadata: Dict[str, Any] = dict(base_metadata or {})
        metadata.update(self._serialize_target_sell_metadata())

        if include_exit_reason:
            exit_reason = (getattr(signal, "reason", "") or "").strip()
            if exit_reason:
                metadata["exit_reason"] = exit_reason[:240]

        return metadata or None

    def _stamp_latest_open_buy_target(self) -> None:
        """Atualiza o BUY aberto mais recente com o target SELL vigente."""
        target_metadata = self._serialize_target_sell_metadata()
        if not target_metadata:
            return

        try:
            trades = self.db.get_recent_trades(
                symbol=self.symbol,
                limit=50,
                include_dry=self.state.dry_run,
                profile=self._current_profile(),
            )
            for trade in trades:
                if trade.get("side") == "sell":
                    break
                if trade.get("side") == "buy" and trade.get("id"):
                    self.db.merge_trade_metadata(int(trade["id"]), target_metadata)
                    return
        except Exception as e:
            logger.debug(f"Target SELL stamp error: {e}")

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
            # Permite entradas com gap mais amplo durante regimes bullish e contexto limpo.
            if confidence >= 0.62 and has_news_bull and clean_context and (has_bid_buy or regime == "BULLISH"):
                return 0.0030
            return 0.0

        if profile == "conservative":
            # Conservador libera um pouco mais de tolerância em reversões claras.
            if confidence >= 0.66 and clean_context and is_oversold:
                return 0.0015
            return 0.0

        if regime == "BULLISH" and confidence >= 0.64 and clean_context and has_news_bull:
            return 0.0010

        return 0.0

    def _get_buy_target_uplift_pct(self, rag_adj, signal: Optional[Signal] = None) -> float:
        """Aproxima o buy target do mercado só nos cenários com melhor replay.

        Diferente da tolerância, o uplift move o próprio alvo efetivo de compra.
        Isso reduz o atraso do target em acelerações curtas, mas continua
        separado por profile e desligado em contexto bearish/conflitante.
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

        if context["strong_bearish"] or context["conflict"] or regime == "BEARISH":
            return 0.0

        if profile == "aggressive":
            if confidence >= 0.62 and has_news_bull and clean_context and has_bid_buy:
                return 0.0020
            return 0.0

        if profile == "conservative":
            if confidence >= 0.66 and clean_context and is_oversold:
                return 0.0008
            return 0.0

        return 0.0

    def _get_profile_min_net_profit_cfg(self) -> Dict[str, float]:
        """Retorna o lucro líquido mínimo efetivo por profile."""
        live_cfg = self._load_live_config()
        base_cfg = live_cfg.get("min_net_profit", {"usd": 0.01, "pct": 0.0005})
        base_usd = float(base_cfg.get("usd", 0.01) or 0.01)
        base_pct = float(base_cfg.get("pct", 0.0005) or 0.0005)
        profile = self._current_profile()

        if profile == "aggressive":
            return {
                "usd": round(max(base_usd * 0.8, 0.008), 4),
                "pct": max(base_pct * 0.8, 0.0004),
            }

        if profile == "conservative":
            return {
                "usd": round(max(base_usd * 1.2, 0.012), 4),
                "pct": max(base_pct * 1.2, 0.0006),
            }

        return {
            "usd": round(max(base_usd, 0.005), 4),
            "pct": max(base_pct, 0.0003),
        }

    def _get_profile_buy_profit_guard_base_cfg(self) -> Dict[str, float]:
        """Retorna o baseline do guard econômico por profile."""
        live_cfg = self._load_live_config()
        profile = self._current_profile()
        base_cfg = live_cfg.get("buy_profit_guard", {})
        min_edge_pct = float(base_cfg.get("min_projected_edge_pct", 0.0) or 0.0)
        min_window_slack_pct = float(base_cfg.get("min_window_slack_pct", 0.0) or 0.0)

        if min_edge_pct <= 0.0:
            min_edge_pct = 0.0050 if profile == "aggressive" else 0.0050 if profile == "conservative" else 0.0040
        if min_window_slack_pct <= 0.0:
            min_window_slack_pct = 0.0003 if profile == "aggressive" else 0.0003 if profile == "conservative" else 0.0002

        return {
            "min_projected_edge_pct": max(0.0, min_edge_pct),
            "min_window_slack_pct": max(0.0, min_window_slack_pct),
        }

    def _get_profile_buy_profit_guard_pressure(self, base_cfg: Dict[str, Any]) -> Dict[str, float]:
        """Resume a pressão de risco recente para apertar o BUY.

        Quanto pior o PnL realizado recente do profile, maior a pressão
        aplicada sobre o edge mínimo exigido e sobre a folga mínima da janela.
        """
        profile = self._current_profile()
        now = time.time()
        cache_ttl_sec = max(5.0, float(base_cfg.get("cache_ttl_sec", 20.0) or 20.0))
        cache = getattr(self, "_buy_profit_guard_cache", {}) or {}
        cache_key = (
            profile,
            round(float(base_cfg.get("performance_lookback_hours", 24.0) or 24.0), 2),
            int(base_cfg.get("recent_sell_window", 12) or 12),
            round(float(base_cfg.get("loss_budget_usd", 0.0) or 0.0), 6),
            round(float(base_cfg.get("avg_loss_pct_scale", 0.0) or 0.0), 6),
        )
        if (
            cache.get("key") == cache_key
            and float(cache.get("expires_at", 0.0) or 0.0) > now
            and isinstance(cache.get("data"), dict)
        ):
            return dict(cache["data"])

        lookback_hours = max(1.0, float(base_cfg.get("performance_lookback_hours", 24.0) or 24.0))
        recent_sell_window = max(4, int(base_cfg.get("recent_sell_window", 12) or 12))
        avg_loss_pct_scale = float(base_cfg.get("avg_loss_pct_scale", 0.0) or 0.0)
        if avg_loss_pct_scale <= 0.0:
            avg_loss_pct_scale = 0.0015 if profile == "aggressive" else 0.0010 if profile == "conservative" else 0.0011

        loss_budget_usd = float(base_cfg.get("loss_budget_usd", 0.0) or 0.0)

        lookback_since = now - (lookback_hours * 3600.0)
        recent_pnl = 0.0
        if hasattr(self.db, "get_pnl_since"):
            recent_pnl = float(
                self.db.get_pnl_since(
                    symbol=self.symbol,
                    since=lookback_since,
                    dry_run=self.state.dry_run,
                    profile=profile,
                ) or 0.0
            )

        recent_sells = []
        if hasattr(self.db, "get_recent_trades"):
            raw_trades = self.db.get_recent_trades(
                symbol=self.symbol,
                limit=max(recent_sell_window * 4, recent_sell_window + 8),
                include_dry=self.state.dry_run,
                profile=profile,
            ) or []
            for trade in raw_trades:
                if str(trade.get("side", "")).lower() != "sell":
                    continue
                pnl = trade.get("pnl")
                if pnl is None:
                    continue
                recent_sells.append(trade)
                if len(recent_sells) >= recent_sell_window:
                    break

        if loss_budget_usd <= 0.0:
            fallback_budget = 0.08 if profile == "aggressive" else 0.05 if profile == "conservative" else 0.06
            if recent_sells:
                median_abs_sell_pnl = statistics.median(abs(float(trade.get("pnl", 0.0) or 0.0)) for trade in recent_sells)
                history_multiplier = 10.0 if profile == "aggressive" else 8.0 if profile == "conservative" else 9.0
                loss_budget_usd = max(fallback_budget, median_abs_sell_pnl * history_multiplier)
            else:
                loss_budget_usd = fallback_budget

        sell_count = len(recent_sells)
        losing_sells = 0
        losing_streak = 0
        recent_sells_pnl = 0.0
        avg_pnl_pct = 0.0
        if sell_count:
            pct_sum = 0.0
            for idx, trade in enumerate(recent_sells):
                pnl = float(trade.get("pnl", 0.0) or 0.0)
                # btc.trades.pct é persistido em pontos percentuais; converter para fração.
                pnl_pct = float(trade.get("pnl_pct", 0.0) or 0.0) / 100.0
                recent_sells_pnl += pnl
                pct_sum += pnl_pct
                if pnl < 0:
                    losing_sells += 1
                    if idx == losing_streak:
                        losing_streak += 1
            avg_pnl_pct = pct_sum / sell_count

        day_loss_pressure = max(0.0, -recent_pnl) / (max(0.0, -recent_pnl) + max(loss_budget_usd, 0.0001))
        recent_loss_pressure = max(0.0, -recent_sells_pnl) / (max(0.0, -recent_sells_pnl) + max(loss_budget_usd * 0.8, 0.0001))
        loss_rate_pressure = (losing_sells / sell_count) if sell_count else 0.0
        streak_pressure = min(losing_streak / 6.0, 1.0)
        avg_loss_pct_pressure = max(0.0, -avg_pnl_pct) / (max(0.0, -avg_pnl_pct) + max(avg_loss_pct_scale, 0.0001))

        pressure = min(
            1.0,
            (day_loss_pressure * 0.32)
            + (recent_loss_pressure * 0.24)
            + (loss_rate_pressure * 0.18)
            + (streak_pressure * 0.16)
            + (avg_loss_pct_pressure * 0.10),
        )

        data = {
            "pressure": round(pressure, 4),
            "recent_pnl": round(recent_pnl, 6),
            "recent_sells_pnl": round(recent_sells_pnl, 6),
            "sell_count": sell_count,
            "losing_sells": losing_sells,
            "losing_streak": losing_streak,
            "avg_pnl_pct": round(avg_pnl_pct, 6),
            "loss_budget_usd": round(loss_budget_usd, 6),
            "lookback_hours": lookback_hours,
            "recent_sell_window": recent_sell_window,
        }
        self._buy_profit_guard_cache = {
            "key": cache_key,
            "expires_at": now + cache_ttl_sec,
            "data": dict(data),
        }
        return data

    def _get_profile_buy_profit_guard_cfg(self) -> Dict[str, float]:
        """Retorna o edge mínimo projetado para aceitar novos BUYs."""
        live_cfg = self._load_live_config()
        profile = self._current_profile()
        base_cfg = live_cfg.get("buy_profit_guard", {})
        base_guard = self._get_profile_buy_profit_guard_base_cfg()
        performance = self._get_profile_buy_profit_guard_pressure(base_cfg)
        pressure = float(performance["pressure"])

        max_extra_edge_pct = float(base_cfg.get("max_extra_projected_edge_pct", 0.0) or 0.0)
        max_extra_window_slack_pct = float(base_cfg.get("max_extra_window_slack_pct", 0.0) or 0.0)
        if max_extra_edge_pct <= 0.0:
            max_extra_edge_pct = 0.0030 if profile == "aggressive" else 0.0035 if profile == "conservative" else 0.0025
        if max_extra_window_slack_pct <= 0.0:
            max_extra_window_slack_pct = 0.0008 if profile == "aggressive" else 0.0010 if profile == "conservative" else 0.0007

        return {
            "base_min_projected_edge_pct": base_guard["min_projected_edge_pct"],
            "base_min_window_slack_pct": base_guard["min_window_slack_pct"],
            "min_projected_edge_pct": max(0.0, base_guard["min_projected_edge_pct"] + (max_extra_edge_pct * pressure)),
            "min_window_slack_pct": max(0.0, base_guard["min_window_slack_pct"] + (max_extra_window_slack_pct * pressure)),
            "pressure": pressure,
            "recent_pnl": performance["recent_pnl"],
            "recent_sells_pnl": performance["recent_sells_pnl"],
            "sell_count": performance["sell_count"],
            "losing_sells": performance["losing_sells"],
            "losing_streak": performance["losing_streak"],
            "avg_pnl_pct": performance["avg_pnl_pct"],
        }

    def _should_allow_low_net_profit_sell(
        self,
        price: float,
        signal: Signal,
        rag_adj,
        force: bool = False,
    ) -> bool:
        """Permite SELL fraco só em contexto de proteção real."""
        if force:
            return True

        live_cfg = self._load_live_config()
        stop_loss_pct = float(live_cfg.get("stop_loss_pct", _config.get("stop_loss_pct", 0.02)))
        stop_loss_price = self.state.entry_price * (1 - stop_loss_pct)
        if price <= stop_loss_price:
            return True

        if rag_adj is None:
            return False

        context = self._analyze_signal_context(rag_adj, signal)
        regime = getattr(rag_adj, "suggested_regime", "RANGING")
        return regime == "BEARISH" or context["strong_bearish"]

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

        if signal.action == "SELL":
            guardrail_sell = self._get_guardrail_sell_verdict(signal.price)
            if guardrail_sell is not None:
                if guardrail_sell["allow"]:
                    logger.info(
                        f"🛡️ Guardrail preserved threshold SELL: "
                        f"net ${guardrail_sell['net_profit']:.4f} "
                        f"({guardrail_sell['net_pnl_pct']*100:.2f}% >= {guardrail_sell['min_sell_pnl_pct']*100:.2f}%) "
                        f"(gross ${guardrail_sell['gross_pnl']:.4f}, fees ${guardrail_sell['total_fees']:.4f})"
                    )
                    return True
                logger.info(
                    f"🛑 Guardrail blocked sub-threshold SELL: "
                    f"net ${guardrail_sell['net_profit']:.4f} "
                    f"({guardrail_sell['net_pnl_pct']*100:.2f}% < {guardrail_sell['min_sell_pnl_pct']*100:.2f}%) "
                    f"(gross ${guardrail_sell['gross_pnl']:.4f}, fees ${guardrail_sell['total_fees']:.4f})"
                )
                return False

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
            buy_limits = self._resolve_buy_gate_limits(rag_adj, signal)
            ai_buy_target = buy_limits["ai_buy_target"]
            extra_discount_pct = buy_limits["extra_discount_pct"]
            uplift_pct = buy_limits["uplift_pct"]
            tolerance_pct = buy_limits["tolerance_pct"]
            effective_buy_target = buy_limits["effective_buy_target"]
            effective_buy_ceiling = buy_limits["effective_buy_ceiling"]
            trade_window = buy_limits["trade_window"]
            window_entry_low = buy_limits["window_entry_low"]
            window_entry_high = buy_limits["window_entry_high"]
            used_trade_window = buy_limits["used_trade_window"]
            profit_guard = self._get_profile_buy_profit_guard_cfg()
            projected_target_sell = 0.0
            if trade_window:
                projected_target_sell = float(trade_window.get("target_sell", 0.0) or 0.0)
            if projected_target_sell <= 0.0:
                take_profit_pct = max(float(getattr(rag_adj, "ai_take_profit_pct", 0.0) or 0.0), TRADING_FEE_PCT * 2.4)
                projected_target_sell = signal.price * (1 + take_profit_pct)

            projected_edge_pct = 0.0
            if projected_target_sell > signal.price > 0:
                projected_edge_pct = (projected_target_sell / signal.price) - 1.0

            if projected_edge_pct < profit_guard["min_projected_edge_pct"]:
                logger.info(
                    f"🧮 BUY blocked (projected edge): alvo ${projected_target_sell:,.2f} "
                    f"projeta +{projected_edge_pct*100:.2f}% < mínimo "
                    f"{profit_guard['min_projected_edge_pct']*100:.2f}% "
                    f"[guard pressure {profit_guard['pressure']*100:.0f}%, "
                    f"PnL {profit_guard['recent_pnl']:+.4f}, streak {int(profit_guard['losing_streak'])}]"
                )
                return False

            if used_trade_window and window_entry_high > 0:
                window_slack_pct = max(0.0, (window_entry_high - signal.price) / signal.price)
                if window_slack_pct < profit_guard["min_window_slack_pct"]:
                    logger.info(
                        f"🪟 BUY blocked (window chase): preço ${signal.price:,.2f} muito perto "
                        f"do teto ${window_entry_high:,.2f} "
                        f"(folga {window_slack_pct*100:.2f}% < "
                        f"{profit_guard['min_window_slack_pct']*100:.2f}% | "
                        f"guard pressure {profit_guard['pressure']*100:.0f}%)"
                    )
                    return False

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
                    adjust_label = f", ajuste {uplift_pct*100:.2f}%" if uplift_pct > 0 else ""
                    window_label = ""
                    if trade_window and window_entry_high > 0:
                        window_label = (
                            f", janela ${window_entry_low:,.2f}-${window_entry_high:,.2f}"
                            if window_entry_low > 0 else
                            f", janela <= ${window_entry_high:,.2f}"
                        )
                    logger.info(
                        f"🔒 BUY blocked (AI target): preço ${signal.price:,.2f} > "
                        f"alvo ${effective_buy_target:,.2f} (+{diff_pct:.2f}%) "
                        f"[tol {tolerance_pct*100:.2f}%{adjust_label}{window_label}] — "
                        f"{rag_adj.ai_buy_target_reason}"
                    )
                return False
            elif effective_buy_target > 0 and signal.price <= effective_buy_ceiling:
                target_label = (
                    f"alvo defensivo ${effective_buy_target:,.2f}"
                    if extra_discount_pct > 0 else
                    f"alvo ${effective_buy_target:,.2f}"
                )
                if uplift_pct > 0:
                    target_label += f" (base +{uplift_pct*100:.2f}%)"
                if tolerance_pct > 0 and signal.price > effective_buy_target:
                    target_label += f" + tolerância {tolerance_pct*100:.2f}%"
                if used_trade_window and window_entry_high > 0:
                    if window_entry_low > 0:
                        target_label += f" + janela ${window_entry_low:,.2f}-${window_entry_high:,.2f}"
                    else:
                        target_label += f" + janela <= ${window_entry_high:,.2f}"
                logger.info(
                    f"🔓 BUY permitido pela IA: preço ${signal.price:,.2f} <= "
                    f"{target_label} ({rag_adj.ai_buy_target_reason})"
                )
                self.state.last_sell_entry_price = 0.0

        # ── Multi-posição: verificar se atingiu limite de entradas ──
        max_positions = controls.effective_max_positions
        logical_slots = int(getattr(self.state, "logical_position_slots", getattr(self.state, "position_count", 0)) or 0)
        raw_entries = int(getattr(self.state, "raw_entry_count", getattr(self.state, "position_count", 0)) or 0)
        if signal.action == "BUY" and self.state.position > 0 and self.state.entry_price > 0:
            rebuy_discount_pct = self._get_rebuy_discount_pct()
            rebuy_trigger_price = self.state.entry_price * (1.0 - rebuy_discount_pct)
            current_discount_pct = ((self.state.entry_price - signal.price) / self.state.entry_price) if self.state.entry_price > 0 else 0.0
            if signal.price > rebuy_trigger_price:
                # Preço ainda acima do gatilho — resetar rastreamento de vale
                if self.state.dca_valley_low > 0:
                    self.state.dca_valley_low = 0.0
                logger.info(
                    f"📉 BUY blocked (rebuy discount not reached): preço ${signal.price:,.2f} > "
                    f"gatilho ${rebuy_trigger_price:,.2f} "
                    f"(avg ${self.state.entry_price:,.2f}, desconto atual {current_discount_pct*100:.2f}% "
                    f"< {rebuy_discount_pct*100:.2f}%)"
                )
                return False

            # ── Valley bounce: rastrear fundo e exigir recuperação mínima ──
            # Atualizar o mínimo do vale desde que o preço cruzou o gatilho
            if self.state.dca_valley_low <= 0 or signal.price < self.state.dca_valley_low:
                self.state.dca_valley_low = signal.price
                logger.debug(
                    f"🕳️ DCA valley low atualizado: ${self.state.dca_valley_low:,.2f}"
                )

            valley_bounce_pct = float(self._load_live_config().get("dca_valley_bounce_pct", DCA_VALLEY_BOUNCE_PCT))
            valley_bounce_trigger = self.state.dca_valley_low * (1.0 + valley_bounce_pct)
            bounce_from_low = ((signal.price - self.state.dca_valley_low) / self.state.dca_valley_low) if self.state.dca_valley_low > 0 else 0.0

            if signal.price < valley_bounce_trigger:
                logger.info(
                    f"🕳️ BUY blocked (aguardando bounce do vale): preço ${signal.price:,.2f} < "
                    f"bounce_trigger ${valley_bounce_trigger:,.2f} "
                    f"(vale ${self.state.dca_valley_low:,.2f}, bounce atual {bounce_from_low*100:.3f}% "
                    f"< {valley_bounce_pct*100:.2f}% exigido)"
                )
                return False

            logger.info(
                f"🪜 BUY rebuy unlocked (valley bounce confirmado): preço ${signal.price:,.2f} "
                f"bounce={bounce_from_low*100:.3f}% >= {valley_bounce_pct*100:.2f}% "
                f"(vale ${self.state.dca_valley_low:,.2f}, avg ${self.state.entry_price:,.2f}, "
                f"desconto {current_discount_pct*100:.2f}%)"
            )
            if logical_slots >= max_positions:
                logger.info(
                    f"📦 Max positions reached ({logical_slots}/{max_positions}) "
                    f"[raw_entries:{raw_entries}, cap:{controls.max_positions_cap}, mode:{controls.ollama_mode}]"
                )
                return False
        elif signal.action == "BUY" and logical_slots >= max_positions:
            logger.info(
                f"📦 Max positions reached ({logical_slots}/{max_positions}) "
                f"[raw_entries:{raw_entries}, cap:{controls.max_positions_cap}, mode:{controls.ollama_mode}]"
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
        day_limits = self._get_runtime_trade_day_limits()
        max_daily = int(day_limits["max_daily_trades"])
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
        max_daily_loss = float(day_limits["max_daily_loss"])
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
            self.state.buy_success_pressure = 0.0
            self.state.buy_success_factor = 1.0
            self.state.buy_dynamic_batch_cap_usdt = 0.0
            caps = self._get_runtime_risk_caps()
            quote_cur = self.symbol.split("-")[1]  # USDT, BRL, etc.
            usdt_balance = get_balance(quote_cur) if not self.state.dry_run else 1000
            # Profile allocation: aplicar % do saldo alocado ao perfil
            usdt_balance = self._apply_profile_allocation(usdt_balance)
            rag_adj = self.market_rag.get_current_adjustment()
            controls = self._resolve_trade_controls(rag_adj)
            ai_controlled = controls.ai_controlled
            max_positions = max(1, int(controls.effective_max_positions or 1))

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

            batch_limit = self._resolve_dynamic_buy_batch_limit(remaining_exposure)
            final_amount = min(
                amount,
                batch_limit["dynamic_batch_cap_usdt"],
                remaining_exposure,
                usdt_balance * 0.95,
            )
            if final_amount < amount:
                logger.info(
                    f"🧮 BUY capped by dynamic batch limit: ${amount:.2f} -> ${final_amount:.2f} "
                    f"(pressure={batch_limit['pressure']:.2f}, success_factor={batch_limit['success_factor']:.2f}, "
                    f"batch_cap=${batch_limit['dynamic_batch_cap_usdt']:.2f}, remaining_exposure=${remaining_exposure:.2f})"
                )

            return final_amount
        
        elif signal.action == "SELL":
            size = self.state.position
            if size <= 0:
                return 0

            guardrail_sell = self._get_guardrail_sell_verdict(price)
            if guardrail_sell is not None:
                if guardrail_sell["allow"]:
                    logger.info(
                        f"🛡️ Guardrail approved threshold SELL execution: "
                        f"net ${guardrail_sell['net_profit']:.4f} "
                        f"({guardrail_sell['net_pnl_pct']*100:.2f}% >= {guardrail_sell['min_sell_pnl_pct']*100:.2f}%) "
                        f"(gross ${guardrail_sell['gross_pnl']:.4f}, fees ${guardrail_sell['total_fees']:.4f})"
                    )
                    return self.state.position
                logger.info(
                    f"🛑 Guardrail rejected sub-threshold SELL execution: "
                    f"net ${guardrail_sell['net_profit']:.4f} "
                    f"({guardrail_sell['net_pnl_pct']*100:.2f}% < {guardrail_sell['min_sell_pnl_pct']*100:.2f}%) "
                    f"(gross ${guardrail_sell['gross_pnl']:.4f}, fees ${guardrail_sell['total_fees']:.4f})"
                )
                return 0

            # Auto-exit (SL/TP) bypasses sell guards quando não há guardrail ativo.
            if force:
                return self.state.position

            # Fee check: estimar taxas antes de enviar ordem de venda
            sell_outcome = self._estimate_sell_outcome(price)
            gross_sell = sell_outcome["gross_sell"]
            total_fees = sell_outcome["total_fees"]
            pnl = sell_outcome["gross_pnl"]
            net_profit = sell_outcome["net_profit"]

            # Min net profit: lucro líquido mínimo (após fees), separado por profile.
            mnp_cfg = self._get_profile_min_net_profit_cfg()
            min_usd = mnp_cfg.get("usd", 0.01)
            min_pct_val = gross_sell * mnp_cfg.get("pct", 0.0005)
            min_required = max(min_usd, min_pct_val)

            rag_adj = None
            if getattr(self, "market_rag", None) is not None:
                try:
                    rag_adj = self.market_rag.get_current_adjustment()
                except Exception as exc:
                    logger.debug(f"Current RAG lookup failed during SELL fee-check: {exc}")

            if net_profit < min_required:
                if self._should_allow_low_net_profit_sell(price, signal, rag_adj, force=force):
                    logger.info(
                        f"⚡ SELL low net profit allowed: ${net_profit:.4f} < min ${min_required:.4f} "
                        f"(gross ${pnl:.4f}, fees ${total_fees:.4f})"
                    )
                else:
                    logger.info(
                        f"🔒 SELL blocked (net profit): ${net_profit:.4f} < min ${min_required:.4f} "
                        f"(gross ${pnl:.4f}, fees ${total_fees:.4f})"
                    )
                    return 0

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
                    self.state.entries.append({"price": price, "size": size, "ts": time.time()})
                    self._sync_position_tracking()
                    # Resetar rastreamento de vale após BUY executado (nova referência de fundo)
                    self.state.dca_valley_low = 0.0
                    
                    logger.info(
                        f"📊 Position: {self.state.position:.6f} BTC "
                        f"({self.state.raw_entry_count} entries, {self.state.logical_position_slots} logical slot, "
                        f"avg ${self.state.entry_price:,.2f})"
                    )
                    
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

                    trade_metadata = self._build_trade_metadata(trade_metadata)
                    
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

                    trade_metadata = self._build_trade_metadata(
                        trade_metadata,
                        signal=signal,
                        include_exit_reason=True,
                    )
                    
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
                    self.state.entries = []
                    self.state.target_sell_price = 0.0
                    self.state.target_sell_reason = ""
                    self.state.buy_success_pressure = 0.0
                    self.state.buy_success_factor = 1.0
                    self.state.buy_dynamic_batch_cap_usdt = 0.0
                    self._sync_position_tracking()
                
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
                        _quote_cur = self.symbol.split("-")[1]
                        usdt_bal = get_balance(_quote_cur) if not self.state.dry_run else 1000
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
                    base_currency = self.symbol.split("-")[0]
                    pos_info = (f"Position: {self.state.position:.6f} {base_currency} ({self.state.position_count} entries, avg ${self.state.entry_price:,.2f})"
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
                    trade_window = self._get_fresh_ai_trade_window()
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
                    if trade_window:
                        age_sec = max(0.0, time.time() - float(trade_window.get("timestamp", time.time())))
                        ai_info += (
                            f", window=${float(trade_window.get('entry_low', 0.0) or 0.0):,.2f}"
                            f"-${float(trade_window.get('entry_high', 0.0) or 0.0):,.2f}"
                            f" age={age_sec:.0f}s"
                        )
                    else:
                        ai_info += ", window=stale"
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
                trade_window_regime_changed = bool(self._last_ai_trade_window_regime and regime_now and regime_now != self._last_ai_trade_window_regime)
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

                trade_window_trigger = ""
                if rss_triggered_plan:
                    trade_window_trigger = "rss"
                elif trade_window_regime_changed:
                    trade_window_trigger = "regime_change"
                elif (time.time() - self._last_ai_trade_window_trigger_ts) >= self._get_trade_window_settings()["min_interval_sec"]:
                    trade_window_trigger = "periodic"

                if trade_window_trigger:
                    self._last_ai_trade_window_trigger_ts = time.time()
                    if trade_window_trigger == "regime_change":
                        logger.info(
                            f"🧭 Market regime changed {self._last_ai_trade_window_regime or '-'} → {regime_now} — refreshing AI trade window"
                        )
                    elif trade_window_trigger == "rss":
                        logger.info("📰 New RSS received — refreshing AI trade window")
                    threading.Thread(
                        target=self._generate_ai_trade_window,
                        args=(market_state, trade_window_trigger),
                        daemon=True,
                    ).start()
                if regime_now:
                    self._last_ai_trade_window_regime = regime_now

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
            _quote_cur = self.symbol.split("-")[1]
            usdt_bal = get_balance(_quote_cur) if not self.state.dry_run else 1000
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
    explicit_config = _explicit_runtime_config_requested(config_name)
    if config_path.exists():
        try:
            _loaded_cfg = _read_json_config(config_path)
        except Exception as exc:
            logger.error(f"❌ Failed to parse config file {config_path}: {exc}")
            if explicit_config:
                sys.exit(2)
    elif explicit_config:
        logger.error(f"❌ Required config file missing: {config_path}")
        sys.exit(2)
    
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
    dry_run = _resolve_process_dry_run(args.live, _loaded_cfg)
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
