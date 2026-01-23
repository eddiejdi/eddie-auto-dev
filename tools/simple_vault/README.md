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
