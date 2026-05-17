"""PreToolUse hook — guardrails de segurança para comandos de terminal e edições de arquivo.

Lições aprendidas incorporadas:
- Incidente SSH 2026-03-02: restart de sshd bloqueou servidor remotamente
- Incidente rede 2026-04-21: mudanças iptables sem rollback → host inacessível
- Guardrail PnL 2026-04-13: agente AI modificou _get_guardrail_sell_verdict sem autorização
- Ollama keep_alive:0 descarrega modelo permanentemente do runner
- OLLAMA_NUM_PARALLEL>4 satura GPU0 (RTX 2060, comprovado 2026-04-11)
- SQLite proibido: APENAS PostgreSQL porta 5433 (schema btc)
- dry_run deve ser bool Python (True/False), nunca int
- DELETE sem WHERE em tabelas de trading destrói histórico de trades
- Credenciais hardcoded violam política de secrets (usar vault/Authentik)
- git push --force em branch main reescreve histórico compartilhado
- docker volume rm destrói dados persistidos irreversivelmente
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Idioma obrigatório — PT-BR em campos textuais globais do payload
# ---------------------------------------------------------------------------
LANGUAGE_TEXT_KEYS: tuple[str, ...] = (
    "explanation",
    "goal",
    "description",
    "query",
    "prompt",
    "reason",
    "message",
)

PT_BR_HINTS: tuple[str, ...] = (
    " para ",
    " com ",
    " sem ",
    " nao ",
    " não ",
    " deve ",
    " validar ",
    " executar ",
    " arquivo ",
    " usuario ",
    " usuário ",
    " servico ",
    " serviço ",
    " linguag",
)

# ---------------------------------------------------------------------------
# Padrões PERIGOSOS — BLOCK imediato (sem confirmação)
# ---------------------------------------------------------------------------
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Destruição de dados/sistema
    (r"\brm\s+-rf\b", "rm -rf é irreversível. Não permitido sem confirmação explícita do usuário."),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard descarta mudanças irreversivelmente."),
    (r"\bgit\s+push\s+(-f|--force)\b", "git push --force reescreve histórico compartilhado. Use --force-with-lease com cautela."),
    (r"\bgit\s+checkout\s+--(?:\s|$)", "git checkout -- descarta mudanças de trabalho sem aviso."),
    (r"\bdd\s+if=", "dd pode sobrescrever discos. Operação proibida sem confirmação."),
    (r"\bmkfs(\.|\s)", "mkfs formata partições irreversivelmente."),
    # Database — operações destrutivas
    (r"\bdrop\s+table\b", "DROP TABLE destrói dados de forma irreversível."),
    (r"\btruncate\s+table\b", "TRUNCATE TABLE remove todos os registros de forma irreversível."),
    (r"\bdelete\s+from\s+btc\.\w+\s*(?!where)\b", "DELETE sem WHERE em tabela btc.* é proibido — destrói histórico de trades."),
    (r"\bdelete\s+from\s+(trades|decisions|market_states|learning_rewards|performance_stats|candles)\s*(?!where)", "DELETE sem WHERE em tabela de trading destrói dados irreversivelmente."),
    # Docker — remoção de volumes/dados
    (r"\bdocker\s+volume\s+rm\b", "docker volume rm destrói dados persistidos irreversivelmente."),
    (r"\bdocker\s+system\s+prune\b", "docker system prune pode remover volumes de dados. Use com --filter para evitar perda."),
    # SQLite — proibido no projeto
    (r"\bsqlite3\b.*\.(db|sqlite|sqlite3)\b", "SQLite é PROIBIDO neste workspace. Use PostgreSQL na porta 5433 (schema btc)."),
]

# ---------------------------------------------------------------------------
# Padrões de REDE/FIREWALL — exigem rollback agendado antes de executar
# (Incidente 2026-04-21: homelab ficou inacessível por mudança de rede sem rollback)
# ---------------------------------------------------------------------------
NETWORK_FIREWALL_PATTERNS: list[str] = [
    r"\biptables\s+-[ADIRF]\b",       # iptables rules
    r"\bnftables?\b",                   # nftables
    r"\bnetplan\s+apply\b",            # netplan apply
    r"\bufw\s+(enable|disable|reset|deny|allow)\b",   # ufw changes
    r"\bip\s+(link|addr|route)\s+(add|del|change|flush)\b",  # ip commands
    r"\bifconfig\b.*\bdown\b",         # interface down
    r"\biwconfig\b",                   # wireless config
]

# ---------------------------------------------------------------------------
# Padrões de CAUTELA — perguntar confirmação antes
# ---------------------------------------------------------------------------
CAUTION_PATTERNS: list[tuple[str, str]] = [
    # Fita LTO / LTFS — operações que afetam hardware de tape e dados não commitados
    # Incidente 2026-05-15: restart do ltfs-lto6.service com LTFS em read-only causou
    # "extra blocks detected" e impossibilidade de montar — sempre pedir confirmação.
    (r"\bsystemctl\s+(restart|stop|disable)\s+ltfs",
     "⚠️ FITA LTO: restart/stop do serviço LTFS pode corromper dados em buffer RAM não commitados na fita. "
     "OBRIGATÓRIO: relatar estado ao usuário e aguardar confirmação explícita antes de executar."),
    (r"\bltfsck\b",
     "⚠️ FITA LTO: ltfsck modifica estrutura da fita irreversivelmente. "
     "OBRIGATÓRIO: relatar diagnóstico ao usuário e aguardar confirmação explícita antes de executar."),
    (r"\bmkltfs\b",
     "⚠️ FITA LTO: mkltfs FORMATA a fita apagando todos os dados. "
     "OBRIGATÓRIO: confirmar com usuário que os dados foram verificados como backup antes de executar."),
    (r"\bmt\s+-f\s+/dev/(n?st|sg)\d+\s+(rewind|erase|eod|offline|retension)\b",
     "⚠️ FITA LTO: operação mt de posicionamento/apagamento na fita. Confirmar com usuário antes."),
    # Serviços críticos
    (r"\bsystemctl\s+(restart|stop|disable)\s+(ssh|sshd)\b",
     "Restart/stop de SSH pode bloquear acesso remoto ao homelab. Valide com 'sudo sshd -t' primeiro e mantenha canal alternativo."),
    (r"\bsystemctl\s+(restart|stop|disable)\s+(docker|networking|systemd-networkd|systemd-resolved|ufw|pihole-FTL|dnsmasq)\b",
     "Este serviço é crítico para a infraestrutura. Confirme antes de reiniciar."),
    (r"\bshutdown\b", "shutdown vai desligar o sistema."),
    (r"\breboot\b", "reboot vai reiniciar o sistema."),
    # Docker — remoção de containers/redes (sem volumes)
    (r"\bdocker\s+rm\s+-f\b", "docker rm -f force-remove pode interromper serviços críticos."),
    (r"\bdocker\s+network\s+rm\b", "docker network rm pode desconectar containers em execução."),
    # Modificação de sshd_config
    (r"sshd_config", "Modificação de sshd_config requer: 1) editar, 2) sudo sshd -t, 3) confirmar, 4) reiniciar."),
    # git clean
    (r"\bgit\s+clean\s+-fd?\b", "git clean -f/fd remove arquivos não rastreados irreversivelmente."),
    # Ollama — parâmetros que afetam estabilidade das GPUs
    (r"OLLAMA_NUM_PARALLEL\s*=\s*[5-9]\d*", "OLLAMA_NUM_PARALLEL>4 satura GPU0 (RTX 2060 8GB). Máximo seguro comprovado: 4."),
    (r'"keep_alive"\s*:\s*["\']?0["\']?\b', "keep_alive:0 descarrega o modelo do runner Ollama permanentemente. Use -1 para manter carregado."),
    (r"keep_alive=0\b", "keep_alive=0 descarrega o modelo do runner Ollama permanentemente. Use -1 para manter carregado."),
    # Cloud APIs sem tentativa GPU (violação da política GPU-first)
    (r"(api\.anthropic\.com|api\.openai\.com|generativelanguage\.googleapis\.com)",
     "⚠️ GPU-FIRST: Tentar SEMPRE GPU0:11434 → GPU1:11435 antes de qualquer API cloud. Cloud só como fallback de último recurso."),
    # Setar modelo na placa (viola política: usar o que já está carregado)
    # Incidente 2026-05-13: rss-sentiment-exporter carregou qwen3:0.6b no GPU1 via FALLBACK_MODEL, expulsando gemma3:1b+nomic-embed-text
    (r"ollama\s+run\s+\S+",
     "🔒 PROIBIDO SETAR MODELO NA PLACA: 'ollama run <model>' força carregamento de modelo específico. "
     "Todo ambiente DEVE usar o que já está carregado na VRAM (keep_alive=-1). "
     "Se precisar de inferência, use a API do endpoint já ativo sem especificar modelo."),
]

# ---------------------------------------------------------------------------
# Padrões de credenciais hardcoded em comandos (segurança)
# ---------------------------------------------------------------------------
HARDCODED_SECRET_PATTERNS: list[str] = [
    r"password\s*=\s*['\"][^'\"]{6,}['\"]",     # password='...' hardcoded
    r"secret\s*=\s*['\"][^'\"]{10,}['\"]",       # secret='...' hardcoded
    r"api_key\s*=\s*['\"][^'\"]{10,}['\"]",      # api_key='...' hardcoded
    r"token\s*=\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",  # token='...' hardcoded
    r"sk-[a-zA-Z0-9]{20,}",                       # OpenAI/OpenRouter tokens
    r"ak-[a-zA-Z0-9\-]{15,}",                     # Authentik tokens em comandos
]

# ---------------------------------------------------------------------------
# Wiki.js locale guardrail — sempre validar locale pt antes de subir conteúdo
# ---------------------------------------------------------------------------
WIKI_PUBLISH_PATTERNS: list[str] = [
    r"\bcreate_wiki_page\.(py|sh)\b",
    r"\bupdate_wiki_page\.py\b",
    r"\bwiki[_-]?rpa4all\b",
    r"\bwikijs\b",
    r"wiki\.rpa4all\.com",
]

WIKI_LOCALE_PT_VALIDATION_PATTERNS: list[str] = [
    r"wiki\.rpa4all\.com/pt(?:/|\b)",
    r"[?&]locale=pt(?:[-_][A-Z]{2})?\b",
    r"\blocale\s*=\s*['\"]pt(?:[-_][A-Z]{2})?['\"]",
    r"\blang\s*=\s*['\"]pt(?:[-_][A-Z]{2})?['\"]",
    r"\blocale\s+pt\b",
]

# ---------------------------------------------------------------------------
# Padrões de edição de ARQUIVO que são proibidos/cautelosos
# (aplicados quando o tool é de edição, não de terminal)
# ---------------------------------------------------------------------------
EDIT_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Trading guardrail — NUNCA MODIFICAR (Incidente 2026-04-13)
    (r"_get_guardrail_sell_verdict",
     "🔒 CÓDIGO PROTEGIDO: _get_guardrail_sell_verdict() é INTOCÁVEL. Ver /memories/repo/trading-guardrail-protected.md. "
     "Esta função protege o PnL mínimo para SELL. Modificações foram revertidas em 2026-04-13."),
    # SQLite no código Python de produção
    (r"\bimport\s+sqlite3\b",
     "import sqlite3 é PROIBIDO no código de produção. Use psycopg2 com PostgreSQL na porta 5433 (schema btc)."),
    # Credentials hardcoded em código
    (r"(password|senha|secret|api_key|token)\s*=\s*['\"][^'\"]{8,}['\"]",
     "Credencial hardcoded detectada. Use tools/vault/secret_store.py ou variáveis de ambiente. Nunca commitar secrets."),
]

EDIT_CAUTION_PATTERNS: list[tuple[str, str]] = [
    # Setar modelo na placa (viola política: usar o que já está carregado)
    # Incidente 2026-05-13: FALLBACK_MODEL=qwen3:0.6b no service expulsou modelos preloaded do GPU1
    (r"OLLAMA_(?:FALLBACK|CLASSIFIER|SENTIMENT|BASE|EMBED)_MODEL(?:_GPU[01])?\s*=\s*[\w:.-]+",
     "🔒 PROIBIDO SETAR MODELO NA PLACA: Alterar *_MODEL* em services/env força carregamento de modelo específico na GPU. "
     "Todo ambiente DEVE usar o modelo já carregado via preload (keep_alive=-1). "
     "Se precisar alterar o modelo carregado, atualize o script de preload (/usr/local/bin/ollama-gpu1-preload.sh) e reinicie o service ollama-gpu1."),
    (r"ExecStartPost.*(?:ollama\s+run|api/generate.*model)",
     "🔒 PROIBIDO SETAR MODELO NA PLACA: ExecStartPost não deve forçar carregamento de modelo específico inline. "
     "Use /usr/local/bin/ollama-gpu1-preload.sh centralizado que já controla os modelos do GPU1."),
    # dry_run como int (deve ser bool)
    (r"\bdry_run\s*=\s*[01]\b",
     "dry_run deve ser bool Python (True/False), NUNCA int (0/1). Viola o schema da tabela btc.trades."),
    # DELETE sem WHERE em queries de trading
    (r"DELETE\s+FROM\s+(?:btc\.)?\w+['\"]?\s*\"?\s*(?!.*WHERE)",
     "DELETE sem cláusula WHERE detectado. Sempre incluir WHERE symbol=%s e filtros de segurança."),
    # autocommit False em código de trading (exceto training_db.py)
    (r"conn\.autocommit\s*=\s*False",
     "conn.autocommit=False detectado. No trading, autocommit deve ser True (exceto training_db.py com commits explícitos)."),
    # keep_alive 0 no código Python
    (r'"keep_alive"\s*:\s*["\']?0["\']?',
     "keep_alive:0 descarrega modelos Ollama permanentemente. Use -1 (infinito) ou tempo em segundos."),
    # OLLAMA_NUM_PARALLEL muito alto
    (r"OLLAMA_NUM_PARALLEL\s*=\s*[5-9]\d*",
     "OLLAMA_NUM_PARALLEL>4 satura GPU0 (RTX 2060 8GB). Máximo seguro comprovado: 4."),
]

# Arquivos protegidos que nunca devem ser editados por ferramentas automáticas
PROTECTED_FILE_PATTERNS: list[tuple[str, str]] = [
    (r"btc_trading_agent/trading_agent\.py",
     "⚠️ ARQUIVO CRÍTICO: trading_agent.py contém código de trading em produção. "
     "Certifique-se de que _get_guardrail_sell_verdict() NÃO está sendo modificada."),
    (r"etc/ssh/sshd_config",
     "⚠️ ARQUIVO CRÍTICO: sshd_config. Sempre validar com 'sudo sshd -t' após editar. "
     "NUNCA reiniciar sshd sem canal alternativo de acesso garantido."),
    (r"/etc/(iptables|nftables|netplan)/",
     "⚠️ ARQUIVO DE REDE CRÍTICO: Agendar rollback automático ANTES de aplicar: "
     "'echo \"iptables -F; iptables -P INPUT ACCEPT; systemctl restart ssh\" | sudo at now + 3 minutes'"),
]


def _load_input() -> dict[str, Any]:
    """Lê e parseia o payload JSON do stdin."""
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _payload_get(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Busca uma chave em variantes snake_case/camelCase usadas por diferentes clientes."""
    for key in keys:
        if key in payload:
            return payload[key]
    return default


