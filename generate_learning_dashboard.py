#!/usr/bin/env python3
"""
Dashboard Interativo de Evolução de Aprendizado - Homelab
Gera um dashboard HTML/Plotly com visualizações interativas
"""

import json
import subprocess
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import base64

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
except ImportError:
    print("Instalando plotly...")
    subprocess.run(["pip", "install", "plotly", "-q"])
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots

# Configurações
HOMELAB_HOST = "homelab@192.168.15.2"
SSH_KEY = os.path.expanduser("~/.ssh/eddie_deploy_rsa")
OLLAMA_URL = "http://127.0.0.1:11434"
TRAINING_DIR = "/home/homelab/myClaude/training_data"

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

def create_interactive_dashboard(training_metrics: List, models_info: List):
    """Cria dashboard interativo com Plotly"""
    
    if not training_metrics:
        print("❌ Sem dados de treinamento")
        return
    
    # Preparar dados
    dates_train = [m[1] for m in training_metrics]
    lines_count = [m[3] for m in training_metrics]
    file_sizes_kb = [m[2] / 1024 for m in training_metrics]
    filenames = [Path(m[0]).stem for m in training_metrics]
    
    # Criar subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Crescimento de Conversas", "Tamanho dos Arquivos", 
                       "Modelos Ollama", "Timeline de Eventos"),
        specs=[[{"type": "scatter"}, {"type": "bar"}],
               [{"type": "bar"}, {"type": "scatter"}]]
    )
    
    # Gráfico 1: Conversas
    fig.add_trace(
        go.Scatter(x=dates_train, y=lines_count, mode='lines+markers',
                   name='Conversas', line=dict(color='#2E86AB', width=3),
                   marker=dict(size=10, symbol='circle'),
                   fill='tozeroy', fillcolor='rgba(46, 134, 171, 0.2)',
                   hovertemplate='<b>%{x|%d/%m/%Y}</b><br>Conversas: %{y}<extra></extra>'),
        row=1, col=1
    )
    
    # Gráfico 2: Tamanho dos arquivos
    fig.add_trace(
        go.Bar(x=filenames, y=file_sizes_kb, name='Tamanho (KB)',
               marker=dict(color='#A23B72'),
               hovertemplate='<b>%{x}</b><br>Tamanho: %{y:.1f}KB<extra></extra>'),
        row=1, col=2
    )
    
    # Gráfico 3: Modelos
    if models_info:
        eddie_models = [m for m in models_info if 'eddie' in m[0].lower()]
        model_names = [m[0].split(':')[0] for m in eddie_models]
        model_sizes = [m[2] for m in eddie_models]
        model_dates = [m[1].strftime('%d/%m') for m in eddie_models]
        
        fig.add_trace(
            go.Bar(x=model_names, y=model_sizes, name='Tamanho (MB)',
                   marker=dict(color='#F18F01'),
                   text=model_dates,
                   textposition='outside',
                   hovertemplate='<b>%{x}</b><br>Tamanho: %{y:.0f}MB<br>Data: %{text}<extra></extra>'),
            row=2, col=1
        )
    
    # Gráfico 4: Timeline
    timeline_dates = dates_train
    timeline_labels = [f"{lines} conversas" for lines in lines_count]
    timeline_y = list(range(len(timeline_dates)))
    
    fig.add_trace(
        go.Scatter(x=timeline_dates, y=timeline_y, mode='markers+text',
                   name='Eventos',
                   marker=dict(size=15, color='#2E86AB', symbol='circle'),
                   text=timeline_labels,
                   textposition='top center',
                   hovertemplate='<b>%{x|%d/%m/%Y}</b><br>%{text}<extra></extra>'),
        row=2, col=2
    )
    
    # Atualizar layout
    fig.update_xaxes(title_text="Data", row=1, col=1)
    fig.update_yaxes(title_text="Conversas", row=1, col=1)
    
    fig.update_xaxes(title_text="Arquivo", row=1, col=2)
    fig.update_yaxes(title_text="Tamanho (KB)", row=1, col=2)
    
    fig.update_xaxes(title_text="Modelo", row=2, col=1)
    fig.update_yaxes(title_text="Tamanho (MB)", row=2, col=1)
    
    fig.update_xaxes(title_text="Data", row=2, col=2)
    fig.update_yaxes(title_text="", row=2, col=2, showticklabels=False)
    
    fig.update_layout(
        title_text="<b>Evolução do Aprendizado - Servidor Homelab</b>",
        height=800,
        showlegend=True,
        hovermode='closest',
        template='plotly_white'
    )
    
    # Salvar HTML
    output_path = Path(__file__).parent / "learning_evolution_dashboard.html"
    fig.write_html(str(output_path))
    print(f"\n✅ Dashboard salvo: {output_path}")
    
    return str(output_path)

def main():
    print("🔍 Gerando dashboard interativo de evolução do aprendizado...")
    print("⏳ Coletando dados...")
    
    # Coletar métricas
    training_metrics = get_training_files_metrics()
    models_info = get_ollama_models_info()
    
    if not training_metrics:
        print("❌ Nenhum arquivo de treinamento encontrado")
        return
    
    print(f"\n✅ Dados coletados:")
    print(f"   - {len(training_metrics)} arquivos de treinamento")
    print(f"   - {len(models_info)} modelos no Ollama")
    
    # Exibir resumo
    print(f"\n📊 Resumo de Dados:")
    total_lines = sum(m[3] for m in training_metrics)
    total_size_mb = sum(m[2] for m in training_metrics) / (1024 * 1024)
    print(f"   Total de conversas indexadas: {total_lines}")
    print(f"   Total de dados de treinamento: {total_size_mb:.2f} MB")
    
    eddie_models = [m for m in models_info if 'eddie' in m[0].lower()]
    print(f"   Modelos Eddie disponíveis: {len(eddie_models)}")
    for model_name, date, size_mb in eddie_models:
        print(f"      - {model_name}: {size_mb:.0f}MB (atualizado em {date.strftime('%d/%m/%Y')})")
    
    # Gerar dashboard
    html_path = create_interactive_dashboard(training_metrics, models_info)
    
    print(f"\n" + "="*60)
    print("✅ DASHBOARD GERADO COM SUCESSO!")
    print(f"   Arquivo: {html_path}")
    print(f"   Abra em um navegador para visualizar interativamente")
    print("="*60)

if __name__ == "__main__":
    main()
