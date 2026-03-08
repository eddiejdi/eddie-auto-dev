#!/usr/bin/env python3
"""
Teste do Sistema de Treinamento de IA com Emails
Verifica se a IA está funcionando corretamente com o conteúdo treinado
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

def test_trainer_stats():
    """Testa estatísticas do trainer"""
    print("=" * 60)
    print("📊 TESTE 1: ESTATÍSTICAS DO TREINAMENTO")
    print("=" * 60)
    
    try:
        from email_trainer import get_email_trainer
        trainer = get_email_trainer()
        
        stats = trainer.get_stats()
        print(f"✅ ChromaDB disponível: {stats['chromadb_available']}")
        print(f"📧 Emails indexados: {stats['emails_indexed']}")
        print(f"💾 Arquivos locais: {stats['local_files']}")
        
        return stats['chromadb_available'], stats['emails_indexed']
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, 0


def test_training_single_email():
    """Testa treinamento de um email de exemplo"""
    print("\n" + "=" * 60)
    print("🧠 TESTE 2: TREINAMENTO DE EMAIL DE TESTE")
    print("=" * 60)
    
    try:
        from email_trainer import get_email_trainer
        trainer = get_email_trainer()
        
        # Email de teste
        test_email = {
            'id': 'test_123',
            'subject': 'Projeto Python - Deploy do servidor homelab',
            'sender': 'Shared Developer',
            'sender_email': 'shared@homelab.local',
            'body': '''
            Olá Edenilson,
            
            Precisamos fazer o deploy do novo servidor Python no homelab.
            O projeto inclui:
            - API REST com FastAPI
            - Integração com Ollama para IA
            - Bot Telegram e WhatsApp
            - Sistema de automação residencial
            
            A reunião está marcada para amanhã às 14h.
            
            Abraços,
            Shared
            ''',
            'date': '2026-01-11',
            'is_important': True,
            'spam_score': -20
        }
        
        print(f"📧 Testando email: {test_email['subject']}")
        
        success, msg = trainer.train_single_email(test_email)
        
        if success:
            print(f"✅ {msg}")
        else:
            print(f"⚠️ {msg}")
        
        return success
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def test_search_emails():
    """Testa busca de emails treinados"""
    print("\n" + "=" * 60)
    print("🔍 TESTE 3: BUSCA SEMÂNTICA DE EMAILS")
    print("=" * 60)
    
    try:
        from email_trainer import get_email_trainer
        trainer = get_email_trainer()
        
        # Diferentes termos de busca
        search_terms = [
            "projeto python deploy",
            "reunião agenda",
            "servidor homelab",
            "telegram bot",
            "automação residencial"
        ]
        
        for term in search_terms:
            print(f"\n🔎 Buscando: '{term}'")
            
            results = trainer.search_emails(term, n_results=3)
            
            if results:
                print(f"   📋 {len(results)} resultado(s) encontrado(s):")
                for i, r in enumerate(results, 1):
                    meta = r.get('metadata', {})
                    relevance = r.get('relevance', 0) * 100
                    subject = meta.get('subject', 'N/A')[:50]
                    print(f"      {i}. {subject}... (relevância: {relevance:.1f}%)")
            else:
                print("   ⚪ Nenhum resultado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def test_ollama_connection():
    """Testa conexão com Ollama"""
    print("\n" + "=" * 60)
    print("🤖 TESTE 4: CONEXÃO COM OLLAMA")
    print("=" * 60)
    
    import requests
    
    OLLAMA_HOST = "http://192.168.15.2:11434"
    
    try:
        # Verificar modelos disponíveis
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            
            print(f"✅ Ollama conectado: {OLLAMA_HOST}")
            print(f"📦 Modelos disponíveis: {len(models)}")
            
            shared_models = [m['name'] for m in models if 'shared' in m['name'].lower()]
            
            if shared_models:
                print(f"🧠 Modelos Shared encontrados:")
                for model in shared_models:
                    print(f"   • {model}")
            else:
                print("⚠️ Nenhum modelo Shared encontrado")
            
            return True, shared_models
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return False, []
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Não foi possível conectar ao Ollama: {OLLAMA_HOST}")
        return False, []
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False, []


def test_ai_query():
    """Testa consulta à IA sobre conteúdo treinado"""
    print("\n" + "=" * 60)
    print("💬 TESTE 5: CONSULTA À IA SOBRE CONTEÚDO TREINADO")
    print("=" * 60)
    
    import requests
    
    OLLAMA_HOST = "http://192.168.15.2:11434"
    
    # Primeiro, buscar contexto nos emails treinados
    try:
        from email_trainer import get_email_trainer
        trainer = get_email_trainer()
        
        # Perguntas sobre o conteúdo
        questions = [
            ("O que você sabe sobre projetos Python no homelab?", "python homelab projeto"),
            ("Quais integrações de bot existem?", "bot telegram whatsapp"),
            ("Fale sobre automação residencial", "automação residencial smart"),
        ]
        
        for question, search_term in questions:
            print(f"\n❓ Pergunta: {question}")
            
            # Buscar contexto relevante
            context_emails = trainer.search_emails(search_term, n_results=3)
            
            context = ""
            if context_emails:
                context = "\n\nContexto dos emails:\n"
                for email in context_emails:
                    context += f"- {email.get('document', '')[:300]}...\n"
            
            # Consultar IA
            prompt = f"""Com base no seguinte contexto de emails do usuário, responda a pergunta de forma útil e concisa.
{context}

