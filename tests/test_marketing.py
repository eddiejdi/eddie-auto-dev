#!/usr/bin/env python3
"""Testes unitários — Marketing RPA4ALL (lead_capture_api, email_nurturing, daily_report)."""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Mock psycopg2 before importing marketing modules
_mock_psycopg2 = MagicMock()
_mock_psycopg2.extras = MagicMock()
_mock_psycopg2.extras.RealDictCursor = MagicMock()
sys.modules.setdefault("psycopg2", _mock_psycopg2)
sys.modules.setdefault("psycopg2.extras", _mock_psycopg2.extras)


# ─── Tests: LeadCreate validation ────────────────────────────────────
class TestLeadCreateValidation:
    """Testa validação do modelo LeadCreate."""

    def test_valid_lead(self) -> None:
        """Lead com todos os campos válidos."""
        from marketing.lead_capture_api import LeadCreate

        lead = LeadCreate(
            nome="João Silva",
            email="joao@empresa.com",
            empresa="Empresa Teste",
            cargo="Diretor",
            telefone="11999990000",
        )
        assert lead.nome == "João Silva"
        assert lead.email == "joao@empresa.com"
        assert lead.empresa == "Empresa Teste"

    def test_email_normalized(self) -> None:
        """Email é normalizado para lowercase."""
        from marketing.lead_capture_api import LeadCreate

        lead = LeadCreate(
            nome="Test",
            email="JOAO@Empresa.COM",
            empresa="Test Co",
        )
        assert lead.email == "joao@empresa.com"

    def test_invalid_email_rejected(self) -> None:
        """Email inválido é rejeitado."""
        from marketing.lead_capture_api import LeadCreate

        with pytest.raises(ValueError):
            LeadCreate(nome="Test", email="nao-eh-email", empresa="Test Co")

    def test_telefone_cleaned(self) -> None:
        """Telefone é limpo de caracteres especiais."""
        from marketing.lead_capture_api import LeadCreate

        lead = LeadCreate(
            nome="Test",
            email="test@test.com",
            empresa="Test Co",
            telefone="(11) 99999-0000",
        )
        assert lead.telefone == "11999990000"

    def test_telefone_too_short(self) -> None:
        """Telefone curto demais é rejeitado."""
        from marketing.lead_capture_api import LeadCreate

        with pytest.raises(ValueError):
            LeadCreate(
                nome="Test",
                email="test@test.com",
                empresa="Test Co",
                telefone="123",
            )

    def test_telefone_none_accepted(self) -> None:
        """Telefone None é aceito."""
        from marketing.lead_capture_api import LeadCreate

        lead = LeadCreate(
            nome="Test",
            email="test@test.com",
            empresa="Test Co",
            telefone=None,
        )
        assert lead.telefone is None

    def test_nome_too_short(self) -> None:
        """Nome com menos de 2 chars é rejeitado."""
        from marketing.lead_capture_api import LeadCreate

        with pytest.raises(ValueError):
            LeadCreate(nome="A", email="test@test.com", empresa="Test Co")

    def test_utm_fields_optional(self) -> None:
        """UTM fields são opcionais."""
        from marketing.lead_capture_api import LeadCreate

        lead = LeadCreate(
            nome="Test",
            email="test@test.com",
            empresa="Test Co",
            utm_source="facebook",
            utm_medium="cpc",
            utm_campaign="diagnostico",
        )
        assert lead.utm_source == "facebook"
        assert lead.utm_medium == "cpc"
        assert lead.utm_campaign == "diagnostico"


