"""
Módulo de Busca Web para Claude Chat
Integra busca na internet com DuckDuckGo e salva conhecimento no RAG
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import re
import json
import time
from urllib.parse import quote_plus, urlparse
import hashlib


@dataclass
class SearchResult:
    """Resultado de busca."""
    title: str
    url: str
    snippet: str
    content: Optional[str] = None
    source: str = "web"
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class WebSearchEngine:
    """Motor de busca web usando DuckDuckGo."""
    
    def __init__(self, rag_api_url: str = None):
        self.rag_api_url = rag_api_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.search_history = []
    
    def search_duckduckgo(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """
        Busca no DuckDuckGo usando HTML scraping.
        Não requer API key.
        """
        results = []
        
        try:
            # DuckDuckGo HTML search
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Encontrar resultados
            result_divs = soup.find_all("div", class_="result")
            
            for div in result_divs[:num_results]:
                try:
                    # Título e URL
                    title_elem = div.find("a", class_="result__a")
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get("href", "")
                    
                    # Snippet
                    snippet_elem = div.find("a", class_="result__snippet")
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    if title and url:
                        results.append(SearchResult(
                            title=title,
                            url=url,
                            snippet=snippet
                        ))
                except Exception:
                    continue
                    
        except Exception as e:
            print(f"Erro na busca DuckDuckGo: {e}")
        
        return results
    
    def search_with_api(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """
        Método alternativo usando a API lite do DuckDuckGo.
        """
        results = []
        
        try:
            # DuckDuckGo Instant Answer API
            api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
            
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Resultado principal (Abstract)
            if data.get("Abstract"):
                results.append(SearchResult(
                    title=data.get("Heading", query),
                    url=data.get("AbstractURL", ""),
                    snippet=data.get("Abstract", ""),
                    source="duckduckgo_instant"
                ))
            
            # Resultados relacionados
            for related in data.get("RelatedTopics", [])[:num_results-1]:
                if isinstance(related, dict) and related.get("Text"):
                    results.append(SearchResult(
                        title=related.get("Text", "")[:100],
                        url=related.get("FirstURL", ""),
                        snippet=related.get("Text", ""),
                        source="duckduckgo_related"
                    ))
                    
        except Exception as e:
            print(f"Erro na API DuckDuckGo: {e}")
        
        return results
    
    def extract_page_content(self, url: str, max_chars: int = 5000) -> Optional[str]:
        """
        Extrai conteúdo principal de uma página web.
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remover scripts, styles, nav, footer, etc.
            for element in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
                element.decompose()
            
            # Tentar encontrar conteúdo principal
            main_content = None
            
            # Tentar diferentes seletores comuns
            selectors = [
                "article",
                "main",
                ".content",
                ".post-content",
                ".article-content",
                ".entry-content",
                "#content",
                ".main-content"
            ]
            
            for selector in selectors:
                content = soup.select_one(selector)
                if content:
                    main_content = content
                    break
            
            if not main_content:
                main_content = soup.find("body")
            
            if main_content:
                # Extrair texto limpo
                text = main_content.get_text(separator="\n", strip=True)
                
                # Limpar espaços extras
                text = re.sub(r"\n{3,}", "\n\n", text)
                text = re.sub(r" {2,}", " ", text)
                
                return text[:max_chars]
                
        except Exception as e:
            print(f"Erro ao extrair conteúdo de {url}: {e}")
        
        return None
    
    def search_and_extract(
        self, 
        query: str, 
        num_results: int = 3,
        extract_content: bool = True
    ) -> List[SearchResult]:
        """
        Busca e opcionalmente extrai conteúdo das páginas.
        """
        # Primeiro tenta busca HTML
        results = self.search_duckduckgo(query, num_results)
        
        # Se não encontrou, tenta API
        if not results:
            results = self.search_with_api(query, num_results)
        
        # Extrair conteúdo das páginas
        if extract_content:
            for result in results:
                if result.url:
                    content = self.extract_page_content(result.url)
                    if content:
                        result.content = content
        
        # Salvar no histórico
        self.search_history.append({
            "query": query,
            "results": len(results),
            "timestamp": datetime.now().isoformat()
        })
        
        return results
    
    def save_to_rag(self, results: List[SearchResult], query: str) -> Dict:
        """
        Salva os resultados da busca na base RAG para incrementar o conhecimento.
        """
        if not self.rag_api_url:
            return {"success": False, "error": "RAG API URL não configurada"}
        
        saved_count = 0
        errors = []
        
        for result in results:
            try:
                # Preparar documento para o RAG
                content_to_save = result.content if result.content else result.snippet
                
                if not content_to_save:
                    continue
                
                # Gerar ID único baseado no conteúdo
                doc_id = hashlib.md5(f"{result.url}{result.title}".encode()).hexdigest()[:12]
                
                # Metadados do documento
                metadata = {
                    "source": "web_search",
                    "url": result.url,
                    "title": result.title,
                    "search_query": query,
                    "timestamp": result.timestamp,
                    "type": "web_content"
                }
                
                # Formatar documento
                document_text = f"""# {result.title}

**Fonte:** {result.url}
**Buscado em:** {result.timestamp}
**Query:** {query}

---

{content_to_save}
"""
                
                # Enviar para RAG API
                # Tentar diferentes endpoints comuns de RAG
                endpoints_to_try = [
                    f"{self.rag_api_url}/api/v1/documents",
                    f"{self.rag_api_url}/api/v1/rag/add",
                    f"{self.rag_api_url}/api/documents",
                    f"{self.rag_api_url}/documents"
                ]
                
                success = False
                for endpoint in endpoints_to_try:
                    try:
                        response = requests.post(
                            endpoint,
                            json={
                                "id": doc_id,
                                "content": document_text,
                                "text": document_text,
                                "metadata": metadata,
                                "source": result.url
                            },
                            timeout=10
                        )
                        if response.status_code in [200, 201]:
                            saved_count += 1
                            success = True
                            break
                    except:
                        continue
                
                if not success:
                    # Salvar localmente como fallback
                    self._save_local_knowledge(document_text, metadata)
                    saved_count += 1
                    
            except Exception as e:
                errors.append(str(e))
        
        return {
            "success": saved_count > 0,
            "saved_count": saved_count,
            "total_results": len(results),
            "errors": errors
        }
    
    def _save_local_knowledge(self, content: str, metadata: Dict):
        """
        Salva conhecimento localmente quando RAG API não está disponível.
        """
        import os
        
        knowledge_dir = "knowledge_base"
        os.makedirs(knowledge_dir, exist_ok=True)
        
        # Criar arquivo de conhecimento
        doc_id = hashlib.md5(content[:100].encode()).hexdigest()[:8]
        filename = f"{knowledge_dir}/web_{doc_id}_{int(time.time())}.md"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"---\n")
            f.write(f"source: {metadata.get('url', 'web')}\n")
            f.write(f"title: {metadata.get('title', 'Sem título')}\n")
            f.write(f"query: {metadata.get('search_query', '')}\n")
            f.write(f"timestamp: {metadata.get('timestamp', '')}\n")
            f.write(f"type: web_knowledge\n")
            f.write(f"---\n\n")
            f.write(content)
        
        return filename
    
    def format_results_for_llm(self, results: List[SearchResult], query: str) -> str:
        """
        Formata resultados para uso pelo LLM.
        """
        if not results:
            return f"Nenhum resultado encontrado para: {query}"
        
        formatted = f"## Resultados da Busca Web para: \"{query}\"\n\n"
        formatted += f"*Encontrados {len(results)} resultados em {datetime.now().strftime('%d/%m/%Y %H:%M')}*\n\n"
        formatted += "---\n\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"### {i}. {result.title}\n"
            formatted += f"**URL:** {result.url}\n\n"
            
            if result.content:
                # Resumir conteúdo se muito longo
                content_preview = result.content[:2000]
                if len(result.content) > 2000:
                    content_preview += "...\n\n[Conteúdo truncado]"
                formatted += f"**Conteúdo:**\n{content_preview}\n\n"
            else:
                formatted += f"**Resumo:** {result.snippet}\n\n"
            
            formatted += "---\n\n"
        
        return formatted


def create_search_engine(rag_api_url: str = None) -> WebSearchEngine:
    """Factory function para criar motor de busca."""
    return WebSearchEngine(rag_api_url=rag_api_url)


# Exemplo de uso
if __name__ == "__main__":
    RAG_API = os.environ.get('RAG_API') or f"http://{os.environ.get('HOMELAB_HOST','localhost')}:8001"
    engine = WebSearchEngine(rag_api_url=RAG_API)
    
    # Testar busca
    results = engine.search_and_extract("Python machine learning tutorial", num_results=3)
    
    for r in results:
        print(f"Título: {r.title}")
        print(f"URL: {r.url}")
        print(f"Snippet: {r.snippet[:100]}...")
        print("---")
    
    # Formatar para LLM
    formatted = engine.format_results_for_llm(results, "Python machine learning tutorial")
    print(formatted)