Pergunta: {question}

Resposta:"""
            
            try:
                response = requests.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={
                        "model": "shared-assistant",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    answer = response.json().get('response', 'Sem resposta')
                    print(f"🤖 Resposta: {answer[:300]}...")
                else:
                    print(f"⚠️ Erro na API: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print("⚠️ Ollama não disponível para consulta")
            except Exception as e:
                print(f"⚠️ Erro na consulta: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def test_embedding_generation():
    """Testa geração de embeddings"""
    print("\n" + "=" * 60)
    print("🔢 TESTE 6: GERAÇÃO DE EMBEDDINGS")
    print("=" * 60)
    
    try:
        from email_trainer import get_email_trainer
        trainer = get_email_trainer()
        
        test_texts = [
            "Projeto de automação com Python",
            "Servidor homelab com Docker",
            "Bot do Telegram para notificações"
        ]
        
        for text in test_texts:
            print(f"\n📝 Texto: '{text}'")
            
            embedding = trainer.get_embedding(text)
            
            if embedding:
                print(f"   ✅ Embedding gerado: {len(embedding)} dimensões")
                print(f"   📊 Primeiros valores: {embedding[:5]}")
            else:
                print(f"   ⚠️ Não foi possível gerar embedding")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


def main():
    """Executa todos os testes"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║        🧪 TESTES DO SISTEMA DE TREINAMENTO DE IA 🧪          ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    results = {}
    
    # Teste 1: Estatísticas
    chromadb_ok, emails_count = test_trainer_stats()
    results['stats'] = chromadb_ok
    
    # Teste 2: Treinamento
    results['training'] = test_training_single_email()
    
    # Teste 3: Busca
    results['search'] = test_search_emails()
    
    # Teste 4: Ollama
    ollama_ok, shared_models = test_ollama_connection()
    results['ollama'] = ollama_ok
    
    # Teste 5: Consulta IA (só se Ollama OK)
    if ollama_ok:
        results['ai_query'] = test_ai_query()
    else:
        results['ai_query'] = False
        print("\n⚠️ Teste de consulta IA pulado (Ollama não disponível)")
    
    # Teste 6: Embeddings
    results['embeddings'] = test_embedding_generation()
    
    # Resumo
    print("\n" + "=" * 60)
    print("📋 RESUMO DOS TESTES")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {test_name}: {status}")
    
    total_passed = sum(1 for v in results.values() if v)
    total_tests = len(results)
    
    print(f"\n📊 Total: {total_passed}/{total_tests} testes passaram")
    
    if total_passed == total_tests:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
    elif total_passed >= total_tests - 1:
        print("\n✅ Sistema funcionando com pequenas ressalvas")
    else:
        print("\n⚠️ Alguns testes falharam - verifique as configurações")
    
    return total_passed == total_tests


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
