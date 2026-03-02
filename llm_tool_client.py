#!/usr/bin/env python3
"""
LLM Tool Client — Cliente interativo que conecta Ollama + Executor Enhanced.

Suporta dois modos de tool calling:
  1. NATIVO (padrão): usa `tools` parameter do Ollama → message.tool_calls
  2. LEGACY: usa tags <tool_call>...</tool_call> (fallback)

Uso:
    python3 llm_tool_client.py "qual é o status do docker?"
    python3 llm_tool_client.py --model qwen3:8b "docker ps"
    python3 llm_tool_client.py -i          # modo interativo
    python3 llm_tool_client.py --legacy     # forçar modo legacy (tags)
    python3 llm_tool_client.py --stats      # estatísticas de aprendizado
"""

import asyncio
import json
import logging
import os
import sys
import argparse
from typing import Optional

import httpx

# Imports locais — parsing e formatação de tool calls (legacy mode)
from specialized_agents.llm_tool_prompts import (
    parse_tool_calls,
    get_tool_result_prompt,
    strip_tool_calls,
)

# Imports nativos — tool schemas Ollama (native mode)
from specialized_agents.llm_tool_schemas import (
    get_ollama_tools,
    get_tool_system_message,
    normalize_tool_calls,
    format_tool_result_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Defaults
# ──────────────────────────────────────────────────────────────────
DEFAULT_OLLAMA = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "eddie-coder")
DEFAULT_API = os.getenv("EDDIE_API", "http://localhost:8503")
MAX_TOOL_ROUNDS = 5  # evitar loop infinito de tool calls


