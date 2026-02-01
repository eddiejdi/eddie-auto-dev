"""
Sistema de execucao de testes e auto-correcao

IMPORTANTE: O Agent de Testes deve seguir as diretrizes em TEST_AGENT_TRAINING.md
- Aumentar cobertura em cada execução até atingir 100%
- Priorizar módulos críticos (api.py, agent_manager.py)
- Gerar relatório de progresso após cada execução
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from pathlib import Path

from .llm_client import LLMClient, CodeGenerator
from .docker_manager import DockerManager, RunResult

# Referência ao documento de treinamento
TRAINING_DOC = Path(__file__).parent / "TEST_AGENT_TRAINING.md"


@dataclass
class AutoFixResult:
    success: bool
    original_code: str
    final_code: str
    iterations: int
    errors: List[str]
    tests_passed: bool


class TestRunner:
    def __init__(self, docker_manager: DockerManager = None):
        self.docker = docker_manager or DockerManager()

    def run_code(self, code: str, language: str = "python") -> RunResult:
        return self.docker.run_code(code, language)

    def run_with_tests(self, code: str, test_code: str) -> RunResult:
        return self.docker.run_tests(code, test_code)

    def validate_syntax(self, code: str, language: str = "python") -> Dict[str, Any]:
        validation_code = f'''
import ast
code = """{code}"""
try:
    ast.parse(code)
    print("SYNTAX_OK")
except SyntaxError as e:
    print(f"SYNTAX_ERROR: {{e}}")
'''
        result = self.docker.run_code(validation_code, "python")

        if "SYNTAX_OK" in result.stdout:
            return {"valid": True, "error": None}

        error_msg = result.stdout.replace("SYNTAX_ERROR:", "").strip()
        return {"valid": False, "error": error_msg}


class AutoFixer:
    def __init__(
        self,
        llm_client: LLMClient = None,
        docker_manager: DockerManager = None,
        max_iterations: int = 10,
    ):
        self.llm = llm_client or LLMClient()
        self.docker = docker_manager or DockerManager()
        self.code_gen = CodeGenerator(self.llm)
        self.test_runner = TestRunner(self.docker)
        self.max_iterations = max_iterations

    async def fix_until_works(
        self, code: str, language: str = "python", test_code: str = None
    ) -> AutoFixResult:
        current_code = code
        errors = []

        for iteration in range(self.max_iterations):
            result = self.test_runner.run_code(current_code, language)

            if result.success:
                if test_code:
                    test_result = self.test_runner.run_with_tests(
                        current_code, test_code
                    )
                    if test_result.success:
                        return AutoFixResult(
                            success=True,
                            original_code=code,
                            final_code=current_code,
                            iterations=iteration + 1,
                            errors=errors,
                            tests_passed=True,
                        )
                    error = test_result.stderr or test_result.stdout
                else:
                    return AutoFixResult(
                        success=True,
                        original_code=code,
                        final_code=current_code,
                        iterations=iteration + 1,
                        errors=errors,
                        tests_passed=True,
                    )
            else:
                error = result.stderr or result.stdout

            errors.append(f"Iteracao {iteration + 1}: {error[:500]}")
            fix_result = await self.code_gen.fix_code(current_code, error, language)

            if fix_result["success"]:
                current_code = fix_result["code"]
            else:
                break

        return AutoFixResult(
            success=False,
            original_code=code,
            final_code=current_code,
            iterations=self.max_iterations,
            errors=errors,
            tests_passed=False,
        )

    async def generate_and_fix(
        self, description: str, language: str = "python", generate_tests: bool = True
    ) -> AutoFixResult:
        gen_result = await self.code_gen.generate_code(description, language)

        if not gen_result["success"]:
            return AutoFixResult(
                success=False,
                original_code="",
                final_code="",
                iterations=0,
                errors=[f"Falha na geracao: {gen_result.get('error', 'desconhecido')}"],
                tests_passed=False,
            )

        code = gen_result["code"]
        test_code = None

        if generate_tests:
            test_result = await self.code_gen.generate_tests(code)
            if test_result["success"]:
                test_code = test_result["test_code"]

        return await self.fix_until_works(code, language, test_code)
