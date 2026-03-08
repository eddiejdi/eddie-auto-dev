"""Shim LLM compatibility module.

This lightweight implementation provides two functions used by
`apply_real_job.py`: `call_ollama(prompt, temperature)` and
`temperature_for_match(score)`.

It uses simple heuristics to produce deterministic, useful outputs when a
real LLM or Ollama integration is not available. This allows advanced
compatibility logic to work in a degraded but functional mode.
"""
from typing import Optional
import os
import json


def temperature_for_match(score: float) -> float:
    """Map a compatibility score (0-100) to a reasonable temperature.

    Lower compatibility -> higher temperature (more exploratory).
    """
    try:
        s = float(score)
    except Exception:
        return 0.1
    # invert and scale
    t = max(0.05, min(0.8, (100.0 - s) / 120.0))
    return t


def _simple_diagnostic(resume: str, job: str) -> str:
    """Produce a short diagnostic string comparing resume and job text.

    This is intentionally conservative and explains likely mismatches.
    """
    resume_l = resume.lower() if resume else ""
    job_l = job.lower() if job else ""

    issues = []
    suggestions = []

    # Tokenization / synonyms
    if any(x in job_l for x in ("machine learning", "ml", "scikit")) and not any(x in resume_l for x in ("machine learning", "ml", "scikit", "tensorflow", "pytorch")):
        issues.append("Termos de Machine Learning presentes na vaga mas ausentes no currículo")
        suggestions.append("Adicionar evidências de ML ou ajustar normalização de sinônimos (ML <-> Machine Learning)")

    # Context mismatch: Python appears but context differs
    if "python" in job_l and "python" in resume_l and ("devops" in resume_l or "sre" in resume_l) and any(x in job_l for x in ("data", "machine", "learning", "ml")):
        issues.append("Python presente em contextos diferentes (DevOps vs Data Science)")
        suggestions.append("Aprimorar detecção de contexto, por exemplo analisando co-ocorrência de termos (ex.: Python + pandas) ")

    # Contact / truncation
    if len(job_l) > 2000:
        issues.append("Descrição de vaga muito longa; possível truncamento ou ruído")
        suggestions.append("Aumentar janela de contexto ou resumir antes da comparação")

    # Default: generic weakness points
    if not issues:
        issues.append("Normal: diferenças finas podem ser causadas por sinônimos, tokenização ou contexto específico da função")
        suggestions.append("Usar método híbrido (TF-IDF + embeddings) e normalização de termos técnicos")

    confidence = 70 if issues and not suggestions else 85

    parts = [
        "1) Diagnóstico geral: " + (issues[0] if issues else "Nenhuma discrepância óbvia."),
        "2) Causas prováveis:",
    ]
    for it in issues:
        parts.append(f"- {it}")
    parts.append("3) Correções recomendadas:")
    for s in suggestions:
        parts.append(f"- {s}")
    parts.append(f"4) Confiança do diagnóstico: {confidence}")

    return "\n".join(parts)


def call_ollama(prompt: str, temperature: float = 0.1) -> Optional[str]:
    """Heuristic replacement for LLM calls.

    If a real Ollama host is configured via `OLLAMA_HOST` and an HTTP
    request works, this function could be extended to call it. For now we
    provide a deterministic local diagnostic useful for testing and for
    degraded environments.
    """
    # Quick heuristic: if the prompt contains our diagnostic marker, try to
    # extract resume/job and run the simple diagnostic.
    marker = "=== VAGA ==="
    if marker in (prompt or ""):
        try:
            # naive split
            parts = prompt.split(marker)
            job_part = parts[1].split("=== CURRÍCULO ===")[0]
            resume_part = parts[1].split("=== CURRÍCULO ===")[1].split("=== DETALHES TÉCNICOS (json) ===")[0]
            return _simple_diagnostic(resume_part, job_part)
        except Exception:
            return "1) Diagnóstico geral: não foi possível extrair textos.\n2) Causas prováveis: entrada incompleta.\n3) Correções recomendadas: enviar textos completos.\n4) Confiança do diagnóstico: 40"

    # Fallback: return a short acknowledgement for email-generation prompts
    if "Generate" in (prompt or "") or "Subject:" in (prompt or "") or "Voce e um assistente" in (prompt or ""):
        return "Subject: Candidatura – Vaga\nBody:\nOlá,\nMensagem gerada automaticamente pelo assistente.\n"

    return None