class LLMToolClient:
    """Cliente multi-turn que conecta Ollama (chat) + executor API.
    
    Modos:
        native (padrão): usa Ollama tools parameter → message.tool_calls
        legacy: usa <tool_call> tags no system prompt
    """

    def __init__(
        self,
        ollama_host: str = DEFAULT_OLLAMA,
        api_host: str = DEFAULT_API,
        model: str = DEFAULT_MODEL,
        verbose: bool = False,
        use_native_tools: bool = True,
    ):
        self.ollama_host = ollama_host.rstrip("/")
        self.api_host = api_host.rstrip("/")
        self.model = model
        self.verbose = verbose
        self.use_native_tools = use_native_tools

        # Histórico de mensagens para multi-turn
        self.messages: list[dict] = []
        # System prompt (carregado da API ou fallback local)
        self.system_prompt: str = ""
        # Histórico de execuções
        self.execution_history: list[dict] = []

    # ──────────────────────────────────────────────────────────────
    # Setup
    # ──────────────────────────────────────────────────────────────

    async def initialize(self):
        """Carrega system prompt e prepara sessão."""
        if self.use_native_tools:
            # Modo nativo: system prompt vem do schema
            self.system_prompt = get_tool_system_message()
            if self.verbose:
                logger.info(f"[NATIVE] System prompt: {len(self.system_prompt)} chars")
                logger.info(f"[NATIVE] Tools: {len(get_ollama_tools())} definidas")
        else:
            # Modo legacy: system prompt da API com instruções de tags
            self.system_prompt = await self._fetch_system_prompt()
            if self.verbose:
                logger.info(f"[LEGACY] System prompt: {len(self.system_prompt)} chars")

    async def _fetch_system_prompt(self) -> str:
        """Busca system prompt de /llm-tools/system-prompt."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.api_host}/llm-tools/system-prompt")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("system_prompt", "")
            except Exception as e:
                logger.warning(f"Falha ao obter system prompt da API: {e}")

        # Fallback: gerar localmente
        from specialized_agents.llm_tool_prompts import get_tool_system_prompt
        return get_tool_system_prompt()

    # ──────────────────────────────────────────────────────────────
    # Core: chat multi-turn com tool calling
    # ──────────────────────────────────────────────────────────────

    async def chat(self, user_input: str) -> str:
        """
        Envia mensagem ao LLM, processa tool calls, re-injeta resultados.
        Retorna resposta final textual.
        
        Modo nativo: usa message.tool_calls do Ollama
        Modo legacy: usa tags <tool_call> no texto
        """
        # Adicionar mensagem do usuário
        self.messages.append({"role": "user", "content": user_input})

        if self.use_native_tools:
            return await self._chat_native()
        else:
            return await self._chat_legacy()

    async def _chat_native(self) -> str:
        """Chat loop usando tool calling nativo do Ollama."""
        for round_num in range(MAX_TOOL_ROUNDS):
            raw_response = await self._call_ollama_native()

            if not raw_response:
                return "Erro: sem resposta do LLM"

            msg = raw_response.get("message", {})
            content = msg.get("content", "")
            tool_calls_raw = msg.get("tool_calls", [])

            if not tool_calls_raw:
                # Sem tool calls — resposta final
                return content or "(sem conteúdo)"

            # Converter tool_calls para formato interno
            tool_calls = normalize_tool_calls(tool_calls_raw)
            logger.info(f"🔧 Round {round_num + 1}: {len(tool_calls)} tool call(s) [nativo]")

            # Adicionar mensagem do assistente com tool_calls ao histórico
            self.messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls_raw,
            })

            # Executar cada tool
            for tc in tool_calls:
                tool_name = tc.get("tool", "")
                params = tc.get("params", {})

                logger.info(f"  ➜ {tool_name}: {json.dumps(params, ensure_ascii=False)[:100]}")
                result = await self._execute_tool(tool_name, params)

                self.execution_history.append({
                    "tool": tool_name,
                    "params": params,
                    "success": result.get("success", False),
                    "learning": result.get("_learning"),
                })

                # Log resultado
                if result.get("success"):
                    output = result.get("stdout", result.get("content", ""))
                    logger.info(f"  ✅ {tool_name} OK")
                    if self.verbose and output:
                        logger.info(f"     {str(output)[:300]}")
                else:
                    logger.warning(f"  ❌ {tool_name}: {result.get('error', '')[:100]}")

                # Formatar resultado como mensagem role=tool
                result_text = (
                    result.get("stdout") or result.get("content") or
                    result.get("output") or json.dumps(result, ensure_ascii=False)
                )
                tool_msg = format_tool_result_message(tool_name, result)
                self.messages.append(tool_msg)

        return content + "\n\n⚠️ Limite de rounds de ferramentas atingido."

    async def _chat_legacy(self) -> str:
        """Chat loop usando tags <tool_call> (modo legacy)."""

    async def _chat_legacy(self) -> str:
        """Chat loop usando tags <tool_call> (modo legacy)."""
        llm_response = ""
        for round_num in range(MAX_TOOL_ROUNDS):
            # Chamar Ollama /api/chat
            llm_response = await self._call_ollama_legacy()

            if not llm_response:
                return "Erro: sem resposta do LLM"

            # Adicionar resposta ao histórico
            self.messages.append({"role": "assistant", "content": llm_response})

            # Extrair tool calls
            tool_calls = parse_tool_calls(llm_response)

            if not tool_calls:
                # Sem tool calls — resposta final
                return strip_tool_calls(llm_response) or llm_response

            # Executar ferramentas
            logger.info(f"🔧 Round {round_num + 1}: {len(tool_calls)} tool call(s) [legacy]")
            tool_results_text = await self._execute_and_format(tool_calls)

            # Re-injetar resultados como mensagem de contexto
            self.messages.append({"role": "user", "content": tool_results_text})

        # Atingiu limite de rounds
        return strip_tool_calls(llm_response) + "\n\n⚠️ Limite de rounds de ferramentas atingido."

    async def _call_ollama_native(self) -> dict:
        """Chama Ollama /api/chat com tools nativas. Retorna response dict completo."""
        payload = {
            "model": self.model,
            "messages": self.messages,
            "tools": get_ollama_tools(),
            "stream": False,
            "options": {
                "temperature": 0.4,
                "num_predict": 2048,
            },
        }

        # System prompt como primeira mensagem
        if self.system_prompt:
            has_system = any(m.get("role") == "system" for m in self.messages)
            if not has_system:
                self.messages.insert(0, {"role": "system", "content": self.system_prompt})
                payload["messages"] = self.messages

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                if self.verbose:
                    logger.info(f"[Ollama] POST {self.ollama_host}/api/chat — {len(self.messages)} msgs + tools")

                resp = await client.post(
                    f"{self.ollama_host}/api/chat",
                    json=payload,
                )

                if resp.status_code != 200:
                    logger.error(f"Ollama erro {resp.status_code}: {resp.text[:200]}")
                    return {}

                data = resp.json()

                if self.verbose:
                    eval_count = data.get("eval_count", 0)
                    eval_duration = data.get("eval_duration", 0)
                    if eval_duration > 0:
                        tps = eval_count / (eval_duration / 1e9)
                        logger.info(f"[Ollama] {eval_count} tokens, {tps:.1f} tok/s")
                    tool_calls = data.get("message", {}).get("tool_calls", [])
                    if tool_calls:
                        logger.info(f"[Ollama] {len(tool_calls)} tool_call(s) recebidas")

                return data

            except httpx.TimeoutException:
                logger.error("Ollama timeout (120s)")
                return {}
            except Exception as e:
                logger.error(f"Ollama erro: {e}")
                return {}

    async def _call_ollama_legacy(self) -> str:
        """Chama Ollama /api/chat com histórico multi-turn (modo legacy, sem tools param)."""
        payload = {
            "model": self.model,
            "messages": self.messages,
            "stream": False,
            "options": {
                "temperature": 0.4,
                "num_predict": 2048,
            },
        }

        # Adicionar system prompt se for a primeira mensagem
        if self.system_prompt:
            payload["system"] = self.system_prompt

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                if self.verbose:
                    logger.info(f"[Ollama] POST {self.ollama_host}/api/chat — {len(self.messages)} msgs")

                resp = await client.post(
                    f"{self.ollama_host}/api/chat",
                    json=payload,
                )

                if resp.status_code != 200:
                    logger.error(f"Ollama erro {resp.status_code}: {resp.text[:200]}")
                    return ""

                data = resp.json()
                content = data.get("message", {}).get("content", "")

                if self.verbose:
                    eval_count = data.get("eval_count", 0)
                    eval_duration = data.get("eval_duration", 0)
                    if eval_duration > 0:
                        tps = eval_count / (eval_duration / 1e9)
                        logger.info(f"[Ollama] {eval_count} tokens, {tps:.1f} tok/s")

                return content

            except httpx.TimeoutException:
                logger.error("Ollama timeout (120s)")
                return ""
            except Exception as e:
                logger.error(f"Ollama erro: {e}")
                return ""

    async def _execute_and_format(self, tool_calls: list[dict]) -> str:
        """Executa tool calls via API e formata resultados para re-injeção."""
        parts = []

        for call in tool_calls:
            tool_name = call.get("tool", "unknown")
            params = call.get("params", {})

            logger.info(f"  ➜ {tool_name}: {json.dumps(params, ensure_ascii=False)[:100]}")

            result = await self._execute_tool(tool_name, params)

            self.execution_history.append({
                "tool": tool_name,
                "params": params,
                "success": result.get("success", False),
                "learning": result.get("_learning"),
            })

            # Mostrar resultado ao usuário
            if result.get("success"):
                output = result.get("stdout", result.get("content", ""))
                preview = output[:300]
                if len(output) > 300:
                    preview += "\n..."
                logger.info(f"  ✅ {tool_name} OK")
                if self.verbose and preview:
                    logger.info(f"     {preview}")
            else:
                logger.warning(f"  ❌ {tool_name} falhou: {result.get('error', '')[:100]}")

            # Formatar para o LLM
            formatted = get_tool_result_prompt(tool_name, result)
            parts.append(formatted)

        return "\n\n".join(parts)

    async def _execute_tool(self, tool_name: str, params: dict) -> dict:
        """Executa ferramenta via API /llm-tools/execute."""
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    f"{self.api_host}/llm-tools/execute",
                    json={"tool_name": tool_name, "params": params},
                )
                return resp.json()
            except Exception as e:
                return {"success": False, "error": str(e)}

    # ──────────────────────────────────────────────────────────────
    # Sessão interativa
    # ──────────────────────────────────────────────────────────────

    async def interactive_session(self):
        """Sessão interativa com prompt loop."""
        await self.initialize()

        mode = "NATIVO" if self.use_native_tools else "LEGACY (tags)"
        print("\n🤖 LLM Tool Client — Sessão Interativa")
        print(f"   Modelo:    {self.model}")
        print(f"   Ollama:    {self.ollama_host}")
        print(f"   API:       {self.api_host}")
        print(f"   Modo:      {mode}")
        if self.use_native_tools:
            print(f"   Tools:     {len(get_ollama_tools())} definidas (nativo Ollama)")
        else:
            print(f"   System:    {len(self.system_prompt)} chars")
        print("\nComandos: 'sair' | 'stats' | 'limpar' | 'historico' | 'modo'\n")

        while True:
            try:
                user_input = input("Você> ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "sair":
                    print("Até logo!")
                    break

                if user_input.lower() == "stats":
                    await self._show_stats()
                    continue

                if user_input.lower() == "limpar":
                    self.messages.clear()
                    self.execution_history.clear()
                    print("🧹 Histórico limpo.\n")
                    continue

                if user_input.lower() == "historico":
                    self._show_history()
                    continue

                if user_input.lower() == "modo":
                    self.use_native_tools = not self.use_native_tools
                    mode = "NATIVO" if self.use_native_tools else "LEGACY (tags)"
                    print(f"🔄 Modo alterado para: {mode}\n")
                    self.messages.clear()
                    await self.initialize()
                    continue

                print("\n🤖 Processando...\n")
                response = await self.chat(user_input)
                print(f"\n🤖 {response}\n")

            except KeyboardInterrupt:
                print("\n\nSessão interrompida.")
                break
            except Exception as e:
                logger.error(f"Erro: {e}")

    async def _show_stats(self):
        """Mostra estatísticas de aprendizado."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.api_host}/llm-tools/learning-stats")
                stats = resp.json()
                print("\n📊 Estatísticas de Aprendizado:")
                print(f"   Habilitado:     {stats.get('enabled', False)}")
                print(f"   Total decisões: {stats.get('total_decisions', 0)}")
                print(f"   Taxa de sucesso: {stats.get('success_rate', 0):.1%}")
                print(f"   Confiança média: {stats.get('avg_confidence', 0):.2f}")
                print(f"   Padrões recentes: {stats.get('recent_patterns', 0)}")
                patterns = stats.get("patterns_summary", [])
                if patterns:
                    print("   Padrões:")
                    for p in patterns:
                        print(f"     - {p['type']}: ✅{p['success']} ❌{p['failure']}")
                print()
            except Exception as e:
                print(f"Erro ao obter stats: {e}\n")

    def _show_history(self):
        """Mostra histórico de execuções."""
        if not self.execution_history:
            print("📋 Nenhuma execução registrada.\n")
            return
        print(f"\n📋 Histórico ({len(self.execution_history)} execuções):")
        for i, entry in enumerate(self.execution_history, 1):
            icon = "✅" if entry.get("success") else "❌"
            tool = entry.get("tool", "?")
            learning = entry.get("learning", {})
            conf = learning.get("confidence", 0) if learning else 0
            print(f"   {i}. {icon} {tool} (confiança: {conf:.2f})")
        print()


