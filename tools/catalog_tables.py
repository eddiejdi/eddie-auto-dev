#!/usr/bin/env python3
"""
Tables Catalog Generator
Scans the repository for database table definitions (SQL + Python DDL).

Sources:
- *.sql files (CREATE TABLE, CREATE INDEX, FOREIGN KEY)
- Python files with CREATE TABLE IF NOT EXISTS / SQLAlchemy-style DDL strings
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from tools.taxonomy_meta import (
        context_window,
        detect_status_from_text,
        parse_taxonomy_annotations,
        resolve_owner_from_path,
    )
except ImportError:  # pragma: no cover
    from taxonomy_meta import (  # type: ignore
        context_window,
        detect_status_from_text,
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
}

# Infer schema from path when DDL does not declare one.
PATH_SCHEMA_HINTS: List[Tuple[str, str]] = [
    ("btc_trading_agent", "btc"),
    ("clear_trading_agent", "clear"),
    ("marketing", "marketing"),
    ("grafana/exporters", "btc"),
    ("tools/migrations", "public"),
    ("tools/agent_ipc", "public"),
    ("content_automation", "public"),
    ("storage_portal", "public"),
    ("specialized_agents", "public"),
]

TABLE_CATEGORIES: Dict[str, str] = {
    "trading": r"(trade|candle|decision|position|order|market_state|learning_reward|performance|conversion|llm_call|llm_log|ai_plan|profile_alloc|ai_trade|exchange_|ledger)",
    "governance": r"(agent_action|schema_migration|agent_audit|governance)",
    "ipc": r"(agent_ipc|bus_message|communication)",
    "marketing": r"(lead|campaign|email_log|x_posts|daily_metric)",
    "portal": r"(contract|portal_user|api_token|payment)",
    "home": r"(home_device|home_command|home_device_history)",
    "content": r"(content_queue|conversation|message|snapshot)",
    "sentiment": r"(news_sentiment|training_sample|sentiment_calibrat|llm_shadow)",
    "identity": r"(user_management|users)",
    "ops": r"(remediation|operational|job_queue)",
}

SENSITIVE_COLUMN_RE = re.compile(
    r"(password|secret|token|api_key|private|credential|ssn|cpf|seed|auth)",
    re.IGNORECASE,
)


class TablesCatalog:
    """Catalog generator for database tables."""

    def __init__(self, root_path: str = "/workspace/eddie-auto-dev"):
        self.root = Path(root_path)
        self.catalog: Dict[str, Any] = {
            "catalogVersion": "1.0.0",
            "domain": "tables",
            "generatedAt": datetime.now().isoformat(),
            "environment": "production",
            "categories": defaultdict(dict),
            "metadata": {
                "totalTables": 0,
                "sourceFiles": [],
                "schemaCount": 0,
            },
        }
        self.tables: Dict[str, Dict[str, Any]] = {}
        self.sources_scanned: List[str] = []

    def _should_skip(self, path: Path) -> bool:
        try:
            parts = set(path.relative_to(self.root).parts)
        except ValueError:
            parts = set(path.parts)
        if parts & SKIP_DIR_PARTS:
            return True
        # Skip tests to reduce fixture noise
        if "tests" in parts:
            return True
        # Any virtualenv / site-packages under the repo
        for p in parts:
            if p.startswith(".venv") or p == "site-packages":
                return True
        return False

    def _path_schema_hint(self, filepath: Path) -> Optional[str]:
        rel = str(filepath.relative_to(self.root)).replace("\\", "/")
        for hint, schema in PATH_SCHEMA_HINTS:
            if rel.startswith(hint) or f"/{hint}" in f"/{rel}":
                return schema
        return None

    def _resolve_schema_const(self, content: str) -> Optional[str]:
        m = re.search(
            r"""(?:^|\n)\s*SCHEMA\s*=\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]""",
            content,
        )
        return m.group(1) if m else None

    def _fqn(self, schema: Optional[str], table: str) -> str:
        sch = (schema or "public").lower()
        return f"{sch}.{table.lower()}"

    def _categorize(self, table_name: str) -> str:
        for category, pattern in TABLE_CATEGORIES.items():
            if re.search(pattern, table_name, re.IGNORECASE):
                return category
        return "general"

    def _parse_columns(self, body: str) -> List[Dict[str, Any]]:
        columns: List[Dict[str, Any]] = []
        # Split top-level commas roughly by lines first (DDL is usually line-oriented).
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line:
                continue
            upper = line.upper()
            if upper.startswith(
                (
                    "PRIMARY KEY",
                    "FOREIGN KEY",
                    "UNIQUE",
                    "CHECK",
                    "CONSTRAINT",
                    "INDEX",
                    "--",
                )
            ):
                continue
            # column_name TYPE ...
            m = re.match(
                r'^"?([A-Za-z_][A-Za-z0-9_]*)"?\s+([A-Za-z][A-Za-z0-9_().\s]+?)(?:\s+(?:NOT NULL|NULL|DEFAULT|PRIMARY|REFERENCES|CHECK|UNIQUE).*)?$',
                line,
                re.IGNORECASE,
            )
            if not m:
                # fallback: first token is name
                parts = line.split()
                if not parts or not re.match(r"^[A-Za-z_]", parts[0]):
                    continue
                name = parts[0].strip('"')
                col_type = parts[1] if len(parts) > 1 else "unknown"
            else:
                name, col_type = m.group(1), m.group(2).strip()
            columns.append(
                {
                    "name": name,
                    "type": re.sub(r"\s+", " ", col_type).strip(),
                    "nullable": "NOT NULL" not in upper,
                    "primaryKey": "PRIMARY KEY" in upper,
                }
            )
        return columns

    def _extract_pk_fk(self, body: str) -> Tuple[List[str], List[Dict[str, str]]]:
        pks: List[str] = []
        fks: List[Dict[str, str]] = []
        for m in re.finditer(
            r"PRIMARY\s+KEY\s*\(([^)]+)\)", body, re.IGNORECASE
        ):
            pks.extend(
                [c.strip().strip('"') for c in m.group(1).split(",") if c.strip()]
            )
        for m in re.finditer(
            r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+([A-Za-z0-9_.\"]+)\s*(?:\(([^)]+)\))?",
            body,
            re.IGNORECASE,
        ):
            fks.append(
                {
                    "columns": m.group(1).strip(),
                    "references": m.group(2).strip().strip('"'),
                    "refColumns": (m.group(3) or "").strip(),
                }
            )
        # inline REFERENCES on column
        for m in re.finditer(
            r'([A-Za-z_][A-Za-z0-9_]*)\s+[A-Za-z0-9_().]+\s+.*?REFERENCES\s+([A-Za-z0-9_."]+)',
            body,
            re.IGNORECASE | re.DOTALL,
        ):
            fks.append(
                {
                    "columns": m.group(1),
                    "references": m.group(2).strip().strip('"'),
                    "refColumns": "",
                }
            )
        return pks, fks

    def _add_table(
        self,
        schema: Optional[str],
        table: str,
        body: str,
        source: str,
        filepath: Path,
        line_num: int,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        table = table.strip().strip('"')
        if not table or not re.match(r"^[A-Za-z_]", table):
            return
        fqn = self._fqn(schema, table)
        columns = self._parse_columns(body) if body else []
        pks, fks = self._extract_pk_fk(body) if body else ([], [])
        # promote inline PK columns
        for col in columns:
            if col.get("primaryKey") and col["name"] not in pks:
                pks.append(col["name"])

        sensitive_cols = [
            c["name"] for c in columns if SENSITIVE_COLUMN_RE.search(c.get("name", ""))
        ]
        owner_meta = resolve_owner_from_path(
            filepath.relative_to(self.root) if filepath.is_absolute() else filepath,
            schema=(schema or "public"),
        )
        status = "active"
        related_apis: List[str] = []
        if extra:
            status = extra.get("status", status)
            if extra.get("owner"):
                owner_meta["owner"] = extra["owner"]
            if extra.get("team"):
                owner_meta["team"] = extra["team"]
            related_apis = list(extra.get("relatedApis") or [])

        if fqn not in self.tables:
            self.tables[fqn] = {
                "name": table.lower(),
                "schema": (schema or "public").lower(),
                "fqn": fqn,
                "source": source,
                "columns": columns,
                "primaryKey": pks,
                "foreignKeys": fks,
                "indexes": [],
                "locations": [],
                "category": self._categorize(table),
                "sensitive": bool(sensitive_cols),
                "sensitiveColumns": sensitive_cols,
                "status": status,
                "owner": owner_meta.get("owner", "unknown"),
                "team": owner_meta.get("team", "unassigned"),
                "relatedApis": related_apis,
            }
        else:
            # merge columns if empty before
            if not self.tables[fqn]["columns"] and columns:
                self.tables[fqn]["columns"] = columns
            if sensitive_cols:
                self.tables[fqn]["sensitive"] = True
                existing_sc = set(self.tables[fqn].get("sensitiveColumns") or [])
                self.tables[fqn]["sensitiveColumns"] = sorted(
                    existing_sc | set(sensitive_cols)
                )
            if not self.tables[fqn]["primaryKey"] and pks:
                self.tables[fqn]["primaryKey"] = pks
            if fks:
                existing = {
                    (fk["columns"], fk["references"])
                    for fk in self.tables[fqn]["foreignKeys"]
                }
                for fk in fks:
                    key = (fk["columns"], fk["references"])
                    if key not in existing:
                        self.tables[fqn]["foreignKeys"].append(fk)
            # Prefer non-active status if annotation says so
            if status != "active":
                self.tables[fqn]["status"] = status
            if owner_meta.get("owner") and self.tables[fqn].get("owner") in {
                "unknown",
                None,
                "",
            }:
                self.tables[fqn]["owner"] = owner_meta["owner"]
                self.tables[fqn]["team"] = owner_meta.get("team", "unassigned")
            if related_apis:
                existing_apis = set(self.tables[fqn].get("relatedApis") or [])
                self.tables[fqn]["relatedApis"] = sorted(
                    existing_apis | set(related_apis)
                )

        loc = {
            "file": str(filepath.relative_to(self.root)),
            "line": line_num,
        }
        if loc not in self.tables[fqn]["locations"]:
            self.tables[fqn]["locations"].append(loc)

    def _add_index(
        self,
        schema: Optional[str],
        index_name: str,
        table_ref: str,
        filepath: Path,
        line_num: int,
    ) -> None:
        table_ref = table_ref.strip().strip('"')
        if "." in table_ref:
            sch, tbl = table_ref.split(".", 1)
        else:
            sch, tbl = schema, table_ref
        fqn = self._fqn(sch, tbl)
        if fqn not in self.tables:
            # create stub so index is not lost
            self._add_table(sch, tbl, "", "index-ref", filepath, line_num)
        idx = {
            "name": index_name,
            "file": str(filepath.relative_to(self.root)),
            "line": line_num,
        }
        if idx not in self.tables[fqn]["indexes"]:
            self.tables[fqn]["indexes"].append(idx)

    # ------------------------------------------------------------------
    # CREATE TABLE (balanced parentheses — NUMERIC(18,4) etc.)
    # ------------------------------------------------------------------
    _CREATE_TABLE_HEAD_RE = re.compile(
        r"""CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?:(?P<schema>\{?[A-Za-z_][A-Za-z0-9_]*\}?)\.)?
            (?P<table>\{?[A-Za-z_][A-Za-z0-9_]*\}?|"[A-Za-z_][A-Za-z0-9_]*")
            \s*\(
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    _CREATE_INDEX_RE = re.compile(
        r"""CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?
            (?P<index>[A-Za-z_][A-Za-z0-9_]*)
            \s+ON\s+
            (?:(?P<schema>[A-Za-z_][A-Za-z0-9_]*)\.)?
            (?P<table>[A-Za-z_][A-Za-z0-9_]*|"[A-Za-z_][A-Za-z0-9_]*")
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    def _extract_balanced_body(self, content: str, open_paren_idx: int) -> Optional[str]:
        """open_paren_idx points at '('; return body inside matching ')'."""
        if open_paren_idx >= len(content) or content[open_paren_idx] != "(":
            return None
        depth = 0
        i = open_paren_idx
        in_single = in_double = False
        while i < len(content):
            ch = content[i]
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif not in_single and not in_double:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        return content[open_paren_idx + 1 : i]
            i += 1
        return None

    def _resolve_token(
        self, token: Optional[str], schema_const: Optional[str]
    ) -> Optional[str]:
        if not token:
            return None
        token = token.strip().strip('"')
        if token in ("{SCHEMA}", "SCHEMA") or token.startswith("{"):
            return schema_const
        return token

    def scan_text(
        self, content: str, filepath: Path, source: str, schema_hint: Optional[str]
    ) -> None:
        schema_const = self._resolve_schema_const(content)
        default_schema = schema_const or schema_hint

        for m in self._CREATE_TABLE_HEAD_RE.finditer(content):
            open_idx = m.end() - 1  # points at '('
            body = self._extract_balanced_body(content, open_idx) or ""
            line_num = content[: m.start()].count("\n") + 1
            raw_schema = m.group("schema")
            raw_table = m.group("table")

            schema = self._resolve_token(raw_schema, schema_const) or default_schema
            table = self._resolve_token(raw_table, schema_const)
            if not table or table in ("SCHEMA",):
                continue
            if "{" in table or "}" in table:
                continue
            # annotations near CREATE TABLE (status/owner)
            ctx = context_window(content, m.start(), before=300, after=80)
            ann = parse_taxonomy_annotations(ctx)
            status = ann.get("status") or detect_status_from_text(ctx)
            extra = {
                "status": status,
            }
            if ann.get("owner"):
                extra["owner"] = ann["owner"]
            if ann.get("team"):
                extra["team"] = ann["team"]
            self._add_table(schema, table, body, source, filepath, line_num, extra=extra)

        for m in self._CREATE_INDEX_RE.finditer(content):
            line_num = content[: m.start()].count("\n") + 1
            schema = m.group("schema") or default_schema
            table = m.group("table")
            self._add_index(schema, m.group("index"), table, filepath, line_num)

    def scan_sql_files(self) -> None:
        logger.info("📄 Scanning SQL files for tables...")
        for sql_file in self.root.rglob("*.sql"):
            if self._should_skip(sql_file):
                continue
            rel = str(sql_file.relative_to(self.root))
            logger.info(f"  └─ {rel}")
            self.sources_scanned.append(rel)
            try:
                content = sql_file.read_text(errors="ignore")
            except Exception as e:
                logger.error(f"    Error reading {rel}: {e}")
                continue
            # SET search_path TO x
            search_path = None
            sp = re.search(
                r"SET\s+search_path\s+TO\s+([A-Za-z_][A-Za-z0-9_]*)",
                content,
                re.IGNORECASE,
            )
            if sp:
                search_path = sp.group(1)
            schema_hint = search_path or self._path_schema_hint(sql_file)
            self.scan_text(content, sql_file, "sql", schema_hint)

    def scan_python_ddl(self) -> None:
        logger.info("🐍 Scanning Python DDL for tables...")
        for py_file in self.root.rglob("*.py"):
            if self._should_skip(py_file):
                continue
            try:
                content = py_file.read_text(errors="ignore")
            except Exception:
                continue
            if "CREATE TABLE" not in content.upper():
                continue
            rel = str(py_file.relative_to(self.root))
            logger.info(f"  └─ {rel}")
            self.sources_scanned.append(rel)
            schema_hint = self._path_schema_hint(py_file)
            self.scan_text(content, py_file, "python-ddl", schema_hint)

    def generate_catalog(self) -> Dict[str, Any]:
        logger.info("\n" + "=" * 70)
        logger.info("🔍 TABLES CATALOG SCANNER")
        logger.info("=" * 70 + "\n")

        self.scan_sql_files()
        self.scan_python_ddl()

        status_counts: Dict[str, int] = {}
        owner_counts: Dict[str, int] = {}
        for fqn, data in sorted(self.tables.items()):
            category = data.get("category") or self._categorize(data["name"])
            data["category"] = category
            data.setdefault("sensitive", False)
            data.setdefault("sensitiveColumns", [])
            data.setdefault("status", "active")
            data.setdefault("owner", "unknown")
            data.setdefault("team", "unassigned")
            data.setdefault("relatedApis", [])
            status_counts[data["status"]] = status_counts.get(data["status"], 0) + 1
            owner_counts[data["owner"]] = owner_counts.get(data["owner"], 0) + 1
            self.catalog["categories"][category][fqn] = data

        schemas = {d["schema"] for d in self.tables.values()}
        self.catalog["metadata"]["totalTables"] = len(self.tables)
        self.catalog["metadata"]["sourceFiles"] = sorted(set(self.sources_scanned))
        self.catalog["metadata"]["schemaCount"] = len(schemas)
        self.catalog["metadata"]["statusCounts"] = status_counts
        self.catalog["metadata"]["ownerCounts"] = owner_counts

        logger.info("\n" + "=" * 70)
        logger.info("📊 TABLES CATALOG SUMMARY")
        logger.info("=" * 70)
        logger.info(f"✅ Total tables: {len(self.tables)}")
        logger.info(f"✅ Schemas: {sorted(schemas)}")
        logger.info(f"✅ Source files: {len(set(self.sources_scanned))}")
        for category, entries in sorted(self.catalog["categories"].items()):
            if entries:
                logger.info(f"  • {category}: {len(entries)} tables")
        logger.info("=" * 70 + "\n")
        return self.catalog

    def save_catalog(self, output_file: Optional[str] = None) -> Path:
        if output_file is None:
            output_file = self.root / ".tables-catalog" / "catalog.json"
        else:
            output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        # convert defaultdict
        payload = {
            **self.catalog,
            "categories": {k: v for k, v in self.catalog["categories"].items()},
        }
        output_file.write_text(json.dumps(payload, indent=2, default=str))
        logger.info(f"💾 Tables catalog saved to: {output_file}")
        return output_file

    def generate_reports(self, output_dir: Optional[Path] = None) -> None:
        out = Path(output_dir) if output_dir else self.root / ".tables-catalog"
        out.mkdir(parents=True, exist_ok=True)

        sensitive_n = sum(
            1
            for entries in self.catalog["categories"].values()
            for d in entries.values()
            if d.get("sensitive")
        )
        # Markdown report
        lines = [
            "# Tables Catalog Report\n",
            f"**Generated:** {self.catalog['generatedAt']}\n",
            f"**Total Tables:** {self.catalog['metadata']['totalTables']}\n",
            f"**Schemas:** {self.catalog['metadata']['schemaCount']}\n",
            f"**Sensitive Tables:** {sensitive_n}\n",
            f"**Source Files:** {len(self.catalog['metadata']['sourceFiles'])}\n",
            "---\n\n",
            "## Summary by Category\n\n",
        ]
        for category, entries in sorted(self.catalog["categories"].items()):
            lines.append(f"### {category} ({len(entries)})\n\n")
            for fqn, data in sorted(entries.items()):
                cols = len(data.get("columns") or [])
                lock = "🔒" if data.get("sensitive") else "✓"
                st = data.get("status", "active")
                owner = data.get("owner", "?")
                lines.append(
                    f"- `{fqn}` {lock} [{st}] owner=`{owner}` — {cols} cols, "
                    f"source=`{data.get('source')}`\n"
                )
            lines.append("\n")
        # Ownership rollup
        lines.append("## Ownership\n\n")
        for owner, count in sorted(
            (self.catalog["metadata"].get("ownerCounts") or {}).items(),
            key=lambda x: -x[1],
        ):
            lines.append(f"- `{owner}`: {count} tables\n")
        lines.append("\n## Lifecycle status\n\n")
        for st, count in sorted(
            (self.catalog["metadata"].get("statusCounts") or {}).items()
        ):
            lines.append(f"- `{st}`: {count}\n")
        (out / "CATALOG_REPORT.md").write_text("".join(lines))

        # CSV
        csv_lines = [
            "fqn,schema,table,category,source,columns,sensitive,status,owner,team,"
            "related_apis,primary_key,locations"
        ]
        for category, entries in self.catalog["categories"].items():
            for fqn, data in entries.items():
                locs = ";".join(
                    f"{l['file']}:{l['line']}" for l in data.get("locations", [])
                )
                pk = ";".join(data.get("primaryKey") or [])
                sens = "yes" if data.get("sensitive") else "no"
                rel = ";".join(data.get("relatedApis") or [])
                csv_lines.append(
                    f'{fqn},{data.get("schema")},{data.get("name")},{category},'
                    f'{data.get("source")},{len(data.get("columns") or [])},{sens},'
                    f'{data.get("status", "active")},{data.get("owner", "")},'
                    f'{data.get("team", "")},"{rel}","{pk}","{locs}"'
                )
        (out / "catalog.csv").write_text("\n".join(csv_lines))
        logger.info(f"✅ Table reports written to {out}")


def main() -> None:
    catalog = TablesCatalog()
    catalog.generate_catalog()
    catalog.save_catalog()
    catalog.generate_reports()


if __name__ == "__main__":
    main()
