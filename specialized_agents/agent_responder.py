"""
Agent responder for coordinator test broadcasts.
Listens for coordinator messages on the communication bus and
emits a `response` message per active agent so tests can validate flow.
This is intentionally lightweight and only used for testing/validation.
"""
import json
import threading
import time
from typing import Any

from specialized_agents.agent_communication_bus import get_communication_bus, MessageType, log_response, log_error
from specialized_agents import get_agent_manager


import logging

def _handle_message(message: Any):
    logger = logging.getLogger("agent_responder")
    logger.info("received message on bus: %s %s", getattr(message, 'id', None), getattr(message, 'content', '')[:120])
    # Mensagens vindas do WebUI devem ser encaminhadas a um modelo LLM em
    # vez de simplesmente ecoadas. O ecocode usado anteriormente era apenas para
    # testes, mas agora queremos que a instância responda com algum conteúdo
    # inteligente (via Ollama/OpenWebUI). Se o pedido falhar, voltamos ao eco como
    # fallback para não deixar o usuário sem resposta.
    msg_content = getattr(message, 'content', '').strip()
    if msg_content and getattr(message, 'source', '').startswith("webui:"):
        target = message.source
        try:
            # chamar o LLM usando integração existente
            from openwebui_integration import MODEL_PROFILES, OLLAMA_HOST
            import httpx

            prof = MODEL_PROFILES.get("assistant", {})
            model_name = prof.get("model")
            system_prompt = prof.get("system_prompt")
            # fazer requisição síncrona simples
            payload = {
                "model": model_name,
                "prompt": msg_content,
                "system": system_prompt,
                "temperature": prof.get("temperature", 0.7),
                "options": {"max_new_tokens": prof.get("max_tokens", 1024)}
            }
            resp = httpx.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("response", "").strip()
            else:
                answer = ""
        except Exception as e:
            logger.exception("LLM call failed")
            answer = ""

        if not answer:
            # fallback para eco
            answer = msg_content

        log_response("assistant", target, answer)
        logger.info(f"published LLM response to {target}: {answer[:120]}")
        return
    try:
        if message.message_type != MessageType.COORDINATOR:
            return

        # try to parse content as JSON to detect op
        op = None
        try:
            payload = json.loads(message.content)
            op = payload.get("op")
        except Exception:
            # content may be plain text
            if "please_respond" in message.content or "por favor respondam" in message.content:
                op = "please_respond"

        if op != "please_respond":
            return

        # Spawn a thread to avoid blocking bus callbacks
        def respond():
            try:
                mgr = get_agent_manager()
                # give a small pause so active agents may initialize
                time.sleep(0.2)
                active = mgr.list_active_agents()

                logger.info("agent_responder found %d active agents", len(active) if active else 0)

                # If no active agents, publish a helpful system response so callers know
                if not active:
                    log_response("assistant", "coordinator", "Nenhum agente ativo disponível para responder ao broadcast")
                    logger.info("published fallback response: no active agents")
                    return

                for a in active:
                    try:
                        agent_name = a.get("name") or a.get("language")
                        content = f"{agent_name} resposta automática ao broadcast: {message.content[:200]}"
                        log_response(agent_name, "coordinator", content)
                        logger.info("published response from agent %s", agent_name)
                    except Exception as e:
                        # Log the exception to the bus for debugging
                        try:
                            log_error("agent_responder", f"Erro ao responder pelo agente {a}: {e}")
                        except Exception:
                            pass
            except Exception as e:
                try:
                    log_error("agent_responder", f"Erro no respond handler: {e}")
                except Exception:
                    pass

        t = threading.Thread(target=respond, daemon=True)
        t.start()
    except Exception as e:
        try:
            log_error("agent_responder", f"_handle_message exception: {e}")
        except Exception:
            pass


def start_responder():
    import logging
    logger = logging.getLogger("agent_responder")
    bus = get_communication_bus()
    bus.subscribe(_handle_message)
    # announce subscription for observability in tests
    try:
        log_response("agent_responder", "coordinator", "agent_responder subscribed to coordinator broadcasts")
    except Exception:
        pass
    logger.info("agent_responder subscribed; subscribers_count=%d", len(bus.subscribers))
    return True


__all__ = ["start_responder"]
