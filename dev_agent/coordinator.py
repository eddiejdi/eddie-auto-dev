"""
Agente Coordenador / Líder

Este componente orquestra o `DevAgent` e integra o `WebSearchEngine`
para pesquisar conhecimento adicional quando necessário. O agente tenta
resolver autonomamente e só solicita intervenção humana quando não
consegue encontrar solução após tentativas e pesquisa.
"""
from typing import Optional, Dict, Any, List
import asyncio
import os
import re
from pathlib import Path
import time
import json
import requests
import logging
import sys

# Ajustar path para permitir execução direta
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# Imports que funcionam tanto como módulo quanto execução direta
try:
    from .agent import DevAgent, TaskStatus
    from .llm_client import LLMClient
except ImportError:
    from dev_agent.agent import DevAgent, TaskStatus
    from dev_agent.llm_client import LLMClient

from web_search import create_search_engine

# Telegram helper (optional)
try:
    from telegram_bot import TelegramAPI
    TELEGRAM_AVAILABLE = True
except Exception:
    TELEGRAM_AVAILABLE = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class NoSolutionError(Exception):
    pass


class CoordinatorAgent:
    def __init__(self, dev_agent: Optional[DevAgent] = None, rag_api_url: Optional[str] = None, max_retries: int = 2):
        self.dev = dev_agent or DevAgent()
        self.search = create_search_engine(rag_api_url=rag_api_url)
        self.max_retries = max_retries

    async def decide_and_execute(self, description: str, language: str = "python") -> Dict[str, Any]:
        """
        Tenta resolver a tarefa autonomamente. Se falhar, roda busca web,
        alimenta o RAG e tenta novamente. Só retorna `requires_user: True`
        quando não houver solução após `max_retries` tentativas.
        """
        attempt = 0
        last_errors: List[str] = []
        research_results = None

        while attempt <= self.max_retries:
            attempt += 1
            result = await self.dev.develop(description, language)

            if result.get("success"):
                return {
                    "success": True,
                    "task_id": result.get("task_id"),
                    "code": result.get("code"),
                    "iterations": result.get("iterations"),
                    "errors": result.get("errors", []),
                    "attempts": attempt,
                    "requires_user": False
                }

            # acumula erros e tenta pesquisa quando ainda há tentativas
            last_errors = result.get("errors", []) or ["unknown_error"]

            # Se já tentou pesquisar, não pesquisar novamente neste loop
            if attempt == 1:
                # Realiza pesquisa para incrementar conhecimento
                query = f"{description}\nErros: {last_errors[:3]}"
                research_results = self.search.search_and_extract(query, num_results=3)
                # Tenta salvar no RAG (se configurado)
                try:
                    _ = self.search.save_to_rag(research_results, query)
                except Exception:
                    pass

                # Tenta re-executar com contexto de pesquisa: envia um prompt curto
                formatted = self.search.format_results_for_llm(research_results, query)
                augmented_description = f"{description}\n\nInformacoes encontradas na web:\n{formatted}\n\nUse essas informacoes para tentar resolver o problema sem perguntar ao usuario."

                # Cria uma tarefa adicional com o contexto pesquisado e executa direto
                task = self.dev.create_task(augmented_description, language)
                executed = await self.dev.execute_task(task.id)

                if executed.status == TaskStatus.COMPLETED:
                    return {
                        "success": True,
                        "task_id": executed.id,
                        "code": executed.code,
                        "iterations": executed.iterations,
                        "errors": executed.errors,
                        "attempts": attempt,
                        "requires_user": False,
                        "research_used": True
                    }

            # se não funcionou, e ainda há tentativas, repetir o loop

        # depois das tentativas, não encontrou solução
        # Antes de acionar o usuario, tentar simular a primeira resposta do proprio usuario
        simulated = await self.simulate_user_response(description, last_errors)

        if simulated:
            # tenta novamente com resposta simulada do usuario
            augmented = f"{description}\n\nResposta do usuario (simulada): {simulated}\nUse essa resposta para tentar solucionar o problema sem perguntar ao usuario."
            task = self.dev.create_task(augmented, language)
            executed = await self.dev.execute_task(task.id)
            if executed.status == TaskStatus.COMPLETED:
                return {
                    "success": True,
                    "task_id": executed.id,
                    "code": executed.code,
                    "iterations": executed.iterations,
                    "errors": executed.errors,
                    "attempts": attempt + 1,
                    "requires_user": False,
                    "simulated_user_response": simulated
                }

        # Antes de acionar o usuário, notificar automaticamente (Telegram/WA) e tentar treinar
        # Se erros aparentam ser de terminal, pedir correção a outros agentes primeiro
        if any(self.is_terminal_error(e) for e in last_errors):
                logger.info("Erro de terminal detectado, solicitando correção a agentes especializados")
                try:
                    agent_fix = self.request_agent_fix(last_errors, description)
                    if agent_fix and agent_fix.get("suggestion"):
                        # tentar aplicar sugestão automaticamente
                        aug = f"{description}\n\nSugerido pelo agente de correção:\n{agent_fix.get('suggestion')}"
                        task = self.dev.create_task(aug, language)
                        executed = await self.dev.execute_task(task.id)
                        if executed.status == TaskStatus.COMPLETED:
                            return {
                                "success": True,
                                "task_id": executed.id,
                                "code": executed.code,
                                "iterations": executed.iterations,
                                "errors": executed.errors,
                                "attempts": attempt,
                                "requires_user": False,
                                "agent_fix": agent_fix
                            }
                except Exception:
                    logger.exception("Falha ao solicitar correção a agentes")

        try:
            contact = {"chat_id": os.getenv("ADMIN_CHAT_ID")}
            if os.getenv("TELEGRAM_BOT_TOKEN"):
                channel = "telegram"
            else:
                channel = "whatsapp"
            logger.info("Tentando notificar o usuario automaticamente via %s", channel)
            notify_result = await self.notify_user_and_retrain(description, contact, channel)
        except Exception as e:
            logger.exception("Falha ao notificar usuario: %s", e)
            notify_result = {"notified": False, "reply": None, "retrain_ok": False}

        return {
            "success": False,
            "task_id": None,
            "errors": last_errors,
            "attempts": attempt,
            "requires_user": True,
            "research": [ {"title": r.title, "url": r.url, "snippet": r.snippet} for r in (research_results or []) ],
            "simulated_user_response": simulated,
            "notify_result": notify_result
        }

    def is_terminal_error(self, err: str) -> bool:
        """Heurística simples para detectar se uma mensagem de erro veio de um terminal/container."""
        if not err:
            return False
        e = err.lower()
        # common substrings
        substrings = [
            "no module named",
            "module not found",
            "permission denied",
            "command not found",
            "not found",
            "docker",
            "pip install",
            "timeout",
            "segmentation fault",
            "traceback (most recent call last)",
            "error code",
            "exit code",
            "failed to start",
            "connection refused",
            "connection timed out",
            "permissionerror",
            "modulenotfounderror",
            "importerror",
        ]

        # regex patterns to catch stack traces and exit codes
        regexes = [
            r"traceback \(most recent call last\)",
            r"moduleNotFoundError|modulenotfounderror",
            r"importerror",
            r"exit code \d+",
            r"error:\s+\w+",
        ]

        if any(s in e for s in substrings):
            return True

        for rx in regexes:
            try:
                if re.search(rx, e, re.IGNORECASE):
                    return True
            except Exception:
                continue

        # fallback: long messages with 'Traceback' or multiple lines
        if "traceback" in e or e.count("\n") > 2:
            return True

        return False

    def request_agent_fix(self, errors: List[str], context: str) -> Optional[Dict[str, Any]]:
        """Envia erro/contexto para um serviço de agentes (`AGENTS_API`) pedindo uma correção.

        Espera JSON de retorno com chave `suggestion` contendo texto a ser aplicado.
        """
        agents_api = os.getenv("AGENTS_API")
        if not agents_api:
            logger.info("AGENTS_API não configurado; pulando request_agent_fix")
            return None

        payload = {
            "type": "terminal_error",
            "errors": errors,
            "context": context
        }

        try:
            url = agents_api.rstrip("/") + "/agent/fix"
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code in (200, 201):
                try:
                    return resp.json()
                except Exception:
                    return {"suggestion": resp.text}
            else:
                logger.warning("Agent fix request returned %s", resp.status_code)
        except Exception as e:
            logger.exception("Erro ao contatar AGENTS_API: %s", e)

        return None

    async def simulate_user_response(self, description: str, last_errors: List[str]) -> Optional[str]:
        """
        Usa o modelo configurado `EDDIE_ASSISTANT_MODEL` (ou 'eddie-assistant')
        para simular a primeira resposta do usuário. Retorna texto curto
        ou None se não houver resposta válida.
        """
        model_name = os.getenv("EDDIE_ASSISTANT_MODEL", "eddie-assistant")
        base_url = getattr(self.dev.llm, "base_url", None) or os.getenv("OLLAMA_HOST")
        try:
            client = LLMClient(base_url, model_name)
            prompt = f"Voce e o usuario final. Seja breve. O agente tentou executar: {description}.\nErros recentes: {last_errors[:3]}.\nSe necessario, responda com a informacao que voce forneceria ao agente para que ele continue (uma ou duas frases). Se nao souber, responda 'nao sei'."
            response = await client.generate(prompt, system=None)
            if response and response.success and response.content:
                text = response.content.strip()
                # evitar respostas vazias que apenas contenham codigo
                if len(text) > 0:
                    return text
        except Exception:
            pass
        return None

    async def notify_user_and_retrain(self, description: str, contact: Dict[str, str], channel: str = "telegram", timeout: int = 300) -> Dict[str, Any]:
        """
        Notifica o usuário via `channel` (telegram|whatsapp). Aguarda resposta
        e, se obtida, dispara um retrain usando a resposta como exemplo.

        `contact` pode ter chaves: for telegram: {'chat_id': <int>}; for whatsapp: {'phone': '<number>'}
        Retorna dict com keys: notified, reply, retrain_ok
        """
        notified = False
        reply = None
        retrain_ok = False

        message = (
            f"O agente encontrou um problema ao executar sua tarefa.\n\n"
            f"Tarefa: {description}\n\n"
            "Por favor, responda com a informação necessária ou confirmações.\n"
            "Sua resposta será usada para treinar o assistente automaticamente."
        )

        logger.info("Enviando notificacao ao usuario via %s", channel)

        if channel == "telegram" and TELEGRAM_AVAILABLE:
            try:
                bot = TelegramAPI(os.getenv("TELEGRAM_BOT_TOKEN"))
                chat_id = int(contact.get("chat_id") or os.getenv("ADMIN_CHAT_ID"))

                # Consumir updates atuais para obter offset inicial
                try:
                    existing = await bot.get_updates(timeout=1)
                    if isinstance(existing, dict):
                        results = existing.get("result", [])
                        if results:
                            last_update_id = max(u.get("update_id", 0) for u in results)
                except Exception:
                    last_update_id = None

                await bot.send_message(chat_id, message)
                notified = True
                logger.info("Notificacao enviada via Telegram para %s", chat_id)
            except Exception as e:
                logger.exception("Erro enviando Telegram: %s", e)
                notified = False

        elif channel == "whatsapp":
            try:
                wa_host = os.getenv("WAHA_URL", "http://localhost:5050")
                payload = {"phone": contact.get("phone"), "message": message}
                requests.post(f"{wa_host}/send", json=payload, timeout=10)
                notified = True
                logger.info("Notificacao enviada via WhatsApp para %s", contact.get("phone"))
            except Exception as e:
                logger.exception("Erro enviando WhatsApp: %s", e)
                notified = False

        # Aguardar resposta (poll)
        start = time.time()

        # estado para evitar reprocessar mensagens antigas
        last_msg_ts = 0

        while time.time() - start < timeout:
            if channel == "telegram" and TELEGRAM_AVAILABLE:
                try:
                    bot = TelegramAPI(os.getenv("TELEGRAM_BOT_TOKEN"))
                    # pedir apenas updates novos usando offset
                    offset = (last_update_id + 1) if last_update_id is not None else None
                    updates = await bot.get_updates(offset=offset, timeout=1)
                    for u in (updates.get("result", []) if isinstance(updates, dict) else []):
                        last_update_id = max(last_update_id or 0, u.get("update_id", 0))
                        msg = u.get("message") or u.get("edited_message")
                        if not msg:
                            continue
                        chat = msg.get("chat", {}).get("id")
                        if str(chat) == str(contact.get("chat_id") or os.getenv("ADMIN_CHAT_ID")):
                            text = msg.get("text") or msg.get("caption")
                            if text:
                                reply = text.strip()
                                logger.info("Resposta recebida via Telegram: %s", reply[:200])
                                break
                except Exception:
                    pass

            if channel == "whatsapp":
                try:
                    wa_host = os.getenv("WAHA_URL", "http://localhost:3000")
                    session = os.getenv("WAHA_SESSION", "default")
                    phone = contact.get("phone")
                    if phone:
                        import urllib.parse
                        encoded = urllib.parse.quote(phone, safe='')
                        r = requests.get(f"{wa_host}/api/{session}/chats/{encoded}/messages", timeout=10)
                        if r.status_code == 200:
                            msgs = r.json()
                            # assumir que mensagens têm 'timestamp' ou 'time'
                            for m in reversed(msgs):
                                ts = m.get("timestamp") or m.get("time") or 0
                                try:
                                    ts = int(ts)
                                except Exception:
                                    ts = 0
                                if ts <= last_msg_ts:
                                    continue
                                if m.get("fromMe") is False and m.get("body"):
                                    reply = m.get("body").strip()
                                    logger.info("Resposta recebida via WhatsApp: %s", reply[:200])
                                    last_msg_ts = max(last_msg_ts, ts)
                                    break
                except Exception:
                    pass

            if reply:
                break

            await asyncio.sleep(1)

        if reply:
            try:
                training_example = [{
                    "prompt": description,
                    "completion": reply,
                    "context": "Resposta do usuário enviada por canal direto"
                }]

                try:
                    from extract_whatsapp_train import train_model_with_examples
                    retrain_ok = train_model_with_examples(training_example)
                    logger.info("Retrain executado: %s", retrain_ok)
                except Exception as e:
                    fname = os.getenv("USER_REPLY_TRAIN_FILE", "user_reply_training.jsonl")
                    with open(fname, "a", encoding="utf-8") as f:
                        f.write(json.dumps(training_example[0], ensure_ascii=False) + "\n")
                    logger.exception("Falha ao retrain, salvo para posterior: %s", e)
                    retrain_ok = False
            except Exception as e:
                logger.exception("Erro preparando retrain: %s", e)
                retrain_ok = False

        return {"notified": notified, "reply": reply, "retrain_ok": retrain_ok}