def _matches_any_simple(patterns: list[str], text: str) -> bool:
    """Verifica se algum padrão simples (sem mensagem) faz match."""
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _first_match_with_reason(
    patterns: list[tuple[str, str]], text: str
) -> tuple[str, str] | None:
    """Retorna (padrão, razão) do primeiro match, ou None."""
    for pattern, reason in patterns:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            return pattern, reason
    return None


def _extract_command_blob(payload: dict[str, Any]) -> str:
    """Extrai o blob de comando para análise — apenas o campo 'command' para evitar
    falsos positivos com conteúdo de heredocs ou strings sendo escritas em arquivos.

    Para 'git commit -m "..."', remove o conteúdo da mensagem para evitar falsos positivos
    (a mensagem descreve mudanças, não executa comandos).
    """
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        # Para ferramentas de terminal, priorizar o campo 'command' específico
        # Evita falsos positivos quando o heredoc contém comandos como strings
        for key in ("command", "cmd", "script"):
            val = tool_input.get(key, "")
            if isinstance(val, str) and val:
                # Remover mensagem de git commit para evitar falsos positivos
                # "git commit -m 'mensagem com conteúdo'|"mensagem"|$(cat heredoc)"
                cleaned = re.sub(
                    r'\bgit\s+commit\b.*',
                    'git commit [message stripped]',
                    val,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                return cleaned
    # Fallback para outros tipos de tool_input
    return json.dumps(tool_input, ensure_ascii=False)


def _extract_content_blob(payload: dict[str, Any]) -> str:
    """Extrai o conteúdo novo/editado para análise de edições de arquivo."""
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    if not isinstance(tool_input, dict):
        return ""
    parts: list[str] = []
    for key in ("newString", "content", "new_string", "text", "fileText", "file_text"):
        val = tool_input.get(key, "")
        if isinstance(val, str) and val:
            parts.append(val)
    # replacements array (multi_replace_string_in_file)
    for item in tool_input.get("replacements", []):
        if isinstance(item, dict):
            val = item.get("newString", "")
            if isinstance(val, str):
                parts.append(val)
    return "\n".join(parts)


def _extract_file_paths(payload: dict[str, Any]) -> list[str]:
    """Extrai paths de arquivos sendo editados."""
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("filePath", "file_path", "path", "target", "uri"):
        val = tool_input.get(key, "")
        if isinstance(val, str) and val:
            paths.append(val)
    for item in tool_input.get("replacements", []):
        if isinstance(item, dict):
            val = item.get("filePath", "")
            if isinstance(val, str) and val:
                paths.append(val)
    return paths


def _extract_natural_language_blob(payload: dict[str, Any]) -> str:
    """Extrai texto natural de campos de intenção para validar idioma PT-BR.

    Ignora comandos técnicos puros e foca apenas em campos textuais usados
    para explicar intenção da ação ao usuário.
    """
    tool_input = _payload_get(payload, "tool_input", "toolInput", "input", default={})
    chunks: list[str] = []

    if isinstance(tool_input, dict):
        for key in LANGUAGE_TEXT_KEYS:
            val = tool_input.get(key)
            if isinstance(val, str) and val.strip():
                chunks.append(val)

    for key in LANGUAGE_TEXT_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            chunks.append(val)

    return "\n".join(chunks)


def _looks_like_pt_br(text: str) -> bool:
    """Retorna True quando o texto apresenta indícios fortes de PT-BR."""
    lowered = f" {text.lower()} "
    if any(marker in lowered for marker in ("ã", "á", "é", "í", "ó", "ú", "ç")):
        return True

    hints_found = sum(1 for hint in PT_BR_HINTS if hint in lowered)
    return hints_found >= 2


def _check_language_guardrail(payload: dict[str, Any], tool_name: str) -> str | None:
    """Exige PT-BR em campos textuais globais do payload."""
    if not (_is_command_like_tool(tool_name) or _is_edit_like_tool(tool_name)):
        return None

    text_blob = _extract_natural_language_blob(payload)
    if not text_blob.strip():
        return None

    # Se não há letras, é provável payload técnico (ex.: UUID, flags) — ignora.
    if not re.search(r"[a-zA-Z]", text_blob):
        return None

    if _looks_like_pt_br(text_blob):
        return None

    return _ask(
        "Idioma obrigatório PT-BR não detectado",
        "Este workspace exige PT-BR nos campos textuais de intenção da ação "
        "(explanation/goal/description/query/prompt/reason/message). "
        "Reescreva em português do Brasil e tente novamente."
    )


def _is_command_like_tool(tool_name: str) -> bool:
    """Retorna True se o tool executa comandos de terminal."""
    lowered = tool_name.lower()
    return any(token in lowered for token in ["terminal", "execute", "command", "run", "shell", "bash"])


def _is_edit_like_tool(tool_name: str) -> bool:
    """Retorna True se o tool edita/cria arquivos."""
    lowered = tool_name.lower()
    return any(token in lowered for token in ["edit", "create", "write", "replace", "patch", "file", "string"])


def _deny(reason: str, context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": context,
        }
    })


