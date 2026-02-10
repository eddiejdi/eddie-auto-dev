# Agent Google Drive (gdrive)

Este documento descreve como configurar um agent simples para acessar contas Google Drive.

Principais pontos:
- O agent espera tokens OAuth gerados por um cliente "Desktop" (Installed App).
- Para cada conta (ex.: edenilson.adm@gmail.com) você terá um arquivo de token em `specialized_agents/gdrive_tokens/`.

Passos resumidos:

1) Criar credenciais OAuth (Desktop) no Google Cloud Console
   - Console: https://console.cloud.google.com/apis/credentials
   - Crie um OAuth 2.0 Client ID do tipo "Desktop"
   - Baixe o `client_secret.json` (ex.: `client_secret.json`)

2) Instalar dependências (virtualenv recomendado)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install google-api-python-client google-auth google-auth-oauthlib
3) Gerar tokens para as contas desejadas

```bash
python3 tools/gdrive_auth.py --client-secrets ~/Downloads/client_secret.json \
  --accounts "edenilson.adm@gmail.com,edenilson.teixeira@rpa4all.com" \
  --tokens-dir specialized_agents/gdrive_tokens
Quando o navegador abrir, faça login com a conta indicada (uma por vez). Os tokens serão salvos em `specialized_agents/gdrive_tokens/` como `edenilson.adm_at_gmail.com.json` e `edenilson.teixeira_at_rpa4all.com.json`.

4) Usar o agent no código

Exemplo rápido (python):

```py
from specialized_agents.gdrive_agent import GDriveAgent

g = GDriveAgent(tokens_dir='specialized_agents/gdrive_tokens')
files = g.list_files('edenilson.adm@gmail.com', page_size=10)
print(files)
5) Segurança
- Nunca comite os arquivos em `specialized_agents/gdrive_tokens/` ao git.
- Recomendado: exportar `GDRIVE_TOKENS_DIR` e apontar para um caminho seguro no homelab.

6) Deploy
- Systemd: use o unit template em `tools/systemd/gdrive-agent.service`.
  - Crie `/etc/default/gdrive_agent` com:
    - `GDRIVE_TOKENS_DIR=/var/lib/eddie/gdrive_tokens`
    - `GDRIVE_AGENT_API_KEY=<chave-secreta>`
  - Coloque os arquivos de token em `/var/lib/eddie/gdrive_tokens/` (um por conta).
  - Habilite e inicie:

```bash
sudo cp tools/systemd/gdrive-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gdrive-agent
- Docker: use `docker-compose.gdrive.yml` para rodar em container (montar tokens como volume):

```bash
GDRIVE_AGENT_API_KEY=replace-me docker compose -f docker-compose.gdrive.yml up -d
Em ambos os casos, garanta que os arquivos de token (`<email>.json`) estejam no diretório apontado por `GDRIVE_TOKENS_DIR`. Nunca comite esses arquivos.
