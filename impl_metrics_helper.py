#!/usr/bin/env python3
"""
Script auxiliar para implementar métricas Prometheus no Shared Central
"""

import os
import subprocess

def print_status(msg, status="info"):
    emoji = {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "progress": "⏳"
    }
    print(f"{emoji.get(status, '•')} {msg}")

def find_file(pattern):
    """Procura arquivo no repo"""
    result = subprocess.run(
        f"find . -name '{pattern}' -type f 2>/dev/null | head -1",
        shell=True,
        capture_output=True,
        text=True,
        cwd="/home/edenilson/shared-auto-dev"
    )
    return result.stdout.strip()

def check_metric_in_file(filepath, metric_name):
    """Verifica se métrica já foi adicionada"""
    if not os.path.exists(filepath):
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
        return metric_name in content

def main():
    print("\n" + "="*80)
    print("🔧 IMPLEMENTADOR DE MÉTRICAS — SHARED CENTRAL DASHBOARD")
    print("="*80)
    
    files_to_check = {
        "agent_manager.py": {
            "metrics": ["agent_count_total"],
            "pattern": "*agent_manager.py"
        },
        "agent_interceptor.py": {
            "metrics": ["message_rate_total", "conversation_count_total"],
            "pattern": "*agent_interceptor.py"
        }
    }
    
    print("\n🔍 Procurando arquivos necessários...\n")
    
    found_files = {}
    for filename, info in files_to_check.items():
        filepath = find_file(info["pattern"])
        if filepath:
            print_status(f"Encontrado: {filepath}", "success")
            found_files[filename] = filepath
        else:
            print_status(f"NÃO ENCONTRADO: {filename}", "error")
    
    if not found_files:
        print_status("Nenhum arquivo foi encontrado. Abortando.", "error")
        return
    
    print("\n" + "="*80)
    print("📋 PRÓXIMOS PASSOS")
    print("="*80)
    
    print("""
1. ABRA O ARQUIVO: specialized_agents/agent_manager.py
   └─ Procure por: 'class AgentManager'
   └─ Adicione imports de Prometheus (ver ACTION_PLAN_NO_DATA_GAUGES.md)
   └─ Crie método _update_agent_metrics()
   └─ Chame em start_agent() e stop_agent()

2. ABRA O ARQUIVO: specialized_agents/agent_interceptor.py
   └─ Procure por: 'class AgentInterceptor' ou 'def publish()'
   └─ Adicione imports de Prometheus
   └─ Incremente counters em publish() e log_response()

3. TESTE:
   └─ sudo systemctl restart specialized-agents-api
   └─ python3 validate_shared_central_api.py

📄 REFERÊNCIA COMPLETA:
   /home/edenilson/shared-auto-dev/ACTION_PLAN_NO_DATA_GAUGES.md

⏱️ TEMPO ESTIMADO: 30-45 minutos por arquivo
    """)
    
    print("\n" + "="*80)
    print("🚀 DEPOIS DE IMPLEMENTAR, EXECUTE:")
    print("="*80)
    
    print("""
# Reiniciar serviço
sudo systemctl restart specialized-agents-api
sleep 5

# Validar
python3 validate_shared_central_api.py

# Monitorar logs
journalctl -u specialized-agents-api -f

# Verificar métricas
curl -s http://192.168.15.2:9090/api/v1/query?query=agent_count_total | jq
    """)

if __name__ == "__main__":
    main()
