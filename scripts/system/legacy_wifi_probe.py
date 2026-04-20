#!/usr/bin/env python3
"""Diagnóstico seguro de rede Wi-Fi legada e roteador de transição."""

from __future__ import annotations

import argparse
import http.cookiejar
import re
import socket
import urllib.parse
import urllib.request
from typing import Iterable

DEFAULT_ROUTER = "192.168.15.1"
DEFAULT_AP = "192.168.15.103"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_TIMEOUT = 5


def build_http_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ]
    return opener


def parse_hidden_form_fields(html: str) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(
        r'<input[^>]*type=["\']hidden["\'][^>]*name=["\'](?P<name>[^"\']+)["\'][^>]*value=["\'](?P<value>[^"\']*)["\']',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        values[match.group("name")] = match.group("value")
    return values


def fetch_url(url: str, opener: urllib.request.OpenerDirector, data: bytes | None = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    request = urllib.request.Request(url, data=data)
    with opener.open(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def is_port_open(host: str, port: int, timeout: int = DEFAULT_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def get_title(html: str) -> str:
    match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def login_zte_router(base_url: str, username: str, password: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[bool, str, urllib.request.OpenerDirector]:
    opener = build_http_opener()
    login_url = urllib.parse.urljoin(base_url, "/")
    login_page = fetch_url(login_url, opener, timeout=timeout)
    fields = parse_hidden_form_fields(login_page)

    post_data = {**fields, "Username": username, "Password": password, "action": "login"}
    if "Frm_Logintoken" not in post_data:
        post_data["Frm_Logintoken"] = "0"

    payload = urllib.parse.urlencode(post_data).encode()
    body = fetch_url(login_url, opener, data=payload, timeout=timeout)

    success = bool(
        re.search(r"logout|logoff|top\.gch|mainFrame|start\.ghtml|template\.gch", body, re.IGNORECASE)
    )
    return success, body, opener


def probe_zte_router(router_host: str, username: str, password: str) -> list[str]:
    base_url = f"http://{router_host}"
    results: list[str] = []

    results.append(f"[router] host={router_host}")
    http_open = is_port_open(router_host, 80)
    results.append(f"[router] HTTP port 80 open: {'yes' if http_open else 'no'}")

    if not http_open:
        results.append("[router] Sem acesso HTTP, não é possível avançar com login.")
        return results

    try:
        success, body, opener = login_zte_router(base_url, username, password)
        results.append(f"[router] login admin result: {'success' if success else 'failure'}")
        results.append(f"[router] login page title: {get_title(body) or '<sem title>'}")

        for path in ["/start.ghtml", "/top.gch", "/template.gch"]:
            try:
                content = fetch_url(urllib.parse.urljoin(base_url, path), opener)
                title = get_title(content)
                results.append(f"[router] {path} reachable, title={title or '<sem title>'}, len={len(content)}")
            except Exception as exc:
                results.append(f"[router] {path} fetch error: {exc.__class__.__name__}: {exc}")
    except Exception as exc:
        results.append(f"[router] login error: {exc.__class__.__name__}: {exc}")

    return results


def probe_network_device(host: str) -> list[str]:
    results: list[str] = []
    results.append(f"[device] host={host}")
    results.append(f"[device] ping port 80 open: {'yes' if is_port_open(host, 80) else 'no'}")
    results.append(f"[device] ping port 23 open: {'yes' if is_port_open(host, 23) else 'no'}")

    if is_port_open(host, 80):
        try:
            opener = build_http_opener()
            body = fetch_url(f"http://{host}/", opener)
            title = get_title(body)
            results.append(f"[device] HTTP title: {title or '<sem title>'}")
            if "login" in body.lower():
                results.append("[device] HTTP login page detected")
        except Exception as exc:
            results.append(f"[device] HTTP fetch error: {exc.__class__.__name__}: {exc}")
    else:
        results.append("[device] HTTP not reachable")

    return results


def render_report(lines: Iterable[str]) -> str:
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legacy Wi-Fi and router probe utility")
    parser.add_argument("--router", default=DEFAULT_ROUTER, help="IP do roteador legado")
    parser.add_argument("--ap", default=DEFAULT_AP, help="IP do AP/Wi-Fi extender")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Roteador admin username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Roteador admin password")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout em segundos para conexões HTTP")
    args = parser.parse_args(argv)

    report_lines: list[str] = []
    report_lines.extend(probe_zte_router(args.router, args.username, args.password))
    report_lines.append("")
    report_lines.extend(probe_network_device(args.ap))

    print(render_report(report_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
