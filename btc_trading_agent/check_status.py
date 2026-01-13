#!/usr/bin/env python3
import requests
import json

try:
    response = requests.get('http://localhost:8511/api/status', timeout=5)
    data = response.json()
    engine = data['engine']

    print('🚀 Status do Bitcoin Trading Agent')
    print('=' * 40)
    print(f'Estado: {engine["state"].upper()}')
    print(f'Uptime: {engine["uptime_seconds"]} segundos')
    print(f'Trades hoje: {engine["trades_today"]}')
    print(f'PNL hoje: ${engine["daily_pnl"]:.2f}')
    print(f'Posição atual: {engine["current_position"]:.8f} BTC')
    print(f'Último sinal: {engine.get("last_signal", "Nenhum")}')
    print()
    print('✅ Serviços ativos:')
    print('  • API Server (porta 8511)')
    print('  • Trading Engine 24/7')
    print('  • WebUI API')
    print('  • Relatório diário (06:00 todos os dias)')
    print()
    print('🔄 Configuração de restart automático:')
    print('  • Restart=on-failure')
    print('  • RestartSec=30s')
    print('  • Máximo 3 reinícios em 5 minutos')

except Exception as e:
    print(f'❌ Erro ao obter status: {e}')