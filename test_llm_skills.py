#!/usr/bin/env python3
"""Test LLM skill extraction."""
import json
import sys
import os

# Ensure we import from current dir
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apply_real_job import extract_skills_llm, compute_compatibility

# Teste 1: Vaga Data Science
job_text = """Data Science - Thera Consulting
Contratacao PJ, Remota, 3-6 meses
Requisitos: Python, R, SQL, Machine Learning, Estatistica, Scikit-Learn, TensorFlow, Tableau, Power BI
Analise de dados, modelagem preditiva, deep learning, NLP, visualizacao de dados
Experiencia com grandes volumes de dados (Big Data)
Conhecimento em frameworks de ML e ferramentas de BI"""

print("=" * 70)
print("TESTE 1: Extracao de skills da VAGA (Data Science)")
print("=" * 70)
result_job = extract_skills_llm(job_text, text_type="job")
print(json.dumps(result_job, indent=2, ensure_ascii=False))

# Teste 2: Curriculo DevOps/SRE
cv_text = """Edenilson - DevOps Engineer | SRE | Platform Engineer
Experiencia com Kubernetes, Docker, Terraform, Ansible, Jenkins
CI/CD, GitOps, AWS, GCP, Azure, Cloud Architecture
Prometheus, Grafana, ELK Stack, Observabilidade
Python, Bash, Go para automacao e ferramentas
Linux, networking, seguranca, infraestrutura como codigo
Scrum, Agile, lideranca tecnica"""

print()
print("=" * 70)
print("TESTE 2: Extracao de skills do CURRICULO (DevOps/SRE)")
print("=" * 70)
result_cv = extract_skills_llm(cv_text, text_type="resume")
print(json.dumps(result_cv, indent=2, ensure_ascii=False))

# Teste 3: Compatibilidade LLM Skills
print()
print("=" * 70)
print("TESTE 3: Compatibilidade LLM Skills (DevOps vs Data Science)")
print("=" * 70)
score, explanation, details = compute_compatibility(cv_text, job_text)
print(f"Score: {score}%")
print(f"Explanation: {explanation}")
print(f"Method: {details.get('method', 'unknown')}")
if details.get('common_technical_skills'):
    print(f"Common skills: {details['common_technical_skills']}")
if details.get('component_scores'):
    print(f"Components: {json.dumps(details['component_scores'], indent=2)}")

# Teste 4: Compatibilidade com vaga compativel
print()
print("=" * 70)
print("TESTE 4: Compatibilidade com vaga COMPATIVEL (DevOps)")
print("=" * 70)
devops_job = """Vaga: DevOps Engineer Senior
Requisitos: Kubernetes, Docker, Terraform, CI/CD, AWS ou GCP
Desejavel: Python, Ansible, Jenkins, Prometheus, Grafana
Experiencia com infraestrutura como codigo (IaC)
Linux avancado, networking, seguranca
Metodologias ageis (Scrum/Kanban)
Lideranca tecnica de equipes"""

score2, explanation2, details2 = compute_compatibility(cv_text, devops_job)
print(f"Score: {score2}%")
print(f"Explanation: {explanation2}")
print(f"Method: {details2.get('method', 'unknown')}")
if details2.get('common_technical_skills'):
    print(f"Common skills: {details2['common_technical_skills']}")
if details2.get('component_scores'):
    print(f"Components: {json.dumps(details2['component_scores'], indent=2)}")
