#!/usr/bin/env python3
"""
TF-IDF + Technical Synonyms Compatibility Scoring
Gives more weight to rare technical terms, expands synonyms
"""
import re
from typing import Dict, Set, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Technical synonyms dictionary (DevOps/SRE/Platform Engineering)
TECH_SYNONYMS = {
    'kubernetes': ['k8s', 'kube', 'orchestration', 'orquestração'],
    'docker': ['container', 'containerization', 'containerização'],
    'ci/cd': ['pipeline', 'continuous', 'integration', 'deployment', 'deploy', 'integração', 'entrega'],
    'cicd': ['pipeline', 'continuous', 'integration', 'deployment'],
    'infrastructure': ['infra', 'plataforma', 'platform'],
    'devops': ['sre', 'site-reliability', 'platform-engineer', 'platform'],
    'sre': ['devops', 'site-reliability', 'reliability-engineer'],
    'terraform': ['iac', 'infrastructure-as-code', 'infraestrutura-como-código'],
    'ansible': ['automation', 'provisioning', 'configuration-management', 'automação'],
    'aws': ['amazon', 'ec2', 's3', 'lambda', 'eks', 'amazon-web-services'],
    'gcp': ['google-cloud', 'gke', 'cloud-run', 'google'],
    'azure': ['microsoft-cloud', 'aks', 'azure-devops'],
    'monitoring': ['observability', 'monitoramento', 'observabilidade'],
    'prometheus': ['metrics', 'alerting', 'monitoring'],
    'grafana': ['dashboard', 'visualization', 'visualização'],
    'elk': ['elasticsearch', 'logstash', 'kibana', 'logging'],
    'jenkins': ['ci', 'continuous-integration', 'pipeline'],
    'gitlab': ['git', 'ci/cd', 'scm', 'source-control'],
    'github': ['git', 'scm', 'source-control', 'actions'],
    'python': ['py', 'scripting'],
    'golang': ['go', 'programming'],
    'bash': ['shell', 'scripting', 'script'],
    'linux': ['unix', 'sistema-operacional', 'os'],
    'networking': ['rede', 'network', 'tcp/ip'],
    'security': ['segurança', 'sec', 'compliance'],
}

# Reverse mapping for faster lookup
SYNONYM_MAP = {}
for main_term, synonyms in TECH_SYNONYMS.items():
    SYNONYM_MAP[main_term] = main_term
    for syn in synonyms:
        SYNONYM_MAP[syn] = main_term


def normalize_tech_terms(text: str) -> str:
    """Normalize technical terms to canonical form."""
    text = text.lower()
    
    # Replace synonyms with canonical terms
    words = text.split()
    normalized = []
    
    for word in words:
        clean_word = re.sub(r'[^a-z0-9/-]', '', word)
        if clean_word in SYNONYM_MAP:
            normalized.append(SYNONYM_MAP[clean_word])
        else:
            normalized.append(word)
    
    return ' '.join(normalized)


def expand_tech_terms(text: str) -> str:
    """Expand technical terms with their synonyms for better matching."""
    text_lower = text.lower()
    expanded_text = text
    
    for main_term, synonyms in TECH_SYNONYMS.items():
        if main_term in text_lower:
            # Add synonyms to text
            expanded_text += " " + " ".join(synonyms)
    
    return expanded_text


def compute_compatibility_tfidf(resume_text: str, job_text: str, 
                                expand_synonyms: bool = True) -> Tuple[float, str, Dict]:
    """
    Compute compatibility using TF-IDF weighting with optional synonym expansion.
    
    Args:
        resume_text: Candidate resume
        job_text: Job posting
        expand_synonyms: If True, expand technical terms with synonyms
    
    Returns:
        (score, explanation, details)
    """
    if not resume_text or not job_text:
        return 0.0, "Empty text", {}
    
    # Normalize technical terms
    resume_normalized = normalize_tech_terms(resume_text)
    job_normalized = normalize_tech_terms(job_text)
    
    # Expand with synonyms if enabled
    if expand_synonyms:
        resume_normalized = expand_tech_terms(resume_normalized)
        job_normalized = expand_tech_terms(job_normalized)
    
    # Portuguese stopwords
    stopwords = [
        'e', 'de', 'do', 'da', 'em', 'com', 'para', 'a', 'o', 'as', 'os', 
        'um', 'uma', 'que', 'the', 'and', 'or', 'in', 'on', 'at', 'by', 
        'of', 'for', 'to', 'with', 'is', 'ser', 'estar'
    ]
    
    try:
        # Create TF-IDF vectorizer
        vectorizer = TfidfVectorizer(
            stop_words=stopwords,
            min_df=1,
            ngram_range=(1, 2),  # Include bigrams for "ci/cd", "platform engineer", etc.
            token_pattern=r'[a-z0-9/-]+',  # Keep hyphens and slashes
            lowercase=True
        )
        
        # Fit and transform
        vectors = vectorizer.fit_transform([resume_normalized, job_normalized])
        
        # Compute cosine similarity
        similarity = cosine_similarity(vectors[0], vectors[1])[0][0]
        score = round(similarity * 100, 1)
        
        # Get feature names and weights for explanation
        feature_names = vectorizer.get_feature_names_out()
        resume_weights = vectors[0].toarray()[0]
        job_weights = vectors[1].toarray()[0]
        
        # Find common important terms
        common_terms = []
        for i, term in enumerate(feature_names):
            if resume_weights[i] > 0 and job_weights[i] > 0:
                avg_weight = (resume_weights[i] + job_weights[i]) / 2
                common_terms.append((term, avg_weight))
        
        common_terms.sort(key=lambda x: x[1], reverse=True)
        top_terms = [term for term, _ in common_terms[:5]]
        
        explanation = f"TF-IDF score: {score}%. Top matches: {', '.join(top_terms) if top_terms else 'none'}"
        
        details = {
            "method": "tfidf" if not expand_synonyms else "tfidf_synonyms",
            "tfidf_score": score,
            "common_terms": len(common_terms),
            "top_terms": top_terms,
            "synonym_expansion": expand_synonyms
        }
        
        return score, explanation, details
        
    except Exception as e:
        # Fallback to simple Jaccard if TF-IDF fails
        from llm_compatibility import compute_compatibility_fallback
        fallback_score = compute_compatibility_fallback(resume_text, job_text)
        return fallback_score, f"TF-IDF failed ({e}), using Jaccard fallback", {"method": "fallback"}


