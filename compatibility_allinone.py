#!/usr/bin/env python3
"""
All-in-one compatibility scoring system
Integrates: Jaccard, TF-IDF, Synonyms, LLM, and Semantic Embeddings
"""
import os
from typing import Tuple, Dict, Optional


# Available methods
AVAILABLE_METHODS = {
    'jaccard': 'Simple token-based Jaccard similarity (baseline)',
    'tfidf': 'TF-IDF weighting without synonym expansion',
    'tfidf_synonyms': 'TF-IDF with technical synonym expansion',
    'tfidf_hybrid': 'Hybrid TF-IDF (60% synonyms + 40% exact)',
    'llm': 'LLM semantic analysis (eddie-whatsapp)',
    'llm_hybrid': 'LLM + Jaccard hybrid (70/30)',
    'semantic': 'Sentence embeddings (transformer-based)',
    'semantic_hybrid': 'Semantic + TF-IDF hybrid (70/30)',
    'ultra': 'Ultra method: 40% Semantic + 30% LLM + 20% TF-IDF + 10% Jaccard',
}


def compute_compatibility(resume_text: str, job_text: str, 
                         method: str = 'auto') -> Tuple[float, str, Dict]:
    """
    Compute compatibility using specified method.
    
    Args:
        resume_text: Candidate resume
        job_text: Job posting
        method: One of: auto, jaccard, tfidf, tfidf_synonyms, tfidf_hybrid,
                llm, llm_hybrid, semantic, semantic_hybrid, ultra
    
    Returns:
        (score, explanation, details)
    """
    if not resume_text or not job_text:
        return 0.0, "Empty text", {"method": method}
    
    # Auto-select best available method
    if method == 'auto':
        method = detect_best_method()
    
    if method not in AVAILABLE_METHODS:
        print(f"⚠️  Unknown method '{method}', using 'auto'")
        method = detect_best_method()
    
    # Route to appropriate implementation
    try:
        if method == 'jaccard':
            from llm_compatibility import compute_compatibility_fallback
            score = compute_compatibility_fallback(resume_text, job_text)
            return score, f"Jaccard: {score}%", {"method": "jaccard", "score": score}
        
        elif method == 'tfidf':
            from compatibility_tfidf import compute_compatibility_tfidf
            return compute_compatibility_tfidf(resume_text, job_text, expand_synonyms=False)
        
        elif method == 'tfidf_synonyms':
            from compatibility_tfidf import compute_compatibility_tfidf
            return compute_compatibility_tfidf(resume_text, job_text, expand_synonyms=True)
        
        elif method == 'tfidf_hybrid':
            from compatibility_tfidf import compute_compatibility_tfidf_hybrid
            return compute_compatibility_tfidf_hybrid(resume_text, job_text)
        
        elif method == 'llm':
            from llm_compatibility import compute_compatibility_llm
            score, explanation = compute_compatibility_llm(resume_text, job_text)
            return score, explanation, {"method": "llm", "score": score}
        
        elif method == 'llm_hybrid':
            from llm_compatibility import compute_compatibility_hybrid
            return compute_compatibility_hybrid(resume_text, job_text)
        
        elif method == 'semantic':
            from compatibility_semantic import compute_compatibility_semantic
            return compute_compatibility_semantic(resume_text, job_text)
        
        elif method == 'semantic_hybrid':
            from compatibility_semantic import compute_compatibility_semantic_hybrid
            return compute_compatibility_semantic_hybrid(resume_text, job_text)
        
        elif method == 'ultra':
            return compute_compatibility_ultra(resume_text, job_text)
        
        else:
            # Fallback
            from llm_compatibility import compute_compatibility_fallback
            score = compute_compatibility_fallback(resume_text, job_text)
            return score, f"Fallback Jaccard: {score}%", {"method": "fallback"}
    
    except Exception as e:
        print(f"⚠️  Method '{method}' failed: {e}")
        print(f"   Falling back to Jaccard")
        from llm_compatibility import compute_compatibility_fallback
        score = compute_compatibility_fallback(resume_text, job_text)
        return score, f"Fallback Jaccard: {score}%", {"method": "fallback", "error": str(e)}


def detect_best_method() -> str:
    """Detect best available method based on installed dependencies."""
    
    # Check semantic embeddings (best if available)
    try:
        import sentence_transformers
        return 'semantic_hybrid'
    except ImportError:
        pass
    
    # Check LLM (second best)
    try:
        import requests
        ollama_host = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
        response = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if response.status_code == 200:
            return 'llm_hybrid'
    except:
        pass
    
    # Check TF-IDF (third best)
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        return 'tfidf_hybrid'
    except ImportError:
        pass
    
    # Fallback to Jaccard
    return 'jaccard'


