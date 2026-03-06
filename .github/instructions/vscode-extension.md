---
applyTo: "eddie-copilot/**,**/*.ts,**/*.js"
---

# Regras VS Code Extension — Eddie Auto-Dev

## Desenvolvimento
```bash
cd eddie-copilot
npm install && npm run compile  # Build
npm run watch                    # Dev watch mode
# F5 no VS Code → Extension Development Host
```

## Homelab Agent Client
- 7 comandos: `homelabExecute`, `homelabHealth`, `homelabDockerPs`, `homelabDockerLogs`, `homelabSystemdStatus`, `homelabSystemdRestart`, `homelabLogs`
- Arquivo: `eddie-copilot/src/homelabAgentClient.ts`

## Cores dinâmicas da janela VS Code
O agente DEVE sinalizar estado via `python tools/vscode_window_state.py <estado> --agent-id <id>`:
- **Amarelo** (`processing`): ao INICIAR tarefa
- **Verde** (`done`): ao CONCLUIR com sucesso
- **Vermelho** (`error`): ao encontrar ERRO crítico
- **Laranja** (`prompt`): ao AGUARDAR input do usuário
- Prioridade: `error > prompt > processing > done`
- Janela só fica verde quando TODOS os agentes estão `done`
