#!/usr/bin/env python3
"""
APIs Catalog Generator
Scans the repository for HTTP API endpoints (FastAPI/Flask + OpenAPI specs).

Sources:
- Python FastAPI/Starlette decorators (@app.get, @router.post, ...)
- Flask-style @app.route when method is explicit
- OpenAPI / Swagger YAML or JSON (paths)
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

try:
    from tools.taxonomy_meta import (
        context_window,
        detect_status_from_openapi_op,
        detect_status_from_text,
        extract_tables_from_openapi_op,
        parse_taxonomy_annotations,
        resolve_owner_from_path,
    )
except ImportError:  # pragma: no cover
    from taxonomy_meta import (  # type: ignore
        context_window,
        detect_status_from_openapi_op,
        detect_status_from_text,
        extract_tables_from_openapi_op,
        parse_taxonomy_annotations,
        resolve_owner_from_path,
    )

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SKIP_DIR_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "agent_rag",
    "agent_data",
    "analysis_results",
    "philco10b_raspios",
    "android",
    "tmp",
    "backups",
    "artifacts",
    "web-ext-artifacts",
}

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# Path-first patterns (order matters: more specific first).
API_CATEGORIES: dict[str, str] = {
    "health": r"(^/health|/ready|/live|/metrics$|/status|/api/health|/[^/]+/health)",
    "auth": r"(/auth|/login|/logout|/signin|/token|/oauth|/session|/callback)",
    "secrets": r"(/secret|/vault|/bw/|/authentik|/audit/recent)",
    "trading": r"(/order|/position|/trade|/symbol|/account|/tick|/market|/history/deals|/balance$)",
    "agents": r"(/agent|/evoke|/coordinator|/diretor|/messages$|/tool-interceptor)",
    "wiki": r"(/wiki|/page(?!s)|/content)",
    "storage": r"(/storage|/ltfs|/tape|/nextcloud|/file|/share/|/portal|/media/)",
    "cmdb": r"(/cmdb|/inventory|/asset)",
    "banking": r"(/bank|/belvo|/payment|/billing|/cofrinho|/balance)",
    "marketing": r"(/lead|/campaign|/marketing|/diagnostico)",
    "llm": r"(/ollama|/model|/rag|/chat|/generate|/completion|/api/tags|/api/v1/models|/resources$|/huggingface)",
    "monitoring": r"(/alert|/prometheus|/grafana|/debug|/dashboard|/reports?/|/admin/logs|/learning-metrics)",
    "social": r"(/tweet|/timeline|/search|/mention|/profile|/x/|/follow|/bookmark|/video/|/me/)",
    "infra": r"(/api/hosts|/api/info|/api/connect|/api/disconnect|/api/test|/api/quick|/ssh)",
    "platform": r"(/api/v2/(packages|runtimes)|/api/v1/functions|/panel$|/index$)",
    "meetings": r"(/api/jobs|/api/join|/jobs/)",
    "ops": r"(/actions/|/remediation|/operational)",
    "admin": r"(/admin/)",
}

# When path patterns miss, classify by owning service/path prefix.
SERVICE_CATEGORY_HINTS: list[tuple[str, str]] = [
    ("mt5_bridge", "trading"),
    ("btc_trading", "trading"),
    ("clear_trading", "trading"),
    ("x_agent", "social"),
    ("secrets_agent", "secrets"),
    ("banking", "banking"),
    ("belvo", "banking"),
    ("nextcloud", "storage"),
    ("tape_", "storage"),
    ("ltfs", "storage"),
    ("storage_portal", "storage"),
    ("wiki", "wiki"),
    ("meeting_translator", "meetings"),
    ("bn_acervo", "acervo"),
    ("cmdb", "cmdb"),
    ("conube", "ops"),
    ("marketing", "marketing"),
    ("agent_communication", "agents"),
    ("operation_agent", "agents"),
    ("proxy_tool_interceptor", "agents"),
    ("huggingface", "llm"),
    ("code_runner", "platform"),
    ("ssh_agent", "infra"),
    ("whatsapp", "social"),
    ("printshare", "storage"),
    ("github_agent", "infra"),
    ("grafana_learning", "monitoring"),
]

SENSITIVE_API_RE = re.compile(
    r"(secret|token|password|auth|login|oauth|vault|credential|key|session|signin)",
    re.IGNORECASE,
)


class ApisCatalog:
    """Catalog generator for HTTP APIs."""

    def __init__(self, root_path: str = "/workspace/eddie-auto-dev"):
        self.root = Path(root_path)
        self.catalog: dict[str, Any] = {
            "catalogVersion": "1.0.0",
            "domain": "apis",
            "generatedAt": datetime.now().isoformat(),
            "environment": "production",
            "categories": defaultdict(dict),
            "metadata": {
                "totalEndpoints": 0,
                "sourceFiles": [],
                "serviceCount": 0,
            },
        }
        self.endpoints: dict[str, dict[str, Any]] = {}
        self.sources_scanned: list[str] = []

    def _should_skip(self, path: Path) -> bool:
        try:
            parts = set(path.relative_to(self.root).parts)
        except ValueError:
            parts = set(path.parts)
        if parts & SKIP_DIR_PARTS:
            return True
        if "tests" in parts:
            return True
        for p in parts:
            if p.startswith(".venv") or p == "site-packages":
                return True
        # Avoid self-scanning catalog tool source (regex noise)
        if path.name in {"catalog_apis.py", "api_registry_validate.py"}:
            return True
        return False

    def _service_from_path(self, filepath: Path) -> str:
        rel = filepath.relative_to(self.root)
        parts = list(rel.parts)
        if len(parts) == 1:
            return parts[0].replace(".py", "")
        # prefer package-ish prefix
        if parts[0] in {
            "tools",
            "specialized_agents",
            "btc_trading_agent",
            "clear_trading_agent",
            "marketing",
            "mt5_bridge",
            "scripts",
            "site",
            "dashboard",
        }:
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}".replace(".py", "")
        return parts[0]

    def _normalize_path(self, path: str) -> str:
        path = path.strip()
        if not path.startswith("/"):
            path = "/" + path
        # collapse {var:type} and :var and <var> into {var}
        path = re.sub(r"\{([^}:]+)(?::[^}]+)?\}", r"{\1}", path)
        path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
        path = re.sub(r"<([A-Za-z_][A-Za-z0-9_]*)>", r"{\1}", path)
        path = re.sub(r"//+", "/", path)
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        return path

    def _operation_key(self, method: str, path: str) -> str:
        return f"{method.upper()} {self._normalize_path(path)}"

    def _categorize(self, path: str, service: str = "") -> str:
        for category, pattern in API_CATEGORIES.items():
            if re.search(pattern, path, re.IGNORECASE):
                return category
        svc = (service or "").lower()
        for hint, category in SERVICE_CATEGORY_HINTS:
            if hint in svc:
                return category
        # file-stem fallback from service tail
        tail = svc.rsplit("/", 1)[-1]
        for hint, category in SERVICE_CATEGORY_HINTS:
            if hint in tail:
                return category
        return "general"

    def _is_sensitive(self, path: str, category: str) -> bool:
        if category in {"secrets", "auth"}:
            return True
        return bool(SENSITIVE_API_RE.search(path))

    def _add_endpoint(
        self,
        method: str,
        path: str,
        source: str,
        filepath: Path,
        line_num: int,
        summary: str = "",
        tags: list[str] | None = None,
        operation_id: str = "",
        status: str = "active",
        related_tables: list[str] | None = None,
        owner: str | None = None,
        team: str | None = None,
    ) -> None:
        method = method.lower().strip()
        if method not in HTTP_METHODS:
            return
        norm_path = self._normalize_path(path)
        if not norm_path or norm_path == "/":
            # still catalog root if intentional
            pass
        key = self._operation_key(method, norm_path)
        service = self._service_from_path(filepath)
        category = self._categorize(norm_path, service)
        sensitive = self._is_sensitive(norm_path, category)
        rel = (
            filepath.relative_to(self.root)
            if filepath.is_absolute()
            else filepath
        )
        owner_meta = resolve_owner_from_path(rel)
        if owner:
            owner_meta["owner"] = owner
        if team:
            owner_meta["team"] = team
        related_tables = list(related_tables or [])

        if key not in self.endpoints:
            self.endpoints[key] = {
                "operationKey": key,
                "method": method.upper(),
                "path": norm_path,
                "source": source,
                "service": service,
                "summary": summary or "",
                "operationId": operation_id or "",
                "tags": tags or [],
                "category": category,
                "sensitive": sensitive,
                "status": status or "active",
                "owner": owner_meta.get("owner", "unknown"),
                "team": owner_meta.get("team", "unassigned"),
                "relatedTables": related_tables,
                "locations": [],
            }
        else:
            if summary and not self.endpoints[key].get("summary"):
                self.endpoints[key]["summary"] = summary
            if operation_id and not self.endpoints[key].get("operationId"):
                self.endpoints[key]["operationId"] = operation_id
            if tags:
                existing = set(self.endpoints[key].get("tags") or [])
                self.endpoints[key]["tags"] = sorted(existing | set(tags))
            if sensitive:
                self.endpoints[key]["sensitive"] = True
            # Prefer non-general category if a later source is more specific
            if self.endpoints[key].get("category") == "general" and category != "general":
                self.endpoints[key]["category"] = category
            if status and status != "active":
                self.endpoints[key]["status"] = status
            if related_tables:
                existing_t = set(self.endpoints[key].get("relatedTables") or [])
                self.endpoints[key]["relatedTables"] = sorted(
                    existing_t | set(related_tables)
                )
            if owner and self.endpoints[key].get("owner") in {"unknown", None, ""}:
                self.endpoints[key]["owner"] = owner
            if team and self.endpoints[key].get("team") in {"unassigned", None, ""}:
                self.endpoints[key]["team"] = team

        loc = {
            "file": str(filepath.relative_to(self.root)),
            "line": line_num,
            "service": service,
        }
        if loc not in self.endpoints[key]["locations"]:
            self.endpoints[key]["locations"].append(loc)

    # FastAPI / Starlette style
    _DECORATOR_RE = re.compile(
        r"""@(?:(?P<app>[A-Za-z_][A-Za-z0-9_]*)\.)?
            (?P<method>get|post|put|patch|delete|head|options)
            \(\s*['"](?P<path>[^'"]+)['"]
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # APIRouter(prefix="...")
    _ROUTER_PREFIX_RE = re.compile(
        r"""(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*APIRouter\s*\([^)]*
            prefix\s*=\s*['"](?P<prefix>[^'"]+)['"]
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    # Flask @app.route("/x", methods=["GET"])
    _FLASK_ROUTE_RE = re.compile(
        r"""@(?P<app>[A-Za-z_][A-Za-z0-9_]*)\.route\(\s*['"](?P<path>[^'"]+)['"]
            (?:[^)]*methods\s*=\s*\[(?P<methods>[^\]]+)\])?
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def scan_python_routes(self) -> None:
        logger.info("🐍 Scanning Python route decorators...")
        for py_file in self.root.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
            except Exception:
                continue
            if not re.search(
                r"@(?:app|router|[A-Za-z_]+)\.(get|post|put|patch|delete|route)\(",
                content,
                re.IGNORECASE,
            ):
                # still catch bare .get( patterns via decorator re
                if "@" not in content or ".get(" not in content and ".post(" not in content:
                    continue

            rel = str(py_file.relative_to(self.root))
            # router prefixes
            prefixes: dict[str, str] = {}
            for m in self._ROUTER_PREFIX_RE.finditer(content):
                prefixes[m.group("name")] = m.group("prefix")

            found_any = False
            for m in self._DECORATOR_RE.finditer(content):
                app_name = m.group("app") or "app"
                method = m.group("method")
                path = m.group("path")
                if app_name in prefixes:
                    prefix = prefixes[app_name].rstrip("/")
                    path = prefix + (path if path.startswith("/") else "/" + path)
                line_num = content[: m.start()].count("\n") + 1
                # Look at comments around decorator + following function def
                ctx = context_window(content, m.start(), before=250, after=350)
                ann = parse_taxonomy_annotations(ctx)
                status = ann.get("status") or detect_status_from_text(ctx)
                self._add_endpoint(
                    method,
                    path,
                    "fastapi",
                    py_file,
                    line_num,
                    status=status,
                    related_tables=ann.get("tables") or [],
                    owner=ann.get("owner"),
                    team=ann.get("team"),
                )
                found_any = True

            for m in self._FLASK_ROUTE_RE.finditer(content):
                path = m.group("path")
                methods_raw = m.group("methods") or "'GET'"
                methods = re.findall(r"[A-Za-z]+", methods_raw)
                line_num = content[: m.start()].count("\n") + 1
                ctx = context_window(content, m.start(), before=250, after=350)
                ann = parse_taxonomy_annotations(ctx)
                status = ann.get("status") or detect_status_from_text(ctx)
                for method in methods:
                    self._add_endpoint(
                        method,
                        path,
                        "flask",
                        py_file,
                        line_num,
                        status=status,
                        related_tables=ann.get("tables") or [],
                        owner=ann.get("owner"),
                        team=ann.get("team"),
                    )
                    found_any = True

            if found_any:
                logger.info(f"  └─ {rel}")
                self.sources_scanned.append(rel)

    def scan_openapi_specs(self) -> None:
        logger.info("📜 Scanning OpenAPI specs...")
        patterns = ["**/openapi*.yaml", "**/openapi*.yml", "**/openapi*.json", "**/swagger*.yaml"]
        seen: set[Path] = set()
        for pattern in patterns:
            for spec in self.root.glob(pattern):
                if self._should_skip(spec) or spec in seen:
                    continue
                # also rglob deeper under docs/
                seen.add(spec)
                self._parse_openapi_file(spec)
        # deeper search limited roots
        for base in (self.root / "docs", self.root / "specialized_agents", self.root):
            if not base.exists():
                continue
            for spec in base.rglob("openapi*.y*ml"):
                if self._should_skip(spec) or spec in seen:
                    continue
                seen.add(spec)
                self._parse_openapi_file(spec)
            for spec in base.rglob("openapi*.json"):
                if self._should_skip(spec) or spec in seen:
                    continue
                seen.add(spec)
                self._parse_openapi_file(spec)

    def _parse_openapi_file(self, spec: Path) -> None:
        rel = str(spec.relative_to(self.root))
        logger.info(f"  └─ {rel}")
        self.sources_scanned.append(rel)
        try:
            text = spec.read_text(errors="ignore")
            if spec.suffix.lower() == ".json":
                data = json.loads(text)
            else:
                if yaml is None:
                    logger.warning("    PyYAML not available; skipping YAML OpenAPI")
                    return
                data = yaml.safe_load(text)
        except Exception as e:
            logger.error(f"    Error parsing {rel}: {e}")
            return
        if not isinstance(data, dict):
            return
        paths = data.get("paths") or {}
        if not isinstance(paths, dict):
            return
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, op in methods.items():
                if method.lower() not in HTTP_METHODS:
                    continue
                summary = ""
                op_id = ""
                tags: list[str] = []
                status = "active"
                related_tables: list[str] = []
                if isinstance(op, dict):
                    summary = op.get("summary") or op.get("description") or ""
                    op_id = op.get("operationId") or ""
                    tags = op.get("tags") or []
                    status = detect_status_from_openapi_op(op)
                    related_tables = extract_tables_from_openapi_op(op)
                # approximate line number
                line_num = 1
                idx = text.find(f"{path}:")
                if idx >= 0:
                    line_num = text[:idx].count("\n") + 1
                self._add_endpoint(
                    method,
                    path,
                    "openapi",
                    spec,
                    line_num,
                    summary=str(summary)[:200],
                    tags=list(tags) if isinstance(tags, list) else [],
                    operation_id=str(op_id),
                    status=status,
                    related_tables=related_tables,
                )

    def generate_catalog(self) -> dict[str, Any]:
        logger.info("\n" + "=" * 70)
        logger.info("🔍 APIS CATALOG SCANNER")
        logger.info("=" * 70 + "\n")

        self.scan_python_routes()
        self.scan_openapi_specs()

        status_counts: dict[str, int] = {}
        owner_counts: dict[str, int] = {}
        for key, data in sorted(self.endpoints.items()):
            category = data.get("category") or self._categorize(
                data["path"], data.get("service", "")
            )
            data["category"] = category
            data.setdefault("sensitive", self._is_sensitive(data["path"], category))
            data.setdefault("status", "active")
            data.setdefault("owner", "unknown")
            data.setdefault("team", "unassigned")
            data.setdefault("relatedTables", [])
            status_counts[data["status"]] = status_counts.get(data["status"], 0) + 1
            owner_counts[data["owner"]] = owner_counts.get(data["owner"], 0) + 1
            self.catalog["categories"][category][key] = data

        services = {d.get("service") for d in self.endpoints.values() if d.get("service")}
        self.catalog["metadata"]["totalEndpoints"] = len(self.endpoints)
        self.catalog["metadata"]["sourceFiles"] = sorted(set(self.sources_scanned))
        self.catalog["metadata"]["serviceCount"] = len(services)
        self.catalog["metadata"]["statusCounts"] = status_counts
        self.catalog["metadata"]["ownerCounts"] = owner_counts

        logger.info("\n" + "=" * 70)
        logger.info("📊 APIS CATALOG SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Total endpoints: {len(self.endpoints)}")
        logger.info(f"✅ Services: {len(services)}")
        logger.info(f"✅ Source files: {len(set(self.sources_scanned))}")
        for category, entries in sorted(self.catalog["categories"].items()):
            if entries:
                logger.info(f"  • {category}: {len(entries)} endpoints")
        logger.info("=" * 70 + "\n")
        return self.catalog

    def save_catalog(self, output_file: str | None = None) -> Path:
        if output_file is None:
            output_file = self.root / ".apis-catalog" / "catalog.json"
        else:
            output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **self.catalog,
            "categories": {k: v for k, v in self.catalog["categories"].items()},
        }
        output_file.write_text(json.dumps(payload, indent=2, default=str))
        logger.info(f"💾 APIs catalog saved to: {output_file}")
        return output_file

    def generate_reports(self, output_dir: Path | None = None) -> None:
        out = Path(output_dir) if output_dir else self.root / ".apis-catalog"
        out.mkdir(parents=True, exist_ok=True)

        sensitive_n = sum(
            1
            for entries in self.catalog["categories"].values()
            for d in entries.values()
            if d.get("sensitive")
        )
        lines = [
            "# APIs Catalog Report\n",
            f"**Generated:** {self.catalog['generatedAt']}\n",
            f"**Total Endpoints:** {self.catalog['metadata']['totalEndpoints']}\n",
            f"**Services:** {self.catalog['metadata']['serviceCount']}\n",
            f"**Sensitive Endpoints:** {sensitive_n}\n",
            f"**Source Files:** {len(self.catalog['metadata']['sourceFiles'])}\n",
            "---\n\n",
            "## Summary by Category\n\n",
        ]
        for category, entries in sorted(self.catalog["categories"].items()):
            lines.append(f"### {category} ({len(entries)})\n\n")
            for key, data in sorted(entries.items()):
                svc = data.get("service", "?")
                lock = "🔒" if data.get("sensitive") else "✓"
                st = data.get("status", "active")
                owner = data.get("owner", "?")
                rel = data.get("relatedTables") or []
                rel_s = f" tables={','.join(rel)}" if rel else ""
                lines.append(
                    f"- `{key}` {lock} [{st}] owner=`{owner}` — service=`{svc}` "
                    f"source=`{data.get('source')}`{rel_s}\n"
                )
            lines.append("\n")
        lines.append("## Ownership\n\n")
        for owner, count in sorted(
            (self.catalog["metadata"].get("ownerCounts") or {}).items(),
            key=lambda x: -x[1],
        ):
            lines.append(f"- `{owner}`: {count} endpoints\n")
        lines.append("\n## Lifecycle status\n\n")
        for st, count in sorted(
            (self.catalog["metadata"].get("statusCounts") or {}).items()
        ):
            lines.append(f"- `{st}`: {count}\n")
        (out / "CATALOG_REPORT.md").write_text("".join(lines))

        # By service
        by_service: dict[str, list[str]] = defaultdict(list)
        for key, data in self.endpoints.items():
            by_service[data.get("service") or "unknown"].append(key)
        svc_lines = ["# API Endpoints by Service\n\n"]
        for svc, keys in sorted(by_service.items()):
            svc_lines.append(f"## {svc} ({len(keys)})\n\n")
            for key in sorted(keys):
                svc_lines.append(f"- `{key}`\n")
            svc_lines.append("\n")
        (out / "SERVICE_ENDPOINTS.md").write_text("".join(svc_lines))

        csv_lines = [
            "operation_key,method,path,category,service,source,sensitive,status,"
            "owner,team,related_tables,locations"
        ]
        for category, entries in self.catalog["categories"].items():
            for key, data in entries.items():
                locs = ";".join(
                    f"{l['file']}:{l['line']}" for l in data.get("locations", [])
                )
                sens = "yes" if data.get("sensitive") else "no"
                rel = ";".join(data.get("relatedTables") or [])
                csv_lines.append(
                    f'"{key}",{data.get("method")},{data.get("path")},{category},'
                    f'{data.get("service")},{data.get("source")},{sens},'
                    f'{data.get("status", "active")},{data.get("owner", "")},'
                    f'{data.get("team", "")},"{rel}","{locs}"'
                )
        (out / "catalog.csv").write_text("\n".join(csv_lines))
        logger.info(f"✅ API reports written to {out}")


def main() -> None:
    catalog = ApisCatalog()
    catalog.generate_catalog()
    catalog.save_catalog()
    catalog.generate_reports()


if __name__ == "__main__":
    main()
