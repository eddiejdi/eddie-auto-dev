#!/usr/bin/env python3
"""
Módulo de Integração de Relatórios
Gera relatórios diversos sob demanda via WhatsApp/Chat

Relatórios disponíveis:
- Bitcoin Trading (btc, bitcoin, trading)
- Status do Sistema (sistema, status, server)
- Homelab (homelab, servidores, docker)
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretórios
BASE_DIR = Path(__file__).parent
BTC_AGENT_DIR = BASE_DIR / "btc_trading_agent"

# ======================== BITCOIN TRADING REPORT ========================

def get_btc_price() -> float | None:
    """Obtém preço atual do BTC"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("bitcoin", {}).get("usd")
    except:
        pass
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10
        )
        if response.status_code == 200:
            return float(response.json().get("price", 0))
    except:
        pass
    return None


def get_btc_trades(hours: int = 24) -> list[dict]:
    """Busca trades das últimas N horas"""
    trades = []
    try:
        db_file = BTC_AGENT_DIR / "data" / "trading_agent.db"
        if not db_file.exists():
            return trades
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        since = datetime.now() - timedelta(hours=hours)
        cursor.execute(
            "SELECT * FROM trades WHERE timestamp > ? ORDER BY timestamp ASC",
            (since.timestamp(),)
        )
        for row in cursor.fetchall():
            trades.append(dict(row))
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao buscar trades: {e}")
    return trades


def get_btc_engine_status() -> dict:
    """Obtém status do engine de trading"""
    try:
        response = requests.get("http://localhost:8511/api/status", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"engine": {"state": "offline"}}


def get_btc_model_stats() -> dict:
    """Obtém estatísticas do modelo ML"""
    stats = {"episodes": 0, "reward": 0.0}
    try:
        import pickle
        model_file = BTC_AGENT_DIR / "models" / "qmodel_BTC_USDT.pkl"
        if model_file.exists():
            with open(model_file, "rb") as f:
                model_data = pickle.load(f)
                stats["episodes"] = model_data.get("episode", 0)
                stats["reward"] = model_data.get("reward", 0.0)
    except:
        pass
    return stats


def calculate_btc_stats(trades: list[dict]) -> dict:
    """Calcula estatísticas dos trades"""
    stats = {
        "total_trades": 0, "buys": 0, "sells": 0,
        "total_volume_usd": 0.0, "total_pnl": 0.0,
        "winning_trades": 0, "losing_trades": 0,
        "win_rate": 0.0, "best_trade": 0.0, "worst_trade": 0.0,
        "open_position": 0.0, "open_position_price": 0.0
    }
    if not trades:
        return stats
    
    stats["total_trades"] = len(trades)
    position = 0.0
    entry_price = 0.0
    
    for trade in trades:
        side = trade.get("side", "")
        price = trade.get("price", 0.0)
        size = trade.get("size", 0.0)
        funds = trade.get("funds", 0.0) or (price * size)
        pnl = trade.get("pnl", 0.0) or 0.0
        
        stats["total_volume_usd"] += funds if side == "buy" else (price * size)
        
        if side == "buy":
            stats["buys"] += 1
            position += size
            entry_price = price
        elif side == "sell":
            stats["sells"] += 1
            position -= size
            stats["total_pnl"] += pnl
            if pnl > 0:
                stats["winning_trades"] += 1
                stats["best_trade"] = max(stats["best_trade"], pnl)
            elif pnl < 0:
                stats["losing_trades"] += 1
                stats["worst_trade"] = min(stats["worst_trade"], pnl)
    
    stats["open_position"] = position
    stats["open_position_price"] = entry_price if position > 0 else 0
    if stats["sells"] > 0:
        stats["win_rate"] = (stats["winning_trades"] / stats["sells"]) * 100
    return stats


