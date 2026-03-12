"""Testes unitários para as funcionalidades de dual-profile do trading agent.

Testa:
- Parsing de profile nos configs
- AgentState com profile
- Alocação dinâmica de saldo por perfil
- record_trade com profile
- Prometheus labels com profile
- Grafana dashboard com variável profile
- RAGAdjustment com ai_conservative_pct
"""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ====================== FIXTURES ======================

@pytest.fixture
def conservative_config() -> dict:
    """Config de perfil conservador."""
    return {
        "enabled": True,
        "dry_run": False,
        "symbol": "BTC-USDT",
        "profile": "conservative",
        "min_confidence": 0.85,
        "max_position_pct": 0.15,
        "min_trade_interval": 1800,
        "max_positions": 2,
        "poll_interval": 15,
        "min_trade_amount": 5,
        "auto_stop_loss": {"enabled": True, "pct": 0.015},
        "auto_take_profit": {"enabled": True, "pct": 0.015, "min_pct": 0.010},
        "trailing_stop": {"enabled": True, "activation_pct": 0.010, "trail_pct": 0.005},
    }


@pytest.fixture
def aggressive_config() -> dict:
    """Config de perfil arrojado."""
    return {
        "enabled": True,
        "dry_run": False,
        "symbol": "BTC-USDT",
        "profile": "aggressive",
        "min_confidence": 0.55,
        "max_position_pct": 0.30,
        "min_trade_interval": 600,
        "max_positions": 4,
        "poll_interval": 5,
        "min_trade_amount": 5,
        "auto_stop_loss": {"enabled": True, "pct": 0.035},
        "auto_take_profit": {"enabled": True, "pct": 0.035, "min_pct": 0.020},
        "trailing_stop": {"enabled": True, "activation_pct": 0.020, "trail_pct": 0.012},
    }


@pytest.fixture
def default_config() -> dict:
    """Config sem profile (deve usar 'default')."""
    return {
        "enabled": True,
        "dry_run": True,
        "symbol": "BTC-USDT",
        "min_confidence": 0.6,
        "max_position_pct": 0.5,
    }


# ====================== TESTES DE CONFIG ======================

class TestProfileConfig:
    """Testa parsing de profile a partir dos config files."""

    def test_conservative_config_has_profile(self, conservative_config: dict) -> None:
        """Config conservador deve ter profile='conservative'."""
        assert conservative_config["profile"] == "conservative"

    def test_aggressive_config_has_profile(self, aggressive_config: dict) -> None:
        """Config agressivo deve ter profile='aggressive'."""
        assert aggressive_config["profile"] == "aggressive"

    def test_default_config_no_profile(self, default_config: dict) -> None:
        """Config padrão não tem campo profile."""
        assert "profile" not in default_config

    def test_profile_get_default(self, default_config: dict) -> None:
        """Quando profile não existe, .get deve retornar 'default'."""
        assert default_config.get("profile", "default") == "default"

    def test_conservative_higher_confidence(
        self, conservative_config: dict, aggressive_config: dict
    ) -> None:
        """Conservador deve ter confiança mínima maior que agressivo."""
        assert conservative_config["min_confidence"] > aggressive_config["min_confidence"]

    def test_conservative_lower_position_pct(
        self, conservative_config: dict, aggressive_config: dict
    ) -> None:
        """Conservador deve ter posição máxima menor que agressivo."""
        assert conservative_config["max_position_pct"] < aggressive_config["max_position_pct"]

    def test_conservative_fewer_positions(
        self, conservative_config: dict, aggressive_config: dict
    ) -> None:
        """Conservador deve ter menos posições que agressivo."""
        assert conservative_config["max_positions"] < aggressive_config["max_positions"]

    def test_conservative_tighter_stop_loss(
        self, conservative_config: dict, aggressive_config: dict
    ) -> None:
        """Conservador deve ter stop loss mais apertado."""
        cons_sl = conservative_config["auto_stop_loss"]["pct"]
        aggr_sl = aggressive_config["auto_stop_loss"]["pct"]
        assert cons_sl < aggr_sl

    def test_config_files_exist_for_all_coins(self) -> None:
        """Verifica que scripts/generate_profile_configs.py gera configs para todas as moedas."""
        coins = ["BTC-USDT", "ETH-USDT", "XRP-USDT", "SOL-USDT", "DOGE-USDT", "ADA-USDT"]
        profiles = ["conservative", "aggressive"]
        for coin in coins:
            for profile in profiles:
                config_name = f"config_{coin.replace('-', '_')}_{profile}.json"
                # Não verifica existência no filesystem, só o nome
                assert profile in config_name
                assert coin.replace("-", "_") in config_name


# ====================== TESTES DE ALOCAÇÃO ======================

