#!/usr/bin/env python3
"""
Gráfico de Evolução do Aprendizado - Servidor Homelab
Analisa: 
  - Crescimento de dados de treinamento (linhas de conversas)
  - Modelos criados e suas datas
  - Tamanho dos arquivos de treinamento
  - Histórico de modificações dos modelos
"""

import json
import subprocess
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict

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
            # Extrair filepath - é sempre o último elemento após split()
            filepath = None
            for part in reversed(parts):
                if 'training_' in part:
                    filepath = part
                    break
            
            if not filepath:
                continue
            
            filename = Path(filepath).name
            
            # Extrair data do nome do arquivo
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
            if 'eddie' in name.lower() or 'qwen' in name.lower() or 'llama' in name.lower():
                modified = model.get('modified_at', '')
                size_bytes = model.get('size', 0)
                size_mb = size_bytes / (1024 * 1024)
                
                try:
                    # Parse ISO timestamp
                    date_obj = datetime.fromisoformat(modified.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    date_obj = datetime.now()
                
                models.append((name, date_obj, size_mb))
    except:
        pass
    
    return sorted(models, key=lambda x: x[1])

def create_evolution_graph(training_metrics: List, models_info: List):
    """Cria gráfico de evolução com múltiplas métricas"""
    
    if not training_metrics:
        print("❌ Sem dados de treinamento disponíveis")
        return
    
    # Preparar dados
    dates_train = [m[1] for m in training_metrics]
    lines_count = [m[3] for m in training_metrics]
    file_sizes_kb = [m[2] / 1024 for m in training_metrics]
    
    # Criar figura com subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Evolução do Aprendizado - Servidor Homelab', fontsize=16, fontweight='bold')
    
    # ==================== Gráfico 1: Conversas por Data ====================
    ax1.plot(dates_train, lines_count, marker='o', linewidth=2, markersize=8, color='#2E86AB', label='Conversas')
    ax1.fill_between(dates_train, lines_count, alpha=0.3, color='#2E86AB')
    ax1.set_title('📊 Crescimento de Conversas Indexadas', fontweight='bold')
    ax1.set_xlabel('Data')
    ax1.set_ylabel('Número de Conversas')
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
    
    # Adicionar valores nos pontos
    for i, (date, count) in enumerate(zip(dates_train, lines_count)):
        ax1.annotate(f'{int(count)}', (date, count), textcoords="offset points", 
                    xytext=(0,10), ha='center', fontsize=9)
    
    # ==================== Gráfico 2: Tamanho dos Arquivos ====================
    ax2.bar(range(len(training_metrics)), file_sizes_kb, color='#A23B72', alpha=0.7)
    ax2.set_title('📁 Tamanho dos Arquivos de Treinamento', fontweight='bold')
    ax2.set_xlabel('Arquivo')
    ax2.set_ylabel('Tamanho (KB)')
    ax2.set_xticks(range(len(training_metrics)))
    ax2.set_xticklabels([Path(m[0]).stem.split('_', 1)[1] for m in training_metrics], rotation=45, ha='right')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Adicionar valores nas barras
    for i, (size, date) in enumerate(zip(file_sizes_kb, dates_train)):
        ax2.text(i, size, f'{size:.1f}KB', ha='center', va='bottom', fontsize=9)
    
    # ==================== Gráfico 3: Modelos Ollama ====================
    if models_info:
        dates_models = [m[1] for m in models_info]
        sizes_models_mb = [m[2] for m in models_info]
        labels_models = [m[0].split(':')[0] for m in models_info]
        
        colors = ['#F18F01', '#C73E1D', '#6A994E', '#2E86AB', '#BC4749']
        ax3.barh(labels_models, sizes_models_mb, color=colors[:len(models_info)], alpha=0.8)
        ax3.set_title('🤖 Modelos Ollama Disponíveis', fontweight='bold')
        ax3.set_xlabel('Tamanho (MB)')
        ax3.grid(True, alpha=0.3, axis='x')
        
        # Adicionar valores
        for i, (size, date) in enumerate(zip(sizes_models_mb, dates_models)):
            ax3.text(size, i, f' {size:.0f}MB', va='center', fontsize=9)
    
    # ==================== Gráfico 4: Evolução Temporal ====================
    # Timeline com eventos importantes
    timeline_data = []
    for filename, date, size_bytes, lines in training_metrics:
        timeline_data.append((date, f"{lines} conversas", lines))
    
    if models_info:
        for name, date, size_mb in models_info:
            timeline_data.append((date, name, size_mb * 10))  # Escalar para visualização
    
    # Ordena por data
    timeline_data.sort(key=lambda x: x[0])
    
    if timeline_data:
        x_pos = [dt[0] for dt in timeline_data]
        y_pos = list(range(len(timeline_data)))
        labels = [f"{dt[1]}\n{dt[0].strftime('%d/%m')}" for dt in timeline_data]
        
        ax4.scatter(x_pos, y_pos, s=200, color='#2E86AB', alpha=0.6, edgecolors='black', linewidth=2)
        ax4.set_title('📅 Timeline de Eventos', fontweight='bold')
        ax4.set_xlabel('Data')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(labels, fontsize=9)
        ax4.grid(True, alpha=0.3, axis='x')
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # Salvar gráfico
    output_path = Path(__file__).parent / "learning_evolution_graph.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n✅ Gráfico salvo: {output_path}")
    
    # Mostrar estatísticas
    print("\n" + "="*60)
    print("📊 ESTATÍSTICAS DE APRENDIZADO")
    print("="*60)
    print(f"\n📈 Crescimento de Conversas:")
    print(f"   Início: {lines_count[0]} conversas ({dates_train[0].strftime('%d/%m/%Y')})")
    print(f"   Atual: {lines_count[-1]} conversas ({dates_train[-1].strftime('%d/%m/%Y')})")
    print(f"   Crescimento: {lines_count[-1] - lines_count[0]} (+{((lines_count[-1]/lines_count[0]-1)*100):.1f}%)")
    
    print(f"\n📁 Tamanho Total de Dados:")
    total_size_mb = sum(m[2] for m in training_metrics) / (1024 * 1024)
    print(f"   Total indexado: {total_size_mb:.2f} MB")
    
    if models_info:
        print(f"\n🤖 Modelos Treinados:")
        eddie_models = [m for m in models_info if 'eddie' in m[0].lower()]
        for name, date, size_mb in eddie_models:
            print(f"   - {name}: {size_mb:.1f}MB (atualizado em {date.strftime('%d/%m/%Y')})")
    
    print("\n" + "="*60)
    
    # Tentar mostrar a imagem
    try:
        plt.show()
    except:
        pass

def main():
    print("🔍 Analisando evolução do aprendizado no homelab...")
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
    
    # Exibir detalhes
    print(f"\n📂 Arquivos de Treinamento:")
    for filename, date, size_bytes, lines in training_metrics:
        print(f"   {filename}")
        print(f"      Data: {date.strftime('%d/%m/%Y')}")
        print(f"      Conversas: {lines}")
        print(f"      Tamanho: {size_bytes/1024:.1f}KB")
    
    # Gerar gráfico
    create_evolution_graph(training_metrics, models_info)

if __name__ == "__main__":
    main()
