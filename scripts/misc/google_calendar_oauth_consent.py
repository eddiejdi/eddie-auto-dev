#!/usr/bin/env python3
"""Consentimento OAuth do Google Calendar — headless, Authentik-first.

Substitui o setup_google_calendar.py antigo (que só entendia credentials.json
em disco e apontava pro diretório errado). Este wrapper usa o mesmo caminho
do serviço: client OAuth vem do Authentik via Secrets Agent
(google/oauth_client_installed#client_id/#client_secret), com credentials.json
como fallback de compatibilidade.

O consentimento em si é inerentemente do dono (abrir a URL, autorizar a conta
Google). Como o homelab é headless, o fluxo usa um servidor local de redirect
e o dono acessa via túnel SSH:

  # no SEU desktop (não no homelab):
  ssh -L 8765:localhost:8765 homelab

  # dentro dessa sessão ssh:
  cd /home/homelab/myClaude && python3 scripts/misc/google_calendar_oauth_consent.py

  # abra no navegador DO SEU DESKTOP a URL que o script imprimir;
  # autorize a conta edenilson.adm@gmail.com; o redirect volta pelo túnel
  # e o token fica salvo em scripts/misc/calendar_data/token.pickle.

Depois do token salvo, religar o serviço:
  sudo systemctl reset-failed eddie-calendar.service
  sudo systemctl start eddie-calendar.service
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))            # google_calendar_integration
sys.path.insert(0, str(HERE.parent.parent))  # tools.secrets_loader

REDIRECT_PORT = 8765


def main() -> int:
    from google_calendar_integration import (  # noqa: E402
        GoogleCalendarClient, CREDENTIALS_FILE, TOKEN_FILE, SCOPES,
        GOOGLE_OAUTH_SECRET,
    )
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

    integ = GoogleCalendarClient()
    if integ.is_authenticated():
        print("✅ Já autenticado — token válido em", TOKEN_FILE)
        return 0

    client_config = integ._client_config_from_vault()
    if client_config is not None:
        print(f"🔐 Client OAuth obtido do Authentik ({GOOGLE_OAUTH_SECRET})")
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    elif CREDENTIALS_FILE.exists():
        print(f"⚠️  Cofre vazio — usando fallback {CREDENTIALS_FILE}")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    else:
        print(
            f"❌ Secret '{GOOGLE_OAUTH_SECRET}' vazio no Authentik e sem "
            "credentials.json local.\n   Popule com: "
            "scripts/import_bw_secret_to_authentik.sh --search google"
        )
        return 1

    print(f"\n🌐 Aguardando consentimento na porta {REDIRECT_PORT}…")
    print("   (rode `ssh -L 8765:localhost:8765 homelab` no seu desktop e abra")
    print("    a URL abaixo no navegador do desktop)\n")
    creds = flow.run_local_server(
        host="localhost", port=REDIRECT_PORT,
        open_browser=False,
        authorization_prompt_message="👉 Abra esta URL no navegador:\n{url}\n",
        success_message="Autorizado! Pode fechar esta aba e voltar ao terminal.",
    )

    TOKEN_FILE.parent.mkdir(exist_ok=True)
    with open(TOKEN_FILE, "wb") as fh:
        pickle.dump(creds, fh)
    print(f"\n✅ Token salvo em {TOKEN_FILE}")
    print("   Agora: sudo systemctl reset-failed eddie-calendar.service && "
          "sudo systemctl start eddie-calendar.service")
    return 0


if __name__ == "__main__":
    sys.exit(main())
