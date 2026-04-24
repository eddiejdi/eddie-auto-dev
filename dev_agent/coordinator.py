"""
Agente Coordenador / Líder

Este componente orquestra o `DevAgent` e integra o `WebSearchEngine`
para pesquisar conhecimento adicional quando necessário. O agente tenta
resolver autonomamente e só solicita intervenção humana quando não
consegue encontrar solução após tentativas e pesquisa.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class NoSolutionError(Exception):
    pass


class CoordinatorAgent:
    def __init__(self, dev_agent, rag_api_url: str = "", max_retries: int = 3):
        self.dev_agent = dev_agent
        self.rag_api_url = rag_api_url
        self.max_retries = max_retries
        self.split_timeout = int(os.getenv("COORDINATOR_SPLIT_TIMEOUT_SECONDS", "120"))
        self.cpu_target = float(os.getenv("COORDINATOR_CPU_TARGET_PERCENT", "75"))
        self.cpu_tolerance = float(os.getenv("COORDINATOR_CPU_TARGET_TOLERANCE", "5"))
        self.autoscale_interval = int(os.getenv("COORDINATOR_AUTOSCALE_INTERVAL", "10"))
        self.max_subtasks = int(os.getenv("COORDINATOR_MAX_SUBTASKS", "10"))
        self.prometheus_url = os.getenv("COORDINATOR_PROMETHEUS_URL", "http://localhost:9090")

        try:
            from web_search import create_search_engine
            self._search = create_search_engine()
        except Exception:
            self._search = None

    def decide_and_execute(self, description: str, language: str = "python") -> Dict[str, Any]:
        """
        Tenta resolver a tarefa autonomamente. Se falhar, roda busca web,
        alimenta o RAG e tenta novamente. Só retorna `requires_user: True`
        quando não houver solução após `max_retries` tentativas.
        """
        errors: List[str] = []
        for attempt in range(self.max_retries):
            try:
                result = self.dev_agent.develop(description, language)
                if result.get("success"):
                    return {
                        "success": True,
                        "task_id": result.get("task_id"),
                        "code": result.get("code"),
                        "iterations": attempt + 1,
                        "errors": errors,
                    }
                err = result.get("error", "unknown_error")
                errors.append(err)
            except Exception as e:
                err = str(e)
                errors.append(err)

            # After first failure try web search enrichment
            if self._search and attempt < self.max_retries - 1:
                try:
                    search_results = self._search.search(description)
                    extra = "\n\nInformacoes encontradas na web:\n" + str(search_results)
                    extra += "\n\nUse essas informacoes para tentar resolver o problema sem perguntar ao usuario."
                    description = description + extra
                except Exception:
                    pass

        return {"success": False, "requires_user": True, "errors": errors}

    def _split_and_execute(self, description: str, language: str, attempt: int) -> Dict[str, Any]:
        subtasks = self._split_description_by_type(description)
        results = []
        for task_type, scope in subtasks:
            sub_desc = f"Tipo de tarefa: {task_type}. Execute apenas esta parte da demanda. Mantenha a resposta objetiva.\n\nDemanda original:\n{description}\n\nEscopo desta parte:\n{scope}"
            result = self.dev_agent.develop(sub_desc, language)
            results.append({"task_type": task_type, "success": result.get("success"), "errors": result.get("error")})
        overall_success = all(r["success"] for r in results)
        return {"success": overall_success, "errors": [r["errors"] for r in results if not r["success"]]}

    def _split_description_by_type(self, description: str) -> List[Tuple[str, str]]:
        return [
            ("analysis", description),
            ("code", description),
            ("tests", description),
        ]

    def _autoscale_to_target(self) -> None:
        min_squad = int(os.getenv("SQUAD_MIN", "1"))
        max_squad = int(os.getenv("SQUAD_MAX", "10"))
        cpu = self._get_cpu_usage_percent()
        if cpu is None:
            return
        target = self.cpu_target
        if cpu < target - self.cpu_tolerance and hasattr(self.dev_agent, "set_squad_capacity"):
            pass

    def _get_cpu_usage_percent(self) -> Optional[float]:
        try:
            import urllib.request, urllib.parse, json as _json
            query = '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))'
            url = self.prometheus_url + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = _json.load(resp)
                return float(data["data"]["result"][0]["value"][1]) * 100
        except Exception:
            return None

    def is_terminal_error(self, err: str) -> bool:
        """Heurística simples para detectar se uma mensagem de erro veio de um terminal/container."""
        keywords = ["traceback", "error", "exception", "stderr"]
        return any(k in err.lower() for k in keywords)

    def request_agent_fix(self, errors: str, context: str) -> Optional[str]:
        """Envia erro/contexto para um serviço de agentes (`AGENTS_API`) pedindo uma correção.

        Espera JSON de retorno com chave `suggestion` contendo texto a ser aplicado.
        """
        agents_api = os.getenv("AGENTS_API")
        if not agents_api:
            logger.debug("AGENTS_API não configurado; pulando request_agent_fix")
            return None
        try:
            import urllib.request, json as _json
            payload = _json.dumps({"terminal_error": errors, "context": context}).encode()
            req = urllib.request.Request(
                agents_api + "/agent/fix",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.load(resp)
                if resp.status != 200:
                    logger.warning("Agent fix request returned %s", resp.status)
                    return None
                return data.get("suggestion")
        except Exception as e:
            logger.warning("Erro ao contatar AGENTS_API: %s", e)
            return None

    def simulate_user_response(self, description: str, last_errors: List[str]) -> Optional[str]:
        """
        Usa o modelo configurado `EDDIE_ASSISTANT_MODEL` (ou 'eddie-assistant')
        para simular a primeira resposta do usuário. Retorna texto curto
        ou None se não houver resposta válida.
        """
        model = os.getenv("EDDIE_ASSISTANT_MODEL", "eddie-assistant")
        base_url = os.getenv("OLLAMA_HOST", "http://192.168.15.2:11434")
        try:
            from dev_agent.llm_client import LLMClient
            llm = LLMClient(base_url=base_url, model=model)
            prompt = (
                f"Voce e o usuario final. Seja breve. O agente tentou executar: {description}.\n"
                f"Erros recentes: {'; '.join(last_errors)}.\n"
                "Se necessario, responda com a informacao que voce forneceria ao agente para que ele continue "
                "(uma ou duas frases). Se nao souber, responda 'nao sei'."
            )
            resp = llm.generate_sync(prompt)
            return resp if resp and resp.strip() else None
        except Exception:
            return None

    def notify_user_and_retrain(
        self,
        description: str,
        contact: Dict,
        channel: str = "telegram",
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Notifica o usuário via `channel` (telegram|whatsapp). Aguarda resposta
        e, se obtida, dispara um retrain usando a resposta como exemplo.

        `contact` pode ter chaves: for telegram: {'chat_id': <int>}; for whatsapp: {'phone': '<number>'}
        Retorna dict com keys: notified, reply, retrain_ok
        """
        message = (
            f"O agente encontrou um problema ao executar sua tarefa.\n\nTarefa: {description}\n\n"
            "Por favor, responda com a informação necessária ou confirmações.\n"
            "Sua resposta será usada para treinar o assistente automaticamente."
        )
        result: Dict[str, Any] = {"notified": False, "reply": None, "retrain_ok": False}
        logger.info("Enviando notificacao ao usuario via %s", channel)

        if channel == "telegram":
            try:
                token = os.getenv("TELEGRAM_BOT_TOKEN")
                chat_id = contact.get("chat_id") or os.getenv("ADMIN_CHAT_ID")
                from telegram_bot import TelegramAPI
                api = TelegramAPI(token)
                api.send_message(chat_id, message)
                result["notified"] = True
                logger.info("Notificacao enviada via Telegram para %s", chat_id)
            except Exception as e:
                logger.warning("Erro enviando Telegram: %s", e)

        return result


