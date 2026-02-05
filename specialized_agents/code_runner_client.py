#!/usr/bin/env python3
"""
Piston/Code Runner Client
Cliente para integração com o Code Runner do RPA4ALL
Permite execução de código Python via API
"""

import httpx
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


@dataclass
class ExecutionResult:
    """Resultado da execução de código"""
    stdout: str
    stderr: str
    exit_code: int
    success: bool
    language: str
    version: str
    signal: Optional[str] = None
    error: Optional[str] = None


class CodeRunnerClient:
    """Cliente para o Code Runner do RPA4ALL"""
    
    def __init__(
        self, 
        base_url: str = "http://192.168.15.2:2000",
        timeout: float = 60.0
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health(self) -> Dict[str, Any]:
        """Verifica saúde do serviço"""
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def is_available(self) -> bool:
        """Verifica se o serviço está disponível"""
        health = await self.health()
        return health.get("status") == "healthy"
    
    async def get_runtimes(self) -> List[Dict[str, Any]]:
        """Lista runtimes disponíveis"""
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/api/v2/runtimes")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return []
    
    async def execute(
        self,
        code: str,
        language: str = "python",
        version: str = "3.11",
        stdin: str = "",
        args: List[str] = None
    ) -> ExecutionResult:
        """
        Executa código no Code Runner
        
        Args:
            code: Código fonte a executar
            language: Linguagem (python, javascript, etc)
            version: Versão da linguagem
            stdin: Entrada padrão
            args: Argumentos de linha de comando
        
        Returns:
            ExecutionResult com stdout, stderr, exit_code
        """
        client = await self._get_client()
        
        payload = {
            "language": language,
            "version": version,
            "files": [{"content": code}],
            "stdin": stdin or "",
            "args": args or []
        }
        
        try:
            response = await client.post(
                f"{self.base_url}/api/v2/execute",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            run = data.get("run", {})
            return ExecutionResult(
                stdout=run.get("stdout", ""),
                stderr=run.get("stderr", ""),
                exit_code=run.get("code", 0),
                success=run.get("code", 0) == 0,
                language=data.get("language", language),
                version=data.get("version", version),
                signal=run.get("signal")
            )
            
        except httpx.TimeoutException:
            return ExecutionResult(
                stdout="",
                stderr="Tempo limite excedido",
                exit_code=124,
                success=False,
                language=language,
                version=version,
                error="timeout"
            )
        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=1,
                success=False,
                language=language,
                version=version,
                error=str(e)
            )
    
    async def execute_python(self, code: str, stdin: str = "") -> ExecutionResult:
        """Atalho para executar Python"""
        return await self.execute(code, language="python", stdin=stdin)


# Singleton global
_client: Optional[CodeRunnerClient] = None


def get_code_runner_client(base_url: str = None) -> CodeRunnerClient:
    """Obtém cliente singleton do Code Runner"""
    global _client
    if _client is None:
        _client = CodeRunnerClient(base_url or "http://192.168.15.2:2000")
    return _client


async def close_code_runner():
    """Fecha o cliente"""
    global _client
    if _client:
        await _client.close()
        _client = None


# ============== CLI Demo ==============
async def demo():
    """Demonstração do cliente"""
    client = get_code_runner_client()
    
    print("=== Code Runner Client Demo ===\n")
    
    # Health check
    print("1. Health Check:")
    health = await client.health()
    print(f"   Status: {health}\n")
    
    # Runtimes
    print("2. Runtimes disponíveis:")
    runtimes = await client.get_runtimes()
    for rt in runtimes:
        print(f"   - {rt['language']} {rt['version']}")
    print()
    
    # Executar código
    print("3. Executar código Python:")
    code = '''
import sys
print(f"Python {sys.version}")
print("Hello from RPA4ALL Code Runner!")

for i in range(5):
    print(f"  Número: {i}")
'''
    result = await client.execute_python(code)
    print(f"   Success: {result.success}")
    print(f"   Exit Code: {result.exit_code}")
    print(f"   Output:\n{result.stdout}")
    
    if result.stderr:
        print(f"   Errors: {result.stderr}")
    
    await close_code_runner()


if __name__ == "__main__":
    asyncio.run(demo())
