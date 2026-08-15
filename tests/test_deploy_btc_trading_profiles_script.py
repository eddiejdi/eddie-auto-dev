"""Regression checks for the BTC trading deploy shell script."""

from __future__ import annotations

from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "deploy_btc_trading_profiles.sh"


def _load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_routes_ollama_fallback_host_through_coordinator() -> None:
    """FALLBACK_HOST tem que apontar pro MESMO coordenador do HOST primário.

    O coordenador (:11437) nunca deve ser derrubado (ver
    whatsapp_toolcall_chunked_train.sh) — ele decide sozinho qual GPU usar
    por modelo/saúde/carga e faz failover interno pra NAS/GPU1 quando o
    GPU0 cai (NAS tem trading-analyst desde 2026-08-01, mesmo Modelfile do
    GPU0). Um FALLBACK_HOST apontando direto numa GPU por fora do
    coordenador tira a serialização anti-503-storm do incidente 2026-07-24.
    """
    content = _load_script()
    assert "Environment=OLLAMA_TRADE_PARAMS_FALLBACK_HOST=http://192.168.15.2:11437" in content
    assert "Environment=OLLAMA_TRADE_WINDOW_FALLBACK_HOST=http://192.168.15.2:11437" in content
    assert "Environment=OLLAMA_TRADE_PARAMS_HOST=http://192.168.15.2:11437" in content
    assert "Environment=OLLAMA_TRADE_WINDOW_HOST=http://192.168.15.2:11437" in content
    assert 'ollama_host="${OLLAMA_PLAN_HOST:-http://192.168.15.2:11437}"' in content
    assert 'ollama_host="${OLLAMA_PLAN_HOST:-http://192.168.15.2:11434}"' not in content


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
        "crypto-exporter@DOGE_USDT_conservative.service",
        "crypto-exporter@DOGE_USDT_aggressive.service",
        "crypto-exporter@DOGE_USDT_shadow.service",
    ):
        assert unit in content


def test_script_staggers_agent_and_exporter_restarts() -> None:
    """Restart em massa sobrecarrega Secrets Agent; deploy deve escalonar."""
    content = _load_script()
    assert "AGENT_RESTART_STAGGER_SEC" in content
    assert "EXPORTER_RESTART_STAGGER_SEC" in content
    assert 'for svc in "${AGENT_SERVICES[@]}"; do' in content
    assert "restart_unit_respecting_disable" in content
    assert 'sudo systemctl restart "${svc}"' in content
    # Não deve mais reiniciar o array inteiro de uma vez
    assert 'sudo systemctl restart "${AGENT_SERVICES[@]}"' not in content
    assert 'sudo systemctl restart "${EXPORTER_SERVICES[@]}"' not in content


def test_script_skips_disabled_inactive_units() -> None:
    """Tombamento: deploy não pode dar start em conservative disabled+inactive.

    disabled+ativo (BTC aggressive) ainda recebe restart, sem enable.
    """
    content = _load_script()
    assert "unit_is_disabled_or_masked" in content
    assert "restart_unit_respecting_disable" in content
    assert "disabled/inactive — pulado" in content
    assert "disabled mas ativo — restart sem enable" in content
    assert content.count("restart_unit_respecting_disable") >= 3
    activate_sol = (SCRIPT_PATH.parent / "activate_sol_trading_profiles.sh").read_text(
        encoding="utf-8"
    )
    activate_doge = (SCRIPT_PATH.parent / "activate_doge_trading_profiles.sh").read_text(
        encoding="utf-8"
    )
    for body in (activate_sol, activate_doge):
        assert "start_or_skip_unit" in body
        assert "não religar" in body
        assert 'systemctl enable "crypto-agent@${inst}.service" "crypto-exporter@${inst}.service"' not in body