def generate_btc_report(hours: int = 24) -> str:
    """Gera relatório de Bitcoin Trading"""
    trades = get_btc_trades(hours)
    stats = calculate_btc_stats(trades)
    engine_status = get_btc_engine_status()
    model_stats = get_btc_model_stats()
    current_price = get_btc_price()
    
    # Configuração
    config = engine_status.get("config", {})
    dry_run = config.get("dry_run", True)
    
    # Status do engine
    engine = engine_status.get("engine", {})
    state = engine.get("state", "offline")
    state_emoji = {"running": "🟢", "paused": "🟡", "stopped": "🔴", "offline": "⚫"}.get(state, "⚪")
    mode = "🧪 SIMULAÇÃO" if dry_run else "💰 MODO REAL"
    
    # Preço
    price_str = f"${current_price:,.2f}" if current_price else "N/A"
    
    # PnL
    pnl = stats["total_pnl"]
    pnl_emoji = "📈" if pnl > 0 else "📉" if pnl < 0 else "➖"
    
    # Posição aberta
    if stats["open_position"] > 0:
        op = stats["open_position"]
        op_price = stats["open_position_price"]
        position_str = f"🔵 {op:.8f} BTC"
        if current_price and op_price > 0:
            unrealized = (current_price - op_price) * op
            unrealized_pct = ((current_price / op_price) - 1) * 100
            position_str += f"\n├ Entrada: ${op_price:,.2f}"
            position_str += f"\n└ P&L: ${unrealized:,.2f} ({unrealized_pct:+.2f}%)"
    else:
        position_str = "💤 Sem posição"
    
    now = datetime.now()
    report = """📊 *RELATÓRIO BITCOIN TRADING*
━━━━━━━━━━━━━━━━━━━━━

💵 *BTC/USD:* {}
{} *Engine:* {}
⚙️ *Modo:* {}
⏰ *Período:* últimas {}h

━━━━━━━━━━━━━━━━━━━━━
📈 *ESTATÍSTICAS*
━━━━━━━━━━━━━━━━━━━━━

*Trades:*
├ Total: {}
├ Compras: {} 🟢
├ Vendas: {} 🔴
└ Volume: ${:,.2f}

*Performance:*
├ {} PnL: ${:,.2f}
├ Win Rate: {:.1f}%
├ Melhor: ${:,.2f}
└ Pior: ${:,.2f}

*Posição Atual:*
{}

━━━━━━━━━━━━━━━━━━━━━
🤖 *MODELO ML*
├ Episódios: {:,}
└ Reward: {:.4f}

🕐 {}
""".format(
        price_str, state_emoji, state.upper(), mode, hours,
        stats["total_trades"], stats["buys"], stats["sells"],
        stats["total_volume_usd"],
        pnl_emoji, pnl, stats["win_rate"],
        stats["best_trade"], stats["worst_trade"],
        position_str,
        model_stats["episodes"], model_stats["reward"],
        now.strftime("%d/%m/%Y %H:%M")
    )
    return report


# ======================== SYSTEM STATUS REPORT ========================

# API Key do WAHA (deve ser a mesma configurada no serviço)
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "96263ae8a9804541849ebc5efa212e0e")

