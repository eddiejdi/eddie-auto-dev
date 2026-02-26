#!/usr/bin/env python3
"""
Multi-Coin Trading Agent - Deployment Script
Creates all necessary configs, patches, and services for multi-coin support.
Run on homelab: python3 deploy_multi_coin.py
"""

import os
import sys
import json
import shutil
from pathlib import Path

BASE_DIR = Path("/home/homelab/myClaude/btc_trading_agent")
MONITORING_DIR = Path("/home/homelab/monitoring")

# ============================================================
# COIN REGISTRY
# ============================================================
COINS = [
    {
        "symbol": "BTC-USDT",
        "enabled": True,
        "capital": 100.0,
        "api_port": 8511,
        "metrics_port": 9092,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.03,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "min_spread_bps": 5,
        "min_trade_amount": 1,
        "max_volatility": 0.05,
        "trailing_activation": 0.015,
        "trailing_trail": 0.008,
        "existing": True
    },
    {
        "symbol": "ETH-USDT",
        "enabled": True,
        "capital": 50.0,
        "api_port": 8512,
        "metrics_port": 9093,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.03,
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "min_spread_bps": 5,
        "min_trade_amount": 5,
        "max_volatility": 0.06,
        "trailing_activation": 0.015,
        "trailing_trail": 0.008,
        "existing": False
    },
    {
        "symbol": "XRP-USDT",
        "enabled": True,
        "capital": 50.0,
        "api_port": 8513,
        "metrics_port": 9094,
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.04,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "min_spread_bps": 8,
        "min_trade_amount": 5,
        "max_volatility": 0.08,
        "trailing_activation": 0.02,
        "trailing_trail": 0.01,
        "existing": False
    },
    {
        "symbol": "SOL-USDT",
        "enabled": True,
        "capital": 50.0,
        "api_port": 8514,
        "metrics_port": 9095,
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.05,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "min_spread_bps": 10,
        "min_trade_amount": 5,
        "max_volatility": 0.10,
        "trailing_activation": 0.025,
        "trailing_trail": 0.012,
        "existing": False
    },
    {
        "symbol": "DOGE-USDT",
        "enabled": True,
        "capital": 50.0,
        "api_port": 8515,
        "metrics_port": 9096,
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.05,
        "rsi_oversold": 25,
        "rsi_overbought": 75,
        "min_spread_bps": 15,
        "min_trade_amount": 5,
        "max_volatility": 0.12,
        "trailing_activation": 0.03,
        "trailing_trail": 0.015,
        "existing": False
    },
    {
        "symbol": "ADA-USDT",
        "enabled": True,
        "capital": 50.0,
        "api_port": 8516,
        "metrics_port": 9097,
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.04,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "min_spread_bps": 10,
        "min_trade_amount": 5,
        "max_volatility": 0.08,
        "trailing_activation": 0.02,
        "trailing_trail": 0.01,
        "existing": False
    }
]

def symbol_safe(symbol: str) -> str:
    """BTC-USDT -> BTC_USDT"""
    return symbol.replace("-", "_")

def symbol_lower(symbol: str) -> str:
    """BTC-USDT -> btc_usdt"""
    return symbol.replace("-", "_").lower()

# ============================================================
# 1. CREATE coins.json
# ============================================================
def create_coins_json():
    print("📋 Creating coins.json...")
    coins_file = BASE_DIR / "coins.json"
    with open(coins_file, "w") as f:
        json.dump(COINS, f, indent=2)
    print(f"   ✅ {coins_file}")

