"""Helpers para detectar se há um runner self-hosted disponível na repo

Função principal `has_matching_runner(runners_json, required_labels)` pode ser testada isoladamente.
"""
from typing import Dict, List


def has_matching_runner(runners_json: Dict, required_labels: List[str]) -> bool:
    """Retorna True se algum runner na resposta tiver pelo menos uma das labels requisitadas.

    runners_json expected format: {"runners": [{"id":.., "name":..., "labels": [{"name": "self-hosted"}, ...]}, ...]}
    """
    runners = runners_json.get("runners", []) if isinstance(runners_json, dict) else []

    for r in runners:
        labels = [l.get("name") for l in r.get("labels", []) if isinstance(l, dict)]
        for req in required_labels:
            if req in labels:
                return True
    return False


if __name__ == "__main__":
    import json, sys

    if len(sys.argv) < 2:
        print("Usage: check_selfhost.py <runners_json_file> [label1,label2]")
        sys.exit(2)

    with open(sys.argv[1], "r") as f:
        data = json.load(f)

    labels = sys.argv[2].split(",") if len(sys.argv) > 2 else ["self-hosted", "homelab"]
    ok = has_matching_runner(data, labels)
    print("FOUND" if ok else "NOTFOUND")
    sys.exit(0 if ok else 1)
