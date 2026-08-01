"""Testes do roteamento persona NSFW (eddie-persona-free) no WhatsApp bot."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "misc" / "whatsapp_bot.py"


def _load_module():
    module_name = "whatsapp_bot_persona_nsfw_tests"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached

    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_extras = types.ModuleType("psycopg2.extras")
    fake_pool = types.ModuleType("psycopg2.pool")
    fake_aiohttp = types.ModuleType("aiohttp")

    class _FakePool:
        def __init__(self, *args, **kwargs):
            pass

    fake_extras.RealDictCursor = object
    fake_pool.SimpleConnectionPool = _FakePool
    fake_aiohttp.web = types.SimpleNamespace()

    sys.modules.setdefault("psycopg2", fake_psycopg2)
    sys.modules.setdefault("psycopg2.extras", fake_extras)
    sys.modules.setdefault("psycopg2.pool", fake_pool)
    sys.modules.setdefault("aiohttp", fake_aiohttp)

    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_is_nsfw_free_contact_matches_phone_and_lid():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    assert bot.is_nsfw_free_contact("5511986117521@c.us")
    assert bot.is_nsfw_free_contact("11986117521")
    assert bot.is_nsfw_free_contact("68371752194106@lid")
    assert bot.is_nsfw_free_contact("Fernanda Baldi")
    assert bot.is_nsfw_free_contact("5511981193899")  # dono / self-chat
    assert not bot.is_nsfw_free_contact("5511999999999@c.us")


def test_resolve_chat_model_nsfw_priority_over_phone_mapping():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    # Dono está no PHONE_MODEL_MAPPING → shared-homelab, mas allowlist NSFW vence
    model = bot.resolve_chat_model(
        sender="5511981193899@c.us",
        chat_id="5511981193899@c.us",
        nsfw_contact=True,
        is_owner=True,
    )
    assert model == mod.PERSONA_MODEL_FREE


def test_resolve_chat_model_owner_without_nsfw_uses_homelab_mapping(monkeypatch):
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)
    monkeypatch.setattr(mod, "PERSONA_MODE", "auto")

    model = bot.resolve_chat_model(
        sender="5511981193899@c.us",
        chat_id="5511981193899@c.us",
        nsfw_contact=False,
        is_owner=True,
    )
    assert model == "shared-homelab"


def test_resolve_chat_model_third_party_uses_whatsapp():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    model = bot.resolve_chat_model(
        sender="5511999999999@c.us",
        chat_id="5511999999999@c.us",
        nsfw_contact=False,
        is_owner=False,
    )
    assert model == "shared-whatsapp"


def test_nsfw_system_prompt_liberates_hardcore():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    prompt = bot.get_system_prompt("assistant", is_owner=True, nsfw_contact=True)
    pl = prompt.lower()
    assert "obediente" in pl or "obede" in pl
    assert "mulher" in pl or "baldi" in pl
    assert "nunca" in pl and "menores" in pl
    assert "não posso te ajudar" in pl or "nao possa" in pl or "recus" in pl or "obede" in pl

    safe = bot.get_system_prompt("assistant", is_owner=True, nsfw_contact=False)
    assert "baldi" not in safe.lower()


def test_limpar_command_aliases():
    mod = _load_module()
    assert "/limpar" in (
        "/limpar",
        "/clear",
        "/reset",
        "limpar",
        "limpar historico",
        "limpar histórico",
    )
    # ConversationDB aliases cover self-chat LID
    aliases = mod.ConversationDB._chat_id_aliases("5511981193899@c.us")
    assert "143430516752629@lid" in aliases
    assert "5511981193899@c.us" in aliases


def test_self_chat_recognizes_owner_lid():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    assert bot.is_self_chat("5511981193899@c.us")
    assert bot.is_self_chat("143430516752629@lid")
    assert bot.is_owner("143430516752629@lid")
    assert bot.canonical_chat_id("143430516752629@lid") == "5511981193899@c.us"
    assert bot.canonical_chat_id("68371752194106@lid") == "5511986117521@c.us"
    assert not bot.is_self_chat("68371752194106@lid")
    # dono falando COM Fernanda: peer=Fernanda NÃO é self (mesmo se sender=dono)
    assert not bot.is_self_chat("68371752194106@lid", "5511981193899@c.us")
    assert bot.canonical_chat_id("68371752194106@lid", "5511981193899@c.us") == "5511986117521@c.us"


def test_resolve_remote_peer_isolates_fernanda_from_self():
    mod = _load_module()
    # fromMe dono → Fernanda: peer é o `to`, não o `from`
    peer = mod.WhatsAppBot.resolve_remote_peer(
        {
            "from": "5511981193899@c.us",
            "to": "68371752194106@lid",
            "fromMe": True,
        },
        from_me=True,
    )
    assert peer == "68371752194106@lid"

    # entrante Fernanda → dono
    peer2 = mod.WhatsAppBot.resolve_remote_peer(
        {
            "from": "68371752194106@lid",
            "to": "5511981193899@c.us",
            "fromMe": False,
        },
        from_me=False,
    )
    assert peer2 == "68371752194106@lid"

    # self-chat fromMe
    peer3 = mod.WhatsAppBot.resolve_remote_peer(
        {
            "from": "5511981193899@c.us",
            "to": "143430516752629@lid",
            "fromMe": True,
        },
        from_me=True,
    )
    assert peer3 == "143430516752629@lid"


def test_extract_search_query_from_quote_envelope():
    mod = _load_module()
    raw = (
        "[Respondendo a esta mensagem]\n"
        "«bot: Lá estão algumas dicas sobre conteúdo adulto»\n\n"
        "[Resposta do usuário]\n"
        "busque os contatos e me traga os links"
    )
    q = mod.WhatsAppBot._extract_search_query(raw)
    assert "busque os contatos" in q
    assert "Respondendo a esta mensagem" not in q
    # citação do bot NÃO deve poluir a query (causava FAQ WhatsApp)
    assert "algumas dicas" not in q.lower()
    assert "bot:" not in q.lower()
    assert mod.WhatsAppBot._wants_web_search(raw) is True
    assert mod.WhatsAppBot._wants_web_search("oi sumida") is False

    # ambíguo + histórico: enriquece com pedido anterior do user
    hist = [
        {
            "role": "user",
            "content": "procure criadora de conteudo adulto procurando parceiro",
        }
    ]
    q2 = mod.WhatsAppBot._extract_search_query("links", history=hist)
    assert "parceiro" in q2.lower() or "criadora" in q2.lower()


def test_extract_search_query_does_not_duplicate_current_message():
    """Regressão do incidente 2026-07-31: get_history() já inclui a msg atual
    (add_message roda antes), então ela entrava 2x na query ambígua e a busca
    degenerava em frases repetidas a cada turno (ex.: "...em você monte um
    texto...em você" — a mesma frase duas vezes na mesma query)."""
    mod = _load_module()
    current = "monte um texto me mim fazendo fistng anal em você"
    hist = [
        {"role": "user", "content": "pesquise sobre fisting anal"},
        {"role": "user", "content": current},  # já presente — add_message roda antes
    ]
    q = mod.WhatsAppBot._extract_search_query(current, history=hist)
    assert q.count("monte um texto me mim fazendo fistng anal em você") == 1


def test_extract_quoted_text_and_format_for_model():
    mod = _load_module()
    # formato replyTo com body
    q = mod.WhatsAppBot.extract_quoted_text(
        {"body": "sim", "replyTo": {"body": "bot: Quer que eu busque e-mails de RH?"}}
    )
    assert "e-mails de RH" in q

    # quotedMsg aninhado
    q2 = mod.WhatsAppBot.extract_quoted_text(
        {"body": "isso", "quotedMsg": {"body": "lista de plataformas onlyfans"}}
    )
    assert "onlyfans" in q2

    # _data.quotedMsg (WEBJS)
    q3 = mod.WhatsAppBot.extract_quoted_text(
        {"body": "ok", "_data": {"quotedMsg": {"body": "mensagem original citada"}}}
    )
    assert "original citada" in q3

    formatted = mod.WhatsAppBot.format_user_text_with_quote("sim", "bot: Quer e-mail de candidatura?")
    assert "Respondendo a esta mensagem" in formatted
    assert "e-mail de candidatura" in formatted
    assert "sim" in formatted
    # sem quote
    assert mod.WhatsAppBot.format_user_text_with_quote("oi", "") == "oi"


def test_is_nsfw_refusal_detects_soft_censor():
    mod = _load_module()
    assert mod.WhatsAppBot._is_obedience_refusal(
        "Desculpe, mas eu preciso me certificar de que estou seguindo as diretrizes "
        "de interação apropriadas. Eu posso proporcionar respostas apropriadas."
    )
    assert mod.WhatsAppBot._is_obedience_refusal(
        "Sou um assistente virtual e não posso fazer o que você pediu."
    )
    assert mod.WhatsAppBot._is_obedience_refusal(
        "desculpe, mas não posso te ajudar com isso. Se você precisa de algo..."
    )
    assert not mod.WhatsAppBot._is_obedience_refusal(
        "Vem que eu te meto fundo até você gozar gritando"
    )
    assert not mod.WhatsAppBot._is_obedience_refusal(
        "sim senhor. ManyVids, Fansly, FanCentro."
    )
    assert not mod.WhatsAppBot._is_obedience_refusal("kkkkk bora")


def test_scrub_refusal_history_drops_bad_assistant_turns():
    mod = _load_module()
    msgs = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "desculpe, mas não posso te ajudar com isso"},
        {"role": "user", "content": "procure email"},
    ]
    cleaned = mod.WhatsAppBot._scrub_refusal_history(msgs)
    assert len(cleaned) == 2
    assert cleaned[-1]["content"] == "procure email"
    assert all("não posso" not in m.get("content", "").lower() for m in cleaned if m["role"] == "assistant")


