#!/usr/bin/env python3
"""
Análise detalhada das negociações do AutoCoinBot
Gera relatório com estatísticas e insights
"""

import json
import statistics

# Carregar dados
with open('/tmp/autocoinbot_trades.json', 'r') as f:
    trades = json.load(f)

# Processamento
buy_trades = [t for t in trades if t.get('side') == 'buy']
sell_trades = [t for t in trades if t.get('side') == 'sell']

prices_buy = [t['price'] for t in buy_trades]
prices_sell = [t['price'] for t in sell_trades if t['price'] > 0]

pnl_values = [t['pnl'] for t in trades if t.get('pnl') is not None and t['pnl'] != 0]

# Cálculos
total_bought = sum(t.get('funds') or 0 for t in buy_trades)
avg_price_buy = statistics.mean(prices_buy) if prices_buy else 0
total_volume = sum(t.get('size') or 0 for t in trades)

wins = sum(1 for t in trades if t.get('pnl') and t['pnl'] > 0)
losses = sum(1 for t in trades if t.get('pnl') and t['pnl'] < 0)
breakevens = sum(1 for t in trades if t.get('pnl') and t['pnl'] == 0)

print(f"""
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                    📊 ANÁLISE DETALHADA - AUTOCOINBOT TRADES                                  ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

📈 ESTATÍSTICAS BÁSICAS:
├─ Total de Trades: {len(trades)} operações
├─ Compras (BUY):  {len(buy_trades)} operações ({len(buy_trades)/len(trades)*100:.1f}%)
├─ Vendas (SELL):  {len(sell_trades)} operações ({len(sell_trades)/len(trades)*100:.1f}%)
└─ Período: {trades[-1]['created_at'][:10]} até {trades[0]['created_at'][:10]}

💰 VOLUME OPERADO:
├─ Total Investido (Compras): ${total_bought:,.2f} USDT
├─ Quantidade Total: {total_volume:.6f} BTC
└─ Preço Médio de Compra: ${avg_price_buy:,.2f}

📊 PERFORMANCE:
├─ Trades Vencedores: {wins} ({wins/(wins+losses+breakevens)*100 if (wins+losses+breakevens) > 0 else 0:.1f}%)
├─ Trades Perdedores: {losses} ({losses/(wins+losses+breakevens)*100 if (wins+losses+breakevens) > 0 else 0:.1f}%)
├─ Breakevens: {breakevens}
├─ Win/Loss Ratio: {wins/losses if losses > 0 else 'N/A'}
└─ PnL Total: ${sum(t.get('pnl') or 0 for t in trades):,.2f}

💹 PREÇOS:
├─ Preço Mínimo: ${min(prices_buy):,.2f}
├─ Preço Máximo: ${max(prices_buy):,.2f}
├─ Amplitude: ${max(prices_buy) - min(prices_buy):,.2f}
└─ Volatilidade: {statistics.stdev(prices_buy) if len(prices_buy) > 1 else 0:.2f}

📉 MODO DE OPERAÇÃO:
├─ Status: 🧪 SIMULAÇÃO (backtesting - sem dinheiro real)
├─ Exchange: KuCoin
├─ Par: BTC-USDT
└─ Todos os trades foram executados em modo de simulação

⚙️ INFORMAÇÕES TÉCNICAS:
├─ Banco de Dados: SQLite Local (trading_agent.db)
├─ Último Trade: {trades[0]['created_at']}
├─ Primeiro Trade: {trades[-1]['created_at']}
└─ Total de IDs: {trades[0]['id']} até {trades[-1]['id']}

════════════════════════════════════════════════════════════════════════════════════════════════
""")

# Top 5 operações mais lucrativas
print("\n🏆 TOP 5 OPERAÇÕES MAIS LUCRATIVAS:")
sorted_trades = sorted([t for t in trades if t.get('pnl') is not None], 
                       key=lambda x: x.get('pnl', 0), reverse=True)[:5]
for i, t in enumerate(sorted_trades, 1):
    emoji = "🟢" if t.get('pnl', 0) > 0 else "🔴"
    print(f"  {i}. {emoji} ${t['pnl']:.2f} ({t['pnl_pct']*100:.2f}%) - {t['created_at'][:16]}")

# Top 5 perdas
print("\n❌ TOP 5 MAIORES PERDAS:")
sorted_losses = sorted([t for t in trades if t.get('pnl') is not None], 
                       key=lambda x: x.get('pnl', 0))[:5]
for i, t in enumerate(sorted_losses, 1):
    print(f"  {i}. 🔴 ${t['pnl']:.2f} ({t['pnl_pct']*100:.2f}%) - {t['created_at'][:16]}")

print("\n════════════════════════════════════════════════════════════════════════════════════════════════\n")
