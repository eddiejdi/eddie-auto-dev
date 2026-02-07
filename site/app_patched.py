#!/usr/bin/env python3
"""
RPA4ALL Code Runner – Patched app.py
─────────────────────────────────────
Identical to the original Code Runner app.py but with
PYTHONPATH=/project so that `specialized_agents` and other
project modules are importable from user scripts.

This file is bind-mounted into per-session containers at /app/app.py.
"""

import os
import subprocess
import tempfile
import uuid
import time
import resource
from typing import Optional
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Same CORS config as production Code Runner to allow IDE access via Cloudflare Tunnel
CORS(app, origins=[
    "https://rpa4all.com",
    "https://www.rpa4all.com",
    "https://ide.rpa4all.com",
    "https://openwebui.rpa4all.com",
    "http://localhost:*"
])

# Configurações de segurança
MAX_EXECUTION_TIME = int(os.getenv("MAX_EXECUTION_TIME", "30"))
MAX_OUTPUT_SIZE = int(os.getenv("MAX_OUTPUT_SIZE", "65536"))  # 64KB
MAX_MEMORY_MB = int(os.getenv("MAX_MEMORY_MB", "256"))

AVAILABLE_PACKAGES = [
    "numpy", "pandas", "matplotlib", "requests", "httpx",
    "pydantic", "datetime", "json", "re", "math", "random",
    "collections", "itertools", "functools", "os", "sys"
]


def set_limits():
    """Define limites de recursos para o processo filho"""
    soft, hard = MAX_MEMORY_MB * 1024 * 1024, MAX_MEMORY_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_EXECUTION_TIME, MAX_EXECUTION_TIME))


def execute_python(code: str, stdin: str = "") -> dict:
    """Executa código Python de forma segura"""
    exec_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        dir="/tmp/code"
    ) as f:
        f.write(code)
        temp_file = f.name

    try:
        result = subprocess.run(
            ["python3", "-u", temp_file],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=MAX_EXECUTION_TIME,
            preexec_fn=set_limits,
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
                "PYTHONPATH": "/project",
            },
            cwd="/tmp/code"
        )

        stdout = result.stdout[:MAX_OUTPUT_SIZE]
        stderr = result.stderr[:MAX_OUTPUT_SIZE]

        return {
            "stdout": stdout,
            "stderr": stderr,
            "code": result.returncode,
            "signal": None
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Erro: Tempo limite excedido ({MAX_EXECUTION_TIME}s)",
            "code": 124,
            "signal": "SIGKILL"
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Erro de execução: {str(e)}",
            "code": 1,
            "signal": None
        }
    finally:
        try:
            os.unlink(temp_file)
        except Exception:
            pass


@app.route("/api/v2/execute", methods=["POST"])
def api_execute():
    try:
        data = request.get_json() or {}

        files = data.get("files", [])
        if not files:
            return jsonify({
                "run": {"stdout": "", "stderr": "Nenhum código fornecido", "code": 1}
            }), 400

        code = files[0].get("content", "")
        stdin = data.get("stdin", "")
        language = data.get("language", "python")

        if language not in ["python", "python3", "py"]:
            return jsonify({
                "run": {"stdout": "", "stderr": f"Linguagem '{language}' não suportada", "code": 1}
            }), 400

        result = execute_python(code, stdin)

        return jsonify({
            "language": "python",
            "version": "3.11",
            "run": result
        })

    except Exception as e:
        return jsonify({
            "run": {"stdout": "", "stderr": str(e), "code": 1}
        }), 500


@app.route("/api/v2/runtimes", methods=["GET"])
def api_runtimes():
    return jsonify([{
        "language": "python",
        "version": "3.11",
        "aliases": ["py", "python3"],
        "runtime": "cpython"
    }])


@app.route("/api/v2/packages", methods=["GET"])
def api_packages():
    return jsonify({"language": "python", "packages": AVAILABLE_PACKAGES})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "rpa4all-code-runner",
        "version": "1.1.0",
        "max_execution_time": MAX_EXECUTION_TIME,
        "max_memory_mb": MAX_MEMORY_MB
    })


@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "RPA4ALL Code Runner",
        "version": "1.1.0",
        "docs": "/api/v2/runtimes",
        "execute": "POST /api/v2/execute"
    })


if __name__ == "__main__":
    os.makedirs("/tmp/code", exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=False)
