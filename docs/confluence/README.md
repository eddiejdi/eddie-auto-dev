Projeto: documentação para Confluence
----------------------------------

Este diretório contém rascunhos de páginas e artefatos que podem ser publicados
no Confluence do projeto. Inclui:

- `pages/PROJECT_OVERVIEW.md` — visão geral do sistema e contexto técnico.
- `pages/ARCHITECTURE.md` — arquitetura do sistema (componentes, fluxos).
- `pages/OPERATIONS.md` — operações, deploy e troubleshooting.

Como usar:

1. Revise os arquivos em `pages/` e ajuste conteúdo.
2. Para publicar, use `scripts/sync_to_confluence.sh` com variáveis de ambiente
   `CONFLUENCE_BASE_URL`, `CONFLUENCE_USER` e `CONFLUENCE_API_TOKEN`.
3. Opcional: execute os agentes especializados (ver `specialized_agents/confluence_tasks.md`) para
   gerar/expandir conteúdo automaticamente.
