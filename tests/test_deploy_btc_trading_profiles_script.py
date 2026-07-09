"""Regression checks for the BTC trading deploy shell script."""

from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "deploy_btc_trading_profiles.sh"


def _load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_syncs_btc_dashboard_to_canonical_remote_filename() -> None:
    content = _load_script()
    assert 'BTC_DASHBOARD_SRC="${REPO_ROOT}/grafana/dashboards/btc-trading-monitor.json"' in content
    assert 'BTC_DASHBOARD_DST="${GRAFANA_PROVISIONING_DIR}/btc-trading-monitor.json"' in content
    assert "sync_btc_grafana_dashboard" in content


def test_script_archives_duplicate_btc_dashboard_files_before_grafana_restart() -> None:
    content = _load_script()
    assert '"${GRAFANA_PROVISIONING_DIR}/btc_trading_monitor.json"' in content
    assert '"${GRAFANA_PROVISIONING_DIR}/btc_trading_dashboard_v3_prometheus.json"' in content
    assert "dashboard_backups" in content
    assert "cleanup_btc_dashboard_duplicates" in content
    assert content.index("cleanup_btc_dashboard_duplicates") < content.index("restart_grafana_if_present")


def test_script_defaults_to_live_crypto_agent_service_user() -> None:
    content = _load_script()
    assert 'SERVICE_USER="${SERVICE_USER:-btc-trading}"' in content
    assert 'SERVICE_GROUP="${SERVICE_GROUP:-btc-trading}"' in content
    assert 'sudo -u "${SERVICE_USER}" /usr/bin/python3 -m py_compile' in content


def test_script_installs_canonical_btc_trading_sudoers_file() -> None:
    content = _load_script()
    assert "sudo rm -f /etc/sudoers.d/trading-svc-ollama" in content
    assert 'systemd/btc-trading-ollama.sudoers' in content
    assert "/etc/sudoers.d/btc-trading-ollama" in content


def test_script_restarts_all_crypto_exporters_using_shared_exporter_code() -> None:
    content = _load_script()
    for unit in (
        "crypto-exporter@BTC_USDT_conservative.service",
        "crypto-exporter@BTC_USDT_aggressive.service",
        "crypto-exporter@BTC_USDT_shadow.service",
        "crypto-exporter@ETH_USDT_conservative.service",
        "crypto-exporter@ETH_USDT_aggressive.service",
        "crypto-exporter@ETH_USDT_shadow.service",
        "crypto-exporter@SOL_USDT_conservative.service",
        "crypto-exporter@SOL_USDT_aggressive.service",
        "crypto-exporter@SOL_USDT_shadow.service",
    ):
        assert unit in content


def test_script_restarts_all_crypto_agents_that_share_runtime_code() -> None:
    """Todos os perfis que rodam o trading_agent.py compartilhado devem ser
    reiniciados no deploy — senão ficam com código antigo em memória (foi o que
    deixou ETH sem log de llm_calls na Fase 1)."""
    content = _load_script()
    agent_block = content.split("AGENT_SERVICES=(", 1)[1].split(")", 1)[0]
    for unit in (
        "crypto-agent@BTC_USDT_conservative.service",
        "crypto-agent@BTC_USDT_aggressive.service",
        "crypto-agent@BTC_USDT_shadow.service",
        "crypto-agent@ETH_USDT_conservative.service",
        "crypto-agent@ETH_USDT_aggressive.service",
        "crypto-agent@ETH_USDT_shadow.service",
        "crypto-agent@SOL_USDT_conservative.service",
        "crypto-agent@SOL_USDT_aggressive.service",
        "crypto-agent@SOL_USDT_shadow.service",
    ):
        assert unit in agent_block, f"{unit} ausente de AGENT_SERVICES"
    # Paridade agents ↔ exporters: mesmos 6 perfis nos dois arrays.
    exporter_block = content.split("EXPORTER_SERVICES=(", 1)[1].split(")", 1)[0]
    agent_profiles = {
        line.split("@", 1)[1].split(".service")[0]
        for line in agent_block.splitlines()
        if "crypto-agent@" in line
    }
    exporter_profiles = {
        line.split("@", 1)[1].split(".service")[0]
        for line in exporter_block.splitlines()
        if "crypto-exporter@" in line
    }
    assert agent_profiles == exporter_profiles, (
        "AGENT_SERVICES e EXPORTER_SERVICES devem cobrir os mesmos perfis; "
        f"diferença: {agent_profiles ^ exporter_profiles}"
    )


def test_script_verifies_deploy_completeness_after_restart() -> None:
    """O deploy deve falhar se algum agent ativo ficar com código pré-sync."""
    content = _load_script()
    assert "verify_agents_running_current_code" in content
    assert "code_reference_epoch" in content
    # A verificação usa o mtime do runtime como marco e aborta em código antigo.
    assert "ActiveEnterTimestamp" in content
    assert "Deploy INCOMPLETO" in content
    assert "exit 1" in content
    # E é efetivamente invocada no fluxo do deploy (não só definida).
    invocations = content.count("verify_agents_running_current_code")
    assert invocations >= 2, "função definida mas não chamada no fluxo"
    # Roda depois de reiniciar os agents.
    assert content.rindex("verify_agents_running_current_code") > content.index(
        'systemctl restart "${AGENT_SERVICES[@]}"'
    )
