#!/usr/bin/env python3
"""
Patch para adicionar fontes de notícias e citações ao relatório Ollama.
Modifica _generate_ai_plan() no trading_agent.py para:
  1. Buscar artigos recentes do btc.news_sentiment
  2. Incluir notícias no prompt do Ollama
  3. Anexar bloco de citações ao plan_text final
"""

import sys
from pathlib import Path

AGENT_PATH = Path("/home/homelab/myClaude/btc_trading_agent/trading_agent.py")


def read_file(path: Path) -> str:
    """Lê conteúdo do arquivo."""
    return path.read_text()


def write_file(path: Path, content: str) -> None:
    """Escreve conteúdo no arquivo com backup."""
    backup = path.with_suffix('.py.bak_citations')
    if not backup.exists():
        import shutil
        shutil.copy2(path, backup)
    path.write_text(content)


def apply_patch() -> int:
    """Aplica patches de citações de notícias no trading_agent.py."""
    code = read_file(AGENT_PATH)
    original = code
    patches: list[str] = []

    # ========== PATCH A: Buscar artigos recentes ANTES do prompt ==========
    # Inserir após o cálculo de current_net_pnl (antes de montar o prompt)
    old_before_prompt = """            else:
                sell_unlock_price = 0
                current_net_pnl = 0

            prompt = (
                f"Você é um analista de trading de BTC. Analise o estado atual e gere um "
                f"resumo dos PRÓXIMOS PASSOS da estratégia em português do Brasil.\\n\\n"
                f"DADOS ATUAIS:\\n\""""

    new_before_prompt = """            else:
                sell_unlock_price = 0
                current_net_pnl = 0

            # ── Buscar notícias recentes para contexto e citações ──
            news_articles = []
            news_prompt_block = ""
            try:
                with self.db._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute(\"\"\"
                        SELECT source, title, sentiment::float, confidence::float,
                               category, url, coin
                        FROM btc.news_sentiment
                        WHERE coin IN ('BTC', 'GENERAL')
                          AND timestamp > NOW() - INTERVAL '4 hours'
                          AND confidence >= 0.5
                        ORDER BY timestamp DESC
                        LIMIT 10
                    \"\"\")
                    news_articles = [
                        {
                            "source": r[0], "title": r[1], "sentiment": r[2],
                            "confidence": r[3], "category": r[4], "url": r[5],
                            "coin": r[6],
                        }
                        for r in cur.fetchall()
                    ]
                    cur.close()
            except Exception as e:
                logger.debug(f"📰 News fetch for plan: {e}")

            if news_articles:
                # Score agregado
                avg_sent = sum(a["sentiment"] for a in news_articles) / len(news_articles)
                sent_label = "BULLISH" if avg_sent > 0.1 else "BEARISH" if avg_sent < -0.1 else "NEUTRO"
                lines = [f"\\nNOTÍCIAS RECENTES (sentimento geral: {sent_label}, score={avg_sent:+.2f}):"]
                for i, art in enumerate(news_articles[:8], 1):
                    s = "🟢" if art["sentiment"] > 0.1 else "🔴" if art["sentiment"] < -0.1 else "⚪"
                    lines.append(
                        f"  {i}. [{art['source']}] {s} {art['title']} "
                        f"(sent={art['sentiment']:+.2f}, cat={art['category']})"
                    )
                lines.append(
                    "Considere essas notícias na sua análise e mencione as mais relevantes."
                )
                news_prompt_block = "\\n".join(lines) + "\\n\\n"

            prompt = (
                f"Você é um analista de trading de BTC. Analise o estado atual e gere um "
                f"resumo dos PRÓXIMOS PASSOS da estratégia em português do Brasil.\\n\\n"
                f"DADOS ATUAIS:\\n\""""

    if old_before_prompt in code:
        code = code.replace(old_before_prompt, new_before_prompt, 1)
        patches.append("PA: Busca artigos recentes para contexto")
    elif "news_articles = []" in code and "news_prompt_block" in code:
        patches.append("PA: SKIP (already applied)")
    else:
        print("⚠️ PA: Before-prompt block not found!")

    # ========== PATCH B: Inserir news_prompt_block no prompt ==========
    old_prompt_end = (
        'f"- Win rate: {self.state.winning_trades}/{self.state.total_trades} trades\\n\\n"\n'
        '                f"CONDIÇÕES DE VENDA (resumo atual):\\n"'
    )

    new_prompt_end = (
        'f"- Win rate: {self.state.winning_trades}/{self.state.total_trades} trades\\n\\n"\n'
        '                f"{news_prompt_block}"\n'
        '                f"CONDIÇÕES DE VENDA (resumo atual):\\n"'
    )

    if old_prompt_end in code:
        code = code.replace(old_prompt_end, new_prompt_end, 1)
        patches.append("PB: Inseriu bloco de notícias no prompt")
    elif 'f"{news_prompt_block}"' in code:
        patches.append("PB: SKIP (already applied)")
    else:
        print("⚠️ PB: Prompt win-rate → sell block not found!")

    # ========== PATCH C: Adicionar instrução para citar fontes ==========
    old_instructions = (
        'f"4. Riscos e oportunidades identificados\\n"\n'
        '                f"Seja direto e objetivo. Não use markdown headers."'
    )

    new_instructions = (
        'f"4. Riscos e oportunidades identificados\\n"\n'
        '                f"5. Cite as fontes de notícias que mais impactam a análise (ex: [CoinDesk], [CoinTelegraph])\\n"\n'
        '                f"Seja direto e objetivo. Não use markdown headers."'
    )

    if old_instructions in code:
        code = code.replace(old_instructions, new_instructions, 1)
        patches.append("PC: Adicionou instrução para citar fontes")
    elif "Cite as fontes" in code:
        patches.append("PC: SKIP (already applied)")
    else:
        print("⚠️ PC: Instructions block not found!")

    # ========== PATCH D: Anexar bloco de citações ao plan_text ==========
    old_sell_append = '            plan_text += "\\n" + "\\n".join(sell_summary_lines)\n\n            self._save_ai_plan('

    new_sell_append = '''            plan_text += "\\n" + "\\n".join(sell_summary_lines)

            # ── Anexar bloco de fontes/citações ──
            if news_articles:
                cite_lines = [
                    "",
                    "━━━ FONTES DE NOTÍCIAS ━━━",
                ]
                for i, art in enumerate(news_articles[:8], 1):
                    s_icon = "🟢" if art["sentiment"] > 0.1 else "🔴" if art["sentiment"] < -0.1 else "⚪"
                    cite_lines.append(
                        f"  {i}. {s_icon} [{art['source'].upper()}] {art['title']}"
                    )
                    cite_lines.append(
                        f"     Sentimento: {art['sentiment']:+.2f} | "
                        f"Confiança: {art['confidence']:.0%} | "
                        f"Categoria: {art['category']}"
                    )
                    if art.get("url"):
                        cite_lines.append(f"     🔗 {art['url']}")
                avg_s = sum(a["sentiment"] for a in news_articles) / len(news_articles)
                cite_lines.append(
                    f"\\n📊 Sentimento agregado: {avg_s:+.2f} "
                    f"({len(news_articles)} artigos analisados via eddie-sentiment)"
                )
                plan_text += "\\n" + "\\n".join(cite_lines)

            self._save_ai_plan('''

    if old_sell_append in code:
        code = code.replace(old_sell_append, new_sell_append, 1)
        patches.append("PD: Anexou bloco de citações ao plan_text")
    elif "━━━ FONTES DE NOTÍCIAS ━━━" in code:
        patches.append("PD: SKIP (already applied)")
    else:
        print("⚠️ PD: Sell-append block not found!")

    # ========== Aplicar ==========
    if code != original:
        write_file(AGENT_PATH, code)
        print(f"\n✅ trading_agent.py: {len(patches)} patches applied:")
        for p in patches:
            print(f"  ✔ {p}")
    else:
        print("⚠️ trading_agent.py: No changes made!")
        for p in patches:
            print(f"  ℹ {p}")

    return len(patches)


if __name__ == "__main__":
    print("=" * 60)
    print("📰 NEWS CITATIONS PATCH: Análise Ollama com Fontes")
    print("=" * 60)

    total = apply_patch()

    print(f"\n{'=' * 60}")
    print(f"📊 Total: {total} patches processed")
    print("=" * 60)

    # Validation
    print("\n🔍 Syntax validation...")
    import subprocess
    result = subprocess.run(
        ["python3", "-c",
         f"import ast; ast.parse(open('{AGENT_PATH}').read()); print('  ✅ trading_agent.py: OK')"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"  ❌ trading_agent.py: SYNTAX ERROR")
        print(result.stderr)
        sys.exit(1)
