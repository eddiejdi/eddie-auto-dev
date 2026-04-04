"""Buscador inteligente dual-GPU para documentos locais.

Fluxo principal:
- GPU1 (Ollama :11435): entende a solicitacao do usuario e sugere palavras-chave.
- GPU0 (Ollama :11434): faz OCR/reconhecimento de imagens e interpreta conteudo.

Uso rapido:
    python tools/intelligent_searcher.py "busque meus laudos medicos" --base-dir data
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

LOGGER = logging.getLogger(__name__)


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".log",
    ".html",
    ".xml",
    ".yaml",
    ".yml",
}

DOC_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
} | TEXT_EXTENSIONS


@dataclass
class SearchHit:
    """Representa um arquivo candidato e seu resumo."""

    path: str
    score: int
    content_type: str
    summary: str


class IntelligentSearcher:
    """Busca inteligente com roteamento de carga entre GPU1 e GPU0."""

    def __init__(
        self,
        *,
        host_gpu0: str = "http://192.168.15.2:11434",
        host_gpu1: str = "http://192.168.15.2:11435",
        model_gpu1: str = "qwen3:0.6b",
        model_gpu0_vision: str = "llava:7b",
        request_timeout: int = 120,
    ) -> None:
        """Inicializa hosts/modelos das duas GPUs.

        Args:
            host_gpu0: Endpoint Ollama dedicado a OCR/visao.
            host_gpu1: Endpoint Ollama dedicado a entendimento de solicitacao.
            model_gpu1: Modelo textual para interpretar intencao.
            model_gpu0_vision: Modelo multimodal para OCR/imagem.
            request_timeout: Timeout de chamadas HTTP em segundos.
        """
        self.host_gpu0 = host_gpu0.rstrip("/")
        self.host_gpu1 = host_gpu1.rstrip("/")
        self.model_gpu1 = model_gpu1
        self.model_gpu0_vision = model_gpu0_vision
        self.request_timeout = request_timeout

    async def search(self, user_request: str, base_dir: Path, limit: int = 8) -> dict[str, Any]:
        """Executa pipeline completo de busca e interpretacao.

        Args:
            user_request: Solicitação em linguagem natural.
            base_dir: Diretorio-base para busca de arquivos.
            limit: Quantidade maxima de candidatos processados.

        Returns:
            Dicionario com analise da solicitacao e resultados dos arquivos.
        """
        intent = await self._analyze_request_with_gpu1(user_request)
        keywords = self._normalize_keywords(intent.get("keywords", []), user_request)
        candidates = await self._find_candidates(base_dir=base_dir, keywords=keywords, limit=limit)

        hits: list[SearchHit] = []
        for candidate_path, score in candidates:
            summary = await self._interpret_content_with_gpu0(candidate_path)
            content_type = self._content_type(candidate_path)
            hits.append(
                SearchHit(
                    path=str(candidate_path),
                    score=score,
                    content_type=content_type,
                    summary=summary,
                )
            )

        return {
            "request": user_request,
            "intent": intent,
            "keywords": keywords,
            "results": [hit.__dict__ for hit in hits],
        }

    async def _analyze_request_with_gpu1(self, user_request: str) -> dict[str, Any]:
        """Usa GPU1 para transformar solicitacao em JSON de intencao."""
        prompt = (
            "Interprete a solicitacao do usuario e retorne APENAS JSON valido com chaves: "
            "intent, keywords, file_types, priority. "
            "keywords deve ser lista curta e objetiva. "
            f"Solicitacao: {user_request}"
        )
        response = await self._ollama_generate(
            host=self.host_gpu1,
            model=self.model_gpu1,
            prompt=prompt,
            num_predict=180,
        )
        text_response = str(response.get("response", "")).strip()
        parsed = self._extract_json(text_response)
        if parsed:
            return parsed

        LOGGER.warning("Falha ao parsear JSON da GPU1; aplicando fallback de keywords.")
        return {
            "intent": "document_search",
            "keywords": self._fallback_keywords(user_request),
            "file_types": ["pdf", "jpg", "jpeg", "png", "txt"],
            "priority": "high",
        }

    async def _find_candidates(self, base_dir: Path, keywords: list[str], limit: int) -> list[tuple[Path, int]]:
        """Busca arquivos no disco e pontua por nome/extensao."""
        if not base_dir.exists():
            return []

        all_files = await asyncio.to_thread(lambda: [p for p in base_dir.rglob("*") if p.is_file()])
        scored: list[tuple[Path, int]] = []
        for file_path in all_files:
            suffix = file_path.suffix.lower()
            if suffix not in DOC_EXTENSIONS:
                continue
            score = self._score_file(file_path, keywords)
            if score > 0:
                scored.append((file_path, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    async def _interpret_content_with_gpu0(self, file_path: Path) -> str:
        """Interpreta conteudo usando GPU0 (OCR/visao) ou leitura textual."""
        suffix = file_path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            content = await self._read_text_file(file_path)
            return self._truncate(content, max_chars=1200)

        if suffix == ".pdf":
            text = await self._extract_pdf_text(file_path)
            if text.strip():
                return self._truncate(text, max_chars=1200)
            image_path = await self._pdf_first_page_to_png(file_path)
            if image_path is None:
                return "Nao foi possivel extrair texto/imagem do PDF neste ambiente."
            return await self._vision_summary(image_path)

        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
            return await self._vision_summary(file_path)

        return "Tipo de arquivo nao suportado para interpretacao."

    async def _vision_summary(self, image_path: Path) -> str:
        """Solicita OCR/descricao para imagem via modelo multimodal na GPU0."""
        image_b64 = await asyncio.to_thread(self._encode_base64, image_path)
        prompt = (
            "Extraia o texto visivel (OCR) e descreva o contexto do documento em portugues. "
            "Se houver dados medicos, destaque CID, nome e data quando presentes."
        )
        response = await self._ollama_chat_with_image(
            host=self.host_gpu0,
            model=self.model_gpu0_vision,
            prompt=prompt,
            image_b64=image_b64,
        )
        message = response.get("message", {})
        content = str(message.get("content", "")).strip()
        if not content:
            return "Resposta vazia do modelo de visao na GPU0."
        return self._truncate(content, max_chars=1600)

    async def _read_text_file(self, file_path: Path) -> str:
        """Le arquivo textual de forma assíncrona."""
        try:
            return await asyncio.to_thread(file_path.read_text, encoding="utf-8", errors="ignore")
        except Exception as exc:
            LOGGER.warning("Falha ao ler arquivo textual %s: %s", file_path, exc)
            return ""

    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Tenta extrair texto de PDF com pdftotext."""
        command = ["pdftotext", str(file_path), "-"]
        try:
            output = await asyncio.to_thread(self._run_command_capture, command)
            return output
        except Exception as exc:
            LOGGER.info("pdftotext indisponivel/falhou para %s: %s", file_path, exc)
            return ""

    async def _pdf_first_page_to_png(self, file_path: Path) -> Path | None:
        """Converte primeira pagina do PDF em PNG para OCR por visao."""
        target = Path("/tmp") / f"{file_path.stem}_page1.png"
        command = ["pdftoppm", "-f", "1", "-singlefile", "-png", str(file_path), str(target.with_suffix(""))]
        try:
            await asyncio.to_thread(self._run_command_capture, command)
            if target.exists():
                return target
            return None
        except Exception as exc:
            LOGGER.info("pdftoppm indisponivel/falhou para %s: %s", file_path, exc)
            return None

    async def _ollama_generate(
        self,
        *,
        host: str,
        model: str,
        prompt: str,
        num_predict: int,
    ) -> dict[str, Any]:
        """Chama endpoint /api/generate do Ollama."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "num_predict": num_predict,
            "temperature": 0.1,
        }
        return await asyncio.to_thread(self._post_json, f"{host}/api/generate", payload)

    async def _ollama_chat_with_image(
        self,
        *,
        host: str,
        model: str,
        prompt: str,
        image_b64: str,
    ) -> dict[str, Any]:
        """Chama endpoint /api/chat com imagem embutida (base64)."""
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
        }
        return await asyncio.to_thread(self._post_json, f"{host}/api/chat", payload)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Executa POST JSON com urllib e retorna dicionario."""
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(url=url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=self.request_timeout) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
                return json.loads(raw)
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            LOGGER.warning("HTTPError Ollama %s: %s", url, details[:300])
            return {"error": f"http_error:{exc.code}", "details": details[:300]}
        except Exception as exc:  # pragma: no cover - erro de ambiente
            LOGGER.warning("Erro de chamada Ollama %s: %s", url, exc)
            return {"error": "request_failed", "details": str(exc)}

    def _run_command_capture(self, command: list[str]) -> str:
        """Executa comando shell e retorna stdout."""
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        return completed.stdout

    def _extract_json(self, model_text: str) -> dict[str, Any] | None:
        """Extrai primeiro objeto JSON de um texto do modelo."""
        if not model_text:
            return None
        try:
            return json.loads(model_text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", model_text, flags=re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _fallback_keywords(self, user_request: str) -> list[str]:
        """Gera palavras-chave simples quando LLM nao retorna JSON valido."""
        tokens = re.findall(r"[a-zA-Z0-9_]{3,}", user_request.lower())
        defaults = ["laudo", "medico", "cid", "requerimento", "atestado"]
        keywords: list[str] = []
        for token in tokens + defaults:
            if token not in keywords:
                keywords.append(token)
        return keywords[:12]

    def _normalize_keywords(self, provided: list[Any], user_request: str) -> list[str]:
        """Normaliza keywords e garante fallback minimo."""
        normalized: list[str] = []
        for item in provided:
            text = str(item).strip().lower()
            if len(text) >= 3 and text not in normalized:
                normalized.append(text)
        if normalized:
            return normalized
        return self._fallback_keywords(user_request)

    def _score_file(self, file_path: Path, keywords: list[str]) -> int:
        """Calcula score simples por filename + extensao."""
        name = file_path.name.lower()
        score = 1
        for keyword in keywords:
            if keyword in name:
                score += 8
        if file_path.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}:
            score += 3
        return score

    def _content_type(self, file_path: Path) -> str:
        """Classifica tipo de conteudo em alto nivel."""
        suffix = file_path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            return "text"
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
            return "image"
        return "other"

    def _encode_base64(self, file_path: Path) -> str:
        """Codifica arquivo em base64 para envio no endpoint de visao."""
        data = file_path.read_bytes()
        return base64.b64encode(data).decode("ascii")

    def _truncate(self, text: str, max_chars: int) -> str:
        """Corta texto longo para manter resposta objetiva."""
        if len(text) <= max_chars:
            return text
        return text[:max_chars] + "..."


