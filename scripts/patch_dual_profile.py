#!/usr/bin/env python3
"""
Patch: Adiciona suporte a dual-profile (conservative/aggressive) no trading agent.

Aplica as seguintes modificações:
1. trading_agent.py: campo profile no AgentState, profile no __init__, profile na main()
2. training_db.py: coluna profile no INSERT de trades
3. prometheus_exporter.py: label profile nas métricas
4. market_rag.py: campo ai_conservative_pct no RAGAdjustment

Uso:
  python3 scripts/patch_dual_profile.py [--dry-run]
"""

import re
import sys
from pathlib import Path

AGENT_DIR = Path("/apps/crypto-trader/trading/btc_trading_agent")
DRY_RUN = "--dry-run" in sys.argv


def patch_file(filepath: Path, patches: list[tuple[str, str]]) -> bool:
    """Aplica patches (old, new) em um arquivo."""
    content = filepath.read_text()
    original = content

    for old, new in patches:
        if old not in content:
            print(f"  ❌ Padrão não encontrado em {filepath.name}:")
            print(f"     {old[:80]}...")
            return False
        content = content.replace(old, new, 1)

    if content != original:
        if DRY_RUN:
            print(f"  🔍 [DRY] {filepath.name}: {len(patches)} patches")
        else:
            filepath.write_text(content)
            print(f"  ✅ {filepath.name}: {len(patches)} patches aplicados")
    return True


def patch_trading_agent() -> bool:
    """Patcha trading_agent.py com suporte a profile."""
    f = AGENT_DIR / "trading_agent.py"

    patches = []

    # 1. Adicionar PROFILE constante após MAX_POSITIONS
    patches.append((
        "MAX_POSITIONS = _config.get(\"max_positions\", 3)  # max BUY entries acumuladas\n",
        "MAX_POSITIONS = _config.get(\"max_positions\", 3)  # max BUY entries acumuladas\n"
        "PROFILE = _config.get(\"profile\", \"default\")  # conservative|aggressive|default\n",
    ))

    # 2. Adicionar campo profile no AgentState
    patches.append((
        "    daily_date: str = ''  # Data do dia para reset\n",
        "    daily_date: str = ''  # Data do dia para reset\n"
        "    profile: str = 'default'  # Perfil de risco: conservative|aggressive\n",
    ))

    # 3. No __init__ do BitcoinTradingAgent, setar profile
    patches.append((
        "        self.state = AgentState(symbol=symbol, dry_run=dry_run)\n",
        "        self.state = AgentState(symbol=symbol, dry_run=dry_run, profile=PROFILE)\n",
    ))

    # 4. No record_trade de BUY, adicionar metadata com profile
    patches.append((
        "                    trade_id = self.db.record_trade(\n"
        "                        symbol=self.symbol,\n"
        "                        side=\"buy\",\n"
        "                        price=price,\n"
        "                        size=size,\n"
        "                        funds=amount_usdt,\n"
        "                        dry_run=self.state.dry_run\n"
        "                    )\n",
        "                    trade_id = self.db.record_trade(\n"
        "                        symbol=self.symbol,\n"
        "                        side=\"buy\",\n"
        "                        price=price,\n"
        "                        size=size,\n"
        "                        funds=amount_usdt,\n"
        "                        dry_run=self.state.dry_run,\n"
        "                        profile=self.state.profile\n"
        "                    )\n",
    ))

    # 5. No record_trade de SELL — precisamos localizar o bloco SELL
    # Vamos procurar pelo padrão do bloco SELL record_trade
    patches.append((
        "                    trade_id = self.db.record_trade(\n"
        "                        symbol=self.symbol,\n"
        "                        side=\"sell\",\n"
        "                        price=price,\n"
        "                        size=size,\n"
        "                        funds=round(price * size, 2),  # FIX #9: Record sell funds\n"
        "                        dry_run=self.state.dry_run\n"
        "                    )\n",
        "                    trade_id = self.db.record_trade(\n"
        "                        symbol=self.symbol,\n"
        "                        side=\"sell\",\n"
        "                        price=price,\n"
        "                        size=size,\n"
        "                        funds=round(price * size, 2),  # FIX #9: Record sell funds\n"
        "                        dry_run=self.state.dry_run,\n"
        "                        profile=self.state.profile\n"
        "                    )\n",
    ))

    # 6. No banner de startup, adicionar profile
    patches.append((
        '    print(f"Symbol: {args.symbol}")\n'
        '    print(f"Mode: {\'🔴 LIVE TRADING\' if not dry_run else \'🟢 DRY RUN\'}")\n',
        '    print(f"Symbol: {args.symbol}")\n'
        '    print(f"Profile: {_loaded_cfg.get(\'profile\', \'default\')}")\n'
        '    print(f"Mode: {\'🔴 LIVE TRADING\' if not dry_run else \'🟢 DRY RUN\'}")\n',
    ))

    # 7. Adicionar allocated_balance na _calculate_trade_size
    # Antes de calcular, ler alocação do DB
    patches.append((
        "    def _calculate_trade_size(self, signal: Signal, price: float, force: bool = False) -> float:\n"
        '        """Calcula tamanho do trade.\n'
        "\n"
        "        Args:\n"
        "            signal: Sinal de trading (BUY/SELL)\n"
        "            price: Preço atual\n"
        "            force: Se True, bypass fee-check (usado por auto-exit SL/TP)\n"
        '        """\n'
        "        if signal.action == \"BUY\":\n"
        "            usdt_balance = get_balance(\"USDT\") if not self.state.dry_run else 1000\n",
        "    def _calculate_trade_size(self, signal: Signal, price: float, force: bool = False) -> float:\n"
        '        """Calcula tamanho do trade.\n'
        "\n"
        "        Args:\n"
        "            signal: Sinal de trading (BUY/SELL)\n"
        "            price: Preço atual\n"
        "            force: Se True, bypass fee-check (usado por auto-exit SL/TP)\n"
        '        """\n'
        "        if signal.action == \"BUY\":\n"
        "            usdt_balance = get_balance(\"USDT\") if not self.state.dry_run else 1000\n"
        "            # ── Profile Allocation: aplicar % do saldo alocado ao perfil ──\n"
        "            usdt_balance = self._apply_profile_allocation(usdt_balance)\n",
    ))

    return patch_file(f, patches)