#!/usr/bin/env python3
"""
LLM-based compatibility scoring using shared-whatsapp model
Provides semantic understanding beyond simple token matching
"""
import os
import json
import requests
import time
from typing import Dict, Optional, Tuple


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
MODEL_NAME = os.getenv("WHATSAPP_MODEL", "shared-whatsapp:latest")
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
USE_DYNAMIC_TEMPERATURE = os.getenv("LLM_DYNAMIC_TEMPERATURE", "1") == "1"
TEMP_MIN = float(os.getenv("LLM_TEMP_MIN", "0.05"))
TEMP_MAX = float(os.getenv("LLM_TEMP_MAX", "0.6"))


def call_ollama(prompt: str, model: str = MODEL_NAME, temperature: float = 0.1) -> Optional[str]:
    """Call Ollama API with retry logic."""
    url = f"{OLLAMA_HOST}/api/generate"
    
    # Convert numpy float32 to Python float for JSON serialization
    temperature = float(temperature)
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 200
        }
    }
    
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return None
    
    return None


def extract_score_from_response(response: str) -> Optional[float]:
    """Extract numerical score from LLM response."""
    if not response:
        return None
    
    # Try to find percentage (e.g., "75%", "75.5%")
    import re
    
    # Pattern 1: Explicit percentage
    match = re.search(r'(\d+\.?\d*)\s*%', response)
    if match:
        return float(match.group(1))
    
    # Pattern 2: Score out of 100
    match = re.search(r'score[:\s]+(\d+\.?\d*)', response, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    # Pattern 3: Just a number between 0-100
    match = re.search(r'\b(\d+\.?\d*)\b', response)
    if match:
        score = float(match.group(1))
        if 0 <= score <= 100:
            return score
    
    return None


def clamp(value: float, min_value: float, max_value: float) -> float:
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def temperature_for_match(estimated_match: float) -> float:
    """
    Map an estimated match percentage (0-100) to a temperature.
    Higher match -> lower temperature (more deterministic).
    Lower match -> higher temperature (more exploratory).
    """
    score = clamp(float(estimated_match), 0.0, 100.0)
    ratio = score / 100.0
    temp = TEMP_MAX - (TEMP_MAX - TEMP_MIN) * ratio
    return float(clamp(temp, TEMP_MIN, TEMP_MAX))


def compute_compatibility_llm(resume_text: str, job_text: str) -> Tuple[float, str]:
    """
    Compute compatibility using LLM with semantic understanding.
    
    Returns:
        (score, explanation) where score is 0-100
    """
    
    # Truncate very long texts
    max_len = 2000
    resume_truncated = resume_text[:max_len] if len(resume_text) > max_len else resume_text
    job_truncated = job_text[:max_len] if len(job_text) > max_len else job_text
    
    # Estimate match for dynamic temperature
    if USE_DYNAMIC_TEMPERATURE:
        estimated_match = compute_compatibility_fallback(resume_text, job_text)
        temperature = temperature_for_match(estimated_match)
    else:
        temperature = 0.1

    prompt = f"""Você é um especialista em recrutamento técnico. Analise a compatibilidade entre o currículo e a vaga abaixo.

**CURRÍCULO:**
{resume_truncated}

**VAGA:**
{job_truncated}

**TAREFA:**
1. Avalie a compatibilidade técnica (tecnologias, ferramentas, experiência)
2. Considere sinônimos e termos equivalentes (ex: Kubernetes = K8s, DevOps = SRE)
3. Avalie a senioridade esperada vs experiência do candidato
4. Ignore diferenças irrelevantes (formato, língua, estilo de escrita)

**RESPONDA NO SEGUINTE FORMATO:**
Score: [número de 0 a 100]%
Justificativa: [explicação breve de 1-2 linhas]

**CRITÉRIOS DE PONTUAÇÃO:**
- 80-100%: Match excelente, candidato muito qualificado
- 60-79%: Match bom, candidato qualificado com pequenas lacunas
- 40-59%: Match moderado, algumas habilidades relevantes
- 20-39%: Match fraco, poucas habilidades em comum
- 0-19%: Sem match, áreas completamente diferentes

Seja objetivo e justo na avaliação."""

    response = call_ollama(prompt, temperature=temperature)
    
    if not response:
        print("⚠️  Falha ao chamar LLM, usando fallback Jaccard")
        return compute_compatibility_fallback(resume_text, job_text), "LLM timeout - fallback usado"
    
    score = extract_score_from_response(response)
    
    if score is None:
        print(f"⚠️  Não foi possível extrair score da resposta: {response[:100]}")
        return compute_compatibility_fallback(resume_text, job_text), "Parse error - fallback usado"
    
    # Extract justification
    justification = response
    if "Justificativa:" in response:
        justification = response.split("Justificativa:", 1)[1].strip()
    
    return round(score, 1), justification[:200]


def compute_compatibility_fallback(resume_text: str, job_text: str) -> float:
    """Fallback to simple Jaccard similarity if LLM fails."""
    import re
    
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
        return 0.0
    
    inter = rset.intersection(jset)
    union = rset.union(jset)
    
    score = len(inter) / len(union)
    return round(score * 100.0, 1)


def compute_compatibility_hybrid(resume_text: str, job_text: str) -> Tuple[float, str, Dict]:
    """
    Hybrid approach: use both LLM and Jaccard, return detailed breakdown.
    
    Returns:
        (final_score, explanation, details)
    """
    
    # Get LLM score
    llm_score, llm_explanation = compute_compatibility_llm(resume_text, job_text)
    
    # Get traditional Jaccard score
    jaccard_score = compute_compatibility_fallback(resume_text, job_text)
    llm_temperature = temperature_for_match(jaccard_score) if USE_DYNAMIC_TEMPERATURE else 0.1
    
    # Weighted average: 70% LLM (semantic), 30% Jaccard (keyword matching)
    final_score = round(llm_score * 0.7 + jaccard_score * 0.3, 1)
    
    details = {
        "llm_score": llm_score,
        "jaccard_score": jaccard_score,
        "final_score": final_score,
        "llm_explanation": llm_explanation,
        "method": "hybrid",
        "llm_temperature": llm_temperature
    }
    
    explanation = f"LLM: {llm_score}%, Jaccard: {jaccard_score}%, Final: {final_score}% | {llm_explanation[:100]}"
    
    return final_score, explanation, details


def benchmark_compatibility_methods(resume_text: str, job_text: str):
    """Compare all methods side-by-side for analysis."""
    
    print("\n" + "=" * 80)
    print("🔬 BENCHMARK: Comparação de Métodos")
    print("=" * 80)
    
    # Jaccard (baseline)
    print("\n1️⃣  Jaccard Similarity (baseline):")
    jaccard_score = compute_compatibility_fallback(resume_text, job_text)
    print(f"   Score: {jaccard_score}%")
    
    # LLM only
    print("\n2️⃣  LLM Semantic (shared-whatsapp):")
    llm_score, llm_explanation = compute_compatibility_llm(resume_text, job_text)
    print(f"   Score: {llm_score}%")
    print(f"   Explicação: {llm_explanation[:150]}...")
    
    # Hybrid
    print("\n3️⃣  Hybrid (70% LLM + 30% Jaccard):")
    hybrid_score, hybrid_explanation, details = compute_compatibility_hybrid(resume_text, job_text)
    print(f"   Score: {hybrid_score}%")
    print(f"   Detalhes: {hybrid_explanation[:150]}...")
    
    print("\n" + "=" * 80)
    print(f"📊 Resumo: Jaccard={jaccard_score}% | LLM={llm_score}% | Hybrid={hybrid_score}%")
    print("=" * 80 + "\n")
    
    return {
        "jaccard": jaccard_score,
        "llm": llm_score,
        "hybrid": hybrid_score,
        "llm_explanation": llm_explanation
    }


if __name__ == "__main__":
    # Test with real examples
    
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
    
    print("\n🧪 TESTE 1: Vaga DevOps/SRE (Match Alto Esperado)")
    job1 = """
    Vaga: Site Reliability Engineer (SRE)
    
    Procuramos SRE com experiência em:
    - Orquestração de containers (K8s ou similar)
    - Pipelines de CI/CD
    - Automação de infraestrutura (Terraform/Ansible)
    - Cloud pública (AWS ou GCP)
    - Monitoramento e observabilidade
    
    Senioridade: Pleno/Sênior
    Remoto | PJ
    """
    
    benchmark_compatibility_methods(resume, job1)
    
    print("\n🧪 TESTE 2: Vaga Data Science (Match Baixo Esperado)")
    job2 = """
    Vaga Nova na Thera Consulting
    Data Science
    Disponibilidade imediata
    Contratação PJ
    Atuação remota
    """
    
    benchmark_compatibility_methods(resume, job2)
    
    print("\n🧪 TESTE 3: Vaga com sinônimos (Testar entendimento semântico)")
    job3 = """
    Estamos contratando Platform Engineer para trabalhar com:
    - K8s e containerização
    - Cloud native applications na AWS
    - IaC com Terraform
    - Observability stack
    - GitOps workflows
    
    Time internacional, 100% remoto
    """
    
    benchmark_compatibility_methods(resume, job3)