def create_coordinator(dev_agent: Optional[DevAgent] = None, rag_api_url: Optional[str] = None) -> CoordinatorAgent:
    return CoordinatorAgent(dev_agent=dev_agent, rag_api_url=rag_api_url)


def create_coordinator_with_homelab(dev_agent: Optional[DevAgent] = None, rag_api_url: Optional[str] = None, homelab_modelfile: str = "eddie-homelab.Modelfile") -> CoordinatorAgent:
    """Factory que tenta detectar host/model do homelab e configurar o DevAgent.

    Procura por um URL HTTP no `homelab_modelfile` e configura `dev_agent.llm.base_url`.
    Também define o modelo `eddie-assistant` por padrão para simular respostas.
    """
    coord = CoordinatorAgent(dev_agent=dev_agent, rag_api_url=rag_api_url)

    try:
        p = Path(homelab_modelfile)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            m = re.search(r"https?://[0-9.:\/a-zA-Z_-]+", text)
            if m:
                host = m.group(0)
                # atualizar o client base_url
                try:
                    coord.dev.llm.base_url = host
                except Exception:
                    pass

            # definir o modelo padrão do assistente
            os.environ.setdefault("EDDIE_ASSISTANT_MODEL", "eddie-assistant")
    except Exception:
        pass

    return coord


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run CoordinatorAgent quickly")
    parser.add_argument("description", nargs="?", default=None, help="Descrição da tarefa a ser executada")
    parser.add_argument("--rag", help="URL da API RAG", default=None)
    parser.add_argument("--test", action="store_true", help="Executar teste básico")
    parser.add_argument("--smoke", action="store_true", help="Smoke test rápido para CI (não executa LLM)")
    args = parser.parse_args()
    
    if args.test:
        print("✅ CoordinatorAgent carregado com sucesso!")
        print(f"   DevAgent: {DevAgent}")
        print(f"   LLMClient: {LLMClient}")
        print(f"   CoordinatorAgent: {CoordinatorAgent}")
        sys.exit(0)
    
    if args.smoke:
        # Smoke test para CI - valida imports e criação de objetos sem chamar LLM
        print("🔥 Running smoke test...")
        try:
            coordinator = create_coordinator(rag_api_url=args.rag)
            print(f"   ✅ CoordinatorAgent criado")
            print(f"   ✅ DevAgent: {type(coordinator.dev).__name__}")
            print(f"   ✅ SearchEngine: {type(coordinator.search).__name__}")
            print(f"   ✅ LLM URL: {coordinator.dev.llm.base_url}")
            # Valida que pode criar uma task (sem executar)
            task = coordinator.dev.create_task("test task", "python")
            print(f"   ✅ Task criada: {task.id[:8]}...")
            print("🎉 Smoke test passed!")
            sys.exit(0)
        except Exception as e:
            print(f"   ❌ Smoke test failed: {e}")
            sys.exit(1)
    
    if not args.description:
        parser.print_help()
        sys.exit(1)

    coordinator = create_coordinator(rag_api_url=args.rag)

    async def main():
        res = await coordinator.decide_and_execute(args.description)
        print(res)

    asyncio.run(main())
