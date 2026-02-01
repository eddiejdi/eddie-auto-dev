# SECRETS — Vault pattern

This repository uses a local encrypted vault for secrets: `tools/simple_vault/secrets/`.

Principles
- Never commit plaintext credentials to git.
- Keep encrypted secrets under `tools/simple_vault/secrets/` (this directory is git-ignored).
- Use the provided helper scripts to encrypt and decrypt secrets; keep the passphrase file safe (`tools/simple_vault/passphrase`).
- To add a new secret:
  1. Put the secret content in a temporary file (local only).
  2. Run `tools/simple_vault/encrypt_secret.sh <in> <out.gpg> tools/simple_vault/passphrase` to create a `.gpg` file.
  3. Add the `.gpg` file to `tools/simple_vault/secrets/` and update `tools/simple_vault/migrated_secrets.json` with the SHA256 checksum.

- The runtime code (e.g. `tools/vault/secret_store.py`) can decrypt `.gpg` using the passphrase file when needed.
- For production, prefer a real secrets manager (Vaultwarden/Bitwarden) and set `BW_SESSION` for `tools/vault/secret_store.py`.

Add and manage secrets (examples)

- Add a secret (reads from stdin and writes an encrypted `.gpg` file):

  printf '%s' '<secret-value>' | tools/simple_vault/add_secret.sh <secret_name>

  Example:
  printf '%s' '1105143633:AAG5BrfOs...' | tools/simple_vault/add_secret.sh telegram_bot_token

- Decrypt a secret and write to a secure file on the homelab:

  tools/simple_vault/decrypt_secret.sh tools/simple_vault/secrets/telegram_bot_token.gpg | sudo tee /etc/eddie/telegram.env >/dev/null
  sudo chown root:root /etc/eddie/telegram.env && sudo chmod 600 /etc/eddie/telegram.env

- Test a Telegram token (run as root to read env file):

  sudo bash -c 'source /etc/eddie/telegram.env && curl -sS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"'

Best practices
- Rotate tokens regularly and update the encrypted file with `add_secret.sh`.
- Keep a secure backup of `tools/simple_vault/passphrase` (required to decrypt secrets).
- Use a remote secret manager (Vault, S3+KMS, HashiCorp Vault) for production workloads; use `tools/simple_vault` as a local/offline backup.
- Do not push decrypted files or credentials into CI logs.

Repository notes
- `tools/simple_vault/secrets/` is intentionally ignored by git; keep an offsite encrypted backup if the secrets are important.
- There are helper scripts for migration and publication; review them (`tools/simple_vault/*`) before use.

SSH deploy keys (recommended)
- Store deploy/private SSH keys in Bitwarden as an SSH Key item or a Secure Note and prefer using the Bitwarden CLI/API for automated imports.
- After successfully storing a private key in Bitwarden, remove redundant copies from root or temporary locations on servers (e.g. `sudo rm -f /root/.ssh/deploy_id_ed25519`) to reduce exposure.
- For automation, use a non-interactive flow (API key or BW_SESSION) and ensure any session files like `/root/.bw_session` are protected with `chmod 600`.

If you want, I can add scripts to synchronize selected encrypted secrets to an S3 bucket or a Vault server and document the workflow (recommended for robust backup).
