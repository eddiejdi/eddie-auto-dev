#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import socket
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import BrowserContext, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import specialized_agents.marketing_assets as marketing_assets
from specialized_agents.marketing_assets import router as marketing_router

SITE_DIR = ROOT / "site"
OUTPUT_ROOT = ROOT / "test-evidence" / "marketing-studio-examples"
VALIDATION_OLLAMA_TIMEOUT = 20
VALIDATION_OLLAMA_HOSTS = ["http://192.168.15.2:11434"]

AUTH_HEADERS = {
    "X-authentik-username": "edenilson",
    "X-authentik-email": "edenilson@rpa4all.com",
    "X-authentik-name": "Edenilson Teixeira",
    "X-authentik-groups": "Admins,Comercial",
}

EXAMPLES = [
    {
        "slug": "odontologia-premium",
        "theme": "odontologia premium",
        "audience": "clinicas odontologicas premium",
        "notes": "priorizar atendimento, agenda, storage de documentos e IA no pre-atendimento",
        "preset": "portrait",
        "flyer_adjustments": {"layer": "headline", "x": 84, "y": 128, "scale": 108, "opacity": 100},
        "card_adjustments": {"side": "front", "layer": "name", "x": 96, "y": 226, "scale": 104, "opacity": 100},
    },
    {
        "slug": "advocacia-empresarial",
        "theme": "advocacia empresarial",
        "audience": "escritorios juridicos com foco corporativo",
        "notes": "destacar triagem documental, observabilidade e automacao de fluxos internos",
        "preset": "square",
        "flyer_adjustments": {"layer": "cta", "x": 86, "y": 902, "scale": 112, "opacity": 100},
        "card_adjustments": {"side": "back", "layer": "specialties", "x": 540, "y": 170, "scale": 106, "opacity": 100},
    },
    {
        "slug": "logistica-transporte",
        "theme": "logistica e transporte",
        "audience": "operadores logisticos e transportadoras",
        "notes": "foco em SLA, visibilidade operacional, atendimento e dashboards executivos",
        "preset": "story",
        "flyer_adjustments": {"layer": "image", "x": 510, "y": 122, "scale": 110, "opacity": 96},
        "card_adjustments": {"side": "front", "layer": "tagline", "x": 72, "y": 404, "scale": 106, "opacity": 100},
    },
]