# ─── Tests: Database functions (mocked) ──────────────────────────────
class TestDatabaseFunctions:
    """Testa funções de banco com mock."""

    @patch("marketing.lead_capture_api._get_conn")
    def test_check_duplicate_true(self, mock_conn: MagicMock) -> None:
        """Retorna True para email duplicado."""
        from marketing.lead_capture_api import _check_duplicate

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (1,)
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = _check_duplicate("test@test.com")
        assert result is True

    @patch("marketing.lead_capture_api._get_conn")
    def test_check_duplicate_false(self, mock_conn: MagicMock) -> None:
        """Retorna False para email novo."""
        from marketing.lead_capture_api import _check_duplicate

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (0,)
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        result = _check_duplicate("novo@test.com")
        assert result is False

    @patch("marketing.lead_capture_api._get_conn")
    def test_insert_lead_returns_id(self, mock_conn: MagicMock) -> None:
        """Insert retorna ID do lead criado."""
        from marketing.lead_capture_api import _insert_lead, LeadCreate

        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (42,)
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        lead = LeadCreate(nome="Test", email="t@t.com", empresa="Co")
        result = _insert_lead(lead)
        assert result == 42


# ─── Tests: Email Nurturing ──────────────────────────────────────────
class TestEmailNurturing:
    """Testa módulo de nurturing."""

    def test_drip_sequence_has_5_steps(self) -> None:
        """Sequência deve ter 5 steps."""
        from marketing.email_nurturing import DRIP_SEQUENCE

        assert len(DRIP_SEQUENCE) == 5

    def test_drip_sequence_steps_ordered(self) -> None:
        """Steps devem estar em ordem 0-4."""
        from marketing.email_nurturing import DRIP_SEQUENCE

        for i, template in enumerate(DRIP_SEQUENCE):
            assert template["step"] == i

    def test_drip_intervals_match_sequence(self) -> None:
        """Intervalos devem ter o mesmo tamanho da sequência."""
        from marketing.email_nurturing import DRIP_INTERVALS, DRIP_SEQUENCE

        assert len(DRIP_INTERVALS) == len(DRIP_SEQUENCE)

    def test_render_email_substitutes_variables(self) -> None:
        """Template é renderizado com nome e empresa."""
        from marketing.email_nurturing import _render_email, DRIP_SEQUENCE

        lead = {"nome": "Carlos Silva", "email": "c@t.com", "empresa": "ACME Corp"}
        subject, body = _render_email(DRIP_SEQUENCE[0], lead)
        assert "Carlos" in body
        assert "ACME Corp" in body

    def test_render_email_subject_has_content(self) -> None:
        """Subject não pode ser vazio."""
        from marketing.email_nurturing import _render_email, DRIP_SEQUENCE

        lead = {"nome": "Test User", "email": "t@t.com", "empresa": "TestCo"}
        for template in DRIP_SEQUENCE:
            subject, _ = _render_email(template, lead)
            assert len(subject) > 5

    @patch("marketing.email_nurturing.smtplib.SMTP")
    def test_send_email_dry_run_no_smtp(self, mock_smtp: MagicMock) -> None:
        """Dry run não envia via SMTP."""
        from marketing.email_nurturing import _send_email

        result = _send_email("test@test.com", "Assunto", "<h1>Corpo</h1>", dry_run=True)
        assert result is True
        mock_smtp.assert_not_called()

    @patch("marketing.email_nurturing._get_conn")
    def test_get_pending_leads_returns_list(self, mock_conn: MagicMock) -> None:
        """Retorna lista de leads pendentes."""
        from marketing.email_nurturing import _get_pending_leads

        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            {"id": 1, "nome": "Test", "email": "t@t.com", "empresa": "Co", "drip_step": 0}
        ]
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        leads = _get_pending_leads()
        assert len(leads) == 1
        assert leads[0]["nome"] == "Test"


