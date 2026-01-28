# Instruções para agentes especializados — gerar conteúdo Confluence e diagramas

Objetivo:
- Usar agentes especializados para extrair, sumarizar e documentar o estado atual do projeto
  (arquitetura, runbooks, segredos, operações) em páginas do Confluence e diagramas draw.io.

Tarefas que um agente especializado deve executar:
1. Reunir dados
   - Ler `docs/confluence/pages/*`, `diagrams/project_architecture.drawio` e os arquivos-chave do repositório
     (`tools/secrets_loader.py`, `specialized_agents/*`, `scripts/*`).
   - Buscar logs recentes em `/var/log/` e `/tmp/*.log` relacionados ao OpenWebUI e ao Agent API.

2. Sumarizar e expandir
   - Gerar uma versão detalhada em português para cada página (Overview, Architecture, Operations), incluindo
     exemplos de comandos, arquivos relevantes e checklist de correção.

3. Gerar diagramas
   - Produzir um diagrama draw.io detalhado com os componentes, fluxos de mensagens e portas.
   - Salvar como `diagrams/project_architecture.drawio` e exportar PNG `diagrams/project_architecture.png`.

4. Publicar no Confluence
   - Usar `scripts/sync_to_confluence.sh` para criar/atualizar páginas (requer credenciais de Confluence).

Prompt sugerido para o agente (Português):
"Você é um engenheiro de documentação. Leia estes arquivos e logs, sintetize uma página detalhada de Confluence para 'Arquitetura do Sistema' em Português, incluindo diagramas atualizados, responsabilidades por componente, comandos de diagnóstico e checklist de mitigação para os bloqueadores atuais. Gere também um arquivo draw.io detalhado. Ao terminar, salve os artefatos em `docs/confluence/pages/` e `diagrams/` e retorne um resumo das mudanças." 

Observações de segurança
- Nunca exponha segredos em páginas públicas. Ao publicar no Confluence, substitua valores sensíveis por placeholders e referencie o cofre.