# ──────────────────────────────────────────────────────────────────
# CLI entrypoint
# ──────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="LLM Tool Client — Execute ferramentas via Ollama"
    )
    parser.add_argument("prompt", nargs="?", help="Prompt para o LLM")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo Ollama")
    parser.add_argument("--ollama", default=DEFAULT_OLLAMA, help="URL do Ollama")
    parser.add_argument("--api", default=DEFAULT_API, help="URL da API Eddie")
    parser.add_argument("-i", "--interactive", action="store_true", help="Modo interativo")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument("--stats", action="store_true", help="Mostrar estatísticas de aprendizado")
    parser.add_argument("--legacy", action="store_true", help="Forçar modo legacy (tags <tool_call>)")
    parser.add_argument("--native", action="store_true", default=True, help="Usar tool calling nativo (padrão)")

    args = parser.parse_args()

    # Determinar modo: --legacy desativa native
    use_native = not args.legacy

    client = LLMToolClient(
        ollama_host=args.ollama,
        api_host=args.api,
        model=args.model,
        verbose=args.verbose,
        use_native_tools=use_native,
    )

    if args.stats:
        await client._show_stats()
        return

    if args.interactive or not args.prompt:
        await client.interactive_session()
    else:
        await client.initialize()
        response = await client.chat(args.prompt)
        print(f"\n{response}\n")

        if client.execution_history and args.verbose:
            print("📋 Execuções:")
            print(json.dumps(client.execution_history, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