def compute_compatibility_tfidf_hybrid(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """
    Hybrid: 60% TF-IDF with synonyms + 40% simple TF-IDF.
    Balances synonym expansion with exact term matching.
    """
    # Get both scores
    score_with_synonyms, _, details_syn = compute_compatibility_tfidf(resume_text, job_text, expand_synonyms=True)
    score_without_synonyms, _, details_no_syn = compute_compatibility_tfidf(resume_text, job_text, expand_synonyms=False)
    
    # Weighted average
    final_score = round(score_with_synonyms * 0.6 + score_without_synonyms * 0.4, 1)
    
    explanation = f"TF-IDF Hybrid: {final_score}% (with synonyms: {score_with_synonyms}%, exact: {score_without_synonyms}%)"
    
    details = {
        "method": "tfidf_hybrid",
        "final_score": final_score,
        "score_with_synonyms": score_with_synonyms,
        "score_exact": score_without_synonyms,
        "top_terms": details_syn.get("top_terms", [])
    }
    
    return final_score, explanation, details


if __name__ == "__main__":
    # Test examples
    print("\n" + "=" * 80)
    print("🧪 TEST: TF-IDF + Technical Synonyms")
    print("=" * 80 + "\n")
    
    resume = """
    DevOps Engineer | SRE | Platform Engineer
    
    Experiência com:
    - Kubernetes (K8s), Docker, containers
    - CI/CD: GitHub Actions, GitLab CI, Jenkins
    - Infrastructure as Code: Terraform, Ansible
    - Cloud: AWS (EC2, S3, Lambda, EKS), GCP (GKE, Cloud Run)
    - Monitoring: Prometheus, Grafana, ELK
    - Languages: Python, Go, Bash
    - 5+ anos de experiência em ambientes de produção
    """
    
    print("Test 1: High match expected (SRE with K8s)")
    print("-" * 80)
    job1 = """
    Vaga: Site Reliability Engineer (SRE)
    
    Requisitos:
    - Experiência com orquestração de containers (K8s)
    - Automação de infraestrutura (IaC)
    - Cloud pública (AWS ou GCP)
    - Pipelines de CI/CD
    - Monitoramento e observabilidade
    """
    
    # Without synonyms
    score1, exp1, det1 = compute_compatibility_tfidf(resume, job1, expand_synonyms=False)
    print(f"   TF-IDF (sem sinônimos): {score1}%")
    print(f"   {exp1}")
    
    # With synonyms
    score2, exp2, det2 = compute_compatibility_tfidf(resume, job1, expand_synonyms=True)
    print(f"\n   TF-IDF (com sinônimos): {score2}%")
    print(f"   {exp2}")
    
    # Hybrid
    score3, exp3, det3 = compute_compatibility_tfidf_hybrid(resume, job1)
    print(f"\n   TF-IDF Hybrid: {score3}%")
    print(f"   {exp3}")
    
    print("\n\nTest 2: Low match expected (Data Science)")
    print("-" * 80)
    job2 = """
    Vaga Nova na Thera Consulting
    Data Science
    Experiência com Python, Machine Learning, estatística
    Atuação remota
    """
    
    score4, exp4, det4 = compute_compatibility_tfidf(resume, job2, expand_synonyms=False)
    print(f"   TF-IDF (sem sinônimos): {score4}%")
    
    score5, exp5, det5 = compute_compatibility_tfidf(resume, job2, expand_synonyms=True)
    print(f"   TF-IDF (com sinônimos): {score5}%")
    
    score6, exp6, det6 = compute_compatibility_tfidf_hybrid(resume, job2)
    print(f"   TF-IDF Hybrid: {score6}%")
    
    print("\n\nTest 3: Synonym recognition (Platform Engineer with orchestration)")
    print("-" * 80)
    job3 = """
    Platform Engineer
    
    Buscamos engenheiro de plataforma com:
    - Orquestração de containers
    - Automação com IaC
    - Observabilidade
    - Cloud native
    """
    
    score7, exp7, det7 = compute_compatibility_tfidf(resume, job3, expand_synonyms=False)
    print(f"   TF-IDF (sem sinônimos): {score7}%")
    
    score8, exp8, det8 = compute_compatibility_tfidf(resume, job3, expand_synonyms=True)
    print(f"   TF-IDF (com sinônimos): {score8}%")
    print(f"   Melhoria: +{score8 - score7:.1f}%")
    
    print("\n" + "=" * 80)
    print("✅ TF-IDF + Synonyms implementation complete")
    print("=" * 80 + "\n")
