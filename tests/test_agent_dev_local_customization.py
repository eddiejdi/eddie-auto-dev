from __future__ import annotations

from pathlib import Path
import unittest


AGENT_FILE = Path(__file__).resolve().parents[1] / ".github" / "agents" / "agent_dev_local.agent.md"


class TestAgentDevLocalCustomization(unittest.TestCase):
    """Garante guardrails centrais de contexto e desempenho no agente principal."""

    def test_preloaded_knowledge_section_is_present(self) -> None:
        """Deve manter um bloco explicito de pacotes de conhecimento pre-carregado."""
        content = AGENT_FILE.read_text(encoding="utf-8")

        self.assertIn("PACOTES DE CONHECIMENTO PRE-CARREGADO", content)
        self.assertIn("1 pacote primario", content)
        self.assertIn("Agentes/Customizacao", content)

    def test_context_budget_rules_are_present(self) -> None:
        """Deve manter regras explicitas para economia de contexto e latencia."""
        content = AGENT_FILE.read_text(encoding="utf-8")

        self.assertIn("ORCAMENTO DE CONTEXTO E DESEMPENHO", content)
        self.assertIn("1 busca ampla", content)
        self.assertIn("3 arquivos profundos", content)

    def test_handoff_contract_is_present(self) -> None:
        """Deve orientar delegacao curta, verificavel e com validacao definida."""
        content = AGENT_FILE.read_text(encoding="utf-8")

        self.assertIn("Contrato de handoff para agentes especializados", content)
        self.assertIn("validacao esperada", content)
        self.assertIn("logs integrais", content)


if __name__ == "__main__":
    unittest.main()