import os
import subprocess
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "monitoring" / "ollama_gpu_selfheal.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content))
    path.chmod(0o755)


def _run_check_gpu(tmp_path: Path, ps_payload: str) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls_file = tmp_path / "curl_calls.log"
    calls_file.touch()

    _write_executable(
        bin_dir / "curl",
        f"""#!/bin/bash
        set -euo pipefail
        printf '%s\\n' "$*" >> "{calls_file}"
        args="$*"
        if [[ "$args" == *"/api/tags"* ]]; then
            printf '%s' '{{"models":[]}}'
        elif [[ "$args" == *"/api/ps"* ]]; then
            cat <<'EOF'
{ps_payload}
EOF
        elif [[ "$args" == *"/api/embeddings"* ]]; then
            printf '%s' '{{"embedding":[0.1,0.2]}}'
        elif [[ "$args" == *"/api/generate"* ]]; then
            printf '%s' '{{"done":true}}'
        else
            echo "unexpected curl args: $args" >&2
            exit 1
        fi
        """,
    )
    _write_executable(
        bin_dir / "nvidia-smi",
        """#!/bin/bash
        printf '%s\\n' 0
        """,
    )
    _write_executable(bin_dir / "systemctl", "#!/bin/bash\nexit 0\n")
    _write_executable(bin_dir / "logger", "#!/bin/bash\nexit 0\n")

    state_dir = tmp_path / "state"
    state_dir.mkdir()

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        export STATE_DIR="{state_dir}"
        source "{SCRIPT_PATH}"
        now=$(date +%s)
        for gpu in gpu0 gpu1; do
            echo "$now" > "$STATE_DIR/${{gpu}}_last_ok"
            echo "0" > "$STATE_DIR/${{gpu}}_restarts"
            echo "0" > "$STATE_DIR/${{gpu}}_restart_ts"
        done
        check_gpu "gpu1" "http://127.0.0.1:11435" "ollama-gpu1"
        """
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    return result, calls_file.read_text()


def _run_cpu_only_check(
    tmp_path: Path,
    ps_payload: str,
    *,
    repeats: int = 1,
    gpu_available: bool = True,
    initial_restarts: int = 0,
    initial_count: int = 0,
    recovered_payload: str = "",
) -> tuple[subprocess.CompletedProcess[str], str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_calls = tmp_path / "systemctl_calls.log"
    systemctl_calls.touch()

    recovered_case = ""
    if recovered_payload:
        recovered_case = f"""
        if [[ -s "{systemctl_calls}" ]]; then
            cat <<'EOF'
{recovered_payload}
EOF
            exit 0
        fi
        """

    _write_executable(
        bin_dir / "curl",
        f"""#!/bin/bash
        set -euo pipefail
        args="$*"
        if [[ "$args" == *"/api/tags"* ]]; then
            printf '%s' '{{"models":[]}}'
        elif [[ "$args" == *"/api/ps"* ]]; then
            {recovered_case}
            cat <<'EOF'
{ps_payload}
EOF
        elif [[ "$args" == *"/api/generate"* ]]; then
            printf '%s' '{{"done":true}}'
        else
            exit 1
        fi
        """,
    )
    _write_executable(
        bin_dir / "nvidia-smi",
        "#!/bin/bash\nprintf '%s\\n' 0\n" if gpu_available else "#!/bin/bash\nexit 1\n",
    )
    _write_executable(
        bin_dir / "systemctl",
        f"""#!/bin/bash
        printf '%s\n' "$*" >> "{systemctl_calls}"
        exit 0
        """,
    )
    _write_executable(bin_dir / "logger", "#!/bin/bash\nexit 0\n")

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        export STATE_DIR="{state_dir}"
        export POST_RESTART_DELAY=0
        export CPU_ONLY_RECOVERY_TIMEOUT=0
        export CPU_ONLY_RECOVERY_POLL=0
        source "{SCRIPT_PATH}"
        now=$(date +%s)
        echo "$now" > "$STATE_DIR/gpu0_last_ok"
        echo "{initial_restarts}" > "$STATE_DIR/gpu0_restarts"
        echo "$now" > "$STATE_DIR/gpu0_restart_ts"
        echo "{initial_count}" > "$STATE_DIR/gpu0_cpu_only_consecutive"
        for _ in $(seq 1 {repeats}); do
            check_gpu "gpu0" "http://127.0.0.1:11434" "ollama"
        done
        """
    )
    result = subprocess.run(
        ["bash", "-c", command],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
    )
    return result, systemctl_calls.read_text()


