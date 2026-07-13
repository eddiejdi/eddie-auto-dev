#!/usr/bin/env python3
"""Coletor de notícias KuCoin para o RSS Sentiment Exporter.

A KuCoin não expõe feed RSS/XML público. Este módulo consome:
  - Flash news via sitemap XML (atualizado ~30 min)
  - Anúncios oficiais via API CMS JSON (/_api/cms/articles)

Retorna itens normalizados para conversão em NewsArticle pelo exporter.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

log = logging.getLogger("rss-sentiment.kucoin")

KUCOIN_BASE = "https://www.kucoin.com"
KUCOIN_FLASH_SITEMAP = KUCOIN_BASE + "/site-map_flash_{lang}_1.xml"
KUCOIN_CMS_API = KUCOIN_BASE + "/_api/cms/articles"
KUCOIN_ANNOUNCEMENT_BASE = KUCOIN_BASE + "/announcement"

FETCH_TIMEOUT = int(os.environ.get("KUCOIN_NEWS_FETCH_TIMEOUT", "30"))
FLASH_MAX = int(os.environ.get("KUCOIN_NEWS_FLASH_MAX", "50"))
ANNOUNCEMENTS_MAX = int(os.environ.get("KUCOIN_NEWS_ANNOUNCEMENTS_MAX", "20"))
SITEMAP_LANG = os.environ.get("KUCOIN_NEWS_SITEMAP_LANG", "en")

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class KuCoinNewsItem:
    """Item de notícia normalizado da KuCoin."""

    title: str
    url: str
    source: str
    published: datetime
    description: str = ""


def _http_get(url: str, timeout: int = FETCH_TIMEOUT) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "eddie-rss-sentiment/1.0 (+https://rpa4all.com)",
            "Accept": "application/json, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def slug_to_title(slug: str) -> str:
    """Converte slug de URL em título legível."""
    slug = slug.rstrip("/").split("/")[-1]
    words = [w for w in slug.split("-") if w]
    titled: List[str] = []
    for word in words:
        if word.isupper() or (len(word) <= 4 and word.isalpha()):
            titled.append(word.upper())
        elif word.isdigit():
            titled.append(word)
        else:
            titled.append(word.capitalize())
    return " ".join(titled)


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_publish_at(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return _parse_iso_datetime(value)


def _parse_unix_ts(value: object) -> Optional[datetime]:
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def fetch_flash_sitemap(lang: str = SITEMAP_LANG, max_items: int = FLASH_MAX) -> List[KuCoinNewsItem]:
    """Busca flash news a partir do sitemap XML da KuCoin."""
    url = KUCOIN_FLASH_SITEMAP.format(lang=lang)
    try:
        xml_text = _http_get(url)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("KuCoin flash sitemap indisponível (%s): %s", url, exc)
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.warning("KuCoin flash sitemap inválido: %s", exc)
        return []

    items: List[KuCoinNewsItem] = []
    for url_node in root.findall("sm:url", SITEMAP_NS):
        loc = (url_node.findtext("sm:loc", default="", namespaces=SITEMAP_NS) or "").strip()
        if not loc or "/news/flash/" not in loc:
            continue

        lastmod = url_node.findtext("sm:lastmod", default="", namespaces=SITEMAP_NS)
        published = _parse_iso_datetime(lastmod) or datetime.now(timezone.utc)
        slug = urlparse(loc).path.rstrip("/").split("/")[-1]
        title = slug_to_title(slug)

        items.append(
            KuCoinNewsItem(
                title=title,
                url=loc,
                source="kucoin_flash",
                published=published,
                description=title,
            )
        )

    items.sort(key=lambda item: item.published, reverse=True)
    return items[:max_items]


def fetch_cms_announcements(max_items: int = ANNOUNCEMENTS_MAX) -> List[KuCoinNewsItem]:
    """Busca anúncios oficiais via API CMS da KuCoin."""
    page_size = min(max(max_items, 1), 50)
    url = f"{KUCOIN_CMS_API}?page=1&pageSize={page_size}"
    try:
        payload = json.loads(_http_get(url))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        log.warning("KuCoin CMS API indisponível: %s", exc)
        return []

    if not payload.get("success") and payload.get("code") != 200:
        log.warning("KuCoin CMS API retornou erro: %s", payload.get("msg", payload))
        return []

    items: List[KuCoinNewsItem] = []
    for entry in payload.get("items") or []:
        title = (entry.get("title") or "").strip()
        path = (entry.get("path") or "").strip()
        if not title or not path:
            continue

        if not path.startswith("/"):
            path = "/" + path
        article_url = f"{KUCOIN_ANNOUNCEMENT_BASE}{path}"
        summary = (entry.get("summary") or title).strip()
        published = (
            _parse_unix_ts(entry.get("publish_ts"))
            or _parse_publish_at(entry.get("publish_at", ""))
            or datetime.now(timezone.utc)
        )

        items.append(
            KuCoinNewsItem(
                title=title,
                url=article_url,
                source="kucoin_announcements",
                published=published,
                description=summary[:1000],
            )
        )

    return items[:max_items]


def collect_kucoin_items(
    *,
    lang: str = SITEMAP_LANG,
    flash_max: int = FLASH_MAX,
    announcements_max: int = ANNOUNCEMENTS_MAX,
) -> List[KuCoinNewsItem]:
    """Consolida flash news e anúncios, deduplicando por URL."""
    seen_urls: set[str] = set()
    merged: List[KuCoinNewsItem] = []

    for fetcher, kwargs in (
        (fetch_flash_sitemap, {"lang": lang, "max_items": flash_max}),
        (fetch_cms_announcements, {"max_items": announcements_max}),
    ):
        for item in fetcher(**kwargs):
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            merged.append(item)

    merged.sort(key=lambda item: item.published, reverse=True)
    return merged