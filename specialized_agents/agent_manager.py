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
from .agent_communication_bus import (
    get_communication_bus,
    log_coordinator,
    log_task_start,
    log_task_end,
    log_request,
    log_response,
    log_docker_operation,
    log_github_operation,
    log_error,
    log_execution,
    log_code_generation,
    MessageType
)


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
        
        # Log início da criação do projeto
        log_coordinator(f"Iniciando criação de projeto {language.upper()}: {description[:100]}")
        log_request("coordinator", agent.name, f"Criar projeto: {description}", language=language)
        
        # Criar task
        task = agent.create_task(description, {"project_name": project_name})
        log_task_start(agent.name, task.id, description, language=language)
        
        # Executar
        result_task = await agent.execute_task(task.id)
        
        # Log resultado
        if result_task.status == TaskStatus.COMPLETED:
            log_task_end(agent.name, task.id, "completed", language=language)
            log_response(agent.name, "coordinator", f"Projeto criado com sucesso: {project_name or task.id}")
        else:
            log_task_end(agent.name, task.id, "failed", errors=result_task.errors)
            log_error(agent.name, f"Falha na criação: {result_task.errors}")
        
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
        
        log_request("coordinator", "docker", f"Executar código {language}", code_length=len(code))
        
        # Criar projeto temporário
        project_result = await self.docker.create_project(
            language, code, [], f"exec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        
        if not project_result.get("success"):
            log_error("docker", f"Falha ao criar container: {project_result.get('error')}")
            return project_result
        
        container_id = project_result["container_id"]
        log_docker_operation("docker", "create_container", container_id, language=language)
        
        # Executar
        run_result = await self.docker.run_code(container_id, code, language=language)
        
        log_execution(
            agent.name, 
            run_result.stdout or run_result.stderr or "Execução concluída",
            success=run_result.success,
            container_id=container_id
        )
        
        result = {
            "success": run_result.success,
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
            "container_id": container_id
        }
        
        # Executar testes se solicitado
        if run_tests:
            log_request(agent.name, "test_generator", "Gerar testes para código")
            test_code = await agent.generate_tests(code)
            test_result = await self.docker.run_tests(
                container_id, code, test_code, language
            )
            log_execution(agent.name, f"Testes executados: {test_result}", success=True)
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
        
        log_github_operation("coordinator", "push_to_github", f"{project_name} -> {repo_name or project_name}")
        
        if not project_path.exists():
            log_error("github", f"Projeto não encontrado: {project_name}")
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
        
        log_github_operation("github", "collect_files", f"{len(files)} arquivos coletados")
        
        repo_name = repo_name or project_name
        
        result = await self.github_workflow.create_project_repo(
            name=repo_name,
            description=description,
            language=language,
            initial_files=files
        )
        
        if result.get("success"):
            log_response("github", "coordinator", f"Repo criado: {repo_name}")
        else:
            log_error("github", f"Falha no push: {result.get('error')}")
        
        return result
    
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

    # ==========================================
    # INTEGRACAO COM ANALISTA DE REQUISITOS
    # ==========================================

    async def analyze_project_requirements(self, description: str) -> Dict[str, Any]:
        """Analisa requisitos de um projeto"""
        requirement = await self.requirements_analyst.analyze_requirements(description)
        return {
            "success": True,
            "requirement": requirement.to_dict()
        }

    async def generate_requirement_docs(self, req_id: str, doc_type: str = "full") -> Dict[str, Any]:
        """Gera documentacao para um requisito"""
        try:
            docs = await self.requirements_analyst.generate_documentation(req_id, doc_type)
            return {"success": True, "documentation": docs}
        except ValueError as e:
            return {"success": False, "error": str(e)}

    async def generate_requirement_tests(self, req_id: str, language: str = "python") -> Dict[str, Any]:
        """Gera casos de teste para um requisito"""
        try:
            test_cases = await self.requirements_analyst.generate_test_cases(req_id, language)
            test_code = await self.requirements_analyst.generate_test_code(req_id, language)
            return {
                "success": True,
                "test_cases": test_cases,
                "test_code": test_code
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}

    async def create_project_with_requirements(
        self,
        description: str,
        language: str,
        project_name: str = None
    ) -> Dict[str, Any]:
        """Fluxo completo: analisa requisitos -> gera docs -> cria projeto -> valida entrega"""
        # 1. Analisar requisitos
        requirement = await self.requirements_analyst.analyze_requirements(description)
        
        # 2. Gerar documentacao
        await self.requirements_analyst.generate_documentation(requirement.id, "technical")
        
        # 3. Preparar tarefa para programador
        task_package = await self.requirements_analyst.prepare_task_for_programmer(
            requirement.id, language
        )
        
        # 4. Criar projeto com agente
        agent = self.get_or_create_agent(language)
        task = agent.create_task(task_package["task_description"], {
            "requirement_id": requirement.id,
            "project_name": project_name
        })
        result_task = await agent.execute_task(task.id)
        
        # 5. Validar entrega
        validation = await self.requirements_analyst.validate_agent_output(
            requirement.id, result_task, agent
        )
        
        return {
            "success": result_task.status.value == "completed" and validation["approved"],
            "requirement": requirement.to_dict(),
            "task": result_task.to_dict(),
            "validation": validation,
            "documentation": task_package["documentation"],
            "test_code": task_package["test_code"]
        }

    async def review_agent_delivery(
        self,
        task_id: str,
        requirement_id: str,
        agent_name: str,
        code: str,
        tests: str = ""
    ) -> Dict[str, Any]:
        """Revisa entrega de um agente"""
        review = await self.requirements_analyst.review_delivery(
            task_id, requirement_id, agent_name, code, tests
        )
        return {
            "success": True,
            "review": review.to_dict()
        }

    def get_requirements_status(self) -> Dict[str, Any]:
        """Status do analista de requisitos"""
        return self.requirements_analyst.get_status()

    def list_all_requirements(self) -> List[Dict]:
        """Lista todos os requisitos"""
        return self.requirements_analyst.list_requirements()

    def list_all_reviews(self) -> List[Dict]:
        """Lista todas as reviews"""
        return self.requirements_analyst.list_reviews()


# Singleton global
_manager_instance: Optional[AgentManager] = None

def get_agent_manager() -> AgentManager:
    """Retorna instância singleton do AgentManager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = AgentManager()
    return _manager_instance


def reset_agent_manager():
    """Reseta o singleton do AgentManager"""
    global _manager_instance
    _manager_instance = None

def reset_agent_manager():
    """Reseta o singleton do AgentManager"""
    global _manager_instance
    _manager_instance = None
