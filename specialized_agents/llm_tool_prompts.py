"""
LLM Tool Prompts — System prompts que instruem o modelo Ollama
a usar ferramentas de terminal em vez de retornar instruções manuais.

Uso:
    from specialized_agents.llm_tool_prompts import get_tool_system_prompt
    prompt = get_tool_system_prompt()
    # Enviar como 'system' no /api/chat do Ollama
"""

import json
from typing import Dict, Any, List


# ──────────────────────────────────────────────────────────────────
# Formato padrão de tool call (consistente em todos os módulos)
# ──────────────────────────────────────────────────────────────────
TOOL_CALL_OPEN = "<tool_call>"
TOOL_CALL_CLOSE = "</tool_call>"


def get_tool_system_prompt(extra_context: str = "") -> str:
    """
    Retorna system prompt que instrui o modelo a invocar ferramentas
    usando o formato <tool_call>{JSON}</tool_call>.

    Args:
        extra_context: contexto adicional para concatenar (ex: RAG results)

    Returns:
        System prompt completo
    """
    return f"""Você é um assistente técnico com acesso a ferramentas de execução no sistema.

## REGRAS OBRIGATÓRIAS

1. Quando o usuário pedir para "executar", "verificar", "rodar", "consultar", "checar":
   - NÃO retorne instruções manuais (curl, psql, etc.)
   - NÃO sugira que o usuário "rode o comando"
   - INVOQUE a ferramenta automaticamente

2. Para executar uma ferramenta, retorne EXATAMENTE neste formato JSON:

{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "SEU_COMANDO"}}}}
{TOOL_CALL_CLOSE}

3. Você pode invocar múltiplas ferramentas numa mesma resposta:

{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "docker ps"}}}}
{TOOL_CALL_CLOSE}

{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "systemctl status nginx"}}}}
{TOOL_CALL_CLOSE}

## FERRAMENTAS DISPONÍVEIS

### shell_exec — Executar comando no terminal
Parâmetros: command (obrigatório), timeout (default 30), cwd (opcional)

Comandos permitidos por categoria:
- system: uname, uptime, whoami, pwd, date, systemctl, journalctl, ps, free, df, du
- files: ls, cat, head, tail, grep, find, wc, stat, tree, mkdir, cp, mv
- dev: git, docker, python, node, npm, pip, pytest, make, cargo, go
- network: curl, wget, ping, dig, ssh, scp
- db: psql, mysql, redis-cli
- ai: ollama, jq, yq

### read_file — Ler conteúdo de arquivo
Parâmetros: filepath (obrigatório), max_lines (opcional)
Exemplo:
{TOOL_CALL_OPEN}
{{"tool": "read_file", "params": {{"filepath": "/etc/hostname"}}}}
{TOOL_CALL_CLOSE}

### list_directory — Listar diretório
Parâmetros: dirpath (obrigatório), recursive (default false)

### system_info — Informações do sistema (CPU, RAM, disco)
Parâmetros: nenhum
{TOOL_CALL_OPEN}
{{"tool": "system_info", "params": {{}}}}
{TOOL_CALL_CLOSE}

## FLUXO DE TRABALHO

1. Analise o pedido do usuário
2. Decida qual(is) ferramenta(s) usar
3. Emita o(s) {TOOL_CALL_OPEN}...{TOOL_CALL_CLOSE} necessário(s)
4. Depois do bloco de ferramenta, explique brevemente o que vai verificar
5. Quando receber o resultado da ferramenta, analise e responda em linguagem natural

## EXEMPLOS

Usuário: "Qual é o status do docker?"
Resposta:
Vou verificar os containers:
{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'"}}}}
{TOOL_CALL_CLOSE}

Usuário: "Verifique o trading agent"
Resposta:
Vou checar o status do serviço:
{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "systemctl status bitcoin-trading-agent"}}}}
{TOOL_CALL_CLOSE}

{TOOL_CALL_OPEN}
{{"tool": "shell_exec", "params": {{"command": "docker logs btc-trading --tail 20"}}}}
{TOOL_CALL_CLOSE}

{extra_context}"""


def get_tool_result_prompt(tool_name: str, result: Dict[str, Any]) -> str:
    """
    Formata resultado de ferramenta para enviar de volta ao modelo.

    Args:
        tool_name: nome da ferramenta executada
        result: resultado retornado pelo executor

    Returns:
        Mensagem formatada para role=tool em /api/chat
    """
    if result.get("success"):
        output = result.get("stdout", result.get("content", ""))
        # Truncar output grande
        if len(output) > 4000:
            output = output[:4000] + "\n... (truncado, output > 4KB)"
        return f"""[RESULTADO: {tool_name}]
Sucesso: sim
Saída:
{output}"""
    else:
        error = result.get("stderr", result.get("error", "Erro desconhecido"))
        return f"""[RESULTADO: {tool_name}]
Sucesso: não
Erro: {error}
Exit code: {result.get('exit_code', -1)}"""


def parse_tool_calls(response_text: str) -> list[dict]:
    """
    Extrai todas as invocações de ferramentas de uma resposta LLM.

    Args:
        response_text: texto completo retornado pelo modelo

    Returns:
        Lista de dicts {tool, params} encontrados
    """
    import re
    tool_calls = []
    pattern = rf"{re.escape(TOOL_CALL_OPEN)}(.*?){re.escape(TOOL_CALL_CLOSE)}"
    matches = re.finditer(pattern, response_text, re.DOTALL)

    for match in matches:
        raw = match.group(1).strip()
        try:
            parsed = json.loads(raw)
            if "tool" in parsed:
                tool_calls.append(parsed)
        except json.JSONDecodeError:
            # Tentar limpar whitespace/newlines e re-parsear
            cleaned = " ".join(raw.split())
            try:
                parsed = json.loads(cleaned)
                if "tool" in parsed:
                    tool_calls.append(parsed)
            except json.JSONDecodeError:
                pass  # Ignorar: LLM gerou JSON inválido

    return tool_calls


def strip_tool_calls(response_text: str) -> str:
    """Remove blocos <tool_call>...</tool_call> do texto para exibição."""
    import re
    pattern = rf"{re.escape(TOOL_CALL_OPEN)}.*?{re.escape(TOOL_CALL_CLOSE)}"
    return re.sub(pattern, "", response_text, flags=re.DOTALL).strip()
