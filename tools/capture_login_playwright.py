#!/usr/bin/env python3
from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright


def main():
    import os
    url = os.environ.get('VALIDATOR_URL', 'http://192.168.15.2:3000/auth?redirect=%2F')
    out_dir = Path("/tmp/playwright_capture")
    out_dir.mkdir(parents=True, exist_ok=True)
    har_path = out_dir / "capture.har"
    screenshot = out_dir / "page.png"
    log_path = out_dir / "network_log.txt"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(record_har_path=str(har_path))
        page = context.new_page()

        network_events = []

        def on_request(request):
            network_events.append(f"REQUEST {request.method} {request.url}")

        def on_response(response):
            try:
                network_events.append(f"RESPONSE {response.status} {response.url}")
            except Exception:
                network_events.append(f"RESPONSE ? {response.url}")

        page.on("request", on_request)
        page.on("response", on_response)

        print(f"navigating to {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)

        # Save initial screenshot
        page.screenshot(path=str(screenshot))

        # Try to find a login form and submit dummy credentials if present
        submitted = False
        try:
            # common selectors
            if page.query_selector('form'):
                form = page.query_selector('form')
                # try to fill inputs
                if page.query_selector('input[type=password]'):
                    page.fill('input[type=password]', 'tester')
                if page.query_selector('input[type=email]'):
                    page.fill('input[type=email]', 'tester@example.com')
                if page.query_selector('input[type=text]') and not page.query_selector('input[type=email]'):
                    page.fill('input[type=text]', 'tester')
                # submit
                try:
                    form.evaluate('f=>f.submit()')
                    submitted = True
                except Exception:
                    # try clicking submit button
                    btn = page.query_selector('button[type=submit]') or page.query_selector('button')
                    if btn:
                        btn.click()
                        submitted = True
        except Exception:
            pass

        # Wait a bit for any redirect messages to arrive
        time.sleep(3)

        # Capture navigation that may have happened
        current_url = page.url

        # Dump network events
        with open(log_path, "w") as f:
            f.write(f"initial_url: {url}\n")
            f.write(f"final_url: {current_url}\n")
            f.write(f"submitted_form: {submitted}\n\n")
            for e in network_events:
                f.write(e + "\n")

        print(f"wrote HAR to {har_path}")
        print(f"wrote screenshot to {screenshot}")
        print(f"wrote network log to {log_path}")

        context.close()
        browser.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('ERROR', e, file=sys.stderr)
        raise
