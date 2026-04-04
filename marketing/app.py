#!/usr/bin/env python3
"""Aplicação FastAPI do módulo Marketing RPA4ALL.

Servir com:
    uvicorn marketing.app:app --host 0.0.0.0 --port 8520

Ou via systemd: marketing-api.service
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from marketing.lead_capture_api import router as leads_router

logger = logging.getLogger("marketing.app")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

MARKETING_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="RPA4ALL Marketing API",
    description="API de captura de leads e automação de marketing",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.rpa4all.com",
        "https://rpa4all.com",
        "http://localhost:8520",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────────
app.include_router(leads_router)

# ─── Static files (imagens de ads) ───────────────────────────────────
ads_images = MARKETING_DIR / "ads" / "images"
if ads_images.exists():
    app.mount("/ads/images", StaticFiles(directory=str(ads_images)), name="ad-images")


# ─── Landing page ────────────────────────────────────────────────────
@app.get("/diagnostico", response_class=HTMLResponse)
async def landing_page():
    """Serve a landing page do diagnóstico gratuito."""
    html_path = MARKETING_DIR / "landing_diagnostico.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Página em construção</h1>", status_code=503)
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/storage", response_class=HTMLResponse)
async def landing_storage():
    """Serve a landing page do Storage Gerenciado."""
    html_path = MARKETING_DIR / "landing_storage.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Página em construção</h1>", status_code=503)
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/")
async def root():
    """Redireciona para a landing page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/diagnostico")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8520)
