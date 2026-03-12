"""Patch market_rag.py para incluir ai_conservative_pct no RAGAdjustment."""
from pathlib import Path

f = Path("/home/homelab/myClaude/btc_trading_agent/market_rag.py")
content = f.read_text()
patches_ok = 0

# 1. Adicionar campo ai_conservative_pct após ai_position_size_reason
old = '    ai_position_size_reason: str = ""     # Razão textual do cálculo\n'
new = (old +
    '\n'
    '    # AI Profile Allocation (split conservador/arrojado)\n'
    '    ai_conservative_pct: float = 0.5       # % do saldo para perfil conservador (0.0-1.0)\n')
if old in content and 'ai_conservative_pct' not in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("1/2 ai_conservative_pct field added")
else:
    print("1/2 SKIP")

# 2. Adicionar no to_dict
old = '            "ai_position_size_reason": self.ai_position_size_reason,\n        }'
new = ('            "ai_position_size_reason": self.ai_position_size_reason,\n'
       '            "ai_conservative_pct": round(self.ai_conservative_pct, 3),\n'
       '        }')
if old in content and 'ai_conservative_pct' not in content.split('to_dict')[1][:500]:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("2/2 to_dict ai_conservative_pct added")
else:
    print("2/2 SKIP")

f.write_text(content)
print(f"\nDone! {patches_ok} patches applied")
