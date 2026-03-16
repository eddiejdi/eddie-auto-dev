from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1] / "site"


def test_conube_daily_report_page_exists_and_wires_api():
    html = (SITE_DIR / "conube-report.html").read_text(encoding="utf-8")

    assert "Relatório Diário Conube" in html
    assert "conube/reports/daily-summary" in html
    assert 'id="conubeDailyNarrative"' in html
    assert 'id="conubePendingItemsTable"' in html
    assert 'id="conubeRecommendedActions"' in html
