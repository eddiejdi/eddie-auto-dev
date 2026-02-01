#!/usr/bin/env python3
"""Capture a headless screenshot of local Open WebUI.

Saves PNG to /tmp/openwebui_screenshot.png
"""

import asyncio
import os


async def capture(
    url: str = "http://127.0.0.1:3000/", out: str = "/tmp/openwebui_screenshot.png"
):
    from pyppeteer import launch

    browser = await launch(args=["--no-sandbox"])
    page = await browser.newPage()
    await page.setViewport({"width": 1400, "height": 900})
    await page.goto(url, {"waitUntil": "networkidle2", "timeout": 30000})
    # give some extra time for client JS to render
    await asyncio.sleep(1)
    await page.screenshot({"path": out, "fullPage": True})
    await browser.close()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", default=os.environ.get("OPENWEBUI_URL", "http://127.0.0.1:3000/")
    )
    parser.add_argument("--out", default="/tmp/openwebui_screenshot.png")
    args = parser.parse_args()
    try:
        asyncio.run(capture(args.url, args.out))
    except KeyboardInterrupt:
        print("Interrupted")


if __name__ == "__main__":
    main()
