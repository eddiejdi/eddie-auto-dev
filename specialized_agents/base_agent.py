"""
Agente Base Especializado
Classe base para todos os agentes de linguagem específica
"""
import asyncio
import json
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path
from enum import Enum

from .config import (
    LLM_CONFIG, LANGUAGE_DOCKER_TEMPLATES, SYSTEM_PROMPTS,
    DATA_DIR, PROJECTS_DIR, TASK_SPLIT_CONFIG
)

# Import do sistema de memória
try:
    from .agent_memory import get_agent_memory, AgentMemory
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# Import do bus de comunicação
try:
    from .agent_communication_bus import (
        log_llm_call,
        log_llm_response,
        log_code_generation,
        log_task_start,
        log_task_end,
        log_error
    )
    COMM_BUS_AVAILABLE = True
except ImportError:
    COMM_BUS_AVAILABLE = False

# Import do Jira Agent Mixin
try:
    from .jira.agent_mixin import JiraAgentMixin
    JIRA_MIXIN_AVAILABLE = True
except ImportError:
    JIRA_MIXIN_AVAILABLE = False


class TaskStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    BUILDING = "building"
    TESTING = "testing"
    FIXING = "fixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CodeResult:
    success: bool
    code: str
    tests: str = ""
    stdout: str = ""
    stderr: str = ""
    iterations: int = 0
    errors: List[str] = field(default_factory=list)
    files_generated: List[str] = field(default_factory=list)


@dataclass
class Task:
    id: str
    description: str
    language: str
    status: TaskStatus = TaskStatus.PENDING
    code: str = ""
    tests: str = ""
    errors: List[str] = field(default_factory=list)
    iterations: int = 0
    container_id: Optional[str] = None
    project_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "language": self.language,
            "status": self.status.value,
            "code": self.code,
            "tests": self.tests,
            "errors": self.errors,
            "iterations": self.iterations,
            "container_id": self.container_id,
            "project_path": self.project_path,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


