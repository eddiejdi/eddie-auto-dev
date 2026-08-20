#!/usr/bin/env python3
"""
Teste de compatibilidade com dados simulados baseados em vagas reais.
Como não há dados históricos dos últimos 30 dias, este script gera
15 vagas simuladas (5 HIGH match, 5 MEDIUM match, 5 LOW match) e testa
com todos os métodos de compatibilidade disponíveis.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Import compatibility modules
try:
    from compatibility_allinone import AVAILABLE_METHODS, compute_compatibility
    ADVANCED_AVAILABLE = True
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")
    print("Execute: source .venv/bin/activate")
    sys.exit(1)


def get_simulated_test_data() -> list[dict[str, Any]]:
    """Gera 15 vagas simuladas baseadas em descrições reais de DevOps/SRE/Cloud."""
    
    # Currículo padrão (simplificado mas realista)
    resume = """
    DevOps Engineer with 5+ years of experience.
    Skills: Kubernetes, Docker, AWS, Terraform, Ansible, Python, GitLab CI/CD,
    Prometheus, Grafana, ELK Stack, Jenkins, Bash scripting.
    Experience with microservices architecture, infrastructure as code,
    monitoring and observability, automation, and site reliability engineering.
    """
    
    # 15 vagas simuladas com diferentes níveis de match
    jobs = [
        # HIGH MATCH (esperado 80-95%)
        ("SRE Engineer - Remote", """
        Looking for SRE with strong Kubernetes and AWS experience.
        Must have: K8s, Docker, cloud infrastructure, monitoring with Prometheus/Grafana.
        Nice to have: Terraform, Python automation, CI/CD pipelines.
        """, "jaccard", 1.2),
        
        ("DevOps Lead - Hybrid", """
        Senior DevOps role. Required: Kubernetes orchestration, AWS cloud services,
        Infrastructure as Code (Terraform/Ansible), GitLab CI/CD, monitoring solutions.
        Strong automation and scripting skills (Python/Bash).
        """, "jaccard", 1.5),
        
        ("Platform Engineer - São Paulo", """
        Platform team seeking engineer with K8s, containers, AWS, IaC experience.
        Tech stack: Kubernetes, Docker, Terraform, Prometheus, ELK, Jenkins.
        Must be comfortable with Linux, scripting, and automation.
        """, "llm", 85.3),
        
        ("Cloud Engineer - Remote", """
        Cloud infrastructure role. AWS expertise required. Kubernetes and Docker mandatory.
        CI/CD pipelines, monitoring/observability, infrastructure automation.
        Bonus: SRE mindset, Python, configuration management tools.
        """, "tfidf", 22.5),
        
        ("Infrastructure Automation Specialist", """
        Seeking automation expert. Key: Ansible, Terraform, CI/CD, scripting.
        Environment: Kubernetes clusters, AWS cloud, microservices.
        Tools: GitLab, Prometheus, Grafana, logging solutions.
        """, "jaccard", 1.8),
        
        # MEDIUM MATCH (esperado 50-75%)
        ("Backend Developer with DevOps - Remote", """
        Backend role with DevOps responsibilities. Python development + infrastructure.
        Need: coding skills, Kubernetes deployment understanding, CI/CD knowledge.
        Nice: AWS, Docker, basic monitoring setup.
        """, "jaccard", 0.9),
        
        ("Site Reliability Engineer - Fintech", """
        SRE for high-traffic fintech. Required: monitoring, incident response, automation.
        Preferred: Kubernetes, cloud platforms, observability tools.
        Some overlap with our stack but not exact match.
        """, "llm", 68.2),
        
        ("Infrastructure Engineer - Azure Focus", """
        Looking for infrastructure engineer. Primary cloud: Microsoft Azure (AKS).
        Secondary: some AWS knowledge acceptable. Terraform, Docker, CI/CD needed.
        """, "tfidf", 18.3),
        
        ("DevOps Consultant - Project Based", """
        Short-term DevOps consulting. Projects vary: cloud migration, automation,
        containerization. Flexible tech stack. Kubernetes and cloud experience valued.
        """, "jaccard", 1.1),
        
        ("Technical Lead - Platform", """
        Leadership role with hands-on platform work. Tech: containers, orchestration,
        cloud, automation. More focus on team management and architecture decisions.
        """, "llm", 72.5),
        
        # LOW MATCH (esperado 10-45%)
        ("Frontend Developer - React/TypeScript", """
        Frontend position. React, TypeScript, JavaScript, CSS, HTML.
        Some Docker knowledge for local development. No infrastructure work.
        """, "jaccard", 0.3),
        
        ("Data Engineer - Spark/Airflow", """
        Data pipeline engineer. Apache Spark, Airflow, Python data libs.
        Runs on Kubernetes but not infrastructure focus. ETL/data processing.
        """, "tfidf", 8.7),
        
        ("Mobile Developer - iOS/Android", """
        Mobile app development. Swift, Kotlin, React Native.
        Minimal DevOps overlap. CI/CD for mobile apps only.
        """, "llm", 15.2),
        
        ("QA Automation Engineer", """
        Test automation role. Selenium, Cypress, test frameworks.
        Some Docker usage for test environments. Not infrastructure focused.
        """, "jaccard", 0.5),
        
        ("Security Engineer - AppSec", """
        Application security specialist. Code review, penetration testing, SAST/DAST.
        Understanding of infrastructure helpful but not core responsibility.
        """, "tfidf", 12.1),
    ]
    
    results = []
    for i, (title, description, method, score) in enumerate(jobs, 1):
        results.append({
            'id': i,
            'title': title,
            'timestamp': (datetime.now() - timedelta(days=30-i*2)).isoformat(),
            'resume': resume.strip(),
            'job_description': description.strip(),
            'original_score': score,
            'original_method': method,
            'applied': 1 if score > 50 or score > 1.5 else 0,
            'user_feedback': None
        })
    
    return results


def test_all_methods(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Testa todos os métodos de compatibilidade com as vagas simuladas."""
    print(f"\n{'='*80}")
    print("🧪 TESTE DE COMPATIBILIDADE")
    print(f"{'='*80}\n")
    
    print(f"📊 Total de vagas: {len(data)}")
    print(f"📅 Período simulado: {data[-1]['timestamp'][:10]} a {data[0]['timestamp'][:10]}\n")
    
    # Estatísticas por método original
    original_methods = {}
    for item in data:
        method = item['original_method'] or 'unknown'
        original_methods[method] = original_methods.get(method, 0) + 1
    
    print("📈 Distribuição por método original:")
    for method, count in sorted(original_methods.items()):
        print(f"   {method}: {count} amostras")
    print()
    
    # Testar cada vaga com todos os métodos disponíveis
    results_by_method = {method: [] for method in AVAILABLE_METHODS.keys()}
    
    print(f"🔬 Testando {len(data)} vagas com todos os métodos...\n")
    
    for i, item in enumerate(data, 1):
        if i % 3 == 0 or i == 1 or i == len(data):
            print(f"   Processando vaga {i}/{len(data)} ({item['title'][:40]}...)", end='\r')
        
        resume = item['resume']
        job = item['job_description']
        
        # Testar cada método
        for method_name in AVAILABLE_METHODS.keys():
            try:
                score, explanation, details = compute_compatibility(resume, job, method=method_name)
                results_by_method[method_name].append({
                    'id': item['id'],
                    'title': item['title'],
                    'original_score': item['original_score'],
                    'new_score': score,
                    'improvement': score - item['original_score'] if isinstance(item['original_score'], (int, float)) else score,
                    'applied': item['applied'],
                    'user_feedback': item['user_feedback']
                })
            except Exception as e:
                # Método não disponível ou erro - apenas logar e continuar
                if i == 1:  # Logar apenas na primeira vaga
                    print(f"   ⚠️  {method_name}: {str(e)[:60]}")
    
    print("\n\n✅ Teste concluído!\n")
    
    # Análise de resultados
    print(f"\n{'='*80}")
    print("📊 RESULTADOS POR MÉTODO")
    print(f"{'='*80}\n")
    
    summary = {}
    
    for method_name, results in results_by_method.items():
        if not results:
            continue
        
        scores = [r['new_score'] for r in results]
        improvements = [r['improvement'] for r in results if r['improvement'] is not None]
        
        avg_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0
        
        # Análise de aplicações
        applied_scores = [r['new_score'] for r in results if r['applied'] == 1]
        not_applied_scores = [r['new_score'] for r in results if r['applied'] == 0]
        
        summary[method_name] = {
            'samples': len(results),
            'avg_score': avg_score,
            'min_score': min_score,
            'max_score': max_score,
            'avg_improvement': avg_improvement,
            'applied_avg': sum(applied_scores) / len(applied_scores) if applied_scores else None,
            'not_applied_avg': sum(not_applied_scores) / len(not_applied_scores) if not_applied_scores else None
        }
    
    # Ordenar por score médio
    sorted_methods = sorted(summary.items(), key=lambda x: x[1]['avg_score'], reverse=True)
    
    for rank, (method_name, stats) in enumerate(sorted_methods, 1):
        icon = {'jaccard': '📏', 'tfidf': '📊', 'tfidf_synonyms': '📊', 
                'tfidf_hybrid': '📊', 'llm': '🤖', 'llm_hybrid': '🤖',
                'semantic': '🧠', 'semantic_hybrid': '🧠', 'ultra': '🏆'}.get(method_name, '🔧')
        
        print(f"{rank}. {icon} {method_name.upper()}")
        print(f"   Amostras: {stats['samples']}")
        print(f"   Score médio: {stats['avg_score']:.1f}%")
        print(f"   Range: {stats['min_score']:.1f}% - {stats['max_score']:.1f}%")
        
        if stats['avg_improvement'] != 0:
            improvement_sign = '+' if stats['avg_improvement'] > 0 else ''
            print(f"   Melhoria vs original: {improvement_sign}{stats['avg_improvement']:.1f}%")
        
        if stats['applied_avg'] is not None and stats['not_applied_avg'] is not None:
            print(f"   Aplicadas: {stats['applied_avg']:.1f}% | Não aplicadas: {stats['not_applied_avg']:.1f}%")
        
        print()
    
    # Recomendação
    print(f"\n{'='*80}")
    print("💡 RECOMENDAÇÃO")
    print(f"{'='*80}\n")
    
    best_method = sorted_methods[0][0]
    best_stats = sorted_methods[0][1]
    
    print(f"🏆 Melhor método: {best_method.upper()}")
    print(f"   Score médio: {best_stats['avg_score']:.1f}%")
    
    if best_stats['avg_improvement'] > 0:
        print(f"   Melhoria: +{best_stats['avg_improvement']:.1f}% sobre método original")
    
    # Mostrar top 5 maiores melhorias
    all_improvements = []
    for method_name, results in results_by_method.items():
        for r in results:
            if r['improvement'] is not None and r['improvement'] > 0:
                all_improvements.append({
                    'id': r['id'],
                    'title': r['title'],
                    'method': method_name,
                    'original': r['original_score'],
                    'new': r['new_score'],
                    'improvement': r['improvement']
                })
    
    if all_improvements:
        print("\n📈 TOP 5 MAIORES MELHORIAS:\n")
        top_improvements = sorted(all_improvements, key=lambda x: x['improvement'], reverse=True)[:5]
        
        for i, imp in enumerate(top_improvements, 1):
            print(f"{i}. {imp['title'][:45]} (método: {imp['method']})")
            print(f"   {imp['original']:.1f}% → {imp['new']:.1f}% (+{imp['improvement']:.1f}%)")
    
    print()
    return summary, results_by_method


