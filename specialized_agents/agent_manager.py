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
from .remote_orchestrator import RemoteOrchestrator
from .rag_manager import LanguageRAGManager, RAGManagerFactory
from .file_manager import FileManager
from .github_client import GitHubAgentClient, GitHubWorkflow
from .cleanup_service import CleanupService
from .requirements_analyst import RequirementsAnalystAgent, get_requirements_analyst
from .config import LLM_CONFIG, DATA_DIR, TASK_SPLIT_CONFIG
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

        # Seleciona orquestrador (local Docker ou remoto via SSH) baseado na config
        from .config import REMOTE_ORCHESTRATOR_CONFIG

        if REMOTE_ORCHESTRATOR_CONFIG.get("enabled"):
            host_cfgs = REMOTE_ORCHESTRATOR_CONFIG.get("hosts", [])
            # Fallback: if only a single dict is present or empty, ensure localhost + homelab are available
            if not host_cfgs:
                host_cfgs = [
                    {"name": "localhost", "host": "127.0.0.1", "user": "root", "ssh_key": None},
                    {"name": "homelab", "host": os.getenv("HOMELAB_HOST", "192.168.15.2"), "user": os.getenv("HOMELAB_USER", "homelab"), "ssh_key": os.getenv("HOMELAB_SSH_KEY", "~/.ssh/id_rsa")}
                ]

            if len(host_cfgs) == 1:
                h = host_cfgs[0]
                self.docker = RemoteOrchestrator(
                    host=h.get("host"),
                    user=h.get("user"),
                    ssh_key=h.get("ssh_key"),
                    base_dir=h.get("base_dir", "~/agent_projects")
                )
            else:
                self.docker = MultiRemoteOrchestrator(host_cfgs)

            self._remote_orchestrator = True
        else:
            self.docker = DockerOrchestrator()
            self._remote_orchestrator = False

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

    async def split_and_execute_task(
        self,
        description: str,
        requirements: Dict = None,
        prefer_language: str = None,
        exclude_language: str = None,
        max_workers: int = None,
        timeout_per_subtask: int = None,
        generate_only: Optional[bool] = None,
        fallback_depth: int = 0,
        max_fallback_depth: Optional[int] = None
    ) -> Dict[str, Any]:
        """Divide uma descrição em pedaços e distribui para múltiplos agentes.

        Estratégia:
        - Se `requirements.features` estiver presente, usa cada feature como chunk.
        - Caso contrário, quebra por sentenças em até `max_workers` pedaços.
        - Cria tasks em agentes diferentes (ou reutiliza linguagens disponíveis) e executa em paralelo.
        - Retorna código combinado se pelo menos uma subtask retornar código.
        - Evita reatribuição ao agente que sofreu timeout (exclude_language).
        - Pode executar subtasks somente geração (generate_only).
        """
        max_workers = max_workers or TASK_SPLIT_CONFIG.get("max_workers", 6)
        timeout_per_subtask = timeout_per_subtask or TASK_SPLIT_CONFIG.get("timeout_per_subtask_seconds", 40)
        if generate_only is None:
            generate_only = TASK_SPLIT_CONFIG.get("generate_only_subtasks", True)
        if max_fallback_depth is None:
            max_fallback_depth = TASK_SPLIT_CONFIG.get("max_fallback_depth", 1)
        if fallback_depth >= max_fallback_depth:
            return {"success": False, "error": "Fallback depth excedido"}

        parts = []
        req = requirements or {}
        features = req.get("features") if isinstance(req, dict) else None

        if features and isinstance(features, list) and len(features) > 0:
            chunks = [f"Implementar: {f}" for f in features]
        else:
            # simples quebra por sentença
            sentences = [s.strip() for s in description.split('.') if s.strip()]
            if not sentences:
                chunks = [description]
            else:
                # agrupar sentenças para criar até max_workers chunks
                n = min(max_workers, len(sentences))
                chunks = [". ".join(sentences[i::n]).strip() for i in range(n)]

        # selecionar agentes disponíveis (excluir o que sofreu timeout)
        available_langs = self.list_available_languages()
        if not available_langs:
            return {"success": False, "error": "Nenhum agente disponível"}

        # remover agente que sofreu timeout
        if exclude_language and exclude_language in available_langs:
            available_langs = [l for l in available_langs if l != exclude_language]
            if not available_langs:
                return {"success": False, "error": "Nenhum agente alternativo disponível"}

        # ordenar por menor carga e priorizar prefer_language quando possível
        lang_loads = []
        for lang in available_langs:
            agent = self.get_or_create_agent(lang)
            status = agent.get_status()
            lang_loads.append((lang, status.get("active_tasks", 0)))
        lang_loads.sort(key=lambda x: x[1])
        ordered = [l for l, _ in lang_loads]

        if prefer_language and prefer_language in ordered and prefer_language != exclude_language:
            ordered.remove(prefer_language)
            ordered.insert(0, prefer_language)

        worker_langs = []
        for i in range(len(chunks)):
            worker_langs.append(ordered[i % len(ordered)])

        async def run_chunk(idx: int, lang: str, chunk_text: str):
            agent = self.get_or_create_agent(lang)
            task = agent.create_task(chunk_text, {"split_part": idx, "fallback_depth": fallback_depth})
            try:
                log_task_start(agent.name, task.id, chunk_text, language=lang)
                # executar com timeout por subtask
                if generate_only:
                    result_task = await asyncio.wait_for(
                        agent.execute_task_generate_only(task.id, timeout_seconds=timeout_per_subtask),
                        timeout=timeout_per_subtask
                    )
                else:
                    result_task = await asyncio.wait_for(agent.execute_task(task.id), timeout=timeout_per_subtask)
                success = result_task.status == TaskStatus.COMPLETED
                log_task_end(agent.name, task.id, "completed" if success else "failed", errors=result_task.errors)
                return {
                    "index": idx,
                    "language": lang,
                    "success": success,
                    "code": result_task.code,
                    "errors": result_task.errors
                }
            except Exception as e:
                log_task_end(agent.name, task.id, "failed", errors=[str(e)])
                return {"index": idx, "language": lang, "success": False, "code": "", "errors": [str(e)]}

        # rodar todos os chunks em paralelo
        coros = [run_chunk(i, worker_langs[i], chunks[i]) for i in range(len(chunks))]
        results = await asyncio.gather(*coros)

        # combinar códigos válidos
        code_parts = []
        seen_codes = set()
        for r in sorted(results, key=lambda x: x.get("index", 0)):
            code = r.get("code")
            if code and code not in seen_codes:
                seen_codes.add(code)
                header = f"# --- chunk {r.get('index')} ({r.get('language')}) ---"
                code_parts.append(header + "\n" + code)

        combined = "\n\n".join(code_parts)

        log_response(
            "coordinator",
            "coordinator",
            f"split_and_execute_task: chunks={len(results)} success={bool(combined)} generate_only={generate_only}"
        )

        return {"success": bool(combined), "combined_code": combined, "parts": results}

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
