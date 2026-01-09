# RAG MCP Server

Servidor MCP que expõe as APIs RAG do personaIDE para uso em:
- Continue
- Cline  
- Roo Code
- Claude Desktop
- VS Code Chat (via extensão MCP)

## Ferramentas Disponíveis

| Ferramenta | Descrição |
|------------|-----------|
| `rag_search` | Busca semântica em qualquer collection |
| `rag_search_chat_history` | Busca no histórico de chats |
| `rag_search_code` | Busca em código indexado |
| `rag_get_context` | Obtém contexto formatado para prompts |
| `rag_index_document` | Indexa novo documento |
| `rag_index_project` | Indexa projeto inteiro |
| `rag_stats` | Estatísticas do sistema |
| `rag_list_collections` | Lista collections disponíveis |
| `rag_submit_feedback` | Envia feedback para aprendizado |
| `rag_trigger_learning` | Dispara aprendizado manual |

## Instalação

```bash
cd /home/eddie/myClaude/rag-mcp-server
pip install mcp httpx
```

## Configuração

### Continue (config.yaml)
```yaml
mcpServers:
  - name: rag
    command: python
    args:
      - /home/eddie/myClaude/rag-mcp-server/src/rag_mcp_server.py
    env:
      RAG_API_BASE: http://192.168.15.2:8001/api/v1
```

### Cline/Roo Code (mcp.json)
```json
{
  "mcpServers": {
    "rag": {
      "command": "python",
      "args": ["/home/eddie/myClaude/rag-mcp-server/src/rag_mcp_server.py"],
      "env": {
        "RAG_API_BASE": "http://192.168.15.2:8001/api/v1"
      }
    }
  }
}
```

### Claude Desktop (claude_desktop_config.json)
```json
{
  "mcpServers": {
    "rag": {
      "command": "wsl",
      "args": ["-d", "Ubuntu", "-e", "python3", "/home/eddie/myClaude/rag-mcp-server/src/rag_mcp_server.py"],
      "env": {
        "RAG_API_BASE": "http://192.168.15.2:8001/api/v1"
      }
    }
  }
}
```

## Uso

Uma vez configurado, você pode usar comandos como:

- "Busque no histórico conversas sobre MCP server"
- "Liste as collections do RAG"
- "Mostre estatísticas do sistema RAG"
- "Indexe este código no RAG"
