from scripts.wikijs_configure import build_welcome_content


def test_build_welcome_content_contains_full_wiki_links() -> None:
    content = build_welcome_content(svg_banner="<svg></svg>")
    assert "https://wiki.rpa4all.com/infraestrutura/arquitetura" in content
    assert "https://wiki.rpa4all.com/infraestrutura/guia-conexao" in content
    assert "https://wiki.rpa4all.com/infraestrutura/operacoes" in content
    assert "https://wiki.rpa4all.com/infraestrutura/eddie-operacoes" in content
    assert "https://wiki.rpa4all.com/infraestrutura/email-server" in content
    assert "https://wiki.rpa4all.com/infraestrutura/integracao" in content
    assert "https://wiki.rpa4all.com/projetos/visao-geral" in content
