from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException


class WikiJsClient:
    """Cliente compartilhado de GraphQL para Wiki.js."""

    def __init__(self, wiki_url: str, token: str, default_locale: str = "pt") -> None:
        self.wiki_url = wiki_url
        self.token = token
        self.default_locale = default_locale

    def effective_locale(self, locale: str | None = None) -> str:
        return locale or self.default_locale

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            self.wiki_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise HTTPException(
                status_code=exc.code,
                detail=f"Wiki.js HTTP {exc.code}: {exc.read().decode()[:300]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Erro de conexão com Wiki.js: {exc}",
            ) from exc

    def list_pages(self, order_by: str = "TITLE") -> list[dict[str, Any]]:
        query = """
        query ListPages($orderBy: PageOrderBy!) {
          pages {
            list(orderBy: $orderBy) {
              id path title locale updatedAt
            }
          }
        }"""
        result = self.graphql(query, {"orderBy": order_by})
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        return result.get("data", {}).get("pages", {}).get("list", [])

    def get_page(self, wiki_path: str, locale: str | None = None) -> dict[str, Any] | None:
        query = """
        query GetPage($path: String!, $locale: String!) {
          pages {
            singleByPath(path: $path, locale: $locale) {
              id path title content updatedAt description
            }
          }
        }"""
        result = self.graphql(
            query,
            {"path": wiki_path, "locale": self.effective_locale(locale)},
        )
        if result.get("errors"):
            return None
        return result.get("data", {}).get("pages", {}).get("singleByPath")

    def create_page(
        self,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        locale: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        mutation = """
        mutation CreatePage(
          $content: String!, $path: String!, $title: String!,
          $locale: String!, $tags: [String]!, $description: String!
        ) {
          pages {
            create(
              content: $content description: $description editor: "markdown"
              isPublished: true isPrivate: false
              locale: $locale path: $path tags: $tags title: $title
            ) {
              responseResult { succeeded errorCode message }
              page { id path }
            }
          }
        }"""
        result = self.graphql(
            mutation,
            {
                "content": content,
                "path": wiki_path,
                "title": title,
                "locale": self.effective_locale(locale),
                "tags": tags or [],
                "description": description,
            },
        )
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        rr = result["data"]["pages"]["create"]["responseResult"]
        if not rr["succeeded"]:
            raise HTTPException(
                status_code=400,
                detail=f"Wiki create falhou ({rr['errorCode']}): {rr['message']}",
            )
        return result["data"]["pages"]["create"]["page"]

    def update_page(
        self,
        page_id: int,
        wiki_path: str,
        title: str,
        content: str,
        tags: list[str] | None = None,
        locale: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        include_tags = tags is not None
        if include_tags:
            mutation = """
            mutation UpdatePage(
              $id: Int!, $content: String!, $path: String!, $title: String!,
              $locale: String!, $description: String!, $tags: [String]!
            ) {
              pages {
                update(
                  id: $id content: $content description: $description editor: "markdown"
                  isPublished: true isPrivate: false
                  locale: $locale path: $path tags: $tags title: $title
                ) {
                  responseResult { succeeded errorCode message }
                  page { id path updatedAt }
                }
              }
            }"""
            variables: dict[str, Any] = {
                "id": page_id,
                "content": content,
                "path": wiki_path,
                "title": title,
                "locale": self.effective_locale(locale),
                "description": description,
                "tags": tags,
            }
        else:
            mutation = """
            mutation UpdatePage(
              $id: Int!, $content: String!, $path: String!, $title: String!,
              $locale: String!, $description: String!
            ) {
              pages {
                update(
                  id: $id content: $content description: $description editor: "markdown"
                  isPublished: true isPrivate: false
                  locale: $locale path: $path title: $title
                ) {
                  responseResult { succeeded errorCode message }
                  page { id path updatedAt }
                }
              }
            }"""
            variables = {
                "id": page_id,
                "content": content,
                "path": wiki_path,
                "title": title,
                "locale": self.effective_locale(locale),
                "description": description,
            }

        result = self.graphql(mutation, variables)
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        rr = result["data"]["pages"]["update"]["responseResult"]
        if not rr["succeeded"]:
            raise HTTPException(
                status_code=400,
                detail=f"Wiki update falhou ({rr['errorCode']}): {rr['message']}",
            )
        return result["data"]["pages"]["update"]["page"]

    def delete_page(self, page_id: int) -> bool:
        mutation = """
        mutation DeletePage($id: Int!) {
          pages {
            delete(id: $id) {
              responseResult { succeeded message }
            }
          }
        }"""
        result = self.graphql(mutation, {"id": page_id})
        if result.get("errors"):
            raise HTTPException(status_code=502, detail=str(result["errors"]))
        return bool(result["data"]["pages"]["delete"]["responseResult"]["succeeded"])

    def archive_page(
        self,
        page_id: int,
        archive_path: str,
        archived_title: str,
        content: str,
        locale: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        return self.update_page(
            page_id=page_id,
            wiki_path=archive_path,
            title=archived_title,
            content=content,
            tags=None,
            locale=locale,
            description=description,
        )
