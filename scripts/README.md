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

Runbook / recovery steps (homelab runner) — quick reference
---------------------------------------------------------

- Ensure the homelab runner user has Bitwarden CLI and gh installed and is
  able to unlock Bitwarden:

    bw login <email>
    bw unlock

- To manually export a session and avoid interactive unlock during automation:

    bw unlock --raw > /tmp/bw_session
    export BW_SESSION=$(cat /tmp/bw_session)

- If `bw get password openwebui/api_key` fails, check that the item exists and
  that the runner has access to the organization or collection where the item
  is stored.

- Manual verification on homelab:

    # Ensure token file is present and permissions are correct
    ls -l ~/.openwebui_token

    # Test API access
    curl -sS -H "Authorization: Bearer $(cat ~/.openwebui_token)" http://127.0.0.1:3000/api/v1/models | jq .

- If you need to re-run the sync from Bitwarden locally:

    ./scripts/sync_openwebui_from_bw.sh --run-workflow

- If Bitwarden isn't logged in on the runner and interactive login is not possible,
  use a maintenance session on the homelab runner to unlock once and store
  the `BW_SESSION` in the session environment for subsequent dispatches.
