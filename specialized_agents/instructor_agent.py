"""
Agent Instrutor - Treinamento Automático dos Agents
Responsável por:
1. Varrer a internet em busca de conhecimento (documentação, tutoriais, best practices)
2. Treinar os agents pelo menos 1x ao dia
3. Operar em horários de baixa atividade para não prejudicar projetos
"""
import asyncio
import aiohttp
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import hashlib
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import schedule
import threading

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuração
INSTRUCTOR_CONFIG = {
    # Horários de treinamento (em horários de baixa atividade)
    "training_schedule": ["03:00", "15:00"],  # 3AM e 3PM UTC
    
    # Limites para não sobrecarregar
    "max_concurrent_requests": 3,
    "request_delay_seconds": 2,
    "max_pages_per_session": 100,
    "max_content_size_kb": 500,
    
    # CPU threshold - só treina se CPU < este valor
    "cpu_threshold_percent": 60,
    
    # Timeout
    "request_timeout_seconds": 30,
    "session_timeout_minutes": 60,
}

# Fontes de conhecimento por linguagem
KNOWLEDGE_SOURCES = {
    "python": {
        "official_docs": [
            "https://docs.python.org/3/library/",
            "https://docs.python.org/3/tutorial/",
            "https://peps.python.org/",
        ],
        "frameworks": [
            "https://fastapi.tiangolo.com/tutorial/",
            "https://docs.djangoproject.com/en/5.0/",
            "https://flask.palletsprojects.com/en/3.0.x/",
            "https://docs.pytest.org/en/stable/",
        ],
        "best_practices": [
            "https://realpython.com/tutorials/best-practices/",
            "https://docs.python-guide.org/",
        ],
        "search_queries": [
            "python best practices 2024",
            "python design patterns",
            "python async await tutorial",
            "python type hints guide",
            "fastapi advanced tutorial",
        ]
    },
    "javascript": {
        "official_docs": [
            "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
            "https://nodejs.org/docs/latest/api/",
        ],
        "frameworks": [
            "https://react.dev/learn",
            "https://vuejs.org/guide/",
            "https://expressjs.com/en/guide/",
            "https://nextjs.org/docs",
        ],
        "best_practices": [
            "https://github.com/goldbergyoni/nodebestpractices",
        ],
        "search_queries": [
            "javascript es2024 features",
            "node.js best practices",
            "react hooks patterns",
            "typescript advanced types",
        ]
    },
    "typescript": {
        "official_docs": [
            "https://www.typescriptlang.org/docs/handbook/",
        ],
        "frameworks": [
            "https://docs.nestjs.com/",
            "https://angular.io/docs",
        ],
        "search_queries": [
            "typescript 5 features",
            "typescript advanced patterns",
            "nestjs best practices",
        ]
    },
    "go": {
        "official_docs": [
            "https://go.dev/doc/",
            "https://go.dev/blog/",
            "https://pkg.go.dev/std",
        ],
        "frameworks": [
            "https://gin-gonic.com/docs/",
            "https://echo.labstack.com/docs",
        ],
        "search_queries": [
            "golang best practices",
            "go concurrency patterns",
            "go microservices",
        ]
    },
    "rust": {
        "official_docs": [
            "https://doc.rust-lang.org/book/",
            "https://doc.rust-lang.org/std/",
        ],
        "frameworks": [
            "https://actix.rs/docs/",
            "https://rocket.rs/guide/",
        ],
        "search_queries": [
            "rust async programming",
            "rust memory safety patterns",
            "rust web development",
        ]
    },
    "devops": {
        "official_docs": [
            "https://docs.docker.com/",
            "https://kubernetes.io/docs/",
        ],
        "best_practices": [
            "https://12factor.net/",
        ],
        "search_queries": [
            "docker best practices 2024",
            "kubernetes patterns",
            "CI/CD pipeline design",
            "infrastructure as code",
        ]
    },
    "ai_ml": {
        "official_docs": [
            "https://pytorch.org/docs/stable/",
            "https://www.tensorflow.org/guide",
            "https://huggingface.co/docs",
        ],
        "search_queries": [
            "LLM fine tuning techniques",
            "RAG implementation patterns",
            "prompt engineering best practices",
            "langchain advanced usage",
        ]
    }
}


