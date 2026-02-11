# Tunnels helpers

Scripts in this folder help deploy and fix Cloudflare named tunnels for the homelab.

Files
- `deploy_named_tunnel_via_ssh.sh` - copy cloudflared credential file and `config.yml` to a remote host and enable `cloudflared-named@.service`.
  - Supports `--creds`/`--config` with local files, or `--creds-secret`/`--config-secret` to fetch from the agent secret store (`tools/vault/secret_store.py`).
  - Validates the credential file is JSON and the config is plausibly YAML (attempts to use PyYAML if available). Use `--no-validate` to skip validation.

- `cloudflared-named@.service` - systemd unit template to run a named Cloudflare tunnel. Expects config at `/etc/cloudflared/config.yml` and credentials in `/etc/cloudflared`.

- `fix_cloudflared_tunnel.sh` - convenience wrapper that calls `deploy_named_tunnel_via_ssh.sh` then ensures `cloudflared` binary is installed on the remote, creates `/var/lib/cloudflared`, reloads systemd and restarts the named service.

Examples

Deploy using repo-local secrets (GPG files):

```bash
./tools/tunnels/deploy_named_tunnel_via_ssh.sh \
  --host 192.0.2.10 --user homelab --tunnel eddie-homelab \
  --creds-secret cloudflare_api --config-secret public_tunnel_url
```

Direct deploy with local files:

```bash
./tools/tunnels/deploy_named_tunnel_via_ssh.sh \
  --host myhost --user homelab --tunnel eddie-homelab \
  --creds ./my-tunnel-credentials.json --config ./config.yml
```

Quick fix (deploy + remote service repair):

```bash
./tools/tunnels/fix_cloudflared_tunnel.sh \
  --host myhost --user homelab --tunnel eddie-homelab \
  --creds-secret cloudflare_api --config-secret public_tunnel_url
```

Notes
- The repository stores many secrets encrypted under `tools/simple_vault/secrets/`. `tools/vault/secret_store.py` reads Bitwarden, environment vars and falls back to these GPG files.
- Ensure `SIMPLE_VAULT_PASSPHRASE_FILE` is set or a default passphrase file exists when relying on local GPG secrets.
