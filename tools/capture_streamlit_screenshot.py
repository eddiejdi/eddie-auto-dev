from playwright.sync_api import sync_playwright
import os

# Use environment variable when available so public pages can point to the
# external tunnel. Falls back to localhost for local dev.
URL = os.environ.get('INTERCEPTOR_PUBLIC_URL', os.environ.get('DASHBOARD_URL', 'http://localhost:8501'))
OUT = os.environ.get('STREAMLIT_SCREENSHOT_OUT', '/tmp/streamlit_8501.png')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, timeout=15000)
    page.screenshot(path=OUT, full_page=True)
    print('screenshot_saved:' + OUT)
    browser.close()