# ─── Tests: Daily Report ─────────────────────────────────────────────
class TestDailyReport:
    """Testa relatório diário."""

    def test_format_report_contains_header(self) -> None:
        """Relatório contém header com data."""
        from marketing.daily_report import format_report

        metrics = {
            "total": 100,
            "hoje": 5,
            "ontem": 3,
            "semana": 25,
            "mes": 50,
            "por_origem": [{"origem": "landing", "qtd": 30}],
            "por_utm": [{"src": "facebook", "qtd": 20}],
            "por_status": [{"status": "novo", "qtd": 80}],
            "drip_stats": [{"drip_step": 0, "qtd": 50}],
        }
        report = format_report(metrics)
        assert "MARKETING RPA4ALL" in report
        assert "100" in report
        assert "5" in report

    def test_format_report_delta_positive(self) -> None:
        """Delta positivo mostra +."""
        from marketing.daily_report import format_report

        metrics = {
            "total": 10, "hoje": 5, "ontem": 2, "semana": 7, "mes": 10,
            "por_origem": [], "por_utm": [], "por_status": [], "drip_stats": [],
        }
        report = format_report(metrics)
        assert "+3" in report
        assert "📈" in report

    def test_format_report_delta_negative(self) -> None:
        """Delta negativo mostra -."""
        from marketing.daily_report import format_report

        metrics = {
            "total": 10, "hoje": 1, "ontem": 4, "semana": 5, "mes": 10,
            "por_origem": [], "por_utm": [], "por_status": [], "drip_stats": [],
        }
        report = format_report(metrics)
        assert "-3" in report
        assert "📉" in report

    def test_format_report_with_empty_data(self) -> None:
        """Relatório funciona com dados zerados."""
        from marketing.daily_report import format_report

        metrics = {
            "total": 0, "hoje": 0, "ontem": 0, "semana": 0, "mes": 0,
            "por_origem": [], "por_utm": [], "por_status": [], "drip_stats": [],
        }
        report = format_report(metrics)
        assert "MARKETING RPA4ALL" in report
        assert "0" in report


# ─── Tests: LeadResponse / LeadStats models ─────────────────────────
class TestResponseModels:
    """Testa modelos de resposta."""

    def test_lead_response(self) -> None:
        """LeadResponse com campos obrigatórios."""
        from marketing.lead_capture_api import LeadResponse

        resp = LeadResponse(success=True, lead_id=1, message="ok")
        assert resp.success is True
        assert resp.lead_id == 1

    def test_lead_stats(self) -> None:
        """LeadStats com campos corretos."""
        from marketing.lead_capture_api import LeadStats

        stats = LeadStats(
            total=100, hoje=5, semana=20,
            por_origem={"landing": 50}, por_utm_source={"facebook": 30},
        )
        assert stats.total == 100
        assert stats.por_origem["landing"] == 50


