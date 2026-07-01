from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import requests


TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
MODULE_PATH = TOOLS_DIR / "build_flavio_bolsonaro_agenda_source.py"
sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("build_flavio_bolsonaro_agenda_source", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
agenda_source = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = agenda_source
_SPEC.loader.exec_module(agenda_source)


CDR_HTML = """
<html><body>
<a href="/atividade/comissoes/comissao/1306/reuniao/99999">
17/06 Quarta 9 h30 10ª Reunião, Extraordinária Semipresencial Deliberação de Indicações de Emendas RP8/2026 - 5º Ciclo Agendada
</a>
</body></html>
"""

CDH_HTML = """
<html><body>
<a href="/atividade/comissoes/comissao/834/reuniao/14728">
17/06 Quarta 11 h00 39ª Reunião, Extraordinária Semipresencial Deliberativa Agendada
</a>
</body></html>
"""

CDH_MEETING_HTML = """
<html><body>
<a href="https://www25.senado.leg.br/web/atividade/materias/-/materia/170486">Ver PL 4598/2025</a>
<a href="https://www25.senado.leg.br/web/atividade/materias/-/materia/169474">Ver PL 3283/2025</a>
<a href="https://www25.senado.leg.br/web/atividade/materias/-/materia/169904">Ver PL 3980/2025</a>
<div>
8 - PL 4598/2025 Ver PL 4598/2025 Ementa Altera o Código Penal para incluir agravante em crimes contra pessoa com deficiência ou neurodivergente. Relator Senador Alessandro Vieira Relatório Favorável ao projeto com uma emenda que apresenta. Observação Tramitação: CDH e terminativo na CCJ.
9 - PL 3283/2025 Ver PL 3283/2025 Ementa Altera o art. 19 da Lei nº 12.965, de 23 de abril de 2014, para dispor sobre obrigatoriedade de comunicação pelo provedor quando da indisponibilidade de conteúdo sem ordem judicial. Relator Senador Flávio Bolsonaro Relatório Favorável ao projeto, com uma emenda que apresenta. Observação Tramitação: CDH e terminativo na CCJ.
10 - PL 3980/2025 Ver PL 3980/2025 Ementa Dispõe sobre a obrigatoriedade de cobertura integral e prioritária, no âmbito do Sistema Único de Saúde, de exames diagnósticos especializados para identificação precoce do transtorno do espectro autista. Relator Senador Flávio Arns Relatório Favorável ao projeto. Observação Tramitação: CDH e terminativo na CAS.
</div>
</body></html>
"""

PL_4598_HTML = """
<html><body>
<h1>Projeto de Lei n° 4598, de 2025</h1>
<p>Autoria: Senador Flávio Bolsonaro (PL/RJ)</p>
<p>Assunto: Direito Penal</p>
<p>Ementa: Altera o Código Penal para incluir agravante em crimes contra pessoa com deficiência ou neurodivergente.</p>
<a>Texto inicial</a>
</body></html>
"""

PL_3980_HTML = """
<html><body>
<h1>Projeto de Lei n° 3980, de 2025</h1>
<p>Autoria: Senador Flávio Bolsonaro (PL/RJ)</p>
<p>Assunto: Saúde Pública</p>
<p>Ementa: Dispõe sobre a obrigatoriedade de cobertura integral e prioritária, no âmbito do Sistema Único de Saúde, de exames diagnósticos especializados para identificação precoce do transtorno do espectro autista.</p>
<a>Entenda a proposta</a>
<p>O que é A proposta estabelece que o Sistema Único de Saúde deve oferecer exames diagnósticos especializados de forma integral e prioritária para identificar precocemente o transtorno do espectro autista. O que diz o autor A medida amplia o acesso.</p>
</body></html>
"""

PL_3283_HTML = """
<html><body>
<h1>Projeto de Lei n° 3283, de 2025</h1>
<p>Autoria: Senador Esperidião Amin (PP/SC)</p>
<p>Assunto: Internet</p>
<p>Ementa: Altera o art. 19 da Lei nº 12.965, de 23 de abril de 2014, para dispor sobre obrigatoriedade de comunicação pelo provedor quando da indisponibilidade de conteúdo sem ordem judicial.</p>
<a>Entenda a proposta</a>
<p>O que é A proposta estabelece que, quando um provedor de internet remover conteúdo sem ordem judicial, ele deve comunicar o fato a órgãos públicos e instituições de controle. O que diz o autor A medida busca mais transparência.</p>
</body></html>
"""


def test_build_source_text_contextualiza_autoria_e_relatoria() -> None:
    entries = agenda_source.AGENDA_BY_DATE["2026-06-17"]

    result = agenda_source.build_source_text(
        entries,
        date_label="esta quarta-feira, 17 de junho de 2026",
    )

    assert "Flávio Bolsonaro tem dois compromissos públicos" in result
    assert "Comissão de Desenvolvimento Regional e Turismo" in result
    assert "Comissão de Direitos Humanos e Legislação Participativa" in result
    assert "Entre as matérias de sua autoria em pauta" in result
    assert "Há também matéria sob sua relatoria" in result
    assert "Esperidião Amin" in result


def test_iter_sources_retorna_urls_unicas() -> None:
    entries = agenda_source.AGENDA_BY_DATE["2026-06-17"]

    urls = agenda_source.iter_sources(entries)

    assert len(urls) == len(set(urls))
    assert agenda_source.PROFILE_URL in urls
    assert "https://www25.senado.leg.br/web/atividade/materias/-/materia/170486" in urls


def test_find_meeting_link_and_extract_committee_entry() -> None:
    meeting_url = agenda_source.find_meeting_link(CDH_HTML, date_token="17/06")
    entry = agenda_source.extract_committee_entry(
        CDR_HTML,
        date_token="17/06",
        committee_name="Comissão de Desenvolvimento Regional e Turismo",
        committee_sigla="CDR",
        source_url=agenda_source.CDR_URL,
    )

    assert meeting_url == "https://legis.senado.leg.br/atividade/comissoes/comissao/834/reuniao/14728"
    assert entry.time_label == "9h30"
    assert "RP-8" in entry.summary


def test_load_live_entries_parseia_agenda_e_materias(monkeypatch) -> None:
    html_by_url = {
        agenda_source.CDR_URL: CDR_HTML,
        agenda_source.CDH_URL: CDH_HTML,
        "https://legis.senado.leg.br/atividade/comissoes/comissao/834/reuniao/14728": CDH_MEETING_HTML,
        "https://www25.senado.leg.br/web/atividade/materias/-/materia/170486": PL_4598_HTML,
        "https://www25.senado.leg.br/web/atividade/materias/-/materia/169904": PL_3980_HTML,
        "https://www25.senado.leg.br/web/atividade/materias/-/materia/169474": PL_3283_HTML,
    }

    def fake_fetch_html(url: str, *, timeout: int, trust_env: bool) -> str:
        del timeout, trust_env
        return html_by_url[url]

    monkeypatch.setattr(agenda_source, "fetch_html", fake_fetch_html)

    entries = agenda_source.load_live_entries(
        "2026-06-17",
        timeout=10,
        trust_env=False,
    )

    assert len(entries) == 2
    assert entries[0].time_label == "9h30"
    assert entries[1].time_label == "11h00"
    assert len(entries[1].materials) == 3
    roles = {item.code: item.role for item in entries[1].materials}
    assert roles["PL 4598/2025"] == "autoria"
    assert roles["PL 3980/2025"] == "autoria"
    assert roles["PL 3283/2025"] == "relatoria"


def test_load_entries_auto_cai_para_snapshot(monkeypatch) -> None:
    def fake_fetch_html(url: str, *, timeout: int, trust_env: bool) -> str:
        del url, timeout, trust_env
        raise requests.Timeout("timeout")

    monkeypatch.setattr(agenda_source, "fetch_html", fake_fetch_html)

    entries = agenda_source.load_entries(
        "2026-06-17",
        mode="auto",
        timeout=10,
        trust_env=False,
    )

    assert len(entries) == 2
    assert entries[0].committee_sigla == "CDR"
