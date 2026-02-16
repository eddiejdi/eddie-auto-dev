from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import httpx

app = FastAPI(title="Homelab Copilot Agent")


class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 256
    model: Optional[str] = None


@app.post("/generate")
async def generate(req: GenerateRequest):
    ollama_host = os.environ.get("OLLAMA_HOST")
    model = req.model or os.environ.get("OLLAMA_MODEL")

    if ollama_host and model:
        try:
            url = f"{ollama_host}/api/generate"
            payload = {
                "model": model,
                "prompt": req.prompt,
                "stream": False,
                "options": {"num_predict": req.max_tokens}
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                # Ollama retorna {"response": "texto gerado", ...}
                if isinstance(data, dict) and "response" in data:
                    return {"result": data["response"], "raw": data}
                return {"result": str(data), "raw": data}
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Erro ao chamar backend LLM: {exc}")

    # Fallback simples — resposta stub para desenvolvimento/local
    stub = f"[stub] Resposta simulada para: {req.prompt[:200]}"
    return {"result": stub, "raw": None}