# ============================================================
# 2. CREATE per-coin config files
# ============================================================
def create_coin_configs():
    print("\n📝 Creating per-coin configs...")
    for coin in COINS:
        sym = coin["symbol"]
        safe = symbol_safe(sym)
        config_file = BASE_DIR / f"config_{safe}.json"
        
        # Skip BTC — it uses config.json directly
        if coin.get("existing"):
            print(f"   ⏭️  {sym}: using existing config.json")
            continue
        
        config = {
            "enabled": coin["enabled"],
            "dry_run": True,  # Start in dry-run mode for safety
            "symbol": sym,
            "poll_interval": 5,
            "min_trade_interval": 180,
            "min_confidence": 0.6,
            "min_trade_amount": coin["min_trade_amount"],
            "max_position_pct": 0.8,
            "stop_loss_pct": coin["stop_loss_pct"],
            "take_profit_pct": coin["take_profit_pct"],
            "max_daily_trades": 0,
            "max_daily_loss": 75,
            "trading_hours": {
                "enabled": False,
                "start": "09:00",
                "end": "22:00"
            },
            "notifications": {
                "enabled": True,
                "telegram_chat_id": "",
                "whatsapp_chat_id": "5511981193899@c.us",
                "on_trade": True,
                "on_signal": False,
                "on_error": True
            },
            "risk_management": {
                "enabled": True,
                "max_drawdown_pct": 0.1,
                "position_sizing": "dynamic",
                "kelly_fraction": 0.25,
                "volatility_filter": True,
                "min_volatility": 0.001,
                "max_volatility": coin["max_volatility"]
            },
            "trailing_stop": {
                "enabled": True,
                "activation_pct": coin["trailing_activation"],
                "trail_pct": coin["trailing_trail"]
            },
            "strategy": {
                "mode": "scalping",
                "use_trend_filter": True,
                "use_volume_filter": True,
                "rsi_oversold": coin["rsi_oversold"],
                "rsi_overbought": coin["rsi_overbought"],
                "min_spread_bps": coin["min_spread_bps"]
            },
            "live_mode": False,
            "initial_capital": coin["capital"]
        }
        
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
        print(f"   ✅ {config_file.name} ({sym}, ${coin['capital']})")

# ============================================================
# 3. PATCH trading_engine.py — Support per-coin config path
# ============================================================
def patch_trading_engine():
    print("\n🔧 Patching trading_engine.py...")
    engine_file = BASE_DIR / "trading_engine.py"
    content = engine_file.read_text()
    
    # Replace the config loading to support COIN_CONFIG_FILE env var
    old_config_block = '''CONFIG_FILE = ENGINE_DIR / "config.json"'''
    new_config_block = '''# Config: use COIN_CONFIG_FILE env var for multi-coin, fallback to config.json
_config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
CONFIG_FILE = ENGINE_DIR / _config_name'''
    
    if old_config_block in content:
        content = content.replace(old_config_block, new_config_block)
        print("   ✅ CONFIG_FILE now reads from COIN_CONFIG_FILE env var")
    else:
        print("   ⏭️  CONFIG_FILE already patched or different format")
    
    # Replace singleton to support multi-instance via symbol key
    old_singleton = '''_engine: Optional[TradingEngine] = None

def get_engine() -> TradingEngine:
    """Obtém instância do engine"""
    global _engine
    if _engine is None:
        _engine = TradingEngine()
    return _engine'''
    
    new_singleton = '''_engines: Dict[str, TradingEngine] = {}

def get_engine(config_file: str = None) -> TradingEngine:
    """Obtém instância do engine (uma por config/symbol)"""
    global _engines
    key = config_file or os.environ.get("COIN_CONFIG_FILE", "config.json")
    if key not in _engines:
        _engines[key] = TradingEngine()
    return _engines[key]'''
    
    if old_singleton in content:
        content = content.replace(old_singleton, new_singleton)
        print("   ✅ Singleton replaced with multi-instance dict")
    else:
        print("   ⏭️  Singleton already patched")
    
    engine_file.write_text(content)

