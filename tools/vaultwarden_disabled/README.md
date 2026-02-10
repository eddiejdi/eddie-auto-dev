# Vaultwarden (self-hosted Bitwarden-compatible server)

This folder contains a minimal docker-compose setup to run Vaultwarden (formerly bitwarden_rs), a lightweight self-hosted Bitwarden-compatible server.

Files:
- `docker-compose.yml` — service definition (exposes port 8080)
- `start_vaultwarden.sh` — convenience script to start the service

Quick start

1. Choose a strong admin token and export it (recommended):

```bash
export VAULTWARDEN_ADMIN_TOKEN="<strong-admin-token>"
2. Start the service:

```bash
bash tools/vaultwarden/start_vaultwarden.sh
3. Open the web UI: http://<host>:8080

Create user accounts using the web UI. To use the `bw` CLI against this server, set `BW_SERVER`:

```bash
export BW_SERVER="http://localhost:8080"
# then login with the user's email/password
bw login you@example.com
Importing the encrypted bundle created earlier

If you used the helper that created `/tmp/secrets_bundle.gpg` and `/tmp/secrets_bundle.pass` on the host, copy them to your local machine and decrypt:

```bash
scp user@host:/tmp/secrets_bundle.gpg .
scp user@host:/tmp/secrets_bundle.pass .
gpg --quiet --batch --yes --decrypt --passphrase-file ./secrets_bundle.pass -o secrets_bundle.tar.gz secrets_bundle.gpg
tar xzf secrets_bundle.tar.gz
# inspect secrets_found.txt and openwebui_api.key.gpg
Then add items to your Vaultwarden account via the web UI, or use `bw` to create items after logging in.

Security notes
- Change the `ADMIN_TOKEN` before exposing the service to untrusted networks.
- Protect `/data` volume backups; it contains the vault database.
