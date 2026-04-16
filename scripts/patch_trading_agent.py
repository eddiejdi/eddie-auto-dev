"""Patch trading_agent.py para suporte a dual-profile."""
from pathlib import Path

f = Path("/apps/crypto-trader/trading/btc_trading_agent/trading_agent.py")
content = f.read_text()

patches_ok = 0

# 1. PROFILE constante após MAX_POSITIONS
old = 'MAX_POSITIONS = _config.get("max_positions", 3)  # max BUY entries acumuladas\n'
new = old + 'PROFILE = _config.get("profile", "default")  # conservative|aggressive|default\n'
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("1/8 PROFILE constant added")
else:
    print("1/8 SKIP (already applied or not found)")

# 2. AgentState.profile field
old = "    daily_date: str = ''  # Data do dia para reset\n"
new = old + "    profile: str = 'default'  # Perfil: conservative|aggressive|default\n"
if old in content and "profile: str = " not in content.split("daily_date: str")[1][:100]:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("2/8 AgentState.profile field added")
else:
    print("2/8 SKIP")

# 3. to_dict profile
old = '            "target_sell_reason": self.target_sell_reason\n'
new = '            "target_sell_reason": self.target_sell_reason,\n            "profile": self.profile\n'
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("3/8 to_dict profile added")
else:
    print("3/8 SKIP")

# 4. __init__ profile
old = "        self.state = AgentState(symbol=symbol, dry_run=dry_run)\n"
new = "        self.state = AgentState(symbol=symbol, dry_run=dry_run, profile=PROFILE)\n"
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("4/8 __init__ profile set")
else:
    print("4/8 SKIP")

# 5. Banner profile — use exact emoji chars from file
import re
m = re.search(r'(    print\(f"Symbol: \{args\.symbol\}"\)\n)(    print\(f"Mode: )', content)
if m and 'Profile:' not in content[m.start():m.start()+200]:
    insert_pos = m.start() + len(m.group(1))
    profile_line = '    print(f"Profile: {_loaded_cfg.get(\'profile\', \'default\')}")\n'
    content = content[:insert_pos] + profile_line + content[insert_pos:]
    patches_ok += 1
    print("5/8 Banner profile added")
else:
    print("5/8 SKIP")

# 6. record_trade BUY — add profile
old = '''                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run
                    )'''
new = '''                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="buy",
                        price=price,
                        size=size,
                        funds=amount_usdt,
                        dry_run=self.state.dry_run,
                        profile=self.state.profile
                    )'''
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("6/8 record_trade BUY profile added")
else:
    print("6/8 SKIP")

# 7. record_trade SELL — add profile
old = '''                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        funds=round(price * size, 2),  # FIX #9: Record sell funds
                        dry_run=self.state.dry_run
                    )'''
new = '''                    trade_id = self.db.record_trade(
                        symbol=self.symbol,
                        side="sell",
                        price=price,
                        size=size,
                        funds=round(price * size, 2),  # FIX #9: Record sell funds
                        dry_run=self.state.dry_run,
                        profile=self.state.profile
                    )'''
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("7/8 record_trade SELL profile added")
else:
    print("7/8 SKIP")

# 8. _calculate_trade_size allocation
old = '''        if signal.action == "BUY":
            usdt_balance = get_balance("USDT") if not self.state.dry_run else 1000'''
new = '''        if signal.action == "BUY":
            usdt_balance = get_balance("USDT") if not self.state.dry_run else 1000
            # Profile allocation: aplicar % do saldo alocado ao perfil
            usdt_balance = self._apply_profile_allocation(usdt_balance)'''
c = content.count(old)
if c == 1 and '_apply_profile_allocation' not in content.split(old)[1][:100]:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("8/8 _calculate_trade_size allocation added")
else:
    print(f"8/8 SKIP (count={c})")

# 9. Adicionar método _apply_profile_allocation antes de _calculate_trade_size
method_code = '''
    def _apply_profile_allocation(self, total_balance: float) -> float:
        """Aplica alocação de saldo baseada no perfil.

        Lê a última alocação da tabela btc.profile_allocations.
        Retorna o saldo alocado para o perfil deste agente.
        """
        profile = self.state.profile
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

'''

target = "    def _calculate_trade_size(self, signal: Signal, price: float, force: bool = False) -> float:\n"
if target in content and "def _apply_profile_allocation" not in content:
    content = content.replace(target, method_code + target, 1)
    patches_ok += 1
    print("9/9 _apply_profile_allocation method added")
else:
    print("9/9 SKIP (already exists)")

f.write_text(content)
print(f"\nDone! {patches_ok} patches applied, {len(content)} bytes written")
