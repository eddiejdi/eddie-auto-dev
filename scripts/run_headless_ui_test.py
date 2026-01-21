#!/usr/bin/env python3
"""Headless UI test: try Playwright, otherwise fallback to simple HTTP + API check.

Avoid direct SQLite access; use the interceptor API (Postgres-backed) instead.
"""
import time
import os
import sys
import requests
from urllib.parse import urljoin

DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'http://127.0.0.1:8501/')
INTERCEPTOR_API = os.environ.get('INTERCEPTOR_API', 'http://192.168.15.2:8503')
TEST_TEXT = os.environ.get('TEST_TEXT')


def latest_conversation_id_from_api(api_base: str):
    """Query the interceptor API for active conversations and return the newest id."""
    try:
        url = urljoin(api_base, '/interceptor/conversations/active')
        r = requests.get(url, timeout=5)
        if r.status_code != 200:
            return None
        data = r.json()
        convs = data.get('conversations') or []
        if not convs:
            return None
        # assume API returns conversations ordered by recency; otherwise pick max started_at
        return convs[0].get('id')
    except Exception:
        return None


def http_check_contains(conv_id: str):
    import requests
    try:
        r = requests.get(DASHBOARD_URL, timeout=5)
        if r.status_code != 200:
            print('Dashboard HTTP status:', r.status_code)
            return False
        html = r.text
        if conv_id and conv_id[:12] in html:
            print('Found conv id in HTML (prefix):', conv_id[:12])
            return True
        # try full id
        if conv_id and conv_id in html:
            print('Found conv id in HTML (full)')
            return True
        print('Conversation id not found in HTML')
        return False
    except Exception as e:
        print('HTTP check failed:', e)
        return False


def playwright_check(conv_id: str):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print('Playwright not available')
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(DASHBOARD_URL, timeout=10000)
            time.sleep(1)
            content = page.content()
            browser.close()
            found = conv_id and (conv_id[:12] in content or conv_id in content)
            print('Playwright found conv:', found)
            return found
    except Exception as e:
        print('Playwright run failed:', e)
        return False


if __name__ == '__main__':
    # Wait a short while for the dashboard to stabilize
    time.sleep(1)
    conv_id = latest_conversation_id_from_api(INTERCEPTOR_API)
    print('Latest conversation id from API:', conv_id)

    # If TEST_TEXT provided, prefer searching for it in the HTML
    if TEST_TEXT:
        print('Looking for TEST_TEXT in HTML:', TEST_TEXT)

    # Try Playwright first
    # Try Playwright first (checking TEST_TEXT if provided)
    pw = playwright_check(conv_id if not TEST_TEXT else TEST_TEXT)
    if pw is True:
        print('HEADLESS TEST: PASS (playwright)')
        sys.exit(0)
    # If playwright returned None (not installed), fall back
    if pw is None:
        ok = http_check_contains(TEST_TEXT if TEST_TEXT else conv_id)
        if ok:
            print('HEADLESS TEST: PASS (http-fallback)')
            sys.exit(0)
        else:
            print('HEADLESS TEST: FAIL (http-fallback)')
            sys.exit(2)
    else:
        if pw:
            print('HEADLESS TEST: PASS (playwright)')
            sys.exit(0)
        else:
            # Try HTTP fallback
            ok = http_check_contains(conv_id)
            if ok:
                print('HEADLESS TEST: PASS (http-fallback)')
                sys.exit(0)
            print('HEADLESS TEST: FAIL')
            sys.exit(3)
