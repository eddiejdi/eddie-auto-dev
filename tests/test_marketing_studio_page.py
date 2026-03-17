from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1] / "site"


def test_marketing_studio_page_exists_and_wires_authenticated_api():
    html = (SITE_DIR / "marketing-studio.html").read_text(encoding="utf-8")
    js = (SITE_DIR / "marketing-studio.js").read_text(encoding="utf-8")

    assert "Estúdio Comercial" in html
    assert "businessCardForm" in html
    assert "marketingFlyerForm" in html
    assert "marketingArtboardCanvas" in html
    assert "businessCardFrontCanvas" in html
    assert "businessCardBackCanvas" in html
    assert "marketing-studio-icon.svg" in html
    assert "marketing-studio.js" in html
    assert "marketing/studio/generate" in js
    assert "marketing/profile" in js
    assert "window.location.origin.replace(/\\/$/, '') + '/agents-api'" in js
