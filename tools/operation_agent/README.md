# Operation Agent - Evoke Handler

Este pequeno serviço fornece um endpoint `/evoke` usado pelo workflow GitHub Actions quando um run falha. Ele orquestra:

- Invocação do agente de desenvolvimento (`DEV_AGENT_ENDPOINT`) com a mesma `chat_session`.
- Invocação do agente de testes (`TEST_AGENT_ENDPOINT`) com a mesma `chat_session`.
- Opcional: solicita penalização e retreinamento ao `TRAINING_AGENT_ENDPOINT` quando `responsible_agents` é informado.


Secrets / variáveis de ambiente necessárias (definir no repositório ou ambiente onde o serviço roda):

- `OP_AGENT_SHARED_SECRET` or `OP_AGENT_TOKEN` (recommended): token Bearer que o workflow deve enviar no header `Authorization`. The handler accepts either name for compatibility.
- `OP_AGENT_ENDPOINT`: URL where the workflow should POST (set in the workflow as `OP_AGENT_ENDPOINT`).
- `OP_AGENT_CHAT_SESSION` (optional): a chat/session id the workflow can pass through.
- `DEV_AGENT_ENDPOINT`: URL do agente de desenvolvimento (ex: `https://op.example.com/dev-agent`).
- `TEST_AGENT_ENDPOINT`: URL do agente de testes.
- `TRAINING_AGENT_ENDPOINT` (opcional): URL do agente de treinamento que realiza penalização/retreinamento. If omitted, the handler will still accept `/penalize_and_retrain` locally.

How to add GitHub repository secrets (brief):

1. Go to repository Settings → Secrets and variables → Actions → New repository secret.
2. Add `OP_AGENT_TOKEN` (or `OP_AGENT_SHARED_SECRET`) with the shared Bearer token used by the workflow.
3. Add `OP_AGENT_ENDPOINT` with the public URL of this service (e.g. `https://op.example.com`).
4. Add `OP_AGENT_CHAT_SESSION` if you want workflows to forward a chat session id.

Workflow mapping notes:
- The workflow `evoke_operation_agent_on_failure.yml` posts to `${OP_AGENT_ENDPOINT%/}/evoke` and sends `Authorization: Bearer ${OP_AGENT_TOKEN}`. The handler accepts that token when present.


Como executar localmente:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/operation_agent/requirements.txt
OP_AGENT_SHARED_SECRET=secret DEV_AGENT_ENDPOINT=http://localhost:8600 TEST_AGENT_ENDPOINT=http://localhost:8601 uvicorn tools.operation_agent.evoke_handler:app --reload
Exemplo de payload enviado pelo workflow (JSON):

```json
{
  "repository": "owner/repo",
  "workflow": "ci.yml",
  "run_id": "21438306328",
  "branch": "feat/my-branch",
  "sha": "abcdef123456",
  "chat_session": "chatid-123",
  "responsible_agents": ["dev-agent-1", "linter-agent"]
}
Retorno: JSON com resultados das invocações a cada agente.
