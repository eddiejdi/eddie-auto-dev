"""
Gerenciador de Agentes
Orquestra todos os agentes especializados
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base_agent import SpecializedAgent, Task, TaskStatus
from .language_agents import (
    PythonAgent, JavaScriptAgent, TypeScriptAgent,
    GoAgent, RustAgent, JavaAgent, CSharpAgent, PHPAgent,
    create_agent, AGENT_CLASSES
)
from .docker_orchestrator import DockerOrchestrator
from .rag_manager import LanguageRAGManager, RAGManagerFactory
from .file_manager import FileManager
from .github_client import GitHubAgentClient, GitHubWorkflow
from .cleanup_service import CleanupService
from .requirements_analyst import RequirementsAnalystAgent, get_requirements_analyst
from .config import LLM_CONFIG, DATA_DIR


class AgentManager:
    """
    Gerenciador central de todos os agentes especializados.
    Coordena criação, execução e limpeza de agentes.
    """
    
    def __init__(self):
        self.agents: Dict[str, SpecializedAgent] = {}
        self.docker = DockerOrchestrator()
        self.file_manager = FileManager()
        self.github_client = GitHubAgentClient()
        self.github_workflow = GitHubWorkflow(self.github_client)
        self.cleanup_service = CleanupService(self.docker)
        
        self.requirements_analyst = get_requirements_analyst()
        self._initialized = False
    
    async def initialize(self):
        """Inicializa o manager e serviços"""
        if self._initialized:
            return
        
        # Verificar Docker
        if not self.docker.is_available():
            print("[Warning] Docker não disponível. Algumas funcionalidades serão limitadas.")
        
        # Verificar GitHub
        github_ok = await self.github_client.check_connection()
        if not github_ok:
            print("[Warning] GitHub Agent não disponível.")
        
        # Iniciar cleanup periódico
        await self.cleanup_service.start_periodic_cleanup()
        
        self._initialized = True
    
    def get_or_create_agent(self, language: str) -> SpecializedAgent:
        """Obtém ou cria agente para linguagem"""
        language = language.lower()
        
        if language not in self.agents:
            agent = create_agent(language)
            
            # Injetar dependências
            agent.docker_orchestrator = self.docker
            agent.rag_manager = RAGManagerFactory.get_manager(language)
            agent.github_client = self.github_client
            
            self.agents[language] = agent
        
        return self.agents[language]
    
    def get_agent(self, language: str) -> Optional[SpecializedAgent]:
        """Obtém agente existente"""
        return self.agents.get(language.lower())
    
    def list_available_languages(self) -> List[str]:
        """Lista linguagens disponíveis"""
        return list(AGENT_CLASSES.keys())
    
    def list_active_agents(self) -> List[Dict]:
        """Lista agentes ativos"""
        return [
            {
                "language": lang,
                "name": agent.name,
                "capabilities": agent.capabilities,
                "status": agent.get_status()
            }
            for lang, agent in self.agents.items()
        ]
    
    async def create_project(
        self,
        language: str,
        description: str,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Cria novo projeto com agente especializado"""
        agent = self.get_or_create_agent(language)
        
        # Criar task
        task = agent.create_task(description, {"project_name": project_name})
        
        # Executar
        result_task = await agent.execute_task(task.id)
        
        return {
            "success": result_task.status == TaskStatus.COMPLETED,
            "task": result_task.to_dict(),
            "agent": agent.name,
            "language": language
        }
    
    async def execute_code(
        self,
        language: str,
        code: str,
        run_tests: bool = True
    ) -> Dict[str, Any]:
        """Executa código em container"""
        agent = self.get_or_create_agent(language)
        
        # Criar projeto temporário
        project_result = await self.docker.create_project(
            language, code, [], f"exec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        if not project_result.get("success"):
            return project_result
        
        container_id = project_result["container_id"]
        
        # Executar
        run_result = await self.docker.run_code(container_id, code, language=language)
        
        result = {
            "success": run_result.success,
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
            "container_id": container_id
        }
        
        # Executar testes se solicitado
        if run_tests:
            test_code = await agent.generate_tests(code)
            test_result = await self.docker.run_tests(
                container_id, code, test_code, language
            )
            result["tests"] = test_result
        
        return result
    
    async def upload_and_process(
        self,
        file_content: bytes,
        filename: str,
        language: str = None,
        auto_run: bool = False
    ) -> Dict[str, Any]:
        """Upload de arquivo e processamento opcional"""
        # Upload
        upload_result = await self.file_manager.upload_file(
            file_content, filename, language
        )
        
        if not upload_result.get("success"):
            return upload_result
        
        file_info = upload_result["file"]
        detected_lang = file_info.get("language") or language
        
        result = {
            "upload": upload_result,
            "language": detected_lang
        }
        
        # Executar se solicitado
        if auto_run and detected_lang and detected_lang != "unknown":
            code = file_content.decode('utf-8')
            exec_result = await self.execute_code(detected_lang, code)
            result["execution"] = exec_result
        
        return result
    
    async def upload_zip_project(
        self,
        zip_content: bytes,
        project_name: str = None,
        auto_build: bool = False
    ) -> Dict[str, Any]:
        """Upload de projeto ZIP"""
        # Upload e extração
        upload_result = await self.file_manager.upload_zip(
            zip_content, project_name=project_name, extract=True
        )
        
        if not upload_result.get("success"):
            return upload_result
        
        language = upload_result.get("language", "unknown")
        project_path = upload_result.get("project_path")
        
        result = {
            "upload": upload_result,
            "language": language
        }
        
        # Build se solicitado
        if auto_build and language != "unknown":
            # Importar projeto para Docker
            import_result = await self.docker.import_project(
                Path(project_path), language, project_name
            )
            result["docker"] = import_result
        
        return result
    
    async def download_project(
        self,
        language: str,
        project_name: str
    ) -> Optional[bytes]:
        """Download de projeto como ZIP"""
        from .config import PROJECTS_DIR
        project_path = PROJECTS_DIR / language / project_name
        
        if not project_path.exists():
            return None
        
        return await self.file_manager.download_project_as_zip(str(project_path))
    
    async def push_to_github(
        self,
        language: str,
        project_name: str,
        repo_name: str = None,
        description: str = ""
    ) -> Dict[str, Any]:
        """Push projeto para GitHub"""
        from .config import PROJECTS_DIR
        project_path = PROJECTS_DIR / language / project_name
        
        if not project_path.exists():
            return {"success": False, "error": "Projeto não encontrado"}
        
        # Coletar arquivos
        files = {}
        for file_path in project_path.rglob("*"):
            if file_path.is_file() and not any(
                p in str(file_path) for p in ["__pycache__", "node_modules", ".git"]
            ):
                relative = file_path.relative_to(project_path)
                try:
                    files[str(relative)] = file_path.read_text()
                except:
                    pass
        
        repo_name = repo_name or project_name
        
        return await self.github_workflow.create_project_repo(
            name=repo_name,
            description=description,
            language=language,
            initial_files=files
        )
    
    async def search_rag_all_languages(
        self,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """Busca RAG em todas as linguagens"""
        return await RAGManagerFactory.global_search(query, n_results)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Retorna status completo do sistema"""
        storage = await self.cleanup_service.get_storage_status()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "docker_available": self.docker.is_available(),
            "github_connected": await self.github_client.check_connection(),
            "active_agents": len(self.agents),
            "agents": self.list_active_agents(),
            "available_languages": self.list_available_languages(),
            "active_containers": len(self.docker.containers),
            "storage": storage,
            "llm_config": {
                "url": LLM_CONFIG["base_url"],
                "model": LLM_CONFIG["model"]
            }
        }
    
    async def run_cleanup(self) -> Dict:
        """Executa limpeza manual"""
        report = await self.cleanup_service.run_full_cleanup()
        return report.to_dict()
    
    async def shutdown(self):
        """Encerra o manager"""
        # Parar cleanup periódico
        await self.cleanup_service.stop_periodic_cleanup()
        
        # Parar containers (opcional - pode querer manter rodando)
        for container_id in list(self.docker.containers.keys()):
            await self.docker.stop_container(container_id)


# Singleton global
_manager_instance: Optional[AgentManager] = None

def get_agent_manager() -> AgentManager:
    """Retorna instância singleton do AgentManager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AgentManager()
    return _manager_instance
