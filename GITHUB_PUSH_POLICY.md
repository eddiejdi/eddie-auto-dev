# GitHub Push Policy (Política de Push no GitHub)

## Status: DESABILITADO

⛔ **Agents não possuem autonomia para fazer push/commit no GitHub**

## Razão

Para evitar poluição do repositório com commits duplicados, não-funcionais ou desnecessários, foi removida a autonomia dos agentes para fazer push no GitHub.

## Locais Afetados

- `specialized_agents/agent_manager.py` → `push_to_github()` - Retorna erro
- `specialized_agents/github_client.py` → Git push desabilitado
- `telegram_bot.py` → `_git_commit_and_push()` - Retorna erro
- `specialized_agents/api.py` → `POST /github/push` - Returnaa erro 
- `specialized_agents/api_ondemand.py` → `POST /github/push` - Retorna erro
- `specialized_agents/streamlit_app.py` → Push button desabilitado

## Como Usar Agora

### Opção 1: Via CLI Manual
```bash
cd <project_path>
git add .
git commit -m "Descrição da mudança"
git push origin main
```

### Opção 2: Via CI/CD Pipeline
Configure um GitHub Actions workflow para fazer push automaticamente quando um evento ocorrer.

### Opção 3: Via Scripts Aprovados
Solicitar via Telegram ao @eddiejdi para executar push manualmente após revisão.

## Resultado Esperado

- ✅ Redução de commits duplicados
- ✅ Melhor qualidade de histórico do Git
- ✅ Controle manual sobre o que é commitado
- ✅ Rastreabilidade de mudanças

## Revertendo (Para Administradores)

Se precisar reverter esta policy, remova os guards da função `push_to_github()` em:
- `specialized_agents/agent_manager.py` (linha ~307)
- `specialized_agents/github_client.py` (linha ~669)
- `telegram_bot.py` (linha ~1254)

Data de Aplicação: 09/02/2026
