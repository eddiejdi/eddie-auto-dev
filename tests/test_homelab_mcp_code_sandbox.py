"""Testes das ferramentas MCP code_write_file/code_read_file/code_list_files
(scripts/homelab_mcp_server.py) — sandbox de criação de código/integrações.

Foco: nenhuma escrita/leitura pode escapar do sandbox (path traversal),
extensões/tamanho são validados, e o roundtrip write->read->list funciona.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "scripts" / "homelab_mcp_server.py"


def _load_module():
    module_name = "homelab_mcp_server_code_sandbox_tests"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod(tmp_path, monkeypatch):
    m = _load_module()
    # Isola cada teste num sandbox descartável — nunca aponta pro repo real.
    monkeypatch.setattr(m, "CODE_SANDBOX_DIR", tmp_path / "sandbox")
    return m


def test_write_then_read_roundtrip(mod):
    result = json.loads(mod.code_write_file("hello.py", "print('oi')", "script de teste"))
    assert result["ok"] is True
    assert result["path"] == "hello.py"

    read = json.loads(mod.code_read_file("hello.py"))
    assert read["ok"] is True
    assert read["content"] == "print('oi')"


def test_write_creates_nested_dirs(mod):
    result = json.loads(mod.code_write_file("clima/client.py", "x = 1", ""))
    assert result["ok"] is True
    assert (mod.CODE_SANDBOX_DIR / "clima" / "client.py").is_file()


def test_list_files_reflects_writes(mod):
    mod.code_write_file("a.py", "1", "")
    mod.code_write_file("sub/b.py", "2", "")
    result = json.loads(mod.code_list_files())
    assert result["ok"] is True
    assert set(result["files"]) == {"a.py", "sub/b.py"}


def test_list_files_scoped_to_subdir(mod):
    mod.code_write_file("a.py", "1", "")
    mod.code_write_file("sub/b.py", "2", "")
    result = json.loads(mod.code_list_files("sub"))
    assert result["ok"] is True
    # Paths sempre relativos ao sandbox inteiro (não ao subdir pedido) —
    # consistente com o que code_read_file/code_write_file esperam receber.
    assert result["files"] == ["sub/b.py"]


@pytest.mark.parametrize(
    "malicious_path",
    [
        "../outside.py",
        "../../etc/passwd",
        "sub/../../outside.py",
        "/etc/passwd",
    ],
)
def test_write_blocks_path_traversal(mod, malicious_path):
    result = json.loads(mod.code_write_file(malicious_path, "x", ""))
    assert result["ok"] is False
    assert "sandbox" in result["error"].lower() or "vazio" in result["error"].lower()


def test_read_blocks_path_traversal(mod):
    result = json.loads(mod.code_read_file("../../etc/passwd"))
    assert result["ok"] is False


def test_write_rejects_disallowed_extension(mod):
    result = json.loads(mod.code_write_file("run.sh", "#!/bin/bash\nrm -rf /", ""))
    assert result["ok"] is False
    assert "extensão" in result["error"]


def test_write_rejects_oversized_content(mod):
    huge = "x" * (mod._CODE_MAX_BYTES + 1)
    result = json.loads(mod.code_write_file("big.py", huge, ""))
    assert result["ok"] is False
    assert "grande" in result["error"]


def test_read_missing_file_returns_error(mod):
    result = json.loads(mod.code_read_file("nao_existe.py"))
    assert result["ok"] is False


def test_list_files_empty_sandbox(mod):
    result = json.loads(mod.code_list_files())
    assert result["ok"] is True
    assert result["files"] == []


def test_write_empty_path_rejected(mod):
    result = json.loads(mod.code_write_file("", "x", ""))
    assert result["ok"] is False
