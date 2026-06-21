from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from types import SimpleNamespace

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - fallback para ambientes mínimos de teste
    class _MissingClientSession:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ModuleNotFoundError("aiohttp is required for runtime HTTP calls")

    class _ClientTimeout:
        def __init__(self, total: int | float | None = None) -> None:
            self.total = total

    aiohttp = SimpleNamespace(  # type: ignore[assignment]
        ClientSession=_MissingClientSession,
        ClientTimeout=_ClientTimeout,
        ClientError=Exception,
    )
    sys.modules.setdefault("aiohttp", aiohttp)
from fastapi import HTTPException
from pydantic import BaseModel, Field

from specialized_agents.config import LLM_CONFIG, LLM_GPU1_CONFIG, get_dynamic_num_ctx
from specialized_agents.wiki_client import WikiJsClient
from specialized_agents.wiki_paths import canonical_wiki_path, normalize_slug


_ROOT_INDEX_TITLES = {
    "home": "RPA4All Wiki",
    "docs": "Docs",
    "homelab": "Homelab",
    "trading": "Trading",
    "operations": "Operations",
    "docs/incidents": "Docs Incidents",
    "docs/agents": "Docs Agents",
}

_ROOT_ORDER = ("docs", "homelab", "trading", "operations", "infraestrutura")
_GENERIC_CLUSTER_SLUGS = {"readme", "index", "home"}
_GENERIC_CLUSTER_TITLES = {"readme", "index", "welcome", "home"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    return int(raw) if raw.isdigit() else default


def _extract_title(path: Path, content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()


def _normalize_title(value: str) -> str:
    return " ".join(value.lower().split())


def _path_aliases(path: str) -> set[str]:
    parts = [part for part in path.strip("/").split("/") if part]
    if not parts:
        return set()

    aliases = {"/".join(parts)}

    deduped: list[str] = []
    for part in parts:
        if not deduped or deduped[-1] != part:
            deduped.append(part)
    aliases.add("/".join(deduped))

    if len(parts) >= 2 and parts[-1] in _GENERIC_CLUSTER_SLUGS:
        aliases.add("/".join(parts[:-1]))

    return {alias for alias in aliases if alias}


@dataclass(slots=True)
class RepoDocument:
    file_path: str
    wiki_path: str
    title: str
    content: str


@dataclass(slots=True)
class ClusterPage:
    id: int
    path: str
    title: str
    locale: str
    updated_at: str


class WikiRefactorRequest(BaseModel):
    mode: str = Field(default="audit", pattern="^(audit|apply)$")
    locale: str = Field(default="pt")
    canonical_source: str = Field(default="repo_and_wiki")
    repo_globs: list[str] = Field(default_factory=lambda: ["docs/**/*.md"])
    rebuild_indexes: bool = True
    archive_duplicates: bool = True
    target_roots: list[str] | None = None
    include_live_orphans: bool = True


class WikiRefactorResponse(BaseModel):
    ok: bool
    run_id: str
    mode: str
    locale: str
    inventory_summary: dict[str, Any]
    duplicate_clusters: list[dict[str, Any]]
    canonical_moves: list[dict[str, Any]]
    archived_pages: list[dict[str, Any]]
    updated_pages: list[dict[str, Any]]
    updated_indexes: list[dict[str, Any]]
    warnings: list[str]
    gpu_usage: dict[str, Any]


class WikiRefactorSkill:
    def __init__(self, wiki_client: WikiJsClient, repo_root: Path | None = None) -> None:
        self.client = wiki_client
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self._page_detail_cache: dict[tuple[str, str], dict[str, Any] | None] = {}
        self.gpu0_url = LLM_CONFIG.get("base_url", "http://192.168.15.2:11434")
        self.gpu1_url = LLM_GPU1_CONFIG.get("base_url", "http://192.168.15.2:11435")
        self.gpu0_model = LLM_CONFIG.get("model", "shared-coder")
        self.gpu1_model = LLM_GPU1_CONFIG.get("model", "qwen3:0.6b")
        self.gpu0_num_ctx_cap = _env_int("WIKI_REFACTOR_GPU0_NUM_CTX_CAP", 4096)
        self.gpu1_num_ctx_cap = _env_int("WIKI_REFACTOR_GPU1_NUM_CTX_CAP", 2048)
        self.max_cluster_pages = _env_int("WIKI_REFACTOR_MAX_CLUSTER_PAGES", 6)
        self.max_source_chars = _env_int("WIKI_REFACTOR_MAX_SOURCE_CHARS", 18000)
        self.archive_root = os.getenv("WIKI_REFACTOR_ARCHIVE_ROOT", "archive/wiki-refactor")
        self._gpu0_sem = asyncio.Semaphore(_env_int("WIKI_REFACTOR_GPU0_CONCURRENCY", 1))
        self._gpu1_sem = asyncio.Semaphore(_env_int("WIKI_REFACTOR_GPU1_CONCURRENCY", 1))
        self._gpu_usage: dict[str, Any] = {
            "gpu0": {"attempted": 0, "completed": 0, "fallbacks": 0},
            "gpu1": {"attempted": 0, "completed": 0, "fallbacks": 0},
            "availability": {},
        }

    async def run(self, req: WikiRefactorRequest) -> WikiRefactorResponse:
        warnings: list[str] = []
        if req.canonical_source != "repo_and_wiki":
            warnings.append("canonical_source diferente de repo_and_wiki caiu para o comportamento padrão da v1")
        if not req.include_live_orphans:
            warnings.append("include_live_orphans=false ainda não altera o inventário na v1; comportamento mantido")
        if req.locale != "pt":
            warnings.append("locale diferente de pt entra em modo somente leitura sem mutacoes")
            if req.mode == "apply":
                req = WikiRefactorRequest(**{**req.model_dump(), "mode": "audit"})
                warnings.append("apply degradado para audit fora do locale pt")

        repo_docs = self._collect_repo_documents(req.repo_globs)
        live_pages = self._collect_live_pages(req.locale)
        if req.target_roots:
            roots = tuple(req.target_roots)
            live_pages = [p for p in live_pages if p["path"] == "home" or p["path"].startswith(roots)]
            repo_docs = {
                path: doc for path, doc in repo_docs.items()
                if path == "home" or path.startswith(roots)
            }

        duplicate_clusters = self._plan_duplicate_clusters(
            live_pages=live_pages,
            repo_docs=repo_docs,
            locale=req.locale,
        )
        index_plans = self._plan_indexes(
            locale=req.locale,
            repo_docs=repo_docs,
            live_pages=live_pages,
            rebuild_indexes=req.rebuild_indexes,
        )

        canonical_moves = [cluster["canonical"] for cluster in duplicate_clusters]
        archived_pages: list[dict[str, Any]] = []
        updated_pages: list[dict[str, Any]] = []
        updated_indexes: list[dict[str, Any]] = []

        inventory_summary = {
            "live_pages": len(live_pages),
            "repo_documents": len(repo_docs),
            "duplicate_clusters": len(duplicate_clusters),
            "title_duplicates": self._count_title_duplicates(live_pages),
            "slug_duplicates": self._count_slug_duplicates(live_pages),
            "root_distribution": self._root_distribution(live_pages),
            "index_targets": [plan["path"] for plan in index_plans],
        }

        if req.mode == "apply":
            apply_warnings = await self._apply_plan(
                req=req,
                repo_docs=repo_docs,
                duplicate_clusters=duplicate_clusters,
                index_plans=index_plans,
                archived_pages=archived_pages,
                updated_pages=updated_pages,
                updated_indexes=updated_indexes,
            )
            warnings.extend(apply_warnings)

        return WikiRefactorResponse(
            ok=True,
            run_id=str(uuid.uuid4()),
            mode=req.mode,
            locale=req.locale,
            inventory_summary=inventory_summary,
            duplicate_clusters=duplicate_clusters,
            canonical_moves=canonical_moves,
            archived_pages=archived_pages,
            updated_pages=updated_pages,
            updated_indexes=updated_indexes,
            warnings=warnings,
            gpu_usage=self._gpu_usage,
        )

    def _collect_repo_documents(self, repo_globs: list[str]) -> dict[str, RepoDocument]:
        docs: dict[str, RepoDocument] = {}
        seen: set[str] = set()
        for pattern in repo_globs:
            for path in sorted(self.repo_root.glob(pattern)):
                if not path.is_file() or path.suffix.lower() != ".md":
                    continue
                if str(path) in seen:
                    continue
                seen.add(str(path))
                content = path.read_text(encoding="utf-8")
                wiki_path = canonical_wiki_path(str(path.relative_to(self.repo_root)), repo_root=self.repo_root)
                docs[wiki_path] = RepoDocument(
                    file_path=str(path.relative_to(self.repo_root)),
                    wiki_path=wiki_path,
                    title=_extract_title(path, content),
                    content=content,
                )
        return docs

    def _collect_live_pages(self, locale: str) -> list[dict[str, Any]]:
        pages = self.client.list_pages()
        result = []
        for page in pages:
            if page.get("locale") != locale:
                continue
            result.append(
                {
                    "id": int(page["id"]),
                    "path": page["path"],
                    "title": page["title"],
                    "locale": page["locale"],
                    "updatedAt": page.get("updatedAt", "") or "",
                }
            )
        return result

    def _plan_duplicate_clusters(
        self,
        live_pages: list[dict[str, Any]],
        repo_docs: dict[str, RepoDocument],
        locale: str,
    ) -> list[dict[str, Any]]:
        pages_by_id = {p["id"]: p for p in live_pages}
        parent: dict[int, int] = {p["id"]: p["id"] for p in live_pages}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        by_slug: dict[str, list[int]] = defaultdict(list)
        by_title: dict[str, list[int]] = defaultdict(list)
        by_repo_slug: dict[str, list[int]] = defaultdict(list)
        by_alias: dict[str, list[int]] = defaultdict(list)

        repo_paths = set(repo_docs)
        repo_slugs = {path.split("/")[-1] for path in repo_paths}
        pages_by_path = {page["path"]: page for page in live_pages}
        for page in live_pages:
            slug = page["path"].split("/")[-1]
            normalized_title = _normalize_title(page["title"])
            parent_path = "/".join(page["path"].split("/")[:-1])
            parent_page = pages_by_path.get(parent_path) if parent_path else None

            if slug not in _GENERIC_CLUSTER_SLUGS:
                by_slug[slug].append(page["id"])
            if (
                normalized_title not in _GENERIC_CLUSTER_TITLES
                and not (
                    slug in _GENERIC_CLUSTER_SLUGS
                    and parent_page
                    and normalized_title == _normalize_title(parent_page["title"])
                    and not self._parent_page_looks_like_index(
                        parent_page=parent_page,
                        repo_docs=repo_docs,
                        locale=locale,
                    )
                )
            ):
                by_title[normalized_title].append(page["id"])
            if slug in repo_slugs and slug not in _GENERIC_CLUSTER_SLUGS:
                by_repo_slug[slug].append(page["id"])
            for alias in _path_aliases(page["path"]):
                if self._should_group_by_alias(
                    page=page,
                    alias=alias,
                    pages_by_path=pages_by_path,
                    repo_docs=repo_docs,
                    locale=locale,
                ):
                    by_alias[alias].append(page["id"])

        for group in list(by_slug.values()) + list(by_title.values()) + list(by_repo_slug.values()) + list(by_alias.values()):
            if len(group) <= 1:
                continue
            base = group[0]
            for other in group[1:]:
                union(base, other)

        clusters: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for page in live_pages:
            clusters[find(page["id"])].append(page)

        plans: list[dict[str, Any]] = []
        for members in clusters.values():
            if len(members) <= 1:
                continue
            canonical_page, repo_doc = self._pick_canonical_page(members, repo_docs)
            duplicates = [m for m in members if m["id"] != canonical_page["id"]]
            if not duplicates:
                continue
            plans.append(
                {
                    "cluster_key": f"{locale}:{canonical_page['path']}",
                    "reason": self._cluster_reason(members, repo_doc),
                    "canonical": {
                        "page_id": canonical_page["id"],
                        "current_path": canonical_page["path"],
                        "target_path": repo_doc.wiki_path if repo_doc else canonical_page["path"],
                        "title": repo_doc.title if repo_doc else canonical_page["title"],
                        "repo_file": repo_doc.file_path if repo_doc else None,
                    },
                    "duplicates": [
                        {
                            "page_id": dup["id"],
                            "path": dup["path"],
                            "title": dup["title"],
                            "archive_path": self._archive_path_for(dup["path"], dup["id"]),
                        }
                        for dup in sorted(duplicates, key=lambda item: item["path"])
                    ],
                }
            )
        plans.sort(key=lambda item: item["canonical"]["target_path"])
        return plans

    def _should_group_by_alias(
        self,
        page: dict[str, Any],
        alias: str,
        pages_by_path: dict[str, dict[str, Any]],
        repo_docs: dict[str, RepoDocument],
        locale: str,
    ) -> bool:
        if alias == page["path"]:
            return True

        slug = page["path"].split("/")[-1]
        if slug not in _GENERIC_CLUSTER_SLUGS:
            return True

        parent_page = pages_by_path.get(alias)
        if not parent_page:
            return False

        return self._parent_page_looks_like_index(
            parent_page=parent_page,
            repo_docs=repo_docs,
            locale=locale,
        )

    def _parent_page_looks_like_index(
        self,
        parent_page: dict[str, Any],
        repo_docs: dict[str, RepoDocument],
        locale: str,
    ) -> bool:
        if parent_page["path"] in repo_docs:
            return False

        detail = self._get_page_detail(parent_page["path"], locale)
        title = _normalize_title(parent_page["title"])
        path_leaf = parent_page["path"].split("/")[-1].replace("-", " ")
        if title in _GENERIC_CLUSTER_TITLES:
            return True

        if detail:
            content = (detail.get("content", "") or "").strip()
            lowered = content.lower()
            if "## navegação" in lowered or "índice regenerado automaticamente pelo wikiagent" in lowered:
                return True
            if len(content) <= 160 and title == _normalize_title(path_leaf):
                return True

        return False

    def _get_page_detail(self, wiki_path: str, locale: str) -> dict[str, Any] | None:
        cache_key = (locale, wiki_path)
        if cache_key not in self._page_detail_cache:
            self._page_detail_cache[cache_key] = self.client.get_page(wiki_path, locale=locale)
        return self._page_detail_cache[cache_key]

    def _pick_canonical_page(
        self,
        members: list[dict[str, Any]],
        repo_docs: dict[str, RepoDocument],
    ) -> tuple[dict[str, Any], RepoDocument | None]:
        repo_doc = None
        path_to_page = {member["path"]: member for member in members}
        for path, candidate_doc in repo_docs.items():
            if path in path_to_page:
                repo_doc = candidate_doc
                return path_to_page[path], repo_doc

        candidate_docs = [doc for doc in repo_docs.values() if doc.wiki_path.split("/")[-1] in {m["path"].split("/")[-1] for m in members}]
        if candidate_docs:
            repo_doc = sorted(candidate_docs, key=lambda doc: (len(doc.wiki_path.split("/")), doc.wiki_path))[0]

        def updated_score(page: dict[str, Any]) -> float:
            updated = page.get("updatedAt", "") or ""
            if not updated:
                return 0.0
            try:
                return datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0

        def rank(page: dict[str, Any]) -> tuple[int, float, int, str]:
            root = page["path"].split("/")[0]
            root_rank = _ROOT_ORDER.index(root) if root in _ROOT_ORDER else 99
            depth = len(page["path"].split("/"))
            return (root_rank, -updated_score(page), depth, page["path"])

        canonical = sorted(members, key=rank)[0]
        return canonical, repo_doc

    def _cluster_reason(self, members: list[dict[str, Any]], repo_doc: RepoDocument | None) -> str:
        slugs = {m["path"].split("/")[-1] for m in members}
        titles = {_normalize_title(m["title"]) for m in members}
        if repo_doc:
            return "repo_canonical_match"
        if len(slugs) == 1:
            return "duplicate_slug"
        if len(titles) == 1:
            return "duplicate_title"
        return "parallel_tree"

    def _archive_path_for(self, old_path: str, page_id: int) -> str:
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        base = "/".join([self.archive_root.strip("/"), date_prefix, old_path.strip("/")])
        return f"{base}-{page_id}"

    def _plan_indexes(
        self,
        locale: str,
        repo_docs: dict[str, RepoDocument],
        live_pages: list[dict[str, Any]],
        rebuild_indexes: bool,
    ) -> list[dict[str, Any]]:
        if not rebuild_indexes or locale != "pt":
            return []
        pages = [p for p in live_pages if not p["path"].startswith(self.archive_root)]
        repo_paths = set(repo_docs)
        combined_paths = sorted(repo_paths | {p["path"] for p in pages})
        targets = ["home", "docs", "homelab", "trading", "operations", "docs/incidents", "docs/agents"]
        plans = []
        for path in targets:
            title = _ROOT_INDEX_TITLES[path]
            body = self._build_index_content(path, title, combined_paths)
            plans.append({"path": path, "title": title, "content": body})
        return plans

    def _build_index_content(self, path: str, title: str, combined_paths: list[str]) -> str:
        lines = [f"# {title}", "", "## Navegação", ""]
        if path == "home":
            for root in ("docs", "homelab", "trading", "operations"):
                children = sorted(p for p in combined_paths if p == root or p.startswith(f"{root}/"))
                if not children:
                    continue
                lines.append(f"### {root.title()}")
                lines.append("")
                for child in children[:15]:
                    lines.append(f"- [{child}](/pt/{child})")
                lines.append("")
        else:
            children = sorted(
                p for p in combined_paths
                if p != path and p.startswith(f"{path}/")
            )
            for child in children:
                lines.append(f"- [{child}](/pt/{child})")
            lines.append("")
        lines.append("## Histórico")
        lines.append("")
        lines.append(f"- {datetime.now().date().isoformat()}: índice regenerado automaticamente pelo WikiAgent.")
        return "\n".join(lines).strip() + "\n"

    async def _apply_plan(
        self,
        req: WikiRefactorRequest,
        repo_docs: dict[str, RepoDocument],
        duplicate_clusters: list[dict[str, Any]],
        index_plans: list[dict[str, Any]],
        archived_pages: list[dict[str, Any]],
        updated_pages: list[dict[str, Any]],
        updated_indexes: list[dict[str, Any]],
    ) -> list[str]:
        warnings: list[str] = []
        availability = await self._gpu_availability()
        self._gpu_usage["availability"] = availability

        for cluster in duplicate_clusters:
            merged, merge_warning = await self._resolve_cluster_content(cluster, repo_docs, availability)
            if merge_warning:
                warnings.append(merge_warning)

            canonical = cluster["canonical"]
            target_path = canonical["target_path"]
            canonical_page = self.client.get_page(canonical["current_path"], locale=req.locale)
            if not canonical_page:
                warnings.append(f"pagina canonica não encontrada ao aplicar cluster {cluster['cluster_key']}")
                continue

            updated = self.client.update_page(
                page_id=canonical_page["id"],
                wiki_path=target_path,
                title=canonical["title"],
                content=merged,
                tags=None,
                locale=req.locale,
            )
            updated_pages.append(
                {
                    "page_id": canonical_page["id"],
                    "from_path": canonical["current_path"],
                    "to_path": updated["path"],
                    "title": canonical["title"],
                }
            )

            if req.archive_duplicates:
                for duplicate in cluster["duplicates"]:
                    duplicate_page = self.client.get_page(duplicate["path"], locale=req.locale)
                    if not duplicate_page:
                        continue
                    archived_content = self._archived_content(duplicate_page["path"], duplicate_page.get("content", ""))
                    archived = self.client.archive_page(
                        page_id=duplicate_page["id"],
                        archive_path=duplicate["archive_path"],
                        archived_title=f"[ARCHIVED] {duplicate_page['title']}",
                        content=archived_content,
                        locale=req.locale,
                    )
                    archived_pages.append(
                        {
                            "page_id": duplicate_page["id"],
                            "from_path": duplicate["path"],
                            "to_path": archived["path"],
                            "title": duplicate_page["title"],
                        }
                    )

        for plan in index_plans:
            page = self.client.get_page(plan["path"], locale=req.locale)
            if page:
                result = self.client.update_page(
                    page_id=page["id"],
                    wiki_path=plan["path"],
                    title=plan["title"],
                    content=plan["content"],
                    tags=None,
                    locale=req.locale,
                )
                updated_indexes.append({"page_id": page["id"], "path": result["path"], "op": "updated"})
            else:
                result = self.client.create_page(
                    wiki_path=plan["path"],
                    title=plan["title"],
                    content=plan["content"],
                    tags=["index", "wiki-refactor"],
                    locale=req.locale,
                )
                updated_indexes.append({"page_id": result["id"], "path": result["path"], "op": "created"})

        return warnings

    async def _resolve_cluster_content(
        self,
        cluster: dict[str, Any],
        repo_docs: dict[str, RepoDocument],
        availability: dict[str, bool],
    ) -> tuple[str, str | None]:
        canonical = cluster["canonical"]
        repo_doc = repo_docs.get(canonical["target_path"])
        base_page = self.client.get_page(canonical["current_path"], locale="pt")
        base_content = repo_doc.content if repo_doc else (base_page.get("content", "") if base_page else "")
        extras: list[tuple[str, str]] = []

        for duplicate in cluster["duplicates"][: self.max_cluster_pages]:
            page = self.client.get_page(duplicate["path"], locale="pt")
            if page and page.get("content", "").strip():
                extras.append((duplicate["path"], page["content"]))

        if not extras:
            return base_content, None

        if availability.get("GPU0"):
            merged = await self._try_gpu_merge(base_content, extras)
            if merged:
                return merged, None
            self._gpu_usage["gpu0"]["fallbacks"] += 1
            return self._fallback_merge(base_content, extras), "merge por GPU0 falhou; aplicado merge determinístico"

        return self._fallback_merge(base_content, extras), "GPU0 indisponível; aplicado merge determinístico"

    def _fallback_merge(self, base_content: str, extras: list[tuple[str, str]]) -> str:
        merged = base_content.rstrip() + "\n"
        seen = {self._normalize_text(base_content)}
        for source_path, content in extras:
            normalized = self._normalize_text(content)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged += (
                "\n## Conteúdo Preservado de Página Duplicada\n\n"
                f"Origem: `{source_path}`\n\n"
                f"{content.strip()}\n"
            )
        return merged.strip() + "\n"

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.split())

    def _archived_content(self, old_path: str, content: str) -> str:
        header = (
            f"> Página arquivada automaticamente pelo wiki refactor.\n"
            f"> Caminho original: `{old_path}`\n\n"
        )
        return header + content

    async def _gpu_availability(self) -> dict[str, bool]:
        return {
            "GPU0": await self._ollama_reachable(self.gpu0_url),
            "GPU1": await self._ollama_reachable(self.gpu1_url),
        }

    async def _ollama_reachable(self, base_url: str) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _try_gpu_merge(self, base_content: str, extras: list[tuple[str, str]]) -> str | None:
        self._gpu_usage["gpu0"]["attempted"] += 1
        prompt = self._merge_prompt(base_content, extras)
        async with self._gpu0_sem:
            try:
                content = await self._ollama_chat(
                    base_url=self.gpu0_url,
                    model=self.gpu0_model,
                    system=(
                        "Você recebe um markdown base e páginas duplicadas. "
                        "Retorne um único markdown canônico, preservando fatos exclusivos sem repetir texto. "
                        "Mantenha título H1, seções H2/H3 e não invente dados."
                    ),
                    user=prompt,
                    num_ctx=min(get_dynamic_num_ctx(self.gpu0_model), self.gpu0_num_ctx_cap),
                    num_predict=1400,
                )
                self._gpu_usage["gpu0"]["completed"] += 1
                return content
            except Exception:
                return None

    def _merge_prompt(self, base_content: str, extras: list[tuple[str, str]]) -> str:
        chunks = [f"=== BASE ===\n{base_content[: self.max_source_chars]}"]
        for source_path, content in extras[: self.max_cluster_pages]:
            chunks.append(f"=== DUPLICATA {source_path} ===\n{content[: self.max_source_chars]}")
        return "\n\n".join(chunks)

    async def _ollama_chat(
        self,
        base_url: str,
        model: str,
        system: str,
        user: str,
        num_ctx: int,
        num_predict: int,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": max(256, num_predict),
                "num_ctx": max(512, num_ctx),
            },
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=90),
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail=f"Ollama retornou {resp.status}")
                data = await resp.json()
        content = data.get("message", {}).get("content", "").strip()
        if not content:
            raise HTTPException(status_code=502, detail="Ollama retornou conteúdo vazio")
        return content

    def _count_title_duplicates(self, live_pages: list[dict[str, Any]]) -> int:
        counter = Counter(_normalize_title(page["title"]) for page in live_pages)
        return sum(1 for _, count in counter.items() if count > 1)

    def _count_slug_duplicates(self, live_pages: list[dict[str, Any]]) -> int:
        counter = Counter(page["path"].split("/")[-1] for page in live_pages)
        return sum(1 for _, count in counter.items() if count > 1)

    def _root_distribution(self, live_pages: list[dict[str, Any]]) -> dict[str, int]:
        counter = Counter(page["path"].split("/")[0] for page in live_pages)
        return dict(sorted(counter.items(), key=lambda item: item[0]))