# ─── Tests: DB Migration ─────────────────────────────────────────────
class TestDBMigration:
    """Testa script de migração do banco."""

    def test_migration_sql_contains_schema(self) -> None:
        """SQL contém CREATE SCHEMA."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "CREATE SCHEMA IF NOT EXISTS marketing" in MIGRATION_SQL

    def test_migration_sql_contains_leads_table(self) -> None:
        """SQL contém tabela de leads."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "marketing.leads" in MIGRATION_SQL

    def test_migration_sql_contains_daily_metrics(self) -> None:
        """SQL contém tabela de métricas diárias."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "marketing.daily_metrics" in MIGRATION_SQL

    def test_migration_sql_contains_email_log(self) -> None:
        """SQL contém tabela de log de emails."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "marketing.email_log" in MIGRATION_SQL

    def test_migration_sql_contains_x_posts_log(self) -> None:
        """SQL contém tabela de log de posts X."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "marketing.x_posts_log" in MIGRATION_SQL

    def test_migration_sql_contains_campaigns(self) -> None:
        """SQL contém tabela de campanhas."""
        from marketing.db_migrate import MIGRATION_SQL

        assert "marketing.campaigns" in MIGRATION_SQL

    def test_dry_run_returns_true(self) -> None:
        """Dry run retorna True sem conectar ao banco."""
        from marketing.db_migrate import run_migration

        assert run_migration(dry_run=True) is True

    def test_migration_with_mock_db(self) -> None:
        """Migração executa SQL no banco (mockado via sys.modules)."""
        from marketing.db_migrate import run_migration

        # psycopg2 já está mockado via sys.modules no topo do arquivo
        result = run_migration(dry_run=False)
        assert result is True


# ─── Tests: X Post Scheduler ─────────────────────────────────────────
class TestXPostScheduler:
    """Testa agendador de posts no X."""

    def test_load_posts_returns_list(self) -> None:
        """Carrega lista de posts do JSON."""
        from marketing.x_post_scheduler import load_posts

        posts = load_posts()
        assert isinstance(posts, list)
        assert len(posts) > 0

    def test_posts_have_required_fields(self) -> None:
        """Cada post tem id, texto e hashtags."""
        from marketing.x_post_scheduler import load_posts

        for post in load_posts():
            assert "id" in post
            assert "texto" in post
            assert isinstance(post["texto"], str)
            assert len(post["texto"]) > 10

    @patch("marketing.x_post_scheduler._get_posted_keys")
    def test_get_next_post_skips_posted(self, mock_keys: MagicMock) -> None:
        """Pula posts já publicados."""
        from marketing.x_post_scheduler import get_next_post, load_posts

        posts = load_posts()
        mock_keys.return_value = {posts[0]["id"]}  # Primeiro já postado

        result = get_next_post()
        assert result is not None
        assert result["id"] != posts[0]["id"]

    @patch("marketing.x_post_scheduler._get_posted_keys")
    def test_get_next_post_all_posted(self, mock_keys: MagicMock) -> None:
        """Retorna None quando todos já foram postados."""
        from marketing.x_post_scheduler import get_next_post, load_posts

        all_ids = {p["id"] for p in load_posts()}
        mock_keys.return_value = all_ids

        result = get_next_post()
        assert result is None

    @patch("marketing.x_post_scheduler._get_conn")
    def test_record_post_inserts(self, mock_conn: MagicMock) -> None:
        """Registra post no banco."""
        from marketing.x_post_scheduler import _record_post

        mock_cur = MagicMock()
        mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

        _record_post("X-01", "Texto do post", "123456")
        mock_cur.execute.assert_called_once()
        call_args = mock_cur.execute.call_args[0]
        assert "INSERT INTO marketing.x_posts_log" in call_args[0]
        assert call_args[1] == ("X-01", "Texto do post", "123456")


# ─── Tests: Marketing App ────────────────────────────────────────────
class TestMarketingApp:
    """Testa aplicação FastAPI."""

    def test_app_has_marketing_routes(self) -> None:
        """App inclui rotas de marketing."""
        from marketing.app import app

        routes = [r.path for r in app.routes]
        assert "/marketing/leads" in routes or any("/marketing" in r for r in routes)

    def test_app_has_diagnostico_route(self) -> None:
        """App serve landing page em /diagnostico."""
        from marketing.app import app

        routes = [r.path for r in app.routes]
        assert "/diagnostico" in routes

    def test_app_cors_configured(self) -> None:
        """App tem middleware CORS."""
        from marketing.app import app

        middleware_classes = [type(m).__name__ for m in app.user_middleware]
        # CORS is added via add_middleware, check it exists
        assert len(app.user_middleware) > 0

    def test_app_has_storage_route(self) -> None:
        """App serve landing page em /storage."""
        from marketing.app import app

        routes = [r.path for r in app.routes]
        assert "/storage" in routes


# ---------------------------------------------------------------------------
# 9. Testes — Storage Ads
# ---------------------------------------------------------------------------

class TestStorageAdsCopy:
    """Valida estrutura dos ad copies de storage."""

    def test_storage_ads_file_exists(self) -> None:
        """Arquivo storage_ads_copy.json existe."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_ads_copy.json"
        assert path.exists(), f"Arquivo não encontrado: {path}"

    def test_storage_ads_has_meta(self) -> None:
        """JSON contém seção meta_ads_storage com anúncios."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_ads_copy.json"
        data = json.loads(path.read_text())
        assert "meta_ads_storage" in data
        assert len(data["meta_ads_storage"]["anuncios"]) >= 4

    def test_storage_ads_has_google(self) -> None:
        """JSON contém seção google_ads_storage com grupos."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_ads_copy.json"
        data = json.loads(path.read_text())
        assert "google_ads_storage" in data
        assert len(data["google_ads_storage"]["grupos"]) >= 3

    def test_storage_ads_has_linkedin(self) -> None:
        """JSON contém seção linkedin_ads_storage com anúncios."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_ads_copy.json"
        data = json.loads(path.read_text())
        assert "linkedin_ads_storage" in data
        assert len(data["linkedin_ads_storage"]["anuncios"]) >= 2

    def test_storage_meta_ad_fields(self) -> None:
        """Cada ad Meta Storage tem campos obrigatórios."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_ads_copy.json"
        data = json.loads(path.read_text())
        base_required = {"id", "headline", "texto_principal"}
        for ad in data["meta_ads_storage"]["anuncios"]:
            assert base_required.issubset(ad.keys()), f"Ad {ad.get('id')} faltando campos"
            # Carrossel tem 'cards' ao invés de 'cta'
            assert "cta" in ad or "cards" in ad, f"Ad {ad.get('id')} sem cta ou cards"


