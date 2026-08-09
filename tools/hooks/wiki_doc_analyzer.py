#!/usr/bin/env python3
"""wiki_doc_analyzer.py — Pré-análise de documentação antes de publicar na wiki.

Executado como pre-commit hook. Analisa .md staged:
  1. Validação estrutural (headings, links, code blocks, frontmatter)
  2. Extração de termos-chave e decisões para memória do agente wiki
  3. Detecção de duplicatas com páginas existentes na wiki

Uso:
    python3 tools/hooks/wiki_doc_analyzer.py [--staged] [--verbose]

Exit codes:
    0 — OK (warnings podem existir)
    1 — Bloqueado (erro estrutural crítico)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# ── Configuração ──────────────────────────────────────────────────────────────

WIKI_GQL = os.environ.get("WIKI_GQL_URL", "http://192.168.15.2:3009/graphql")
SECRETS_ENDPOINT = "http://192.168.15.2:8088/secret/wikijs/token"

# Padrões para skip (mesmos do post-commit)
SKIP_PATTERNS = [
    r"^wiki_",
    r"CONVERSAS_",
    r"COMPARISON",
    r"^\.github/",
    r"^docs/confluence",
    r"^\.claude/",
]

# ── Regex para análise ────────────────────────────────────────────────────────

RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
RE_CODE_BLOCK = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
RE_INTERNAL_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
RE_ADR = re.compile(r"(?:ADR|Decision|Decisão)[:\s]+(.+)", re.IGNORECASE)
RE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
RE_TODO = re.compile(r"(?:TODO|FIXME|HACK|XXX)[:\s]+(.+)", re.IGNORECASE)


# ── Utilitários ───────────────────────────────────────────────────────────────

def _git_staged_files() -> list[Path]:
    """Retorna arquivos .md staged para commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        return [
            REPO_ROOT / f
            for f in result.stdout.splitlines()
            if f.endswith(".md")
        ]
    except Exception:
        return []


def _load_wiki_token() -> str:
    """Carrega token da wiki (env > .env > secrets agent)."""
    val = os.environ.get("WIKI_TOKEN", "")
    if val:
        return val
    env_f = REPO_ROOT / ".env"
    if env_f.exists():
        for line in env_f.read_text().splitlines():
            if line.startswith("WIKI_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    try:
        import urllib.request
        req = urllib.request.Request(SECRETS_ENDPOINT)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read()).get("value", "")
    except Exception:
        return ""


def _should_skip(filepath: Path) -> bool:
    """Verifica se o arquivo deve ser ignorado."""
    rel = str(filepath.relative_to(REPO_ROOT)) if filepath.is_relative_to(REPO_ROOT) else filepath.name
    return any(re.search(pat, rel) for pat in SKIP_PATTERNS)


# ── 1. Validação Estrutural ───────────────────────────────────────────────────

class StructuralValidator:
    """Valida estrutura do markdown."""

    def __init__(self, content: str, filepath: Path):
        self.content = content
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> tuple[list[str], list[str]]:
        self._check_frontmatter()
        self._check_headings()
        self._check_code_blocks()
        self._check_internal_links()
        self._check_line_length()
        self._check_empty_sections()
        return self.errors, self.warnings

    def _check_frontmatter(self):
        """Verifica se frontmatter existe e tem campos obrigatórios."""
        match = RE_FRONTMATTER.match(self.content)
        if not match:
            self.warnings.append("Sem frontmatter (recomendado: title, description)")
            return
        fm = match.group(1)
        if "title:" not in fm:
            self.errors.append("Frontmatter sem campo 'title'")
        if "description:" not in fm:
            self.warnings.append("Frontmatter sem campo 'description'")

    def _check_headings(self):
        """Valida hierarquia de headings."""
        headings = RE_HEADING.findall(self.content)
        if not headings:
            self.warnings.append("Documento sem headings (H1/H2/H3)")
            return

        levels = [len(h[0]) for h in headings]
        if levels[0] != 1:
            self.errors.append(f"Primeiro heading deve ser H1 (encontrou H{levels[0]})")

        for i in range(1, len(levels)):
            if levels[i] - levels[i - 1] > 1:
                self.warnings.append(
                    f"Pulo de H{levels[i-1]} para H{levels[i]} (linhas podem estar inconsistentes)"
                )

    def _check_code_blocks(self):
        """Verifica code blocks."""
        blocks = RE_CODE_BLOCK.findall(self.content)
        for lang, _ in blocks:
            if not lang:
                self.warnings.append("Code block sem linguagem especificada")

    def _check_internal_links(self):
        """Verifica links internos quebrados (básico)."""
        links = RE_INTERNAL_LINK.findall(self.content)
        for text, url in links:
            if url.startswith("#"):
                continue  # Anchor local
            if url.startswith("http"):
                continue  # Link externo
            # Link interno — verificar se o arquivo existe
            target = self.filepath.parent / url
            if not target.exists():
                self.warnings.append(f"Link interno quebrado: [{text}]({url})")

    def _check_line_length(self):
        """Avisa sobre linhas muito longas."""
        for i, line in enumerate(self.content.split("\n"), 1):
            if len(line) > 200 and not line.strip().startswith("```"):
                self.warnings.append(f"Linha {i}: {len(line)} chars (>200)")

    def _check_empty_sections(self):
        """Detecta seções vazias."""
        lines = self.content.split("\n")
        for i in range(len(lines) - 1):
            if re.match(r"^#{1,6}\s+", lines[i]):
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if not next_line or next_line.startswith("#"):
                    self.warnings.append(f"Seção vazia: {lines[i].strip()}")


