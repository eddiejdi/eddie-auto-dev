from __future__ import annotations

import re
from pathlib import Path

import requests


# Usar caminho relativo ao projeto para funcionar em qualquer ambiente (local, CI, etc)
SITE_INDEX = Path(__file__).parent.parent / "site" / "index.html"
IMG_SRC_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)


def _extract_remote_icon_urls() -> list[str]:
    html = SITE_INDEX.read_text(encoding="utf-8")
    urls = {
        url
        for url in IMG_SRC_PATTERN.findall(html)
        if url.startswith("http://") or url.startswith("https://")
    }
    return sorted(urls)


def test_all_remote_icons_return_http_200() -> None:
    """Todos os icones remotos do site devem responder HTTP 200."""
    icon_urls = _extract_remote_icon_urls()
    assert icon_urls, "Nenhum ícone remoto foi encontrado em site/index.html"

    session = requests.Session()
    failures: list[str] = []

    for url in icon_urls:
        try:
            response = session.get(url, timeout=20)
        except requests.RequestException as exc:
            failures.append(f"{url} -> erro de rede: {exc}")
            continue

        if response.status_code != 200:
            failures.append(f"{url} -> HTTP {response.status_code}")

    assert not failures, "Falhas encontradas nos ícones remotos:\n" + "\n".join(failures)
