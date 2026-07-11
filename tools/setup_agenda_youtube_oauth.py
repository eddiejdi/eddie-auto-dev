#!/usr/bin/env python3
"""Autentica a conta Google/YouTube do canal Agenda Diária Importante.

Modos:
  --manual (padrão)  Servidor sem gráfico: imprime URL, você autoriza no celular/PC
                     e cola a URL de redirecionamento no terminal.
  --server           Servidor local na porta 8094 (requer túnel SSH + navegador).
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from daily_agenda_config import load_config, resolve_repo_path  # noqa: E402
from youtube_agenda_publisher import (  # noqa: E402
    YOUTUBE_SCOPES,
    get_authenticated_channel_info,
    verify_upload_channel,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OAuth YouTube para agenda diária.")
    parser.add_argument("--port", type=int, default=8094, help="Porta do modo --server")
    parser.add_argument(
        "--server",
        action="store_true",
        help="Fluxo com servidor local (precisa túnel SSH + navegador).",
    )
    parser.add_argument(
        "--paste-url",
        default="",
        help="URL completa de redirecionamento (http://localhost/?code=...).",
    )
    parser.add_argument(
        "--url-only",
        action="store_true",
        help="Só imprime a URL e salva o state (para colar depois com --paste-url).",
    )
    parser.add_argument(
        "--upload-only-scope",
        action="store_true",
        help="Solicita só youtube.upload (menos fricção na tela de consentimento).",
    )
    return parser.parse_args()


def _resolve_scopes(args: argparse.Namespace) -> tuple[str, ...]:
    if args.upload_only_scope:
        return ("https://www.googleapis.com/auth/youtube.upload",)
    return YOUTUBE_SCOPES


def _scopes_from_pending(pending: dict, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw = pending.get("scopes")
    if isinstance(raw, list) and raw:
        return tuple(str(s) for s in raw)
    auth_url = pending.get("auth_url", "")
    if auth_url:
        scope_param = parse_qs(urlparse(auth_url).query).get("scope", [""])[0]
        if scope_param:
            return tuple(scope_param.split())
    return fallback


def _pending_path(token_file: Path) -> Path:
    return token_file.parent / "oauth_pending.json"


def _redirect_uri_from_credentials(credentials_file: Path, *, port: int | None = None) -> str:
    data = json.loads(credentials_file.read_text(encoding="utf-8"))
    section = data.get("installed") or data.get("web") or {}
    uris = section.get("redirect_uris") or ["http://localhost"]
    base = uris[0].rstrip("/")
    if port is not None:
        return f"http://localhost:{port}"
    return base


def _save_pending(
    token_file: Path,
    state: str,
    auth_url: str,
    *,
    redirect_uri: str,
    scopes: tuple[str, ...],
) -> Path:
    path = _pending_path(token_file)
    path.write_text(
        json.dumps(
            {
                "state": state,
                "auth_url": auth_url,
                "redirect_uri": redirect_uri,
                "scopes": list(scopes),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _load_pending(token_file: Path) -> dict:
    path = _pending_path(token_file)
    if not path.exists():
        raise RuntimeError(
            f"State OAuth ausente em {path}. Rode primeiro: "
            "python3 tools/setup_agenda_youtube_oauth.py --url-only"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_redirect_response(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise ValueError("URL/código vazio.")
    if text.startswith("http://") or text.startswith("https://"):
        return text
    if "code=" in text:
        return "http://localhost/?" + text.lstrip("?")
    return f"http://localhost/?code={text}"


def _save_token(flow, token_file: Path) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with token_file.open("wb") as handle:
        pickle.dump(flow.credentials, handle)
    print(f"Token salvo em {token_file}")


def print_manual_instructions(auth_url: str) -> None:
    print("\n=== OAuth manual (servidor só texto) ===\n")
    print("1. Abra esta URL no CELULAR ou em outro PC com navegador:\n")
    print(auth_url)
    print(
        "\n2. Entre com a conta Google do canal @AgendaDiáriaImportante e autorize.\n"
        "3. O navegador vai redirecionar para localhost e pode mostrar ERRO — normal.\n"
        "4. Copie a URL COMPLETA da barra de endereços (ex.: http://localhost/?code=...&scope=...)\n"
        "5. No SSH, rode:\n"
        "   python3 tools/setup_agenda_youtube_oauth.py --paste-url 'URL_COPIADA'\n"
    )


def manual_flow(
    flow,
    token_file: Path,
    *,
    pasted: str = "",
    url_only: bool = False,
    redirect_uri: str = "http://localhost",
    scopes: tuple[str, ...] = YOUTUBE_SCOPES,
) -> None:
    if pasted:
        pending = _load_pending(token_file)
        flow.redirect_uri = pending.get("redirect_uri") or redirect_uri
        redirect_response = _normalize_redirect_response(pasted)
        if f"state={pending['state']}" not in redirect_response:
            raise RuntimeError(
                "State OAuth não confere. Gere uma nova URL com --url-only e autorize de novo."
            )
        flow.fetch_token(authorization_response=redirect_response)
        _save_token(flow, token_file)
        _pending_path(token_file).unlink(missing_ok=True)
        return

    flow.redirect_uri = redirect_uri
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    if "redirect_uri=" not in auth_url:
        raise RuntimeError(
            f"URL OAuth sem redirect_uri (esperado {redirect_uri}). "
            "Verifique credentials.json no Google Cloud Console."
        )
    pending = _save_pending(
        token_file,
        state,
        auth_url,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )
    print_manual_instructions(auth_url)
    print(f"State salvo em {pending}")
    if url_only:
        return

    redirect_response = input("Cole a URL de redirecionamento aqui: ").strip()
    redirect_response = _normalize_redirect_response(redirect_response)
    if f"state={state}" not in redirect_response:
        raise RuntimeError("State OAuth não confere com a URL gerada nesta sessão.")
    flow.fetch_token(authorization_response=redirect_response)
    _save_token(flow, token_file)
    _pending_path(token_file).unlink(missing_ok=True)


def server_flow(flow, token_file: Path, port: int, *, redirect_uri: str) -> None:
    flow.redirect_uri = redirect_uri
    print(f"OAuth escutando em {redirect_uri}")
    print("Em outro terminal no seu PC:")
    print(f"  ssh -L {port}:localhost:{port} homelab@192.168.15.2")
    print("Depois abra a URL que aparecer abaixo no navegador do seu PC.")
    creds = flow.run_local_server(port=port, open_browser=False)
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with token_file.open("wb") as handle:
        pickle.dump(creds, handle)
    print(f"Token salvo em {token_file}")


def main() -> int:
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    args = parse_args()
    cfg = load_config()
    yt = cfg["youtube"]
    credentials_file = resolve_repo_path(yt["credentials_file"])
    token_file = resolve_repo_path(yt["token_file"])

    if not credentials_file.exists():
        print(f"Faltando credentials.json em {credentials_file}", file=sys.stderr)
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Instale: pip install google-auth-oauthlib google-api-python-client",
            file=sys.stderr,
        )
        return 1

    scopes = _resolve_scopes(args)
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), scopes)
    redirect_uri = _redirect_uri_from_credentials(
        credentials_file,
        port=args.port if args.server else None,
    )
    try:
        if args.server:
            server_flow(flow, token_file, args.port, redirect_uri=redirect_uri)
        elif args.paste_url:
            pending = _load_pending(token_file)
            paste_scopes = _scopes_from_pending(pending, scopes)
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), paste_scopes)
            manual_flow(
                flow,
                token_file,
                pasted=args.paste_url,
                redirect_uri=redirect_uri,
                scopes=paste_scopes,
            )
        else:
            manual_flow(
                flow,
                token_file,
                url_only=not args.server,
                redirect_uri=redirect_uri,
                scopes=scopes,
            )
    except Exception as exc:
        print(f"Falha no OAuth: {exc}", file=sys.stderr)
        return 1

    if not token_file.exists() or args.url_only:
        return 0

    channel_id = (yt.get("channel_id") or "").strip()
    if args.upload_only_scope:
        print(
            "AVISO: --upload-only-scope impede validar o canal de destino. "
            "Use escopos completos em produção.",
            file=sys.stderr,
        )
        if channel_id:
            print(f"Canal esperado: {yt.get('channel_handle', channel_id)}")
            print(f"https://www.youtube.com/channel/{channel_id}")
        return 0

    try:
        info = verify_upload_channel(config=cfg)
    except Exception as exc:
        print(f"Token salvo, mas canal OAuth incorreto: {exc}", file=sys.stderr)
        print(
            "Apague o token e autorize de novo com a conta Google de "
            "@AgendaDiáriaImportante (não use sua conta pessoal).",
            file=sys.stderr,
        )
        return 1

    print(f"Canal validado: {info.get('title')} ({info.get('id')})")
    print(info.get("url", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())