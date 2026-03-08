#!/usr/bin/env python3
"""
Validador de Datasources do Grafana — Prometheus + PostgreSQL
Verifica se ambos os datasources estão respondendo corretamente
e retornando dados esperados (trading agent status, métricas, histórico)

Uso: python3 validate_grafana_datasources.py
"""

import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

try:
    import psycopg2
except ImportError:
    print("❌ psycopg2 não instalado. Use: pip install psycopg2-binary")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════
# CORES ANSI
# ═══════════════════════════════════════════════════════════════
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.END}\n")


def print_section(text: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-' * 70}{Colors.END}")


def print_ok(text: str):
    print(f"  {Colors.GREEN}✅{Colors.END} {text}")


def print_error(text: str):
    print(f"  {Colors.RED}❌{Colors.END} {text}")


def print_warn(text: str):
    print(f"  {Colors.YELLOW}⚠️ {Colors.END} {text}")


def print_info(text: str):
    print(f"  {Colors.CYAN}ℹ️ {Colors.END} {text}")


# ═══════════════════════════════════════════════════════════════
# PROMETHEUS VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_prometheus() -> Dict:
    """Valida conexão e métricas do Prometheus"""
    result = {
        "status": "error",
        "connected": False,
        "metrics": {},
        "error_msg": None
    }

    try:
        url = "http://192.168.15.2:9092/metrics"
        req = urllib.request.Request(url)
        
        print_info(f"Conectando ao Prometheus: {url}")
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode('utf-8')
            print_ok("Conexão HTTP 200 OK")
            
            result["connected"] = True
            
            # Parse text format Prometheus
            metrics_dict = {}
            for line in data.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.split('{')
                if len(parts) >= 2:
                    metric_name = parts[0]
                    # Extract value (last token)
                    value_part = line.split()[-1]
                    try:
                        metrics_dict[metric_name] = float(value_part)
                    except ValueError:
                        metrics_dict[metric_name] = value_part
            
            result["metrics"] = metrics_dict
            result["status"] = "ok"
            
    except urllib.error.URLError as e:
        result["error_msg"] = f"Erro de conexão: {str(e)}"
        result["status"] = "error"
    except Exception as e:
        result["error_msg"] = f"Erro inesperado: {str(e)}"
        result["status"] = "error"
    
    return result


# ═══════════════════════════════════════════════════════════════
# POSTGRESQL VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_postgresql() -> Dict:
    """Valida conexão e dados do PostgreSQL"""
    result = {
        "status": "error",
        "connected": False,
        "data": {},
        "error_msg": None
    }

    try:
        dsn = "host=localhost port=5433 user=postgres password=shared_memory_2026 dbname=btc_trading"
        print_info(f"Conectando ao PostgreSQL: localhost:5433/btc_trading")
        
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        
        cursor = conn.cursor()
        cursor.execute("SET search_path TO btc, public")
        
        print_ok("Conexão bem-sucedida")
        result["connected"] = True
        
        # Query 1: Contagens totais
        cursor.execute("""
            SELECT 
              (SELECT COUNT(*) FROM decisions WHERE symbol='BTC-USDT') as decisoes,
              (SELECT COUNT(*) FROM trades WHERE symbol='BTC-USDT') as trades,
              (SELECT COUNT(*) FROM market_states WHERE symbol='BTC-USDT') as market_states
        """)
        counts = cursor.fetchone()
        result["data"]["decisoes"] = counts[0]
        result["data"]["trades"] = counts[1]
        result["data"]["market_states"] = counts[2]
        
        # Query 2: Distribuição de decisões
        cursor.execute("""
            SELECT action, COUNT(*) as qtd, MAX(timestamp) as ultima
            FROM decisions 
            WHERE symbol='BTC-USDT'
            GROUP BY action 
            ORDER BY qtd DESC
        """)
        decisions = cursor.fetchall()
        result["data"]["decisions_by_action"] = {}
        for action, qtd, ts in decisions:
            result["data"]["decisions_by_action"][action] = {
                "count": qtd,
                "last_timestamp": ts.isoformat() if (ts and hasattr(ts, 'isoformat')) else str(ts) if ts else None
            }
        
        # Query 3: Distribuição de trades (dry vs live)
        cursor.execute("""
            SELECT 
              CASE WHEN dry_run THEN 'DRY' ELSE 'LIVE' END as modo,
              COUNT(*) as qtd,
              COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as wins,
              COALESCE(SUM(pnl), 0) as total_pnl
            FROM trades 
            WHERE symbol='BTC-USDT'
            GROUP BY dry_run
            ORDER BY dry_run DESC
        """)
        trades = cursor.fetchall()
        result["data"]["trades_by_mode"] = {}
        for modo, qtd, wins, pnl in trades:
            result["data"]["trades_by_mode"][modo] = {
                "count": qtd,
                "wins": wins,
                "total_pnl": float(pnl) if pnl else 0
            }
        
        # Query 4: Última atividade
        cursor.execute("""
            SELECT 'decisions' as tipo, MAX(timestamp) as ts FROM decisions WHERE symbol='BTC-USDT'
            UNION ALL
            SELECT 'trades' as tipo, MAX(timestamp) FROM trades WHERE symbol='BTC-USDT'
        """)
        activities = cursor.fetchall()
        result["data"]["last_activity"] = {}
        for tipo, ts in activities:
            result["data"]["last_activity"][tipo] = ts.isoformat() if (ts and hasattr(ts, 'isoformat')) else str(ts) if ts else None
        
        # Query 5: Verificar equity (se existe na tabela agent_state)
        try:
            cursor.execute("""
                SELECT equity_usdt, open_position_btc, live_pnl
                FROM agent_state
                WHERE symbol='BTC-USDT'
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            state = cursor.fetchone()
            if state:
                result["data"]["agent_state"] = {
                    "equity_usdt": float(state[0]) if state[0] else 0,
                    "open_position_btc": float(state[1]) if state[1] else 0,
                    "live_pnl": float(state[2]) if state[2] else 0
                }
        except Exception:
            result["data"]["agent_state"] = None
        
        cursor.close()
        conn.close()
        
        result["status"] = "ok"
        
    except psycopg2.OperationalError as e:
        result["error_msg"] = f"Erro de conexão: {str(e)}"
        result["status"] = "error"
    except Exception as e:
        result["error_msg"] = f"Erro inesperado: {str(e)}"
        result["status"] = "error"
    
    return result


# ═══════════════════════════════════════════════════════════════
# MAIN REPORT
# ═══════════════════════════════════════════════════════════════

def main():
    print_header(f"VALIDAÇÃO DATASOURCES GRAFANA\n{datetime.now().strftime('%d de março de %Y - %H:%M:%S')}")
    
    # ═══ PROMETHEUS ═══
    print_section("🔌 PROMETHEUS (http://192.168.15.2:9092/metrics)")
    
    prom_result = validate_prometheus()
    
    if prom_result["status"] != "ok":
        print_error(f"Falha na validação: {prom_result['error_msg']}")
        return False
    
    metrics = prom_result["metrics"]
    
    # Extrair métricas críticas
    print_info("Métricas Críticas:")
    
    btc_price = metrics.get("btc_price", 0)
    print(f"    • BTC Price: ${btc_price:,.2f} USD" if btc_price > 0 else f"    • BTC Price: {Colors.RED}$0.00{Colors.END} ⚠️")
    
    live_mode = metrics.get("btc_trading_live_mode", 0)
    mode_text = "💰 LIVE TRADING" if live_mode == 1 else "🧪 DRY RUN"
    mode_color = Colors.GREEN if live_mode == 1 else Colors.YELLOW
    print(f"    • Mode: {mode_color}{mode_text}{Colors.END}")
    
    agent_running = metrics.get("btc_trading_agent_running", 0)
    agent_text = "🟢 ATIVO" if agent_running == 1 else "🔴 INATIVO"
    agent_color = Colors.GREEN if agent_running == 1 else Colors.RED
    print(f"    • Agent: {agent_color}{agent_text}{Colors.END}")
    
    equity = metrics.get("btc_trading_equity_usdt", 0)
    print(f"    • Equity: ${equity:,.2f} USDT" if equity > 0 else f"    • Equity: {Colors.RED}$0.00{Colors.END} ⚠️")
    
    open_btc = metrics.get("btc_trading_open_position_btc", 0)
    print(f"    • Open Position: {open_btc:.8f} BTC" if open_btc > 0 else f"    • Open Position: 0.00000000 BTC")
    
    rsi = metrics.get("btc_trading_rsi", None)
    if rsi is not None:
        rsi_text = f"{rsi:.2f}"
        if 30 <= rsi <= 70:
            print(f"    • RSI: {rsi_text} (Normal)")
        elif rsi < 30:
            print(f"    • RSI: {Colors.GREEN}{rsi_text}{Colors.END} (Sobrevenda ✅)")
        else:
            print(f"    • RSI: {Colors.RED}{rsi_text}{Colors.END} (Sobrecompra ⚠️)")
    
    total_trades = metrics.get("btc_trading_total_trades", 0)
    print(f"    • Total Trades: {int(total_trades)}")
    
    win_rate = metrics.get("btc_trading_win_rate", 0)
    print(f"    • Win Rate: {win_rate*100:.1f}%")
    
    total_pnl = metrics.get("btc_trading_total_pnl", 0)
    pnl_color = Colors.GREEN if total_pnl > 0 else Colors.RED
    print(f"    • PnL Total: {pnl_color}${total_pnl:,.4f}{Colors.END} USDT")
    
    # ═══ POSTGRESQL ═══
    print_section("🗄️  POSTGRESQL (localhost:5433/btc_trading)")
    
    pg_result = validate_postgresql()
    
    if pg_result["status"] != "ok":
        print_error(f"Falha na validação: {pg_result['error_msg']}")
        return False
    
    data = pg_result["data"]
    
    print_info("Contagem de Registros (symbol='BTC-USDT'):")
    print(f"    • Decisões: {data['decisoes']}")
    print(f"    • Trades: {data['trades']}")
    print(f"    • Market States: {data['market_states']}")
    
    # Distribuição de decisões
    if data.get("decisions_by_action"):
        print_info("Distribuição de Decisões:")
        for action, info in sorted(data["decisions_by_action"].items()):
            count = info["count"]
            pct = (count / data["decisoes"] * 100) if data["decisoes"] > 0 else 0
            emoji = "🟢" if action == "BUY" else ("🔴" if action == "SELL" else "🔵")
            last_ts = info["last_timestamp"]
            # Apenas mostrar ação se houver timestamp
            ts_str = f" (último: {last_ts[:10]})" if last_ts else ""
            print(f"    • {emoji} {action}: {count} ({pct:.1f}%){ts_str}")
    
    # Distribuição de trades
    if data.get("trades_by_mode"):
        print_info("Distribuição de Trades:")
        for mode, info in sorted(data["trades_by_mode"].items()):
            count = info["count"]
            wins = info["wins"]
            wr = (wins / count * 100) if count > 0 else 0
            pnl = info["total_pnl"]
            pnl_color = Colors.GREEN if pnl > 0 else Colors.RED
            print(f"    • {mode}: {count} trades ({wins} wins, {wr:.1f}% WR) — PnL: {pnl_color}${pnl:,.4f}{Colors.END}")
    
    # Última atividade
    if data.get("last_activity"):
        print_info("Última Atividade:")
        for tipo, ts in data["last_activity"].items():
            if ts:
                try:
                    # Tente como ISO format primeiro, depois como unix timestamp
                    try:
                        dt = datetime.fromisoformat(ts)
                    except:
                        # Unix timestamp em segundos
                        dt = datetime.fromtimestamp(float(ts))
                    
                    delta = datetime.now() - dt
                    h = int(delta.total_seconds() // 3600)
                    m = int((delta.total_seconds() % 3600) // 60)
                    print(f"    • {tipo.title()}: {dt.isoformat()[:19]} (há {h}h {m}m atrás)")
                except Exception as e:
                    print(f"    • {tipo.title()}: {ts}")
            else:
                print(f"    • {tipo.title()}: Sem dados")
    
    # ═══ ANOMALIAS ═══
    print_section("⚠️  DETECÇÃO DE ANOMALIAS")
    
    anomalies_found = False
    
    # Verificar modo de trading
    if live_mode != 1:
        print_error(f"Modo DRY detectado (live_mode={live_mode}) — esperado LIVE (1)")
        anomalies_found = True
    else:
        print_ok("Modo LIVE ativo (correto)")
    
    # Verificar se há decisões recentes
    if data.get("decisions_by_action"):
        max_ts = max([info.get("last_timestamp") for info in data["decisions_by_action"].values() if info.get("last_timestamp")])
        if max_ts:
            try:
                # Tente como ISO format primeiro, depois como unix timestamp
                try:
                    dt = datetime.fromisoformat(max_ts)
                except:
                    dt = datetime.fromtimestamp(float(max_ts))
                
                delta = datetime.now() - dt
                hours_ago = delta.total_seconds() / 3600
                
                if hours_ago > 2:
                    print_warn(f"Sem decisões há {hours_ago:.1f} horas (esperado <1h)")
                    anomalies_found = True
                else:
                    print_ok(f"Decisões ativas (última há {hours_ago:.1f}h)")
            except Exception as e:
                print_info(f"Não foi possível validar timestamp: {str(e)[:50]}")
    
    # Validar ranges
    if rsi is not None:
        if not (0 <= rsi <= 100):
            print_error(f"RSI fora do range 0-100: {rsi}")
            anomalies_found = True
        else:
            print_ok(f"RSI dentro do range (0-100)")
    
    if not (0 <= win_rate <= 1):
        print_error(f"Win rate fora do range 0-1: {win_rate}")
        anomalies_found = True
    else:
        print_ok(f"Win rate dentro do range (0-1)")
    
    # Verificar equity sensata
    if equity == 0:
        print_warn(f"Equity zerada — verifique agent state")
        anomalies_found = True
    elif equity < 10:
        print_warn(f"Equity muito baixa: ${equity:.2f} — risco de liquidação")
        anomalies_found = True
    else:
        print_ok(f"Equity dentro de faixa sensata (${equity:,.2f})")
    
    if not anomalies_found:
        print_ok("Nenhuma anomalia detectada ✅")
    
    # ═══ RESUMO FINAL ═══
    print_section("✅ RESUMO FINAL")
    
    print_ok("Prometheus datasource operacional")
    print_ok("PostgreSQL datasource operacional")
    
    if live_mode == 1 and agent_running == 1:
        print_ok(f"Trading agent ATIVO em LIVE MODE")
    elif agent_running == 1:
        print_warn(f"Trading agent ativo mas em DRY RUN")
    else:
        print_warn(f"Trading agent INATIVO")
    
    if data["trades"] > 0:
        print_ok(f"Histórico de trades disponível ({data['trades']} registros)")
    else:
        print_warn(f"Sem histórico de trades")
    
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'═' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}Todos os datasources validados com sucesso!{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'═' * 70}{Colors.END}\n")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrompido pelo usuário{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Erro não capturado: {str(e)}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