# ============================================================
# 4. PATCH trading_agent.py — Add --config, --api-port, --metrics-port
# ============================================================
def patch_trading_agent():
    print("\n🔧 Patching trading_agent.py...")
    agent_file = BASE_DIR / "trading_agent.py"
    content = agent_file.read_text()
    
    # Add --config flag to CLI
    old_cli = '''    parser.add_argument("--symbol", default="BTC-USDT", help="Trading pair")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Dry run mode (no real trades)")
    parser.add_argument("--live", action="store_true",
                       help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon")'''
    
    new_cli = '''    parser.add_argument("--symbol", default=None, help="Trading pair (overrides config)")
    parser.add_argument("--config", default=None, help="Config file name (e.g. config_ETH_USDT.json)")
    parser.add_argument("--api-port", type=int, default=None, help="Engine API port")
    parser.add_argument("--metrics-port", type=int, default=None, help="Prometheus metrics port")
    parser.add_argument("--dry-run", action="store_true", default=True,
                       help="Dry run mode (no real trades)")
    parser.add_argument("--live", action="store_true",
                       help="Live trading mode (real money!)")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon")'''
    
    if old_cli in content:
        content = content.replace(old_cli, new_cli)
        print("   ✅ CLI flags added: --config, --api-port, --metrics-port")
    else:
        print("   ⏭️  CLI flags already patched")
    
    # After parser block, add config loading logic
    old_parse = '''    args = parser.parse_args()
    
    # Verificar credenciais para modo live
    dry_run = not args.live'''
    
    new_parse = '''    args = parser.parse_args()
    
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
    dry_run = not args.live'''
    
    if old_parse in content:
        content = content.replace(old_parse, new_parse)
        print("   ✅ Config/symbol loading logic added")
    else:
        print("   ⏭️  Config loading already patched")
    
    # Also replace DEFAULT_SYMBOL usage to support env var
    old_default = '''DEFAULT_SYMBOL = "BTC-USDT"'''
    new_default = '''# Default symbol — can be overridden by config file or CLI
_config_file = os.environ.get("COIN_CONFIG_FILE", "config.json")
_config_path = Path(__file__).parent / _config_file
try:
    with open(_config_path) as _cf:
        _config = json.load(_cf)
    DEFAULT_SYMBOL = _config.get("symbol", "BTC-USDT")
except Exception:
    DEFAULT_SYMBOL = "BTC-USDT"'''
    
    if 'DEFAULT_SYMBOL = "BTC-USDT"' in content and '_config_file = os.environ.get' not in content:
        content = content.replace(old_default, new_default, 1)
        print("   ✅ DEFAULT_SYMBOL now reads from config")
    else:
        print("   ⏭️  DEFAULT_SYMBOL already patched")
    
    agent_file.write_text(content)

# ============================================================
# 5. PATCH engine_api.py — Support multi-coin via env
# ============================================================
def patch_engine_api():
    print("\n🔧 Patching engine_api.py...")
    api_file = BASE_DIR / "engine_api.py"
    content = api_file.read_text()
    
    # The API already reads port from BTC_ENGINE_API_PORT env var — good!
    # Just need to make sure get_engine() uses the right config
    # Already handled via COIN_CONFIG_FILE env var in trading_engine.py
    
    # Also update the import to handle the patched get_engine
    if "from trading_engine import get_engine" in content:
        print("   ✅ engine_api.py already imports get_engine (will use COIN_CONFIG_FILE)")
    
    print("   ✅ No changes needed — uses BTC_ENGINE_API_PORT env var already")