def patch_training_db() -> bool:
    """Patcha training_db.py para incluir coluna profile no INSERT."""
    f = AGENT_DIR / "training_db.py"

    patches = []

    # 1. Atualizar método record_trade para aceitar profile
    patches.append((
        "    def record_trade(self, symbol: str, side: str, price: float,\n"
        "                     size: float = None, funds: float = None,\n"
        "                     order_id: str = None, dry_run: bool = False,\n"
        "                     metadata: Dict = None) -> int:\n",
        "    def record_trade(self, symbol: str, side: str, price: float,\n"
        "                     size: float = None, funds: float = None,\n"
        "                     order_id: str = None, dry_run: bool = False,\n"
        "                     metadata: Dict = None, profile: str = 'default') -> int:\n",
    ))

    # 2. Atualizar INSERT para incluir profile
    patches.append((
        '            cur.execute(f"""\n'
        f"                INSERT INTO {{SCHEMA}}.trades\n"
        "                    (timestamp, symbol, side, price, size, funds,\n"
        "                     order_id, dry_run, metadata)\n"
        "                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)\n"
        "                RETURNING id\n"
        '            """, (\n'
        "                time.time(), symbol, side, price, size, funds,\n"
        "                order_id, dry_run,\n"
        "                json.dumps(metadata) if metadata else None\n"
        "            ))\n",
        '            cur.execute(f"""\n'
        f"                INSERT INTO {{SCHEMA}}.trades\n"
        "                    (timestamp, symbol, side, price, size, funds,\n"
        "                     order_id, dry_run, metadata, profile)\n"
        "                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)\n"
        "                RETURNING id\n"
        '            """, (\n'
        "                time.time(), symbol, side, price, size, funds,\n"
        "                order_id, dry_run,\n"
        "                json.dumps(metadata) if metadata else None,\n"
        "                profile\n"
        "            ))\n",
    ))

    return patch_file(f, patches)