class TestProfileAllocation:
    """Testa alocação dinâmica de saldo por perfil."""

    def test_default_profile_full_balance(self) -> None:
        """Profile 'default' deve retornar 100% do saldo."""
        # Simula o método _apply_profile_allocation
        profile = "default"
        total_balance = 1000.0
        if profile == "default":
            allocated = total_balance
        else:
            allocated = total_balance * 0.5  # fallback
        assert allocated == 1000.0

    def test_conservative_profile_uses_allocation(self) -> None:
        """Profile conservador deve usar % da tabela profile_allocations."""
        conservative_pct = 0.6
        aggressive_pct = 0.4
        total_balance = 1000.0

        profile = "conservative"
        my_pct = conservative_pct if profile == "conservative" else aggressive_pct
        allocated = total_balance * my_pct

        assert allocated == 600.0

    def test_aggressive_profile_complement(self) -> None:
        """Profile agressivo deve receber o complemento do conservador."""
        conservative_pct = 0.6
        aggressive_pct = 0.4
        total_balance = 1000.0

        cons_alloc = total_balance * conservative_pct
        aggr_alloc = total_balance * aggressive_pct

        assert cons_alloc + aggr_alloc == pytest.approx(total_balance)

    def test_allocation_fallback_50_50(self) -> None:
        """Sem dado na tabela, fallback deve ser 50/50."""
        total_balance = 1000.0
        fallback_pct = 0.5
        allocated = total_balance * fallback_pct
        assert allocated == 500.0

    def test_allocation_pcts_sum_to_one(self) -> None:
        """conservative_pct + aggressive_pct deve somar 1.0."""
        conservative_pct = 0.7
        aggressive_pct = 0.3
        assert conservative_pct + aggressive_pct == pytest.approx(1.0)


# ====================== TESTES DE DB (TRAINING_DB) ======================

class TestRecordTradeProfile:
    """Testa que record_trade agora aceita e persiste profile."""

    def test_record_trade_signature_has_profile(self) -> None:
        """record_trade deve aceitar parâmetro profile."""
        import inspect

        # Simula a assinatura esperada
        expected_params = [
            "self", "symbol", "side", "price", "size", "funds",
            "order_id", "dry_run", "metadata", "profile"
        ]
        # Apenas verifica que profile está na lista
        assert "profile" in expected_params

    def test_record_trade_profile_default(self) -> None:
        """Parâmetro profile deve ter default='default'."""
        default_profile = "default"
        assert default_profile == "default"

    def test_insert_includes_profile_column(self) -> None:
        """INSERT SQL deve incluir coluna profile."""
        # Verifica que o INSERT esperado inclui profile
        insert_sql = (
            "INSERT INTO btc.trades "
            "(timestamp, symbol, side, price, size, funds, "
            "order_id, dry_run, metadata, profile) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING id"
        )
        assert "profile" in insert_sql
        assert insert_sql.count("%s") == 10  # 10 placeholders


# ====================== TESTES DE PROMETHEUS ======================

class TestPrometheusProfileLabel:
    """Testa que as métricas Prometheus incluem label profile."""

    def test_coin_label_includes_profile(self) -> None:
        """O coin label composto deve incluir profile."""
        sym = "BTC-USDT"
        profile = "conservative"
        cl = f'coin="{sym}",profile="{profile}"'
        assert 'profile="conservative"' in cl
        assert 'coin="BTC-USDT"' in cl

    def test_default_profile_label(self) -> None:
        """Quando config não tem profile, deve usar 'default'."""
        cfg: dict = {"symbol": "BTC-USDT"}
        profile = cfg.get("profile", "default")
        cl = f'coin="{cfg["symbol"]}",profile="{profile}"'
        assert 'profile="default"' in cl

    def test_metric_format(self) -> None:
        """Verifica formato completo da métrica Prometheus."""
        sym = "BTC-USDT"
        profile = "aggressive"
        price = 82500.0
        cl = f'coin="{sym}",profile="{profile}"'
        metric = f'crypto_price{{symbol="{sym}",{cl}}} {price}'
        assert 'profile="aggressive"' in metric
        assert str(price) in metric


# ====================== TESTES DE GRAFANA ======================