async def _async_main() -> int:
    """Executa CLI async do buscador inteligente."""
    parser = argparse.ArgumentParser(description="Buscador inteligente dual-GPU para documentos")
    parser.add_argument("request", type=str, help="Solicitacao em linguagem natural")
    parser.add_argument("--base-dir", type=Path, default=Path("."), help="Diretorio-base da busca")
    parser.add_argument("--limit", type=int, default=8, help="Limite de resultados")
    parser.add_argument("--gpu0-host", type=str, default="http://192.168.15.2:11434", help="Host Ollama GPU0")
    parser.add_argument("--gpu1-host", type=str, default="http://192.168.15.2:11435", help="Host Ollama GPU1")
    parser.add_argument("--gpu1-model", type=str, default="qwen3:0.6b", help="Modelo textual GPU1")
    parser.add_argument("--gpu0-vision-model", type=str, default="llava:7b", help="Modelo OCR/visao GPU0")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    searcher = IntelligentSearcher(
        host_gpu0=args.gpu0_host,
        host_gpu1=args.gpu1_host,
        model_gpu1=args.gpu1_model,
        model_gpu0_vision=args.gpu0_vision_model,
    )
    result = await searcher.search(args.request, args.base_dir, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    """Ponto de entrada sync para facilitar execucao por script."""
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