# ============================================================
# 6. PATCH prometheus_exporter.py — Support env var for port & symbol
# ============================================================
def patch_prometheus_exporter():
    print("\n🔧 Patching prometheus_exporter.py...")
    exporter_file = BASE_DIR / "prometheus_exporter.py"
    content = exporter_file.read_text()
    
    # Patch the hardcoded BTC-USDT in _fetch_live_price
    old_fetch = '''    def _fetch_live_price(self) -> float:
        """Busca preço BTC-USDT ao vivo via KuCoin API"""
        try:
            req = urllib.request.Request(
                "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT",
                headers={"User-Agent": "AutoCoinBot-Exporter/2.1"}
            )'''
    
    new_fetch = '''    def _fetch_live_price(self) -> float:
        """Busca preço ao vivo via KuCoin API"""
        try:
            symbol = self.symbol
            req = urllib.request.Request(
                f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={symbol}",
                headers={"User-Agent": "AutoCoinBot-Exporter/2.1"}
            )'''
    
    if old_fetch in content:
        content = content.replace(old_fetch, new_fetch)
        print("   ✅ _fetch_live_price now uses self.symbol")
    else:
        print("   ⏭️  _fetch_live_price already patched")
    
    # Add symbol attribute to MetricsCollector.__init__
    old_init = '''    def __init__(self, db_path: str):
        self.db_path = db_path'''
    
    new_init = '''    def __init__(self, db_path: str, symbol: str = "BTC-USDT"):
        self.db_path = db_path
        self.symbol = symbol'''
    
    if old_init in content and 'symbol: str = "BTC-USDT"' not in content:
        content = content.replace(old_init, new_init)
        print("   ✅ MetricsCollector now accepts symbol parameter")
    else:
        print("   ⏭️  MetricsCollector already has symbol")
    
    # Patch main() to read port and symbol from env
    old_main = '''def main():
    """Main function"""
    port = 9092'''
    
    new_main = '''def main():
    """Main function"""
    port = int(os.environ.get("METRICS_PORT", "9092"))
    
    # Load symbol from config
    config_name = os.environ.get("COIN_CONFIG_FILE", "config.json")
    config_path = BASE_DIR / config_name
    _symbol = "BTC-USDT"
    try:
        with open(config_path) as _f:
            _cfg = json.load(_f)
            _symbol = _cfg.get("symbol", "BTC-USDT")
    except Exception:
        pass
    os.environ.setdefault("COIN_SYMBOL", _symbol)'''
    
    if old_main in content:
        content = content.replace(old_main, new_main)
        print("   ✅ main() port from METRICS_PORT env, symbol from config")
    else:
        print("   ⏭️  main() already patched")
    
    # Also patch where MetricsCollector is instantiated in the handler
    # Find where collector = MetricsCollector(DB_PATH) is used
    if "MetricsCollector(DB_PATH)" in content and "MetricsCollector(DB_PATH, " not in content:
        # Need to find all instances and add symbol
        content = content.replace(
            "MetricsCollector(DB_PATH)",
            'MetricsCollector(DB_PATH, os.environ.get("COIN_SYMBOL", "BTC-USDT"))'
        )
        print("   ✅ MetricsCollector instances now pass symbol")
    else:
        print("   ⏭️  MetricsCollector instances already patched")
    
    # Add symbol label to metric names output — prefix metrics with generic name
    # Replace btc_price metric name with crypto_price{symbol="X"}
    # This is a bigger change in send_metrics - let's add symbol label to output
    
    exporter_file.write_text(content)

