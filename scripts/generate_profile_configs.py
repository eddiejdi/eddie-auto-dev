#!/usr/bin/env python3
"""
Gera configs de perfil (conservative/aggressive) para cada moeda.

Lê o config base de cada moeda e cria 2 variantes com parâmetros
ajustados para cada perfil de risco.

Uso:
  python3 scripts/generate_profile_configs.py [--base-dir /path/to/btc_trading_agent]
"""

import json
import copy
import argparse
from pathlib import Path

# Mapeamento moeda → config base
COINS = {
    "BTC_USDT": "config.json",
    "ETH_USDT": "config_ETH_USDT.json",
    "XRP_USDT": "config_XRP_USDT.json",
    "SOL_USDT": "config_SOL_USDT.json",
    "DOGE_USDT": "config_DOGE_USDT.json",
    "ADA_USDT": "config_ADA_USDT.json",
}

# Overrides por perfil (aplicados sobre o config base)
PROFILE_OVERRIDES: dict[str, dict] = {
    "conservative": {
        "profile": "conservative",
        "min_confidence": 0.85,
        "max_position_pct": 0.15,
        "min_trade_interval": 1800,
        "max_positions": 2,
        "auto_stop_loss": {"enabled": True, "pct": 0.015},
        "auto_take_profit": {"enabled": True, "pct": 0.015, "min_pct": 0.010},
        "trailing_stop": {"enabled": True, "activation_pct": 0.010, "trail_pct": 0.005},
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.015,
        "strategy": {
            "mode": "scalping",
            "use_trend_filter": True,
            "use_volume_filter": True,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "min_spread_bps": 15,
        },
        "risk_management": {
            "enabled": True,
            "max_drawdown_pct": 0.05,
            "position_sizing": "dynamic",
            "kelly_fraction": 0.15,
            "volatility_filter": True,
            "min_volatility": 0.001,
            "max_volatility": 0.03,
        },
    },
    "aggressive": {
        "profile": "aggressive",
        "min_confidence": 0.55,
        "max_position_pct": 0.30,
        "min_trade_interval": 600,
        "max_positions": 4,
        "auto_stop_loss": {"enabled": True, "pct": 0.035},
        "auto_take_profit": {"enabled": True, "pct": 0.035, "min_pct": 0.020},
        "trailing_stop": {"enabled": True, "activation_pct": 0.020, "trail_pct": 0.012},
        "stop_loss_pct": 0.035,
        "take_profit_pct": 0.035,
        "strategy": {
            "mode": "scalping",
            "use_trend_filter": True,
            "use_volume_filter": False,
            "rsi_oversold": 40,
            "rsi_overbought": 60,
            "min_spread_bps": 5,
        },
        "risk_management": {
            "enabled": True,
            "max_drawdown_pct": 0.15,
            "position_sizing": "dynamic",
            "kelly_fraction": 0.35,
            "volatility_filter": True,
            "min_volatility": 0.0005,
            "max_volatility": 0.08,
        },
    },
}


def generate_configs(base_dir: Path) -> list[Path]:
    """Gera configs de perfil para todas as moedas."""
    created: list[Path] = []

    for coin, base_filename in COINS.items():
        base_path = base_dir / base_filename

        if base_path.exists():
            with open(base_path) as f:
                base_config = json.load(f)
        else:
            # Se não existe config base, criar um mínimo
            symbol = coin.replace("_", "-")
            base_config = {
                "enabled": True,
                "dry_run": True,
                "symbol": symbol,
                "poll_interval": 5,
                "min_trade_interval": 300,
                "min_confidence": 0.55,
                "min_trade_amount": 5,
                "max_position_pct": 0.5,
                "max_positions": 4,
                "stop_loss_pct": 0.025,
                "take_profit_pct": 0.04,
                "max_daily_trades": 999,
                "max_daily_loss": 50,
                "min_sell_pnl": 0.005,
                "notifications": {"enabled": True, "on_trade": True, "on_signal": False, "on_error": True},
                "risk_management": {"enabled": True, "max_drawdown_pct": 0.1, "position_sizing": "dynamic"},
                "trailing_stop": {"enabled": True, "activation_pct": 0.015, "trail_pct": 0.008},
                "auto_stop_loss": {"enabled": True, "pct": 0.025},
                "auto_take_profit": {"enabled": True, "pct": 0.025, "min_pct": 0.015},
                "min_net_profit": {"usd": 0.005, "pct": 0.0003},
            }

        for profile, overrides in PROFILE_OVERRIDES.items():
            cfg = copy.deepcopy(base_config)
            cfg.update(overrides)
            # Preservar symbol do base
            cfg["symbol"] = base_config.get("symbol", coin.replace("_", "-"))

            out_path = base_dir / f"config_{coin}_{profile}.json"
            with open(out_path, "w") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print(f"  ✅ {out_path.name}")
            created.append(out_path)

    return created


def main() -> None:
    """Ponto de entrada."""
    parser = argparse.ArgumentParser(description="Gera configs de perfil para trading agent")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent.parent / "btc_trading_agent",
        help="Diretório base do trading agent",
    )
    args = parser.parse_args()

    print(f"📁 Base dir: {args.base_dir}")
    created = generate_configs(args.base_dir)
    print(f"\n🎉 {len(created)} configs criados!")


if __name__ == "__main__":
    main()
