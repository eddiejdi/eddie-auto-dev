# Conube Support Flow

Fluxo para abrir chamado de suporte na Conube usando o `specialized-agents-api`.

## Endpoint

- `POST /conube/support/open-ticket`

Base local:

- `http://127.0.0.1:8503/conube/support/open-ticket`

## O que esse fluxo faz

- Faz login na Conube com as credenciais configuradas.
- Seleciona uma tarefa aberta.
- Usa `task_id` se informado; senão, usa filtro `subject_contains` + `responsible`.
- Abre a solicitação no canal funcional da Conube:
  - `POST /api/client/tarefas/{task_id}/solicitar-recalculo`
- Retorna status antes/depois e timestamps.

## Payload

```json
{
  "headless": true,
  "task_id": null,
  "subject_contains": "DEFIS",
  "responsible": "contador",
  "message": "Olá, podem confirmar se existe alguma pendência de responsabilidade do cliente neste CNPJ?"
}
```

Campos:

- `headless`: opcional (`true` por padrão do serviço).
- `task_id`: opcional; se enviado, força abertura naquela tarefa.
- `subject_contains`: opcional; filtro por assunto quando `task_id` não é enviado.
- `responsible`: opcional; filtro por responsável (`contador`, `cliente`, etc.).
- `message`: texto que será enviado na solicitação.

## Exemplo cURL

```bash
curl -sS -X POST 'http://127.0.0.1:8503/conube/support/open-ticket' \
  -H 'Content-Type: application/json' \
  -d '{
    "headless": true,
    "subject_contains": "DEFIS",
    "responsible": "contador",
    "message": "Olá, peço confirmação formal se existe alguma pendência de responsabilidade do cliente neste CNPJ."
  }'
```

## Resposta esperada

```json
{
  "status": "ok",
  "channel": "task_recalculation",
  "endpoint": "/api/client/tarefas/5bd229d9202e060dd517e0cb/solicitar-recalculo",
  "task_id": "5bd229d9202e060dd517e0cb",
  "task_subject": "DEFIS - Entrega Anual ",
  "responsible": "contador",
  "before_status": "Pendente",
  "after_status": "Em análise",
  "before_updated_at": "2018-10-25T20:38:49.656Z",
  "after_updated_at": "2026-03-18T22:04:09.896Z",
  "message_sent": "..."
}
```

## Observações

- A Conube não retorna protocolo numérico nesse endpoint.
- Indicadores práticos de abertura:
  - `after_status` alterado (ex: `Pendente` -> `Em análise`).
  - `after_updated_at` atualizado.
- Se não achar tarefa com o filtro, a API retorna erro (`503`) com a causa.
- Credenciais necessárias:
  - `CONUBE_EMAIL` + `CONUBE_PASSWORD`, ou
  - secret `conube/rpa4all` no Secrets Agent.
