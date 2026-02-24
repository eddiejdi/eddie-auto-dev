"""ServerKnowledgeRAG
Standalone module for the Homelab Advisor Agent.
Provides a TF-based retriever for server knowledge RAG.
Indexes runtime state (docker, systemd, journal) PLUS all project
documentation (.md files, configs, lessons learned, architecture docs).
"""
import os
import re
import glob
from collections import Counter as _Counter
import math
import subprocess
import logging

logger = logging.getLogger("rag")

# Base path of the main repo
REPO_ROOT = os.environ.get(
    "RAG_REPO_ROOT",
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

# Max size per file to avoid OOM (512KB)
MAX_FILE_SIZE = int(os.environ.get("RAG_MAX_FILE_SIZE", 524288))

# Directories to skip entirely
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "build", "dist", ".tox", ".mypy_cache", ".pytest_cache",
    "chroma_db", "chroma_data", ".dart_tool", ".gradle",
    "app/build", "web/build",
}

# Extensions to index as documentation
DOC_EXTENSIONS = {".md", ".txt", ".rst"}
CONFIG_EXTENSIONS = {".yml", ".yaml", ".json", ".toml", ".conf", ".env", ".ini"}


class ServerKnowledgeRAG:
    def __init__(self):
        self.documents = []
        self.indexed = False

    def _tokenize(self, text: str):
        toks = re.findall(r"\w+", (text or "").lower())
        return [t for t in toks if len(t) > 1]

    def _tf(self, tokens):
        c = _Counter(tokens)
        return dict(c)

    def _norm(self, vec):
        return math.sqrt(sum(v * v for v in vec.values()))

    def _dot(self, a, b):
        return sum(a.get(k, 0) * b.get(k, 0) for k in a.keys())

    def _excerpt(self, text, n=800):
        if not text:
            return ""
        return text.strip().replace("\n", " ")[:n]

    def _should_skip_dir(self, dirname: str) -> bool:
        """Check if directory should be skipped."""
        return dirname in SKIP_DIRS or dirname.startswith(".")

    def _read_file_safe(self, path: str) -> str:
        """Read file with size limit."""
        try:
            size = os.path.getsize(path)
            if size > MAX_FILE_SIZE:
                logger.debug(f"Skipping large file ({size}B): {path}")
                return ""
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception as e:
            logger.debug(f"Read error {path}: {e}")
            return ""

    def collect_runtime_documents(self):
        """Collect runtime state documents (docker, systemd, journal)."""
        docs = []

        # docker ps
        try:
            out = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}: {{.Image}} - {{.Status}}"],
                capture_output=True, text=True, timeout=5
            ).stdout
        except Exception as e:
            out = f"docker ps error: {e}"
        docs.append({"id": "docker_ps", "source": "runtime", "text": out})

        # systemd running services
        try:
            out = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
                capture_output=True, text=True, timeout=5
            ).stdout
        except Exception as e:
            out = f"systemctl error: {e}"
        docs.append({"id": "systemd_services", "source": "runtime", "text": out})

        # candidate config files
        candidate_paths = [
            "/etc/prometheus/rules/homelab-advisor-alerts.yml",
            "/etc/prometheus/rules/homelab-alerts.yml",
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                content = self._read_file_safe(p)
                if content:
                    docs.append({"id": f"file:{p}", "source": "config", "text": content})

        # recent journal
        try:
            out = subprocess.run(
                ["journalctl", "-u", "estouaqui-backend", "-n", "200", "--no-pager"],
                capture_output=True, text=True, timeout=5
            ).stdout
            if out:
                docs.append({"id": "journal_estouaqui", "source": "journal", "text": out})
        except Exception:
            pass

        return docs

    def collect_documentation(self):
        """Collect all documentation files from the repo."""
        docs = []
        if not os.path.isdir(REPO_ROOT):
            logger.warning(f"Repo root not found: {REPO_ROOT}")
            return docs

        count = 0
        for root, dirs, files in os.walk(REPO_ROOT):
            # Filter out directories to skip
            dirs[:] = [d for d in dirs if not self._should_skip_dir(d)]

            rel_root = os.path.relpath(root, REPO_ROOT)

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in DOC_EXTENSIONS:
                    continue

                fpath = os.path.join(root, fname)
                content = self._read_file_safe(fpath)
                if not content or len(content.strip()) < 50:
                    continue

                rel_path = os.path.join(rel_root, fname) if rel_root != "." else fname
                # Category based on path
                category = self._categorize(rel_path)
                doc_id = f"doc:{rel_path}"
                docs.append({
                    "id": doc_id,
                    "source": category,
                    "text": f"# {rel_path}\n\n{content}",
                })
                count += 1

        logger.info(f"Collected {count} documentation files from {REPO_ROOT}")
        return docs

    def collect_configs(self):
        """Collect key configuration files."""
        docs = []
        if not os.path.isdir(REPO_ROOT):
            return docs

        # Specific important configs to index
        important_configs = [
            "docker-compose-exporters.yml",
            "prometheus-config.yml",
            "monitoring/prometheus.yml",
            "monitoring/alert_rules.yml",
            ".github/copilot-instructions.md",
            ".github/copilot-instructions-extended.md",
            ".github/agents/agent_dev_local.agent.md",
            "specialized_agents/config.py",
            "pytest.ini",
        ]

        for relpath in important_configs:
            fpath = os.path.join(REPO_ROOT, relpath)
            if os.path.exists(fpath):
                content = self._read_file_safe(fpath)
                if content:
                    docs.append({
                        "id": f"cfg:{relpath}",
                        "source": "config",
                        "text": f"# Config: {relpath}\n\n{content}",
                    })

        # Also scan for GitHub Actions workflows
        wf_dir = os.path.join(REPO_ROOT, ".github", "workflows")
        if os.path.isdir(wf_dir):
            for fname in os.listdir(wf_dir):
                if fname.endswith((".yml", ".yaml")):
                    fpath = os.path.join(wf_dir, fname)
                    content = self._read_file_safe(fpath)
                    if content:
                        docs.append({
                            "id": f"workflow:{fname}",
                            "source": "ci-cd",
                            "text": f"# GitHub Actions: {fname}\n\n{content}",
                        })

        return docs

    def _categorize(self, rel_path: str) -> str:
        """Categorize a document based on its relative path."""
        p = rel_path.lower()
        if "lesson" in p or "recovery" in p or "crash" in p or "incident" in p:
            return "lessons-learned"
        if "architect" in p or "distributed" in p or "team" in p:
            return "architecture"
        if "secret" in p or "vault" in p:
            return "security"
        if "deploy" in p or "setup" in p or "install" in p:
            return "deployment"
        if "grafana" in p or "monitor" in p or "alert" in p or "metric" in p or "prometheus" in p:
            return "monitoring"
        if "docker" in p or "container" in p:
            return "infrastructure"
        if "telegram" in p or "whatsapp" in p or "bot" in p:
            return "integrations"
        if "google" in p or "printer" in p:
            return "integrations"
        if "interceptor" in p or "bus" in p:
            return "interceptor"
        if "rag" in p or "llm" in p or "ollama" in p or "gemini" in p:
            return "ai-ml"
        if "test" in p or "selenium" in p:
            return "testing"
        if "jira" in p or "itil" in p or "project" in p:
            return "management"
        if "btc" in p or "trading" in p or "invest" in p:
            return "trading"
        if "specialized_agents" in p or "agent" in p:
            return "agents"
        if p.startswith("docs/"):
            return "documentation"
        if p.startswith("tools/"):
            return "tools"
        if "readme" in p:
            return "readme"
        return "general"

    def collect_documents(self):
        """Collect ALL documents: runtime + documentation + configs."""
        docs = []

        # 1. Runtime state
        runtime_docs = self.collect_runtime_documents()
        docs.extend(runtime_docs)

        # 2. Documentation files (.md, .txt, .rst)
        doc_files = self.collect_documentation()
        docs.extend(doc_files)

        # 3. Key configs and CI/CD
        config_docs = self.collect_configs()
        docs.extend(config_docs)

        logger.info(
            f"Total documents collected: {len(docs)} "
            f"(runtime={len(runtime_docs)}, docs={len(doc_files)}, configs={len(config_docs)})"
        )
        return docs

    def index(self):
        raw_docs = self.collect_documents()
        indexed = []
        for d in raw_docs:
            text = d.get("text") or ""
            tokens = self._tokenize(text)
            if not tokens:
                continue
            tf = self._tf(tokens)
            norm = self._norm(tf) or 1.0
            indexed.append({
                "id": d.get("id"),
                "source": d.get("source"),
                "text": text,
                "tf": tf,
                "norm": norm,
                "excerpt": self._excerpt(text, 800),
            })
        self.documents = indexed
        self.indexed = True
        logger.info(f"Indexed {len(self.documents)} documents into RAG")
        return len(self.documents)

    def query(self, q: str, top_k: int = 3):
        tokens = self._tokenize(q)
        if not tokens or not self.documents:
            return []
        q_tf = self._tf(tokens)
        q_norm = self._norm(q_tf) or 1.0
        results = []
        for doc in self.documents:
            try:
                score = self._dot(q_tf, doc["tf"]) / (q_norm * doc["norm"])
            except Exception:
                score = 0.0
            if score > 0:
                results.append({
                    "id": doc["id"],
                    "source": doc["source"],
                    "score": float(score),
                    "excerpt": doc["excerpt"],
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def status(self):
        sources = {}
        for d in self.documents:
            src = d.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        return {
            "indexed": self.indexed,
            "documents": len(self.documents),
            "sources": sources,
        }