# ── 2. Extração de Termos ────────────────────────────────────────────────────

class TermExtractor:
    """Extrai termos-chave, decisões e contexto do documento."""

    def __init__(self, content: str, filepath: Path):
        self.content = content
        self.filepath = filepath
        self.result: dict[str, Any] = {
            "file": str(filepath.relative_to(REPO_ROOT) if filepath.is_relative_to(REPO_ROOT) else filepath.name),
            "headings": [],
            "decisions": [],
            "todos": [],
            "code_langs": [],
            "key_terms": [],
        }

    def extract(self) -> dict[str, Any]:
        self._extract_headings()
        self._extract_decisions()
        self._extract_todos()
        self._extract_code_langs()
        self._extract_key_terms()
        return self.result

    def _extract_headings(self):
        """Extrai todos os headings como estrutura do documento."""
        self.result["headings"] = [
            {"level": len(h[0]), "text": h[1].strip()}
            for h in RE_HEADING.findall(self.content)
        ]

    def _extract_decisions(self):
        """Extrai decisões/ADRs mencionadas."""
        self.result["decisions"] = RE_ADR.findall(self.content)

    def _extract_todos(self):
        """Extrai TODOs e FIXMEs."""
        self.result["todos"] = RE_TODO.findall(self.content)

    def _extract_code_langs(self):
        """Lista linguagens de code blocks."""
        self.result["code_langs"] = list(set(
            lang for lang, _ in RE_CODE_BLOCK.findall(self.content) if lang
        ))

    def _extract_key_terms(self):
        """Extrai termos técnicos relevantes."""
        # Termos de alto sinal: tecnologias, serviços, conceitos
        patterns = [
            r"\b(Python|Rust|Go|TypeScript|Docker|Kubernetes|PostgreSQL|Redis)\b",
            r"\b(MCP|LLM|Ollama|GPU|CPU|RAM|VRAM)\b",
            r"\b(trading|deploy|rollback|hotfix|incident|outage)\b",
            r"\b(Grafana|Prometheus|Alertmanager|Telegram)\b",
        ]
        terms = set()
        for pat in patterns:
            terms.update(re.findall(pat, self.content, re.IGNORECASE))
        self.result["key_terms"] = sorted(terms)


# ── 3. Detecção de Duplicatas ────────────────────────────────────────────────

class DuplicateDetector:
    """Verifica se o conteúdo já existe na wiki."""

    def __init__(self, content: str, filepath: Path, token: str):
        self.content = content
        self.filepath = filepath
        self.token = token
        self.duplicates: list[dict[str, str]] = []

    def check(self) -> list[dict[str, str]]:
        if not self.token:
            return []

        try:
            from specialized_agents.wiki_client import WikiJsClient
            client = WikiJsClient(WIKI_GQL, self.token, default_locale="pt")

            # Extrair título do documento
            title_match = RE_HEADING.search(self.content)
            if not title_match:
                return []

            search_term = title_match.group(2).strip()[:50]

            # Listar páginas e comparar similaridade básica
            pages = client.list_pages()
            for page in pages:
                page_title = page.get("title", "").lower()
                if self._similar(search_term.lower(), page_title):
                    self.duplicates.append({
                        "wiki_path": page.get("path", "?"),
                        "title": page.get("title", "?"),
                        "updated": page.get("updatedAt", "?"),
                    })

        except Exception:
            pass  # Falha silenciosa — não bloqueia commit

        return self.duplicates

    def _similar(self, a: str, b: str) -> bool:
        """Similaridade básica por tokens compartilhados."""
        tokens_a = set(a.split())
        tokens_b = set(b.split())
        if not tokens_a or not tokens_b:
            return False
        overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))
        return overlap > 0.7


