Título: Corrige `DATABASE_URL` no homelab e valida persistência

Resumo:
- Sincroniza e documenta o `DATABASE_URL` usado em homelab e nos exemplos de `systemd`.
- Passos de validação e rollback inclusos.

Ações realizadas:
- Atualizei senha do Postgres no container e ajustei `DATABASE_URL` para `eddie_memory_2026`.
- Movi `tools/simple_vault/passphrase` para backup seguro e removi do repositório.
- Iniciei watcher para aplicar a variável no homelab quando o Diretor autorizar.

Validação:
- `SELECT 1` via psql executado com sucesso no homelab.
- `tools/invoke_director.py` registrou `DB publish id: 7` após correção.