class TrainingStatus(Enum):
    IDLE = "idle"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"  # Pausado por alta carga


@dataclass
class CrawledContent:
    """Conteúdo coletado da web."""
    url: str
    title: str
    content: str
    language: str
    content_type: str  # docs, tutorial, blog, reference
    crawled_at: datetime
    word_count: int
    hash: str  # Para evitar duplicatas
    
    def to_dict(self) -> Dict:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content[:1000] + "..." if len(self.content) > 1000 else self.content,
            "language": self.language,
            "content_type": self.content_type,
            "crawled_at": self.crawled_at.isoformat(),
            "word_count": self.word_count,
        }


@dataclass
class TrainingSession:
    """Sessão de treinamento."""
    id: str
    started_at: datetime
    status: TrainingStatus
    languages_trained: List[str] = field(default_factory=list)
    pages_crawled: int = 0
    content_indexed: int = 0
    errors: List[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "status": self.status.value,
            "languages_trained": self.languages_trained,
            "pages_crawled": self.pages_crawled,
            "content_indexed": self.content_indexed,
            "errors": self.errors[-10:],  # Últimos 10 erros
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_minutes": (
                (self.completed_at or datetime.now()) - self.started_at
            ).seconds // 60
        }


class WebCrawler:
    """Crawler inteligente para coletar conhecimento."""
    
    def __init__(self):
        self.visited_urls: set = set()
        self.content_hashes: set = set()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=INSTRUCTOR_CONFIG["request_timeout_seconds"])
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "Eddie-Instructor-Bot/1.0 (Training Agent for Development)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def crawl_url(self, url: str, language: str) -> Optional[CrawledContent]:
        """Crawla uma URL e extrai conteúdo relevante."""
        if url in self.visited_urls:
            return None
            
        self.visited_urls.add(url)
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                    
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    return None
                    
                html = await response.text()
                
                # Verificar tamanho
                if len(html) > INSTRUCTOR_CONFIG["max_content_size_kb"] * 1024:
                    html = html[:INSTRUCTOR_CONFIG["max_content_size_kb"] * 1024]
                    
                return self._parse_html(url, html, language)
                
        except Exception as e:
            logger.debug(f"Erro ao crawlar {url}: {e}")
            return None
            
    def _parse_html(self, url: str, html: str, language: str) -> Optional[CrawledContent]:
        """Extrai conteúdo relevante do HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remover scripts, styles, nav, footer, etc
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 
                           'aside', 'iframe', 'noscript', 'svg', 'form']):
                tag.decompose()
                
            # Extrair título
            title = ""
            if soup.title:
                title = soup.title.string or ""
            if not title:
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)
                    
            # Extrair conteúdo principal
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if not main_content:
                return None
                
            # Extrair texto
            text = main_content.get_text(separator='\n', strip=True)
            
            # Limpar texto
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r' {2,}', ' ', text)
            
            # Verificar se é conteúdo útil (mínimo de palavras)
            words = text.split()
            if len(words) < 100:
                return None
                
            # Gerar hash para detectar duplicatas
            content_hash = hashlib.md5(text[:5000].encode()).hexdigest()
            if content_hash in self.content_hashes:
                return None
            self.content_hashes.add(content_hash)
            
            # Detectar tipo de conteúdo
            content_type = self._detect_content_type(url, title, text)
            
            return CrawledContent(
                url=url,
                title=title[:200],
                content=text[:50000],  # Limitar tamanho
                language=language,
                content_type=content_type,
                crawled_at=datetime.now(),
                word_count=len(words),
                hash=content_hash
            )
            
        except Exception as e:
            logger.debug(f"Erro ao parsear HTML: {e}")
            return None
            
    def _detect_content_type(self, url: str, title: str, text: str) -> str:
        """Detecta o tipo de conteúdo."""
        url_lower = url.lower()
        title_lower = title.lower()
        
        if any(x in url_lower for x in ['/docs/', '/documentation/', '/reference/', '/api/']):
            return "documentation"
        if any(x in url_lower for x in ['/tutorial/', '/guide/', '/learn/', '/getting-started']):
            return "tutorial"
        if any(x in url_lower for x in ['/blog/', '/post/', '/article/']):
            return "blog"
        if any(x in title_lower for x in ['best practice', 'pattern', 'tip', 'trick']):
            return "best_practices"
        if any(x in title_lower for x in ['example', 'sample', 'demo']):
            return "example"
            
        return "reference"
        
    async def search_duckduckgo(self, query: str) -> List[str]:
        """Busca URLs no DuckDuckGo."""
        try:
            # DuckDuckGo HTML search
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            
            async with self.session.get(search_url) as response:
                if response.status != 200:
                    return []
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                urls = []
                for link in soup.find_all('a', class_='result__a', limit=10):
                    href = link.get('href', '')
                    if href.startswith('http'):
                        urls.append(href)
                        
                return urls
                
        except Exception as e:
            logger.debug(f"Erro na busca: {e}")
            return []


class AgentInstructor:
    """
    Agent Instrutor - Treina outros agents automaticamente.
    
    Responsabilidades:
    1. Varrer a internet em busca de conhecimento atualizado
    2. Processar e indexar conteúdo no RAG
    3. Treinar agents pelo menos 1x ao dia
    4. Operar em horários de baixa atividade
    """
    
    def __init__(self):
        self.config = INSTRUCTOR_CONFIG
        self.current_session: Optional[TrainingSession] = None
        self.session_history: List[TrainingSession] = []
        self.running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._training_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Inicia o Agent Instrutor."""
        self.running = True
        
        # Iniciar scheduler em thread separada
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        logger.info("🎓 Agent Instrutor iniciado")
        logger.info(f"   Horários de treinamento: {self.config['training_schedule']}")
        
    async def stop(self):
        """Para o Agent Instrutor."""
        self.running = False
        if self._training_task:
            self._training_task.cancel()
        logger.info("⏹️ Agent Instrutor parado")
        
    def _run_scheduler(self):
        """Executa o scheduler em thread separada."""
        for training_time in self.config["training_schedule"]:
            schedule.every().day.at(training_time).do(self._trigger_training)
            
        while self.running:
            schedule.run_pending()
            time.sleep(60)
            
    def _trigger_training(self):
        """Dispara treinamento (chamado pelo scheduler)."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_training_session())
            loop.close()
        except Exception as e:
            logger.error(f"Erro ao disparar treinamento: {e}")
            
    async def run_training_session(self, languages: Optional[List[str]] = None) -> TrainingSession:
        """
        Executa uma sessão de treinamento.
        
        Args:
            languages: Lista de linguagens para treinar (None = todas)
        """
        # Verificar carga do sistema
        if not await self._check_system_resources():
            logger.warning("⚠️ Sistema sobrecarregado, adiando treinamento")
            return None
            
        # Criar sessão
        session_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_session = TrainingSession(
            id=session_id,
            started_at=datetime.now(),
            status=TrainingStatus.CRAWLING
        )
        
        logger.info(f"🎓 Iniciando sessão de treinamento: {session_id}")
        
        try:
            # Determinar linguagens
            if languages is None:
                languages = list(KNOWLEDGE_SOURCES.keys())
                
            # Crawlar e indexar para cada linguagem
            async with WebCrawler() as crawler:
                for language in languages:
                    if not self.running:
                        break
                        
                    # Verificar recursos periodicamente
                    if not await self._check_system_resources():
                        self.current_session.status = TrainingStatus.PAUSED
                        logger.warning(f"⏸️ Treinamento pausado (alta carga) em {language}")
                        await asyncio.sleep(300)  # Aguardar 5 min
                        continue
                        
                    await self._train_language(crawler, language)
                    self.current_session.languages_trained.append(language)
                    
            # Finalizar sessão
            self.current_session.status = TrainingStatus.COMPLETED
            self.current_session.completed_at = datetime.now()
            self.session_history.append(self.current_session)
            
            # Notificar
            await self._notify_training_complete()
            
            logger.info(
                f"✅ Treinamento concluído: {session_id} | "
                f"Páginas: {self.current_session.pages_crawled} | "
                f"Indexados: {self.current_session.content_indexed}"
            )
            
            return self.current_session
            
        except Exception as e:
            self.current_session.status = TrainingStatus.ERROR
            self.current_session.errors.append(str(e))
            logger.error(f"❌ Erro no treinamento: {e}")
            return self.current_session
            
    async def _train_language(self, crawler: WebCrawler, language: str):
        """Treina um agent específico."""
        logger.info(f"📚 Treinando: {language}")
        
        sources = KNOWLEDGE_SOURCES.get(language, {})
        contents_to_index = []
        
        # 1. Crawlar documentação oficial
        for url in sources.get("official_docs", []):
            if self.current_session.pages_crawled >= self.config["max_pages_per_session"]:
                break
                
            content = await crawler.crawl_url(url, language)
            if content:
                contents_to_index.append(content)
                self.current_session.pages_crawled += 1
                
            await asyncio.sleep(self.config["request_delay_seconds"])
            
        # 2. Crawlar frameworks
        for url in sources.get("frameworks", []):
            if self.current_session.pages_crawled >= self.config["max_pages_per_session"]:
                break
                
            content = await crawler.crawl_url(url, language)
            if content:
                contents_to_index.append(content)
                self.current_session.pages_crawled += 1
                
            await asyncio.sleep(self.config["request_delay_seconds"])
            
        # 3. Buscar conteúdo via search
        for query in sources.get("search_queries", [])[:5]:
            if self.current_session.pages_crawled >= self.config["max_pages_per_session"]:
                break
                
            urls = await crawler.search_duckduckgo(query)
            for url in urls[:3]:
                content = await crawler.crawl_url(url, language)
                if content:
                    contents_to_index.append(content)
                    self.current_session.pages_crawled += 1
                    
                await asyncio.sleep(self.config["request_delay_seconds"])
                
        # 4. Indexar no RAG
        self.current_session.status = TrainingStatus.INDEXING
        indexed = await self._index_contents(contents_to_index, language)
        self.current_session.content_indexed += indexed
        
    async def _index_contents(self, contents: List[CrawledContent], language: str) -> int:
        """Indexa conteúdos no RAG."""
        indexed_count = 0
        
        try:
            # Tentar usar o RAG manager existente
            from specialized_agents.rag_manager import RAGManager
            rag = RAGManager()
            
            for content in contents:
                try:
                    # Preparar documento para indexação
                    doc_text = f"""