def patch_market_rag() -> bool:
    """Patcha market_rag.py para incluir campo ai_conservative_pct."""
    f = AGENT_DIR / "market_rag.py"

    patches = []

    # 1. Adicionar campo ai_conservative_pct no RAGAdjustment
    patches.append((
        "    ai_position_size_reason: str = \"\"     # Razão textual do cálculo\n",
        "    ai_position_size_reason: str = \"\"     # Razão textual do cálculo\n"
        "\n"
        "    # ── AI Profile Allocation (split conservador/arrojado) ──\n"
        "    ai_conservative_pct: float = 0.5       # % do saldo para perfil conservador (0.0-1.0)\n",
    ))

    # 2. Adicionar no to_dict()
    patches.append((
        '            "ai_position_size_reason": self.ai_position_size_reason,\n',
        '            "ai_position_size_reason": self.ai_position_size_reason,\n'
        '            "ai_conservative_pct": round(self.ai_conservative_pct, 3),\n',
    ))

    return patch_file(f, patches)


def patch_prometheus_exporter() -> bool:
    """Patcha prometheus_exporter.py para incluir label profile nas métricas."""
    f = AGENT_DIR / "prometheus_exporter.py"

    patches = []

    # 1. Adicionar profile label ao lado do coin label
    patches.append((
        "            _cl = f'coin=\"{_sym}\"'  # coin label reutilizável\n",
        "            _profile = cfg.get('profile', 'default')\n"
        "            _cl = f'coin=\"{_sym}\",profile=\"{_profile}\"'  # coin+profile labels\n",
    ))

    return patch_file(f, patches)


def add_profile_allocation_method() -> bool:
    """Adiciona método _apply_profile_allocation ao BitcoinTradingAgent."""
    f = AGENT_DIR / "trading_agent.py"
    content = f.read_text()

    # Verificar se já existe
    if "_apply_profile_allocation" in content and "def _apply_profile_allocation" in content:
        print("  ⏭️ _apply_profile_allocation já existe")
        return True

    # Inserir o método antes de _calculate_trade_size
    method = '''
    def _apply_profile_allocation(self, total_balance: float) -> float:
        """Aplica alocação de saldo baseada no perfil.

        Lê a última alocação da tabela btc.profile_allocations.
        Retorna o saldo alocado para o perfil deste agente.
        """
        profile = self.state.profile
        if profile == "default":
            return total_balance

        try:
            with self.db._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT conservative_pct, aggressive_pct
                    FROM btc.profile_allocations
                    WHERE symbol = %s
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (self.symbol,))
                row = cur.fetchone()
                if row:
                    cons_pct, aggr_pct = row
                    my_pct = cons_pct if profile == "conservative" else aggr_pct
                    allocated = total_balance * my_pct
                    logger.debug(
                        f"💰 Profile allocation: {profile} gets "
                        f"{my_pct*100:.0f}% of ${total_balance:.2f} = ${allocated:.2f}"
                    )
                    return allocated
        except Exception as e:
            logger.warning(f"⚠️ Profile allocation lookup failed: {e}")

        # Fallback: split 50/50
        return total_balance * 0.5

'''
    # Inserir antes de _calculate_trade_size
    target = "    def _calculate_trade_size(self, signal: Signal, price: float, force: bool = False) -> float:\n"
    if target in content:
        content = content.replace(target, method + target)
        if DRY_RUN:
            print("  🔍 [DRY] Método _apply_profile_allocation")
        else:
            f.write_text(content)
            print("  ✅ Método _apply_profile_allocation adicionado")
        return True
    else:
        print("  ❌ _calculate_trade_size não encontrado para inserir allocation method")
        return False


def main() -> None:
    """Aplica todos os patches."""
    print("🔧 Dual-Profile Patch" + (" [DRY RUN]" if DRY_RUN else ""))
    print(f"📁 Agent dir: {AGENT_DIR}")
    print()

    results = []

    print("1️⃣ trading_agent.py (constantes, state, record_trade, banner):")
    results.append(patch_trading_agent())

    print("\n2️⃣ trading_agent.py (método _apply_profile_allocation):")
    results.append(add_profile_allocation_method())

    print("\n3️⃣ training_db.py (INSERT com profile):")
    results.append(patch_training_db())

    print("\n4️⃣ market_rag.py (RAGAdjustment ai_conservative_pct):")
    results.append(patch_market_rag())

    print("\n5️⃣ prometheus_exporter.py (label profile):")
    results.append(patch_prometheus_exporter())

    print()
    if all(results):
        print("🎉 Todos os patches aplicados com sucesso!")
    else:
        failed = sum(1 for r in results if not r)
        print(f"⚠️ {failed} patch(es) falharam")
        sys.exit(1)


if __name__ == "__main__":
    main()
