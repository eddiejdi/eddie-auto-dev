from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_module(monkeypatch):
    monkeypatch.setenv("AUTHENTIK_URL", "https://auth.example.test")
    monkeypatch.setenv("AUTHENTIK_TOKEN", "test-token")

    import specialized_agents.marketing_assets as marketing_assets

    return importlib.reload(marketing_assets)


def _build_client(module):
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app, raise_server_exceptions=False)


def test_marketing_profile_uses_authentik_headers(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    response = client.get(
        "/marketing/profile",
        headers={
            "X-authentik-username": "edenilson",
            "X-authentik-email": "edenilson@rpa4all.com",
            "X-authentik-name": "Edenilson Teixeira",
            "X-authentik-groups": "Admins, Comercial",
        },
    )

    assert response.status_code == 200
    payload = response.json()["profile"]
    assert payload["username"] == "edenilson"
    assert payload["email"] == "edenilson@rpa4all.com"
    assert payload["name"] == "Edenilson Teixeira"
    assert "Comercial" in payload["groups"]


def test_marketing_generate_flyer_returns_brief_and_images(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    def fake_generate(prompt, model=None):
        if "agente de pesquisa comercial e visual" in prompt:
            return {
                "market_context": "Clínicas precisam reduzir retrabalho e aumentar previsibilidade.",
                "pain_points": ["retrabalho", "baixa previsibilidade", "atendimento manual"],
                "value_angles": ["Storage", "IA", "Observabilidade"],
                "visual_keywords": ["clinica", "consultorio", "atendimento", "tecnologia"],
                "search_queries": ["clinica medica", "consultorio", "medical office"],
                "business_card_focus": "RPA4ALL para saúde",
                "image_style": "fotografia corporativa em ambiente clínico",
                "color_hint": "azul e verde",
                "notes_summary": "nota",
                "_ollama_host": "http://127.0.0.1:11434",
                "_ollama_model": "phi4-mini:latest",
            }
        if "agente de raciocínio comercial" in prompt:
            return {
                "positioning": "Eficiência operacional com IA e observabilidade para clínicas.",
                "message_strategy": "Abrir com dor e fechar com diagnóstico.",
                "proof_points": ["Storage", "IA", "Observabilidade"],
                "cta_rationale": "Chamar para proposta curta.",
                "flyer_layout": "headline à esquerda e imagem à direita",
                "business_card_layout": "frente com nome e verso com contatos",
                "flyer_format": "poster-portrait",
                "card_tone": "Executivo",
                "_ollama_host": "http://127.0.0.1:11434",
                "_ollama_model": "phi4-mini:latest",
            }
        return {
            "headline": "Storage e IA para clínicas",
            "subheadline": "Operação mais previsível.",
            "intro": "Texto gerado.",
            "offer_title": "O que entregamos",
            "offer_bullets": ["Storage", "IA", "Observabilidade", "Automação"],
            "image_queries": ["clinica medica", "consultorio"],
            "cta_primary": "Solicitar proposta",
            "cta_secondary": "Agendar conversa",
            "business_card_tagline": "RPA4ALL para saúde",
            "business_card_back_note": "Observabilidade e IA para clínicas.",
            "audience_label": "Saúde",
            "notes_summary": "nota",
            "visual_direction": "Fotografia corporativa em ambiente clínico",
            "canvas_prompt": "Headline forte e imagem lateral",
            "_ollama_host": "http://127.0.0.1:11434",
            "_ollama_model": "phi4-mini:latest",
        }

    monkeypatch.setattr(module, "_generate_ollama_json", fake_generate)
    monkeypatch.setattr(
        module,
        "_search_wikimedia_images",
        lambda queries, limit=6: [
            {
                "query": queries[0],
                "title": "Medical office",
                "image_url": "https://images.example.test/office.jpg",
                "source_page": "https://commons.example.test/file",
                "author": "Author",
                "license": "CC BY 4.0",
            }
        ],
    )

    response = client.post(
        "/marketing/studio/generate",
        json={"theme": "clinicas medicas", "audience": "saude privada", "notes": "priorizar storage"},
        headers={
            "X-authentik-username": "edenilson",
            "X-authentik-email": "edenilson@rpa4all.com",
            "X-authentik-name": "Edenilson Teixeira",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["theme"] == "clinicas medicas"
    assert payload["brief"]["headline"] == "Storage e IA para clínicas"
    assert payload["brief"]["business_card_back_note"] == "Observabilidade e IA para clínicas."
    assert payload["research"]["market_context"] == "Clínicas precisam reduzir retrabalho e aumentar previsibilidade."
    assert payload["reasoning"]["positioning"] == "Eficiência operacional com IA e observabilidade para clínicas."
    assert payload["agent_sources"] == {"research": "ollama", "reasoning": "ollama", "brief": "ollama"}
    assert payload["narrative_source"] == "ollama"
    assert payload["image_research"]["provider"] == "wikimedia_commons"
    assert payload["image_research"]["items"][0]["title"] == "Medical office"
    assert payload["profile"]["email"] == "edenilson@rpa4all.com"


def test_marketing_generate_flyer_requires_theme(monkeypatch):
    module = _load_module(monkeypatch)
    client = _build_client(module)

    response = client.post("/marketing/studio/generate", json={"theme": "   "})

    assert response.status_code == 400
    assert "Informe um tema" in response.json()["detail"]