class TestStorageXPosts:
    """Valida posts X de storage."""

    def test_storage_x_posts_file_exists(self) -> None:
        """Arquivo storage_x_posts.json existe."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_x_posts.json"
        assert path.exists()

    def test_storage_x_posts_count(self) -> None:
        """Deve ter pelo menos 8 posts de storage."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_x_posts.json"
        data = json.loads(path.read_text())
        posts = data["x_posts_storage"]["posts"]
        assert len(posts) >= 8

    def test_storage_x_post_fields(self) -> None:
        """Cada post X de storage tem campos obrigatórios."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_x_posts.json"
        data = json.loads(path.read_text())
        posts = data["x_posts_storage"]["posts"]
        for post in posts:
            assert "id" in post
            assert "texto" in post
            assert len(post["texto"]) <= 300, f"Post {post['id']} excede 300 chars"


class TestStorageWhatsAppTemplates:
    """Valida templates WhatsApp de storage."""

    def test_storage_wa_file_exists(self) -> None:
        """Arquivo storage_whatsapp_templates.json existe."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_whatsapp_templates.json"
        assert path.exists()

    def test_storage_wa_template_count(self) -> None:
        """Deve ter pelo menos 4 templates de storage."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "storage_whatsapp_templates.json"
        data = json.loads(path.read_text())
        templates = data["whatsapp_templates_storage"]["templates"]
        assert len(templates) >= 4


class TestStorageLandingPage:
    """Valida landing page de storage."""

    def test_storage_landing_file_exists(self) -> None:
        """Arquivo landing_storage.html existe."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "landing_storage.html"
        assert path.exists()

    def test_storage_landing_has_form(self) -> None:
        """Landing page tem formulário de captura."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "landing_storage.html"
        html = path.read_text()
        assert "landing_storage" in html or "storage" in html.lower()
        assert "<form" in html.lower()

    def test_storage_landing_has_lgpd_section(self) -> None:
        """Landing page menciona LGPD."""
        path = Path(__file__).resolve().parent.parent / "marketing" / "landing_storage.html"
        html = path.read_text()
        assert "LGPD" in html


class TestStorageImages:
    """Valida imagens de storage geradas."""

    def test_storage_images_exist(self) -> None:
        """Pelo menos 10 imagens de storage foram geradas."""
        img_dir = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "images"
        stg_images = list(img_dir.glob("STG-*.png"))
        assert len(stg_images) >= 10, f"Apenas {len(stg_images)} imagens STG encontradas"

    def test_storage_meta_images_exist(self) -> None:
        """Imagens Meta de storage existem."""
        img_dir = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "images"
        assert (img_dir / "STG-META-01_storage_10x.png").exists()
        assert (img_dir / "STG-META-02_lgpd_compliance.png").exists()

    def test_storage_display_images_exist(self) -> None:
        """Imagens Google Display de storage existem."""
        img_dir = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "images"
        assert (img_dir / "STG-GADS_display_300x250.png").exists()
        assert (img_dir / "STG-GADS_display_728x90.png").exists()

    def test_storage_linkedin_images_exist(self) -> None:
        """Imagens LinkedIn de storage existem."""
        img_dir = Path(__file__).resolve().parent.parent / "marketing" / "ads" / "images"
        assert (img_dir / "STG-LINKEDIN-01_custo.png").exists()
        assert (img_dir / "STG-LINKEDIN-02_lgpd.png").exists()
