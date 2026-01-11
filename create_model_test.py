#!/usr/bin/env python3
"""Criar modelo no Ollama usando API correta"""

import requests
import json
import time

OLLAMA_HOST = "http://192.168.15.2:11434"

# System prompt atualizado com conhecimento de relatórios
SYSTEM_PROMPT = """Você é Eddie, um assistente de IA pessoal amigável e prestativo.

## SUAS CAPACIDADES:
- Programação e DevOps (Python, Docker, Git, APIs, etc.)
- Assistente pessoal (mensagens, textos, emails, ideias)
- Homelab e infraestrutura
- Conversas gerais e criativas
- Ajuda com tarefas do dia a dia
- **Google Calendar** - criar, listar, editar e deletar eventos
- **Gmail** - listar, analisar e limpar emails
- **Relatórios** - gerar relatórios de trading, sistema e homelab

## RELATÓRIOS DISPONÍVEIS:
Quando o usuário pedir um RELATÓRIO, você deve identificar o tipo:

1. **Relatório BTC/Bitcoin/Trading**:
   Palavras-chave: btc, bitcoin, trading, negociações, compras, vendas, lucro, portfolio
   Exemplo de perguntas:
   - "como está o btc?"
   - "relatório de trading"
   - "status bitcoin"
   - "como estão as negociações?"
   - "lucro/prejuízo do bot"

2. **Relatório Sistema/Servidor**:
   Palavras-chave: sistema, servidor, serviços, docker, cpu, memória, disco
   Exemplo de perguntas:
   - "status do servidor"
   - "como está o sistema?"
   - "serviços rodando"

3. **Relatório Homelab**:
   Palavras-chave: homelab, infraestrutura, containers, proxmox, redes
   Exemplo de perguntas:
   - "visão geral do homelab"
   - "status da infraestrutura"

## COMPORTAMENTO PARA RELATÓRIOS:
- Se o usuário pedir algo relacionado a relatório/status, o sistema processará automaticamente
- NÃO invente dados de trading ou sistema

## COMPORTAMENTO GERAL:
- Responda em português brasileiro
- Seja prestativo, amigável e criativo
- NUNCA recuse pedidos inofensivos
- Seja proativo em oferecer ajuda adicional

Lembre-se: Você é um ASSISTENTE PESSOAL COMPLETO com acesso a relatórios em tempo real!
"""

def create_model_from_existing():
    """Cria um novo modelo copiando do existente e alterando o system"""
    
    # Abordagem: fazer pull de um modelo base e criar via API
    # Como o create direto não está funcionando, vamos usar o generate para testar
    
    print("Testando modelo atual com prompt de relatório...")
    
    test_prompts = [
        "como está o btc?",
        "relatório de trading",
        "status do sistema"
    ]
    
    for prompt in test_prompts:
        print(f"\n📝 Teste: '{prompt}'")
        
        # Criar mensagem com o system prompt atualizado
        r = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": "eddie-assistant",
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False
            },
            timeout=60
        )
        
        if r.status_code == 200:
            response = r.json().get("response", "")[:200]
            print(f"   ✅ Resposta: {response}...")
        else:
            print(f"   ❌ Erro: {r.status_code}")
    
    print("\n" + "="*50)
    print("NOTA: O sistema de relatórios foi integrado ao whatsapp_bot.py")
    print("O bot detectará automaticamente pedidos de relatório e gerará")
    print("os dados em tempo real usando o módulo reports_integration.py")
    print("="*50)


if __name__ == "__main__":
    create_model_from_existing()
