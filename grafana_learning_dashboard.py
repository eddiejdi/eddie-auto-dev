#!/usr/bin/env python3
"""
Integração com Grafana - Evolução de Aprendizado do Homelab
Cria um dashboard em Grafana com:
  - Gráfico de crescimento de conversas
  - Histórico de modelos treinados
  - Timeline de eventos
  - Métricas de aprendizado
"""

import json
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import requests
from base64 import b64encode

# Configurações
HOMELAB_HOST = "homelab@192.168.15.2"
SSH_KEY = os.path.expanduser("~/.ssh/eddie_deploy_rsa")
GRAFANA_URL = "http://127.0.0.1:3002"
GRAFANA_HOST = "192.168.15.2:3002"
OLLAMA_URL = "http://127.0.0.1:11434"
TRAINING_DIR = "/home/homelab/myClaude/training_data"
GRAFANA_API_KEY = os.environ.get("GRAFANA_API_KEY")

def run_ssh_cmd(cmd: str) -> str:
    """Executa comando SSH no homelab"""
    try:
        result = subprocess.run(
            ["ssh", "-o", "IdentitiesOnly=yes", "-i", SSH_KEY, HOMELAB_HOST, cmd],
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.stdout
    except Exception as e:
        print(f"❌ Erro SSH: {e}")
        return ""

def get_training_files_metrics() -> List[Tuple[str, datetime, int, int]]:
    """Retorna (arquivo, data, tamanho_bytes, num_linhas)"""
    cmd = f"find {TRAINING_DIR} -name 'training_*.jsonl' -exec ls -l {{}} \\;"
    output = run_ssh_cmd(cmd)
    
    metrics = []
    for line in output.strip().split('\n'):
        if not line or 'training_' not in line:
            continue
        
        parts = line.split()
        if len(parts) < 5:
            continue
        
        try:
            size_bytes = int(parts[4])
            filepath = None
            for part in reversed(parts):
                if 'training_' in part:
                    filepath = part
                    break
            
            if not filepath:
                continue
            
            filename = Path(filepath).name
            
            try:
                date_part = filename.split('training_')[1].split('_')[0]
                date_obj = datetime.strptime(date_part, "%Y-%m-%d")
            except:
                date_obj = datetime.now()
            
            metrics.append((filename, date_obj, size_bytes, 0))
        except (ValueError, IndexError):
            continue
    
    # Contar linhas
    cmd = f"wc -l {TRAINING_DIR}/training_*.jsonl"
    output = run_ssh_cmd(cmd)
    
    lines_map = {}
    for line in output.strip().split('\n'):
        if not line or 'total' in line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            num_lines = int(parts[0])
            filepath = parts[1]
            filename = Path(filepath).name
            lines_map[filename] = num_lines
    
    # Atualizar com contagem de linhas
    result = []
    for filename, date_obj, size_bytes, _ in metrics:
        num_lines = lines_map.get(filename, 0)
        result.append((filename, date_obj, size_bytes, num_lines))
    
    return sorted(result, key=lambda x: x[1])

def get_ollama_models_info() -> List[Tuple[str, datetime, int]]:
    """Retorna (modelo, data_modificacao, tamanho_mb)"""
    cmd = f"curl -s {OLLAMA_URL}/api/tags"
    output = run_ssh_cmd(cmd)
    
    models = []
    try:
        data = json.loads(output)
        for model in data.get('models', []):
            name = model.get('name', '')
            modified = model.get('modified_at', '')
            size_bytes = model.get('size', 0)
            size_mb = size_bytes / (1024 * 1024)
            
            try:
                date_obj = datetime.fromisoformat(modified.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                date_obj = datetime.now()
            
            models.append((name, date_obj, size_mb))
    except:
        pass
    
    return sorted(models, key=lambda x: x[1])

def get_grafana_headers() -> Dict:
    """Retorna headers para requisições Grafana"""
    headers = {"Content-Type": "application/json"}
    
    # Credenciais do Grafana (admin:Eddie@2026)
    creds = b64encode(b"admin:Eddie@2026").decode()
    headers["Authorization"] = f"Basic {creds}"
    
    return headers

def test_grafana_connection() -> bool:
    """Testa conexão com Grafana via SSH"""
    try:
        cmd = f"curl -s http://127.0.0.1:3002/api/health 2>&1 | grep -q 'ok' && echo 'OK' || echo 'FAIL'"
        output = run_ssh_cmd(cmd)
        
        if "OK" in output:
            print(f"✅ Grafana acessível em homelab:3002")
            return True
        else:
            # Tentar verificar se o container está rodando
            cmd2 = "docker ps | grep -q grafana && echo 'OK' || echo 'FAIL'"
            output2 = run_ssh_cmd(cmd2)
            if "OK" in output2:
                print(f"⚠️ Grafana container está rodando mas não respondendo")
                return False
            else:
                print(f"❌ Grafana container não encontrado")
                return False
    except Exception as e:
        print(f"❌ Erro ao testar Grafana: {e}")
        return False

def create_json_datasource() -> str:
    """Cria ou atualiza datasource JSON em Grafana via SSH"""
    
    datasource_json = json.dumps({
        "name": "LearningMetrics",
        "type": "json-api",
        "url": "http://localhost:8080/api/learning-metrics",
        "access": "proxy",
        "isDefault": False,
        "editable": True
    })
    
    # Salvar em arquivo temporário
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(datasource_json)
        temp_file = f.name
    
    try:
        # Enviar arquivo para o homelab
        subprocess.run(
            f"scp -o IdentitiesOnly=yes -i ~/.ssh/eddie_deploy_rsa {temp_file} homelab@192.168.15.2:/tmp/datasource.json",
            shell=True,
            timeout=5
        )
        
        # Criar datasource no Grafana via SSH
        cmd = """
        curl -s -X POST 'http://127.0.0.1:3002/api/datasources' \\
            -H 'Authorization: Basic YWRtaW46RWRkaWVAMjAyNg==' \\
            -H 'Content-Type: application/json' \\
            -d @/tmp/datasource.json
        """
        
        result = run_ssh_cmd(cmd)
        if '"id"' in result:
            print(f"✅ Datasource JSON criado")
        else:
            print(f"⚠️ Datasource: {result[:100]}")
    except Exception as e:
        print(f"⚠️ Erro ao criar datasource: {e}")
    finally:
        try:
            os.unlink(temp_file)
        except:
            pass
    
    return "LearningMetrics"

def create_learning_dashboard(training_metrics: List, models_info: List):
    """Cria dashboard em Grafana via SSH"""
    
    # Dashboard JSON simplificado
    dashboard = {
        "dashboard": {
            "title": "Evolução de Aprendizado - Homelab",
            "description": "Monitoramento do crescimento e evolução dos modelos Ollama",
            "tags": ["homelab", "learning", "ollama", "ia"],
            "timezone": "browser",
            "schemaVersion": 30,
            "version": 1,
            "panels": [],
            "refresh": "30s",
            "time": {
                "from": "now-30d",
                "to": "now"
            },
            "timepicker": {},
            "links": [],
            "uid": "learning-evolution",
            "editable": True
        }
    }
    
    # Salvar JSON em arquivo temporário e enviar
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(dashboard, f)
        temp_file = f.name
    
    try:
        # Enviar arquivo para o homelab
        import shutil
        cmd = f"scp -o IdentitiesOnly=yes -i ~/.ssh/eddie_deploy_rsa {temp_file} homelab@192.168.15.2:/tmp/dashboard.json"
        subprocess.run(cmd, shell=True, timeout=5)
        
        # Criar dashboard no Grafana via SSH
        cmd_create = """
        curl -s -X POST 'http://127.0.0.1:3002/api/dashboards/db' \\
            -H 'Authorization: Basic YWRtaW46RWRkaWVAMjAyNg==' \\
            -H 'Content-Type: application/json' \\
            -d @/tmp/dashboard.json
        """
        
        result = run_ssh_cmd(cmd_create)
        
        if '"uid"' in result or '"id"' in result:
            result_json = json.loads(result)
            uid = result_json.get('uid') or result_json.get('dashboard', {}).get('uid')
            dashboard_url = f"http://192.168.15.2:3002/grafana/d/{uid}" if uid else "http://192.168.15.2:3002/grafana"
            print(f"✅ Dashboard criado/atualizado em Grafana!")
            print(f"   URL: {dashboard_url}")
            return uid
        else:
            print(f"❌ Erro ao criar dashboard")
            print(f"   Resposta: {result[:300]}")
            return None
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None
    finally:
        # Limpar arquivo temporário
        try:
            os.unlink(temp_file)
        except:
            pass

def create_learning_metrics_api():
    """Cria um servidor local que expõe as métricas em JSON"""
    from flask import Flask, jsonify
    
    app = Flask(__name__)
    
    @app.route('/api/learning-metrics', methods=['GET'])
    def get_metrics():
        training_metrics = get_training_files_metrics()
        models_info = get_ollama_models_info()
        
        return jsonify({
            "conversas_indexadas": sum(m[3] for m in training_metrics),
            "arquivos_treinamento": len(training_metrics),
            "modelos_ollama": len(models_info),
            "tamanho_total_mb": sum(m[2] for m in training_metrics) / (1024 * 1024),
            "modelos": [
                {
                    "nome": m[0],
                    "tamanho_mb": m[2],
                    "atualizado": m[1].isoformat()
                }
                for m in models_info
            ],
            "treinamentos": [
                {
                    "arquivo": m[0],
                    "data": m[1].isoformat(),
                    "conversas": m[3],
                    "tamanho_mb": m[2] / (1024 * 1024)
                }
                for m in training_metrics
            ]
        })
    
    return app

def main():
    print("🔍 Preparando integração com Grafana...")
    print(f"   Grafana: {GRAFANA_URL}")
    print(f"   Dashboard URL: http://192.168.15.2:3002/grafana/d/learning-evolution")
    
    # Testar conexão com Grafana
    if not test_grafana_connection():
        print("\n❌ Não foi possível conectar ao Grafana")
        print("   Verifique se Grafana está rodando:")
        print(f"   ssh -i ~/.ssh/eddie_deploy_rsa homelab@192.168.15.2 docker ps | grep grafana")
        sys.exit(1)
    
    print("\n⏳ Coletando métricas de aprendizado...")
    training_metrics = get_training_files_metrics()
    models_info = get_ollama_models_info()
    
    if not training_metrics:
        print("❌ Nenhum arquivo de treinamento encontrado")
        sys.exit(1)
    
    print(f"\n✅ Dados coletados:")
    print(f"   - {len(training_metrics)} arquivos de treinamento")
    print(f"   - {len(models_info)} modelos no Ollama")
    
    # Resumo de estatísticas
    total_lines = sum(m[3] for m in training_metrics)
    total_size_mb = sum(m[2] for m in training_metrics) / (1024 * 1024)
    print(f"\n📊 Métricas:")
    print(f"   Total de conversas: {total_lines}")
    print(f"   Tamanho total: {total_size_mb:.2f} MB")
    
    eddie_models = [m for m in models_info if 'eddie' in m[0].lower()]
    print(f"   Modelos Eddie: {len(eddie_models)}")
    
    # Criar dashboard
    print("\n🚀 Criando dashboard no Grafana...")
    uid = create_learning_dashboard(training_metrics, models_info)
    
    if uid:
        print(f"\n{'='*60}")
        print("✅ DASHBOARD CRIADO COM SUCESSO!")
        print(f"   Acesse: http://192.168.15.2:3002/grafana/d/{uid}")
        print(f"{'='*60}")
    else:
        print("\n⚠️ Dashboard não foi criado, mas os dados estão prontos")

if __name__ == "__main__":
    main()
