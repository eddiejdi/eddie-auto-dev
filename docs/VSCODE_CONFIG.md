# VS Code Configuration (recommended) 🔧

Recomendações para configurar sua IDE para desenvolvimento remoto e trabalhar com este repositório:

Extensões recomendadas:
- ms-vscode-remote.remote-ssh (Remote - SSH)
- ms-python.python (Python support)
- ms-azuretools.vscode-docker (Docker support)
- eamodio.gitlens (Git UX)

Sugestões rápidas:
1. Abra o comando `Remote-SSH: Add New SSH Host...` e adicione `ssh homelab@192.168.15.2` (ou seu host), então conecte-se.
2. Configure o interpretador Python (no host remoto) em `Command Palette -> Python: Select Interpreter`.
3. Habilite `editor.formatOnSave` e instale `black`/`ruff` no ambiente remoto.
4. Para deploy via GitHub Actions: crie os `Secrets` no repo (`HOMELAB_SSH_PRIVATE_KEY`, `HOMELAB_HOST`, `HOMELAB_USER`).

Arquivo `.vscode/extensions.json` de exemplo (local, opcional):
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-vscode-remote.remote-ssh",
    "ms-azuretools.vscode-docker",
    "eamodio.gitlens"
  ]
}
```

> Nota: este repositório ignora `.vscode/` por padrão. Se quiser compartilhar as recomendações com a equipe, crie um arquivo `docs/VSCODE_CONFIG.md` (este arquivo) ou um `README` na equipe.
