"""Patch training_db.py para suporte a dual-profile."""
from pathlib import Path

f = Path("/home/homelab/myClaude/btc_trading_agent/training_db.py")
content = f.read_text()
patches_ok = 0

# 1. Adicionar profile parameter ao record_trade
old = '''    def record_trade(self, symbol: str, side: str, price: float,
                     size: float = None, funds: float = None,
                     order_id: str = None, dry_run: bool = False,
                     metadata: Dict = None) -> int:'''
new = '''    def record_trade(self, symbol: str, side: str, price: float,
                     size: float = None, funds: float = None,
                     order_id: str = None, dry_run: bool = False,
                     metadata: Dict = None, profile: str = 'default') -> int:'''
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("1/2 record_trade signature updated")
else:
    print("1/2 SKIP (already applied or not found)")

# 2. Adicionar profile ao INSERT
old = '''            cur.execute(f"""
                INSERT INTO {SCHEMA}.trades
                    (timestamp, symbol, side, price, size, funds,
                     order_id, dry_run, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, side, price, size, funds,
                order_id, dry_run,
                json.dumps(metadata) if metadata else None
            ))'''
new = '''            cur.execute(f"""
                INSERT INTO {SCHEMA}.trades
                    (timestamp, symbol, side, price, size, funds,
                     order_id, dry_run, metadata, profile)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                time.time(), symbol, side, price, size, funds,
                order_id, dry_run,
                json.dumps(metadata) if metadata else None,
                profile
            ))'''
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("2/2 INSERT statement updated with profile")
else:
    print("2/2 SKIP")

f.write_text(content)
print(f"\nDone! {patches_ok} patches applied")
