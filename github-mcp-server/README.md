# GitHub MCP Server

🚀 Servidor MCP (Model Context Protocol) para integração completa com GitHub.

## Compatível com:

| Extensão | Status | Configuração |
|----------|--------|--------------|
| **Continue** | ✅ | `config/continue-config.json` |
| **Cline** | ✅ | `config/cline-mcp-settings.json` |
| **Roo Code** | ✅ | `config/roo-code-mcp-settings.json` |
| **Claude Desktop** | ✅ | `config/claude-desktop-config.json` |
| **Cursor** | ✅ | Use config do Cline |
| **Windsurf** | ✅ | Use config do Continue |

## Funcionalidades (35+ ferramentas)

### 🔐 Autenticação
- `github_set_token` - Configurar token de acesso

### 📂 Repositórios
- `github_list_repos` - Listar repositórios
- `github_get_repo` - Obter detalhes do repositório
- `github_create_repo` - Criar repositório
- `github_delete_repo` - Deletar repositório

### 🐛 Issues
- `github_list_issues` - Listar issues
- `github_get_issue` - Obter detalhes da issue
- `github_create_issue` - Criar issue
- `github_update_issue` - Atualizar issue
- `github_add_comment` - Adicionar comentário

### 🔀 Pull Requests
- `github_list_prs` - Listar PRs
- `github_get_pr` - Obter detalhes do PR
- `github_create_pr` - Criar PR
- `github_merge_pr` - Fazer merge do PR

### 🌿 Branches
- `github_list_branches` - Listar branches

### 📝 Commits
- `github_list_commits` - Listar commits
- `github_get_commit` - Obter detalhes do commit

### 🔍 Busca
- `github_search_code` - Buscar código
- `github_search_repos` - Buscar repositórios
- `github_search_issues` - Buscar issues/PRs

### 📁 Arquivos
- `github_get_file` - Obter conteúdo de arquivo
- `github_create_or_update_file` - Criar/atualizar arquivo

### ⚙️ GitHub Actions
- `github_list_workflows` - Listar workflows
- `github_list_workflow_runs` - Listar execuções
- `github_trigger_workflow` - Disparar workflow

### 🏷️ Releases
- `github_list_releases` - Listar releases
- `github_create_release` - Criar release

### 📋 Gists
- `github_list_gists` - Listar gists
- `github_create_gist` - Criar gist

### 🔔 Outros
- `github_list_notifications` - Listar notificações
- `github_rate_limit` - Verificar rate limit

---

## Instalação

### 1. Instalar dependências

```bash
cd /home/home-lab/myClaude/github-mcp-server
pip install -r requirements.txt
```

### 2. Configurar Token GitHub

Crie um Personal Access Token em: https://github.com/settings/tokens/new

Scopes necessários:
- `repo` - Acesso total a repositórios
- `read:user` - Ler perfil do usuário
- `read:org` - Ler informações de organizações
- `gist` - Acesso a gists
- `notifications` - Acesso a notificações
- `workflow` - Acesso ao GitHub Actions

### 3. Configurar variável de ambiente

```bash
export GITHUB_TOKEN="ghp_seu_token_aqui"
```

Ou adicione ao seu `.bashrc` / `.zshrc`:
```bash
echo 'export GITHUB_TOKEN="ghp_seu_token_aqui"' >> ~/.bashrc
```

---

## Configuração por Extensão

### Continue

1. Copie o conteúdo de `config/continue-config.json`
2. Cole em `~/.continue/config.json`

Ou use o comando:
```bash
cp config/continue-config.json ~/.continue/config.json
```

### Cline

1. Abra VS Code → Configurações → Cline → MCP Settings
2. Cole o conteúdo de `config/cline-mcp-settings.json`

### Roo Code

1. Abra VS Code → Configurações → Roo Code → MCP Servers
2. Cole o conteúdo de `config/roo-code-mcp-settings.json`

### Claude Desktop

1. Abra o arquivo de configuração:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Adicione a configuração de `config/claude-desktop-config.json`

---

## Uso

Após configurar, você pode usar comandos naturais como:

- "Liste meus repositórios"
- "Crie uma issue no repo X com título Y"
- "Mostre os PRs abertos do projeto Z"
- "Busque código que contém função login"
- "Faça merge do PR #123"
- "Crie uma release v1.0.0"

---

## Testando

```bash
# Testar se o servidor inicia corretamente
python src/github_mcp_server.py

# Você deve ver: "🚀 Iniciando GitHub MCP Server..."
```

---

## Arquitetura

```
github-mcp-server/
├── src/
│   └── github_mcp_server.py    # Servidor MCP principal
├── config/
│   ├── continue-config.json    # Config para Continue
│   ├── cline-mcp-settings.json # Config para Cline
│   ├── roo-code-mcp-settings.json # Config para Roo Code
│   └── claude-desktop-config.json # Config para Claude Desktop
├── requirements.txt            # Dependências Python
├── package.json               # Metadados do projeto
└── README.md                  # Esta documentação
```

---

## Servidor no Homelab

O MCP Server também pode ser instalado no servidor:

```bash
# No servidor 192.168.15.2
scp -r github-mcp-server homelab@192.168.15.2:~/
ssh homelab@192.168.15.2 'cd ~/github-mcp-server && pip install -r requirements.txt'
```

---

## Troubleshooting

### Erro: "Token GitHub não configurado"
→ Use a ferramenta `github_set_token` primeiro ou defina `GITHUB_TOKEN` no ambiente.

### Erro: "Módulo mcp não encontrado"
→ Execute: `pip install mcp httpx`

### Erro: "Acesso negado"
→ Verifique se seu token tem os scopes necessários.

---

## Licença

MIT License
