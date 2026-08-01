"""Invariantes de paridade dos drop-ins systemd entre repo e homelab.

Contexto: o deploy versionava `systemd/**/*.service.d/*.conf` mas nunca os
instalava, então repo e produção divergiam em silêncio — e nos dois sentidos.
Na captura de 2026-07-25 havia 25 drop-ins vivos fora do git e casos em que o
**host** estava à frente do repo. Ver docs/systemd/DROPIN_DEPLOY_PARITY.md.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy_btc_trading_profiles.sh"
CHECKER_PATH = REPO_ROOT / "scripts" / "check_systemd_dropin_drift.py"
EXPORT_SCRIPT = REPO_ROOT / "scripts" / "export_host_systemd_dropins.sh"
ALLOWLIST = REPO_ROOT / "deploy" / "systemd-dropins-sync.allowlist"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-btc-trading-profiles.yml"
DRIFT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "systemd-dropin-drift-check.yml"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_systemd_dropin_drift", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _script() -> str:
    return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _allowed() -> list[str]:
    return checker.read_allowlist(ALLOWLIST)


def _allowed_dirs() -> list[str]:
    return checker.observed_dirs(_allowed())


# --------------------------------------------------------------------------
# Manifesto
# --------------------------------------------------------------------------

def test_allowlist_is_the_single_source_of_truth() -> None:
    """Manter duas listas (allowlist do #248 + manifesto proprio) recria a dupla
    fonte de verdade que ja mordeu nos dashboards do Grafana."""
    assert ALLOWLIST.is_file()
    assert not (REPO_ROOT / "systemd" / "managed_dropins.conf").exists()
    for consumer in (DEPLOY_SCRIPT, CHECKER_PATH):
        assert "systemd-dropins-sync.allowlist" in consumer.read_text(encoding="utf-8")


def test_allowlist_covers_trading_and_ollama_dropins() -> None:
    dirs = _allowed_dirs()
    for expected in (
        "crypto-agent@.service.d",
        "crypto-agent@BTC_USDT_aggressive.service.d",
        "crypto-agent@BTC_USDT_conservative.service.d",
        "ollama.service.d",
        "ollama-gpu1.service.d",
        "ollama-gpu-coordinator.service.d",
    ):
        assert expected in dirs, f"{expected} fora da allowlist"


def test_every_allowlisted_file_exists_in_repo() -> None:
    for rel in _allowed():
        assert (REPO_ROOT / rel).is_file(), f"Allowlist aponta para arquivo inexistente: {rel}"


def test_allowlist_rejects_absolute_traversal_and_non_dropin_entries(tmp_path: Path) -> None:
    bad = tmp_path / "bad.allowlist"
    for content in ("/etc/systemd/system/x.conf\n", "../../etc/x.conf\n", "scripts/foo.sh\n"):
        bad.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError):
            checker.read_allowlist(bad)


# --------------------------------------------------------------------------
# Deploy script: instalação, tools e hooks
# --------------------------------------------------------------------------

def test_deploy_script_installs_dropins_and_verifies_parity() -> None:
    content = _script()
    assert "sync_systemd_dropins" in content
    assert "verify_systemd_dropin_parity" in content
    assert "check_systemd_dropin_drift.py" in content
    assert 'DROPIN_ALLOWLIST="${REPO_ROOT}/deploy/systemd-dropins-sync.allowlist"' in content
    # A instalação precisa preceder o daemon-reload e o restart dos agents.
    assert content.index("sync_systemd_dropins\n") < content.index("sudo systemctl daemon-reload")


def test_deploy_script_never_deletes_host_only_dropins() -> None:
    """O host tem drop-ins vivos fora do git; --delete apagaria produção."""
    content = _script()
    start = content.index("\nsync_systemd_dropins() {")
    end = content.index("\nrestart_dropin_changed_units() {")
    dropin_block = content[start:end]
    code = "\n".join(
        line for line in dropin_block.splitlines() if not line.strip().startswith("#")
    )
    assert "--delete" not in code
    assert "rsync" not in code
    assert "host_only" in code, "deploy precisa reportar o que existe só no host"


def test_deploy_script_skips_redacted_templates() -> None:
    content = _script()
    assert "dropin_is_redacted" in content
    assert "from_bitwarden" in content


def test_deploy_script_syncs_tools_referenced_by_managed_units() -> None:
    """Drop-in instalado que chama script ausente derruba o ExecStartPost."""
    content = _script()
    referenced: set[str] = set()
    unit_sources = list((REPO_ROOT / "systemd").glob("*.service"))
    for rel_dir in _allowed_dirs():
        unit_sources.extend((REPO_ROOT / "systemd" / rel_dir).glob("*.conf"))

    for path in unit_sources:
        referenced.update(
            re.findall(r"/apps/crypto-trader/tools/([A-Za-z0-9_.-]+\.py)",
                       path.read_text(encoding="utf-8"))
        )

    assert referenced, "nenhuma tool referenciada encontrada — regex quebrada?"
    for tool in sorted(referenced):
        assert (REPO_ROOT / "tools" / tool).is_file(), f"tools/{tool} não existe no repo"
        assert f'"{tool}"' in content, f"deploy não sincroniza tools/{tool}"


def test_deploy_script_restarts_only_affected_units_staggered() -> None:
    content = _script()
    assert "restart_dropin_changed_units" in content
    assert "DROPIN_CHANGED_UNITS" in content
    assert "DROPIN_RESTART_STAGGER_SEC" in content
    assert "dropin_unit_is_restarted_elsewhere" in content


# --------------------------------------------------------------------------
# Workflows
# --------------------------------------------------------------------------

def test_deploy_workflow_triggers_on_managed_dropin_changes() -> None:
    workflow = yaml.safe_load(DEPLOY_WORKFLOW.read_text(encoding="utf-8"))
    paths = workflow[True]["push"]["paths"] if True in workflow else workflow["on"]["push"]["paths"]

    assert "deploy/systemd-dropins-sync.allowlist" in paths
    for rel_dir in _allowed_dirs():
        assert f"systemd/{rel_dir}/**" in paths, f"gatilho não cobre systemd/{rel_dir}"
    assert "scripts/check_systemd_dropin_drift.py" in paths


def test_deploy_workflow_verifies_parity_after_deploy() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    assert "check_systemd_dropin_drift.py --strict" in text
    assert "tests/test_systemd_dropin_parity.py" in text


def test_drift_workflow_runs_on_homelab_runner_and_alerts() -> None:
    workflow = yaml.safe_load(DRIFT_WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert "schedule" in triggers
    runs_on = workflow["jobs"]["check-dropin-drift"]["runs-on"]
    assert "self-hosted" in runs_on and "homelab" in runs_on
    assert "sendMessage" in DRIFT_WORKFLOW.read_text(encoding="utf-8")


def test_export_helper_is_dry_run_by_default() -> None:
    text = EXPORT_SCRIPT.read_text(encoding="utf-8")
    assert "--apply" in text
    assert "APPLY=0" in text


# --------------------------------------------------------------------------
# Verificador de drift
# --------------------------------------------------------------------------

def _fixture(tmp_path: Path, repo_files: dict[str, str], host_files: dict[str, str]):
    repo_root = tmp_path / "repo"
    system_dir = tmp_path / "etc"
    rel_dir = "demo.service.d"

    (repo_root / "systemd" / rel_dir).mkdir(parents=True)
    (repo_root / "deploy").mkdir(parents=True, exist_ok=True)
    (repo_root / "deploy" / "systemd-dropins-sync.allowlist").write_text(
        "# comentário\n"
        + "".join(f"systemd/{rel_dir}/{name}\n" for name in repo_files),
        encoding="utf-8",
    )
    for name, text in repo_files.items():
        (repo_root / "systemd" / rel_dir / name).write_text(text, encoding="utf-8")

    (system_dir / rel_dir).mkdir(parents=True)
    for name, text in host_files.items():
        (system_dir / rel_dir / name).write_text(text, encoding="utf-8")

    return repo_root, system_dir


def test_checker_reports_ok_when_identical(tmp_path: Path) -> None:
    repo, host = _fixture(tmp_path, {"a.conf": "[Service]\nX=1\n"}, {"a.conf": "[Service]\nX=1\n"})
    report = checker.compare(repo, host)
    assert report["drift"] == 0
    assert report["summary"]["ok"] == 1


def test_checker_flags_missing_and_differing_files(tmp_path: Path) -> None:
    repo, host = _fixture(
        tmp_path,
        {"a.conf": "[Service]\nX=1\n", "b.conf": "[Service]\nY=2\n"},
        {"a.conf": "[Service]\nX=999\n"},
    )
    report = checker.compare(repo, host)
    statuses = {f["path"]: f["status"] for f in report["findings"]}
    assert statuses["demo.service.d/a.conf"] == checker.STATUS_DIFFERS
    assert statuses["demo.service.d/b.conf"] == checker.STATUS_MISSING
    assert report["drift"] == 2


def test_checker_reports_host_only_without_counting_as_drift(tmp_path: Path) -> None:
    repo, host = _fixture(
        tmp_path,
        {"a.conf": "[Service]\nX=1\n"},
        {"a.conf": "[Service]\nX=1\n", "zz-so-no-host.conf": "[Service]\nZ=3\n"},
    )
    report = checker.compare(repo, host)
    assert report["drift"] == 0
    assert report["host_only"] == 1
    host_only = [f for f in report["findings"] if f["status"] == checker.STATUS_HOST_ONLY]
    assert host_only[0]["path"] == "demo.service.d/zz-so-no-host.conf"


def test_checker_ignores_backup_files_on_host(tmp_path: Path) -> None:
    repo, host = _fixture(
        tmp_path,
        {"a.conf": "[Service]\nX=1\n"},
        {
            "a.conf": "[Service]\nX=1\n",
            "a.conf.bak.20260725_101010": "[Service]\nX=0\n",
            "old.conf.dpkg-old": "[Service]\nX=0\n",
        },
    )
    report = checker.compare(repo, host)
    assert report["host_only"] == 0


def test_checker_skips_redacted_templates(tmp_path: Path) -> None:
    repo, host = _fixture(
        tmp_path,
        {"common.conf": "[Service]\nEnvironment=SECRETS_AGENT_API_KEY=<from_bitwarden>\n"},
        {"common.conf": "[Service]\nEnvironment=SECRETS_AGENT_API_KEY=real-secret\n"},
    )
    report = checker.compare(repo, host)
    assert report["drift"] == 0
    assert report["summary"]["redacted"] == 1


def test_checker_exit_codes(tmp_path: Path, capsys) -> None:
    repo, host = _fixture(tmp_path, {"a.conf": "X=1\n"}, {"a.conf": "X=2\n"})
    assert checker.main(["--repo-root", str(repo), "--system-dir", str(host)]) == 0
    assert checker.main(["--repo-root", str(repo), "--system-dir", str(host), "--strict"]) == 1

    repo2, host2 = _fixture(tmp_path / "b", {"a.conf": "X=1\n"}, {"a.conf": "X=1\n", "extra.conf": "Y=1\n"})
    assert checker.main(["--repo-root", str(repo2), "--system-dir", str(host2), "--strict"]) == 0
    assert checker.main(
        ["--repo-root", str(repo2), "--system-dir", str(host2), "--fail-on-host-only"]
    ) == 1
    capsys.readouterr()


def test_sync_systemd_dropins_installs_repo_confs_into_fake_system_dir(tmp_path: Path) -> None:
    """Ponta a ponta: roda a função real do deploy contra um /etc falso e depois
    o verificador — o que o deploy instala tem que passar em --strict."""
    fake_etc = tmp_path / "etc-systemd-system"
    fake_etc.mkdir()
    # Drop-in vivo que só existe no host: precisa sobreviver ao sync.
    host_only_dir = fake_etc / "ollama.service.d"
    host_only_dir.mkdir()
    (host_only_dir / "zz-so-no-host.conf").write_text(
        "[Service]\nEnvironment=OLLAMA_NUM_PARALLEL=4\n", encoding="utf-8"
    )

    script = f"""
    set -euo pipefail
    sudo() {{ "$@"; }}
    export SYSTEMD_SYSTEM_DIR={fake_etc!s}
    source {DEPLOY_SCRIPT!s}
    sync_systemd_dropins
    printf 'CHANGED:%s\\n' "${{DROPIN_CHANGED_UNITS[@]:-}}"
    """
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert proc.returncode == 0, proc.stderr

    # Drop-in não-redigido chegou ao destino, idêntico.
    installed = fake_etc / "ollama-gpu1.service.d" / "zzzz-warmup-curl.conf"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8") == (
        REPO_ROOT / "systemd" / "ollama-gpu1.service.d" / "zzzz-warmup-curl.conf"
    ).read_text(encoding="utf-8")

    # Template com placeholder NÃO foi instalado.
    assert not (fake_etc / "crypto-agent@.service.d" / "common.conf").exists()

    # Drop-in exclusivo do host preservado e reportado.
    assert (host_only_dir / "zz-so-no-host.conf").is_file()
    assert "zz-so-no-host.conf" in proc.stdout

    # Units afetadas foram registradas para restart.
    assert "ollama-gpu1.service" in proc.stdout

    # E o verificador concorda: sem drift após o sync.
    report = checker.compare(REPO_ROOT, fake_etc)
    assert report["drift"] == 0, [f for f in report["findings"] if f["status"] != "ok"]
    assert report["host_only"] == 1


def test_sync_systemd_dropins_is_idempotent(tmp_path: Path) -> None:
    fake_etc = tmp_path / "etc"
    fake_etc.mkdir()
    script = f"""
    set -euo pipefail
    sudo() {{ "$@"; }}
    export SYSTEMD_SYSTEM_DIR={fake_etc!s}
    source {DEPLOY_SCRIPT!s}
    sync_systemd_dropins >/dev/null
    sync_systemd_dropins
    printf 'CHANGED_COUNT:%s\\n' "${{#DROPIN_CHANGED_UNITS[@]}}"
    """
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert proc.returncode == 0, proc.stderr
    assert "CHANGED_COUNT:0" in proc.stdout, "2ª execução não deveria marcar unit alterada"
    assert "já em paridade" in proc.stdout


def test_repo_real_allowlist_is_loadable_by_checker() -> None:
    """compare() precisa rodar contra a árvore real sem estourar."""
    report = checker.compare(REPO_ROOT, Path("/nonexistent-system-dir"))
    assert report["summary"]["missing"] == len(_allowed())
    # common.conf esta versionado mas fora da allowlist
    assert report["summary"]["not_synced"] >= 1


# --------------------------------------------------------------------------
# Regressão do bug de origem: modelo do drop-in x modelo realmente servido
# --------------------------------------------------------------------------

def test_managed_dropins_only_reference_models_declared_in_models_env() -> None:
    """Foi assim que `OLLAMA_PLAN_MODEL=gemma3-fast:gpu1` sobreviveu: o drop-in
    apontava para um modelo que não está na GPU1 desde 2026-07-10, e nada
    comparava o drop-in com deploy/crypto-agent/models.env."""
    models_env = (REPO_ROOT / "deploy" / "crypto-agent" / "models.env").read_text(encoding="utf-8")
    def _norm(model: str) -> str:
        """`trading-analyst` e `trading-analyst:latest` sao o mesmo modelo."""
        model = model.strip()
        return model[: -len(":latest")] if model.endswith(":latest") else model

    known = {
        _norm(line.split("=", 1)[1])
        for line in models_env.splitlines()
        if line.strip() and not line.startswith("#") and "=" in line
    }
    assert known, "models.env vazio"

    offenders = []
    for rel_dir in _allowed_dirs():
        for conf in sorted((REPO_ROOT / "systemd" / rel_dir).glob("*.conf")):
            for name, value in re.findall(
                r"^Environment=(OLLAMA_[A-Z_]*MODEL)=(.+)$",
                conf.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            ):
                if _norm(value) not in known:
                    offenders.append(f"{rel_dir}/{conf.name}: {name}={value.strip()}")

    assert not offenders, (
        "drop-in aponta para modelo ausente de deploy/crypto-agent/models.env "
        "(com MAX_LOADED_MODELS=1 isso devolve 503): " + "; ".join(offenders)
    )


# --------------------------------------------------------------------------
# Environment= morto: sombreado por EnvironmentFile=
# --------------------------------------------------------------------------

def test_dropin_environment_never_shadowed_by_models_env() -> None:
    """`EnvironmentFile=` VENCE `Environment=` no systemd, independente da ordem
    de merge dos drop-ins.

    Medido no homelab em 2026-07-25: `zz-direct-ollama.conf` (instância) traz
    `Environment=OLLAMA_PLAN_MODEL=lfm2.5-fast:gpu1` e é mesclado DEPOIS de
    `common.conf` (que tem `EnvironmentFile=/etc/crypto-agent/models.env`) —
    e mesmo assim `/proc/<pid>/environ` do agente mostra o valor do models.env.

    Consequência: qualquer `Environment=` de drop-in cujo nome também esteja no
    models.env é LINHA MORTA. Foi sobre duas dessas linhas que os PRs #246 e
    #247 discordaram — nenhuma delas jamais teve efeito.

    Cuidado ao diagnosticar: `systemctl show -p Environment` NÃO expande
    `EnvironmentFile=`, então ele mostra o valor do drop-in e dá a impressão
    errada de que o drop-in venceu. A fonte de verdade é `/proc/<pid>/environ`.
    """
    models_env = REPO_ROOT / "deploy" / "crypto-agent" / "models.env"
    shadowing = {
        line.split("=", 1)[0].strip()
        for line in models_env.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    assert shadowing, "models.env vazio — regex quebrada?"

    dead: list[str] = []
    for rel_dir in _allowed_dirs():
        if not rel_dir.startswith("crypto-agent@"):
            continue  # models.env é EnvironmentFile só dos crypto-agent
        for conf in sorted((REPO_ROOT / "systemd" / rel_dir).glob("*.conf")):
            for name in re.findall(
                r'^Environment="?([A-Z][A-Z0-9_]*)=',
                conf.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            ):
                if name in shadowing:
                    dead.append(f"{rel_dir}/{conf.name}: {name}")

    assert not dead, (
        "Environment= de drop-in sombreado por EnvironmentFile=/etc/crypto-agent/models.env "
        "— a linha não tem efeito nenhum em runtime. Mude o valor no models.env "
        "(vale para os 14 agentes) ou use um EnvironmentFile= por perfil, que é "
        "mesclado depois. Linhas mortas: " + "; ".join(dead)
    )


def test_ollama_fallback_host_never_matches_primary_host_in_dropins() -> None:
    """`*_FALLBACK_HOST` não pode apontar pro mesmo endereço do `*_HOST` primário.

    O coordenador (:11437) é pausado toda hora pelo job de fine-tune
    (whatsapp_toolcall_chunked_train.sh). Se o fallback também apontar pra
    ele, primário e fallback caem juntos e os crypto-agent@* ficam sem
    nenhum caminho pra IA durante a pausa — o "fallback" nunca ajuda.
    ollama-gpu1.service (:11435) não é parado por esse job; é o fallback
    correto (ver deploy_btc_trading_profiles.sh e zz-direct-ollama.conf).
    """
    offenders: list[str] = []
    for rel_dir in _allowed_dirs():
        if not rel_dir.startswith("crypto-agent@"):
            continue
        for conf in sorted((REPO_ROOT / "systemd" / rel_dir).glob("*.conf")):
            text = conf.read_text(encoding="utf-8")
            hosts: dict[str, str] = {}
            for name, value in re.findall(
                r'^Environment="?(OLLAMA_[A-Z_]*_HOST)="?([^"\s]+)"?\s*$',
                text,
                flags=re.MULTILINE,
            ):
                hosts[name] = value
            for name, value in hosts.items():
                if not name.endswith("_FALLBACK_HOST"):
                    continue
                primary_name = name.replace("_FALLBACK_HOST", "_HOST")
                primary_value = hosts.get(primary_name)
                if primary_value is not None and primary_value == value:
                    offenders.append(f"{rel_dir}/{conf.name}: {name}={value} == {primary_name}")

    assert not offenders, (
        "FALLBACK_HOST igual ao HOST primário — fallback inútil quando o "
        "primário cai. Offenders: " + "; ".join(offenders)
    )