def slugify(value: str) -> str:
    return (
        value.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(":", "-")
        .replace(",", "")
        .replace(".", "")
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def decode_data_url(data_url: str) -> bytes:
    _, encoded = data_url.split(",", 1)
    return base64.b64decode(encoded)


def build_preview_app() -> FastAPI:
    api_app = FastAPI(title="Marketing Studio Preview API")
    api_app.include_router(marketing_router)

    @api_app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = FastAPI(title="Marketing Studio Preview")
    app.mount("/agents-api", api_app)
    app.mount("/", StaticFiles(directory=str(SITE_DIR), html=True), name="site")
    return app


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class PreviewServer:
    port: int
    server: uvicorn.Server
    thread: threading.Thread

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


def start_preview_server() -> PreviewServer:
    marketing_assets.OLLAMA_REQUEST_TIMEOUT = VALIDATION_OLLAMA_TIMEOUT
    marketing_assets._candidate_ollama_hosts = lambda: VALIDATION_OLLAMA_HOSTS[:]
    marketing_assets.logger.disabled = True
    app = build_preview_app()
    port = reserve_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return PreviewServer(port=port, server=server, thread=thread)
        except OSError:
            time.sleep(0.1)

    raise RuntimeError("Preview server did not start")


def canvas_hash(page: Page, selector: str) -> str:
    data_url = page.locator(selector).evaluate("el => el.toDataURL('image/png')")
    return data_url[:64] + str(len(data_url))


def set_range(page: Page, selector: str, value: int) -> None:
    page.locator(selector).evaluate(
        """(el, nextValue) => {
            el.value = String(nextValue);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        value,
    )


def apply_flyer_adjustments(page: Page, preset: str, adjustments: dict[str, Any]) -> tuple[str, str]:
    page.select_option("#marketingCanvasPreset", preset)
    page.select_option("#marketingCanvasLayer", adjustments["layer"])
    before_hash = canvas_hash(page, "#marketingArtboardCanvas")
    set_range(page, "#marketingCanvasX", int(adjustments["x"]))
    set_range(page, "#marketingCanvasY", int(adjustments["y"]))
    set_range(page, "#marketingCanvasScale", int(adjustments["scale"]))
    set_range(page, "#marketingCanvasOpacity", int(adjustments["opacity"]))
    page.wait_for_timeout(300)
    after_hash = canvas_hash(page, "#marketingArtboardCanvas")
    return before_hash, after_hash


def apply_card_adjustments(page: Page, adjustments: dict[str, Any]) -> tuple[str, str]:
    page.select_option("#businessCardEditorSide", adjustments["side"])
    page.select_option("#businessCardLayer", adjustments["layer"])
    active_canvas = "#businessCardBackCanvas" if adjustments["side"] == "back" else "#businessCardFrontCanvas"
    before_hash = canvas_hash(page, active_canvas)
    set_range(page, "#businessCardX", int(adjustments["x"]))
    set_range(page, "#businessCardY", int(adjustments["y"]))
    set_range(page, "#businessCardScale", int(adjustments["scale"]))
    set_range(page, "#businessCardOpacity", int(adjustments["opacity"]))
    page.wait_for_timeout(300)
    after_hash = canvas_hash(page, active_canvas)
    return before_hash, after_hash


def export_canvas(page: Page, selector: str, destination: Path) -> None:
    data_url = page.locator(selector).evaluate("el => el.toDataURL('image/png')")
    destination.write_bytes(decode_data_url(data_url))


def run_example(context: BrowserContext, base_url: str, example: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    page = context.new_page()
    page.set_default_timeout(180_000)
    page.goto(f"{base_url}/marketing-studio.html", wait_until="domcontentloaded")
    page.wait_for_selector("#marketingArtboardCanvas")
    page.wait_for_selector("#businessCardFrontCanvas")

    page.fill("#marketingTheme", example["theme"])
    page.fill("#marketingAudience", example["audience"])
    page.fill("#marketingNotes", example["notes"])

    with page.expect_response(
        lambda response: response.url.endswith("/agents-api/marketing/studio/generate")
        and response.request.method == "POST"
    ) as response_info:
        page.click("button[type='submit']")

    response = response_info.value
    payload = response.json()
    page.wait_for_selector("#marketingStudioStatus[data-mode='success']")
    page.wait_for_timeout(1200)

    image_buttons = page.locator("[data-image-index]")
    image_count = image_buttons.count()
    if image_count > 1:
        image_buttons.nth(1).click()
        page.wait_for_timeout(500)

    flyer_before, flyer_after = apply_flyer_adjustments(page, example["preset"], example["flyer_adjustments"])
    card_before, card_after = apply_card_adjustments(page, example["card_adjustments"])

    export_canvas(page, "#marketingArtboardCanvas", output_dir / "flyer.png")
    export_canvas(page, "#businessCardFrontCanvas", output_dir / "business-card-front.png")
    export_canvas(page, "#businessCardBackCanvas", output_dir / "business-card-back.png")
    page.screenshot(path=str(output_dir / "page.png"), full_page=True)

    headline = (page.text_content("#marketingFlyerHeadline") or "").strip()
    selected_image_title = ""
    if image_count:
        selected_locator = page.locator(".marketing-image-card.is-selected strong")
        if selected_locator.count():
            selected_image_title = (selected_locator.text_content() or "").strip()

    validation = {
        "slug": example["slug"],
        "theme": example["theme"],
        "audience": example["audience"],
        "headline": headline,
        "narrative_source": payload.get("narrative_source"),
        "agent_sources": payload.get("agent_sources"),
        "image_count": len(((payload.get("image_research") or {}).get("items") or [])),
        "browser_image_count": image_count,
        "selected_image_title": selected_image_title,
        "flyer_canvas_changed": flyer_before != flyer_after,
        "business_card_canvas_changed": card_before != card_after,
        "status_text": (page.text_content("#marketingStudioStatus") or "").strip(),
        "offer_source_text": (page.text_content("#marketingOfferSource") or "").strip(),
        "research_source_text": (page.text_content("#marketingResearchSource") or "").strip(),
        "reasoning_source_text": (page.text_content("#marketingReasoningSource") or "").strip(),
        "saved_files": [
            "payload.json",
            "validation.json",
            "flyer.png",
            "business-card-front.png",
            "business-card-back.png",
            "page.png",
        ],
    }

    if payload.get("status") != "ok":
        raise RuntimeError(f"Generation failed for {example['slug']}: {payload}")
    if not headline:
        raise RuntimeError(f"Headline missing for {example['slug']}")
    if not validation["flyer_canvas_changed"]:
        raise RuntimeError(f"Flyer canvas did not change after adjustments for {example['slug']}")
    if not validation["business_card_canvas_changed"]:
        raise RuntimeError(f"Business card canvas did not change after adjustments for {example['slug']}")

    write_json(output_dir / "payload.json", payload)
    write_json(output_dir / "validation.json", validation)
    page.close()
    return validation


def write_summary(run_dir: Path, validations: list[dict[str, Any]]) -> None:
    lines = [
        "# Marketing Studio Examples",
        "",
        f"Gerado em: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Exemplo | Fonte narrativa | Imagens | Canvas flyer | Canvas cartao | Arquivos |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in validations:
        lines.append(
            "| {slug} | {narrative_source} | {image_count} | {flyer_canvas_changed} | {business_card_canvas_changed} | {files} |".format(
                slug=item["slug"],
                narrative_source=item["narrative_source"],
                image_count=item["image_count"],
                flyer_canvas_changed="ok" if item["flyer_canvas_changed"] else "falhou",
                business_card_canvas_changed="ok" if item["business_card_canvas_changed"] else "falhou",
                files=", ".join(item["saved_files"]),
            )
        )
    (run_dir / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(run_dir / "summary.json", {"examples": validations})

def main() -> int:
    run_dir = OUTPUT_ROOT / time.strftime("%Y-%m-%d_%H-%M-%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    validations: list[dict[str, Any]] = []

    server = start_preview_server()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1600, "height": 2200},
                extra_http_headers=AUTH_HEADERS,
            )
            for example in EXAMPLES:
                example_dir = run_dir / slugify(example["slug"])
                example_dir.mkdir(parents=True, exist_ok=True)
                print(f"[run] {example['slug']} -> {example_dir}")
                validation = run_example(context, server.base_url, example, example_dir)
                validations.append(validation)
            browser.close()

        write_summary(run_dir, validations)
    finally:
        server.stop()

    print(f"[done] exemplos salvos em {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
