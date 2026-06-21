#!/usr/bin/env python3
"""Register known Tuya Local IR codes into Smart Life/Tuya cloud.

This script reads the codes already learned by Home Assistant `tuya_local`
and submits them to Tuya's official "Save Learning Code" endpoint.

It supports a dry-run mode that prints the payload even when OpenAPI
credentials are not available yet.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


DEFAULT_STORAGE = Path(
    "/home/homelab/homeassistant/config/.storage/"
    "tuya_local_remote_ebf9cf282b8d78ddd8t7ql_codes"
)
DEFAULT_INFRARED_ID = "ebf9cf282b8d78ddd8t7ql"
DEFAULT_DEVICE_NAME = "luz_cortina"
DEFAULT_REMOTE_NAME = "Cortina"
DEFAULT_ENDPOINT = "https://openapi.tuyaus.com"


def _normalize_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    if not parsed.netloc:
        raise ValueError(f"invalid endpoint: {endpoint}")
    return f"{parsed.scheme or 'https'}://{parsed.netloc}"


def _load_known_codes(storage_path: Path, device_name: str) -> dict[str, str]:
    data = json.loads(storage_path.read_text())
    codes = data.get("data", {}).get(device_name)
    if not isinstance(codes, dict) or not codes:
        raise ValueError(
            f"no learned codes found for {device_name!r} in {storage_path}"
        )
    filtered = {k: v for k, v in codes.items() if isinstance(v, str) and v}
    if not filtered:
        raise ValueError(f"no usable string codes found for {device_name!r}")
    return filtered


def _build_payload(
    *,
    remote_name: str,
    codes: dict[str, str],
    category_id: str | None,
    brand_name: str | None,
) -> dict[str, Any]:
    key_list = [{"key_name": key, "code": code} for key, code in sorted(codes.items())]
    payload: dict[str, Any] = {
        "remote_name": remote_name,
        "key_list": key_list,
    }
    if category_id:
        payload["category_id"] = category_id
    if brand_name:
        payload["brand_name"] = brand_name
    return payload


def _request(
    *,
    endpoint: str,
    access_id: str,
    access_secret: str,
    method: str,
    path: str,
    token: str | None,
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    body_json = json.dumps(body or {}, separators=(",", ":"), ensure_ascii=True)
    body_hash = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    now_ms = str(int(time.time() * 1000))
    parsed = urlparse(endpoint)
    sign_path = path if path.startswith("/") else f"/{path}"
    payload = f"{method}\n{body_hash}\n\n{sign_path}"
    if token:
        sign_base = access_id + token + now_ms + payload
    else:
        sign_base = access_id + now_ms + payload
    sign = hmac.new(
        access_secret.encode("utf-8"),
        msg=sign_base.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest().upper()
    headers = {
        "client_id": access_id,
        "sign": sign,
        "t": now_ms,
        "sign_method": "HMAC-SHA256",
        "mode": "cors",
        "Content-Type": "application/json",
    }
    if token:
        headers["access_token"] = token
    response = requests.request(
        method,
        f"{parsed.scheme}://{parsed.netloc}{sign_path}",
        headers=headers,
        data=body_json if body is not None else None,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _get_token(endpoint: str, access_id: str, access_secret: str) -> str:
    response = _request(
        endpoint=endpoint,
        access_id=access_id,
        access_secret=access_secret,
        method="GET",
        path="/v1.0/token?grant_type=1",
        token=None,
        body=None,
    )
    if not response.get("success"):
        raise RuntimeError(f"token request failed: {response}")
    token = response.get("result", {}).get("access_token")
    if not token:
        raise RuntimeError(f"missing access_token in response: {response}")
    return token


def _save_learning_codes(
    *,
    endpoint: str,
    access_id: str,
    access_secret: str,
    infrared_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = _get_token(endpoint, access_id, access_secret)
    response = _request(
        endpoint=endpoint,
        access_id=access_id,
        access_secret=access_secret,
        method="POST",
        path=f"/v2.0/infrareds/{infrared_id}/learning-codes",
        token=token,
        body=payload,
    )
    return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-path", type=Path, default=DEFAULT_STORAGE)
    parser.add_argument("--infrared-id", default=DEFAULT_INFRARED_ID)
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--remote-name", default=DEFAULT_REMOTE_NAME)
    parser.add_argument("--brand-name")
    parser.add_argument("--category-id")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--access-id")
    parser.add_argument("--access-secret")
    parser.add_argument("--payload-out", type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="send the payload to Tuya cloud instead of dry-run output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = _normalize_endpoint(args.endpoint)
    codes = _load_known_codes(args.storage_path, args.device_name)
    payload = _build_payload(
        remote_name=args.remote_name,
        codes=codes,
        category_id=args.category_id,
        brand_name=args.brand_name,
    )

    if args.payload_out:
        args.payload_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )

    if not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(
            "\nDry-run only. Use --apply with --access-id and --access-secret "
            "from a Tuya OpenAPI project that has infrared cloud permissions.",
            file=sys.stderr,
        )
        return 0

    if not args.access_id or not args.access_secret:
        raise SystemExit("--apply requires --access-id and --access-secret")

    response = _save_learning_codes(
        endpoint=endpoint,
        access_id=args.access_id,
        access_secret=args.access_secret,
        infrared_id=args.infrared_id,
        payload=payload,
    )
    print(json.dumps(response, ensure_ascii=False, indent=2))
    if not response.get("success"):
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
