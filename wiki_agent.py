#!/usr/bin/env python3
"""
Wiki Agent - Publicar páginas Markdown no Wiki.js via Ollama + GraphQL

Configuração via variáveis de ambiente (ver .env.example) ou .env no diretório.
Páginas configuradas via PAGES_FILE (JSON). Nenhum valor hardcoded.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


@dataclass
class Config:
    wiki_api: str = field(default_factory=lambda: _env("WIKI_API"))
    wiki_public: str = field(default_factory=lambda: _env("WIKI_PUBLIC"))
    wiki_token: str = field(default_factory=lambda: _env("WIKI_TOKEN"))
    ollama_api: str = field(default_factory=lambda: _env("WIKI_OLLAMA_API") or _env("OLLAMA_API"))
    ollama_model: str = field(default_factory=lambda: _env("WIKI_OLLAMA_MODEL") or _env("OLLAMA_MODEL", "qwen3:8b"))
    secrets_api: str = field(default_factory=lambda: _env("SECRETS_API"))
    api_key_name: str = field(default_factory=lambda: _env("API_KEY_NAME", "wikijs/api_key"))
    pages_file: str = field(default_factory=lambda: _env("PAGES_FILE", "wiki_pages.json"))
    locale: str = field(default_factory=lambda: _env("WIKI_LOCALE", "pt"))
    timeout: int = field(default_factory=lambda: int(_env("WIKI_TIMEOUT") or _env("TIMEOUT", "60")))
    verbose: bool = field(default_factory=lambda: _env("VERBOSE", "false").lower() == "true")

    def validate(self):
        missing = [k for k, v in [("WIKI_API", self.wiki_api), ("WIKI_PUBLIC", self.wiki_public), ("OLLAMA_API", self.ollama_api)] if not v]
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    def log(self, msg: str):
        if self.verbose:
            print(f"[DEBUG] {msg}")


class SecretsClient:
    def __init__(self, config: Config):
        self.config = config

    def get(self, name: str) -> Optional[str]:
        if not self.config.secrets_api:
            return None
        try:
            r = requests.get(f"{self.config.secrets_api}/{name}", timeout=5)
            if r.status_code == 200:
                return r.json().get("value") or r.text.strip()
        except Exception as e:
            self.config.log(f"SecretsClient error: {e}")
        return None


class OllamaProcessor:
    def __init__(self, config: Config):
        self.config = config

    def process(self, content: str, title: str) -> Dict:
        prompt = f"""Analise este documento Markdown e extraia em JSON:

TÍTULO: {title}

CONTEÚDO:
```markdown
{content[:2000]}
```

Responda APENAS com JSON válido, sem explicações:
{{
  "summary": "resumo executivo de 1-2 linhas",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}"""

        try:
            r = requests.post(
                f"{self.config.ollama_api}/generate",
                json={"model": self.config.ollama_model, "prompt": prompt, "stream": False, "temperature": 0.2},
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            text = r.json().get("response", "")
            start, end = text.find("{"), text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            self.config.log(f"Ollama error: {e}")

        return {"summary": title, "tags": ["auto-generated"]}


class WikiClient:
    def __init__(self, config: Config, token: str):
        self.config = config
        self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    def create_page(self, path: str, title: str, description: str, content: str, tags: List[str]) -> Tuple[bool, str]:
        query = """
        mutation CreatePage($content: String!, $title: String!, $path: String!,
                           $description: String!, $tags: [String]!) {
          pages {
            create(
              content: $content
              title: $title
              path: $path
              description: $description
              editor: "markdown"
              isPublished: true
              isPrivate: false
              locale: "%s"
              tags: $tags
            ) {
              responseResult { succeeded errorCode message }
              page { id path }
            }
          }
        }""" % self.config.locale

        try:
            r = requests.post(
                self.config.wiki_api,
                json={"query": query, "variables": {"content": content, "title": title, "path": path, "description": description, "tags": tags}},
                headers=self.headers,
                timeout=self.config.timeout,
            )
            r.raise_for_status()
            result = r.json()

            if result.get("errors"):
                return False, result["errors"][0].get("message", "GraphQL error")

            res = result.get("data", {}).get("pages", {}).get("create", {})
            rr = res.get("responseResult", {})
            if rr.get("succeeded"):
                page_id = res.get("page", {}).get("id", "?")
                locale_prefix = f"/{self.config.locale}" if self.config.locale != "en" else ""
                return True, f"ID={page_id} → {self.config.wiki_public}{locale_prefix}/{path}"
            return False, rr.get("message", "Unknown error")
        except Exception as e:
            return False, str(e)


class WikiAgent:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.config.validate()

        token = self.config.wiki_token or SecretsClient(self.config).get(self.config.api_key_name) or ""
        if not token:
            raise ValueError("No wiki token: set WIKI_TOKEN or configure SECRETS_API + API_KEY_NAME")

        self.ollama = OllamaProcessor(self.config)
        self.wiki = WikiClient(self.config, token)
        self.created = self.failed = 0

    def process_and_create(self, file_path: str, path: str, title: str) -> bool:
        print(f"\n  {title}")
        print(f"   path: {path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"   FAIL read: {e}")
            self.failed += 1
            return False

        print("   ollama processing...")
        meta = self.ollama.process(content, title)
        summary = meta.get("summary", title)
        tags = meta.get("tags", ["auto-generated"])
        print(f"   summary: {summary[:70]}")
        print(f"   tags: {', '.join(tags[:4])}")

        print("   creating page...")
        ok, msg = self.wiki.create_page(path=path, title=title, description=summary, content=content, tags=tags)
        if ok:
            print(f"   OK {msg}")
            self.created += 1
        else:
            print(f"   FAIL {msg}")
            self.failed += 1
        return ok

    def run(self, pages: List[Dict]) -> Tuple[int, int]:
        print(f"Wiki Agent | model={self.config.ollama_model} | pages={len(pages)}")
        print("=" * 70)
        for p in pages:
            self.process_and_create(file_path=p["file"], path=p["path"], title=p["title"])
        print(f"\n{'=' * 70}")
        print(f"created={self.created} failed={self.failed}")
        return self.created, self.failed


def _load_dotenv(path: str = ".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    _load_dotenv()
    config = Config()

    pages_file = config.pages_file
    if not os.path.exists(pages_file):
        print(f"ERROR: PAGES_FILE not found: {pages_file}")
        return 1

    with open(pages_file, encoding="utf-8") as f:
        pages = json.load(f)

    agent = WikiAgent(config)
    _, failed = agent.run(pages)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
