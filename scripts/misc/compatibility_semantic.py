#!/usr/bin/env python3
"""
Semantic Similarity using Sentence Embeddings
Uses sentence-transformers for deep semantic understanding
"""
import os
from typing import Tuple, Dict, Optional
import numpy as np


def check_sentence_transformers() -> bool:
    """Check if sentence-transformers is available."""
    try:
        import sentence_transformers
        return True
    except ImportError:
        return False


def install_sentence_transformers():
    """Install sentence-transformers package."""
    import subprocess
    import sys
    
    print("📦 Installing sentence-transformers...")
    print("   This will download ~500MB of models")
    print("   Proceed? (y/n): ", end='')
    
    response = input().strip().lower()
    if response != 'y':
        print("❌ Installation cancelled")
        return False
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q",
            "sentence-transformers", "torch", "transformers"
        ])
        print("✅ sentence-transformers installed successfully")
        return True
    except Exception as e:
        print(f"❌ Installation failed: {e}")
        return False


# Global model cache
_EMBEDDING_MODEL = None
_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")


def get_embedding_model():
    """Get or initialize the sentence embedding model."""
    global _EMBEDDING_MODEL
    
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    
    if not check_sentence_transformers():
        print("⚠️  sentence-transformers not installed")
        if not install_sentence_transformers():
            return None
    
    try:
        from sentence_transformers import SentenceTransformer
        
        print(f"📥 Loading embedding model: {_MODEL_NAME}")
        print("   First time may take 1-2 minutes to download...")
        
        _EMBEDDING_MODEL = SentenceTransformer(_MODEL_NAME)
        
        print("✅ Model loaded successfully")
        return _EMBEDDING_MODEL
        
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None


