"""
Agente Base Especializado
Classe base para todos os agentes de linguagem específica
"""

import json
import httpx
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum

from .config import LLM_CONFIG, LANGUAGE_DOCKER_TEMPLATES, SYSTEM_PROMPTS, PROJECTS_DIR

# Import do bus de comunicação
try:
    from .agent_communication_bus import (
        log_llm_call,
        log_llm_response,
        log_code_generation,
        log_task_start,
        log_task_end,
        log_error,
    )

    COMM_BUS_AVAILABLE = True
except ImportError:
    COMM_BUS_AVAILABLE = False


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
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "metadata": self.metadata,
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
            rf"```{language}\n(.*?)```",
            rf"```{language}(.*?)```",
            r"```\n(.*?)```",
            r"```(.*?)```",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                code = match.group(1).strip()
                if code:
                    return code

        # Se não encontrou bloco, limpar resposta
        lines = response.strip().split("\n")
        code_lines = []
        in_code = False

        for line in lines:
            # Pular linhas de explicação
            if line.strip().startswith(
                ("Here", "This", "The ", "Note:", "I ", "Let me", "---")
            ):
                continue
            # Detectar início de código Python
            if line.strip().startswith(
                ("import ", "from ", "def ", "class ", "#!", '"""', "'''")
            ):
                in_code = True
            if in_code or line.strip().startswith(
                (
                    "#",
                    "import",
                    "from",
                    "def",
                    "class",
                    "if",
                    "for",
                    "while",
                    "try",
                    "with",
                    "@",
                )
            ):
                code_lines.append(line)
                in_code = True

        if code_lines:
            return "\n".join(code_lines)

        return response.strip()

    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        language: str = "python",
    ) -> str:
        """Gera resposta do LLM"""
        try:
            # Log da chamada LLM
            if COMM_BUS_AVAILABLE:
                log_llm_call(f"llm_client_{language}", prompt, model=self.model)

            temp = (
                temperature
                if temperature is not None
                else LLM_CONFIG.get("temperature", 0.3)
            )
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temp,
                    "num_predict": LLM_CONFIG.get("max_tokens", 16384),
                    "repeat_penalty": LLM_CONFIG.get("repeat_penalty", 1.1),
                    "top_p": LLM_CONFIG.get("top_p", 0.9),
                },
            }
            if system:
                payload["system"] = system

            response = await self.client.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            result = response.json()
            raw_response = result.get("response", "")

            # Log da resposta LLM
            if COMM_BUS_AVAILABLE:
                log_llm_response(
                    f"llm_client_{language}", raw_response, model=self.model
                )

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

            payload = {"model": self.model, "messages": all_messages, "stream": False}

            response = await self.client.post(f"{self.base_url}/api/chat", json=payload)
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