# {content.title}

**Fonte:** {content.url}
**Tipo:** {content.content_type}
**Coletado em:** {content.crawled_at.isoformat()}

---

{content.content}
"""
                    # Indexar
                    await rag.add_document(
                        language=language,
                        content=doc_text,
                        metadata={
                            "source": content.url,
                            "title": content.title,
                            "content_type": content.content_type,
                            "crawled_at": content.crawled_at.isoformat(),
                            "word_count": content.word_count,
                            "indexed_by": "instructor_agent"
                        }
                    )
                    indexed_count += 1
                    
                except Exception as e:
                    logger.debug(f"Erro ao indexar {content.url}: {e}")
                    self.current_session.errors.append(f"Index error: {content.url}")
                    
        except ImportError:
            # RAG não disponível, salvar em arquivo
            logger.warning("RAG não disponível, salvando em arquivo")
            await self._save_contents_to_file(contents, language)
            indexed_count = len(contents)
            
        return indexed_count
        
    async def _save_contents_to_file(self, contents: List[CrawledContent], language: str):
        """Salva conteúdos em arquivo quando RAG não está disponível."""
        output_dir = Path(__file__).parent.parent / "training_data" / language
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for content in contents:
            filename = hashlib.md5(content.url.encode()).hexdigest()[:12] + ".json"
            filepath = output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content.to_dict(), f, indent=2, ensure_ascii=False)
                
    async def _check_system_resources(self) -> bool:
        """Verifica se o sistema tem recursos disponíveis."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            
            if cpu > self.config["cpu_threshold_percent"]:
                logger.debug(f"CPU alta: {cpu}% > {self.config['cpu_threshold_percent']}%")
                return False
                
            return True
            
        except Exception:
            return True  # Se não conseguir verificar, prossegue
            
    async def _notify_training_complete(self):
        """Notifica sobre conclusão do treinamento."""
        try:
            from specialized_agents.agent_communication_bus import log_coordinator
            log_coordinator(
                f"🎓 Treinamento concluído: {self.current_session.pages_crawled} páginas, "
                f"{self.current_session.content_indexed} indexados, "
                f"linguagens: {', '.join(self.current_session.languages_trained)}"
            )
        except ImportError:
            pass
    
    async def train_specific_language(self, language: str, query: Optional[str] = None) -> Dict:
        """Treina uma linguagem específica sob demanda."""
        if language not in KNOWLEDGE_SOURCES:
            return {
                "success": False,
                "error": f"Linguagem não suportada: {language}",
                "supported": list(KNOWLEDGE_SOURCES.keys())
            }
        
        session = await self.run_training_session(languages=[language])
        
        # Calcula duração em segundos
        duration = (session.completed_at or datetime.now()) - session.started_at
        duration_seconds = int(duration.total_seconds())
        
        result = {
            "success": True,
            "language": language,
            "pages_crawled": session.pages_crawled,
            "content_indexed": session.content_indexed,
            "duration_seconds": duration_seconds
        }
        
        if session.errors:
            result["errors"] = session.errors[:5]  # Limitar erros no response
            
        return result
    
    async def train_all_agents(self) -> Dict:
        """Força treinamento completo de todas as linguagens."""
        session = await self.run_training_session()
        
        # Calcula duração em segundos
        duration = (session.completed_at or datetime.now()) - session.started_at
        duration_seconds = int(duration.total_seconds())
        
        return {
            "success": True,
            "languages_trained": session.languages_trained,
            "pages_crawled": session.pages_crawled,
            "content_indexed": session.content_indexed,
            "duration_seconds": duration_seconds,
            "errors_count": len(session.errors)
        }
    
    @property
    def training_history(self) -> List[TrainingSession]:
        """Retorna histórico de treinamentos."""
        return self.session_history
            
    def get_status(self) -> Dict:
        """Retorna status do Agent Instrutor."""
        return {
            "running": self.running,
            "training_schedule": self.config["training_schedule"],
            "cpu_threshold": self.config["cpu_threshold_percent"],
            "current_session": self.current_session.to_dict() if self.current_session else None,
            "total_sessions": len(self.session_history),
            "last_session": self.session_history[-1].to_dict() if self.session_history else None,
            "knowledge_sources": {
                lang: len(sources.get("official_docs", []) + sources.get("frameworks", []))
                for lang, sources in KNOWLEDGE_SOURCES.items()
            }
        }
        
    def get_training_history(self, limit: int = 10) -> List[Dict]:
        """Retorna histórico de treinamentos."""
        return [s.to_dict() for s in self.session_history[-limit:]]


# Singleton
_instructor_instance: Optional[AgentInstructor] = None


def get_instructor() -> AgentInstructor:
    """Retorna instância singleton do Agent Instrutor."""
    global _instructor_instance
    if _instructor_instance is None:
        _instructor_instance = AgentInstructor()
    return _instructor_instance


async def run_manual_training(languages: Optional[List[str]] = None):
    """Executa treinamento manual."""
    instructor = get_instructor()
    return await instructor.run_training_session(languages)
