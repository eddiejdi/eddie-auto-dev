#!/usr/bin/env python3
"""X Agent — serviço FastAPI para interação com X.com (Twitter).

Funcionalidades:
  - Postar tweets (texto, com imagem)
  - Ler timeline (home, user)
  - Buscar tweets por query/hashtag
  - Gerenciar interações (like, retweet, follow, unfollow)
  - Ler menções e notificações
  - Obter informações de perfil

Requer credenciais X API v2 armazenadas no Secrets Agent.
Porta padrão: 8515

Métricas Prometheus em /metrics (porta 8002).
"""
import os
import re
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from pydantic import BaseModel, Field
import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("x_agent")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SECRETS_AGENT_URL = os.environ.get("SECRETS_AGENT_URL", "http://localhost:8088")
SECRETS_AGENT_API_KEY = os.environ.get("SECRETS_AGENT_API_KEY", "")
X_API_BASE = "https://api.x.com/2"

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
try:
    from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, start_http_server

    TWEETS_POSTED = Counter("x_agent_tweets_posted_total", "Tweets posted")
    API_CALLS = Counter("x_agent_api_calls_total", "X API calls made", ["endpoint", "method"])
    API_ERRORS = Counter("x_agent_api_errors_total", "X API errors", ["endpoint", "status"])
    RATE_LIMIT_REMAINING = Gauge("x_agent_rate_limit_remaining", "Rate limit remaining", ["endpoint"])
    PROM_ENABLED = True
except ImportError:
    PROM_ENABLED = False
    log.warning("prometheus_client not installed -- metrics disabled")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TweetRequest(BaseModel):
    text: str = Field(..., max_length=280, description="Texto do tweet (max 280 chars)")
    reply_to_id: Optional[str] = Field(None, description="ID do tweet para responder")
    quote_tweet_id: Optional[str] = Field(None, description="ID do tweet para citar")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Query de busca (suporta operadores X)")
    max_results: int = Field(10, ge=1, le=100)


class UserActionRequest(BaseModel):
    username: str = Field(..., description="Username do perfil (sem @)")


class TweetActionRequest(BaseModel):
    tweet_id: str = Field(..., description="ID do tweet")


# ---------------------------------------------------------------------------
# X API Client
# ---------------------------------------------------------------------------

