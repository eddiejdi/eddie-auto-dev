"""Patch prometheus_exporter.py para incluir label profile nas métricas."""
from pathlib import Path

f = Path("/home/homelab/myClaude/btc_trading_agent/prometheus_exporter.py")
content = f.read_text()
patches_ok = 0

# 1. Adicionar profile label (modificar _cl)
old = """            _cl = f'coin="{_sym}"'  # coin label reutilizável"""
new = """            _profile = cfg.get('profile', 'default')
            _cl = f'coin="{_sym}",profile="{_profile}"'  # coin+profile labels"""
if old in content:
    content = content.replace(old, new, 1)
    patches_ok += 1
    print("1/1 Prometheus profile label added")
else:
    print("1/1 SKIP (already applied or not found)")

f.write_text(content)
print(f"\nDone! {patches_ok} patches applied")
