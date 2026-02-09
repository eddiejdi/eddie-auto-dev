#!/usr/bin/env python3
"""Testes de integração leves para o `TelegramBot`.

Cenários implementados:
- pergunta sobre "agent bitcoin" (fluxo normal via `ask_ollama`)
- Diretor instrui a prosseguir -> aciona `auto_dev.auto_develop`

O script cria um `TelegramBot` em memória, injeta dublês para API/Bus/AutoDev
e executa `handle_message` com mensagens simuladas, verificando as chamadas
de saída registradas.
"""
import asyncio
import json
import time

from telegram_bot import TelegramBot


class DummyAPI:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None, reply_markup=None):
        self.sent.append((chat_id, text))
        return {"ok": True, "result": {"message_id": int(time.time())}}

    async def send_chat_action(self, chat_id, action="typing"):
        # no-op
        return {"ok": True}

    async def get_me(self):
        return {"ok": True, "result": {"id": 99999, "first_name": "TestBot", "username": "testbot"}}


class DummyBus:
    def __init__(self, respond_with=None, delay=0.1):
        self.subs = []
        self.respond_with = respond_with
        self.delay = delay

    def subscribe(self, cb):
        self.subs.append(cb)

    def unsubscribe(self, cb):
        try:
            self.subs.remove(cb)
        except Exception:
            pass

    def publish(self, mtype, source, target, content, meta=None):
        # If configured to respond, call subscribers with a fake message from DIRETOR
        if self.respond_with and target == 'DIRETOR':
            msg = type('M', (), {})()
            msg.source = 'DIRETOR'
            msg.target = 'assistant'
            msg.content = self.respond_with
            # call subscribers shortly later
            for cb in list(self.subs):
                cb(msg)


async def run_tests():
    results = []

    # --- Test 1: pergunta sobre agent bitcoin, fluxo normal ---
    bot = TelegramBot()
    bot.api = DummyAPI()
    # stub ask_ollama to a deterministic response
    async def fake_ask(prompt, user_id=None, profile=None):
        return "O agent bitcoin está online e executando sincronização." 

    bot.ask_ollama = fake_ask
    # replace bus with no-op to avoid director routing
    import specialized_agents.agent_communication_bus as bus_mod
    real_get = getattr(bus_mod, 'get_communication_bus', None)
    bus_mod.get_communication_bus = lambda: DummyBus(respond_with=None)

    msg = {
        "chat": {"id": 948686300},
        "from": {"id": 111111, "first_name": "Tester"},
        "text": "Qual o status do agent de bitcoin?",
        "message_id": 1,
    }

    await bot.handle_message(msg)
    sent = bot.api.sent[-1][1] if bot.api.sent else ''
    ok1 = "bitcoin" in sent.lower()
    results.append(("agent_bitcoin_status", ok1, sent))

    # --- Test 2: Diretor instrui a prosseguir -> aciona auto_dev ---
    bot2 = TelegramBot()
    bot2.api = DummyAPI()
    # stub ask to something that triggers inability if needed
    async def ask_stub(prompt, user_id=None, profile=None):
        return "Não tenho integração pronta para isso." 

    bot2.ask_ollama = ask_stub
    # dummy auto_dev that returns success
    class AD:
        def __init__(self):
            pass
        def detect_inability(self, resp):
            return True
        async def auto_develop(self, text, director_response):
            return True, "Desenvolvimento concluído: deploy do agent bitcoin realizado." 

    bot2.auto_dev = AD()
    # bus that responds as DIRETOR with instruction to 'implementar'
    bus_mod.get_communication_bus = lambda: DummyBus(respond_with="Por favor, implementar agent bitcoin")

    msg2 = {
        "chat": {"id": 948686300},
        "from": {"id": 222222, "first_name": "Tester2"},
        "text": "Crie e rode o agent de bitcoin por favor",
        "message_id": 2,
    }

    await bot2.handle_message(msg2)
    sent2 = [t for (_, t) in bot2.api.sent]
    ok2 = any("Auto-Desenvolvimento" in s or "Desenvolvimento concluído" in s for s in sent2)
    results.append(("director_auto_dev", ok2, sent2))

    # restore original
    if real_get:
        bus_mod.get_communication_bus = real_get

    # Report
    for name, ok, detail in results:
        print(json.dumps({"test": name, "ok": bool(ok), "detail": detail}))


if __name__ == '__main__':
    asyncio.run(run_tests())
