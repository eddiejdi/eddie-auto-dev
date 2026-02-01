#!/usr/bin/env python3
"""Mock AGENTS_API para testes locais.
Exponha endpoint POST /agent/fix que retorna uma sugestão baseada no erro.
"""

from flask import Flask, request, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


@app.route("/agent/fix", methods=["POST"])
def fix():
    data = request.json or {}
    errors = data.get("errors", [])
    context = data.get("context", "")

    # Simples heurística: se erro mencionar pytest, sugerir instalar pytest
    suggestion = None
    joined = "\n".join(errors).lower()
    if (
        "pytest" in joined
        or "no module named" in joined
        or "module not found" in joined
    ):
        suggestion = "Instale dependências faltantes: `pip install pytest` e reexecute os testes."
    elif "permission denied" in joined:
        suggestion = (
            "Verifique permissões e execute com usuário correto ou corrija owner/perms."
        )
    elif "docker" in joined:
        suggestion = (
            "Verifique se o Docker está instalado e o usuário pertence ao grupo docker."
        )
    else:
        suggestion = "Analise o log e aplique correções locais; exemplo: revisar traceback e dependências."

    response = {"success": True, "suggestion": suggestion, "source": "mock_agents_api"}

    app.logger.info("agent/fix called; returning suggestion")
    return jsonify(response)


if __name__ == "__main__":
    print("Mock AGENTS_API running on http://127.0.0.1:5200")
    app.run(host="127.0.0.1", port=5200)