class LLMClient:
    """Cliente para comunicação com Ollama"""
    
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or LLM_CONFIG["base_url"]
        self.model = model or LLM_CONFIG["model"]
        self.timeout = LLM_CONFIG.get("timeout", 300)
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    def _extract_code(self, response: str, language: str = "python") -> str:
        """Extrai código de blocos markdown ou retorna texto limpo"""
        import re
        
        # Tentar extrair de bloco ```language ou ```
        patterns = [
            rf'```{language}\n(.*?)```',
            rf'```{language}(.*?)```',
            r'```\n(.*?)```',
            r'```(.*?)```',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                code = match.group(1).strip()
                if code:
                    return code
        
        # Se não encontrou bloco, limpar resposta
        lines = response.strip().split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            # Pular linhas de explicação
            if line.strip().startswith(('Here', 'This', 'The ', 'Note:', 'I ', 'Let me', '---')):
                continue
            # Detectar início de código Python
            if line.strip().startswith(('import ', 'from ', 'def ', 'class ', '#!', '"""', "'''")):
                in_code = True
            if in_code or line.strip().startswith(('#', 'import', 'from', 'def', 'class', 'if', 'for', 'while', 'try', 'with', '@')):
                code_lines.append(line)
                in_code = True
        
        if code_lines:
            return '\n'.join(code_lines)
        
        return response.strip()
    
    async def generate(self, prompt: str, system: str = None, temperature: float = None, language: str = "python") -> str:
        """Gera resposta do LLM"""
        try:
            # Log da chamada LLM
            if COMM_BUS_AVAILABLE:
                log_llm_call(f"llm_client_{language}", prompt, model=self.model)
            
            temp = temperature if temperature is not None else LLM_CONFIG.get("temperature", 0.3)
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temp,
                    "num_predict": LLM_CONFIG.get("max_tokens", 16384),
                    "repeat_penalty": LLM_CONFIG.get("repeat_penalty", 1.1),
                    "top_p": LLM_CONFIG.get("top_p", 0.9)
                }
            }
            if system:
                payload["system"] = system
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            raw_response = result.get("response", "")
            
            # Log da resposta LLM
            if COMM_BUS_AVAILABLE:
                log_llm_response(f"llm_client_{language}", raw_response, model=self.model)
            
            # Extrair código se necessário
            return self._extract_code(raw_response, language)
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error(f"llm_client_{language}", f"Erro LLM: {str(e)}")
            print(f"[LLM Error] {e}")
            return ""
    
    async def chat(self, messages: List[Dict], system: str = None) -> str:
        """Chat com histórico de mensagens"""
        try:
            # Log da chamada
            if COMM_BUS_AVAILABLE:
                last_msg = messages[-1]["content"] if messages else ""
                log_llm_call("llm_chat", last_msg, model=self.model)
            
            all_messages = []
            if system:
                all_messages.append({"role": "system", "content": system})
            all_messages.extend(messages)
            
            payload = {
                "model": self.model,
                "messages": all_messages,
                "stream": False
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            
            # Log da resposta
            if COMM_BUS_AVAILABLE:
                log_llm_response("llm_chat", content, model=self.model)
            
            return content
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error("llm_chat", f"Erro no chat: {str(e)}")
            print(f"[LLM Chat Error] {e}")
            return ""
    
    async def check_connection(self) -> bool:
        """Verifica conexão com Ollama"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except:
            return False
    
    async def list_models(self) -> List[str]:
        """Lista modelos disponíveis"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        except:
            return []


# Bases dinâmicas: inclui JiraAgentMixin quando disponível
_AGENT_BASES = (ABC,)
if JIRA_MIXIN_AVAILABLE:
    _AGENT_BASES = (JiraAgentMixin, ABC)


class SpecializedAgent(*_AGENT_BASES):
    """
    Agente base para programação especializada em uma linguagem.
    Cada agente de linguagem herda desta classe.
    Inclui JiraAgentMixin automaticamente quando disponível.
    """
    
    def __init__(self, language: str):
        self.language = language
        self.config = LANGUAGE_DOCKER_TEMPLATES.get(language, LANGUAGE_DOCKER_TEMPLATES["python"])
        self.system_prompt = SYSTEM_PROMPTS.get(f"{language}_expert", SYSTEM_PROMPTS["python_expert"])
        self.llm = LLMClient()
        self.tasks: Dict[str, Task] = {}
        self._task_counter = 0
        
        # Memória persistente
        self.memory = None
        if MEMORY_AVAILABLE:
            try:
                self.memory = get_agent_memory(f"{language}_agent")
            except Exception as e:
                print(f"[Warning] Memória não disponível para {language}: {e}")
        
        self.rag_manager = None  # Será injetado
        self.docker_orchestrator = None  # Será injetado
        self.github_client = None  # Será injetado
        self.project_dir = PROJECTS_DIR / language
        self.project_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do agente"""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Lista de capacidades do agente"""
        pass
    
    def create_task(self, description: str, metadata: Dict = None) -> Task:
        """Cria uma nova task"""
        self._task_counter += 1
        task_id = f"{self.language}_{self._task_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        task = Task(
            id=task_id,
            description=description,
            language=self.language,
            metadata=metadata or {}
        )
        self.tasks[task_id] = task
        return task
    
    async def analyze_requirements(self, description: str) -> Dict[str, Any]:
        """Analisa os requisitos do projeto"""
        prompt = f"""Analise os requisitos do seguinte projeto e retorne um JSON estruturado:

PROJETO: {description}

Retorne APENAS um JSON válido com:
{{
    "project_name": "nome_do_projeto",
    "description": "descrição breve",
    "features": ["feature1", "feature2"],
    "dependencies": ["dep1", "dep2"],
    "files_needed": ["file1.{self.config['extension']}", "file2.{self.config['extension']}"],
    "estimated_complexity": "low|medium|high",
    "docker_config": {{
        "ports": [8000],
        "volumes": ["/data"],
        "env_vars": {{"VAR": "value"}}
    }}
}}"""
        
        response = await self.llm.generate(prompt, self.system_prompt)
        try:
            # Extrair JSON da resposta
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return {
            "project_name": "project",
            "dependencies": [],
            "files_needed": [f"main{self.config['extension']}"],
            "estimated_complexity": "medium"
        }
    
    async def generate_code(self, description: str, context: str = "") -> str:
        """Gera código baseado na descrição"""
        rag_context = ""
        if self.rag_manager:
            rag_results = await self.rag_manager.search(description, self.language)
            if rag_results:
                rag_context = "\n\nEXEMPLOS DE REFERÊNCIA:\n" + "\n---\n".join(rag_results[:2])
        
        prompt = f"""Implemente em {self.language} o seguinte:

REQUISITOS:
{description}

{f"CONTEXTO ADICIONAL: {context}" if context else ""}
{rag_context}

INSTRUÇÕES:
1. Implemente TODAS as funcionalidades listadas nos requisitos
2. Crie classes e funções bem estruturadas
3. Inclua docstrings explicando cada função
4. Adicione tratamento de erros apropriado
5. O código deve ser completo e executável
6. Se for CLI, inclua if __name__ == "__main__":

Forneça APENAS o código {self.language} completo, sem explicações."""

        return await self.llm.generate(prompt, self.system_prompt, language=self.language)
    
    async def generate_tests(self, code: str, description: str = "") -> str:
        """Gera testes para o código"""
        prompt = f"""Crie testes unitários em {self.language} para o código abaixo.

CÓDIGO A TESTAR:
{code}

{f"DESCRIÇÃO DO PROJETO: {description}" if description else ""}

INSTRUÇÕES:
1. Use {self.config.get('test_cmd', 'pytest').split()[0]} como framework de testes
2. Teste TODAS as funções e métodos públicos
3. Inclua testes para:
   - Casos de sucesso com valores válidos
   - Casos de erro (divisão por zero, valores inválidos, etc)
   - Edge cases (valores limite, strings vazias, None, etc)
4. Use assertions claras e descritivas
5. Cada teste deve ser independente

Forneça APENAS o código de testes, sem explicações."""

        return await self.llm.generate(prompt, SYSTEM_PROMPTS["tester"], language=self.language)
    
    async def analyze_error(self, code: str, error: str) -> Dict[str, Any]:
        """Analisa erro e sugere correção"""
        prompt = f"""Analise e corrija o erro no código {self.language}.

CÓDIGO COM ERRO:
{code}

MENSAGEM DE ERRO:
{error}

TAREFA:
1. Identifique a causa raiz do erro
2. Corrija o código completamente
3. Mantenha toda a funcionalidade original

Retorne APENAS um JSON válido no formato:
{{"cause": "descrição breve da causa", "fix_suggestion": "o que foi corrigido", "corrected_code": "código completo corrigido"}}

IMPORTANTE: O campo corrected_code deve conter o código {self.language} COMPLETO e funcional."""

        response = await self.llm.generate(prompt, SYSTEM_PROMPTS["debugger"], temperature=0.2, language=self.language)
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except:
            pass
        return {"cause": "unknown", "fix_suggestion": "", "corrected_code": code}
    
    async def execute_task(self, task_id: str) -> Task:
        """Executa uma task completa"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} não encontrada")
        
        max_iterations = 5
        
        # Analisar requisitos
        task.status = TaskStatus.ANALYZING
        print(f"[{self.name}] Analisando requisitos...")
        requirements = await self.analyze_requirements(task.description)
        task.metadata["requirements"] = requirements
        
        # Gerar código (com timeout e fallback distribuído)
        task.status = TaskStatus.GENERATING
        print(f"[{self.name}] Gerando código...")
        # Timeout configurável (segundos) - se expirar, distribuímos a tarefa
        split_timeout = getattr(self, "split_timeout", None) or TASK_SPLIT_CONFIG.get("split_timeout_seconds", 30)
        try:
            task.code = await asyncio.wait_for(self.generate_code(task.description), timeout=split_timeout)
        except asyncio.TimeoutError:
            # Fallback: dividir a tarefa e distribuir entre múltiplos agentes
            fallback_depth = task.metadata.get("fallback_depth", 0)
            max_depth = TASK_SPLIT_CONFIG.get("max_fallback_depth", 1)
            if fallback_depth >= max_depth:
                task.status = TaskStatus.FAILED
                task.errors.append("Fallback depth excedido")
                return task
            task.metadata["fallback_depth"] = fallback_depth + 1
            try:
                from .agent_manager import get_agent_manager
                mgr = get_agent_manager()
                max_workers = TASK_SPLIT_CONFIG.get("max_workers", 6)
                subtask_timeout = TASK_SPLIT_CONFIG.get("timeout_per_subtask_seconds", 40)
                exclude_origin = TASK_SPLIT_CONFIG.get("exclude_origin_agent", True)
                generate_only = TASK_SPLIT_CONFIG.get("generate_only_subtasks", True)
                print(
                    f"[{self.name}] Geração demorando (timeout {split_timeout}s), "
                    f"distribuindo tarefa entre {max_workers} agentes..."
                )
                distributed = await mgr.split_and_execute_task(
                    task.description,
                    task.metadata.get("requirements", {}),
                    prefer_language=self.language,
                    exclude_language=self.language if exclude_origin else None,
                    max_workers=max_workers,
                    timeout_per_subtask=subtask_timeout,
                    generate_only=generate_only,
                    fallback_depth=fallback_depth + 1
                )
                # distributed será um dict com 'success' e 'combined_code'
                if distributed.get("success") and distributed.get("combined_code"):
                    task.code = distributed.get("combined_code")
                else:
                    task.code = ""
            except Exception as e:
                task.code = ""
                if COMM_BUS_AVAILABLE:
                    try:
                        log_error(self.name, f"Erro no fallback distribuído: {e}")
                    except Exception:
                        pass
        
        # Validar se código foi gerado
        if not task.code or len(task.code.strip()) < 50:
            print(f"[{self.name}] Código muito curto, tentando novamente...")
            # Tentar com prompt mais específico
            detailed_prompt = f"""Implemente uma {requirements.get('project_name', 'aplicação')} em {self.language}.