def compute_compatibility_ultra(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """
    Ultra method: combines all available methods with weighted average.
    
    Weights:
    - 40% Semantic Embeddings (deep understanding)
    - 30% LLM (semantic + reasoning)
    - 20% TF-IDF + Synonyms (keyword + synonyms)
    - 10% Jaccard (baseline)
    """
    scores = {}
    weights = {}
    
    # Get Jaccard (always available)
    from llm_compatibility import compute_compatibility_fallback
    scores['jaccard'] = compute_compatibility_fallback(resume_text, job_text)
    weights['jaccard'] = 0.10
    
    # Try TF-IDF + Synonyms
    try:
        from compatibility_tfidf import compute_compatibility_tfidf_hybrid
        score, _, _ = compute_compatibility_tfidf_hybrid(resume_text, job_text)
        scores['tfidf'] = score
        weights['tfidf'] = 0.20
    except Exception as e:
        print(f"   TF-IDF unavailable: {e}")
    
    # Try LLM
    try:
        from llm_compatibility import compute_compatibility_llm
        score, _ = compute_compatibility_llm(resume_text, job_text)
        scores['llm'] = score
        weights['llm'] = 0.30
    except Exception as e:
        print(f"   LLM unavailable: {e}")
    
    # Try Semantic Embeddings
    try:
        from compatibility_semantic import compute_compatibility_semantic
        score, _, _ = compute_compatibility_semantic(resume_text, job_text)
        scores['semantic'] = score
        weights['semantic'] = 0.40
    except Exception as e:
        print(f"   Semantic unavailable: {e}")
    
    # Normalize weights if some methods unavailable
    total_weight = sum(weights.values())
    normalized_weights = {k: v/total_weight for k, v in weights.items()}
    
    # Compute weighted average
    final_score = sum(scores[k] * normalized_weights[k] for k in scores.keys())
    final_score = round(final_score, 1)
    
    # Build explanation
    method_scores = ", ".join([f"{k}={scores[k]:.1f}%" for k in scores.keys()])
    explanation = f"Ultra method: {final_score}% (weighted: {method_scores})"
    
    details = {
        "method": "ultra",
        "final_score": final_score,
        "component_scores": scores,
        "weights": normalized_weights
    }
    
    return final_score, explanation, details


def benchmark_all_methods(resume_text: str, job_text: str):
    """Benchmark all available methods side-by-side."""
    print("\n" + "=" * 80)
    print("🏆 ULTIMATE BENCHMARK: All Methods")
    print("=" * 80 + "\n")
    
    results = []
    
    for method_name, description in AVAILABLE_METHODS.items():
        if method_name == 'auto':
            continue
        
        try:
            score, explanation, details = compute_compatibility(resume_text, job_text, method=method_name)
            results.append((method_name, score, explanation))
            print(f"✅ {method_name:20s} {score:6.1f}% | {description}")
        except Exception as e:
            print(f"❌ {method_name:20s}  ERROR | {str(e)[:50]}")
    
    print("\n" + "=" * 80)
    
    # Sort by score
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n📊 Ranking (highest to lowest):")
    for i, (method, score, _) in enumerate(results, 1):
        print(f"   {i}. {method:20s} {score:.1f}%")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("🚀 ALL-IN-ONE COMPATIBILITY SCORING SYSTEM")
    print("=" * 80 + "\n")
    
    print("Available methods:")
    for i, (method, desc) in enumerate(AVAILABLE_METHODS.items(), 1):
        print(f"   {i:2d}. {method:20s} - {desc}")
    
    print("\n" + "=" * 80)
    print("Choose test mode:")
    print("   1. Quick demo (single method)")
    print("   2. Full benchmark (all methods)")
    print("   3. Exit")
    print("=" * 80 + "\n")
    
    choice = input("Option (1-3): ").strip()
    
    if choice == '3':
        sys.exit(0)
    
    # Test data
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
    
    job = """
    Vaga: Site Reliability Engineer (SRE)
    
    Procuramos profissional com experiência em:
    - Orquestração de containers (K8s ou similar)
    - Automação de infraestrutura (Terraform/Ansible)
    - Pipelines de CI/CD
    - Cloud pública (AWS ou GCP)
    - Monitoramento e observabilidade
    - Linguagens: Python ou Go
    
    Senioridade: Pleno/Sênior
    Modalidade: Remoto
    """
    
    if choice == '1':
        print("\nSelect method:")
        methods_list = list(AVAILABLE_METHODS.keys())
        for i, m in enumerate(methods_list, 1):
            print(f"   {i}. {m}")
        
        method_choice = input("\nMethod number: ").strip()
        try:
            method_idx = int(method_choice) - 1
            method = methods_list[method_idx]
        except:
            method = 'auto'
        
        print(f"\n🧪 Testing method: {method}")
        print("-" * 80)
        
        score, explanation, details = compute_compatibility(resume, job, method=method)
        
        print(f"\n📊 Result:")
        print(f"   Score: {score}%")
        print(f"   {explanation}")
        print(f"\n   Details: {details}")
    
    elif choice == '2':
        benchmark_all_methods(resume, job)
    
    print("\n✅ Test complete\n")
