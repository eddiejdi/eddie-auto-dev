"""NetBox extra settings for CMDB publication behind auth.rpa4all.com."""

from __future__ import annotations

import os


_base_path = os.getenv("NETBOX_BASE_PATH", "").strip().strip("/")
if _base_path:
    BASE_PATH = f"{_base_path}/"
