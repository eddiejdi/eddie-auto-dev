"""Simple client for local Agent RCA API.

This client is safe for local development: it will perform no network
operations unless `AGENT_API_URL` is set and `ALLOW_AGENT_API=1` is present
in the environment. Use this to integrate agents; real consumption should
be enabled only after deploy to homelab.
"""
from typing import List, Dict, Optional
import os
import json
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

AGENT_API_URL = os.environ.get('AGENT_API_URL')  # e.g. http://127.0.0.1:8888
ALLOW = os.environ.get('ALLOW_AGENT_API', '0') == '1'


def _disabled_response():
    return []


def fetch_pending(limit: int = 10) -> List[Dict]:
    """Return list of pending RCAs from the agent API.

    Returns empty list when client is disabled.
    """
    if not AGENT_API_URL or not ALLOW:
        return _disabled_response()
    url = AGENT_API_URL.rstrip('/') + '/rcas'
    try:
        req = Request(url)
        with urlopen(req, timeout=5) as resp:
            data = resp.read()
            return json.loads(data)
    except (URLError, HTTPError, ValueError):
        return []


def get_rca(issue: str) -> Optional[Dict]:
    if not AGENT_API_URL or not ALLOW:
        return None
    url = AGENT_API_URL.rstrip('/') + f'/rca/{issue}'
    try:
        req = Request(url)
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except (URLError, HTTPError, ValueError):
        return None


def ack_rca(issue: str) -> bool:
    if not AGENT_API_URL or not ALLOW:
        return False
    url = AGENT_API_URL.rstrip('/') + f'/rca/{issue}/ack'
    try:
        req = Request(url, method='POST')
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (URLError, HTTPError):
        return False