class SpecializedAgent(ABC):
    """
    Agente base para programação especializada em uma linguagem.
    Cada agente de linguagem herda desta classe.
    """

    def __init__(self, language: str):
        self.language = language
        self.config = LANGUAGE_DOCKER_TEMPLATES.get(
            language, LANGUAGE_DOCKER_TEMPLATES["python"]
        )
        self.system_prompt = SYSTEM_PROMPTS.get(
            f"{language}_expert", SYSTEM_PROMPTS["python_expert"]
        )
        self.llm = LLMClient()
        self.tasks: Dict[str, Task] = {}
        self._task_counter = 0
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
            metadata=metadata or {},
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
    "files_needed": ["file1.{self.config["extension"]}", "file2.{self.config["extension"]}"],
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
            "estimated_complexity": "medium",
        }

    async def generate_code(self, description: str, context: str = "") -> str:
        """Gera código baseado na descrição"""
        rag_context = ""
        if self.rag_manager:
            rag_results = await self.rag_manager.search(description, self.language)
            if rag_results:
                rag_context = "\n\nEXEMPLOS DE REFERÊNCIA:\n" + "\n---\n".join(
                    rag_results[:2]
                )

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

        return await self.llm.generate(
            prompt, self.system_prompt, language=self.language
        )

    async def generate_tests(self, code: str, description: str = "") -> str:
        """Gera testes para o código"""
        prompt = f"""Crie testes unitários em {self.language} para o código abaixo.

CÓDIGO A TESTAR:
{code}

{f"DESCRIÇÃO DO PROJETO: {description}" if description else ""}

INSTRUÇÕES:
1. Use {self.config.get("test_cmd", "pytest").split()[0]} como framework de testes
2. Teste TODAS as funções e métodos públicos
3. Inclua testes para:
   - Casos de sucesso com valores válidos
   - Casos de erro (divisão por zero, valores inválidos, etc)
   - Edge cases (valores limite, strings vazias, None, etc)
4. Use assertions claras e descritivas
5. Cada teste deve ser independente

Forneça APENAS o código de testes, sem explicações."""

        return await self.llm.generate(
            prompt, SYSTEM_PROMPTS["tester"], language=self.language
        )

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

        response = await self.llm.generate(
            prompt, SYSTEM_PROMPTS["debugger"], temperature=0.2, language=self.language
        )
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

        # Gerar código
        task.status = TaskStatus.GENERATING
        print(f"[{self.name}] Gerando código...")
        task.code = await self.generate_code(task.description)

        # Validar se código foi gerado
        if not task.code or len(task.code.strip()) < 50:
            print(f"[{self.name}] Código muito curto, tentando novamente...")
            # Tentar com prompt mais específico
            detailed_prompt = f"""Implemente uma {requirements.get("project_name", "aplicação")} em {self.language}.

FUNCIONALIDADES REQUERIDAS:
{chr(10).join(f"- {f}" for f in requirements.get("features", [task.description]))}

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
            project_name = (
                task.metadata.get("project_name")
                or f"{self.language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
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
                self.language, task.code, requirements.get("dependencies", [])
            )
            task.container_id = project_result.get("container_id")
            if project_result.get("project_path"):
                task.project_path = project_result.get("project_path")

            # Loop de teste e correção
            for iteration in range(max_iterations):
                task.status = TaskStatus.TESTING
                task.iterations = iteration + 1
                print(
                    f"[{self.name}] Executando testes (iteração {iteration + 1}/{max_iterations})..."
                )

                test_result = await self.docker_orchestrator.run_tests(
                    task.container_id, task.code, task.tests, self.language
                )

                if test_result["success"]:
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    break
                else:
                    task.status = TaskStatus.FIXING
                    task.errors.append(test_result.get("error", ""))

                    # Tentar corrigir
                    fix = await self.analyze_error(
                        task.code, test_result.get("error", "")
                    )
                    if fix.get("corrected_code"):
                        task.code = fix["corrected_code"]
                        # Atualizar código no container
                        await self.docker_orchestrator.update_code(
                            task.container_id, task.code
                        )
            else:
                task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()

        # Indexar no RAG se bem sucedido
        if task.status == TaskStatus.COMPLETED and self.rag_manager:
            await self.rag_manager.index_code(
                task.code, self.language, task.description, task.id
            )

        return task

    async def collaborate_github(self, action: str, params: Dict) -> Dict:
        """Colabora com o GitHub Agent"""
        if not self.github_client:
            return {"error": "GitHub client não configurado"}

        return await self.github_client.execute(action, params)

    def get_status(self) -> Dict[str, Any]:
        """Retorna status do agente"""
        return {
            "name": self.name,
            "language": self.language,
            "capabilities": self.capabilities,
            "active_tasks": len(
                [
                    t
                    for t in self.tasks.values()
                    if t.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]
                ]
            ),
            "completed_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
            ),
            "failed_tasks": len(
                [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]
            ),
        }

    def list_tasks(self) -> List[Dict]:
        """Lista todas as tasks"""
        return [task.to_dict() for task in self.tasks.values()]
