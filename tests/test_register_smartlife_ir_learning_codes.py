import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "homelab"
    / "register_smartlife_ir_learning_codes.py"
)
SPEC = importlib.util.spec_from_file_location(
    "register_smartlife_ir_learning_codes",
    MODULE_PATH,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _write_storage(path: Path, codes: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"data": {MODULE.DEFAULT_DEVICE_NAME: codes}}),
        encoding="utf-8",
    )


def test_normalize_endpoint_accepts_bare_host() -> None:
    assert MODULE._normalize_endpoint("openapi.tuyaus.com") == "https://openapi.tuyaus.com"


def test_load_known_codes_filters_empty_and_non_string_values(tmp_path: Path) -> None:
    storage_path = tmp_path / "codes.json"
    _write_storage(
        storage_path,
        {
            "off": "abc123",
            "empty": "",
            "numeric": 7,
        },
    )

    assert MODULE._load_known_codes(storage_path, MODULE.DEFAULT_DEVICE_NAME) == {
        "off": "abc123"
    }


def test_build_payload_sorts_keys_and_keeps_optional_fields() -> None:
    payload = MODULE._build_payload(
        remote_name="Cortina",
        codes={"z": "zzz", "a": "aaa"},
        category_id="123",
        brand_name="NovaDigital",
    )

    assert payload["remote_name"] == "Cortina"
    assert payload["category_id"] == "123"
    assert payload["brand_name"] == "NovaDigital"
    assert payload["key_list"] == [
        {"key_name": "a", "code": "aaa"},
        {"key_name": "z", "code": "zzz"},
    ]


def test_main_dry_run_writes_payload_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    storage_path = tmp_path / "codes.json"
    payload_path = tmp_path / "payload.json"
    _write_storage(
        storage_path,
        {
            "g": "green",
            "b": "blue",
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_smartlife_ir_learning_codes.py",
            "--storage-path",
            str(storage_path),
            "--payload-out",
            str(payload_path),
        ],
    )

    assert MODULE.main() == 0

    stdout = json.loads(capsys.readouterr().out)
    assert stdout["remote_name"] == MODULE.DEFAULT_REMOTE_NAME
    assert stdout["key_list"] == [
        {"key_name": "b", "code": "blue"},
        {"key_name": "g", "code": "green"},
    ]

    saved_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert saved_payload == stdout