def test_embedding_model_uses_embeddings_probe(tmp_path: Path) -> None:
    result, curl_calls = _run_check_gpu(
        tmp_path,
        '{"models":[{"name":"nomic-embed-text:latest","details":{"family":"nomic-bert","families":["nomic-bert"]}}]}',
    )

    assert result.returncode == 0, result.stderr
    parts = result.stdout.strip().split()
    assert parts[:2] == ["1", "1"]
    assert parts[-1] == "nomic-embed-text:latest"
    assert "/api/embeddings" in curl_calls
    assert "/api/generate" not in curl_calls


def test_generate_model_uses_generate_probe(tmp_path: Path) -> None:
    result, curl_calls = _run_check_gpu(
        tmp_path,
        '{"models":[{"name":"gemma3-fast:gpu1","details":{"family":"gemma3","families":["gemma3"]}}]}',
    )

    assert result.returncode == 0, result.stderr
    parts = result.stdout.strip().split()
    assert parts[:2] == ["1", "1"]
    assert parts[-1] == "gemma3-fast:gpu1"
    assert "/api/generate" in curl_calls
    assert "/api/embeddings" not in curl_calls


def test_large_cpu_only_model_restarts_after_three_cycles(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":0}]}',
        repeats=3,
    )

    assert result.returncode == 0, result.stderr
    assert systemctl_calls.splitlines() == ["restart ollama"]
    outputs = [line.split() for line in result.stdout.strip().splitlines()]
    assert [parts[4:6] for parts in outputs] == [["1", "1"], ["1", "2"], ["1", "0"]]


def test_cpu_only_restart_requires_vram_recovery(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":0}]}',
        repeats=3,
        recovered_payload='{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":5456359587}]}',
    )

    assert result.returncode == 0, result.stderr
    assert systemctl_calls.splitlines() == ["restart ollama"]
    assert result.stdout.strip().splitlines()[-1].split()[4:6] == ["0", "0"]


def test_healthy_vram_resets_cpu_only_counter(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":5456359587}]}',
        initial_count=2,
    )

    assert result.returncode == 0, result.stderr
    assert not systemctl_calls
    assert result.stdout.strip().split()[4:6] == ["0", "0"]


def test_light_cpu_model_does_not_restart(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"gemma3:1b","size":815319791,"size_vram":0}]}',
        repeats=3,
    )

    assert result.returncode == 0, result.stderr
    assert not systemctl_calls
    assert all(line.split()[4:6] == ["0", "0"] for line in result.stdout.strip().splitlines())


def test_missing_physical_gpu_blocks_cpu_only_restart(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":0}]}',
        repeats=3,
        gpu_available=False,
    )

    assert result.returncode == 0, result.stderr
    assert not systemctl_calls
    assert all(line.split()[4:6] == ["1", "0"] for line in result.stdout.strip().splitlines())


def test_restart_rate_limit_is_respected(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(
        tmp_path,
        '{"models":[{"name":"trading-analyst:latest","size":5456359587,"size_vram":0}]}',
        initial_restarts=3,
        initial_count=2,
    )

    assert result.returncode == 0, result.stderr
    assert not systemctl_calls
    assert result.stdout.strip().split()[4:6] == ["1", "0"]


def test_invalid_ps_payload_is_not_cpu_only(tmp_path: Path) -> None:
    result, systemctl_calls = _run_cpu_only_check(tmp_path, "not-json", repeats=3)

    assert result.returncode == 0, result.stderr
    assert not systemctl_calls
    assert all(line.split()[4:6] == ["0", "0"] for line in result.stdout.strip().splitlines())


def test_selfheal_script_bash_syntax_is_valid() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
