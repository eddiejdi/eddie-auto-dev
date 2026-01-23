## Simple vault (recommendation)

This repository previously included a Vaultwarden (Bitwarden-compatible) deployment.
That proved heavy to automate in this environment. This `simple_vault` folder
provides a lightweight alternative based on standard tooling (GPG or SOPS).

Options:

- GPG symmetric encryption (very simple): use `gpg --symmetric` to encrypt
  a secrets file and place it under secure storage. Decrypt with `gpg --decrypt`.

- Mozilla SOPS (recommended for Git-friendly encrypted secrets): SOPS supports
  multiple key backends (GPG, age, KMS). It's scriptable and integrates with CI.

Quick examples (GPG):

1) Encrypt a plaintext secret:

```bash
gpg --symmetric --cipher-algo AES256 -o secrets/openwebui_api.key.gpg --passphrase-file /path/to/passphrase.txt secrets/openwebui_api.key
```

2) Decrypt:

```bash
gpg --quiet --batch --yes --passphrase-file /path/to/passphrase.txt -o /tmp/openwebui_api.key -d secrets/openwebui_api.key.gpg
```

SOPS example:

```bash
# create a new sops file
sops --encrypt --age <AGE-PUB-KEY> secrets/openwebui_api.sops.yaml > secrets/openwebui_api.sops.yaml

# decrypt for use
sops -d secrets/openwebui_api.sops.yaml > /tmp/openwebui_api.key
```

Why use this:

- No container/service to manage.
- Works well for CI, scripts and automation.
- Easier to audit and integrate into existing backup workflows.

If you want, I can add a small wrapper that reads `tools/vault/secret_map.json`
and writes encrypted files with `gpg`/`sops` for the items listed there.

--

Quick: how to use secrets with systemd (examples)

1) Decrypt into an EnvironmentFile for a unit (recommended):

```bash
# as root (or with sudo)
bash tools/simple_vault/export_env.sh > /etc/default/eddie-calendar
systemctl daemon-reload
systemctl restart eddie-calendar.service
```

2) Directly from a script using the vault helper (Python):

```py
from tools.secrets_loader import get_telegram_token
token = get_telegram_token()
```

3) How to add a new secret (plaintext -> encrypted):

```bash
# create plaintext file under tools/simple_vault/secrets/new_secret.txt
# then encrypt with repo passphrase file
gpg --symmetric --cipher-algo AES256 --batch --yes \
  --passphrase-file tools/simple_vault/passphrase \
  -o tools/simple_vault/secrets/new_secret.gpg \
  tools/simple_vault/secrets/new_secret.txt
# remove plaintext
rm -f tools/simple_vault/secrets/new_secret.txt
```

Security notes:
- Keep `tools/simple_vault/passphrase` readable only by trusted users (chmod 600).
- Consider migrating to SOPS or an external secret manager for production.
