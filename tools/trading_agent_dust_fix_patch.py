#!/usr/bin/env python3
"""Patch trading_agent.py to stop invalid dust SELL loops."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


DEFAULT_AGENT_PATH = Path("/home/homelab/myClaude/btc_trading_agent/trading_agent.py")


HELPER_BLOCK = """
    def _pick_live_position_owner(self) -> Optional[str]:
        \"\"\"Pick a single profile to own the shared live balance.\"\"\"
        try:
            trades_all = self.db.get_recent_trades(
                symbol=self.symbol,
                limit=200,
                include_dry=self.state.dry_run,
            )
        except Exception as e:
            logger.debug(f\"Live owner lookup failed: {e}\")
            return None

        profiles: Dict[str, Dict[str, float]] = {}
        sell_seen: set[str] = set()
        for trade in trades_all:
            trade_profile = trade.get(\"profile\") or \"default\"
            if trade_profile == \"exchange_sync\":
                continue
            if trade_profile in sell_seen:
                continue
            side = (trade.get(\"side\") or \"\").lower()
            if side == \"sell\":
                sell_seen.add(trade_profile)
                continue
            if side != \"buy\":
                continue
            slot = profiles.setdefault(
                trade_profile,
                {\"size\": 0.0, \"latest_ts\": 0.0, \"entries\": 0.0},
            )
            slot[\"size\"] += float(trade.get(\"size\") or 0.0)
            slot[\"latest_ts\"] = max(slot[\"latest_ts\"], float(trade.get(\"timestamp\") or 0.0))
            slot[\"entries\"] += 1.0

        contenders = [
            (name, data) for name, data in profiles.items()
            if data[\"size\"] > 0 and name != \"default\"
        ]
        if not contenders:
            return None
        contenders.sort(
            key=lambda item: (
                item[1][\"size\"],
                item[1][\"latest_ts\"],
                item[1][\"entries\"],
                item[0] == \"aggressive\",
            ),
            reverse=True,
        )
        return contenders[0][0]

    def _clear_local_position_state(self, reason: str) -> None:
        \"\"\"Clear stale local position state to stop repeated dust exits.\"\"\"
        logger.warning(f\"Clearing local position state: {reason}\")
        self.state.position = 0.0
        self.state.position_value = 0.0
        self.state.entry_price = 0.0
        self.state.position_count = 0
        self.state.entries = []
        self.state.target_sell_price = 0.0
        self.state.target_sell_reason = \"\"
        self._reset_sell_target_peak_state()
"""


OLD_EXTERNAL_DEPOSIT_BLOCK = """            # Em conta compartilhada, só atribuir saldo live ao perfil que já tem
            # posição aberta no próprio ledger. Isso evita duplicar a mesma posição
            # entre aggressive e conservative após restart.
            if not self.state.entries and profile != "default":
                logger.info(
                    f"⏭️ External deposit skipped for profile={profile}: "
                    "no profile-scoped open entries to attach live balance"
                )
                return
"""


NEW_EXTERNAL_DEPOSIT_BLOCK = """            live_owner = self._pick_live_position_owner()
            if live_owner and profile != live_owner:
                logger.info(
                    f"⏭️ External deposit skipped for profile={profile}: "
                    f"live balance assigned to profile={live_owner}"
                )
                return

            # Fallback when there is still no explicit owner in the ledger.
            if not live_owner and not self.state.entries and profile != "default":
                logger.info(
                    f"⏭️ External deposit skipped for profile={profile}: "
                    "no profile-scoped open entries to attach live balance"
                )
                return
"""


NEW_SELL_BLOCK = """        elif signal.action == "SELL":
            size = self.state.position
            if size <= 0:
                return 0

            sell_min_funds = float(_config.get("min_sell_funds", 0.1))
            base_currency = self.symbol.split("-")[0]
            live_balance = None
            live_owner = None
            if not self.state.dry_run:
                try:
                    live_balance = float(get_balance(base_currency) or 0.0)
                    live_owner = self._pick_live_position_owner()
                except Exception as e:
                    logger.debug(f"Live sell balance check failed: {e}")

            if (
                live_balance is not None
                and live_owner == self._current_profile()
                and live_balance * price >= sell_min_funds
                and live_balance > size * 5
            ):
                logger.warning(
                    f"Reconciling SELL size with live balance: local {size:.8f} -> "
                    f"exchange {live_balance:.8f} {base_currency}"
                )
                size = live_balance
                self.state.position = live_balance

            gross_sell = price * size
            if gross_sell < sell_min_funds:
                if live_owner and live_owner != self._current_profile():
                    self._clear_local_position_state(
                        f"stale dust sell for profile={self._current_profile()} "
                        f"while live owner is profile={live_owner}"
                    )
                else:
                    self._clear_local_position_state(
                        f"dust position below sell minimum: ${gross_sell:.4f} < ${sell_min_funds:.4f}"
                    )
                return 0

            # Auto-exit (SL/TP) bypasses fee check — always sell
            if force:
                return size

            # Fee check: estimar taxas antes de enviar ordem de venda
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

            # Só aceitar venda abaixo do target com lucro líquido mínimo, exceto
            # quando já estivermos em stop-loss real.
            stop_loss_pct = _config.get("stop_loss_pct", 0.02)
            stop_loss_price = self.state.entry_price * (1 - stop_loss_pct)
            if net_profit < min_required and price > stop_loss_price:
                logger.info(
                    f"🔒 SELL blocked (net profit): ${net_profit:.4f} < min ${min_required:.4f} "
                    f"(gross ${pnl:.4f}, fees ${total_fees:.4f}, stop ${stop_loss_price:,.2f})"
                )
                return 0

            # Vender posicao inteira
            return size
"""


SELL_BLOCK_PATTERN = re.compile(
    r'''        elif signal\.action == "SELL":\n'''
    r'''(?:.*\n)*?'''
    r'''            # Vender posicao inteira\n'''
    r'''            return self\.state\.position\n''',
    re.MULTILINE,
)


def apply_patch(agent_path: Path) -> int:
    code = agent_path.read_text()
    original = code
    changes = 0

    insertion_anchor = """        # Fallback: split 50/50
        return total_balance * 0.5
"""
    if "_pick_live_position_owner" not in code:
        if insertion_anchor not in code:
            raise RuntimeError("Could not find _apply_profile_allocation fallback anchor")
        code = code.replace(insertion_anchor, insertion_anchor + HELPER_BLOCK, 1)
        changes += 1

    sell_fix_present = (
        'sell_min_funds = float(_config.get("min_sell_funds", 0.1))' in code
        and "_clear_local_position_state(" in code
    )
    if not sell_fix_present:
        code, replaced = SELL_BLOCK_PATTERN.subn(NEW_SELL_BLOCK, code, count=1)
        if replaced == 0:
            raise RuntimeError("Could not find SELL sizing block to replace")
        changes += 1

    if NEW_EXTERNAL_DEPOSIT_BLOCK not in code:
        if OLD_EXTERNAL_DEPOSIT_BLOCK not in code:
            raise RuntimeError("Could not find external deposit owner block to replace")
        code = code.replace(OLD_EXTERNAL_DEPOSIT_BLOCK, NEW_EXTERNAL_DEPOSIT_BLOCK, 1)
        changes += 1

    if code == original:
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = agent_path.with_name(f"{agent_path.name}.bak.{ts}.dust_fix")
    backup.write_text(original)
    agent_path.write_text(code)
    print(f"backup={backup}")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_AGENT_PATH)
    args = parser.parse_args()

    if not args.path.exists():
        print(f"missing file: {args.path}", file=sys.stderr)
        return 1

    changes = apply_patch(args.path)
    if changes == 0:
        print("no changes needed")
    else:
        print(f"applied {changes} change set(s) to {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
