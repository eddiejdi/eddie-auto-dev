scripts/README
================

sync_openwebui_from_bw.sh
-------------------------

Purpose:
  Read `openwebui/api_key` from Bitwarden and set the repository secret
  `OPENWEBUI_API_KEY` in `eddiejdi/eddie-auto-dev` using `gh` CLI. Optionally
  trigger the workflow `write-openwebui-token.yml` which writes the token to
  the homelab runner (`~/.openwebui_token`).

Prerequisites:
  - `bw` (Bitwarden CLI) installed and logged in (`bw login` + `bw unlock`).
  - `gh` (GitHub CLI) installed and authenticated with access to the repo.

Usage examples:

  # Set secret from Bitwarden and do not run the write workflow
  ./scripts/sync_openwebui_from_bw.sh

  # Set secret and trigger the write to homelab workflow
  ./scripts/sync_openwebui_from_bw.sh --run-workflow

Security notes:
  - The script reads the secret directly from Bitwarden; ensure your local
    session is secure and use a machine you trust.
  - The token is transmitted to GitHub as a repository secret; repository
    admins will be able to use it in workflows but it will not be visible.

If you want, I can add a GitHub Actions workflow that runs this script in a
controlled runner, but that would require storing a Bitwarden session token
or a PAT with appropriate permissions — let me know if you prefer that
approach and I will implement it safely.
