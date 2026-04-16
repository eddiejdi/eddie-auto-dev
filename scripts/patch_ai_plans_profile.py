#!/usr/bin/env python3
"""
Migração: adiciona coluna `profile` em btc.ai_plans e atualiza o INSERT do
trading_agent.py para gravar o perfil de cada plano de IA.

Passos:
1. ALTER TABLE btc.ai_plans ADD COLUMN IF NOT EXISTS profile TEXT DEFAULT 'default'
2. Patch trading_agent.py: INSERT inclui profile
3. Patch trading_agent.py: housekeeping DELETE filtra por profile

Uso:
  python3 scripts/patch_ai_plans_profile.py [--dry-run]

Requer: psycopg2, SSH a homelab@192.168.15.2 (acesso a /home/homelab/myClaude).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv
AGENT_FILE = Path("/apps/crypto-trader/trading/btc_trading_agent/trading_agent.py")

DB_HOST = os.getenv("PGHOST", "192.168.15.2")
DB_PORT = int(os.getenv("PGPORT", "5433"))
DB_NAME = os.getenv("PGDATABASE", "btc_trading")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "eddie_memory_2026")

# ---------------------------------------------------------------------------
# 1. Migração SQL
# ---------------------------------------------------------------------------

MIGRATION_SQL = """
ALTER TABLE btc.ai_plans
  ADD COLUMN IF NOT EXISTS profile TEXT NOT NULL DEFAULT 'default';

COMMENT ON COLUMN btc.ai_plans.profile IS
  'Perfil de risco que gerou o plano: conservative | aggressive | default';
"""


def run_migration() -> bool:
    """Adiciona coluna profile em btc.ai_plans via psycopg2."""
    try:
        import psycopg2  # type: ignore
    except ImportError:
        print("❌ psycopg2 não disponível — execute a migration manualmente:")
        print(MIGRATION_SQL)
        return False

    if DRY_RUN:
        print("🔍 [DRY] Migration SQL:")
        print(MIGRATION_SQL)
        return True

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(MIGRATION_SQL)
        cur.close()
        conn.close()
        print("✅ Migration aplicada: btc.ai_plans.profile adicionada")
        return True
    except Exception as exc:
        print(f"❌ Falha na migration: {exc}")
        return False


# ---------------------------------------------------------------------------
# 2. Patch do trading_agent.py
# ---------------------------------------------------------------------------

# ---- INSERT: adiciona profile nos campos e valores -------------------------
OLD_INSERT = (
    '"""INSERT INTO btc.ai_plans\n'
    "                       (timestamp, symbol, plan_text, model, regime, price, metadata)\n"
    "                       VALUES (%s, %s, %s, %s, %s, %s, %s)\"\"\","
)
NEW_INSERT = (
    '"""INSERT INTO btc.ai_plans\n'
    "                       (timestamp, symbol, plan_text, model, regime, price, metadata, profile)\n"
    "                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)\"\"\","
)

# ---- Valores do INSERT: adiciona self.state.profile no tuple ---------------
OLD_INSERT_VALUES = (
    "                    (\n"
    "                        time.time(),\n"
    "                        self.symbol,\n"
    "                        plan_text,\n"
    "                        model,\n"
    "                        regime,\n"
    "                        price,\n"
    "                        json.dumps(metadata or {}),\n"
    "                    ),"
)
NEW_INSERT_VALUES = (
    "                    (\n"
    "                        time.time(),\n"
    "                        self.symbol,\n"
    "                        plan_text,\n"
    "                        model,\n"
    "                        regime,\n"
    "                        price,\n"
    "                        json.dumps(metadata or {}),\n"
    "                        self.state.profile,\n"
    "                    ),"
)

# ---- Housekeeping DELETE: filtra por profile também -----------------------
OLD_HOUSEKEEPING = (
    '                cursor.execute(\n'
    '                    """DELETE FROM btc.ai_plans\n'
    "                       WHERE symbol = %s AND id NOT IN (\n"
    "                           SELECT id FROM btc.ai_plans\n"
    "                           WHERE symbol = %s\n"
    "                           ORDER BY timestamp DESC LIMIT 10\n"
    "                       )\"\"\",\n"
    "                    (self.symbol, self.symbol),\n"
    "                )"
)
NEW_HOUSEKEEPING = (
    '                cursor.execute(\n'
    '                    """DELETE FROM btc.ai_plans\n'
    "                       WHERE symbol = %s AND profile = %s AND id NOT IN (\n"
    "                           SELECT id FROM btc.ai_plans\n"
    "                           WHERE symbol = %s AND profile = %s\n"
    "                           ORDER BY timestamp DESC LIMIT 10\n"
    "                       )\"\"\",\n"
    "                    (self.symbol, self.state.profile, self.symbol, self.state.profile),\n"
    "                )"
)

PATCHES: list[tuple[str, str]] = [
    (OLD_INSERT, NEW_INSERT),
    (OLD_INSERT_VALUES, NEW_INSERT_VALUES),
    (OLD_HOUSEKEEPING, NEW_HOUSEKEEPING),
]


def patch_trading_agent() -> bool:
    """Aplica patches no trading_agent.py do homelab via SSH."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "homelab@192.168.15.2", f"cat {AGENT_FILE}"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        print(f"❌ Não foi possível ler {AGENT_FILE} via SSH: {result.stderr}")
        return False
    content = result.stdout

    original = content
    errors: list[str] = []

    for old, new in PATCHES:
        if old not in content:
            errors.append(f"Padrão não encontrado:\n{old[:120]}...")
        else:
            content = content.replace(old, new, 1)

    if errors:
        for err in errors:
            print(f"❌ {err}")
        return False

    if content == original:
        print("ℹ️  Nenhuma alteração (patch já aplicado?)")
        return True

    if DRY_RUN:
        print(f"🔍 [DRY] trading_agent.py: {len(PATCHES)} patches seriam aplicados")
        return True

    # Escreve via SSH usando base64 para evitar problemas de escaping
    import base64
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    remote_cmd = (
        f"python3 -c \""
        f"import base64; "
        f"open('{AGENT_FILE}', 'w', encoding='utf-8').write("
        f"base64.b64decode('{encoded}').decode('utf-8'))\""
    )
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "homelab@192.168.15.2", remote_cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"❌ Falha ao escrever arquivo: {result.stderr}")
        return False
    print(f"✅ trading_agent.py: {len(PATCHES)} patches aplicados (homelab)")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Executa migração completa: SQL + patch do agente."""
    print("=" * 60)
    print("Migração: btc.ai_plans + profile")
    print(f"Modo: {'DRY-RUN' if DRY_RUN else 'REAL'}")
    print("=" * 60)

    ok = True

    print("\n[1/2] Migration SQL...")
    ok = run_migration() and ok

    print("\n[2/2] Patch trading_agent.py...")
    ok = patch_trading_agent() and ok

    if ok:
        print("\n✅ Migração concluída. Reinicie o serviço btc-trading-agent para ativar.")
        print("   sudo systemctl restart btc-trading-agent-conservative btc-trading-agent-aggressive btc-trading-agent-default")
    else:
        print("\n❌ Migração incompleta — revise os erros acima.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
