#!/usr/bin/env python3
"""Testes unitários para o coletor de notícias KuCoin."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

_FETCHER_PATH = (
    Path(__file__).parent.parent / "grafana" / "exporters" / "kucoin_news_fetcher.py"
)
_spec = importlib.util.spec_from_file_location("kucoin_news_fetcher", str(_FETCHER_PATH))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["kucoin_news_fetcher"] = _mod
_spec.loader.exec_module(_mod)

KuCoinNewsItem = _mod.KuCoinNewsItem
slug_to_title = _mod.slug_to_title
fetch_flash_sitemap = _mod.fetch_flash_sitemap
fetch_cms_announcements = _mod.fetch_cms_announcements
collect_kucoin_items = _mod.collect_kucoin_items


SAMPLE_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.kucoin.com/news/flash/bitcoin-etfs-end-8-week-redemption-streak-with-197m-inflow</loc>
    <lastmod>2026-07-12T14:55:03Z</lastmod>
  </url>
  <url>
    <loc>https://www.kucoin.com/news/flash/dogecoin-price-jumps-7-despite-zero-spot-etf-inflows</loc>
    <lastmod>2026-07-12T20:44:38Z</lastmod>
  </url>
</urlset>"""

SAMPLE_CMS = {
    "success": True,
    "code": 200,
    "items": [
        {
            "title": "KuCoin Will Delist BTC Trading Pair",
            "summary": "Delisting notice for maintenance.",
            "path": "/en-kucoin-will-delist-btc",
            "publish_at": "2026-07-12 23:02:00",
            "publish_ts": 1783868520,
        }
    ],
}


class TestSlugToTitle:
    def test_converte_slug_flash(self) -> None:
        title = slug_to_title(
            "bitcoin-etfs-end-8-week-redemption-streak-with-197m-inflow"
        )
        assert "Bitcoin" in title
        assert "197m" in title.lower() or "197M" in title

    def test_converte_path_completo(self) -> None:
        title = slug_to_title(
            "/news/flash/ethereum-whales-add-20-6m-in-eth-amid-price-stability"
        )
        assert "Ethereum" in title


class TestFetchFlashSitemap:
    @patch.object(_mod, "_http_get", return_value=SAMPLE_SITEMAP)
    def test_parseia_urls_flash(self, _mock_get) -> None:
        items = fetch_flash_sitemap(lang="en", max_items=10)
        assert len(items) == 2
        assert items[0].source == "kucoin_flash"
        assert "dogecoin" in items[0].url
        assert items[0].published.tzinfo == timezone.utc

    @patch.object(_mod, "_http_get", side_effect=TimeoutError("timeout"))
    def test_erro_rede_retorna_vazio(self, _mock_get) -> None:
        assert fetch_flash_sitemap() == []


class TestFetchCmsAnnouncements:
    @patch.object(_mod, "_http_get", return_value=json.dumps(SAMPLE_CMS))
    def test_parseia_anuncios(self, _mock_get) -> None:
        items = fetch_cms_announcements(max_items=5)
        assert len(items) == 1
        assert items[0].source == "kucoin_announcements"
        assert items[0].url.endswith("/announcement/en-kucoin-will-delist-btc")
        assert "Delisting" in items[0].description

    @patch.object(_mod, "_http_get", return_value='{"success": false, "code": 500}')
    def test_api_erro_retorna_vazio(self, _mock_get) -> None:
        assert fetch_cms_announcements() == []


class TestCollectKucoinItems:
    @patch.object(_mod, "fetch_cms_announcements")
    @patch.object(_mod, "fetch_flash_sitemap")
    def test_deduplica_por_url(self, mock_flash, mock_cms) -> None:
        shared_url = "https://www.kucoin.com/news/flash/shared-item"
        mock_flash.return_value = [
            KuCoinNewsItem(
                title="Shared",
                url=shared_url,
                source="kucoin_flash",
                published=datetime(2026, 7, 12, 20, 0, tzinfo=timezone.utc),
            )
        ]
        mock_cms.return_value = [
            KuCoinNewsItem(
                title="Other",
                url="https://www.kucoin.com/announcement/en-other",
                source="kucoin_announcements",
                published=datetime(2026, 7, 12, 19, 0, tzinfo=timezone.utc),
            ),
            KuCoinNewsItem(
                title="Dup",
                url=shared_url,
                source="kucoin_announcements",
                published=datetime(2026, 7, 12, 18, 0, tzinfo=timezone.utc),
            ),
        ]

        items = collect_kucoin_items()
        assert len(items) == 2
        assert items[0].url == shared_url