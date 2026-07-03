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


def test_selfheal_script_bash_syntax_is_valid() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
