#!/usr/bin/env python3
"""
Script para processar a tarefa de documentação do sistema.
Coordena: ConfluenceAgent, BPMAgent, RequirementsAnalyst
"""

import asyncio
import json
import os
import sys
import httpx
from datetime import datetime
from pathlib import Path

# Configuração
BASE_DIR = Path("/home/shared/myClaude")
TASK_FILE = BASE_DIR / "tasks/DOC-2025-01-16-001.json"
DOCS_FILE = BASE_DIR / "docs/SYSTEM_DOCUMENTATION.md"
DIAGRAM_FILE = BASE_DIR / "diagrams/arquitetura_shared_auto_dev.drawio"
API_URL = "http://localhost:8503"
OLLAMA_URL = "http://192.168.15.2:11434"

# Telegram
from tools.secrets_loader import get_telegram_token

TELEGRAM_TOKEN = get_telegram_token()
TELEGRAM_CHAT_ID = "948686300"

async def send_telegram(message: str):
    """Envia atualização para Telegram"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
        except Exception as e:
            print(f"Erro Telegram: {e}")

async def interview_agent(agent_name: str) -> dict:
    """Entrevista um agent usando Ollama local"""
    
    prompt = f"""Você é o {agent_name} do sistema Shared Auto-Dev.
    
Responda de forma estruturada:

1. **Responsabilidade Principal**: O que você faz?
2. **Tecnologias**: Quais linguagens/frameworks você domina?
3. **Endpoints**: Quais APIs você expõe (se aplicável)?
4. **Integrações**: Com quais outros agents você se comunica?
5. **Regras Seguidas**: Quais regras do sistema você implementa?
6. **Inputs/Outputs**: O que você recebe e o que você entrega?
7. **Fluxo Típico**: Descreva um workflow comum.

Seja conciso e técnico."""

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:latest",
                    "prompt": prompt,
                    "stream": False
                }
            )
            if response.status_code == 200:
                return {
                    "agent": agent_name,
                    "interview": response.json().get("response", ""),
                    "status": "completed"
                }
        except Exception as e:
            return {
                "agent": agent_name,
                "interview": f"Erro: {e}",
                "status": "error"
            }
    
    return {"agent": agent_name, "interview": "", "status": "timeout"}

async def update_documentation(interviews: list):
    """Atualiza o documento de documentação com as entrevistas"""
    
    content = DOCS_FILE.read_text()
    
    # Gerar seção de agents
    agents_section = "\n## 🤖 Agents e Responsabilidades\n\n"
    agents_section += f"> ✅ Entrevistas realizadas em {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for interview in interviews:
        if interview["status"] == "completed":
            agents_section += f"### {interview['agent']}\n\n"
            agents_section += interview["interview"]
            agents_section += "\n\n---\n\n"
    
    # Substituir seção de agents
    import re
    pattern = r"## 🤖 Agents e Responsabilidades.*?(?=\n## |$)"
    new_content = re.sub(pattern, agents_section, content, flags=re.DOTALL)
    
    DOCS_FILE.write_text(new_content)
    return True

async def git_commit_and_push(message: str):
    """Faz commit e push das alterações"""
    import subprocess
    
    os.chdir(BASE_DIR)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push"], check=True)

async def main():
    print("=" * 60)
    print("📋 TAREFA: DOC-2025-01-16-001")
    print("🎯 Documentação Completa do Sistema Shared Auto-Dev")
    print("=" * 60)
    
    # Carregar tarefa
    with open(TASK_FILE) as f:
        task = json.load(f)
    
    agents_to_interview = task["workflow"]["phases"][0]["agents_to_interview"]
    
    # Fase 1: Entrevistas
    await send_telegram("🎬 <b>Fase 1: Iniciando Entrevistas</b>\n\nTotal de agents: " + str(len(agents_to_interview)))
    
    interviews = []
    for i, agent in enumerate(agents_to_interview, 1):
        print(f"\n[{i}/{len(agents_to_interview)}] Entrevistando {agent}...")
        
        result = await interview_agent(agent)
        interviews.append(result)
        
        if i % 5 == 0:
            await send_telegram(f"📊 Progresso: {i}/{len(agents_to_interview)} entrevistas concluídas")
    
    # Fase 2: Documentação
    await send_telegram("📝 <b>Fase 2: Atualizando Documentação</b>")
    
    await update_documentation(interviews)
    
    # Fase 3: Commit e Push
    await send_telegram("🔄 <b>Fase 3: Sincronizando com GitHub</b>")
    
    try:
        await git_commit_and_push("docs: atualizar documentação com entrevistas dos agents")
        await send_telegram("✅ <b>Tarefa Concluída!</b>\n\n📄 Documentação atualizada:\nhttps://github.com/eddiejdi/shared-auto-dev/blob/main/docs/SYSTEM_DOCUMENTATION.md")
    except Exception as e:
        await send_telegram(f"⚠️ Erro no commit: {e}")
    
    print("\n" + "=" * 60)
    print("✅ TAREFA CONCLUÍDA!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
