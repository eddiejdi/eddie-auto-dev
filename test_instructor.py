#!/usr/bin/env python3
"""Teste do Instructor Agent"""

import sys

sys.path.insert(0, "/home/homelab/myClaude")

try:
    from specialized_agents.instructor_agent import get_instructor

    print("✅ Importação OK")

    instructor = get_instructor()
    print(f"✅ Instructor criado: {instructor}")
    print(f"   - Ativo: {instructor.is_running}")
    print(f"   - Linguagens: {list(instructor.knowledge_sources.keys())}")

except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback

    traceback.print_exc()