def test_workflow_verify_skips_disabled_sol_doge_units() -> None:
    """Verify do workflow não pode falhar porque conservative está disabled."""
    workflow = (
        SCRIPT_PATH.parent.parent
        / ".github"
        / "workflows"
        / "deploy-btc-trading-profiles.yml"
    ).read_text(encoding="utf-8")
    assert "verify pulado" in workflow
    assert '== "disabled"' in workflow
    assert "required_job" in workflow


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
        "crypto-agent@DOGE_USDT_conservative.service",
        "crypto-agent@DOGE_USDT_aggressive.service",
        "crypto-agent@DOGE_USDT_shadow.service",
        "crypto-agent@USDT_BRL_conservative.service",
        "crypto-agent@USDT_BRL_aggressive.service",
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
    # Roda depois de reiniciar os agents. O restart é escalonado (loop por svc,
    # não em massa — ver asserts acima), então o marcador é o restart do loop.
    assert content.rindex("verify_agents_running_current_code") > content.index(
        'sudo systemctl restart "${svc}"'
    )


def test_script_syncs_market_rag_runtime() -> None:
    """market_rag.py precisa ser sincronizado no deploy — o fix do índice
    per-symbol (contaminação de buy target entre símbolos) vive nesse módulo
    e sem o sync os agents continuariam com o index.pkl compartilhado."""
    content = _load_script()
    assert "btc_trading_agent/market_rag.py" in content
    assert '${TARGET_DIR}/market_rag.py' in content


def test_every_file_the_deploy_syncs_also_triggers_the_deploy() -> None:
    """Arquivo sincronizado mas fora dos `paths` = correção que nunca chega ao host.

    Foi assim que o `OLLAMA_PLAN_MODEL` dos drop-ins sobreviveu errado por três
    PRs (#246→#249), e de novo com `training_db.py` no #251: o merge entrou no
    main e nenhum deploy disparou.

    Este teste fecha a classe inteira, não um caso: extrai de
    deploy_btc_trading_profiles.sh todo `${REPO_ROOT}/<arquivo>` e exige que o
    gatilho do workflow o cubra.
    """
    import fnmatch
    import re

    import yaml

    workflow_path = (
        SCRIPT_PATH.parent.parent / ".github" / "workflows" / "deploy-btc-trading-profiles.yml"
    )
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    # `on:` vira True no YAML 1.1
    triggers = workflow[True] if True in workflow else workflow["on"]
    paths = triggers["push"]["paths"]

    synced = sorted(set(re.findall(
        r"\$\{REPO_ROOT\}/([A-Za-z0-9_./@-]+\.(?:py|txt|json|sudoers|service))",
        _load_script(),
    )))
    assert synced, "nenhum arquivo sincronizado encontrado — regex quebrada?"

    def covered(rel_path: str) -> bool:
        return any(fnmatch.fnmatch(rel_path, p.replace("**", "*")) for p in paths)

    missing = [f for f in synced if not covered(f)]
    assert not missing, (
        "o deploy sincroniza estes arquivos, mas mudá-los NÃO dispara o "
        "workflow — a correção ficaria só no repo: " + ", ".join(missing)
    )


def test_trigger_paths_do_not_reference_removed_files() -> None:
    """Path de gatilho apontando para arquivo inexistente é ruído que esconde
    a ausência do path certo (era o caso de systemd/trading-svc-ollama.sudoers,
    que o próprio deploy remove do host)."""
    import glob

    import yaml

    repo_root = SCRIPT_PATH.parent.parent
    workflow = yaml.safe_load(
        (repo_root / ".github" / "workflows" / "deploy-btc-trading-profiles.yml")
        .read_text(encoding="utf-8")
    )
    triggers = workflow[True] if True in workflow else workflow["on"]

    dangling = [
        p for p in triggers["push"]["paths"]
        if not glob.glob(str(repo_root / p), recursive=True)
    ]
    assert not dangling, (
        "paths do gatilho sem arquivo correspondente no repo: " + ", ".join(dangling)
    )
