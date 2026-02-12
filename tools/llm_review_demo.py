#!/usr/bin/env python3
"""Demo runner for `review_compatibility_with_llm`.

This script stubs Google libs to allow importing `apply_real_job` without
installing heavy dependencies, mocks the LLM call and runs a sample review.
"""
import sys, types
from pathlib import Path

# Create stubs for google / googleapiclient used at module import
def _inject_google_stubs():
    m_google = types.ModuleType('google')
    m_google_oauth2 = types.ModuleType('google.oauth2')
    m_google_oauth2_credentials = types.ModuleType('google.oauth2.credentials')
    setattr(m_google_oauth2_credentials, 'Credentials', type('Credentials', (), {}))
    m_google_auth = types.ModuleType('google.auth')
    m_google_auth_transport = types.ModuleType('google.auth.transport')
    m_google_auth_transport_requests = types.ModuleType('google.auth.transport.requests')
    setattr(m_google_auth_transport_requests, 'Request', type('Request', (), {}))
    m_googleapiclient = types.ModuleType('googleapiclient')
    m_googleapiclient_discovery = types.ModuleType('googleapiclient.discovery')
    setattr(m_googleapiclient_discovery, 'build', lambda *a, **k: None)
    m_googleapiclient_http = types.ModuleType('googleapiclient.http')
    setattr(m_googleapiclient_http, 'MediaFileUpload', type('MediaFileUpload', (), {}))
    setattr(m_googleapiclient_http, 'MediaIoBaseDownload', type('MediaIoBaseDownload', (), {}))

    stubs = {
        'google': m_google,
        'google.oauth2': m_google_oauth2,
        'google.oauth2.credentials': m_google_oauth2_credentials,
        'google.auth': m_google_auth,
        'google.auth.transport': m_google_auth_transport,
        'google.auth.transport.requests': m_google_auth_transport_requests,
        'googleapiclient': m_googleapiclient,
        'googleapiclient.discovery': m_googleapiclient_discovery,
        'googleapiclient.http': m_googleapiclient_http,
    }
    for k, v in stubs.items():
        if k not in sys.modules:
            sys.modules[k] = v


def main():
    _inject_google_stubs()

    try:
        # Garantir que o diretório raiz do projeto esteja no sys.path
        repo_root = Path(__file__).resolve().parents[1]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        import apply_real_job as arj
    except Exception as e:
        print('ERRO: não foi possível importar apply_real_job:', e)
        raise

    # Force LLM path and mock call_ollama
    arj.ADVANCED_AVAILABLE = True
    def mock_call_ollama(prompt, temperature=0.1):
        # Return a realistic diagnostic sample
        return (
            "1) Tokenização: o método Jaccard pode ignorar sinônimos (ex.: 'ML' vs 'Machine Learning').\n"
            "2) Contexto: termos como 'Python' aparecem em contextos diferentes (DevOps x Data Science).\n"
            "3) Extração: contatos ou requisitos podem ter sido truncados ou mal parseados.\n"
            "Sugestões: use método híbrido (tfidf+embeddings), normalização de termos e aumentar contexto de análise."
        )

    arj.call_ollama = mock_call_ollama
    arj.temperature_for_match = lambda c: 0.1

    resume = (
        "Edenilson Teixeira - DevOps / SRE\n"
        "Experiência com Kubernetes, Docker, CI/CD, Terraform, AWS, Python para automação."
    )

    job = (
        "Vaga: Data Scientist - Remoto\n"
        "Requisitos: Python, R, SQL, Machine Learning, estatística, experiência com scikit-learn e TensorFlow."
    )

    print('\n=== Executando revisão LLM demo ===\n')
    diag = arj.review_compatibility_with_llm(resume, job, 1.1, {'method': 'jaccard'})
    print('DIAGNÓSTICO LLM:\n')
    print(diag)


if __name__ == '__main__':
    main()