def compute_compatibility_semantic(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """
    Compute semantic compatibility using sentence embeddings.
    
    Uses multilingual sentence-transformers model to understand
    semantic meaning beyond literal word matching.
    
    Args:
        resume_text: Candidate resume
        job_text: Job posting
    
    Returns:
        (score, explanation, details)
    """
    if not resume_text or not job_text:
        return 0.0, "Empty text", {}
    
    model = get_embedding_model()
    if model is None:
        # Fallback to simple Jaccard
        from llm_compatibility import compute_compatibility_fallback
        fallback_score = compute_compatibility_fallback(resume_text, job_text)
        return fallback_score, "Embeddings unavailable, using Jaccard fallback", {"method": "fallback"}
    
    try:
        # Truncate very long texts
        max_len = 2000
        resume_truncated = resume_text[:max_len]
        job_truncated = job_text[:max_len]
        
        # Generate embeddings
        embeddings = model.encode([resume_truncated, job_truncated])
        
        # Compute cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        score = round(similarity * 100, 1)
        
        explanation = f"Semantic embedding similarity: {score}%. Model: {_MODEL_NAME}"
        
        details = {
            "method": "semantic_embeddings",
            "semantic_score": score,
            "model": _MODEL_NAME,
            "embedding_dim": embeddings.shape[1]
        }
        
        return score, explanation, details
        
    except Exception as e:
        from llm_compatibility import compute_compatibility_fallback
        fallback_score = compute_compatibility_fallback(resume_text, job_text)
        return fallback_score, f"Embeddings failed ({e}), using Jaccard fallback", {"method": "fallback"}


def compute_compatibility_semantic_hybrid(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """
    Hybrid: 70% Semantic Embeddings + 30% TF-IDF.
    Combines deep semantic understanding with keyword matching.
    """
    # Get semantic score
    semantic_score, _, semantic_details = compute_compatibility_semantic(resume_text, job_text)
    
    # Get TF-IDF score
    try:
        from compatibility_tfidf import compute_compatibility_tfidf_hybrid
        tfidf_score, _, tfidf_details = compute_compatibility_tfidf_hybrid(resume_text, job_text)
    except:
        # Fallback to simple Jaccard
        from llm_compatibility import compute_compatibility_fallback
        tfidf_score = compute_compatibility_fallback(resume_text, job_text)
        tfidf_details = {"method": "fallback"}
    
    # Weighted average
    final_score = round(semantic_score * 0.7 + tfidf_score * 0.3, 1)
    
    explanation = f"Semantic Hybrid: {final_score}% (semantic: {semantic_score}%, tfidf: {tfidf_score}%)"
    
    details = {
        "method": "semantic_hybrid",
        "final_score": final_score,
        "semantic_score": semantic_score,
        "tfidf_score": tfidf_score,
        "model": _MODEL_NAME
    }
    
    return final_score, explanation, details


def benchmark_semantic_methods(resume_text: str, job_text: str):
    """Compare semantic methods with baselines."""
    print("\n" + "=" * 80)
    print("🔬 BENCHMARK: Semantic Embeddings vs Baselines")
    print("=" * 80 + "\n")
    
    # 1. Jaccard (baseline)
    from llm_compatibility import compute_compatibility_fallback
    jaccard_score = compute_compatibility_fallback(resume_text, job_text)
    print(f"1️⃣  Jaccard Similarity (baseline): {jaccard_score}%")
    
    # 2. TF-IDF
    try:
        from compatibility_tfidf import compute_compatibility_tfidf_hybrid
        tfidf_score, tfidf_exp, _ = compute_compatibility_tfidf_hybrid(resume_text, job_text)
        print(f"\n2️⃣  TF-IDF + Synonyms: {tfidf_score}%")
        print(f"   {tfidf_exp[:100]}")
    except Exception as e:
        print(f"\n2️⃣  TF-IDF: ERROR ({e})")
        tfidf_score = jaccard_score
    
    # 3. Semantic Embeddings
    semantic_score, semantic_exp, semantic_details = compute_compatibility_semantic(resume_text, job_text)
    print(f"\n3️⃣  Semantic Embeddings: {semantic_score}%")
    print(f"   {semantic_exp[:100]}")
    
    # 4. Semantic Hybrid
    hybrid_score, hybrid_exp, hybrid_details = compute_compatibility_semantic_hybrid(resume_text, job_text)
    print(f"\n4️⃣  Semantic Hybrid (70/30): {hybrid_score}%")
    print(f"   {hybrid_exp[:100]}")
    
    print("\n" + "=" * 80)
    print(f"📊 Summary: Jaccard={jaccard_score}% | TF-IDF={tfidf_score}% | Semantic={semantic_score}% | Hybrid={hybrid_score}%")
    print("=" * 80 + "\n")
    
    # Calculate improvements
    if jaccard_score > 0:
        tfidf_improvement = ((tfidf_score - jaccard_score) / jaccard_score) * 100
        semantic_improvement = ((semantic_score - jaccard_score) / jaccard_score) * 100
        hybrid_improvement = ((hybrid_score - jaccard_score) / jaccard_score) * 100
        
        print("📈 Improvement over Jaccard:")
        print(f"   TF-IDF: {tfidf_improvement:+.1f}%")
        print(f"   Semantic: {semantic_improvement:+.1f}%")
        print(f"   Hybrid: {hybrid_improvement:+.1f}%")
        print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🧪 TEST: Semantic Similarity with Sentence Embeddings")
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
    
    print("Test 1: High match (SRE with K8s and AWS)")
    print("-" * 80)
    job1 = """
    Vaga: Site Reliability Engineer (SRE)
    
    Procuramos profissional com experiência em:
    - Orquestração de containers na nuvem
    - Automação de infraestrutura
    - Pipelines de integração contínua
    - Monitoramento e observabilidade
    - Cloud pública (AWS preferencial)
    
    Senioridade: Pleno/Sênior
    """
    
    benchmark_semantic_methods(resume, job1)
    
    print("\n\nTest 2: Medium match (Platform Engineer with similar tech)")
    print("-" * 80)
    job2 = """
    Platform Engineer para time de infraestrutura
    
    Responsabilidades:
    - Desenhar e manter plataforma de containers
    - Implementar ferramentas de automação
    - Garantir observabilidade do ambiente
    - Trabalhar com equipe de desenvolvimento
    """
    
    benchmark_semantic_methods(resume, job2)
    
    print("\n\nTest 3: Low match (Data Science - different domain)")
    print("-" * 80)
    job3 = """
    Vaga: Data Scientist
    
    Requisitos:
    - Python para análise de dados
    - Machine Learning e estatística
    - Experiência com pandas, sklearn
    - Visualização de dados
    """
    
    benchmark_semantic_methods(resume, job3)
    
    print("\n" + "=" * 80)
    print("✅ Semantic Embeddings implementation complete")
    print("=" * 80 + "\n")
    
    print("💡 Tip: Use semantic_hybrid for best results")
    print("   Combines deep understanding with keyword matching")
