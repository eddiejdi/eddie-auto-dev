"""Testes unitarios para specialized_agents/bn_acervo_agent.py."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest
import httpx
pytest.importorskip("bs4")

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "specialized_agents" / "bn_acervo_agent.py"
sys.path.insert(0, str(ROOT))

_SPEC = importlib.util.spec_from_file_location("bn_acervo_agent", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["bn_acervo_agent"] = mod
_SPEC.loader.exec_module(mod)


def test_extract_duckduckgo_result_urls_decodes_uddg_and_filters_domain() -> None:
    html = """
    <html><body>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facervo.bn.gov.br%2Fsophia_web%2Facervo%2Fdetalhe%2F1218773">ok</a>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fhemeroteca-pdf.bn.gov.br%2F123456%2Fper123456_1989_00001.pdf">pdf</a>
      <a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ffora">fora</a>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facervo.bn.gov.br%2Fsophia_web%2Facervo%2Fdetalhe%2F1218773">dup</a>
    </body></html>
    """
    urls = mod.extract_duckduckgo_result_urls(html)
    assert urls == [
        "https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        "https://hemeroteca-pdf.bn.gov.br/123456/per123456_1989_00001.pdf",
    ]


def test_extract_duckduckgo_result_hits_extracts_snippet_text() -> None:
    html = """
    <div class="result">
      <div class="links_main result__body">
        <h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Facervo.bn.gov.br%2Fsophia_web%2Facervo%2Fdetalhe%2F84268">Terminal - Sophia Biblioteca Web</a></h2>
        <a class="result__url" href="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/84268">acervo.bn.gov.br/sophia_web/acervo/detalhe/84268</a>
        <a class="result__snippet">Administração do produto Floriano do Amaral Gurgel Material Livro Idioma Português</a>
      </div>
    </div>
    """
    hits = mod.extract_duckduckgo_result_hits(html)
    assert len(hits) == 1
    assert hits[0].detail_url == "https://acervo.bn.gov.br/sophia_web/acervo/detalhe/84268"
    assert "Administração do produto" in hits[0].snippet


def test_clean_search_snippet_removes_duckduckgo_ad_tail() -> None:
    snippet = mod._clean_search_snippet(
        "PDF Correio da Manhã | João Goulart | Amazon.com.br - Conta com a gente! | Ad | Viewing ads is privacy protected by DuckDuckGo."
    )
    assert "Amazon.com.br" not in snippet
    assert "Viewing ads" not in snippet
    assert "Correio da Manhã" in snippet


def test_detect_cloudflare_block_flags_known_block_page() -> None:
    assert mod.detect_cloudflare_block(
        "Attention Required! | Cloudflare",
        "Sorry, you have been blocked",
        "",
    )
    assert not mod.detect_cloudflare_block("Terminal - Sophia Biblioteca Web", "Registro completo", "")


def test_extract_document_links_keeps_objdigital_and_pdf_links() -> None:
    links = [
        "https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        "http://objdigital.bn.br/objdigital2/acervo_digital/div_obrasraras/or1556329/or1556329.pdf",
        "https://example.com/arquivo.txt",
        "https://cdn.example.org/image.JPG",
    ]
    extracted = mod.extract_document_links(links)
    assert "http://objdigital.bn.br/objdigital2/acervo_digital/div_obrasraras/or1556329/or1556329.pdf" in extracted
    assert "https://cdn.example.org/image.JPG" in extracted
    assert "https://example.com/arquivo.txt" not in extracted


def test_parse_record_metadata_extracts_main_fields() -> None:
    body = """
    Registro completo
    Link do título
    Memórias póstumas de Brás Cubas
    Material
    Livro
    Idioma
    Português
    Publicação
    São Paulo : Moderna, 2015.
    Descrição física
    239 p. : il. ; 23 cm.
    Nota da Bibliografia Nacional Brasileira
    BNB
    06/17
    Assuntos
    Ficção brasileira
    Desenvolvido por
    App instalado
    """
    metadata = mod.parse_record_metadata(body)
    assert metadata["title"] == "Memórias póstumas de Brás Cubas"
    assert metadata["material"] == "Livro"
    assert metadata["idioma"] == "Português"
    assert metadata["publicacao"] == "São Paulo : Moderna, 2015."
    assert metadata["descricao_fisica"] == "239 p. : il. ; 23 cm."
    assert metadata["nota_da_bibliografia_nacional_brasileira"] == "BNB 06/17"


def test_build_reference_entries_includes_document_summary() -> None:
    document = mod.DownloadedDocument(
        source_url="http://objdigital.bn.br/doc.pdf",
        media_type="application/pdf",
        summary="Resumo OCR do documento.",
    )
    record = mod.AcervoRecord(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        title="Registro de teste",
        metadata={"publicacao": "Rio de Janeiro, 1985."},
        documents=[document],
    )
    refs = mod.build_reference_entries([record])
    assert refs[0]["id"] == "R1"
    assert refs[0]["document_urls"] == ["http://objdigital.bn.br/doc.pdf"]
    assert "Rio de Janeiro, 1985." in refs[0]["evidence_excerpt"]


class _FakeDigester(mod.BaseDocumentDigester):
    def __init__(self, name: str, *, available: bool = True, succeed: bool = True, supports: bool = True) -> None:
        self.name = name
        self._available = available
        self._succeed = succeed
        self._supports = supports
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    def supports(self, document: mod.DownloadedDocument) -> bool:
        return self._supports

    async def digest(
        self,
        agent: mod.BnAcervoAgent,
        document: mod.DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> bool:
        self.calls += 1
        if self._succeed:
            document.extraction_mode = self.name
            document.summary = f"digested by {self.name}"
            document.extracted_text = f"content from {self.name}"
            return True
        return False


def test_document_digester_registry_prefers_primary_backend() -> None:
    primary = _FakeDigester("docling")
    fallback = _FakeDigester("legacy")
    registry = mod.DocumentDigesterRegistry([primary, fallback])
    agent = mod.BnAcervoAgent()
    document = mod.DownloadedDocument(source_url="http://example.com/doc.pdf", media_type="application/pdf", local_path="/tmp/doc.pdf")

    digested = asyncio.run(
        registry.digest(
            agent,
            document,
            max_ocr_pages_per_document=2,
            prefer_ocr=True,
        )
    )

    assert digested is True
    assert document.extraction_mode == "docling"
    assert primary.calls == 1
    assert fallback.calls == 0


def test_document_digester_registry_falls_back_when_primary_is_unavailable() -> None:
    primary = _FakeDigester("docling", available=False)
    fallback = _FakeDigester("legacy")
    registry = mod.DocumentDigesterRegistry([primary, fallback])
    agent = mod.BnAcervoAgent()
    document = mod.DownloadedDocument(source_url="http://example.com/doc.pdf", media_type="application/pdf", local_path="/tmp/doc.pdf")

    digested = asyncio.run(
        registry.digest(
            agent,
            document,
            max_ocr_pages_per_document=2,
            prefer_ocr=True,
        )
    )

    assert digested is True
    assert document.extraction_mode == "legacy"
    assert primary.calls == 0
    assert fallback.calls == 1


def test_docling_digester_supports_document_and_image_extensions() -> None:
    digester = mod.DoclingDocumentDigester(enabled=True)
    assert digester.supports(mod.DownloadedDocument(source_url="a", media_type="application/pdf", local_path="/tmp/a.pdf"))
    assert digester.supports(mod.DownloadedDocument(source_url="b", media_type="image/png", local_path="/tmp/b.png"))
    assert digester.supports(mod.DownloadedDocument(source_url="c", media_type="text/html", local_path="/tmp/c.html"))


def test_resolve_investigation_profile_deep_expands_scope() -> None:
    agent = mod.BnAcervoAgent()
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", investigation_mode="deep")
    profile = agent._resolve_investigation_profile(payload)
    assert profile.mode == "deep"
    assert profile.max_search_results == 60
    assert profile.max_detail_records == 40
    assert profile.max_download_documents == 30
    assert profile.max_ocr_pages_per_document == 120
    assert profile.include_authority_pages is True


def test_investigation_budget_policy_allows_large_explicit_payload() -> None:
    policy = mod.InvestigationBudgetPolicy()
    payload = mod.AcervoStoryRequest(
        query="João Amaral Gurgel",
        investigation_mode="deep",
        max_search_results=120,
        max_detail_records=80,
        max_download_documents=55,
        max_ocr_pages_per_document=250,
    )
    profile = policy.build_profile(payload)
    assert profile.max_search_results == 120
    assert profile.max_detail_records == 80
    assert profile.max_download_documents == 55
    assert profile.max_ocr_pages_per_document == 250


def test_investigation_budget_policy_respects_explicit_zero_limits() -> None:
    policy = mod.InvestigationBudgetPolicy()
    payload = mod.AcervoStoryRequest(
        query="João Amaral Gurgel",
        investigation_mode="quick",
        max_download_documents=0,
        max_ocr_pages_per_document=0,
    )
    profile = policy.build_profile(payload)
    assert profile.max_download_documents == 0
    assert profile.max_ocr_pages_per_document == 0


def test_download_document_rejects_invalid_url_without_network() -> None:
    agent = mod.BnAcervoAgent()

    document = asyncio.run(agent._download_document("sem-esquema-ou-host"))

    assert document.local_path is None
    assert document.skipped_reason == "url_documento_invalida"
    assert document.media_type == "application/octet-stream"


def test_download_and_digest_documents_skips_failed_download_and_continues() -> None:
    agent = mod.BnAcervoAgent()
    first = mod.AcervoRecord(
        detail_url="https://example.com/r1",
        title="Primeiro",
        document_links=["https://host-invalido.local/documento.pdf"],
    )
    second = mod.AcervoRecord(
        detail_url="https://example.com/r2",
        title="Segundo",
        document_links=["https://example.com/ok.pdf"],
    )

    async def fake_download(url: str) -> mod.DownloadedDocument:
        if "host-invalido" in url:
            raise httpx.ConnectError("dns failure")
        return mod.DownloadedDocument(
            source_url=url,
            media_type="application/pdf",
            local_path="/tmp/ok.pdf",
        )

    async def fake_digest(
        document: mod.DownloadedDocument,
        *,
        max_ocr_pages_per_document: int,
        prefer_ocr: bool,
    ) -> None:
        document.summary = "ok"
        document.extracted_text = "texto"

    agent._download_document = fake_download  # type: ignore[method-assign]
    agent._digest_document = fake_digest  # type: ignore[method-assign]

    asyncio.run(
        agent._download_and_digest_documents(
            [first, second],
            max_download_documents=2,
            max_ocr_pages_per_document=1,
            prefer_ocr=False,
        )
    )

    assert len(first.documents) == 1
    assert first.documents[0].skipped_reason == "download_falhou:ConnectError"
    assert len(second.documents) == 1
    assert second.documents[0].summary == "ok"


def test_expand_deep_search_terms_composes_axes_without_duplicates() -> None:
    agent = mod.BnAcervoAgent()
    terms = agent._expand_deep_search_terms(
        "João Amaral Gurgel",
        {
            "search_terms": ["João Amaral Gurgel"],
            "must_include": ["governo brasileiro", "política industrial"],
            "hypotheses": ["sabotagem estatal"],
            "institutions": ["Finep"],
            "companies": ["Gurgel Motores"],
        },
        4,
    )
    assert terms[0] == "João Amaral Gurgel"
    assert "João Amaral Gurgel governo brasileiro" in terms
    assert "sabotagem estatal" in terms
    assert terms.count("João Amaral Gurgel") == 1


def test_investigation_memory_store_persists_case_runs(tmp_path: Path) -> None:
    store = mod.InvestigationMemoryStore(tmp_path)
    profile = mod.InvestigationProfile(mode="deep")
    store.save_run(
        query="João Amaral Gurgel",
        profile=profile,
        plan={"unresolved_questions": ["Quem atuou contra a empresa?"]},
        references=[{"id": "R1", "title": "Fonte", "detail_url": "https://exemplo"}],
        dossier={"subject": {"name": "João Amaral Gurgel", "kind": "figura_publica"}, "timeline": [], "relationships": [], "entities": []},
        records=[{"title": "Fonte"}],
    )
    payload = store.load("João Amaral Gurgel")
    assert payload["query"] == "João Amaral Gurgel"
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["mode"] == "deep"
    assert payload["aggregate_references"][0]["title"] == "Fonte"
    assert payload["aggregate_entities"][0]["name"] == "João Amaral Gurgel"


def test_build_story_prompt_mentions_reference_codes() -> None:
    record = mod.AcervoRecord(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        title="Gurgel em revista",
        metadata={"publicacao": "São Paulo, 1987."},
    )
    references = [{"id": "R1", "title": "Gurgel em revista", "detail_url": record.detail_url, "document_urls": [], "evidence_excerpt": "BR-800"}]
    prompt = mod.build_story_prompt(
        "historia da empresa automobilistica Gurgel",
        {"search_terms": ["Gurgel BR-800"], "must_include": ["cronologia", "BR-800"]},
        [record],
        references,
    )
    assert "historia da empresa automobilistica Gurgel" in prompt
    assert "R1 ::" in prompt
    assert "BR-800" in prompt


def test_build_dossier_prompt_mentions_json_relationship_schema() -> None:
    record = mod.AcervoRecord(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        title="João Goulart em jornal",
        metadata={"publicacao": "Rio de Janeiro, 1964."},
    )
    references = [{"id": "R1", "title": record.title, "detail_url": record.detail_url, "document_urls": [], "evidence_excerpt": "João Goulart e Congresso"}]
    prompt = mod.build_dossier_prompt(
        "João Goulart",
        {"search_terms": ["João Goulart"], "must_include": ["relações políticas"], "people": ["João Goulart"]},
        [record],
        references,
    )
    assert '"relationships"' in prompt
    assert '"object"' in prompt
    assert '"timeline"' in prompt
    assert "João Goulart" in prompt


def test_normalize_search_terms_preserves_query_and_filters_noise() -> None:
    terms = mod._normalize_search_terms_from_query(
        "história da empresa automobilística Gurgel",
        ["Gurgel", "Sã?", "Automóvel", "A", "123", "Industrialização"],
    )
    assert terms[0] == "história da empresa automobilística Gurgel"
    assert "Sã?" not in terms
    assert "A" not in terms
    assert "Gurgel automóvel" in terms
    assert "Gurgel empresa" in terms


def test_normalize_search_terms_uses_company_anchor_for_model_like_query() -> None:
    terms = mod._normalize_search_terms_from_query(
        "Gurgel BR-800",
        ["Gurgel", "Livro", "Biblioteca Nacional", "Pesquisa Histórica"],
    )
    assert terms[0] == "Gurgel BR-800"
    assert "Gurgel automóvel" in terms
    assert "Gurgel carro" in terms
    assert "Livro" not in terms
    assert "Biblioteca Nacional" not in terms


def test_entity_subject_resolver_expands_configured_aliases() -> None:
    resolver = mod.EntitySubjectResolver({"amaral gurgel": ["João Amaral Gurgel", "João Gurgel"]})
    terms = resolver.expand_query_terms("Amaral Gurgel", [])
    assert terms[0] == "Amaral Gurgel"
    assert "João Amaral Gurgel" in terms
    assert "João Gurgel" in terms


def test_slug_identifier_removes_accents() -> None:
    assert mod._slug_identifier("João Amaral Gurgel", prefix="e1") == "joao_amaral_gurgel"


def test_build_partial_record_from_search_hit_marks_partial_source() -> None:
    agent = mod.BnAcervoAgent()
    hit = mod.SearchHit(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/869819",
        title="Terminal - Sophia Biblioteca Web",
        snippet="Boletim do Grande Oriente do Brasil",
    )
    record = agent._build_partial_record_from_search_hit(hit)
    assert record.metadata["fonte_parcial"] == "resultado_externo_duckduckgo"
    assert "Boletim do Grande Oriente do Brasil" in record.raw_text


def test_parse_bing_rss_hits_filters_domain_and_extracts_description() -> None:
    xml = """
    <rss version="2.0">
      <channel>
        <item>
          <title>Terminal - Sophia Biblioteca Web - acervo.bn.gov.br</title>
          <link>https://acervo.bn.gov.br/sophia_web/acervo/detalhe/84268</link>
          <description>Administração do produto Floriano do Amaral Gurgel.</description>
        </item>
        <item>
          <title>Wikipedia</title>
          <link>https://pt.wikipedia.org/wiki/Gurgel</link>
          <description>fora do dominio</description>
        </item>
      </channel>
    </rss>
    """
    agent = mod.BnAcervoAgent()
    hits = agent._parse_bing_rss_hits(xml)
    assert len(hits) == 1
    assert hits[0].detail_url.endswith("/84268")
    assert "Administração do produto" in hits[0].snippet
    assert hits[0].source_engine == "bing_rss"


def test_build_search_queries_includes_press_corpora() -> None:
    agent = mod.BnAcervoAgent()
    queries = agent._build_search_queries("João Goulart", "deep")
    query_texts = [item[1] for item in queries]
    assert any("hemeroteca-pdf.bn.gov.br" in item for item in query_texts)
    assert any("bndigital.bn.gov.br" in item for item in query_texts)
    assert any("jornal revista imprensa hemeroteca" in item for item in query_texts)


def test_build_search_queries_quick_mode_stays_small() -> None:
    agent = mod.BnAcervoAgent()
    queries = agent._build_search_queries("João Goulart", "quick")
    assert len(queries) == 2
    assert all("acervo.bn.gov.br" in item[1] for item in queries)


def test_build_mermaid_graph_includes_entities_and_labels() -> None:
    mermaid = mod.build_mermaid_graph(
        {
            "subject": {"id": "subject", "name": "João Goulart", "kind": "figura_publica"},
            "entities": [{"id": "congresso", "name": "Congresso Nacional", "kind": "instituicao"}],
            "relationships": [{"source": "subject", "target": "congresso", "label": "negociou com", "description": "Relação política"}],
        }
    )
    assert "graph TD" in mermaid
    assert "João Goulart" in mermaid
    assert "Congresso Nacional" in mermaid
    assert "negociou com" in mermaid


def test_build_mermaid_graph_uses_relation_node_when_object_exists() -> None:
    mermaid = mod.build_mermaid_graph(
        {
            "subject": {"id": "subject", "name": "Banco do Brasil", "kind": "instituicao"},
            "entities": [{"id": "gurgel_motores", "name": "Gurgel Motores", "kind": "organizacao"}],
            "relationships": [
                {
                    "source": "subject",
                    "target": "gurgel_motores",
                    "label": "emprestou",
                    "object": "capital de giro",
                    "description": "Banco do Brasil emprestou capital de giro para Gurgel Motores.",
                }
            ],
        }
    )
    assert 'rel_1["emprestou capital de giro"]' in mermaid
    assert "subject --> rel_1" in mermaid
    assert "rel_1 --> gurgel_motores" in mermaid


def test_build_external_record_from_hemeroteca_pdf_adds_document_link() -> None:
    agent = mod.BnAcervoAgent()
    hit = mod.SearchHit(
        detail_url="https://hemeroteca-pdf.bn.gov.br/761036/per761036_1989_22311.pdf",
        title="Jornal da Amazônia, 21 mai. 1989",
        snippet="BR-800 e Correios.",
        source_engine="bing_rss",
        source_kind="hemeroteca_pdf",
    )
    record = agent._build_external_record_from_search_hit(hit)
    assert record.document_links == ["https://hemeroteca-pdf.bn.gov.br/761036/per761036_1989_22311.pdf"]
    assert record.metadata["corpus"] == "hemeroteca_pdf"
    assert "resultado externo do corpus" in record.relevance_reason


def test_extract_actor_relationship_mentions_finds_chained_actor_links() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/registro",
        title="Registro relacional",
        raw_text=(
            "Banco do Brasil emprestou recursos para Gurgel Motores. "
            "Gurgel Motores prometeu fabricar veículos para Correios."
        ),
    )
    references = mod.build_reference_entries([record])
    mentions = agent._extract_actor_relationship_mentions([record], references)
    assert len(mentions) == 2
    assert mentions[0]["source_name"] == "Banco do Brasil"
    assert mentions[0]["target_name"] == "Gurgel Motores"
    assert mentions[0]["label"] == "emprestou"
    assert mentions[0]["object_text"] == "recursos"
    assert mentions[1]["source_name"] == "Gurgel Motores"
    assert mentions[1]["target_name"] == "Correios"
    assert mentions[1]["label"] == "prometeu"
    assert mentions[1]["object_text"] == "fabricar veículos"


def test_extract_named_actor_mentions_finds_politicians_by_title() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/politica",
        title="Registro político",
        raw_text=(
            "O presidente João Goulart discursou sobre a crise. "
            "Mário Andreazza, ministro, reuniu-se com empresários."
        ),
    )
    references = mod.build_reference_entries([record])
    mentions = agent._extract_named_actor_mentions([record], references)
    names = {item["name"]: item for item in mentions}
    assert names["João Goulart"]["kind"] == "figura_publica"
    assert names["João Goulart"]["role"].lower() == "presidente"
    assert names["Mário Andreazza"]["kind"] == "figura_publica"
    assert names["Mário Andreazza"]["role"].lower() == "ministro"


def test_fallback_dossier_builds_actor_to_actor_mermaid_chain() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/registro",
        title="Registro relacional",
        metadata={"publicacao": "São Paulo, 1989."},
        raw_text=(
            "Banco do Brasil emprestou recursos para Gurgel Motores. "
            "Gurgel Motores prometeu fabricar veículos para Correios."
        ),
    )
    references = mod.build_reference_entries([record])
    dossier = agent._fallback_dossier("Banco do Brasil", {}, [record], references)
    assert dossier["subject"]["kind"] == "instituicao"
    labels = {relation["label"] for relation in dossier["relationships"]}
    assert "emprestou" in labels
    assert "prometeu" in labels
    assert any(relation["object"] == "recursos" for relation in dossier["relationships"])
    assert any(relation["object"] == "fabricar veículos" for relation in dossier["relationships"])
    assert 'subject["Banco do Brasil<br/>instituicao"]' in dossier["mermaid_graph"]
    assert 'evt_1_1["emprestou recursos<br/>São Paulo, 1989. | 1 fonte(s)"]' in dossier["mermaid_graph"]
    assert "subject --> evt_1_1" in dossier["mermaid_graph"]
    assert "evt_1_1 --> gurgel_motores" in dossier["mermaid_graph"]
    assert 'evt_2_1["prometeu fabricar veículos<br/>São Paulo, 1989. | 1 fonte(s)"]' in dossier["mermaid_graph"]
    assert "gurgel_motores --> evt_2_1" in dossier["mermaid_graph"]
    assert "evt_2_1 --> correios" in dossier["mermaid_graph"]


def test_fallback_dossier_includes_politician_names_even_without_explicit_relation() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/gurgel-politica",
        title="Registro com políticos",
        raw_text=(
            "O presidente João Goulart comentou a situação industrial. "
            "O governador Orestes Quércia acompanhou o debate sobre a Gurgel Motores."
        ),
    )
    references = mod.build_reference_entries([record])
    dossier = agent._fallback_dossier("Gurgel Motores", {}, [record], references)
    entity_map = {entity["name"]: entity for entity in dossier["entities"]}
    assert entity_map["João Goulart"]["kind"] == "figura_publica"
    assert "Presidente citado nas fontes" in entity_map["João Goulart"]["description"]
    assert entity_map["Orestes Quércia"]["kind"] == "figura_publica"
    assert "Governador citado nas fontes" in entity_map["Orestes Quércia"]["description"]


def test_fallback_dossier_builds_role_history_and_thematic_groups() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/gurgel-aprofundado",
        title="Gurgel aprofundado",
        raw_text=(
            "O presidente João Goulart comentou a situação industrial. "
            "Banco do Brasil emprestou capital de giro para Gurgel Motores. "
            "Gurgel Motores prometeu entregar 5 mil BR-800 para Correios. "
            "A revista Quatro Rodas criticou o plano comercial."
        ),
    )
    references = mod.build_reference_entries([record])
    dossier = agent._fallback_dossier("Gurgel Motores", {}, [record], references)
    entity_map = {entity["name"]: entity for entity in dossier["entities"]}
    assert entity_map["João Goulart"]["role_history"][0]["role"].lower() == "presidente"
    assert "governo_politica" in entity_map["João Goulart"]["themes"]
    relationship_themes = {relation["theme"] for relation in dossier["relationships"]}
    assert "financiamento" in relationship_themes
    assert "mercado_distribuicao" in relationship_themes or "producao_operacao" in relationship_themes
    assert "financiamento" in dossier["thematic_groups"]
    assert "governo_politica" in dossier["thematic_groups"]


def test_fallback_dossier_consolidates_same_relation_across_sources_and_derives_timeline() -> None:
    agent = mod.BnAcervoAgent()
    records = [
        mod.AcervoRecord(
            detail_url="https://example.com/gurgel-1",
            title="Fonte 1",
            metadata={"publicacao": "Rio de Janeiro, 1988."},
            raw_text="Banco do Brasil emprestou capital de giro para Gurgel Motores.",
        ),
        mod.AcervoRecord(
            detail_url="https://example.com/gurgel-2",
            title="Fonte 2",
            metadata={"publicacao": "São Paulo, 1989."},
            raw_text="Banco do Brasil emprestou capital de giro para Gurgel Motores em nova rodada de crédito.",
        ),
    ]
    references = mod.build_reference_entries(records)
    dossier = agent._fallback_dossier("Gurgel Motores", {}, records, references)
    matching = [
        relation
        for relation in dossier["relationships"]
        if relation["label"] == "emprestou" and relation["object"] == "capital de giro"
    ]
    assert len(matching) == 1
    relation = matching[0]
    assert relation["source_count"] == 2
    assert set(relation["evidence_refs"]) == {"R1", "R2"}
    assert len(relation["evidence_details"]) == 2
    assert len(dossier["events"]) == 2
    assert dossier["events"][0]["date"] == "Rio de Janeiro, 1988."
    assert dossier["events"][1]["date"] == "São Paulo, 1989."
    assert any("Banco do Brasil emprestou capital de giro para Gurgel Motores." in item["description"] for item in dossier["timeline"])
    assert any(item["evidence_refs"] == ["R1"] for item in dossier["timeline"])
    assert any(item["evidence_refs"] == ["R2"] for item in dossier["timeline"])


def test_character_memory_persists_and_expands_future_mermaid() -> None:
    agent = mod.BnAcervoAgent()
    with tempfile.TemporaryDirectory() as temp_dir:
        agent.memory_dir = Path(temp_dir)
        agent.character_memory_path = agent.memory_dir / "characters_graph.json"

        first_dossier = {
            "subject": {"id": "subject", "name": "João Goulart", "kind": "figura_publica", "themes": ["governo_politica"], "description": "Presidente em conflito institucional."},
            "entities": [
                {
                    "id": "congresso_nacional",
                    "name": "Congresso Nacional",
                    "kind": "instituicao",
                    "themes": ["governo_politica"],
                    "role_history": [],
                    "aliases": [],
                    "description": "Poder Legislativo central na crise.",
                }
            ],
            "relationships": [
                {
                    "source": "subject",
                    "target": "congresso_nacional",
                    "label": "negociou com",
                    "object": "reformas de base",
                    "description": "João Goulart negociou reformas de base com Congresso Nacional.",
                    "theme": "governo_politica",
                    "support_excerpt": "João Goulart negociou reformas de base com Congresso Nacional.",
                    "evidence_refs": ["R1"],
                    "evidence_details": [{"ref": "R1", "date": "Rio de Janeiro, 1963.", "excerpt": "João Goulart negociou reformas de base com Congresso Nacional."}],
                    "source_count": 1,
                }
            ],
            "timeline": [],
            "thematic_groups": {"governo_politica": ["congresso_nacional"]},
        }
        agent._persist_character_memory("João Goulart", first_dossier)

        second_dossier = {
            "subject": {"id": "subject", "name": "João Goulart", "kind": "figura_publica", "themes": ["governo_politica"]},
            "entities": [],
            "relationships": [],
            "timeline": [],
            "thematic_groups": {},
        }
        expanded = agent._expand_dossier_with_character_memory("João Goulart", second_dossier)
        memory_entity = next(entity for entity in expanded["entities"] if entity["name"] == "Congresso Nacional")
        assert memory_entity.get("memory_origin")
        assert "Poder Legislativo central na crise." in memory_entity["description"]
        memory_relation = next(relation for relation in expanded["relationships"] if relation["label"] == "negociou com")
        assert memory_relation.get("memory_origin")
        assert "João Goulart negociou reformas de base com Congresso Nacional." in memory_relation["description"]
        assert memory_relation["evidence_details"][0]["date"] == "Rio de Janeiro, 1963."
        assert expanded["events"][0]["date"] == "Rio de Janeiro, 1963."
        mermaid = mod.build_mermaid_graph(expanded)
        assert "Congresso Nacional" in mermaid
        assert "reformas de base" in mermaid
        assert "Rio de Janeiro, 1963." in mermaid


def test_build_mermaid_graph_prefers_event_nodes_when_events_exist() -> None:
    mermaid = mod.build_mermaid_graph(
        {
            "subject": {"id": "subject", "name": "João Goulart", "kind": "figura_publica"},
            "entities": [{"id": "congresso_nacional", "name": "Congresso Nacional", "kind": "instituicao"}],
            "relationships": [
                {"source": "subject", "target": "congresso_nacional", "label": "negociou com", "object": "reformas de base"}
            ],
            "events": [
                {
                    "id": "evt_1",
                    "date": "Rio de Janeiro, 1963.",
                    "source": "subject",
                    "target": "congresso_nacional",
                    "label": "negociou com",
                    "object": "reformas de base",
                    "source_count": 1,
                }
            ],
            "thematic_groups": {"governo_politica": ["congresso_nacional"]},
        }
    )
    assert 'evt_1["negociou com reformas de base<br/>Rio de Janeiro, 1963. | 1 fonte(s)"]' in mermaid
    assert "subject --> evt_1" in mermaid
    assert "evt_1 --> congresso_nacional" in mermaid


def test_build_mermaid_graph_uses_thematic_subgraphs() -> None:
    mermaid = mod.build_mermaid_graph(
        {
            "subject": {"id": "subject", "name": "Gurgel Motores", "kind": "organizacao"},
            "entities": [
                {"id": "banco_do_brasil", "name": "Banco do Brasil", "kind": "instituicao"},
                {"id": "joao_goulart", "name": "João Goulart", "kind": "figura_publica"},
            ],
            "relationships": [],
            "thematic_groups": {
                "financiamento": ["banco_do_brasil"],
                "governo_politica": ["joao_goulart"],
            },
        }
    )
    assert 'subgraph financiamento["Financiamento"]' in mermaid
    assert 'subgraph governo_politica["Governo Politica"]' in mermaid
    assert 'subgraph eixo_central["Eixo central"]' in mermaid


def test_build_neural_correlation_map_aggregates_relationships_and_cooccurrence() -> None:
    neural_map = mod.build_neural_correlation_map(
        {
            "subject": {"id": "subject", "name": "João Amaral Gurgel", "kind": "figura_publica", "evidence_refs": ["R1", "R2"]},
            "entities": [
                {"id": "gurgel_motores", "name": "Gurgel Motores", "kind": "organizacao", "evidence_refs": ["R1", "R2"]},
                {"id": "banco_do_brasil", "name": "Banco do Brasil", "kind": "instituicao", "evidence_refs": ["R1"]},
                {"id": "correios", "name": "Correios", "kind": "instituicao", "evidence_refs": ["R2"]},
            ],
            "relationships": [
                {
                    "source": "banco_do_brasil",
                    "target": "gurgel_motores",
                    "label": "emprestou",
                    "object": "capital de giro",
                    "theme": "financiamento",
                    "evidence_refs": ["R1"],
                    "source_count": 1,
                },
                {
                    "source": "gurgel_motores",
                    "target": "correios",
                    "label": "prometeu",
                    "object": "entregar BR-800",
                    "theme": "mercado_distribuicao",
                    "evidence_refs": ["R2"],
                    "source_count": 1,
                },
            ],
            "thematic_groups": {"financiamento": ["banco_do_brasil"], "mercado_distribuicao": ["correios"]},
        }
    )
    assert neural_map["stats"]["node_count"] == 4
    assert any(edge["type"] == "relationship" and edge["label"] == "emprestou capital de giro" for edge in neural_map["edges"])
    assert any(edge["type"] == "co_occurrence" for edge in neural_map["edges"])
    subject_node = next(node for node in neural_map["nodes"] if node["id"] == "subject")
    assert subject_node["degree"] >= 1


def test_investigation_job_store_persists_partial_result(tmp_path: Path) -> None:
    store = mod.InvestigationJobStore(tmp_path)
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", output_mode="dossier")
    created = store.create(payload)
    job_id = created["job_id"]
    partial_result = {"query": "João Amaral Gurgel", "partial_snapshot": True, "dossier": {"summary": "parcial"}}
    store.update(job_id, status="running", phase="composition", progress_percent=82, partial_result=partial_result)
    loaded = store.load(job_id)
    assert loaded is not None
    assert loaded["partial_result"]["partial_snapshot"] is True
    assert loaded["partial_result"]["dossier"]["summary"] == "parcial"


def test_partial_result_snapshot_includes_neural_map() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/registro",
        title="Registro relacional",
        metadata={"publicacao": "São Paulo, 1989."},
        raw_text="Banco do Brasil emprestou capital de giro para Gurgel Motores.",
    )
    references = mod.build_reference_entries([record])
    snapshot = agent._build_partial_result_snapshot(
        "Gurgel Motores",
        {},
        [record],
        references,
        phase="ranking",
    )
    assert snapshot["partial_snapshot"] is True
    assert snapshot["phase"] == "ranking"
    assert snapshot["neural_map"]["stats"]["node_count"] >= 2


def test_candidate_hits_snapshot_includes_partial_graphs() -> None:
    agent = mod.BnAcervoAgent()
    hits = [
        mod.SearchHit(
            detail_url="https://hemeroteca-pdf.bn.gov.br/761036/per761036_1989_22311.pdf",
            title="Jornal da Amazônia, 21 mai. 1989",
            snippet="João Amaral Gurgel e BR-800 em destaque.",
            source_engine="bing_rss",
            source_kind="hemeroteca_pdf",
        )
    ]
    snapshot = agent._build_candidate_hits_snapshot("João Amaral Gurgel", {}, hits)
    assert snapshot["phase"] == "discovery"
    assert snapshot["partial_snapshot"] is True
    assert snapshot["mermaid_graph"]
    assert snapshot["neural_map"]["stats"]["node_count"] >= 1


def test_fallback_dossier_prefers_actor_names_over_source_titles_when_no_relation_exists() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/fonte",
        title="Jornal da Amazônia, 21 mai. 1989",
        raw_text="João Amaral Gurgel apresentou o projeto da Gurgel Motores ao mercado nacional.",
    )
    references = mod.build_reference_entries([record])
    dossier = agent._fallback_dossier("João Amaral Gurgel", {}, [record], references)
    entity_names = {entity["name"] for entity in dossier["entities"]}
    assert "João Amaral Gurgel" not in entity_names
    assert "Gurgel Motores" in entity_names
    assert "Jornal da Amazônia, 21 mai. 1989" not in entity_names
    assert "Nenhuma evidencia documental confiavel" not in dossier["summary"]


def test_build_contingency_result_does_not_persist_investigation(tmp_path: Path) -> None:
    agent = mod.BnAcervoAgent()
    agent.investigation_dir = tmp_path
    agent.investigation_memory_store = mod.InvestigationMemoryStore(tmp_path)
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", output_mode="dossier", persist_investigation=True)
    profile = agent._resolve_investigation_profile(payload)
    result = agent._build_contingency_result(payload, profile, {}, [], [])
    assert result["contingency_mode"] is True
    stored = agent.investigation_memory_store.load("João Amaral Gurgel")
    assert stored["runs"] == []


def test_compose_story_falls_back_when_ollama_times_out() -> None:
    agent = mod.BnAcervoAgent()
    agent.story_timeout_seconds = 0.01
    record = mod.AcervoRecord(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        title="Gurgel em revista",
        metadata={"publicacao": "São Paulo, 1987."},
        raw_text="BR-800 e a indústria nacional.",
    )
    references = mod.build_reference_entries([record])

    async def fake_generate(**_: object) -> str:
        await asyncio.sleep(0.05)
        return "R1"

    agent._ollama_generate = fake_generate  # type: ignore[method-assign]
    story = asyncio.run(agent._compose_story("Gurgel BR-800", {"search_terms": [], "must_include": []}, [record], references))
    assert "## Historia" in story
    assert "[R1]" in story


def test_normalize_dossier_payload_resolves_names_to_internal_ids() -> None:
    agent = mod.BnAcervoAgent()
    references = [
        {"id": "R1", "title": "Fonte 1", "detail_url": "https://example.com/1", "document_urls": [], "evidence_excerpt": "x"},
        {"id": "R2", "title": "Fonte 2", "detail_url": "https://example.com/2", "document_urls": [], "evidence_excerpt": "y"},
    ]
    dossier = agent._normalize_dossier_payload(
        {
            "subject": {"name": "João Goulart", "kind": "figura_publica", "evidence_refs": ["R1"]},
            "summary": "Presidente deposto.",
            "entities": [
                {"name": "Congresso Nacional", "kind": "instituicao", "description": "Poder Legislativo", "evidence_refs": ["R2"]}
            ],
            "relationships": [
                {"source": "João Goulart", "target": "Congresso Nacional", "label": "negociou com", "description": "Negociação política", "evidence_refs": ["R2"]}
            ],
            "timeline": [{"date": "1964", "description": "Crise política", "evidence_refs": ["R1"]}],
        },
        "João Goulart",
        {"people": ["João Goulart"]},
        references,
    )
    assert dossier is not None
    assert dossier["subject"]["id"] == "subject"
    assert dossier["relationships"][0]["source"] == "subject"
    assert dossier["relationships"][0]["target"] == "congresso_nacional"


def test_normalize_dossier_payload_keeps_multiple_relationships_for_same_actors_when_objects_differ() -> None:
    agent = mod.BnAcervoAgent()
    references = [
        {"id": "R1", "title": "Fonte 1", "detail_url": "https://example.com/1", "document_urls": [], "evidence_excerpt": "x"},
    ]
    dossier = agent._normalize_dossier_payload(
        {
            "subject": {"name": "Gurgel Motores", "kind": "organizacao", "evidence_refs": ["R1"]},
            "summary": "Atos distintos.",
            "entities": [{"name": "Correios", "kind": "instituicao", "description": "Empresa pública", "evidence_refs": ["R1"]}],
            "relationships": [
                {
                    "source": "Gurgel Motores",
                    "target": "Correios",
                    "label": "prometeu",
                    "object": "entregar veículos",
                    "description": "Compromisso de entrega",
                    "evidence_refs": ["R1"],
                },
                {
                    "source": "Gurgel Motores",
                    "target": "Correios",
                    "label": "prometeu",
                    "object": "adaptar utilitários",
                    "description": "Compromisso técnico distinto",
                    "evidence_refs": ["R1"],
                },
            ],
            "timeline": [],
        },
        "Gurgel Motores",
        {},
        references,
    )
    assert dossier is not None
    assert len(dossier["relationships"]) == 2
    assert {item["object"] for item in dossier["relationships"]} == {"entregar veículos", "adaptar utilitários"}


def test_compose_dossier_falls_back_when_model_times_out() -> None:
    agent = mod.BnAcervoAgent()
    agent.dossier_timeout_seconds = 0.01
    record = mod.AcervoRecord(
        detail_url="https://acervo.bn.gov.br/sophia_web/acervo/detalhe/1218773",
        title="João Goulart em revista",
        metadata={"publicacao": "Rio de Janeiro, 1964."},
        raw_text="João Goulart foi citado em relação ao Congresso Nacional.",
    )
    references = mod.build_reference_entries([record])

    async def fake_generate(**_: object) -> str:
        await asyncio.sleep(0.05)
        return "{}"

    agent._ollama_generate = fake_generate  # type: ignore[method-assign]
    dossier = asyncio.run(agent._compose_dossier("João Goulart", {"people": ["João Goulart"]}, [record], references))
    assert "mermaid_graph" in dossier
    assert "dossier_markdown" in dossier
    assert "```mermaid" in dossier["dossier_markdown"]


def test_fallback_dossier_prefers_canonical_subject_for_amaral_gurgel_query() -> None:
    agent = mod.BnAcervoAgent()
    record = mod.AcervoRecord(
        detail_url="https://example.com/amaral-gurgel",
        title="Amaral Gurgel em jornal",
        metadata={"publicacao": "São Paulo, 1989."},
        raw_text="João Amaral Gurgel negociou incentivos fiscais com Governo Federal.",
    )
    references = mod.build_reference_entries([record])
    dossier = agent._fallback_dossier("Amaral Gurgel", {}, [record], references)
    assert dossier["subject"]["name"] == "João Amaral Gurgel"
    assert dossier["subject"]["kind"] == "figura_publica"


def test_entity_subject_resolver_prefers_longer_evidence_backed_person_name() -> None:
    resolver = mod.EntitySubjectResolver()
    records = [
        mod.AcervoRecord(
            detail_url="https://example.com/amaral-gurgel",
            title="Amaral Gurgel em jornal",
            raw_text="João Amaral Gurgel negociou incentivos fiscais com Governo Federal.",
        )
    ]
    assert resolver.choose_subject_name("Amaral Gurgel", [], records) == "João Amaral Gurgel"


def test_story_response_is_usable_rejects_unknown_reference_codes() -> None:
    agent = mod.BnAcervoAgent()
    references = [
        {"id": "R1", "title": "Fonte 1", "detail_url": "https://example.com/1", "document_urls": [], "evidence_excerpt": "x"},
        {"id": "R2", "title": "Fonte 2", "detail_url": "https://example.com/2", "document_urls": [], "evidence_excerpt": "y"},
    ]
    bad_story = "## Historia\\nTexto com [R1].\\n\\n## Referencias\\n- [R1] ok\\n- [R4] inventada"
    assert not agent._story_response_is_usable(bad_story, references)


def test_investigation_job_store_persists_status_and_logs(tmp_path: Path) -> None:
    store = mod.InvestigationJobStore(tmp_path)
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", output_mode="dossier")
    created = store.create(payload)
    assert created["status"] == "queued"
    job_id = created["job_id"]
    store.update(job_id, status="running", phase="planning", progress_percent=12)
    store.append_log(job_id, level="info", message="Planejamento iniciado")
    loaded = store.load(job_id)
    assert loaded is not None
    assert loaded["status"] == "running"
    assert loaded["phase"] == "planning"
    assert loaded["progress_percent"] == 12
    assert any("Planejamento iniciado" in item["message"] for item in loaded["logs"])


def test_reconcile_active_jobs_marks_stale_records_as_cancelled(tmp_path: Path) -> None:
    store = mod.InvestigationJobStore(tmp_path)
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", output_mode="dossier")
    created = store.create(payload)
    job_id = created["job_id"]
    store.update(job_id, status="running", phase="documents", progress_percent=66)
    mod._JOB_TASKS.pop(job_id, None)
    active = mod._reconcile_active_jobs(store)
    assert active == []
    loaded = store.load(job_id)
    assert loaded is not None
    assert loaded["status"] == "cancelled"
    assert loaded["error"] == "stale_job_reconciled"


def test_cancel_job_marks_record_cancelled(tmp_path: Path) -> None:
    store = mod.InvestigationJobStore(tmp_path)
    payload = mod.AcervoStoryRequest(query="João Amaral Gurgel", output_mode="dossier")
    created = store.create(payload)
    job_id = created["job_id"]
    store.update(job_id, status="running", phase="planning", progress_percent=8)

    async def scenario() -> None:
        task = asyncio.create_task(asyncio.sleep(10))
        mod._JOB_TASKS[job_id] = task
        try:
            record = await mod._cancel_job(store, job_id, reason="cancelled_by_operator")
            assert record is not None
            assert record["status"] == "cancelled"
            assert record["error"] == "cancelled_by_operator"
            assert task.cancelled()
        finally:
            mod._JOB_TASKS.pop(job_id, None)

    asyncio.run(scenario())