def show_test_info():
    """Mostra informações sobre o teste."""
    print(f"\n{'='*80}")
    print("ℹ️  DADOS DO TESTE")
    print(f"{'='*80}\n")
    print("⚠️  Como não há dados históricos reais disponíveis, este teste usa")
    print("   15 vagas simuladas baseadas em descrições reais de DevOps/SRE/Cloud:")
    print()
    print("   • 5 vagas HIGH MATCH (esperado 80-95%)")
    print("   • 5 vagas MEDIUM MATCH (esperado 50-75%)")
    print("   • 5 vagas LOW MATCH (esperado 10-45%)")
    print()
    print("   Os scores originais foram gerados com Jaccard, TF-IDF e LLM")
    print("   para simular um histórico realista de processamento.")
    print()


def main():
    print(f"\n{'='*80}")
    print("🔬 TESTE DE COMPATIBILIDADE - VAGAS SIMULADAS")
    print(f"{'='*80}\n")
    
    # Mostrar informações do teste
    show_test_info()
    
    # Gerar dados simulados
    print("🔍 Gerando 15 vagas simuladas para teste...\n")
    data = get_simulated_test_data()
    
    if not data:
        print("❌ Erro ao gerar dados de teste")
        return
    
    # Testar todos os métodos
    summary, detailed_results = test_all_methods(data)
    
    # Salvar resultados
    output_file = Path("/tmp/compatibility_test_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': summary,
            'test_data': data,
            'timestamp': datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Resultados salvos em: {output_file}")
    print()


if __name__ == "__main__":
    main()
