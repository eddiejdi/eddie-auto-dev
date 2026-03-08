
import sys
import os
from pathlib import Path

# Adicionar o diretório atual ao path para importar web_search
sys.path.insert(0, str(Path(__file__).parent))

from web_search import create_search_engine

def train_coordinator():
    # RAG API URL do usuário
    RAG_API = os.environ.get('RAG_API') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:8001"
    
    print(f"Iniciando treinamento do agente coordenador via {RAG_API}")
    
    engine = create_search_engine(rag_api_url=RAG_API)
    
    topics = [
        "gestão de projetos de software melhores práticas agile scrum kanban",
        "gestão de incidentes ITILv4 melhores práticas",
        "como um coordenador de projetos de software deve atuar",
        "ciclo de vida de gestão de incidentes e resolução de problemas"
    ]
    
    all_results = []
    
    for topic in topics:
        print(f"\nPesquisando sobre: {topic}...")
        results = engine.search_and_extract(topic, num_results=3)
        print(f"Encontrados {len(results)} resultados.")
        
        # Salvar no RAG
        save_status = engine.save_to_rag(results, topic)
        print(f"Status do salvamento no RAG: {save_status}")
        
        all_results.extend(results)
    
    print("\n--- Resumo do Treinamento ---")
    print(f"Total de tópicos pesquisados: {len(topics)}")
    print(f"Total de documentos processados: {len(all_results)}")
    print("Treinamento concluído. O agente coordenador agora tem acesso a estes conhecimentos via RAG.")

if __name__ == "__main__":
    train_coordinator()
