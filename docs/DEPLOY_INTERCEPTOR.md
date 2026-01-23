# Deploy Interceptor Dashboard

This document describes the automated deploy flow for the Interceptor (Streamlit) dashboard and how to operate/troubleshoot it.

## Workflow overview
- GitHub Actions workflow: `.github/workflows/deploy_interceptor.yml` triggers on pushes to branch `deploy/interceptor-dashboard`.
- The workflow SSHes to the deploy host and attempts a safe deploy: fetch branch, checkout pushed branch, and restart the `eddie-conversation-monitor.service` systemd unit (or start Streamlit from the repository venv as fallback).

## Required secrets (GitHub repository)
- `DEPLOY_HOST` — host/IP (e.g., `192.168.15.2`).
- `DEPLOY_USER` — ssh user on the host (e.g., `homelab`).
- `DEPLOY_PATH` — full path to the repository on the host (e.g., `/home/homelab/eddie-auto-dev`).
- `DEPLOY_SSH_KEY` — private SSH key for the `DEPLOY_USER` (add as Actions secret).

Optional: the workflow runs as an unauthenticated SSH, but for advanced cases provide a `GITHUB_TOKEN` to the `github-agent` on the host for authenticated API access.

## Host requirements
- The repository must be cloned at `DEPLOY_PATH` and accessible by `DEPLOY_USER`.
- A systemd unit `eddie-conversation-monitor.service` (system-wide) is preferred; the workflow will restart it with `sudo systemctl restart eddie-conversation-monitor.service` when available.
- The deploy path should include a Python venv at `$DEPLOY_PATH/.venv` with `streamlit` installed as fallback.

## How the CI deploy works (safe steps)
1. Actions checks out the pushed branch.
2. SSH to host with `BatchMode` (non-interactive) and `StrictHostKeyChecking=no` disabled for automation.
3. Change to `DEPLOY_PATH`, fetch remote refs and reset to the pushed branch (`origin/${{ github.ref_name }}`).
4. Attempt to restart `eddie-conversation-monitor.service` via `sudo systemctl`.
5. If systemd unit not present, kill any previous Streamlit process and start a new one from the repo venv.

## Troubleshooting
- If the Actions job fails at "Set up job": inspect the workflow run HTML via Actions UI. This failure indicates runner setup issues — retrying the run or checking repository permissions often helps.
- To retrieve full logs programmatically: use a GitHub token with `actions:read` scope and call the Actions API or use the local `github-agent` web UI at `http://HOST:5000` to authenticate and fetch logs.
- If port 8501 is in use on the host: `sudo ss -ltnp | grep 8501` then `sudo kill <pid>` of conflicting process, or prefer systemd-managed restarts.

## Rollback
- The workflow performs a `git reset --hard origin/<branch>` on the repo. To rollback to a previous commit on the host, SSH and run:

```bash
cd $DEPLOY_PATH
git reflog # find previous commit
git reset --hard <commit>
sudo systemctl restart eddie-conversation-monitor.service
```

## Security notes
- Keep `DEPLOY_SSH_KEY` restricted and rotate periodically.
- Avoid embedding tokens in the workflow; use repository secrets.

## Next steps / Improvements
- Use `github-agent` (running on the host) with an injected `GITHUB_TOKEN` to allow authenticated log retrieval, reruns, and safer remote file edits without SSH keys.
- Add healthcheck endpoints to the Streamlit app and check them from the workflow before reporting success.

---
Generated: 2026-01-21
