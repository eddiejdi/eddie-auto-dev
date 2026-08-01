# CODE_SANDBOX_DIR

## Propósito
Diretório onde as ferramentas MCP `code_write_file`/`code_read_file`/`code_list_files` (`scripts/homelab_mcp_server.py`) criam, leem e listam código — a superfície de "criação de código/integrações" exposta a agentes (incl. o bot do WhatsApp via `TOOL_CALLING_MODEL=shared-homelab` + `mcp_tool_bridge.py`).

## Escopo
- **Consumidor**: `scripts/homelab_mcp_server.py` (`_code_sandbox_path`, `code_write_file`, `code_read_file`, `code_list_files`).
- **Default**: `<repo>/generated/integrations`.
- **Segredo**: não.

## Por que existe (sandbox, não escrita livre no repo)
O modelo que recebe essas ferramentas roda sem revisão humana de código linha a linha — permitir `path` arbitrário seria execução remota de código via WhatsApp. `_code_sandbox_path()` resolve todo `path` relativo a este diretório e **bloqueia qualquer tentativa de escapar dele** (`..`, path absoluto, symlink escapando via `resolve()`). Escrita (`code_write_file`) também:
- só aceita extensões de texto/código sem execução implícita (`.py .js .ts .json .yaml .yml .md .txt .toml .cfg .ini .sql .html .css` — **sem `.sh`**, de propósito);
- limita o tamanho do conteúdo (`_CODE_MAX_BYTES`, 200 KB);
- nunca executa o arquivo escrito — só grava texto.

## Governança
Em `scripts/misc/mcp_tool_bridge.py::TOOL_RISK`: `code_write_file` é `"high"` (exige aprovação via Telegram, mesma trava usada por `secrets_get`/`db_execute_query`); `code_read_file`/`code_list_files` são `"none"` (leitura, auto-executam).

## Relacionadas
- [[WHATSAPP_TOOL_CALLING]], [[HOMELAB_URL]], [[API_BASE_URL]]