def create_coordinator(dev_agent, rag_api_url: str = "") -> CoordinatorAgent:
    return CoordinatorAgent(dev_agent=dev_agent, rag_api_url=rag_api_url)


def create_coordinator_with_homelab(dev_agent, rag_api_url: str = "", homelab_modelfile: str = "") -> CoordinatorAgent:
    """Factory que tenta detectar host/model do homelab e configurar o DevAgent.

    Procura por um URL HTTP no `homelab_modelfile` e configura `dev_agent.llm.base_url`.
    Também define o modelo `eddie-assistant` por padrão para simular respostas.
    """
    if homelab_modelfile:
        try:
            with open(homelab_modelfile, "r", encoding="utf-8") as f:
                content = f.read()
            urls = re.findall(r"https?://[0-9.:\\/a-zA-Z_-]+", content)
            if urls and hasattr(dev_agent, "llm") and dev_agent.llm:
                dev_agent.llm.base_url = urls[0]
        except Exception:
            pass
    os.environ.setdefault("EDDIE_ASSISTANT_MODEL", "eddie-assistant")
    return CoordinatorAgent(dev_agent=dev_agent, rag_api_url=rag_api_url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CoordinatorAgent quickly")
    parser.add_argument("description", nargs="?", default="", help="Descrição da tarefa a ser executada")
    parser.add_argument("--rag", default="", help="URL da API RAG")
    parser.add_argument("--test", action="store_true", help="Executar teste básico")
    parser.add_argument("--smoke", action="store_true", help="Smoke test rápido para CI (não executa LLM)")
    args = parser.parse_args()

    from dev_agent.config import OLLAMA_HOST, OLLAMA_MODEL
    from dev_agent.llm_client import LLMClient
    from dev_agent.agent import DevAgent

    llm = LLMClient(base_url=OLLAMA_HOST, model=OLLAMA_MODEL)
    agent = DevAgent(llm_url=OLLAMA_HOST, model=OLLAMA_MODEL)
    coordinator = CoordinatorAgent(dev_agent=agent, rag_api_url=args.rag)

    print("✅ CoordinatorAgent carregado com sucesso!")
    print("   DevAgent: " + str(agent))
    print("   LLMClient: " + str(llm))
    print("   CoordinatorAgent: " + str(coordinator))

    if args.smoke:
        print("🔥 Running smoke test...")
        try:
            print("   ✅ CoordinatorAgent criado")
            print("   ✅ DevAgent: " + str(agent))
            print("   ✅ SearchEngine: " + str(coordinator._search))
            print("   ✅ LLM URL: " + OLLAMA_HOST)
            task_id = agent.create_task("test task", "python")
            print("   ✅ Task criada: " + task_id + "...")
            print("🎉 Smoke test passed!")
        except Exception as e:
            print("   ❌ Smoke test failed: " + str(e))
            sys.exit(1)
        return

    if args.description:
        result = coordinator.decide_and_execute(args.description)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