# ============================================================
# 7. CREATE systemd template units
# ============================================================
def create_systemd_units():
    print("\n🔧 Creating systemd template units...")
    
    # Template for trading agent
    agent_template = '''[Unit]
Description=Crypto Trading Agent - %I
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=homelab
Group=homelab
WorkingDirectory=/home/homelab/myClaude/btc_trading_agent
Environment=PATH=/home/homelab/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
Environment=COIN_CONFIG_FILE=config_%I.json

ExecStart=/usr/bin/python3 /home/homelab/myClaude/btc_trading_agent/trading_agent.py --daemon --config config_%I.json
ExecStop=/bin/kill -SIGTERM $MAINPID

Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=120

StandardOutput=journal
StandardError=journal
SyslogIdentifier=crypto-agent-%I

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/homelab/myClaude/btc_trading_agent

[Install]
WantedBy=multi-user.target
'''
    
    # Template for engine API
    api_template = '''[Unit]
Description=Crypto Trading Engine API - %I
After=network.target crypto-agent@%I.service

[Service]
Type=simple
User=homelab
Group=homelab
WorkingDirectory=/home/homelab/myClaude/btc_trading_agent
Environment=PATH=/home/homelab/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONUNBUFFERED=1
Environment=COIN_CONFIG_FILE=config_%I.json

ExecStart=/usr/bin/python3 /home/homelab/myClaude/btc_trading_agent/engine_api.py
ExecStop=/bin/kill -SIGTERM $MAINPID

Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=crypto-api-%I

[Install]
WantedBy=multi-user.target
'''
    
    # Template for prometheus exporter
    exporter_template = '''[Unit]
Description=Crypto Prometheus Exporter - %I
After=network.target crypto-agent@%I.service
Wants=crypto-agent@%I.service

[Service]
Type=simple
User=homelab
WorkingDirectory=/home/homelab/myClaude/btc_trading_agent
Environment=PYTHONUNBUFFERED=1
Environment=COIN_CONFIG_FILE=config_%I.json

ExecStart=/usr/bin/python3 /home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal
SyslogIdentifier=crypto-exporter-%I

[Install]
WantedBy=multi-user.target
'''
    
    # Write templates
    template_dir = BASE_DIR / "systemd"
    template_dir.mkdir(exist_ok=True)
    
    (template_dir / "crypto-agent@.service").write_text(agent_template)
    (template_dir / "crypto-api@.service").write_text(api_template)
    (template_dir / "crypto-exporter@.service").write_text(exporter_template)
    
    print("   ✅ crypto-agent@.service")
    print("   ✅ crypto-api@.service")
    print("   ✅ crypto-exporter@.service")
    
    # Also create env drop-in dirs for port overrides per coin
    for coin in COINS:
        if coin.get("existing"):
            continue
        
        sym = symbol_safe(coin["symbol"])
        
        # Agent drop-in
        agent_dropin_dir = template_dir / f"crypto-agent@{sym}.service.d"
        agent_dropin_dir.mkdir(exist_ok=True)
        (agent_dropin_dir / "env.conf").write_text(f"""[Service]
Environment=COIN_CONFIG_FILE=config_{sym}.json
""")
        
        # API drop-in
        api_dropin_dir = template_dir / f"crypto-api@{sym}.service.d"
        api_dropin_dir.mkdir(exist_ok=True)
        (api_dropin_dir / "env.conf").write_text(f"""[Service]
Environment=BTC_ENGINE_API_PORT={coin['api_port']}
Environment=COIN_CONFIG_FILE=config_{sym}.json
""")
        
        # Exporter drop-in
        exp_dropin_dir = template_dir / f"crypto-exporter@{sym}.service.d"
        exp_dropin_dir.mkdir(exist_ok=True)
        (exp_dropin_dir / "env.conf").write_text(f"""[Service]
Environment=METRICS_PORT={coin['metrics_port']}
Environment=COIN_CONFIG_FILE=config_{sym}.json
""")
        
        print(f"   ✅ Drop-ins for {sym} (API:{coin['api_port']}, Metrics:{coin['metrics_port']})")

# ============================================================
# 8. CREATE install_multi_coin.sh
# ============================================================
def create_install_script():
    print("\n📝 Creating install_multi_coin.sh...")
    
    coins_new = [c for c in COINS if not c.get("existing")]
    
    install_lines = ['#!/bin/bash', 
                     '# Install Multi-Coin Trading Services',
                     'set -e', '',
                     'SYSTEMD_DIR="/etc/systemd/system"',
                     'SRC_DIR="/home/homelab/myClaude/btc_trading_agent/systemd"',
                     '',
                     'echo "📦 Installing systemd template units..."',
                     'sudo cp "$SRC_DIR/crypto-agent@.service" "$SYSTEMD_DIR/"',
                     'sudo cp "$SRC_DIR/crypto-api@.service" "$SYSTEMD_DIR/"',
                     'sudo cp "$SRC_DIR/crypto-exporter@.service" "$SYSTEMD_DIR/"',
                     '']
    
    for coin in coins_new:
        sym = symbol_safe(coin["symbol"])
        install_lines.extend([
            f'# --- {coin["symbol"]} ---',
            f'echo "🪙 Installing {coin["symbol"]}..."',
            f'sudo mkdir -p "$SYSTEMD_DIR/crypto-agent@{sym}.service.d"',
            f'sudo cp "$SRC_DIR/crypto-agent@{sym}.service.d/env.conf" "$SYSTEMD_DIR/crypto-agent@{sym}.service.d/"',
            f'sudo mkdir -p "$SYSTEMD_DIR/crypto-api@{sym}.service.d"',
            f'sudo cp "$SRC_DIR/crypto-api@{sym}.service.d/env.conf" "$SYSTEMD_DIR/crypto-api@{sym}.service.d/"',
            f'sudo mkdir -p "$SYSTEMD_DIR/crypto-exporter@{sym}.service.d"',
            f'sudo cp "$SRC_DIR/crypto-exporter@{sym}.service.d/env.conf" "$SYSTEMD_DIR/crypto-exporter@{sym}.service.d/"',
            ''
        ])
    
    install_lines.extend([
        'echo "🔄 Reloading systemd..."',
        'sudo systemctl daemon-reload',
        '',
        '# Enable and start new coin services',
    ])
    
    for coin in coins_new:
        sym = symbol_safe(coin["symbol"])
        install_lines.extend([
            f'echo "🚀 Starting {coin["symbol"]}..."',
            f'sudo systemctl enable --now crypto-agent@{sym}.service',
            f'sudo systemctl enable --now crypto-exporter@{sym}.service',
            # Not starting API for all by default — save resources
            f'# sudo systemctl enable --now crypto-api@{sym}.service',
            ''
        ])
    
    install_lines.extend([
        'echo ""',
        'echo "✅ Multi-coin services installed!"',
        'echo ""',
        'echo "Status:"',
    ])
    
    for coin in coins_new:
        sym = symbol_safe(coin["symbol"])
        install_lines.append(f'systemctl is-active crypto-agent@{sym}.service && echo "  ✅ {coin["symbol"]} agent" || echo "  ❌ {coin["symbol"]} agent"')
        install_lines.append(f'systemctl is-active crypto-exporter@{sym}.service && echo "  ✅ {coin["symbol"]} exporter" || echo "  ❌ {coin["symbol"]} exporter"')
    
    install_script = BASE_DIR / "install_multi_coin.sh"
    install_script.write_text('\n'.join(install_lines) + '\n')
    install_script.chmod(0o755)
    print(f"   ✅ {install_script}")

