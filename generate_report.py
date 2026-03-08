#!/usr/bin/env python3
"""
Gerador de Relatório Consolidado - Análise de Refatoração
Consolida LOTE1_RESUMO.json + LOTE2_RESUMO.json + etc.
"""

import json
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path("/home/edenilson/shared-auto-dev/analysis_results")

def load_lote_resumo(lote_num: int) -> dict:
    """Carrega resumo de um lote."""
    arquivo = RESULTS_DIR / f"lote_{lote_num:02d}.json"
    if arquivo.exists():
        try:
            return json.loads(arquivo.read_text())
        except:
            return []
    return []

def generate_consolidated_report():
    """Gera relatório consolidado."""
    
    report = {
        "titulo": "Análise de Refatoração - Projeto Shared-Auto-Dev",
        "data": "7 de março de 2026",
        "total_arquivos": 0,
        "total_shared_refs": 0,
        "lotes_processados": 0,
        "arquivos_críticos": [],
        "componentes_isoláveis": {},
        "impacto_refatoracao": {}
    }
    
    # Carregar todos os resultados dos lotes
    all_files = {}
    shared_by_component = defaultdict(int)
    
    for lote_file in sorted(RESULTS_DIR.glob("lote_*.json")):
        try:
            dados = json.loads(lote_file.read_text())
            for arquivo in dados:
                if arquivo.get("sucesso"):
                    report["total_arquivos"] += 1
                    shared_count = arquivo.get("shared_count", 0)
                    report["total_shared_refs"] += shared_count
                    
                    # Caminho relativo para componente
                    caminho = arquivo.get("caminho", "")
                    if "/" in caminho:
                        comp = caminho.split("/")[1]
                        shared_by_component[comp] += shared_count
                    
                    # Arquivos críticos (5+ referências SHARED)
                    if shared_count >= 5:
                        report["arquivos_críticos"].append({
                            "nome": arquivo.get("arquivo"),
                            "caminho": caminho,
                            "shared_refs": shared_count,
                            "linhas": arquivo.get("linhas_total", 0)
                        })
                    
                    all_files[caminho] = arquivo
        except Exception as e:
            print(f"⚠️  Erro lendo {lote_file}: {e}")
    
    report["lotes_processados"] = len(list(RESULTS_DIR.glob("lote_*.json")))
    
    # Componentes principais
    report["componentes_isoláveis"] = {
        "crypto_trading_bot": {
            "arquivos": sum(1 for f in all_files if "btc_trading_agent" in f or "shared_tray_agent" in f),
            "shared_refs": shared_by_component["btc_trading_agent"] + shared_by_component.get("shared_tray_agent", 0),
            "descricao": "Trading de BTC com ensemble de modelos",
            "novo_nome": "crypto-trading-bot"
        },
        "homelab_agent": {
            "arquivos": sum(1 for f in all_files if "homelab" in f.lower()),
            "shared_refs": shared_by_component.get("homelab_copilot_agent", 0),
            "descricao": "Agente de automação do homelab",
            "novo_nome": "homelab-agent"
        },
        "estou_aqui": {
            "arquivos": sum(1 for f in all_files if "estou-aqui" in f),
            "shared_refs": shared_by_component.get("estou-aqui", 0),
            "descricao": "Plataforma de eventos comunitários",
            "novo_nome": "mantém-se (projeto independente)"
        },
        "smart_integrations": {
            "arquivos": sum(1 for f in all_files if "smartlife" in f or "homeassistant" in f),
            "shared_refs": shared_by_component.get("smartlife_integration", 0) + shared_by_component.get("homeassistant_integration", 0),
            "descricao": "Integração com SmartLife + Home Assistant",
            "novo_nome": "smart-home-bridge"
        },
        "mcp_servers": {
            "arquivos": sum(1 for f in all_files if "mcp-server" in f or "rag-mcp" in f),
            "shared_refs": shared_by_component.get("rag-mcp-server", 0) + shared_by_component.get("github-mcp-server", 0),
            "descricao": "Model Context Protocol servers (RAG + GitHub)",
            "novo_nome": "mantém-se (independente)"
        }
    }
    
    # Impacto de refatoração
    report["impacto_refatoracao"] = {
        "total_linhas": sum(f.get("linhas_total", 0) for f in all_files.values()),
        "imports_impactados": sum(f.get("imports_count", 0) for f in all_files.values()),
        "funcoes_publicas": sum(len(f.get("funcoes_publicas", [])) for f in all_files.values()),
        "esforço_estimado": {
            "automatizado": "80% (refactoring com AST)",
            "manual": "20% (testes + integração)",
            "tempo_estimado_dias": 5
        }
    }
    
    # Ordenar arquivos críticos por quantidade de refs
    report["arquivos_críticos"].sort(key=lambda x: x["shared_refs"], reverse=True)
    report["arquivos_críticos"] = report["arquivos_críticos"][:15]
    
    return report

def save_report(report: dict):
    """Salva relatório."""
    output_file = RESULTS_DIR / "RELATORIO_CONSOLIDADO.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return output_file

if __name__ == "__main__":
    print("📊 Gerando relatório consolidado...")
    report = generate_consolidated_report()
    output = save_report(report)
    
    print(f"\n{'='*70}")
    print(f"✅ Relatório Consolidado")
    print(f"{'='*70}")
    print(f"Total de arquivos: {report['total_arquivos']}")
    print(f"Referências SHARED: {report['total_shared_refs']}")
    print(f"Lotes processados: {report['lotes_processados']}")
    print(f"\nArquivos críticos (5+ refs):")
    for arq in report['arquivos_críticos'][:5]:
        print(f"  - {arq['nome']}: {arq['shared_refs']} refs")
    
    print(f"\nComponentes isoláveis:")
    for comp, dados in report['componentes_isoláveis'].items():
        print(f"  {comp}: {dados['arquivos']} arquivos, {dados['shared_refs']} refs SHARED")
    
    print(f"\nSalvo em: {output}")
