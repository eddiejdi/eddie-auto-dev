#!/usr/bin/env python3
"""
Demonstração de como funciona o cálculo de compatibilidade (%)
"""
import re


def compute_compatibility_demo(resume_text: str, job_text: str) -> tuple:
    """Compute compatibility and return detailed breakdown."""
    
    stopwords = {
        'e','de','do','da','em','com','para','a','o','as','os','um','uma','que',
        'the','and','or','in','on','at','by','of','for','to','with'
    }
    
    def tokens(s: str):
        s = s.lower()
        s = re.sub(r"[^a-z0-9çãõáéíóúâêîôûàèìòù-]+", " ", s)
        toks = [t.strip() for t in s.split() if t and t not in stopwords and len(t) > 2]
        return set(toks)
    
    rset = tokens(resume_text)
    jset = tokens(job_text)
    
    if not rset or not jset:
        return 0.0, set(), set(), set(), set()
    
    inter = rset.intersection(jset)
    union = rset.union(jset)
    only_resume = rset - jset
    only_job = jset - rset
    
    score = len(inter) / len(union)
    
    return round(score * 100.0, 1), inter, only_resume, only_job, union


# Exemplos práticos
print("=" * 80)
print("🔍 DEMONSTRAÇÃO: Como funciona o cálculo de compatibilidade")
print("=" * 80)

print("\n📐 MÉTODO: Jaccard Similarity (Índice de Jaccard)")
print("-" * 80)
print("""
Fórmula: compatibilidade = (palavras em comum) / (todas as palavras únicas) × 100

Passos:
1. Normalizar textos (lowercase, remover pontuação)
2. Extrair tokens (palavras com 3+ caracteres, exceto stopwords)
3. Criar conjuntos únicos de palavras
4. Calcular interseção e união
5. Aplicar fórmula de Jaccard

""")

# Exemplo 1: Alta compatibilidade
print("\n" + "=" * 80)
print("EXEMPLO 1: Alta compatibilidade (~30%)")
print("=" * 80)

resume1 = """
DevOps Engineer com experiência em Kubernetes, Docker, CI/CD, 
Terraform, AWS, automação e monitoramento com Prometheus e Grafana.
"""

job1 = """
Vaga DevOps: Procuramos profissional com conhecimento em Kubernetes, 
Docker, AWS, Terraform e experiência com CI/CD e automação.
"""

compat1, common1, only_r1, only_j1, union1 = compute_compatibility_demo(resume1, job1)

print(f"\n📄 Currículo ({len(resume1)} chars):")
print(f"   {resume1.strip()[:100]}...")

print(f"\n💼 Vaga ({len(job1)} chars):")
print(f"   {job1.strip()[:100]}...")

print("\n📊 Análise:")
print(f"   Palavras únicas no currículo: {len(common1) + len(only_r1)}")
print(f"   Palavras únicas na vaga: {len(common1) + len(only_j1)}")
print(f"   Palavras em comum: {len(common1)}")
print(f"   Total de palavras únicas: {len(union1)}")

print(f"\n✅ Palavras em comum ({len(common1)}):")
print(f"   {', '.join(sorted(list(common1))[:15])}")
if len(common1) > 15:
    print(f"   ... e mais {len(common1) - 15} palavras")

print("\n🔢 Cálculo:")
print(f"   {len(common1)} (comum) / {len(union1)} (total) = {len(common1)/len(union1):.4f}")
print(f"   {len(common1)/len(union1):.4f} × 100 = {compat1}%")

print(f"\n🎯 COMPATIBILIDADE: {compat1}%")


# Exemplo 2: Baixa compatibilidade
print("\n\n" + "=" * 80)
print("EXEMPLO 2: Baixa compatibilidade (~2%)")
print("=" * 80)

resume2 = """
DevOps Engineer com experiência em Kubernetes, Docker, CI/CD, 
Terraform, AWS, automação e monitoramento.
"""

job2 = """
Vendedor de roupas para loja no shopping. 
Necessário boa comunicação, organização e disponibilidade.
"""

compat2, common2, only_r2, only_j2, union2 = compute_compatibility_demo(resume2, job2)

print("\n📄 Currículo:")
print(f"   {resume2.strip()[:100]}...")

