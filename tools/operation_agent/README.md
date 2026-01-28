# Operation Agent - Evoke Handler

Este pequeno serviço fornece um endpoint `/evoke` usado pelo workflow GitHub Actions quando um run falha. Ele orquestra:

- Invocação do agente de desenvolvimento (`DEV_AGENT_ENDPOINT`) com a mesma `chat_session`.
- Invocação do agente de testes (`TEST_AGENT_ENDPOINT`) com a mesma `chat_session`.
- Opcional: solicita penalização e retreinamento ao `TRAINING_AGENT_ENDPOINT` quando `responsible_agents` é informado.

Secrets / variáveis de ambiente necessárias (definir no repositório ou ambiente onde o serviço roda):

- `OP_AGENT_SHARED_SECRET` (opcional): token Bearer que o workflow deve enviar no header `Authorization`.
- `DEV_AGENT_ENDPOINT`: URL do agente de desenvolvimento (ex: `https://op.example.com/dev-agent`).
- `TEST_AGENT_ENDPOINT`: URL do agente de testes.
- `TRAINING_AGENT_ENDPOINT` (opcional): URL do agente de treinamento que realiza penalização/retreinamento.

Como executar localmente:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/operation_agent/requirements.txt
OP_AGENT_SHARED_SECRET=secret DEV_AGENT_ENDPOINT=http://localhost:8600 TEST_AGENT_ENDPOINT=http://localhost:8601 uvicorn tools.operation_agent.evoke_handler:app --reload
```

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
```

Retorno: JSON com resultados das invocações a cada agente.
