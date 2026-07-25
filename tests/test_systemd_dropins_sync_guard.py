"""Impede que uma sincronização de drop-ins systemd derrube produção.

Auditoria de 2026-07-25 comparou os drop-ins versionados com
/etc/systemd/system/ no homelab. O repo diverge do host nas DUAS direções:

  - `crypto-agent@.service.d/common.conf` (vale para os 14 agentes) tem
    TELEGRAM_BOT_TOKEN, SECRETS_AGENT_API_KEY e ADMIN_CHAT_ID como PLACEHOLDER,
    e aponta OLLAMA_*_HOST para as GPUs diretas (:11434/:11435) enquanto
    produção usa o coordinator (:11437). Empurrar esse arquivo derruba a frota.
  - `ollama-gpu-coordinator.service.d/zz-dual-gpu-routing.conf` estava ATRÁS de
    produção (faltavam OLLAMA_NAS_HOST e GPU_COORD_POLL_INTERVAL_SEC).

Por isso a sincronização é opt-in por arquivo, via
deploy/systemd-dropins-sync.allowlist. Estes testes protegem essa lista.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ALLOWLIST = RAIZ / "deploy" / "systemd-dropins-sync.allowlist"

# Chaves cujo valor real é segredo — o host é a fonte de verdade, nunca o git.
CREDENCIAL = re.compile(r"(TOKEN|_KEY|SECRET|PASSWORD|PASSWD|CHAT_ID)", re.IGNORECASE)
# Valores de exemplo que, se sincronizados, viram configuração literal quebrada.
PLACEHOLDER = re.compile(r"<[^>]+>|your_|changeme|replace_me|change_me", re.IGNORECASE)


def _entradas() -> list[str]:
    linhas = ALLOWLIST.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in linhas if ln.strip() and not ln.lstrip().startswith("#")]


def _ambientes(conf: Path) -> list[tuple[str, str]]:
    """Pares (chave, valor) de linhas Environment=, ignorando comentários."""
    pares = []
    for linha in conf.read_text(encoding="utf-8").splitlines():
        if linha.lstrip().startswith("#"):
            continue
        match = re.match(r"\s*Environment=([^=]+)=(.*)$", linha)
        if match:
            pares.append((match.group(1), match.group(2)))
    return pares


@pytest.fixture(scope="module")
def entradas() -> list[str]:
    lista = _entradas()
    assert lista, "allowlist vazia — sem isso a sincronização não tem entrada segura"
    return lista


def test_allowlist_so_lista_arquivos_existentes(entradas: list[str]) -> None:
    faltando = [e for e in entradas if not (RAIZ / e).is_file()]
    assert not faltando, f"allowlist aponta para arquivo inexistente: {faltando}"


def test_allowlist_nao_tem_duplicatas(entradas: list[str]) -> None:
    vistos, duplicados = set(), []
    for e in entradas:
        (duplicados.append(e) if e in vistos else vistos.add(e))
    assert not duplicados, f"entradas duplicadas na allowlist: {duplicados}"


def test_arquivo_sincronizavel_nao_carrega_credencial(entradas: list[str]) -> None:
    """Nada com token/chave/segredo pode ser empurrado do git para o host."""
    ofensores = [
        f"{e} → {chave}"
        for e in entradas
        for chave, _ in _ambientes(RAIZ / e)
        if CREDENCIAL.search(chave)
    ]
    assert not ofensores, (
        "arquivo na allowlist declara credencial — o valor real vive no host, "
        "não no git:\n  " + "\n  ".join(ofensores)
    )


def test_arquivo_sincronizavel_nao_tem_placeholder(entradas: list[str]) -> None:
    """Placeholder sincronizado vira configuração literal quebrada em produção."""
    ofensores = [
        f"{e} → {chave}={valor}"
        for e in entradas
        for chave, valor in _ambientes(RAIZ / e)
        if PLACEHOLDER.search(valor)
    ]
    assert not ofensores, (
        "arquivo na allowlist tem valor de exemplo; sincronizar gravaria isso "
        "literalmente no host:\n  " + "\n  ".join(ofensores)
    )


def test_conf_com_credencial_ou_placeholder_fica_fora(entradas: list[str]) -> None:
    """Rede de segurança: quem tem segredo/exemplo não pode ser listado.

    Complementa os testes acima olhando do outro lado — varre TODOS os drop-ins
    e confirma que os perigosos não entraram na lista. Pega o caso de alguém
    adicionar credencial a um arquivo que já estava allowlisted.
    """
    perigosos = set()
    for conf in (RAIZ / "systemd").rglob("*.conf"):
        for chave, valor in _ambientes(conf):
            if CREDENCIAL.search(chave) or PLACEHOLDER.search(valor):
                perigosos.add(str(conf.relative_to(RAIZ)))
                break

    listados_e_perigosos = sorted(perigosos.intersection(entradas))
    assert not listados_e_perigosos, (
        "drop-in com credencial ou placeholder está na allowlist de "
        f"sincronização: {listados_e_perigosos}"
    )


def test_common_conf_nunca_e_sincronizavel(entradas: list[str]) -> None:
    """common.conf vale para os 14 agentes e no git é template — nunca sincronizar.

    Guarda nomeada porque este é o arquivo cujo empurrão causaria o dano maior:
    os agentes perderiam o coordinator (:11437 → :11434/:11435) e os alertas do
    Telegram parariam (token e chat_id virariam string de exemplo).
    """
    assert "systemd/crypto-agent@.service.d/common.conf" not in entradas, (
        "common.conf entrou na allowlist. Ele é template no git e configura os "
        "14 agentes; sincronizar derruba a frota. O host é a fonte de verdade."
    )
