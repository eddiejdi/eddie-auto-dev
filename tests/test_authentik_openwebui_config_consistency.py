import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_public_openwebui_urls_use_rpa4all_domain() -> None:
    openwebui_config = json.loads((ROOT / "site" / "openwebui-config.json").read_text(encoding="utf-8"))
    agents_config = json.loads((ROOT / "site" / "agents-config.json").read_text(encoding="utf-8"))

    expected = "https://openwebui.rpa4all.com/"
    assert openwebui_config["openwebui_url"] == expected
    assert agents_config["openwebui_url"] == expected


def test_openwebui_redirect_uri_matches_public_host() -> None:
    setup_text = (ROOT / "tools" / "setup_authentik_sso.py").read_text(encoding="utf-8")
    match = re.search(r'"redirect_uris": "([^"]+openwebui[^"]+)"', setup_text)

    assert match is not None
    assert match.group(1) == "https://openwebui.rpa4all.com/oauth/oidc/callback"


def test_openwebui_env_uses_validated_oauth_variable_names() -> None:
    env_text = (ROOT / "tools" / "authentik_management" / "configs" / "openwebui.env").read_text(
        encoding="utf-8"
    )

    assert "OPENID_PROVIDER_URL=https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration" in env_text
    assert "OAUTH_CLIENT_ID=authentik-openwebui" in env_text
    assert "ENABLE_OAUTH_SIGNUP=true" in env_text
    assert "WEBUI_AUTH_PROVIDER=oidc" not in env_text
    assert "OIDC_PROVIDER_URL=https://auth.rpa4all.com/application/o/openwebui/" not in env_text
