"""
title: WebUI Bus Chat Bridge
author: Eddie
version: 1.0.0
description: Função simples para Open WebUI que encaminha mensagens do chat para o Agent Communication Bus (/communication/send) e retorna respostas agregadas.
"""

import os
import httpx
import json
from typing import Optional, Callable, Awaitable, Dict, List
from pydantic import BaseModel


class Pipe:
    class Valves(BaseModel):
        COORDINATOR_API: str = "http://192.168.15.2:8503"
        TIMEOUT: int = 5

    def __init__(self):
        self.valves = self.Valves()
        self.name = "WebUI Bus Chat Bridge"

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        messages = body.get("messages", [])
        if not messages:
            return "Nenhuma mensagem recebida."

        last = messages[-1].get("content", "").strip()
        user_id = __user__.get("id", "webui_user") if __user__ else "webui_user"

        payload = {
            "user_id": user_id,
            "content": last,
            "conversation_id": body.get("conversation_id"),
            "wait_for_responses": True,
            "timeout": int(self.valves.TIMEOUT),
            "clarify_to_director": True
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{self.valves.COORDINATOR_API}/communication/send", json=payload)
                if r.status_code == 200:
                    data = r.json()
                    # Retornar respostas concatenadas de forma legível
                    parts = []
                    for resp in data.get("responses", []):
                        src = resp.get("source", "")
                        content = resp.get("content", "")
                        parts.append(f"[{src}] {content}")
                    if parts:
                        return "\n\n".join(parts)
                    # Se não houver respostas, informar que foi encaminhado ao Diretor
                    if data.get("responses_count", 0) == 0:
                        return "Nenhuma resposta imediata. Mensagem encaminhada ao Diretor para esclarecimento."
                    return json.dumps(data)
                else:
                    return f"Erro ao chamar bridge: HTTP {r.status_code} - {r.text[:200]}"
        except Exception as e:
            return f"❌ Erro: {e}"
