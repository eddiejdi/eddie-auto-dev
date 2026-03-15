from __future__ import annotations

import base64
import json

from specialized_agents.gmail_credentials import _decode_token_mapping


def test_decode_token_mapping_accepts_json():
    payload = {"access_token": "abc", "refresh_token": "def"}

    result = _decode_token_mapping(json.dumps(payload))

    assert result == payload


def test_decode_token_mapping_accepts_base64_encoded_json():
    payload = {"access_token": "abc", "refresh_token": "def"}
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    result = _decode_token_mapping(encoded)

    assert result == payload


def test_decode_token_mapping_accepts_double_encoded_json():
    payload = {"access_token": "abc", "refresh_token": "def"}
    encoded = json.dumps(json.dumps(payload))

    result = _decode_token_mapping(encoded)

    assert result == payload