def _ask(reason: str, context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
            "additionalContext": context,
        }
    })


def _check_terminal_commands(command_blob: str) -> str | None:
    """Verifica padrões perigosos em comandos de terminal. Retorna JSON de resposta ou None."""
    # 1. Padrões PERIGOSOS → deny
    match = _first_match_with_reason(DANGEROUS_PATTERNS, command_blob)
    if match:
        _, reason = match
        return _deny(
            "Comando destrutivo bloqueado pelos guardrails do workspace",
            f"{reason}\n\nSe necessário, obtenha confirmação explícita do usuário antes de prosseguir."
        )

    # 2. Rede/Firewall sem rollback agendado → ask
    if _matches_any_simple(NETWORK_FIREWALL_PATTERNS, command_blob):
        has_rollback = bool(re.search(r"\bat\s+now\b|\batrm\b", command_blob, re.IGNORECASE))
        if not has_rollback:
            return _ask(
                "Mudança de rede/firewall sem rollback automático detectada",
                "⚠️ INCIDENTE 2026-04-21: Mudanças de rede sem rollback bloquearam o homelab remotamente.\n\n"
                "OBRIGATÓRIO antes de aplicar:\n"
                "```bash\n"
                "echo 'iptables -F; iptables -P INPUT ACCEPT; systemctl restart ssh' \\\n"
                "  | sudo at now + 3 minutes\n"
                "```\n"
                "Cancelar com 'atrm <job_id>' somente após validar que SSH ainda funciona."
            )

    # 3. Credenciais hardcoded em comandos → ask
    if _matches_any_simple(HARDCODED_SECRET_PATTERNS, command_blob):
        return _ask(
            "Possível credencial hardcoded detectada no comando",
            "Credenciais não devem aparecer em comandos de terminal. "
            "Use variáveis de ambiente ou tools/vault/secret_store.py.\n"
            "Nunca exponha tokens/senhas em logs ou histórico de terminal."
        )

    # 4. Padrões de CAUTELA → ask
    match = _first_match_with_reason(CAUTION_PATTERNS, command_blob)
    if match:
        _, reason = match
        return _ask(
            "Operação crítica requer confirmação explícita",
            reason
        )

    # 5. Wiki.js publish sem validação explícita de locale pt → ask
    if _matches_any_simple(WIKI_PUBLISH_PATTERNS, command_blob):
        has_locale_pt_validation = _matches_any_simple(WIKI_LOCALE_PT_VALIDATION_PATTERNS, command_blob)
        if not has_locale_pt_validation:
            return _ask(
                "Publicação Wiki sem validação de locale pt detectada",
                "Antes de subir conteúdo para a wiki, valide explicitamente o locale `pt` para evitar 404 por locale incorreto.\n\n"
                "Exemplo de validação obrigatória:\n"
                "```bash\n"
                "curl -sf -o /dev/null -w 'HTTP %{http_code}\\n' 'https://wiki.rpa4all.com/pt/<path>'\n"
                "```\n"
                "Somente depois execute a publicação/update da página."
            )

    return None