# ── Relatório ─────────────────────────────────────────────────────────────────

def _print_report(
    filepath: Path,
    errors: list[str],
    warnings: list[str],
    terms: dict[str, Any],
    duplicates: list[dict[str, str]],
    verbose: bool,
):
    """Imprime relatório de análise."""
    rel = filepath.relative_to(REPO_ROOT) if filepath.is_relative_to(REPO_ROOT) else filepath.name
    print(f"\n📄 Analisando: {rel}")

    if errors:
        print(f"  ❌ Erros ({len(errors)}):")
        for e in errors:
            print(f"     - {e}")

    if warnings:
        print(f"  ⚠️  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"     - {w}")

    if verbose:
        headings = terms.get("headings", [])
        if headings:
            print(f"  📑 Estrutura: {len(headings)} headings")
            for h in headings[:5]:
                print(f"     {'  ' * (h['level'] - 1)}H{h['level']}: {h['text']}")

        decisions = terms.get("decisions", [])
        if decisions:
            print(f"  🎯 Decisões: {len(decisions)}")
            for d in decisions[:3]:
                print(f"     - {d[:80]}")

        todos = terms.get("todos", [])
        if todos:
            print(f"  📝 TODOs: {len(todos)}")
            for t in todos[:3]:
                print(f"     - {t[:80]}")

        langs = terms.get("code_langs", [])
        if langs:
            print(f"  💻 Code blocks: {', '.join(langs)}")

        key_terms = terms.get("key_terms", [])
        if key_terms:
            print(f"  🔑 Termos-chave: {', '.join(key_terms[:10])}")

    if duplicates:
        print(f"  🔄 Possíveis duplicatas ({len(duplicates)}):")
        for d in duplicates:
            print(f"     - {d['title']} → {d['wiki_path']} (atualizado: {d['updated']})")

    if not errors and not warnings and not duplicates:
        print("  ✅ Tudo OK")


# ── Persistência para memória do agente ──────────────────────────────────────

def _persist_to_memory(terms: list[dict[str, Any]]):
    """Salva termos extraídos para uso do agente wiki."""
    memory_file = REPO_ROOT / "tools" / "hooks" / ".wiki_doc_terms.json"
    existing = []
    if memory_file.exists():
        try:
            existing = json.loads(memory_file.read_text())
        except Exception:
            existing = []

    # Adicionar novos termos (dedup por arquivo)
    existing_files = {t["file"] for t in existing}
    for t in terms:
        if t["file"] not in existing_files:
            existing.append(t)

    # Manter apenas últimos 100 documentos
    existing = existing[-100:]

    try:
        memory_file.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    except Exception:
        pass  # Não bloqueia commit


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pré-análise de documentação wiki")
    parser.add_argument("--staged", action="store_true", help="Analisar apenas arquivos staged")
    parser.add_argument("--verbose", action="store_true", help="Saída detalhada")
    parser.add_argument("--skip-dedup", action="store_true", help="Pular checagem de duplicatas")
    parser.add_argument("files", nargs="*", help="Arquivos específicos para analisar")
    args = parser.parse_args()

    if args.files:
        files = [Path(f) for f in args.files if Path(f).exists()]
    elif args.staged:
        files = _git_staged_files()
    else:
        files = list(REPO_ROOT.rglob("*.md"))
        files = [f for f in files if f.is_file() and not _should_skip(f)]

    if not files:
        print("📭 Nenhum .md para analisar")
        return 0

    token = _load_wiki_token()
    all_terms = []
    has_errors = False

    for filepath in files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"❌ Erro lendo {filepath}: {exc}")
            has_errors = True
            continue

        # 1. Validação estrutural
        validator = StructuralValidator(content, filepath)
        errors, warnings = validator.validate()

        # 2. Extração de termos
        extractor = TermExtractor(content, filepath)
        terms = extractor.extract()

        # 3. Detecção de duplicatas
        duplicates = []
        if not args.skip_dedup and token:
            detector = DuplicateDetector(content, filepath, token)
            duplicates = detector.check()

        # Relatório
        _print_report(filepath, errors, warnings, terms, duplicates, args.verbose)

        if errors:
            has_errors = True

        all_terms.append(terms)

    # Persistir termos para memória
    if all_terms:
        _persist_to_memory(all_terms)

    print()
    if has_errors:
        print("❌ Análise encontrou erros — commit bloqueado")
        print("   Corrija os erros ou use --no-verify para ignorar")
        return 1

    print("✅ Análise de documentação concluída")
    return 0


if __name__ == "__main__":
    sys.exit(main())
