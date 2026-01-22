# Secrets handling

Guidelines for storing and using secrets in this repository:

- Never commit plaintext secrets. Use the repository `tools/simple_vault` to encrypt secrets.
- To add a new secret:
  1. Put the secret content in a temporary file (local only).
  2. Run `tools/simple_vault/encrypt_secret.sh <in> <out.gpg> tools/simple_vault/passphrase` to create a `.gpg` file.
  3. Add the `.gpg` file to `tools/simple_vault/secrets/` and update `tools/simple_vault/migrated_secrets.json` with the SHA256 checksum.

- The runtime code (e.g. `tools/vault/secret_store.py`) can decrypt `.gpg` using the passphrase file when needed.
- For production, prefer a real secrets manager (Vaultwarden/Bitwarden) and set `BW_SESSION` for `tools/vault/secret_store.py`.

Always rotate long-lived tokens and avoid storing production tokens in the repository when possible.