# ============================================================
# 9. UPDATE prometheus.yml with new scrape targets
# ============================================================
def update_prometheus_config():
    print("\n📊 Updating prometheus.yml...")
    prom_file = MONITORING_DIR / "prometheus.yml"
    
    if not prom_file.exists():
        print("   ⚠️  prometheus.yml not found, skipping")
        return
    
    content = prom_file.read_text()
    
    # Generate new scrape configs for each new coin
    new_jobs = []
    for coin in COINS:
        if coin.get("existing"):
            continue
        
        sym = symbol_safe(coin["symbol"])
        job = f"""
  - job_name: 'crypto-exporter-{symbol_lower(coin["symbol"])}'
    scrape_interval: 30s
    static_configs:
      - targets: ['172.17.0.1:{coin["metrics_port"]}']
        labels:
          coin: '{coin["symbol"]}'
          instance: '{symbol_lower(coin["symbol"])}'"""
        
        # Check if this job already exists
        if f"crypto-exporter-{symbol_lower(coin['symbol'])}" not in content:
            new_jobs.append(job)
            print(f"   ✅ Adding scrape job: {coin['symbol']} (port {coin['metrics_port']})")
        else:
            print(f"   ⏭️  {coin['symbol']} scrape job already exists")
    
    if new_jobs:
        # Append jobs at end of file
        content = content.rstrip() + '\n' + '\n'.join(new_jobs) + '\n'
        prom_file.write_text(content)
        print("   ✅ prometheus.yml updated")
    else:
        print("   ⏭️  No new jobs to add")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("🪙 Multi-Coin Trading Agent - Deployment")
    print("=" * 60)
    print(f"\nCoins: {', '.join(c['symbol'] for c in COINS)}")
    print(f"New coins: {', '.join(c['symbol'] for c in COINS if not c.get('existing'))}")
    print(f"Total capital: ${sum(c['capital'] for c in COINS):.0f} USDT")
    print()
    
    create_coins_json()
    create_coin_configs()
    patch_trading_engine()
    patch_trading_agent()
    patch_engine_api()
    patch_prometheus_exporter()
    create_systemd_units()
    create_install_script()
    update_prometheus_config()
    
    print("\n" + "=" * 60)
    print("✅ Deployment preparation complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Review configs:  ls -la config_*.json")
    print("  2. Install services: bash install_multi_coin.sh")
    print("  3. Check status:     systemctl status 'crypto-agent@*'")
    print("  4. Reload Prometheus: docker restart prometheus")
    print("  5. When ready for live: edit each config_*.json → dry_run: false")
    print()

if __name__ == "__main__":
    main()
