# Agent Responder (test helper)

Overview
- A lightweight `agent_responder` subscribes to coordinator broadcasts (MessageType.COORDINATOR) and emits `response` messages so tests and manual validation can verify message flows.
- The responder runs inside the API process by default (started at API startup).

Behavior
- When coordinator broadcasts a `please_respond` op (either as plain content or JSON `{ "op": "please_respond" }`), the responder:
  - checks active agents via the AgentManager
  - if agents are active, publishes a `response` message for each active agent (source set to agent name)
  - if no agents are active, publishes a helpful fallback `response` ("Nenhum agente ativo disponível...")

Debug & test endpoints
- POST `/communication/test` accepts `message` and optional `start_responder` boolean. Example:

  curl -X POST "http://127.0.0.1:8503/communication/test" -H "Content-Type: application/json" -d '{"message":"please_respond","start_responder":true}'

  If `start_responder` true the endpoint will attempt to start the in-process responder before publishing the message. When `wait_seconds` is provided (default 0.5s) the endpoint will wait briefly and return any `response` messages observed in the local process under the keys `local_responses_count` and `local_responses`.

- POST `/debug/responder/start` will start `agent_responder()` inside the running process (useful when the responder didn't auto-start).

- GET `/debug/communication/subscribers` returns the number of subscribers currently attached to the communication bus for debugging.

CI note: the integration workflow now performs a pre-check that calls POST `/communication/test` with `start_responder=true` and `wait_seconds=1.0`. The pre-check expects at least one `local_responses` entry from the same API process and will fail early with additional debug dumps (`/debug/communication/subscribers` and `/communication/messages`) if no local responses are observed. This helps catch cases where the running API process hasn't been updated or the responder isn't subscribed in that worker.

Manual verification
1. Activate an agent (e.g., Python):
   curl -X POST "http://127.0.0.1:8503/agents/python/activate"
2. Publish the broadcast (plain or JSON):
   curl -X POST "http://127.0.0.1:8503/communication/publish" -H "Content-Type: application/json" -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
3. Fetch recent messages and look for `type: response` entries:
   curl "http://127.0.0.1:8503/communication/messages?limit=50" | jq '.messages[] | select(.type=="response")'

Notes
- The integration CI job runs on the self-hosted homelab runner to ensure network reachability to the local API process.

Optional: automated restart on runners 🔁
- A small helper script is available at `scripts/restart_specialized_agents_api.sh` which takes one or more `user@host` arguments and executes `sudo systemctl restart specialized-agents-api` remotely.
- We also provide a workflow template `.github/workflows/restart-runner-on-update.yml` that will run after pushes to `feat/agent-responder-startup-tests` and attempt to restart the service on hosts declared in the `RUNNER_HOSTS` secret, using the `SSH_PRIVATE_KEY` secret.
- To enable the workflow, add the following repository secrets (Settings → Secrets):
  - `SSH_PRIVATE_KEY`: private SSH key with access to the runner hosts (the runner user must be able to run `sudo systemctl restart specialized-agents-api`).
  - `RUNNER_HOSTS`: space-separated `user@host` entries, e.g. `homelab@${HOMELAB_HOST} eddie@192.168.15.3`.
  - `ENABLE_AUTO_RESTART`: must be set to the literal string `true` to permit automatic restarts. This flag keeps the workflow safe-by-default; without it the workflow exits early and does nothing.

  Example (using `gh` CLI to set secrets):

  ```bash
  gh secret set RUNNER_HOSTS --body "homelab@${HOMELAB_HOST} eddie@192.168.15.3"
  gh secret set SSH_PRIVATE_KEY --body-file ~/.ssh/id_rsa
  gh secret set ENABLE_AUTO_RESTART --body "true"  # REQUIRED to enable automatic restarts
  ```

Security note: granting an automated workflow the ability to restart services requires careful trust and should be used only for trusted self-hosted runners. If you prefer manual control, follow the manual steps below.

Manual restart (operators)
1. SSH to the runner: `ssh homelab@${HOMELAB_HOST}`
2. Restart the API: `sudo systemctl restart specialized-agents-api`
3. Confirm: `sudo journalctl -u specialized-agents-api -n50 --no-pager` and `curl -sS http://127.0.0.1:8503/communication/messages?limit=10 | jq '.messages | length'`