print("\n💼 Vaga:")
print(f"   {job2.strip()[:100]}...")

print("\n📊 Análise:")
print(f"   Palavras únicas no currículo: {len(common2) + len(only_r2)}")
print(f"   Palavras únicas na vaga: {len(common2) + len(only_j2)}")
print(f"   Palavras em comum: {len(common2)}")
print(f"   Total de palavras únicas: {len(union2)}")

if common2:
    print(f"\n✅ Palavras em comum ({len(common2)}):")
    print(f"   {', '.join(sorted(list(common2)))}")
else:
    print("\n⚠️  Nenhuma palavra em comum!")

print("\n🔢 Cálculo:")
print(f"   {len(common2)} (comum) / {len(union2)} (total) = {len(common2)/len(union2):.4f}")
print(f"   {len(common2)/len(union2):.4f} × 100 = {compat2}%")

print(f"\n🎯 COMPATIBILIDADE: {compat2}%")


# Exemplo 3: Sua vaga real mais compatível
print("\n\n" + "=" * 80)
print("EXEMPLO 3: Sua vaga real do WhatsApp (Data Science)")
print("=" * 80)

resume3 = """
DevOps Engineer | SRE | Platform Engineer
Kubernetes, Docker, CI/CD, Terraform, Ansible, AWS, GCP, 
Prometheus, Grafana, Python, Go, automação, infraestrutura
"""

job3 = """
Vaga Nova na Thera Consulting
Data Science
Disponibilidade imediata
Contratação PJ
Atuação remota
"""

compat3, common3, only_r3, only_j3, union3 = compute_compatibility_demo(resume3, job3)

print("\n📄 Seu currículo (resumido):")
print(f"   {resume3.strip()[:100]}...")

print("\n💼 Vaga real do WhatsApp:")
print(f"   {job3.strip()}")

print("\n📊 Análise:")
print(f"   Palavras únicas no currículo: {len(common3) + len(only_r3)}")
print(f"   Palavras únicas na vaga: {len(common3) + len(only_j3)}")
print(f"   Palavras em comum: {len(common3)}")
print(f"   Total de palavras únicas: {len(union3)}")

if common3:
    print(f"\n✅ Palavras em comum ({len(common3)}):")
    print(f"   {', '.join(sorted(list(common3)))}")
else:
    print("\n⚠️  Nenhuma palavra em comum!")

print("\n❌ Apenas no currículo (amostra de 10):")
print(f"   {', '.join(sorted(list(only_r3))[:10])}")

print("\n❌ Apenas na vaga (amostra de 10):")
print(f"   {', '.join(sorted(list(only_j3))[:10])}")

print("\n🔢 Cálculo:")
print(f"   {len(common3)} (comum) / {len(union3)} (total) = {len(common3)/len(union3):.4f}")
print(f"   {len(common3)/len(union3):.4f} × 100 = {compat3}%")

print(f"\n🎯 COMPATIBILIDADE: {compat3}%")


# Conclusão
print("\n\n" + "=" * 80)
print("📝 RESUMO")
print("=" * 80)
print("""
✅ VANTAGENS do método Jaccard:
   • Simples e rápido de calcular
   • Independente do tamanho dos textos
   • Funciona bem para overlap de palavras-chave

⚠️  LIMITAÇÕES:
   • Não considera sinônimos (Kubernetes ≠ K8s)
   • Não considera ordem ou contexto das palavras
   • Palavras muito comuns reduzem o score
   • Não entende significado (apenas overlap literal)

💡 MELHORIAS POSSÍVEIS:
   • TF-IDF: dar peso a palavras mais relevantes
   • Word embeddings: entender sinônimos e similaridade semântica
   • NLP avançado: análise contextual com transformers
   • Dicionário de sinônimos: expandir vocabulário técnico

🎯 THRESHOLDS RECOMENDADOS (baseado nos seus dados):
   • Threshold atual: 75% (muito restritivo - 0 matches)
   • Máximo real encontrado: 1.1%
   • Sugerido para testes: 0.5-1.0%
   • Ideal para produção: ajustar conforme os grupos de vagas que entrar
""")

print("\n" + "=" * 80)
