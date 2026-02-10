# Como obter secrets do Secrets Agent

Este documento descreve as formas recomendadas de acessar secrets usados pelos agentes.

- Visão geral
  - O *Secrets Agent* é o repositório central de segredos para o ambiente homelab.
  - Em muitas instalações o agente fica disponível no host homelab na porta `8088` (ex.: `http://<HOMELAB_HOST>:8088`).

- Autenticação
  - O acesso ao Secrets Agent normalmente requer um `API_KEY` (Bearer token) ou credenciais armazenadas em `agent secrets`/vault.
  - Nunca exponha o `API_KEY` em commits.

- Acesso rápido (exemplos)
  - Request via curl (substitua <API_KEY> e <HOMELAB_HOST>):

    ```bash
    curl -H "Authorization: Bearer <API_KEY>" "http://<HOMELAB_HOST>:8088/secrets/<SECRET_NAME>"
    ```

  - Em Python (requests):

    ```py
    import requests
    r = requests.get(
      "http://<HOMELAB_HOST>:8088/secrets/<SECRET_NAME>",
      headers={"Authorization": "Bearer <API_KEY>"},
      timeout=10,
    )
    r.raise_for_status()
    print(r.json())
    ```

- Arquivos de fallback
  - Alguns agentes/scrips locais podem armazenar secrets em arquivos de ambiente como `.env.jira` sob o diretório do projeto no homelab (ex.: `~/eddie-auto-dev/.env.jira`). Use estes arquivos apenas como fallback e não os commit no Git.

- Cliente local / utilitários
  - Use o cliente/driver do projeto em `tools/secrets_agent/` ou `tools/vault/secret_store.py` quando disponível.
  - Se existir um `Secrets Agent` em container ou serviço systemd, cheque `systemctl status` ou `docker ps` no homelab para encontrar o host/porta.

- Boas práticas
  - Prefira GitHub Secrets ou o Secrets Agent em vez de arquivos `.env` em repositórios.
  - Restrinja o escopo de tokens e rotacione quando necessário.
  - Documente em notas de implantação (docs) qualquer localização alternativa de secrets.

Se precisar, posso varrer os arquivos `.md` do repositório e inserir um link para este documento onde for apropriado.