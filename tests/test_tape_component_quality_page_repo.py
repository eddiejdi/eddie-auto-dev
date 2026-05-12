"""Valida o scaffold do repo da pagina Tape Component Quality."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tape-component-quality-page"


def test_repo_scaffold_exists() -> None:
    assert (ROOT / "README.md").exists()
    assert (ROOT / "index.html").exists()
    assert (ROOT / "styles.css").exists()
    assert (ROOT / "script.js").exists()
    assert (ROOT / ".github/workflows/deploy-pages.yml").exists()


def test_index_links_assets() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert 'href="styles.css"' in html
    assert 'src="script.js"' in html
    assert 'id="componentGrid"' in html


def test_workflow_deploys_github_pages() -> None:
    workflow = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")

    assert "actions/upload-pages-artifact@v3" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "permissions:" in workflow
