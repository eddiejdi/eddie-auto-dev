#!/usr/bin/env python3
"""wiki_doc_analyzer.py — Pré-análise de documentação focada na tarefa.

Executado como pre-commit hook. Analisa .md staged no contexto da atividade:
  1. Validação estrutural (headings, links, code blocks, frontmatter)
  2. Extração de conhecimento relevante para a tarefa sendo commitada
  3. Gera resumo de contexto para o agente wiki

Foco: agregar conhecimento à tarefa atual, não análise genérica.

Uso:
    python3 tools/hooks/wiki_doc_analyzer.py [--staged] [--verbose]

Exit codes:
    0 — OK
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

SECRETS_ENDPOINT = "http://192.168.15.2:8088/secret/wikijs/token"

SKIP_PATTERNS = [
    r"^wiki_",
    r"CONVERSAS_",
    r"COMPARISON",
    r"^\.github/",
    r"^docs/confluence",
    r"^\.claude/",
]

# ── Regex ─────────────────────────────────────────────────────────────────────

RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
RE_CODE_BLOCK = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
RE_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
RE_ADR = re.compile(r"(?:ADR|Decision|Decisão|decidido)[:\s]+(.+)", re.IGNORECASE)
RE_TODO = re.compile(r"(?:TODO|FIXME|HACK|XXX)[:\s]+(.+)", re.IGNORECASE)

# Mapeamento de paths para categorias de tarefa
TASK_CATEGORIES = {
    r"btc_trading_agent|trading": "trading",
    r"specialized_agents|coordinator": "agentes",
    r"deploy|systemd|docker": "infraestrutura",
    r"grafana|monitoring|alert": "monitoramento",
    r"wiki|docs|documentation": "documentação",
    r"scripts|tools": "automação",
    r"tests|test": "testes",
    r"security|vault|auth|secrets": "segurança",
}


# ── Utilitários ───────────────────────────────────────────────────────────────

def _git_staged_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        return [REPO_ROOT / f for f in result.stdout.splitlines() if f.endswith(".md")]
    except Exception:
        return []


def _git_staged_python() -> list[Path]:
    """Retorna arquivos .py staged (para contexto da tarefa)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        return [REPO_ROOT / f for f in result.stdout.splitlines() if f.endswith(".py")]
    except Exception:
        return []


