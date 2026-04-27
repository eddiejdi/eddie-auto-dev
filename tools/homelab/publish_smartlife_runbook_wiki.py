#!/usr/bin/env python3
"""Publish the Smart Life/Tuya runbook to Wiki.js.

Run on the homelab host. The script reads the Wiki.js API token from the
Secrets Agent local vault and reads the markdown file provided with --doc.
It prints only page metadata, never the token.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_APP_DIR = Path("/var/lib/eddie/secrets_agent")
DEFAULT_WIKI_URL = "http://127.0.0.1:3009/graphql"
DEFAULT_TOKEN_SECRET = "authentik/wikijs/api_key"
DEFAULT_TOKEN_FIELD = "password"


class LocalVaultReader:
    def __init__(self, app_dir: Path) -> None:
        self.vault_dir = app_dir / "local_vault"
        passfile = app_dir / "simple_vault_passphrase"
        self.key = hashlib.sha256(passfile.read_text().strip().encode()).digest()

    @staticmethod
    def safe_filename(name: str, field: str) -> str:
        tag = hashlib.sha256(f"{name}:{field}".encode()).hexdigest()[:16]
        return f"{tag}.json"

    def sign(self, data: bytes) -> str:
        return hmac.new(self.key, data, hashlib.sha256).hexdigest()

    def xor_crypt(self, data: bytes) -> bytes:
        stream = hashlib.sha256(self.key + b"stream").digest()
        out = bytearray(len(data))
        for i, _ in enumerate(data):
            ki = i % len(stream)
            if ki == 0 and i > 0:
                stream = hashlib.sha256(self.key + stream).digest()
            out[i] = data[i] ^ stream[ki]
        return bytes(out)

    def get(self, name: str, field: str) -> str:
        path = self.vault_dir / self.safe_filename(name, field)
        envelope = json.loads(path.read_text())
        data = envelope["data"]
        if not hmac.compare_digest(self.sign(data.encode()), envelope["sig"]):
            raise RuntimeError(f"HMAC mismatch for {name}#{field}")
        payload = json.loads(data)
        return self.xor_crypt(base64.b64decode(payload["value"])).decode()


class WikiClient:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token = token

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {"query": query, "variables": variables or {}}
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Wiki.js HTTP {exc.code}: {body[:500]}") from exc
        if result.get("errors"):
            raise RuntimeError(f"Wiki.js GraphQL errors: {result['errors']}")
        return result

    def page_by_path(self, path: str, locale: str) -> dict[str, Any] | None:
        query = """
        query($path: String!, $locale: String!) {
          pages {
            singleByPath(path: $path, locale: $locale) {
              id
              path
              title
              locale
            }
          }
        }
        """
        try:
            result = self.graphql(query, {"path": path, "locale": locale})
        except RuntimeError as exc:
            if "This page does not exist" in str(exc):
                return None
            raise
        return result.get("data", {}).get("pages", {}).get("singleByPath")

    def create_page(
        self,
        *,
        path: str,
        locale: str,
        title: str,
        description: str,
        content: str,
        tags: list[str],
    ) -> dict[str, Any]:
        query = """
        mutation(
          $content: String!
          $description: String!
          $editor: String!
          $isPublished: Boolean!
          $isPrivate: Boolean!
          $locale: String!
          $path: String!
          $tags: [String]!
          $title: String!
        ) {
          pages {
            create(
              content: $content
              description: $description
              editor: $editor
              isPublished: $isPublished
              isPrivate: $isPrivate
              locale: $locale
              path: $path
              tags: $tags
              title: $title
            ) {
              responseResult { succeeded message }
              page { id path title }
            }
          }
        }
        """
        variables = {
            "content": content,
            "description": description,
            "editor": "markdown",
            "isPublished": True,
            "isPrivate": False,
            "locale": locale,
            "path": path,
            "tags": tags,
            "title": title,
        }
        result = self.graphql(query, variables)
        return result["data"]["pages"]["create"]

    def update_page(
        self,
        *,
        page_id: int,
        title: str,
        description: str,
        content: str,
        tags: list[str],
    ) -> dict[str, Any]:
        query = """
        mutation(
          $id: Int!
          $content: String!
          $description: String!
          $isPublished: Boolean!
          $isPrivate: Boolean!
          $tags: [String]!
          $title: String!
        ) {
          pages {
            update(
              id: $id
              content: $content
              description: $description
              isPublished: $isPublished
              isPrivate: $isPrivate
              tags: $tags
              title: $title
            ) {
              responseResult { succeeded message }
              page { id path title }
            }
          }
        }
        """
        variables = {
            "id": page_id,
            "content": content,
            "description": description,
            "isPublished": True,
            "isPrivate": False,
            "tags": tags,
            "title": title,
        }
        result = self.graphql(query, variables)
        return result["data"]["pages"]["update"]


def ensure_success(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = payload.get("responseResult") or {}
    if not response.get("succeeded"):
        raise RuntimeError(f"{action} failed: {response.get('message')}")
    return payload.get("page") or {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", type=Path, required=True)
    parser.add_argument("--path", default="infraestrutura/smartlife-tuya-home-assistant")
    parser.add_argument("--title", default="Smart Life / Tuya via Home Assistant")
    parser.add_argument(
        "--description",
        default="Runbook operacional da integracao Smart Life/Tuya no homelab.",
    )
    parser.add_argument("--locale", default="en")
    parser.add_argument("--wiki-url", default=DEFAULT_WIKI_URL)
    parser.add_argument("--app-dir", type=Path, default=DEFAULT_APP_DIR)
    args = parser.parse_args()

    content = args.doc.read_text(encoding="utf-8")
    token = LocalVaultReader(args.app_dir).get(DEFAULT_TOKEN_SECRET, DEFAULT_TOKEN_FIELD)
    wiki = WikiClient(args.wiki_url, token)
    tags = ["homelab", "home-assistant", "smartlife", "tuya", "runbook"]

    existing = wiki.page_by_path(args.path, args.locale)
    if existing:
        page = ensure_success(
            "update",
            wiki.update_page(
                page_id=int(existing["id"]),
                title=args.title,
                description=args.description,
                content=content,
                tags=tags,
            ),
        )
        action = "updated"
    else:
        page = ensure_success(
            "create",
            wiki.create_page(
                path=args.path,
                locale=args.locale,
                title=args.title,
                description=args.description,
                content=content,
                tags=tags,
            ),
        )
        action = "created"

    print(json.dumps({"action": action, "page": page}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
