# 🧠 Instalação da Tool GitHub Copilot no Open WebUI

## Objetivo
Adicionar uma **Tool** no Open WebUI que executa o **GitHub Copilot CLI** via `gh copilot`.

---

## Pré-requisitos

- `gh` instalado e autenticado no servidor
- Extensão/feature `gh copilot` disponível e logada

Teste rápido no terminal do servidor:

```bash
gh copilot --help
---

## Opção A — Instalação via API (recomendado)

1. Exporte a chave do Open WebUI:

```bash
export WEBUI_API_KEY="SEU_TOKEN"
export OPENWEBUI_URL="http://192.168.15.2:3000"
2. Execute o instalador:

```bash
python3 install_copilot_function.py
---

## Opção B — Instalação manual (Admin Panel)

1. Acesse o Open WebUI: **http://192.168.15.2:3000**
2. Vá em **Admin Panel** → **Functions**
3. Clique em **Create Function**
4. Preencha:
   - **ID**: `github_copilot`
   - **Name**: `GitHub Copilot CLI`
   - **Description**: `Executa comandos do GitHub Copilot via gh copilot`
5. Cole o conteúdo do arquivo:

/home/edenilson/shared-auto-dev/openwebui_copilot_tool.py
6. Salve e deixe **Enabled**

---

## Uso no chat (exemplos)

Use a tool github_copilot com args:
suggest -q "listar arquivos grandes" -t shell
Use a tool github_copilot com args:
explain -q "tar -xzf arquivo.tar.gz"
## Execução automática (Copilot → comando → execução)

Use o método `copilot_suggest_and_run` passando uma descrição:

Use a tool github_copilot com query:
"criar um arquivo backup.txt com a lista de arquivos .log"
---

## Troubleshooting

- **"unknown command copilot"**: instale/ative o Copilot no `gh`
- **"gh não encontrado"**: instale o GitHub CLI no servidor
- **Sem saída**: verifique se o usuário está autenticado (`gh auth status`)