def get_system_services() -> dict[str, str]:
    """Verifica status dos serviços"""
    services = {}
    
    # Checks simples (sem autenticação)
    simple_checks = [
        ("Ollama", "http://192.168.15.2:11434/api/tags"),
        ("BTC Engine", "http://localhost:8511/api/status"),
    ]
    
    for name, url in simple_checks:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                services[name] = "🟢 Online"
            else:
                services[name] = f"🟡 Erro {response.status_code}"
        except requests.exceptions.ConnectionError:
            services[name] = "🔴 Offline"
        except:
            services[name] = "⚪ Desconhecido"
    
    # Check WAHA (requer autenticação)
    try:
        response = requests.get(
            "http://localhost:3000/api/sessions",
            headers={"X-Api-Key": WAHA_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            services["WAHA (WhatsApp)"] = "🟢 Online"
        else:
            services["WAHA (WhatsApp)"] = f"🟡 Erro {response.status_code}"
    except requests.exceptions.ConnectionError:
        services["WAHA (WhatsApp)"] = "🔴 Offline"
    except:
        services["WAHA (WhatsApp)"] = "⚪ Desconhecido"
    
    return services


def get_ollama_models() -> list[str]:
    """Lista modelos Ollama disponíveis"""
    try:
        response = requests.get("http://192.168.15.2:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return [m.get("name", "") for m in models]
    except:
        pass
    return []


def generate_system_report() -> str:
    """Gera relatório de status do sistema"""
    services = get_system_services()
    models = get_ollama_models()
    now = datetime.now()
    
    # Serviços
    services_str = "\n".join([f"{v} {k}" for k, v in services.items()])
    
    # Modelos (top 5)
    models_str = "\n".join([f"• {m}" for m in models[:5]])
    if len(models) > 5:
        models_str += f"\n• ... e mais {len(models) - 5} modelos"
    
    report = """🖥️ *STATUS DO SISTEMA*
━━━━━━━━━━━━━━━━━━━━━

📡 *SERVIÇOS*
━━━━━━━━━━━━━━━━━━━━━
{}

━━━━━━━━━━━━━━━━━━━━━
🤖 *MODELOS OLLAMA*
━━━━━━━━━━━━━━━━━━━━━
{}

🕐 {}
""".format(services_str, models_str, now.strftime("%d/%m/%Y %H:%M"))
    return report


# ======================== HOMELAB REPORT ========================

def get_docker_containers() -> list[dict]:
    """Lista containers Docker (requer acesso SSH ou API)"""
    # Por enquanto retorna info estática - pode ser expandido
    containers = [
        {"name": "ollama", "status": "running"},
        {"name": "waha", "status": "running"},
        {"name": "openwebui", "status": "running"},
    ]
    return containers


def generate_homelab_report() -> str:
    """Gera relatório do Homelab"""
    services = get_system_services()
    containers = get_docker_containers()
    now = datetime.now()
    
    containers_str = "\n".join([
        "• {} - {}".format(c["name"], "🟢" if c["status"] == "running" else "🔴") 
        for c in containers
    ])
    
    report = """🏠 *RELATÓRIO HOMELAB*
━━━━━━━━━━━━━━━━━━━━━

🐳 *CONTAINERS*
━━━━━━━━━━━━━━━━━━━━━
{}

📡 *SERVIÇOS*
━━━━━━━━━━━━━━━━━━━━━
{}

🕐 {}
""".format(
        containers_str,
        "\n".join([f"{v} {k}" for k, v in services.items()]),
        now.strftime("%d/%m/%Y %H:%M")
    )
    return report


# ======================== REPORT DISPATCHER ========================

# Mapeamento de palavras-chave para tipos de relatório (ordem de prioridade)
REPORT_KEYWORDS = {
    "btc": ["btc", "bitcoin", "trading", "trade", "cripto", "crypto", "moeda", "negociação", "negociacoes", "lucro", "portfolio"],
    "homelab": ["homelab", "home lab", "infraestrutura", "infra"],
    "system": ["sistema", "server", "servidor", "serviços", "servicos", "docker", "containers"],
}

def detect_report_type(text: str) -> str | None:
    """Detecta tipo de relatório baseado no texto"""
    text_lower = text.lower()
    
    # Verificar se é solicitação de relatório
    report_triggers = ["relatório", "relatorio", "report", "status", "como está", "como esta", "como vai", "como ta"]
    if not any(trigger in text_lower for trigger in report_triggers):
        return None
    
    # Priorizar BTC se mencionado explicitamente
    btc_keywords = ["btc", "bitcoin", "trading", "trade", "cripto", "crypto", "moeda", "negociaç", "lucro", "portfolio"]
    if any(kw in text_lower for kw in btc_keywords):
        return "btc"
    
    # Detectar outros tipos
    if any(kw in text_lower for kw in ["homelab", "home lab", "infraestrutura", "infra"]):
        return "homelab"
    
    if any(kw in text_lower for kw in ["sistema", "server", "servidor", "serviços", "servicos", "docker", "containers"]):
        return "system"
    
    # Se mencionar relatório sem especificar, assumir BTC (mais comum)
    if "relatório" in text_lower or "relatorio" in text_lower or "report" in text_lower:
        return "btc"
    
    return None


def generate_report(report_type: str, **kwargs) -> str:
    """Gera relatório do tipo especificado"""
    if report_type == "btc":
        hours = kwargs.get("hours", 24)
        return generate_btc_report(hours)
    elif report_type == "system":
        return generate_system_report()
    elif report_type == "homelab":
        return generate_homelab_report()
    else:
        return "❌ Tipo de relatório não reconhecido. Use: btc, sistema ou homelab"


async def process_report_request(text: str) -> str | None:
    """Processa solicitação de relatório e retorna o relatório gerado"""
    report_type = detect_report_type(text)
    if report_type:
        logger.info(f"📊 Gerando relatório: {report_type}")
        return generate_report(report_type)
    return None


# ======================== COMANDOS DO BOT ========================

def get_report_commands() -> str:
    """Retorna lista de comandos de relatório disponíveis"""
    return """📊 *COMANDOS DE RELATÓRIO*

• *relatório btc* - Status do trading de Bitcoin
• *relatório sistema* - Status dos serviços
• *relatório homelab* - Status da infraestrutura

Você também pode perguntar:
• "como está o bitcoin?"
• "status do trading"
• "como estão os servidores?"
"""


# ======================== TEST ========================

if __name__ == "__main__":
    print("=== Teste de Relatórios ===\n")
    
    # Testar detecção
    tests = [
        "quero um relatório do btc",
        "como está o bitcoin?",
        "status do sistema",
        "relatório homelab",
        "oi tudo bem",  # Não deve gerar relatório
    ]
    
    for test in tests:
        report_type = detect_report_type(test)
        print(f"'{test}' -> {report_type}")
    
    print("\n=== Relatório BTC ===")
    print(generate_btc_report(24))
    
    print("\n=== Relatório Sistema ===")
    print(generate_system_report())