def _is_test_file(file_paths: list[str]) -> bool:
    """Retorna True se todos os arquivos sendo editados são arquivos de teste."""
    if not file_paths:
        return False
    return all(
        re.search(r"(^|/)tests?/|test_.*\.py$|_test\.py$", p.replace("\\", "/"), re.IGNORECASE)
        for p in file_paths
    )


def _check_file_edits(payload: dict[str, Any]) -> str | None:
    """Verifica padrões perigosos em edições de arquivo. Retorna JSON de resposta ou None."""
    content_blob = _extract_content_blob(payload)
    file_paths = _extract_file_paths(payload)
    all_paths_str = " ".join(file_paths).replace("\\", "/")

    # 1. Arquivos protegidos → ask com contexto
    for path_pattern, reason in PROTECTED_FILE_PATTERNS:
        if re.search(path_pattern, all_paths_str, re.IGNORECASE):
            return _ask(
                "Arquivo protegido sendo editado — verificação necessária",
                reason
            )

    # Arquivos de teste: pular verificações de conteúdo (os testes precisam referenciar
    # padrões proibidos como strings para validar o próprio hook)
    if _is_test_file(file_paths):
        return None

    # Verificações de conteúdo só se aplicam a arquivos Python/YAML/config relevantes
    # Arquivos .txt, .md, .json genéricos, mensagens de commit, etc. → skip
    has_source_file = any(
        re.search(r"\.(py|yml|yaml|sh|conf|cfg|ini|toml|env)$", p, re.IGNORECASE)
        for p in file_paths
    )
    if not has_source_file:
        return None

    # 2. Padrões PERIGOSOS no conteúdo editado → deny
    match = _first_match_with_reason(EDIT_DANGEROUS_PATTERNS, content_blob)
    if match:
        _, reason = match
        return _deny(
            "Conteúdo proibido detectado na edição do arquivo",
            reason
        )

    # 3. Padrões de CAUTELA no conteúdo editado → ask
    match = _first_match_with_reason(EDIT_CAUTION_PATTERNS, content_blob)
    if match:
        _, reason = match
        return _ask(
            "Padrão suspeito detectado na edição — confirme antes de prosseguir",
            reason
        )

    return None


def main() -> int:
    payload = _load_input()
    tool_name = str(_payload_get(payload, "tool_name", "toolName", "tool", default=""))
    command_blob = _extract_command_blob(payload)

    language_guardrail = _check_language_guardrail(payload, tool_name)
    if language_guardrail:
        print(language_guardrail)
        return 0

    # Verificações para ferramentas de terminal
    if _is_command_like_tool(tool_name):
        result = _check_terminal_commands(command_blob)
        if result:
            print(result)
            return 0

    # Verificações para ferramentas de edição de arquivo
    if _is_edit_like_tool(tool_name):
        result = _check_file_edits(payload)
        if result:
            print(result)
            return 0

    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
