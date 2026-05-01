from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / "tools"
    / "authentik_management"
    / "register_nextcloud_access_panel.py"
)
SPEC = importlib.util.spec_from_file_location("register_nextcloud_access_panel", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_default_panel_url_points_to_auth_domain() -> None:
    """Default de publicacao deve usar auth.rpa4all.com."""
    assert module.PANEL_URL == "https://auth.rpa4all.com/nextcloud-access/"


def test_app_payload_uses_auth_domain_launch_url() -> None:
    """Payload da aplicacao deve publicar a launch URL em auth.rpa4all.com."""
    payload = module.app_payload()

    assert payload["slug"] == "nextcloud-access-panel"
    assert payload["meta_launch_url"] == "https://auth.rpa4all.com/nextcloud-access/"
