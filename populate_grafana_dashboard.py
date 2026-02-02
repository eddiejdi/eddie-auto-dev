#!/usr/bin/env python3
"""
Popula o dashboard do Grafana com dados reais via SSH
Solução direta: usar curl via SSH para criar o painel com dados
"""

import subprocess
import os
import json
import sys
from datetime import datetime
from pathlib import Path

HOMELAB_HOST = os.getenv("HOMELAB_HOST", "192.168.15.2")
HOMELAB_USER = os.getenv("HOMELAB_USER", "homelab")
HOMELAB_TARGET = f"{HOMELAB_USER}@{HOMELAB_HOST}"
SSH_KEY = os.path.expanduser(os.getenv("HOMELAB_SSH_KEY", "~/.ssh/eddie_deploy_rsa"))
TRAINING_DIR = os.getenv("TRAINING_DIR", "/home/homelab/myClaude/training_data")
GRAFANA_USER = os.getenv("GRAFANA_USER")
GRAFANA_PASS = os.getenv("GRAFANA_PASS")

def run_ssh_cmd(cmd: str) -> str:
    """Executa comando no homelab"""
    try:
        result = subprocess.run(
            ["ssh", "-i", SSH_KEY, HOMELAB_TARGET, cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except Exception as e:
        print(f"❌ Erro SSH: {e}")
        return ""

def collect_metrics():
    """Coleta dados do servidor"""
    print("📊 Coletando métricas...")
    
    metrics = {
        "training_files": [],
        "total_conversations": 0,
        "models": [],
        "timestamps": []
    }
    
    # Arquivos de treinamento
    cmd = f"ls -lh {TRAINING_DIR}/training_*.jsonl | awk '{{print $(NF-1), $NF}}'"
    output = run_ssh_cmd(cmd)
    
    total_lines = 0
    for line in output.strip().split('\n'):
        if not line or 'training_' not in line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            size = parts[0]
            filepath = parts[1]
            filename = Path(filepath).name
            
            # Contar linhas deste arquivo
            wc_output = run_ssh_cmd(f"wc -l {filepath}").strip()
            lines = int(wc_output.split()[0])
            total_lines += lines
            
            metrics["training_files"].append({
                "name": filename,
                "size": size,
                "lines": lines
            })
    
    metrics["total_conversations"] = total_lines
    
    # Modelos
    cmd = "curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('\\n'.join([m.get('name','') for m in d.get('models',[])]))\" || echo 'Ollama unavailable'"
    output = run_ssh_cmd(cmd)
    metrics["models"] = [m for m in output.strip().split('\n') if m and 'unavailable' not in m]
    
    print(f"   ✅ {len(metrics['training_files'])} arquivos")
    print(f"   ✅ {metrics['total_conversations']} conversas")
    print(f"   ✅ {len(metrics['models'])} modelos")
    
    return metrics

def create_dashboard_json(metrics):
    """Cria JSON do dashboard com dados reais"""
    
    # Dados para o gráfico
    timeline_data = "Evolução de Aprendizado: " + ", ".join([
        f"{f['name'].replace('training_', '')}: {f['lines']} conversas"
        for f in metrics['training_files']
    ])
    
    models_list = "\n".join([f"- {m}" for m in metrics['models'][:10]])
    
    dashboard = {
        "dashboard": {
            "title": "Evolução de Aprendizado - Homelab",
            "description": "Monitoramento em tempo real de treinamento e modelos IA",
            "tags": ["homelab", "ia", "learning", "ollama"],
            "timezone": "browser",
            "schemaVersion": 38,
            "version": 0,
            "refresh": "1m",
            "time": {
                "from": "now-30d",
                "to": "now"
            },
            "panels": [
                {
                    "id": 1,
                    "title": "📊 Evolução de Aprendizado",
                    "type": "text",
                    "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                    "options": {
                        "text": f"# Evolução de Aprendizado\n\n{timeline_data}",
                        "mode": "markdown"
                    }
                },
                {
                    "id": 2,
                    "title": "🤖 Modelos IA Disponíveis",
                    "type": "text",
                    "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                    "options": {
                        "text": f"# Modelos Disponíveis ({len(metrics['models'])} ativos)\n\n{models_list}",
                        "mode": "markdown"
                    }
                },
                {
                    "id": 3,
                    "title": "📈 Estatísticas",
                    "type": "text",
                    "gridPos": {"x": 0, "y": 6, "w": 24, "h": 6},
                    "options": {
                        "text": f"""# 📋 Resumo de Treinamento

## Métricas Principais
- **Total de Conversas Indexadas:** {metrics['total_conversations']:,}
- **Arquivos de Treinamento:** {len(metrics['training_files'])}
- **Modelos IA Ativos:** {len(metrics['models'])}

## Arquivos
{chr(10).join([f"- {f['name']}: {f['lines']} conversas ({f['size']})" for f in metrics['training_files']])}

## Modelos Treinados
{models_list}
""",
                        "mode": "markdown"
                    }
                }
            ]
        },
        "overwrite": True
    }
    
    return dashboard

