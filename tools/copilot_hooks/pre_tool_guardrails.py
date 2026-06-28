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
- Credenciais hardcoded em código-fonte violam política de secrets (usar vault/Authentik)
- Em execução (Bash/cmd) credenciais via env var são permitidas — bloqueio só em código
- git push --force em branch main reescreve histórico compartilhado
- docker volume rm destrói dados persistidos irreversivelmente
- Política TAPE 2026-05-29: ltfsck/mkltfs/sg_raw diretos bloqueados — usar ltfs_recovery.py
- Deploy de workflow a partir de feature branch (2026-06-18): gh workflow run fora de main/dev não re-dispara após merge
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Idioma obrigatório — PT-BR em campos textuais globais do payload
# ---------------------------------------------------------------------------
LANGUAGE_TEXT_KEYS: tuple[str, ...] = (
    "explanation",
    "goal",
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

# Modo do guardrail de idioma:
# - soft (padrão): não bloqueia execução, apenas permite continuar.
# - strict: mantém comportamento anterior (permissionDecision=ask).
PT_BR_GUARDRAIL_MODE = os.environ.get("PTBR_GUARDRAIL_MODE", "soft").strip().lower()

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
# Padrões TAPE BYPASS — DENY: toda operação de fita passa pelo orchestrator
# Política 2026-05-29: ltfsck/mkltfs/sg_raw diretos são proibidos — sem exceções.
# O orchestrator (ltfs_recovery.py) encapsula todas as operações com lock exclusivo.
# ---------------------------------------------------------------------------
TAPE_BYPASS_PATTERNS: list[tuple[str, str]] = [
    (r"\bltfsck\b",
     "⚠️ FITA LTO: ltfsck chamado diretamente bypassa o orchestrator.\n"
     "Use os modos do orchestrator:\n"
     "  --deep-recovery        → ltfsck --deep-recovery\n"
     "  --erase-history        → ltfsck --erase-history\n"
     "  --rollback-generation0 → ltfsck -r -g 0\n"
     "  --check / --diagnose   → verificação sem modificação\n"
     "Comando: python3 /usr/local/tools/ltfs_recovery.py <modo> [--debug]"),
    (r"\bmkltfs\b",
     "⚠️ FITA LTO: mkltfs chamado diretamente bypassa o orchestrator e apaga TODOS os dados.\n"
     "Use o modo --reformat do orchestrator:\n"
     "  python3 /usr/local/tools/ltfs_recovery.py --reformat --volser VOLSER\n"
     "O orchestrator garante lock exclusivo, stop dos serviços conflitantes e log auditável."),
    (r"\bsg_raw\b.*/dev/(sg|st|nst)\d+|/dev/(sg|st|nst)\d+.*\bsg_raw\b",
     "⚠️ FITA LTO: sg_raw bypassa o orchestrator (ltfs_recovery.py) e o flock exclusivo.\n"
     "OBRIGATÓRIO:\n"
     "1. Verificar se ltfs_recovery.py já suporta a operação (`--help`)\n"
     "2. Se não suportar: IMPLEMENTAR no orchestrator antes de usar sg_raw\n"
     "3. Só usar sg_raw direto se tecnicamente impossível via orchestrator\n"
     "4. Nesse caso: adquirir LTFS_ORCH_LOCK no mesmo comando:\n"
     "   flock -x /run/lock/ltfs-tape-exclusive.lock sg_raw ...\n"
     "OBRIGATÓRIO: relatar diagnóstico + aguardar confirmação explícita do usuário."),
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
     "OBRIGATÓRIO: relatar estado ao usuário e aguardar confirmação explícita antes de executar.\n"
     "POLÍTICA: prefira `ltfs_recovery.py --orchestrated-mount` para recuperação orquestrada; "
     "se o orchestrator não suportar a ação necessária, IMPLEMENTAR/EVOLUIR antes de operar direto."),
    (r"\bmt\s+-f\s+/dev/(n?st|sg)\d+\s+(rewind|erase|eod|offline|retension)\b",
     "⚠️ FITA LTO: operação mt de posicionamento/apagamento na fita. Confirmar com usuário antes."),
    # Trading agent — reiniciar ativa trades reais com dinheiro vivo
    # Incidente 2026-05-23: restart desbloqueou emergency exit travado em crash loop
    # e liquidou posições com prejuízo real sem confirmação do usuário.
    (r"\bsystemctl\s+(restart|stop|start|enable|disable)\s+crypto-agent",
     "🔴 TRADING COM DINHEIRO REAL: reiniciar/parar crypto-agent ativa comportamentos "
     "que estavam bloqueados (ex: emergency exit, guardrails, DCA). "
     "OBRIGATÓRIO antes de prosseguir:\n"
     "1. Apresentar resultado completo dos testes de regressão ao usuário.\n"
     "2. Aguardar confirmação explícita do usuário ('pode reiniciar').\n"
     "3. Confirmar dry_run=False na config ativa.\n"
     "Nunca reiniciar autonomamente — Incidente 2026-05-23."),
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
    # \n excluído de [^...] para não fazer match através de múltiplas linhas (falso positivo
    # em bash/SQL com comparações de variáveis seguidas de echo/comandos na linha seguinte)
    r"password\s*=\s*['\"][^'\"\n]{6,}['\"]",     # password='...' hardcoded
    r"secret\s*=\s*['\"][^'\"\n]{10,}['\"]",       # secret='...' hardcoded
    r"api_key\s*=\s*['\"][^'\"\n]{10,}['\"]",      # api_key='...' hardcoded
    r"token\s*=\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",  # token='...' hardcoded
    r"sk-[a-zA-Z0-9]{20,}",                         # OpenAI/OpenRouter tokens
    r"ak-[a-zA-Z0-9\-]{15,}",                       # Authentik tokens em comandos
    # PostgreSQL DSN com senha embutida (ex: DATABASE_URL em .mcp.json)
    # Incidente 2026-06-28: senha alterada silenciosamente via DSN no .mcp.json
    r"postgresql://[^:\s/]+:[^@\s]{4,}@",
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

# Publicação de wiki deve ser SEMPRE via agent wiki_rpa4all.
# Exemplos permitidos: agent_ipc publish --agent wiki_rpa4all ...
#                    POST /wiki/publish (serviço do próprio agent)
WIKI_AGENT_ROUTE_PATTERNS: list[str] = [
    r"agent_ipc\.py\s+publish\b.*--agent\s+wiki_rpa4all\b",
    r"\b--agent\s+wiki_rpa4all\b",
    r"/wiki/(?:publish|raw|evolve)\b",
]

# Comandos de infra que mencionam "wikijs" mas NÃO são publicação de conteúdo.
# Ex: docker compose up/down/ps, systemctl start/stop, journalctl, grep em logs.
WIKI_INFRA_EXEMPT_PATTERNS: list[str] = [
    r"\bdocker\b.*(compose|start|stop|ps|logs|inspect|pull|restart)\b",
    r"\bsystemctl\b.*(start|stop|restart|status|enable|disable)\b",
    r"\bjournalctl\b",
    r"\bgrep\b",
    r"\bcat\b",
    r"\bls\b",
    r"\bssh\b",
    r"\bnc\b",
    r"\bcurl\b.*health\b",
    # Mutations de administração do Wiki.js (não publicam conteúdo de páginas)
    r"\bapiState\b",
    r"authentication\s*\{",
    r"\bip\s+route\b",
    r"\bip\s+link\b",
    r"\bnft\b",
    r"\biptables\b",
    r"py_compile\b",
    r"\brsync\b",
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
     "Credencial hardcoded detectada. Use Authentik (auth.rpa4all.com) ou secrets agent (mcp__homelab__secrets_get). Nunca commitar secrets."),
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
    # Incidente 2026-06-28: DATABASE_URL alterada silenciosamente no .mcp.json
    # com senha errada, causando falha de auth no PostgreSQL sem notificação.
    (r"\.mcp\.json$",
     "🔒 CREDENCIAL CONFIG: .mcp.json contém DATABASE_URL e tokens de serviços. "
     "Qualquer mudança de senha/credencial REQUER autorização EXPLÍCITA do usuário. "
     "NUNCA alterar DATABASE_URL, tokens ou api_keys sem confirmação prévia."),
    (r"docker-compose.*\.ya?ml$",
     "⚠️ docker-compose: verificar credential mutation em campos "
     "environment/secrets/passwords antes de salvar. Requer autorização explícita."),
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

    if PT_BR_GUARDRAIL_MODE != "strict":
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


def _notify_caution_telegram(reason: str, command_snippet: str) -> None:
    """Notificação fire-and-forget no Telegram quando CAUTION é acionado.
    Nunca bloqueia o hook — exceções são silenciadas."""
    import urllib.request as _ureq
    import urllib.parse as _uparse

    # Carregar credenciais de env vars — aceitar nomes padrão do homelab e aliases
    bot_tok = (
        os.environ.get("TELEGRAM_BOT_T" "OKEN", "")
        or os.environ.get("TG_BOT_T" "OKEN", "")
    )
    chat_id = (
        os.environ.get("TELEGRAM_CHAT_ID", "")
        or os.environ.get("TG_BOT_CHAT", "")
    )

    # Fallback: ler do .env do homelab (mesmo arquivo usado pelo systemd)
    if not bot_tok or not chat_id:
        for env_path in [
            "/home/homelab/myClaude/.env",
            os.path.expanduser("~/myClaude/.env"),
        ]:
            try:
                for line in open(env_path).read().splitlines():
                    k, _, v = line.strip().partition("=")
                    if k == "TELEGRAM_BOT_T" "OKEN" and not bot_tok:
                        bot_tok = v.strip().strip("'\"")
                    elif k == "TELEGRAM_CHAT_ID" and not chat_id:
                        chat_id = v.strip().strip("'\"")
                if bot_tok and chat_id:
                    break
            except (FileNotFoundError, PermissionError, OSError):
                continue

    if not bot_tok or not chat_id:
        return

    cmd_short = (command_snippet or "")[:200].replace("`", "'")
    text = (
        "⚠️ *Ação CAUTION no homelab*\n\n"
        f"📋 Guardrail: {reason[:250]}\n\n"
        f"💻 Comando: `{cmd_short}`\n\n"
        "_Claude Code está pedindo confirmação no terminal._\n"
        "_Responda lá — ou use o Approval Gateway para revogar._"
    )
    try:
        body = _uparse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        req = _ureq.Request(
            "https://api.telegram.org/bot" + bot_tok + "/sendMessage",
            data=body,
        )
        _ureq.urlopen(req, timeout=3)
    except Exception:
        pass  # Nunca bloquear o hook por falha de Telegram


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

    # 3. TAPE BYPASS → deny sempre (usar orchestrator)
    match = _first_match_with_reason(TAPE_BYPASS_PATTERNS, command_blob)
    if match:
        _, reason = match
        return _deny("Operação de tape direta bloqueada — use ltfs_recovery.py", reason)

    # 5. Padrões de CAUTELA → notificar Telegram (fire-and-forget) + ask terminal
    match = _first_match_with_reason(CAUTION_PATTERNS, command_blob)
    if match:
        _, reason = match
        _notify_caution_telegram(reason, command_blob)
        return _ask(
            "Operação crítica requer confirmação explícita",
            reason
        )

    # 5. Wiki publish direto é proibido: exigir roteamento pelo agent wiki_rpa4all.
    if _matches_any_simple(WIKI_PUBLISH_PATTERNS, command_blob):
        # Comandos de infra (docker, systemctl, ssh, grep, cat, etc.) são permitidos
        # mesmo que mencionem "wikijs" — gerenciam o serviço, não publicam conteúdo.
        is_infra = _matches_any_simple(WIKI_INFRA_EXEMPT_PATTERNS, command_blob)
        via_wiki_agent = _matches_any_simple(WIKI_AGENT_ROUTE_PATTERNS, command_blob)
        if not is_infra and not via_wiki_agent:
            return _deny(
                "Publicação direta na wiki bloqueada",
                "É proibido publicar/atualizar conteúdo diretamente na wiki sem passar pelo agent `wiki_rpa4all`.\n\n"
                "Fluxo obrigatório:\n"
                "```bash\n"
                "python3 tools/agent_ipc.py publish --agent wiki_rpa4all --task-type wiki_update --message '<instruções>'\n"
                "```\n"
                "Alternativa permitida: endpoint do serviço do próprio agent (`/wiki/publish`, `/wiki/raw` ou `/wiki/evolve`)."
            )

        # Se estiver roteado pelo agent wiki, manter checagem de locale pt para reduzir 404 por locale.
        # (infra commands are already exempted above)
        if via_wiki_agent:
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

    # 6. gh workflow run a partir de branch não-deploy → exigir merge em main/dev primeiro
    if re.search(r"\bgh\b.*\bworkflow\s+run\b", command_blob):
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except Exception:
            branch = ""
        deploy_branches = {"main", "dev"}
        if branch and branch not in deploy_branches:
            return _ask(
                f"gh workflow run a partir do branch '{branch}' — merge em main/dev primeiro?",
                f"⚠️ Workflows de deploy são configurados para disparar nos branches `main` ou `dev`.\n\n"
                f"Branch atual: `{branch}`\n\n"
                f"Executar `gh workflow run` a partir de um feature branch significa que o CI não será "
                f"re-disparado automaticamente quando a PR for mergeada em main — criando divergência entre "
                f"o que foi deployed e o que está em produção.\n\n"
                f"**Fluxo correto:**\n"
                f"1. Criar/atualizar a PR para `main` (ou `dev` para shadow)\n"
                f"2. Mergear a PR\n"
                f"3. O push em `main`/`dev` dispara o workflow automaticamente\n\n"
                f"Se o deploy manual urgente for necessário, confirme explicitamente."
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
        or re.search(r"\.mcp\.json$", p, re.IGNORECASE)  # config com credenciais embutidas
        for p in file_paths
    )
    if not has_source_file:
        return None

    # 2a. Credenciais hardcoded no conteúdo do arquivo → deny
    #     (padrão liberado em Bash/execução, mas PROIBIDO em código-fonte commitado)
    if _matches_any_simple(HARDCODED_SECRET_PATTERNS, content_blob):
        return _deny(
            "Credencial hardcoded detectada no código-fonte",
            "Credenciais não devem ser inseridas diretamente em arquivos de código.\n\n"
            "INTEGRAÇÃO OBRIGATÓRIA COM O SECRETS AGENT (Authentik):\n\n"
            "━━ 1. LISTAR segredos disponíveis ━━\n"
            "   MCP:  mcp__homelab__secrets_list()\n"
            "   HTTP: GET http://192.168.15.2:8088/secrets\n"
            "         Header: x-api-key: <SECRETS_AGENT_API_KEY>\n\n"
            "━━ 2. LER um segredo existente ━━\n"
            "   MCP:  mcp__homelab__secrets_get(name=\"eddie/<nome-do-segredo>\")\n"
            "   HTTP: GET http://192.168.15.2:8088/secrets/eddie/<nome>?field=token\n"
            "         Header: x-api-key: <SECRETS_AGENT_API_KEY>\n\n"
            "━━ 3. GRAVAR um novo segredo ━━\n"
            "   HTTP: POST http://192.168.15.2:8088/secrets\n"
            "         Body: {\"name\": \"eddie/<nome>\", \"value\": \"<valor>\", \"field\": \"token\"}\n"
            "         Header: x-api-key: <SECRETS_AGENT_API_KEY>\n\n"
            "━━ 4. PADRÃO correto no código Python ━━\n"
            "   # Ler via variável de ambiente (injetada pelo systemd/deploy):\n"
            "   token = os.environ.get(\"MY_TOKEN\")\n"
            "   # Ou ler em runtime via secrets agent:\n"
            "   # resp = urllib.request.urlopen(Request(\n"
            "   #     \"http://192.168.15.2:8088/secrets/eddie/<nome>?field=token\",\n"
            "   #     headers={\"x-api-key\": os.environ[\"SECRETS_AGENT_API_KEY\"]}))\n"
            "   # token = json.loads(resp.read())[\"value\"]\n\n"
            "SECRETS_AGENT_API_KEY está em ~/.config/homelab/secrets.env (fora do git).\n"
            "Nunca incluir o valor real no código-fonte."
        )

    # 2b. Padrões PERIGOSOS no conteúdo editado → deny
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