class XClient:
    """Client assíncrono para a API v2 do X.com."""

    def __init__(self):
        self._bearer_token: Optional[str] = None
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._access_token: Optional[str] = None
        self._access_secret: Optional[str] = None
        self._user_id: Optional[str] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._oauth_http: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _fetch_secret(self, name: str, field: str = "password") -> str:
        """Busca credencial no Secrets Agent."""
        if not SECRETS_AGENT_API_KEY:
            raise RuntimeError("SECRETS_AGENT_API_KEY not set")
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                f"{SECRETS_AGENT_URL}/secrets/{name}/{field}",
                headers={"X-API-KEY": SECRETS_AGENT_API_KEY},
            )
            if r.status_code != 200:
                raise RuntimeError(f"Secret fetch failed: {name}/{field} -> {r.status_code}")
            data = r.json()
            return data.get("value", data.get("field_value", ""))

    async def init(self):
        """Inicializa credenciais e HTTP clients."""
        if self._initialized:
            return
        try:
            self._bearer_token = await self._fetch_secret("eddie/x_bearer_token", "password")
            self._api_key = await self._fetch_secret("eddie/x_api_key", "password")
            self._api_secret = await self._fetch_secret("eddie/x_api_secret", "password")
            self._access_token = await self._fetch_secret("eddie/x_access_token", "password")
            self._access_secret = await self._fetch_secret("eddie/x_access_secret", "password")
        except Exception as e:
            log.error("Failed to load X credentials from Secrets Agent: %s", e)
            raise

        # Bearer token client (read operations)
        self._http = httpx.AsyncClient(
            base_url=X_API_BASE,
            headers={"Authorization": f"Bearer {self._bearer_token}"},
            timeout=30,
        )

        # OAuth 1.0a client (write operations — post, like, retweet, follow)
        from authlib.integrations.httpx_client import AsyncOAuth1Client
        self._oauth_http = AsyncOAuth1Client(
            client_id=self._api_key,
            client_secret=self._api_secret,
            token=self._access_token,
            token_secret=self._access_secret,
            base_url=X_API_BASE,
        )

        # Get authenticated user ID
        try:
            me = await self._http.get("/users/me")
            me_data = me.json()
            self._user_id = me_data.get("data", {}).get("id")
            log.info("Authenticated as user_id=%s", self._user_id)
        except Exception as e:
            log.warning("Could not get user_id: %s", e)

        self._initialized = True
        log.info("XClient initialized successfully")

    def _track(self, endpoint: str, method: str, response=None):
        """Track metrics."""
        if not PROM_ENABLED:
            return
        API_CALLS.labels(endpoint=endpoint, method=method).inc()
        if response and response.status_code >= 400:
            API_ERRORS.labels(endpoint=endpoint, status=str(response.status_code)).inc()
        if response:
            remaining = response.headers.get("x-rate-limit-remaining")
            if remaining:
                RATE_LIMIT_REMAINING.labels(endpoint=endpoint).set(int(remaining))

    # ----- Tweet Operations -----

    async def post_tweet(self, text: str, reply_to_id: Optional[str] = None,
                         quote_tweet_id: Optional[str] = None) -> dict:
        """Posta um tweet."""
        await self.init()
        payload = {"text": text}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
        if quote_tweet_id:
            payload["quote_tweet_id"] = quote_tweet_id

        r = await self._oauth_http.post(f"{X_API_BASE}/tweets", json=payload)
        self._track("tweets", "POST", r)
        if r.status_code not in (200, 201):
            raise HTTPException(status_code=r.status_code, detail=r.text)
        if PROM_ENABLED:
            TWEETS_POSTED.inc()
        return r.json()

    async def delete_tweet(self, tweet_id: str) -> dict:
        """Deleta um tweet."""
        await self.init()
        r = await self._oauth_http.delete(f"{X_API_BASE}/tweets/{tweet_id}")
        self._track("tweets", "DELETE", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def get_tweet(self, tweet_id: str) -> dict:
        """Obtém detalhes de um tweet por ID."""
        await self.init()
        params = {
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id,lang",
            "expansions": "author_id",
            "user.fields": "name,username,profile_image_url",
        }
        r = await self._http.get(f"/tweets/{tweet_id}", params=params)
        self._track("tweets", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- Timeline -----

    async def get_home_timeline(self, max_results: int = 10) -> dict:
        """Obtém timeline home do user autenticado."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,author_id,lang",
            "expansions": "author_id",
            "user.fields": "name,username",
        }
        r = await self._http.get(f"/users/{self._user_id}/timelines/reverse_chronological", params=params)
        self._track("timeline_home", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def get_user_tweets(self, username: str, max_results: int = 10) -> dict:
        """Obtém tweets de um usuário por username."""
        await self.init()
        # Resolve username -> user_id
        user = await self._http.get(f"/users/by/username/{username}")
        if user.status_code != 200:
            raise HTTPException(status_code=user.status_code, detail=f"User '{username}' not found")
        user_id = user.json().get("data", {}).get("id")
        if not user_id:
            raise HTTPException(404, f"User '{username}' not found")

        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,lang",
        }
        r = await self._http.get(f"/users/{user_id}/tweets", params=params)
        self._track("user_tweets", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- Search -----

    async def search_tweets(self, query: str, max_results: int = 10) -> dict:
        """Busca tweets recentes por query."""
        await self.init()
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,author_id,lang",
            "expansions": "author_id",
            "user.fields": "name,username",
        }
        r = await self._http.get("/tweets/search/recent", params=params)
        self._track("search", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- Mentions -----

    async def get_mentions(self, max_results: int = 10) -> dict:
        """Obtém menções ao user autenticado."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id",
            "expansions": "author_id",
            "user.fields": "name,username",
        }
        r = await self._http.get(f"/users/{self._user_id}/mentions", params=params)
        self._track("mentions", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- User Profile -----

    async def get_profile(self, username: Optional[str] = None) -> dict:
        """Obtém perfil de um usuário (ou do autenticado)."""
        await self.init()
        if username:
            r = await self._http.get(
                f"/users/by/username/{username}",
                params={"user.fields": "created_at,description,public_metrics,profile_image_url,url,verified"},
            )
        else:
            r = await self._http.get(
                "/users/me",
                params={"user.fields": "created_at,description,public_metrics,profile_image_url,url,verified"},
            )
        self._track("profile", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- Social Actions -----

    async def like_tweet(self, tweet_id: str) -> dict:
        """Dá like em um tweet."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        r = await self._oauth_http.post(
            f"{X_API_BASE}/users/{self._user_id}/likes",
            json={"tweet_id": tweet_id},
        )
        self._track("likes", "POST", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def unlike_tweet(self, tweet_id: str) -> dict:
        """Remove like de um tweet."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        r = await self._oauth_http.delete(
            f"{X_API_BASE}/users/{self._user_id}/likes/{tweet_id}"
        )
        self._track("likes", "DELETE", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def retweet(self, tweet_id: str) -> dict:
        """Retweeta um tweet."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        r = await self._oauth_http.post(
            f"{X_API_BASE}/users/{self._user_id}/retweets",
            json={"tweet_id": tweet_id},
        )
        self._track("retweets", "POST", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def unretweet(self, tweet_id: str) -> dict:
        """Remove retweet."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        r = await self._oauth_http.delete(
            f"{X_API_BASE}/users/{self._user_id}/retweets/{tweet_id}"
        )
        self._track("retweets", "DELETE", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def follow_user(self, username: str) -> dict:
        """Segue um usuário por username."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        # Resolve username
        user = await self._http.get(f"/users/by/username/{username}")
        if user.status_code != 200:
            raise HTTPException(404, f"User '{username}' not found")
        target_id = user.json().get("data", {}).get("id")

        r = await self._oauth_http.post(
            f"{X_API_BASE}/users/{self._user_id}/following",
            json={"target_user_id": target_id},
        )
        self._track("follow", "POST", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def unfollow_user(self, username: str) -> dict:
        """Deixa de seguir um usuário por username."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        # Resolve username
        user = await self._http.get(f"/users/by/username/{username}")
        if user.status_code != 200:
            raise HTTPException(404, f"User '{username}' not found")
        target_id = user.json().get("data", {}).get("id")

        r = await self._oauth_http.delete(
            f"{X_API_BASE}/users/{self._user_id}/following/{target_id}"
        )
        self._track("follow", "DELETE", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def get_followers(self, username: Optional[str] = None, max_results: int = 20) -> dict:
        """Lista seguidores de um usuário."""
        await self.init()
        if username:
            user = await self._http.get(f"/users/by/username/{username}")
            if user.status_code != 200:
                raise HTTPException(404, f"User '{username}' not found")
            uid = user.json().get("data", {}).get("id")
        else:
            uid = self._user_id
        if not uid:
            raise HTTPException(400, "User ID not available")

        params = {
            "max_results": max_results,
            "user.fields": "name,username,description,public_metrics,profile_image_url",
        }
        r = await self._http.get(f"/users/{uid}/followers", params=params)
        self._track("followers", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def get_following(self, username: Optional[str] = None, max_results: int = 20) -> dict:
        """Lista quem um usuário segue."""
        await self.init()
        if username:
            user = await self._http.get(f"/users/by/username/{username}")
            if user.status_code != 200:
                raise HTTPException(404, f"User '{username}' not found")
            uid = user.json().get("data", {}).get("id")
        else:
            uid = self._user_id
        if not uid:
            raise HTTPException(400, "User ID not available")

        params = {
            "max_results": max_results,
            "user.fields": "name,username,description,public_metrics",
        }
        r = await self._http.get(f"/users/{uid}/following", params=params)
        self._track("following", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    # ----- Bookmarks -----

    async def bookmark_tweet(self, tweet_id: str) -> dict:
        """Adiciona tweet aos bookmarks."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        r = await self._oauth_http.post(
            f"{X_API_BASE}/users/{self._user_id}/bookmarks",
            json={"tweet_id": tweet_id},
        )
        self._track("bookmarks", "POST", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def get_bookmarks(self, max_results: int = 10) -> dict:
        """Lista bookmarks do user autenticado."""
        await self.init()
        if not self._user_id:
            raise HTTPException(400, "User ID not available")
        params = {
            "max_results": max_results,
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "name,username",
        }
        r = await self._http.get(f"/users/{self._user_id}/bookmarks", params=params)
        self._track("bookmarks", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def close(self):
        if self._http:
            await self._http.aclose()

    # ----- Video/Media Download -----

    @staticmethod
    def _extract_tweet_id(url_or_id: str) -> str:
        """Extrai tweet ID de um URL do X/Twitter ou retorna o ID direto."""
        # Formatos aceitos:
        #   https://x.com/user/status/1234567890
        #   https://twitter.com/user/status/1234567890
        #   1234567890
        m = re.search(r"(?:x\.com|twitter\.com)/\w+/status/(\d+)", url_or_id)
        if m:
            return m.group(1)
        if url_or_id.isdigit():
            return url_or_id
        raise HTTPException(400, f"Não foi possível extrair tweet ID de: {url_or_id}")

    async def get_video_info(self, url_or_id: str) -> dict:
        """Obtém informações de mídia/vídeo de um tweet."""
        await self.init()
        tweet_id = self._extract_tweet_id(url_or_id)
        params = {
            "tweet.fields": "created_at,public_metrics,author_id,attachments",
            "expansions": "attachments.media_keys,author_id",
            "media.fields": "type,url,preview_image_url,variants,duration_ms,height,width,alt_text",
            "user.fields": "name,username",
        }
        r = await self._http.get(f"/tweets/{tweet_id}", params=params)
        self._track("video_info", "GET", r)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        return r.json()

    async def download_video(self, url_or_id: str, quality: str = "best") -> dict:
        """Baixa vídeo de um tweet. Retorna info + arquivo salvo.

        quality: 'best' | 'worst' | 'medium' ou bitrate específico.
        """
        await self.init()
        tweet_id = self._extract_tweet_id(url_or_id)

        # 1. Buscar mídia do tweet via API v2
        info = await self.get_video_info(tweet_id)
        includes = info.get("includes", {})
        media_list = includes.get("media", [])
        users = includes.get("users", [])
        tweet_data = info.get("data", {})

        # Encontrar vídeo ou GIF
        video_media = None
        for m in media_list:
            if m.get("type") in ("video", "animated_gif"):
                video_media = m
                break

        if not video_media:
            # Tentar via yt-dlp como fallback (funciona sem autenticação)
            return await self._download_via_ytdlp(url_or_id, tweet_id)

        # 2. Selecionar variante de melhor qualidade
        variants = video_media.get("variants", [])
        mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]

        if not mp4_variants:
            return await self._download_via_ytdlp(url_or_id, tweet_id)

        # Ordenar por bitrate (maior = melhor qualidade)
        mp4_variants.sort(key=lambda v: v.get("bit_rate", 0), reverse=True)

        if quality == "worst":
            selected = mp4_variants[-1]
        elif quality == "medium" and len(mp4_variants) > 2:
            selected = mp4_variants[len(mp4_variants) // 2]
        else:  # "best" ou default
            selected = mp4_variants[0]

        video_url = selected["url"]
        bitrate = selected.get("bit_rate", 0)

        # 3. Baixar o vídeo
        download_dir = Path("/tmp/x_agent_downloads")
        download_dir.mkdir(parents=True, exist_ok=True)
        filename = f"x_video_{tweet_id}_{bitrate}.mp4"
        filepath = download_dir / filename

        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as dl:
            resp = await dl.get(video_url)
            if resp.status_code != 200:
                raise HTTPException(502, f"Falha no download do vídeo: HTTP {resp.status_code}")
            filepath.write_bytes(resp.content)

        author = users[0] if users else {}
        return {
            "status": "downloaded",
            "tweet_id": tweet_id,
            "author": author.get("username", "unknown"),
            "type": video_media.get("type"),
            "duration_ms": video_media.get("duration_ms"),
            "width": video_media.get("width"),
            "height": video_media.get("height"),
            "bitrate": bitrate,
            "file": str(filepath),
            "file_size_bytes": filepath.stat().st_size,
            "download_url": f"/download/file/{filename}",
            "all_qualities": [
                {"bitrate": v.get("bit_rate", 0), "url": v.get("url", "")}
                for v in mp4_variants
            ],
        }

    async def _download_via_ytdlp(self, url_or_id: str, tweet_id: str) -> dict:
        """Fallback: usa yt-dlp para baixar vídeo quando a API não retorna variantes."""
        import subprocess

        download_dir = Path("/tmp/x_agent_downloads")
        download_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(download_dir / f"x_video_{tweet_id}.%(ext)s")

        # Montar URL se for só ID
        if url_or_id.isdigit():
            url = f"https://x.com/i/status/{url_or_id}"
        else:
            url = url_or_id

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--no-warnings",
                    "-f", "best[ext=mp4]/best",
                    "-o", output_template,
                    "--print", "after_move:filepath",
                    url,
                ],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise HTTPException(502, f"yt-dlp falhou: {result.stderr[:500]}")

            filepath = Path(result.stdout.strip().split("\n")[-1])
            if not filepath.exists():
                # Tentar encontrar o arquivo
                candidates = list(download_dir.glob(f"x_video_{tweet_id}.*"))
                if candidates:
                    filepath = candidates[0]
                else:
                    raise HTTPException(500, "Arquivo baixado não encontrado")

            return {
                "status": "downloaded",
                "tweet_id": tweet_id,
                "method": "yt-dlp",
                "file": str(filepath),
                "file_size_bytes": filepath.stat().st_size,
                "download_url": f"/download/file/{filepath.name}",
            }
        except FileNotFoundError:
            raise HTTPException(
                501,
                "yt-dlp não instalado. Instale com: pip install yt-dlp ou apt install yt-dlp"
            )


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="X Agent",
    description="Agent para interação com X.com (Twitter) — Eddie Auto-Dev",
    version="1.0.0",
)

x_client = XClient()


@app.on_event("startup")
async def startup():
    if PROM_ENABLED:
        try:
            start_http_server(8002)
            log.info("Prometheus metrics on :8002")
        except OSError:
            log.warning("Prometheus port 8002 already in use")
    log.info("X Agent starting up...")


@app.on_event("shutdown")
async def shutdown():
    await x_client.close()


# ----- Health -----

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "x-agent",
        "initialized": x_client._initialized,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ----- Metrics -----

if PROM_ENABLED:
    @app.get("/metrics")
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ----- Tweet Endpoints -----

@app.post("/tweets")
async def post_tweet(req: TweetRequest):
    """Posta um novo tweet."""
    return await x_client.post_tweet(req.text, req.reply_to_id, req.quote_tweet_id)


@app.delete("/tweets/{tweet_id}")
async def delete_tweet(tweet_id: str):
    """Deleta um tweet."""
    return await x_client.delete_tweet(tweet_id)


@app.get("/tweets/{tweet_id}")
async def get_tweet(tweet_id: str):
    """Obtém detalhes de um tweet."""
    return await x_client.get_tweet(tweet_id)


# ----- Timeline -----

@app.get("/timeline/home")
async def home_timeline(max_results: int = Query(10, ge=1, le=100)):
    """Timeline home do usuário autenticado."""
    return await x_client.get_home_timeline(max_results)


@app.get("/timeline/user/{username}")
async def user_timeline(username: str, max_results: int = Query(10, ge=1, le=100)):
    """Timeline de um usuário específico."""
    return await x_client.get_user_tweets(username, max_results)


# ----- Search -----

@app.post("/search")
async def search_tweets(req: SearchRequest):
    """Busca tweets recentes."""
    return await x_client.search_tweets(req.query, req.max_results)


@app.get("/search")
async def search_tweets_get(q: str = Query(...), max_results: int = Query(10, ge=1, le=100)):
    """Busca tweets recentes (GET)."""
    return await x_client.search_tweets(q, max_results)


# ----- Mentions -----

@app.get("/mentions")
async def get_mentions(max_results: int = Query(10, ge=1, le=100)):
    """Menções ao usuário autenticado."""
    return await x_client.get_mentions(max_results)


# ----- Profile -----

@app.get("/profile")
async def get_my_profile():
    """Perfil do usuário autenticado."""
    return await x_client.get_profile()


@app.get("/profile/{username}")
async def get_user_profile(username: str):
    """Perfil de um usuário por username."""
    return await x_client.get_profile(username)


# ----- Social Actions -----

@app.post("/tweets/{tweet_id}/like")
async def like_tweet(tweet_id: str):
    """Like em um tweet."""
    return await x_client.like_tweet(tweet_id)


@app.delete("/tweets/{tweet_id}/like")
async def unlike_tweet(tweet_id: str):
    """Remove like de um tweet."""
    return await x_client.unlike_tweet(tweet_id)


@app.post("/tweets/{tweet_id}/retweet")
async def retweet(tweet_id: str):
    """Retweet de um tweet."""
    return await x_client.retweet(tweet_id)


@app.delete("/tweets/{tweet_id}/retweet")
async def unretweet(tweet_id: str):
    """Remove retweet."""
    return await x_client.unretweet(tweet_id)


@app.post("/tweets/{tweet_id}/bookmark")
async def bookmark_tweet(tweet_id: str):
    """Adiciona tweet aos bookmarks."""
    return await x_client.bookmark_tweet(tweet_id)


@app.get("/bookmarks")
async def get_bookmarks(max_results: int = Query(10, ge=1, le=100)):
    """Lista bookmarks."""
    return await x_client.get_bookmarks(max_results)


# ----- Follow/Unfollow -----

@app.post("/users/{username}/follow")
async def follow_user(username: str):
    """Seguir um usuário."""
    return await x_client.follow_user(username)


@app.delete("/users/{username}/follow")
async def unfollow_user(username: str):
    """Deixar de seguir um usuário."""
    return await x_client.unfollow_user(username)


@app.get("/users/{username}/followers")
async def get_followers(username: str, max_results: int = Query(20, ge=1, le=100)):
    """Lista seguidores de um usuário."""
    return await x_client.get_followers(username, max_results)


@app.get("/users/{username}/following")
async def get_following(username: str, max_results: int = Query(20, ge=1, le=100)):
    """Lista quem o usuário segue."""
    return await x_client.get_following(username, max_results)


@app.get("/me/followers")
async def my_followers(max_results: int = Query(20, ge=1, le=100)):
    """Meus seguidores."""
    return await x_client.get_followers(max_results=max_results)


@app.get("/me/following")
async def my_following(max_results: int = Query(20, ge=1, le=100)):
    """Quem eu sigo."""
    return await x_client.get_following(max_results=max_results)


# ----- Video Download -----

class VideoDownloadRequest(BaseModel):
    url: str = Field(..., description="Link do post no X (ex: https://x.com/user/status/123) ou tweet ID")
    quality: str = Field("best", description="Qualidade: best, medium, worst")


@app.post("/video/download")
async def download_video(req: VideoDownloadRequest):
    """Baixa vídeo de um post do X. Aceita link completo ou tweet ID."""
    return await x_client.download_video(req.url, req.quality)


@app.get("/video/download")
async def download_video_get(url: str = Query(..., description="Link do post ou tweet ID"),
                              quality: str = Query("best")):
    """Baixa vídeo de um post do X (GET). Aceita link completo ou tweet ID."""
    return await x_client.download_video(url, quality)


@app.get("/video/info")
async def video_info(url: str = Query(..., description="Link do post ou tweet ID")):
    """Obtém informações de mídia/vídeo de um post sem baixar."""
    return await x_client.get_video_info(url)


@app.get("/download/file/{filename}")
async def serve_downloaded_file(filename: str):
    """Serve um arquivo de vídeo já baixado para download."""
    filepath = Path("/tmp/x_agent_downloads") / filename
    if not filepath.exists():
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="video/mp4",
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("X_AGENT_PORT", "8515"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
