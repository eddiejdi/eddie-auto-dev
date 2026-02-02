#!/usr/bin/env python3
"""Instrumented Selenium test to exercise the WebUI Bus Chat Bridge and capture network logs.
Saves screenshot, performance logs, and extracts any XHR responses to /api/v1/functions or /communication.
"""

import argparse
import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--save-dir", default="/tmp/bridge_test")
    parser.add_argument("--wait", type=int, default=4)
    args = parser.parse_args()

    save_dir = args.save_dir
    os.makedirs(save_dir, exist_ok=True)

    options = webdriver.ChromeOptions()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1000")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    try:
        driver.get(args.url)
        time.sleep(2)
        driver.save_screenshot(os.path.join(save_dir, "page_initial.png"))

        # Save page source for inspection
        with open(
            os.path.join(save_dir, "page_source.html"), "w", encoding="utf-8"
        ) as f:
            f.write(driver.page_source)

        # Try to find the "WebUI Bus Chat Bridge" element (normalize-space to avoid issues with nested nodes)
        found = False
        elems = driver.find_elements(
            By.XPATH, "//*[contains(normalize-space(.), 'WebUI Bus Chat Bridge')]"
        )
        # record snippets for debugging
        snippets = []
        for e in elems:
            try:
                snippets.append(
                    {
                        "tag": e.tag_name,
                        "text": e.text[:200],
                        "outer": (e.get_attribute("outerHTML") or "")[:800],
                    }
                )
            except Exception:
                pass
        save_json(os.path.join(save_dir, "bridge_candidates.json"), snippets)

        if elems:
            el = elems[0]
            try:
                el.location_once_scrolled_into_view
                el.click()
                found = True
            except Exception:
                pass

        # Fallback: try to open /functions page
        if not found:
            try:
                driver.get(args.url.rstrip("/") + "/api-docs")
                time.sleep(1)
                driver.save_screenshot(os.path.join(save_dir, "api_docs.png"))
            except Exception:
                pass

        # Try to find a chat input
        input_el = None
        for sel in [
            "textarea",
            "input[type='text']",
            "input[placeholder*='message']",
            "input[placeholder*='Message']",
        ]:
            try:
                input_el = driver.find_element(By.CSS_SELECTOR, sel)
                break
            except Exception:
                input_el = None
        if input_el:
            try:
                input_el.send_keys("Teste de debug do bridge\n")
            except Exception:
                pass
        time.sleep(args.wait)

        driver.save_screenshot(os.path.join(save_dir, "page_after_click.png"))

        # Collect performance logs
        logs = driver.get_log("performance")
        save_json(os.path.join(save_dir, "performance_raw.json"), logs)

        # Parse logs to find interesting network events
        interesting = []
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                method = msg.get("method")
                if method in ("Network.responseReceived", "Network.requestWillBeSent"):
                    params = msg.get("params", {})
                    request = params.get("request") or params.get("response") or {}
                    url = request.get("url") or params.get("response", {}).get("url")
                    status = params.get("response", {}).get("status")
                    if url and (
                        "/api/v1/functions" in url
                        or "/communication" in url
                        or "/api/chat" in url
                    ):
                        interesting.append(
                            {"method": method, "url": url, "status": status, "raw": msg}
                        )
            except Exception:
                pass

        save_json(os.path.join(save_dir, "interesting_network.json"), interesting)

        print("Saved artifacts to", save_dir)
        print("Found", len(interesting), "interesting network events")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
