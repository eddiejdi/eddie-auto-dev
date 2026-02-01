#!/usr/bin/env python3
"""Teste de validação do BPM Agent - IDs únicos"""

import re
import sys
import pytest

sys.path.insert(0, "/home/eddie/myClaude")


def test_bpm_unique_ids():
    """Testa que os IDs gerados pelo BPM Agent são únicos."""
    # Reset singleton
    import specialized_agents.bpm_agent as bpm_mod

    bpm_mod._bpm_agent_instance = None

    from specialized_agents.bpm_agent import get_bpm_agent

    agent = get_bpm_agent()
    path = agent.create_from_template("approval_flow", "Teste_Validacao")
    print(f"Gerado: {path}")

    # Verificar IDs
    with open(path) as f:
        content = f.read()

    # Contar IDs
    ids = re.findall(r'mxCell id="([0-9]+)"', content)
    print(f"IDs encontrados: {ids}")
    print(f"IDs únicos: {len(set(ids))} de {len(ids)}")

    assert len(ids) == len(
        set(ids)
    ), f"IDs duplicados encontrados: {[x for x in ids if ids.count(x) > 1]}"
    print("✅ SEM IDs DUPLICADOS!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
