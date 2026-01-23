Project Vault conventions

- Prefer OAuth flows for integrations (GitHub, Google, Telegram where supported).
- When OAuth is not available, store API keys, passwords and tokens in the project vault.

How to store secrets:

- Preferred: Bitwarden / Vaultwarden using `bw` CLI. Example item names used in this repo:
  - `eddie/telegram_bot_token` (password)
  - `eddie/github_token` (password)
  - `eddie/waha_api_key` (password)
  - `eddie/deploy_password` (password)
  - `eddie/webui_admin_password` (password)

- Fallback: tools/simple_vault (GPG-encrypted files). Place files under `tools/simple_vault/secrets/` named like `eddie_telegram_bot_token.gpg`.

Usage in scripts and code:

- Code should prefer environment variables first, then call `tools.vault.secret_store.get_field("<item>", "password")`.
- Shell scripts can call the CLI helper: `python3 tools/vault/secret_store.py get eddie/deploy_password`.

Examples:

- Set the Telegram token in the vault:
  - `bw login` / `bw unlock` and then create item `eddie/telegram_bot_token` with the token stored as the password field.

- For OAuth-enabled integrations (GitHub, Google): create the OAuth app and store client secret in the vault, then perform the OAuth flow; store the resulting refresh token or credential file in `calendar_data/token.json` (for Google) or in the vault for server-side tokens.

Security notes:

- Do not commit secrets to git. Use the vault or environment variables only.
- Avoid printing secrets to logs; prefer confirmation messages that secrets are stored without echoing them.