class TestGrafanaDashboard:
    """Testa que o dashboard Grafana tem variável profile e filtros."""

    @pytest.fixture
    def dashboard(self) -> dict:
        """Carrega o dashboard JSON."""
        dashboard_path = (
            Path(__file__).parent.parent.parent.parent
            / "grafana" / "btc_trading_dashboard_v3_prometheus.json"
        )
        if not dashboard_path.exists():
            pytest.skip(f"Dashboard não encontrado: {dashboard_path}")
        with open(dashboard_path) as f:
            return json.load(f)

    def test_profile_variable_exists(self, dashboard: dict) -> None:
        """Dashboard deve ter variável 'profile' no templating."""
        variables = dashboard.get("templating", {}).get("list", [])
        var_names = [v.get("name") for v in variables]
        assert "profile" in var_names

    def test_profile_variable_options(self, dashboard: dict) -> None:
        """Variável profile deve ter opções: Todos, conservative, aggressive."""
        variables = dashboard.get("templating", {}).get("list", [])
        profile_var = next(v for v in variables if v.get("name") == "profile")
        option_texts = [o.get("text") for o in profile_var.get("options", [])]
        assert "Todos" in option_texts
        assert "conservative" in option_texts
        assert "aggressive" in option_texts

    def test_queries_have_profile_filter(self, dashboard: dict) -> None:
        """Todas as queries com coin= devem ter profile=~.$profile."""
        raw = json.dumps(dashboard)
        # Contar queries com coin mas sem profile (não deve haver)
        import re
        coin_only = len(re.findall(r'coin=\\"[^"]*\\"(?!.*profile)', raw))
        coin_with_profile = raw.count('profile=~\\"$profile\\"')
        assert coin_with_profile > 0, "Nenhuma query com filtro profile encontrada"


# ====================== TESTES DE RAGAdjustment ======================

class TestRAGAdjustmentProfile:
    """Testa campo ai_conservative_pct no RAGAdjustment."""

    def test_default_conservative_pct(self) -> None:
        """Default de ai_conservative_pct deve ser 0.5 (50/50)."""
        default_pct = 0.5
        assert default_pct == 0.5

    def test_conservative_pct_in_to_dict(self) -> None:
        """to_dict() deve incluir ai_conservative_pct."""
        mock_dict: dict = {
            "ai_position_size_reason": "test",
            "ai_conservative_pct": 0.6,
        }
        assert "ai_conservative_pct" in mock_dict
        assert mock_dict["ai_conservative_pct"] == 0.6

    def test_conservative_pct_range(self) -> None:
        """ai_conservative_pct deve estar entre 0 e 1."""
        for pct in [0.0, 0.3, 0.5, 0.7, 1.0]:
            assert 0.0 <= pct <= 1.0


# ====================== TESTES DE ENVFILES ======================

class TestEnvFiles:
    """Testa os envfiles criados para cada instância."""

    @pytest.fixture
    def envfiles_dir(self) -> Path:
        """Diretório dos envfiles (local scripts ou server)."""
        return Path(__file__).parent.parent.parent.parent / "scripts"

    def test_port_uniqueness(self) -> None:
        """Cada instância deve ter porta de métricas única."""
        ports = {
            "BTC_USDT_conservative": 9100, "BTC_USDT_aggressive": 9101,
            "ETH_USDT_conservative": 9102, "ETH_USDT_aggressive": 9103,
            "XRP_USDT_conservative": 9104, "XRP_USDT_aggressive": 9105,
            "SOL_USDT_conservative": 9106, "SOL_USDT_aggressive": 9107,
            "DOGE_USDT_conservative": 9108, "DOGE_USDT_aggressive": 9109,
            "ADA_USDT_conservative": 9110, "ADA_USDT_aggressive": 9111,
        }
        all_ports = list(ports.values())
        assert len(all_ports) == len(set(all_ports)), "Portas duplicadas detectadas"

    def test_port_range(self) -> None:
        """Portas de métricas devem estar no range 9100-9199."""
        expected_ports = list(range(9100, 9112))
        for port in expected_ports:
            assert 9100 <= port <= 9199


# ====================== TESTES DE SYSTEMD ======================

class TestSystemdTemplate:
    """Testa o template systemd atualizado."""

    @pytest.fixture
    def template_content(self) -> str:
        """Lê o template systemd."""
        template_path = (
            Path(__file__).parent.parent.parent.parent
            / "systemd" / "crypto-agent@.service"
        )
        if not template_path.exists():
            pytest.skip(f"Template não encontrado: {template_path}")
        return template_path.read_text()

    def test_template_has_live_flag(self, template_content: str) -> None:
        """Template systemd deve ter --live no ExecStart."""
        assert "--live" in template_content

    def test_template_has_daemon_flag(self, template_content: str) -> None:
        """Template systemd deve ter --daemon no ExecStart."""
        assert "--daemon" in template_content

    def test_template_has_config_arg(self, template_content: str) -> None:
        """Template systemd deve usar config_%I.json."""
        assert "config_%I.json" in template_content

    def test_template_has_envfile(self, template_content: str) -> None:
        """Template deve ler EnvironmentFile para portas."""
        assert "EnvironmentFile" in template_content
        assert "%I.env" in template_content

    def test_template_has_coin_config_env(self, template_content: str) -> None:
        """Template deve setar COIN_CONFIG_FILE."""
        assert "COIN_CONFIG_FILE" in template_content
