#!/usr/bin/env python3
"""
Teste interativo da IA treinada com emails
"""

import sys
from pathlib import Path
import os
import requests

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from email_trainer import get_email_trainer

OLLAMA_HOST = os.environ.get("OLLAMA_URL") or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:11434"

def main():
    trainer = get_email_trainer()
    
    print("=" * 60)
    print("🧠 TESTE INTERATIVO COM A IA TREINADA")
    print("=" * 60)
    
    # Verificar conteúdo indexado
    stats = trainer.get_stats()
    print(f"\n📊 Base de conhecimento:")
    print(f"   • ChromaDB: {'✅' if stats['chromadb_available'] else '❌'}")
    print(f"   • Emails indexados: {stats['emails_indexed']}")
    print(f"   • Arquivos locais: {stats['local_files']}")
    
    # Buscar todos os emails
    print("\n📧 Conteúdo treinado:")
    results = trainer.search_emails("email projeto reunião servidor deploy", n_results=10)
    
    if results:
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            relevance = r.get("relevance", 0) * 100
            print(f"\n   📌 Email {i}:")
            print(f"      Assunto: {meta.get('subject', 'N/A')[:60]}")
            print(f"      De: {meta.get('sender', 'N/A')}")
            print(f"      Data: {meta.get('date', 'N/A')}")
            print(f"      Relevância: {relevance:.1f}%")
    else:
        print("   ⚪ Nenhum email encontrado")
    
    # Perguntas específicas para a IA
    print("\n" + "=" * 60)
    print("💬 CONSULTAS À IA SHARED")
    print("=" * 60)
    
    questions = [
        "Quais são os emails mais recentes sobre deploy?",
        "Sobre o que é a reunião mencionada nos emails?",
        "Quais tecnologias são mencionadas nos emails do homelab?"
    ]
    
    for q in questions:
        print(f"\n❓ {q}")
        
        # Buscar contexto
        context_results = trainer.search_emails(q, n_results=3)
        context = ""
        if context_results:
            for r in context_results:
                doc = r.get('document', '')[:500]
                context += f"\n{doc}\n---"
        
        # Consultar IA
        prompt = f"""Baseado nos seguintes emails do usuário:
{context}

Responda de forma breve e direta: {q}"""
        
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "shared-assistant",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                answer = response.json().get('response', 'Sem resposta')
                print(f"🤖 {answer[:400]}")
            else:
                print(f"⚠️ Erro: {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Erro: {e}")
    
    # Teste de busca específica
    print("\n" + "=" * 60)
    print("🔍 TESTES DE BUSCA SEMÂNTICA")
    print("=" * 60)
    
    search_tests = [
        "FastAPI REST",
        "Ollama integração",
        "Telegram WhatsApp bot",
        "automação",
        "Edenilson"
    ]
    
    for term in search_tests:
        results = trainer.search_emails(term, n_results=2)
        
        if results:
            best = results[0]
            relevance = best.get('relevance', 0) * 100
            subject = best.get('metadata', {}).get('subject', 'N/A')[:40]
            print(f"   '{term}' → {subject}... ({relevance:.0f}%)")
        else:
            print(f"   '{term}' → Nenhum resultado")
    
    print("\n✅ Testes concluídos!")


if __name__ == "__main__":
    main()