FUNCIONALIDADES REQUERIDAS:
{chr(10).join(f'- {f}' for f in requirements.get('features', [task.description]))}

O código deve:
1. Implementar TODAS as funcionalidades acima
2. Ser completo e executável
3. Incluir uma função main() ou ponto de entrada
4. Usar boas práticas de {self.language}"""
            task.code = await self.generate_code(detailed_prompt)
        
        # Gerar testes
        print(f"[{self.name}] Gerando testes...")
        task.tests = await self.generate_tests(task.code, task.description)
        
        # Salvar código em arquivo antes de Docker
        if task.code:
            project_name = task.metadata.get("project_name") or f"{self.language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            project_path = self.project_dir / project_name
            project_path.mkdir(parents=True, exist_ok=True)
            
            main_file = project_path / f"main{self.config['extension']}"
            main_file.write_text(task.code)
            
            test_file = project_path / f"test_main{self.config['extension']}"
            test_file.write_text(task.tests)
            
            task.project_path = str(project_path)
            print(f"[{self.name}] Código salvo em: {project_path}")
        
        # Build e teste no Docker
        if self.docker_orchestrator and self.docker_orchestrator.is_available():
            task.status = TaskStatus.BUILDING
            print(f"[{self.name}] Criando container Docker...")
            
            # Criar projeto Docker
            project_result = await self.docker_orchestrator.create_project(
                self.language,
                task.code,
                requirements.get("dependencies", [])
            )
            task.container_id = project_result.get("container_id")
            if project_result.get("project_path"):
                task.project_path = project_result.get("project_path")
            
            # Loop de teste e correção
            for iteration in range(max_iterations):
                task.status = TaskStatus.TESTING
                task.iterations = iteration + 1
                print(f"[{self.name}] Executando testes (iteração {iteration + 1}/{max_iterations})...")
                
                test_result = await self.docker_orchestrator.run_tests(
                    task.container_id,
                    task.code,
                    task.tests,
                    self.language
                )
                
                if test_result["success"]:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    break
                else:
                    task.status = TaskStatus.FIXING
                    task.errors.append(test_result.get("error", ""))
                    
                    # Tentar corrigir
                    fix = await self.analyze_error(task.code, test_result.get("error", ""))
                    if fix.get("corrected_code"):
                        task.code = fix["corrected_code"]
                        # Atualizar código no container
                        await self.docker_orchestrator.update_code(
                            task.container_id,
                            task.code
                        )
            else:
                task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
        
        # Indexar no RAG se bem sucedido
        if task.status == TaskStatus.COMPLETED and self.rag_manager:
            await self.rag_manager.index_code(
                task.code,
                self.language,
                task.description,
                task.id
            )
        
        return task

    async def execute_task_generate_only(self, task_id: str, timeout_seconds: Optional[int] = None) -> Task:
        """Executa somente análise + geração, sem testes e sem Docker."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} não encontrada")

        # Analisar requisitos
        task.status = TaskStatus.ANALYZING
        requirements = await self.analyze_requirements(task.description)
        task.metadata["requirements"] = requirements

        # Gerar código com timeout (sem fallback para evitar recursão)
        task.status = TaskStatus.GENERATING
        timeout_seconds = timeout_seconds or TASK_SPLIT_CONFIG.get("timeout_per_subtask_seconds", 40)
        try:
            task.code = await asyncio.wait_for(self.generate_code(task.description), timeout=timeout_seconds)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.errors.append(f"Timeout na geração (>{timeout_seconds}s)")
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.errors.append(str(e))

        return task
    
    async def collaborate_github(self, action: str, params: Dict) -> Dict:
        """Colabora com o GitHub Agent"""
        if not self.github_client:
            return {"error": "GitHub client não configurado"}
        
        return await self.github_client.execute(action, params)
    
    def should_remember_decision(
        self,
        application: str,
        component: str,
        error_type: str,
        error_message: str,
        decision_type: str,
        decision: str,
        reasoning: str = None,
        confidence: float = 0.5,
        context_data: Dict = None
    ) -> Optional[int]:
        """Registra uma decisão na memória do agente. Returns ID da decisão ou None."""
        if not self.memory:
            return None
        
        try:
            decision_id = self.memory.record_decision(
                application=application,
                component=component,
                error_type=error_type,
                error_message=error_message,
                decision_type=decision_type,
                decision=decision,
                reasoning=reasoning,
                confidence=confidence,
                context_data=context_data,
                metadata={"agent": self.name, "language": self.language}
            )
            
            if COMM_BUS_AVAILABLE:
                log_task_start(
                    self.name,
                    f"decision_{decision_id}",
                    f"Recorded decision: {decision_type} for {application}/{component}"
                )
            
            return decision_id
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error(self.name, f"Erro ao registrar decisão: {e}")
            return None
    
    def recall_past_decisions(
        self,
        application: str,
        component: str,
        error_type: str,
        error_message: str,
        limit: int = 5
    ) -> List[Dict]:
        """Busca decisões similares na memória. Returns lista de decisões."""
        if not self.memory:
            return []
        
        try:
            similar = self.memory.recall_similar_decisions(
                application=application,
                component=component,
                error_type=error_type,
                error_message=error_message,
                limit=limit
            )
            
            if similar and COMM_BUS_AVAILABLE:
                log_response(
                    self.name,
                    "memory",
                    f"Found {len(similar)} similar decisions for {application}/{component}"
                )
            
            return similar
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error(self.name, f"Erro ao buscar memória: {e}")
            return []
    
    async def make_informed_decision(
        self,
        application: str,
        component: str,
        error_type: str,
        error_message: str,
        context: Dict = None
    ) -> Dict[str, Any]:
        """Toma decisão informada consultando memória + LLM."""
        past_decisions = self.recall_past_decisions(
            application, component, error_type, error_message
        )
        
        memory_context = ""
        if past_decisions:
            memory_context = "\n\n## EXPERIÊNCIAS PASSADAS:\n"
            for i, pd in enumerate(past_decisions[:3], 1):
                outcome_text = pd.get('outcome', 'unknown')
                feedback = pd.get('feedback_score', 0.0)
                memory_context += f"""
{i}. Decisão anterior (confiança: {pd['confidence']:.2f}):
   - Decisão: {pd['decision_type']} - {pd['decision']}
   - Raciocínio: {pd.get('reasoning', 'N/A')}
   - Resultado: {outcome_text} (feedback: {feedback:.2f})
   - Data: {pd['created_at']}
"""
        
        prompt = f"""Como {self.name}, você precisa tomar uma decisão sobre o seguinte:

APLICAÇÃO: {application}
COMPONENTE: {component}
TIPO DE ERRO: {error_type}
MENSAGEM: {error_message}

CONTEXTO ADICIONAL:
{json.dumps(context or {}, indent=2)}
{memory_context}

Com base nas experiências passadas (se houver) e no contexto atual, tome uma decisão.

IMPORTANTE:
- Se houve tentativas anteriores que FALHARAM com o mesmo erro, considere uma abordagem DIFERENTE
- Se uma decisão passada teve sucesso, pode ser apropriado repetir
- Aprenda com os feedbacks negativos

Retorne um JSON com:
{{
    "decision_type": "deploy|reject|fix|analyze|investigate",
    "decision": "descrição da decisão",
    "reasoning": "raciocínio detalhado incluindo análise de experiências passadas",
    "confidence": 0.0-1.0,
    "alternative_if_fails": "o que fazer se esta decisão falhar",
    "learned_from_past": true/false
}}
"""
        
        try:
            response = await self.llm.chat(prompt, self.system_prompt)
            
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                decision_data = json.loads(json_match.group())
                decision_data['past_experiences'] = len(past_decisions)
                decision_data['past_decisions'] = past_decisions
                
                decision_id = self.should_remember_decision(
                    application=application,
                    component=component,
                    error_type=error_type,
                    error_message=error_message,
                    decision_type=decision_data['decision_type'],
                    decision=decision_data['decision'],
                    reasoning=decision_data['reasoning'],
                    confidence=decision_data.get('confidence', 0.5),
                    context_data={
                        'past_experiences_count': len(past_decisions),
                        'context': context
                    }
                )
                decision_data['memory_id'] = decision_id
                
                return decision_data
            else:
                raise ValueError("Resposta do LLM não contém JSON válido")
        
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error(self.name, f"Erro ao tomar decisão: {e}")
            
            return {
                "decision_type": "analyze",
                "decision": "Necessário análise manual devido a erro no processamento",
                "reasoning": f"Erro ao processar decisão: {str(e)}",
                "confidence": 0.3,
                "error": str(e),
                "past_experiences": len(past_decisions)
            }
    
    def update_decision_feedback(
        self,
        decision_id: int,
        success: bool,
        details: Dict = None
    ):
        """Atualiza o feedback de uma decisão após ver o resultado."""
        if not self.memory or not decision_id:
            return
        
        try:
            outcome = "success" if success else "failure"
            feedback_score = 1.0 if success else -1.0
            
            self.memory.update_decision_outcome(
                decision_id=decision_id,
                outcome=outcome,
                outcome_details=details,
                feedback_score=feedback_score
            )
            
            if COMM_BUS_AVAILABLE:
                log_task_end(
                    self.name,
                    f"decision_{decision_id}",
                    outcome,
                    feedback=feedback_score
                )
        except Exception as e:
            if COMM_BUS_AVAILABLE:
                log_error(self.name, f"Erro ao atualizar feedback: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Retorna status do agente"""
        return {
            "name": self.name,
            "language": self.language,
            "capabilities": self.capabilities,
            "active_tasks": len([t for t in self.tasks.values() if t.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]]),
            "completed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
        }
    
    def list_tasks(self) -> List[Dict]:
        """Lista todas as tasks"""
        return [task.to_dict() for task in self.tasks.values()]