def test_normalize_outbound_preserves_lid():
    mod = _load_module()
    waha = mod.WAHAClient.__new__(mod.WAHAClient)

    assert waha._normalize_outbound_chat_id("68371752194106@lid") == "68371752194106@lid"
    assert waha._normalize_outbound_chat_id("5511986117521@c.us") == "5511986117521@s.whatsapp.net"
    assert waha._normalize_outbound_chat_id("5511986117521") == "5511986117521@s.whatsapp.net"
    # nunca empilhar sufixos em cima de @lid
    assert "@lid@s.whatsapp.net" not in waha._normalize_outbound_chat_id("68371752194106@lid")


def test_outbound_candidates_include_fernanda_phone_fallback():
    mod = _load_module()
    waha = mod.WAHAClient.__new__(mod.WAHAClient)

    cands = waha._outbound_chat_id_candidates("68371752194106@lid")
    assert "68371752194106@lid" in cands
    assert "5511986117521@s.whatsapp.net" in cands
    assert "5511986117521@c.us" in cands
    assert not any(c.endswith("@lid@s.whatsapp.net") for c in cands)


def test_outbound_text_gets_bot_tag():
    mod = _load_module()
    tag_fn = mod.WAHAClient._tag_outbound_text

    assert tag_fn("oi sumida").startswith("bot:")
    assert "oi sumida" in tag_fn("oi sumida")
    # não duplica
    assert tag_fn("bot: já marcado") == "bot: já marcado"
    assert tag_fn("") == ""


def test_ollama_client_gpu_tolerance_defaults(monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("OLLAMA_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("OLLAMA_HTTP_RETRIES", raising=False)
    monkeypatch.delenv("OLLAMA_HTTP_RETRY_BACKOFF", raising=False)
    client = mod.OllamaClient(host="http://127.0.0.1:9")
    assert client.read_timeout_s >= 300
    assert client.http_retries >= 5
    assert client.retry_backoff >= 1
    assert client._is_retryable_status(503)
    assert client._is_retryable_status(504)
    assert not client._is_retryable_status(404)


def test_is_allowed_sender_accepts_nsfw_lid():
    mod = _load_module()
    bot = mod.WhatsAppBot.__new__(mod.WhatsAppBot)

    assert bot.is_allowed_sender("68371752194106@lid", "68371752194106@lid")
    assert not bot.is_allowed_sender("5511999999999@c.us", "5511999999999@c.us")
