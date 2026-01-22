from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = "/tmp/streamlit_8501.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL, timeout=15000)
    page.screenshot(path=OUT, full_page=True)
    print('screenshot_saved:' + OUT)
    browser.close()