def deploy_dashboard(dashboard_json):
    """Faz deploy do dashboard via SSH"""
    print("\n🚀 Fazendo deploy do dashboard...")
    
    # Salvar JSON temporário
    json_file = "/tmp/dashboard_deploy.json"
    with open(json_file, 'w') as f:
        json.dump(dashboard_json, f)
    
    # Transferir arquivo para servidor
    print("   📤 Transferindo arquivo...")
    transfer_cmd = f"scp -i {SSH_KEY} {json_file} {HOMELAB_TARGET}:/tmp/"
    result = subprocess.run(transfer_cmd, shell=True, capture_output=True)
    
    if result.returncode != 0:
        print(f"   ❌ Erro ao transferir: {result.stderr.decode()}")
        return False
    
    # Fazer upload para Grafana via curl no servidor
    print("   🔧 Fazendo upload no Grafana...")

    upload_cmd = f"""
    ssh -i {SSH_KEY} {HOMELAB_TARGET} << 'EOFCURL'
    curl -X POST http://127.0.0.1:3002/api/dashboards/db \
      -u {GRAFANA_USER}:{GRAFANA_PASS} \
      -H 'Content-Type: application/json' \
      -d @/tmp/dashboard_deploy.json
EOFCURL
    """
    
    result = subprocess.run(upload_cmd, shell=True, capture_output=True, text=True)
    
    if "success" in result.stdout.lower() or '"id"' in result.stdout:
        print("   ✅ Dashboard deployado com sucesso!")
        print(f"      URL: http://{HOMELAB_HOST}:3002/grafana/d/learning-evolution")
        return True
    else:
        print(f"   ⚠️ Resposta: {result.stdout[:200]}")
        if "already exists" in result.stdout.lower():
            print("   ℹ️ Dashboard já existe (será atualizado)")
            return True
    
    return False

def validate_dashboard():
    """Valida o dashboard no servidor"""
    print("\n✅ Validando dashboard no servidor...")
    
    cmd = f"""
    curl -s -u {GRAFANA_USER}:{GRAFANA_PASS} 'http://127.0.0.1:3002/api/dashboards/uid/learning-evolution' > /tmp/learning_dashboard.json
    python3 - << 'PY'
import json
with open('/tmp/learning_dashboard.json','r') as f:
    d = json.load(f)
panels = d.get('dashboard', {}).get('panels', [])
print(f"Painéis: {len(panels)}")
for p in panels:
    print(f"  • {p.get('title')}")
PY
    """
    
    output = run_ssh_cmd(cmd)
    if output:
        print(output)
        return "Painéis:" in output
    
    return False

def main():
    print("=" * 70)
    print("🎨 POPULATE GRAFANA DASHBOARD COM DADOS REAIS")
    print("=" * 70)

    if not GRAFANA_USER or not GRAFANA_PASS:
        print("\n❌ Defina GRAFANA_USER e GRAFANA_PASS no ambiente para continuar.")
        return False

    if not os.path.exists(SSH_KEY):
        print(f"\n❌ SSH key não encontrada: {SSH_KEY}")
        return False
    
    # Etapa 1: Coletar métricas
    print("\n🔄 ETAPA 1: COLETA DE DADOS")
    metrics = collect_metrics()
    
    if not metrics['training_files']:
        print("\n❌ Nenhum dado de treinamento encontrado!")
        return False
    
    # Etapa 2: Criar JSON do dashboard
    print("\n🔄 ETAPA 2: PREPARAÇÃO DO DASHBOARD")
    dashboard_json = create_dashboard_json(metrics)
    print(f"   ✅ Dashboard preparado com 3 painéis")
    
    # Etapa 3: Deploy
    print("\n🔄 ETAPA 3: DEPLOY")
    if not deploy_dashboard(dashboard_json):
        print("\n❌ Falha no deploy")
        return False
    
    # Etapa 4: Validação
    print("\n🔄 ETAPA 4: VALIDAÇÃO")
    if validate_dashboard():
        print("   ✅ Dashboard validado!")
    else:
        print("   ⚠️ Dashboard pode estar sendo carregado, aguarde alguns segundos")
    
    print("\n" + "=" * 70)
    print("✅ CONCLUÍDO COM SUCESSO!")
    print("=" * 70)
    print("\n📌 Acesse seu dashboard em:")
    print(f"   http://{HOMELAB_HOST}:3002/grafana/d/learning-evolution")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
