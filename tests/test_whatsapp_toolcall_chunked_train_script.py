"""Regression checks for the hourly QLoRA chunk-training script.

O coordenador (ollama-gpu-coordinator.service) NUNCA pode ser parado por
esse job. Ele não retém VRAM da 3060 (é só um proxy HTTP) e ficando no ar
detecta o GPU0 indisponível sozinho, roteando trading-analyst pra NAS
(:11436) automaticamente — os 14 crypto-agent@* continuam com IA durante o
pacote de treino inteiro. Derrubar o coordenador tira TODO caminho pra IA
dos agentes, não só o GPU0; é o problema em si, não uma consequência
aceitável do treino.
"""

from __future__ import annotations

from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "whatsapp_toolcall_chunked_train.sh"
)


def _load_script() -> str:
    return SCRIPT_PATH.read_text(encoding="utf-8")


def test_script_never_stops_the_gpu_coordinator() -> None:
    content = _load_script()
    assert "systemctl stop ollama-gpu-coordinator.service" not in content
    assert "systemctl start ollama-gpu-coordinator.service" not in content


def test_script_still_pauses_ollama_service_and_selfheal() -> None:
    """A pausa continua existindo — só não inclui mais o coordenador.

    ollama.service (GPU0) precisa parar de verdade pra liberar VRAM pro
    treino. ollama-gpu-selfheal precisa ser pausado junto porque ELE
    monitora ollama.service diretamente e o religaria sem saber que a
    pausa é intencional (ver OLLAMA_PULLERS no script).
    """
    content = _load_script()
    assert "systemctl stop ollama.service" in content
    assert "systemctl start ollama.service" in content
    assert "ollama-gpu-selfheal.service" in content
    assert "OLLAMA_PULLERS=(eddie-calendar.service llm-optimizer.service ollama-gpu-selfheal.service)" in content


def test_script_alerts_if_coordinator_ever_found_down() -> None:
    """Se o coordenador cair por conta própria (nunca por este script), alerta.

    Isso só pode acontecer por crash/OOM/bug — nunca pela pausa em si — e é
    o alerta mais sério possível: todos os agentes ficam sem IA, não só o
    GPU0.
    """
    content = _load_script()
    assert '"$st_coord" != "active"' in content
    assert "ollama-gpu-coordinator caiu" in content
