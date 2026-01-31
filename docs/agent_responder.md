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

  If `start_responder` true the endpoint will attempt to start the in-process responder before publishing the message.

- POST `/debug/responder/start` will start `agent_responder()` inside the running process (useful when the responder didn't auto-start).

- GET `/debug/communication/subscribers` returns the number of subscribers currently attached to the communication bus for debugging.

Manual verification
1. Activate an agent (e.g., Python):
   curl -X POST "http://127.0.0.1:8503/agents/python/activate"
2. Publish the broadcast (plain or JSON):
   curl -X POST "http://127.0.0.1:8503/communication/publish" -H "Content-Type: application/json" -d '{"message_type":"coordinator","source":"coordinator","target":"all","content":"please_respond"}'
3. Fetch recent messages and look for `type: response` entries:
   curl "http://127.0.0.1:8503/communication/messages?limit=50" | jq '.messages[] | select(.type=="response")'

Notes
- The integration CI job runs on the self-hosted homelab runner to ensure network reachability to the local API process.
