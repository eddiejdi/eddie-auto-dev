"""Testes de roteamento Hugging Face no Diretor service."""

from __future__ import annotations


def test_should_delegate_to_huggingface_by_keyword() -> None:
    """Deve delegar quando a requisição menciona Hugging Face/Inferences de imagem."""
    from dev_agent.run_diretor_service import _should_delegate_to_huggingface

    assert _should_delegate_to_huggingface("Por favor usar huggingface para gerar imagem") is True
    assert _should_delegate_to_huggingface("quero text-to-image via inference-api") is True
    assert _should_delegate_to_huggingface("apenas revisar um codigo python") is False


def test_extract_huggingface_prompt_defaults_when_empty() -> None:
    """Prompt vazio deve gerar fallback seguro para criação de imagem."""
    from dev_agent.run_diretor_service import _extract_huggingface_prompt

    prompt = _extract_huggingface_prompt("   ")

    assert "Arte digital" in prompt


def test_extract_huggingface_prompt_keeps_text() -> None:
    """Prompt textual deve ser preservado sem alteração."""
    from dev_agent.run_diretor_service import _extract_huggingface_prompt

    prompt = _extract_huggingface_prompt("dragão azul voando sobre montanhas")

    assert prompt == "dragão azul voando sobre montanhas"


def test_should_list_huggingface_resources_by_keywords() -> None:
    """Pedidos de recursos/modelos devem ativar rota de listagem."""
    from dev_agent.run_diretor_service import _should_list_huggingface_resources

    assert _should_list_huggingface_resources("listar recursos disponíveis da huggingface") is True
    assert _should_list_huggingface_resources("quais modelos posso usar no hf inference") is True
    assert _should_list_huggingface_resources("gerar imagem de um castelo") is False
