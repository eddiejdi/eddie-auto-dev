#!/bin/bash
# 🚨 FIX SCRIPT - BTC TRADING AGENT
# Automatically apply critical configuration fixes
# Run on homelab: ssh homelab@192.168.15.2 'bash < fix_btc_config.sh'

set -e

AGENT_DIR="/apps/crypto-trader/trading/btc_trading_agent"
CONFIG_FILE="$AGENT_DIR/config.json"

echo "🚨 BTC TRADING AGENT - CRITICAL FIX"
echo "======================================"

# Step 1: Stop the daemon
echo ""
echo "1️⃣  Stopping trading daemon..."
pkill -9 -f "trading_agent.py --daemon" 2>/dev/null || echo "   (Already stopped)"
sleep 2

# Check stopped
if ! pgrep -f "trading_agent.py --daemon" > /dev/null; then
    echo "   ✅ Daemon stopped"
else
    echo "   ❌ Failed to stop daemon (manual intervention needed)"
    exit 1
fi

# Step 2: Backup current config
echo ""
echo "2️⃣  Backing up current config..."
BACKUP_FILE="$CONFIG_FILE.backup.$(date +%s)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "   ✅ Backed up to: $BACKUP_FILE"

# Step 3: Update config.json with Python
echo ""
echo "3️⃣  Applying critical fixes..."
python3 << 'PYEOF'
import json

config_file = "/apps/crypto-trader/trading/btc_trading_agent/config.json"

with open(config_file) as f:
    config = json.load(f)

# CRITICAL FIXES
print("\n   Changes:")

# 1. Enable auto_take_profit
old_atp = config.get('auto_take_profit', {}).get('enabled')
config['auto_take_profit']['enabled'] = True
config['auto_take_profit']['pct'] = 0.025
print(f"   ✅ auto_take_profit: {old_atp} → True")

# 2. Increase min_confidence
old_confidence = config.get('min_confidence')
config['min_confidence'] = 0.85
print(f"   ✅ min_confidence: {old_confidence} → 0.85")

# 3. Increase min_net_profit
old_mnp = config.get('min_net_profit')
config['min_net_profit']['usd'] = 0.50
config['min_net_profit']['pct'] = 0.015
print(f"   ✅ min_net_profit: ${old_mnp['usd']} → $0.50")
print(f"   ✅ min_net_profit pct: {old_mnp['pct']*100:.4f}% → 1.5%")

# 4. Update stop/take profit
config['stop_loss_pct'] = 0.025
config['take_profit_pct'] = 0.035
config['auto_stop_loss']['pct'] = 0.025
print(f"   ✅ stop_loss_pct: 0.02 → 0.025")
print(f"   ✅ take_profit_pct: 0.03 → 0.035")

# 5. Increase minimum spread
old_spread = config.get('strategy', {}).get('min_spread_bps', 5)
config['strategy']['min_spread_bps'] = 10
print(f"   ✅ min_spread_bps: {old_spread} → 10")

# 6. Enable dry_run for safety
config['dry_run'] = True
print(f"   ✅ dry_run: ENABLED (for testing)")

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print("\n   ✅ Config updated successfully")
PYEOF

# Step 4: Show what changed
echo ""
echo "4️⃣  Validating changes..."
python3 << 'PYEOF'
import json

with open("/apps/crypto-trader/trading/btc_trading_agent/config.json") as f:
    config = json.load(f)

print("\n   New Critical Values:")
print(f"   - auto_take_profit.enabled: {config['auto_take_profit']['enabled']}")
print(f"   - auto_take_profit.pct: {config['auto_take_profit']['pct']*100:.2f}%")
print(f"   - min_confidence: {config['min_confidence']}")
print(f"   - min_net_profit.usd: ${config['min_net_profit']['usd']}")
print(f"   - min_net_profit.pct: {config['min_net_profit']['pct']*100:.2f}%")
print(f"   - dry_run: {config['dry_run']}")

if config['dry_run']:
    print("\n   ⚠️  DRY RUN MODE ENABLED - No real trades will execute!")
    print("      To enable live mode, set 'dry_run: false' in config.json")
PYEOF

echo ""
echo "======================================"
echo "✅ ALL CRITICAL FIXES APPLIED"
echo ""
echo "NEXT STEPS:"
echo "1. Verify config in Grafana dashboard"
echo "2. Start bot in DRY RUN mode:"
echo "   cd $AGENT_DIR && python3 trading_agent.py --daemon --dry"
echo "3. Monitor for 2-3 hours"
echo "4. If Win Rate improves (>40%), enable LIVE mode"
echo "5. Start with reduced position size:"
echo "   'max_position_pct': 0.2  (instead of 0.8)"
echo ""