def _git_diff_summary() -> str:
    """Retorna resumo do diff staged."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _detect_task_category(staged_files: list[Path], py_files: list[Path]) -> str:
    """Detecta a categoria da tarefa baseado nos arquivos staged."""
    all_files = [str(f) for f in staged_files + py_files]
    combined = " ".join(all_files).lower()

    for pattern, category in TASK_CATEGORIES.items():
        if re.search(pattern, combined, re.IGNORECASE):
            return category

    return "geral"


def _should_skip(filepath: Path) -> bool:
    rel = str(filepath.relative_to(REPO_ROOT)) if filepath.is_relative_to(REPO_ROOT) else filepath.name
    return any(re.search(pat, rel) for pat in SKIP_PATTERNS)


# ── 1. Validação Estrutural ───────────────────────────────────────────────────

class StructuralValidator:
    def __init__(self, content: str, filepath: Path):
        self.content = content
        self.filepath = filepath
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate(self) -> tuple[list[str], list[str]]:
        self._check_frontmatter()
        self._check_headings()
        self._check_code_blocks()
        self._check_line_length()
        return self.errors, self.warnings

    def _check_frontmatter(self):
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
        headings = RE_HEADING.findall(self.content)
        if not headings:
            self.warnings.append("Documento sem headings")
            return
        levels = [len(h[0]) for h in headings]
        if levels[0] != 1:
            self.errors.append(f"Primeiro heading deve ser H1 (encontrou H{levels[0]})")

    def _check_code_blocks(self):
        blocks = RE_CODE_BLOCK.findall(self.content)
        for lang, _ in blocks:
            if not lang:
                self.warnings.append("Code block sem linguagem especificada")

    def _check_line_length(self):
        for i, line in enumerate(self.content.split("\n"), 1):
            if len(line) > 200 and not line.strip().startswith("```"):
                self.warnings.append(f"Linha {i}: {len(line)} chars (>200)")


# ── 2. Extração de Conhecimento da Tarefa ────────────────────────────────────

class TaskKnowledgeExtractor:
    """Extrai conhecimento relevante para a tarefa sendo commitada."""

    def __init__(self, content: str, filepath: Path, task_category: str):
        self.content = content
        self.filepath = filepath
        self.task_category = task_category
        self.result: dict[str, Any] = {
            "file": str(filepath.relative_to(REPO_ROOT) if filepath.is_relative_to(REPO_ROOT) else filepath.name),
            "task_category": task_category,
            "title": "",
            "summary": "",
            "key_concepts": [],
            "decisions": [],
            "action_items": [],
            "related_services": [],
        }

    def extract(self) -> dict[str, Any]:
        self._extract_title()
        self._extract_summary()
        self._extract_key_concepts()
        self._extract_decisions()
        self._extract_action_items()
        self._extract_related_services()
        return self.result

    def _extract_title(self):
        match = RE_HEADING.search(self.content)
        if match:
            self.result["title"] = match.group(2).strip()

    def _extract_summary(self):
        """Extrai primeiro parágrafo significativo como resumo."""
        lines = self.content.split("\n")
        in_content = False
        summary_lines = []

        for line in lines:
            # Pular frontmatter
            if line.strip() == "---" and not in_content:
                in_content = True
                continue

            # Pular headings e linhas vazias no início
            if not in_content or line.strip().startswith("#") or not line.strip():
                if summary_lines:
                    break
                continue

            summary_lines.append(line.strip())
            if len(summary_lines) >= 3:
                break

        self.result["summary"] = " ".join(summary_lines)[:300]

    def _extract_key_concepts(self):
        """Extrai conceitos-chave baseado na categoria da tarefa."""
        patterns_by_category = {
            "trading": [
                r"\b(trading|trade|buy|sell|position|order|exchange|btc|bitcoin)\b",
                r"\b(strategy|signal|indicator|rsi|macd|bollinger)\b",
                r"\b(risk|profit|loss|drawdown|sharpe)\b",
            ],
            "agentes": [
                r"\b(agent|coordinator|langgraph|state|node|edge)\b",
                r"\b(mcp|tool|function|call|invoke)\b",
                r"\b(memory|context|prompt|llm|model)\b",
            ],
            "infraestrutura": [
                r"\b(deploy|deploy|systemd|docker|compose)\b",
                r"\b(service|unit|restart|start|stop|enable)\b",
                r"\b(server|host|ssh|nginx|proxy)\b",
            ],
            "monitoramento": [
                r"\b(grafana|dashboard|panel|metric)\b",
                r"\b(prometheus|alertmanager|alert|rule)\b",
                r"\b(log|trace|span|observability)\b",
            ],
            "documentação": [
                r"\b(wiki|page|document|readme|guide)\b",
                r"\b(section|heading|structure|format)\b",
                r"\b(link|reference|anchor|toc)\b",
            ],
            "automação": [
                r"\b(script|hook|pipeline|workflow|ci)\b",
                r"\b(automate|schedule|cron|trigger)\b",
                r"\b(tool|utility|helper|cli)\b",
            ],
            "testes": [
                r"\b(test|assert|expect|mock|fixture)\b",
                r"\b(pytest|unittest|coverage|regression)\b",
                r"\b(validate|verify|check|assert)\b",
            ],
            "segurança": [
                r"\b(security|secret|vault|token|key)\b",
                r"\b(auth|auth|permission|rbac|role)\b",
                r"\b(encrypt|hash|certificate|tls)\b",
            ],
        }

        # Usar padrões da categoria + padrões gerais
        patterns = patterns_by_category.get(self.task_category, [])
        patterns.extend([
            r"\b(Python|Rust|Go|TypeScript|PostgreSQL|Redis)\b",
            r"\b(MCP|LLM|Ollama|GPU|CPU|RAM)\b",
        ])

        terms = set()
        for pat in patterns:
            terms.update(re.findall(pat, self.content, re.IGNORECASE))

        self.result["key_concepts"] = sorted(terms)[:15]

    def _extract_decisions(self):
        """Extrai decisões relevantes para a tarefa."""
        decisions = RE_ADR.findall(self.content)
        self.result["decisions"] = [d.strip()[:100] for d in decisions[:5]]

    def _extract_action_items(self):
        """Extrai TODOs e itens de ação."""
        todos = RE_TODO.findall(self.content)
        self.result["action_items"] = [t.strip()[:100] for t in todos[:5]]

    def _extract_related_services(self):
        """Identifica serviços relacionados à tarefa."""
        service_patterns = [
            r"\b(shared-telegram-bot|shared-whatsapp-bot|github-agent)\b",
            r"\b(specialized-agents|coordinator-langgraph)\b",
            r"\b(btc-trading-agent|crypto-agent|trading-engine)\b",
            r"\b(grafana|prometheus|alertmanager|secrets-agent)\b",
            r"\b(cloudflared|nextcloud|wiki)\b",
        ]

        services = set()
        for pat in service_patterns:
            services.update(re.findall(pat, self.content, re.IGNORECASE))

        self.result["related_services"] = sorted(services)[:10]


# ── 3. Geração de Resumo de Tarefa ───────────────────────────────────────────

class TaskSummaryGenerator:
    """Gera resumo consolidado da tarefa para o agente wiki."""

    def __init__(
        self,
        task_category: str,
        staged_files: list[Path],
        py_files: list[Path],
        all_knowledge: list[dict[str, Any]],
        diff_summary: str,
    ):
        self.task_category = task_category
        self.staged_files = staged_files
        self.py_files = py_files
        self.all_knowledge = all_knowledge
        self.diff_summary = diff_summary

    def generate(self) -> dict[str, Any]:
        """Gera resumo consolidado."""
        # Consolidar conceitos
        all_concepts = set()
        for k in self.all_knowledge:
            all_concepts.update(k.get("key_concepts", []))

        # Consolidar serviços
        all_services = set()
        for k in self.all_knowledge:
            all_services.update(k.get("related_services", []))

        # Consolidar decisões
        all_decisions = []
        for k in self.all_knowledge:
            all_decisions.extend(k.get("decisions", []))

        # Gerar título da tarefa
        task_title = self._infer_task_title()

        return {
            "task_category": self.task_category,
            "task_title": task_title,
            "files_changed": len(self.staged_files) + len(self.py_files),
            "md_files": [str(f.name) for f in self.staged_files],
            "py_files": [str(f.name) for f in self.py_files],
            "key_concepts": sorted(all_concepts)[:20],
            "related_services": sorted(all_services)[:10],
            "decisions": all_decisions[:5],
            "diff_summary": self.diff_summary[:500],
        }

    def _infer_task_title(self) -> str:
        """Infere título da tarefa baseado nos arquivos."""
        if not self.staged_files and not self.py_files:
            return "Atualização diversas"

        # Usar primeiro .md como referência
        if self.staged_files:
            first_md = self.staged_files[0]
            try:
                content = first_md.read_text(encoding="utf-8", errors="replace")
                match = RE_HEADING.search(content)
                if match:
                    return match.group(2).strip()[:80]
            except Exception:
                pass

        # Fallback: usar nome do diretório
        if self.py_files:
            parent = self.py_files[0].parent.name
            return f"Atualização em {parent}"

        return "Atualização de documentação"


# ── Relatório ─────────────────────────────────────────────────────────────────

def _print_report(
    filepath: Path,
    errors: list[str],
    warnings: list[str],
    knowledge: dict[str, Any],
    verbose: bool,
):
    rel = filepath.relative_to(REPO_ROOT) if filepath.is_relative_to(REPO_ROOT) else filepath.name
    print(f"\n📄 {rel}")

    if errors:
        print(f"  ❌ Erros ({len(errors)}):")
        for e in errors:
            print(f"     - {e}")

    if warnings:
        print(f"  ⚠️  ({len(warnings)}):")
        for w in warnings:
            print(f"     - {w}")

    if verbose:
        title = knowledge.get("title", "")
        if title:
            print(f"  📌 Título: {title}")

        concepts = knowledge.get("key_concepts", [])
        if concepts:
            print(f"  🔑 Conceitos: {', '.join(concepts[:8])}")

        services = knowledge.get("related_services", [])
        if services:
            print(f"  🔧 Serviços: {', '.join(services[:5])}")

        decisions = knowledge.get("decisions", [])
        if decisions:
            print(f"  🎯 Decisões: {len(decisions)}")

    if not errors and not warnings:
        print("  ✅ OK")


def _print_task_summary(summary: dict[str, Any]):
    """Imprime resumo consolidado da tarefa."""
    print("\n" + "=" * 60)
    print("📋 RESUMO DA TAREFA")
    print("=" * 60)
    print(f"Categoria: {summary['task_category']}")
    print(f"Título:    {summary['task_title']}")
    print(f"Arquivos:  {summary['files_changed']} ({len(summary['md_files'])} .md, {len(summary['py_files'])} .py)")

    if summary["key_concepts"]:
        print(f"Conceitos: {', '.join(summary['key_concepts'][:10])}")

    if summary["related_services"]:
        print(f"Serviços:  {', '.join(summary['related_services'][:5])}")

    if summary["decisions"]:
        print(f"Decisões:  {len(summary['decisions'])} registradas")

    print("=" * 60)


# ── Persistência ──────────────────────────────────────────────────────────────

def _persist_task_context(summary: dict[str, Any], knowledge: list[dict[str, Any]]):
    """Salva contexto da tarefa para uso do agente wiki."""
    context_file = REPO_ROOT / "tools" / "hooks" / ".wiki_task_context.json"

    context = {
        "task": summary,
        "documents": knowledge,
    }

    try:
        context_file.write_text(json.dumps(context, indent=2, ensure_ascii=False))
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pré-análise de documentação focada na tarefa")
    parser.add_argument("--staged", action="store_true", help="Analisar apenas arquivos staged")
    parser.add_argument("--verbose", action="store_true", help="Saída detalhada")
    parser.add_argument("files", nargs="*", help="Arquivos específicos para analisar")
    args = parser.parse_args()

    # Coletar arquivos
    if args.files:
        md_files = [Path(f) for f in args.files if Path(f).exists() and f.endswith(".md")]
        py_files = []
    elif args.staged:
        md_files = _git_staged_files()
        py_files = _git_staged_python()
    else:
        print("ℹ️  Use --staged para analisar arquivos do commit atual")
        return 0

    if not md_files and not py_files:
        print("📭 Nenhum .md para analisar")
        return 0

    # Detectar categoria da tarefa
    task_category = _detect_task_category(md_files, py_files)
    diff_summary = _git_diff_summary()

    print(f"\n🔍 Analisando tarefa: {task_category.upper()}")

    all_knowledge = []
    has_errors = False

    # Analisar cada .md
    for filepath in md_files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"❌ Erro lendo {filepath}: {exc}")
            has_errors = True
            continue

        # Validação
        validator = StructuralValidator(content, filepath)
        errors, warnings = validator.validate()

        # Extração de conhecimento
        extractor = TaskKnowledgeExtractor(content, filepath, task_category)
        knowledge = extractor.extract()

        # Relatório
        _print_report(filepath, errors, warnings, knowledge, args.verbose)

        if errors:
            has_errors = True

        all_knowledge.append(knowledge)

    # Gerar resumo da tarefa
    summary_gen = TaskSummaryGenerator(
        task_category, md_files, py_files, all_knowledge, diff_summary
    )
    summary = summary_gen.generate()

    # Imprimir resumo
    _print_task_summary(summary)

    # Persistir contexto
    if all_knowledge:
        _persist_task_context(summary, all_knowledge)

    print()
    if has_errors:
        print("❌ Análise encontrou erros — commit bloqueado")
        return 1

    print("✅ Análise de tarefa concluída")
    return 0


if __name__ == "__main__":
    sys.exit(main())
