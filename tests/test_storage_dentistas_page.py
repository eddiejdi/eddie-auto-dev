from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1] / "site"


def test_storage_dentistas_page_is_print_oriented_and_has_contact_info():
    html = (SITE_DIR / "storage-dentistas.html").read_text(encoding="utf-8")

    assert 'meta name="generator" content="Ollama phi4-mini + RPA4ALL"' in html
    assert "Panfleto RPA4ALL" in html
    assert "Pré-visualizar A4" in html
    assert "Pré-visualizar A5" in html
    assert "contato@rpa4all.com" in html
    assert "www.rpa4all.com" in html
    assert "assets/storage-images/dentistas/dental-visit.jpg" in html
    assert "applyPaperSize('a4')" in html
