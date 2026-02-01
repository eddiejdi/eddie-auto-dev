#!/usr/bin/env python3
"""Open Streamlit dashboard, click homelab fetch button, and check for TEST_TEXT."""

import os
import time
import sys

from playwright.sync_api import sync_playwright

DASHBOARD_URL = os.environ.get(
    "DASHBOARD_URL", "https://heights-treasure-auto-phones.trycloudflare.com/"
)
TEST_TEXT = os.environ.get("TEST_TEXT")


def main():
    if not TEST_TEXT:
        print("TEST_TEXT env var required")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(DASHBOARD_URL, timeout=30000)
        # Give Streamlit a moment
        time.sleep(1)
        # Try clicking the sidebar button that starts a UI test conversation.
        try:
            if page.locator("text=Iniciar conversa de teste").count() > 0:
                page.get_by_text("Iniciar conversa de teste").click()
            elif page.locator("text=▶️ Iniciar conversa de teste").count() > 0:
                page.get_by_text("▶️ Iniciar conversa de teste").click()
        except Exception as e:
            print("Start-test click failed:", e)

        # Also try clicking the sidebar button that triggers homelab fetch (if present).
        try:
            if page.locator("text=Buscar conversas do homelab").count() > 0:
                page.get_by_text("Buscar conversas do homelab").click()
            elif page.locator("text=Buscar conversas").count() > 0:
                page.get_by_text("Buscar conversas").click()
            else:
                # try the arrow-prefixed label
                if page.locator("text=↗️ Buscar conversas do homelab").count() > 0:
                    page.get_by_text("↗️ Buscar conversas do homelab").click()
        except Exception as e:
            print("Homelab click attempt failed:", e)

        # Wait for the test text to appear in the page
        try:
            locator = page.locator(f'text="{TEST_TEXT}"')
            locator.wait_for(timeout=15000)
            print("FOUND:", TEST_TEXT)
            browser.close()
            return 0
        except Exception:
            # also try checking the full content as fallback
            content = page.content()
            if TEST_TEXT in content:
                print("FOUND in content:", TEST_TEXT)
                browser.close()
                return 0
            print("NOT FOUND")
            browser.close()
            return 3


if __name__ == "__main__":
    sys.exit(main())
