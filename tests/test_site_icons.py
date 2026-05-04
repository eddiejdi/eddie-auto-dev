from __future__ import annotations

import re
from pathlib import Path

import pytest
import requests


# Usar caminho relativo ao projeto para funcionar em qualquer ambiente (local, CI, etc)
SITE_INDEX = Path(__file__).parent.parent / "site" / "index.html"
IMG_SRC_PATTERN = re.compile(r'<img[^>]+src="([^"]+)"', re.IGNORECASE)

# CDNs conhecidos que retornam 403 para bots/CI (não é erro de arquivo ausente)
_CDN_BOT_BLOCK_ALLOWLIST = frozenset([
    "cdn.simpleicons.org",
])


def _extract_remote_icon_urls() -> list[str]:
    html = SITE_INDEX.read_text(encoding="utf-8")
    urls = {
        url
        for url in IMG_SRC_PATTERN.findall(html)
        if url.startswith("http://") or url.startswith("https://")
    }
    return sorted(urls)


def _cdn_blocks_bots(url: str) -> bool:
    from urllib.parse import urlparse
    return urlparse(url).netloc in _CDN_BOT_BLOCK_ALLOWLIST


def test_all_remote_icons_return_http_200() -> None:
    """Todos os icones remotos do site devem responder HTTP 200.

    CDNs que bloqueiam bots com 403 (ex: cdn.simpleicons.org) são aceitos
    pois o bloqueio é de acesso de CI, não ausência do recurso.
    """
    icon_urls = _extract_remote_icon_urls()
    assert icon_urls, "Nenhum ícone remoto foi encontrado em site/index.html"

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; site-validator/1.0)"})
    failures: list[str] = []

    for url in icon_urls:
        try:
            response = session.get(url, timeout=20)
        except requests.RequestException as exc:
            failures.append(f"{url} -> erro de rede: {exc}")
            continue

        # 403 em CDNs conhecidos por bloquear bots = aceitável
        if response.status_code == 403 and _cdn_blocks_bots(url):
            continue

        if response.status_code != 200:
            failures.append(f"{url} -> HTTP {response.status_code}")

    assert not failures, "Falhas encontradas nos ícones remotos:\n" + "\n".join(failures)
