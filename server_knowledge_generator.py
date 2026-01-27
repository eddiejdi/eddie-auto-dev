#!/usr/bin/env python3
"""
Gerador de Conhecimento do Servidor
Coleta informações do homelab e gera documentação para RAG
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path

def run_ssh_command(cmd: str) -> str:
    """Executa comando via SSH no servidor homelab"""
    try:
        result = subprocess.run(
            ["ssh", "homelab@192.168.15.2", cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Erro: {e}"

def collect_server_info() -> dict:
    """Coleta informações do servidor"""
        doc += """
### Open WebUI
- **Porta**: 3000
- **URL Local**: http://192.168.15.2:3000
- **URL Externa**: N/A (no public tunnel configured)
- **Autenticação**: Google OAuth
- **Recursos**:
    - Chat com modelos Ollama
    - Upload de documentos para RAG
    - Histórico de conversas
    - Múltiplos modelos

"""
                })
    return containers

def collect_ollama_models() -> list:
    """Lista modelos do Ollama"""
    output = run_ssh_command("curl -s http://localhost:11434/api/tags 2>/dev/null")
    try:
        data = json.loads(output)
        return [m.get("name", "") for m in data.get("models", [])]
    except:
        return []

def collect_systemd_services() -> list:
    """Lista serviços systemd relevantes"""
    services = ["ollama", "docker"]
    status = []
    for svc in services:
        st = run_ssh_command(f"systemctl is-active {svc} 2>/dev/null")
        status.append({"name": svc, "status": st})
    return status

def collect_project_structure() -> dict:
    """Coleta estrutura de projetos"""
    output = run_ssh_command("find ~/projects -maxdepth 2 -type d 2>/dev/null | head -50")
    return {"directories": output.split('\n') if output else []}

def generate_markdown_doc() -> str:
    """Gera documentação em Markdown"""
    
    server = collect_server_info()
    docker = collect_docker_info()
    models = collect_ollama_models()
    services = collect_systemd_services()
    projects = collect_project_structure()
    
    doc = f"""# Homelab Server - Documentação Completa

## Informações do Sistema
- **Hostname**: {server['hostname']}
- **IP**: {server['ip']}
- **OS**: {server['os']}
- **Uptime**: {server['uptime']}
- **Memória Total**: {server['memory']}
- **Espaço em Disco Livre**: {server['disk']}
- **Última Atualização**: {server['timestamp']}

## Serviços Principais

### Ollama (LLM Local)
- **Porta**: 11434
- **URL**: http://192.168.15.2:11434
- **Modelos Disponíveis**:
"""
    for model in models:
        doc += f"  - {model}\n"
    
        doc += """
### Open WebUI
- **Porta**: 3000
- **URL Local**: http://192.168.15.2:3000
- **URL Externa**: N/A (nenhum túnel público configurado)
- **Autenticação**: Google OAuth
- **Recursos**:
    - Chat com modelos Ollama
    - Upload de documentos para RAG
    - Histórico de conversas
    - Múltiplos modelos

### Public Tunnel
- **Status**: Nenhum túnel público configurado no repositório. Se você usa um túnel (Cloudflare, ngrok, etc.), defina a URL em `HOMELAB_TUNNEL_URL` ou documente o provedor na sua documentação de deploy.

## Containers Docker
"""
    for c in docker:
        doc += f"""
### {c['name']}
- **Imagem**: {c['image']}
- **Status**: {c['status']}
- **Portas**: {c['ports']}
"""

    doc += """
## Serviços Systemd
"""
    for svc in services:
        status_emoji = "✅" if svc['status'] == "active" else "❌"
        doc += f"- {status_emoji} **{svc['name']}**: {svc['status']}\n"

    doc += """
## Estrutura de Projetos
"""
    for d in projects['directories'][:20]:
        if d:
            doc += f"- `{d}`\n"

    doc += """
## Comandos de Gerenciamento

### Ollama
```bash
# Listar modelos
ollama list

# Executar modelo interativo
ollama run eddie-coder

# Testar API
curl http://localhost:11434/api/tags

# Gerar resposta
curl http://localhost:11434/api/generate -d '{"model":"eddie-coder","prompt":"Hello"}'
```

### Docker
```bash
# Ver containers
docker ps

# Logs do Open WebUI
docker logs open-webui --tail 50

# Reiniciar Open WebUI
docker restart open-webui
```

### Public Tunnel
No public tunnel helper configured in this repository. If you use a tunnel provider, add details to your deployment docs.

## API Endpoints

### Ollama API (Local)
- GET http://192.168.15.2:11434/api/tags - Lista modelos
- POST http://192.168.15.2:11434/api/generate - Gerar texto
- POST http://192.168.15.2:11434/api/chat - Chat completion

### Ollama API (Via Tunnel)
No external tunnel configured. Use local Ollama API at http://192.168.15.2:11434

## Troubleshooting

### Ollama não responde
```bash
systemctl status ollama
systemctl restart ollama
journalctl -u ollama -f
```

### Open WebUI com erro
```bash
docker logs open-webui
docker restart open-webui
```

### Túnel público (se aplicável)
Se você utiliza um túnel público (Cloudflare, ngrok, Cloud Run, etc.), verifique o helper de túnel que estiver em uso. Não há comandos de túnel configurados neste repositório por padrão.

Exemplo genérico (substitua pelo seu provedor):
```bash
# /path/to/your/tunnel-helper status
# /path/to/your/tunnel-helper start
```

## Contato e Suporte
- Servidor gerenciado por: Eddie
- Localização: Rede local 192.168.15.x
"""
    
    return doc

def save_documentation():
    """Salva documentação em arquivo"""
    doc = generate_markdown_doc()
    
    # Salvar localmente
    local_path = Path("/home/homelab/myClaude/homelab_documentation.md")
    local_path.write_text(doc)
    print(f"Documentação salva em: {local_path}")
    
    # Salvar no servidor
    subprocess.run([
        "ssh", "homelab@192.168.15.2",
        f"cat > ~/projects/homelab-documentation.md << 'ENDDOC'\n{doc}\nENDDOC"
    ])
    print("Documentação enviada para o servidor")
    
    return doc

if __name__ == "__main__":
    print("Gerando documentação do servidor...")
    doc = save_documentation()
    print("\n" + "="*50)
    print("Documentação gerada com sucesso!")
    print("="*50)
    print("\nPara usar no Open WebUI:")
    print("1. Acesse http://192.168.15.2:3000")
    print("2. Vá em Workspace > Knowledge")
    print("3. Faça upload do arquivo homelab_documentation.md")
    print("4. Selecione o conhecimento ao iniciar um novo chat")
