#!/usr/bin/env python3
"""Seleciona o servidor ProtonVPN mais rápido e troca só o [Peer] do túnel.

O túnel do homelab é um wg-quick estático cuja config carrega ~40 regras PostUp
(tabela 205, fwmark 0xca6c, rotas da LAN, bridges Docker, exceções de edge
Cloudflare por UID, macvlan Storj, kill-switch). Derrubar o túnel para trocar de
servidor destruiria tudo isso — e o homelab é o gateway da LAN.

Por isso a troca é feita com `wg syncconf`, que atualiza o peer no kernel **sem**
disparar PostDown/PostUp. Nenhuma regra de roteamento é tocada.

Fluxo:
1. Mede RTT/perda de cada candidato (ICMP no endpoint).
2. Pontua (RTT penalizado por perda) e escolhe o melhor.
3. Só troca se o ganho passar da histerese E o dwell mínimo tiver vencido —
   evita ficar alternando a cada execução.
4. Aplica via syncconf, confirma handshake e faz rollback se o peer novo não
   fechar handshake dentro do prazo.

Dry-run é o padrão. Para aplicar de fato é preciso --apply.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("protonvpn-best-server")

IFACE = os.environ.get("PVPN_IFACE", "protonvpn")
CONF = Path(os.environ.get("PVPN_CONF", "/etc/wireguard/protonvpn.conf"))
CANDIDATES = Path(
    os.environ.get("PVPN_CANDIDATES", "/etc/protonvpn-best-server.json")
)
STATE = Path(os.environ.get("PVPN_STATE", "/var/lib/protonvpn-best-server/state.json"))
METRICS = Path(
    os.environ.get(
        "PVPN_METRICS", "/var/lib/prometheus/node-exporter/protonvpn_best_server.prom"
    )
)

# Só troca se o candidato for pelo menos X% melhor que o atual. Sem isso, dois
# servidores empatados dentro do ruído de medição ficariam se revezando.
MIN_GAIN_PCT = float(os.environ.get("PVPN_MIN_GAIN_PCT", "20"))
# E nunca troca antes disso, mesmo que o ganho seja grande — o pedido é que a
# alternância seja de 1h, então o timer horário é o piso e este é o teto.
MIN_DWELL_SEC = int(os.environ.get("PVPN_MIN_DWELL_SEC", "3600"))
PING_COUNT = int(os.environ.get("PVPN_PING_COUNT", "10"))
# A medição PRECISA sair por fora do túnel. Todo o tráfego do homelab cai na
# tabela 205 (regra 32764 = "not fwmark 0xca6c"), então um ping normal mediria
# "RTT via servidor atual até o candidato" — inflado pelo RTT do túnel e
# praticamente igual para todos, tornando a escolha aleatória. Marcando com
# 0xca6c (51820, a mesma marca que o WireGuard usa para evitar loop de
# roteamento) o pacote escapa da 205 e vai direto pela eth-wan.
# Medido no homelab 2026-07-28: 1.1.1.1 dá 206ms sem a marca e 7ms com ela.
PING_FWMARK = int(os.environ.get("PVPN_PING_FWMARK", "51820"))
HANDSHAKE_TIMEOUT_SEC = int(os.environ.get("PVPN_HANDSHAKE_TIMEOUT_SEC", "25"))
# Perda vira penalidade de RTT: 1% de perda ~ +8ms. Um servidor com 5% de perda
# e 40ms perde para um com 0% e 70ms — perda trava vídeo, latência só atrasa.
LOSS_PENALTY_MS = float(os.environ.get("PVPN_LOSS_PENALTY_MS", "8"))
UNREACHABLE_SCORE = 10_000.0


@dataclass
class Candidate:
    name: str
    country: str
    public_key: str
    endpoint: str  # host:porta

    @property
    def host(self) -> str:
        return self.endpoint.rsplit(":", 1)[0]


@dataclass
class Measurement:
    name: str
    country: str
    endpoint: str
    rtt_ms: float | None
    loss_pct: float
    score: float
    reachable: bool


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def load_candidates() -> list[Candidate]:
    if not CANDIDATES.exists():
        log.error(
            "Arquivo de candidatos ausente: %s — veja o exemplo em "
            "docs/PROTONVPN_BEST_SERVER.md",
            CANDIDATES,
        )
        return []
    raw = json.loads(CANDIDATES.read_text())
    servers = raw.get("servers", raw if isinstance(raw, list) else [])
    out: list[Candidate] = []
    for item in servers:
        try:
            cand = Candidate(
                name=item["name"],
                country=item.get("country", "??"),
                public_key=item["public_key"],
                endpoint=item["endpoint"],
            )
        except KeyError as exc:
            log.warning("Candidato ignorado (campo %s ausente): %r", exc, item)
            continue
        if ":" not in cand.endpoint:
            log.warning("Endpoint sem porta, ignorado: %s", cand.endpoint)
            continue
        out.append(cand)
    return out


def resolve(host: str) -> str | None:
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    try:
        return socket.gethostbyname(host)
    except OSError:
        return None


def measure(cand: Candidate, count: int = PING_COUNT) -> Measurement:
    """Mede RTT e perda até o endpoint do servidor.

    Os endpoints WireGuard da Proton respondem a ICMP. Se um servidor não
    responder, ele é considerado inalcançável em vez de "rápido" — sem isso, um
    servidor mudo ganharia por ausência de dados.
    """
    ip = resolve(cand.host)
    if ip is None:
        log.warning("%s: DNS falhou para %s", cand.name, cand.host)
        return Measurement(cand.name, cand.country, cand.endpoint, None, 100.0, UNREACHABLE_SCORE, False)

    base = ["ping", "-n", "-q", "-c", str(count), "-i", "0.3", "-W", "2"]
    proc = run([*base, "-m", str(PING_FWMARK), ip])
    if proc.returncode != 0 and "invalid argument" in (proc.stderr + proc.stdout).lower():
        # ping sem suporte a -m (ou sem CAP_NET_ADMIN): mede pelo túnel. Serve
        # para não quebrar, mas os números ficam inflados e comparáveis só entre si.
        log.warning(
            "%s: ping -m indisponível — medindo PELO TÚNEL (valores inflados)", cand.name
        )
        proc = run([*base, ip])
    out = proc.stdout

    loss = 100.0
    m = re.search(r"(\d+(?:\.\d+)?)% packet loss", out)
    if m:
        loss = float(m.group(1))

    rtt = None
    m = re.search(r"rtt [^=]+= [\d.]+/([\d.]+)/", out)
    if m:
        rtt = float(m.group(1))

    if rtt is None or loss >= 100.0:
        return Measurement(cand.name, cand.country, cand.endpoint, rtt, loss, UNREACHABLE_SCORE, False)

    score = rtt + loss * LOSS_PENALTY_MS
    return Measurement(cand.name, cand.country, cand.endpoint, rtt, loss, score, True)


def current_peer() -> tuple[str | None, str | None]:
    """Retorna (public_key, endpoint) do peer ativo no kernel."""
    proc = run(["wg", "show", IFACE, "dump"])
    if proc.returncode != 0:
        log.error("wg show falhou: %s", proc.stderr.strip())
        return None, None
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    # 1ª linha = interface; demais = peers. O túnel Proton tem um peer só.
    if len(lines) < 2:
        return None, None
    fields = lines[1].split("\t")
    pubkey = fields[0] if fields else None
    endpoint = fields[2] if len(fields) > 2 and fields[2] != "(none)" else None
    return pubkey, endpoint


def last_handshake_age() -> float | None:
    proc = run(["wg", "show", IFACE, "latest-handshakes"])
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].isdigit():
            ts = int(parts[1])
            if ts == 0:
                return None
            return time.time() - ts
    return None


def rewrite_peer(conf_text: str, cand: Candidate) -> str:
    """Troca PublicKey e Endpoint do bloco [Peer], preservando o resto.

    AllowedIPs/PersistentKeepalive e todo o bloco [Interface] (com as ~40 regras
    PostUp) ficam intactos — só as duas linhas que identificam o servidor mudam.
    """
    head, sep, peer = conf_text.partition("[Peer]")
    if not sep:
        raise ValueError("conf sem bloco [Peer]")

    peer = re.sub(
        r"(?m)^\s*PublicKey\s*=.*$", f"PublicKey = {cand.public_key}", peer, count=1
    )
    peer = re.sub(
        r"(?m)^\s*Endpoint\s*=.*$", f"Endpoint = {cand.endpoint}", peer, count=1
    )
    # Comentário de identificação do servidor (a conf atual usa "# BE#72").
    if re.search(r"(?m)^\s*#\s*\S+", peer):
        peer = re.sub(r"(?m)^\s*#\s*\S+.*$", f"# {cand.name}", peer, count=1)
    else:
        peer = f"\n# {cand.name}" + peer

    return head + sep + peer


def apply_peer(cand: Candidate, dry_run: bool) -> bool:
    conf_text = CONF.read_text()
    new_text = rewrite_peer(conf_text, cand)

    if dry_run:
        log.info("[dry-run] trocaria peer para %s (%s)", cand.name, cand.endpoint)
        return True

    backup = CONF.with_suffix(CONF.suffix + f".bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(CONF, backup)
    log.info("Backup da conf em %s", backup)

    CONF.write_text(new_text)
    if not syncconf():
        log.error("syncconf falhou — restaurando %s", backup)
        shutil.copy2(backup, CONF)
        syncconf()
        return False

    if not wait_handshake():
        log.error(
            "Peer %s não fechou handshake em %ss — rollback para a config anterior",
            cand.name,
            HANDSHAKE_TIMEOUT_SEC,
        )
        shutil.copy2(backup, CONF)
        syncconf()
        wait_handshake()
        return False

    log.info("✅ Peer ativo: %s (%s)", cand.name, cand.endpoint)
    return True


def syncconf() -> bool:
    """Aplica a conf sem derrubar a interface (não dispara PostDown/PostUp)."""
    stripped = run(["wg-quick", "strip", str(CONF)])
    if stripped.returncode != 0:
        log.error("wg-quick strip falhou: %s", stripped.stderr.strip())
        return False
    proc = subprocess.run(
        ["wg", "syncconf", IFACE, "/dev/stdin"],
        input=stripped.stdout,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        log.error("wg syncconf falhou: %s", proc.stderr.strip())
        return False
    return True


def wait_handshake(timeout: int = HANDSHAKE_TIMEOUT_SEC) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        age = last_handshake_age()
        if age is not None and age < timeout:
            return True
        time.sleep(2)
    return False


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("State ilegível em %s — recomeçando", STATE)
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def write_metrics(measurements: list[Measurement], active: str | None, switched: bool) -> None:
    try:
        METRICS.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.debug("Sem textfile collector (%s) — métricas ignoradas", exc)
        return

    lines = [
        "# HELP protonvpn_candidate_rtt_ms RTT medido até o endpoint do servidor",
        "# TYPE protonvpn_candidate_rtt_ms gauge",
    ]
    for m in measurements:
        if m.rtt_ms is not None:
            lines.append(
                f'protonvpn_candidate_rtt_ms{{server="{m.name}",country="{m.country}"}} {m.rtt_ms}'
            )
    lines += [
        "# HELP protonvpn_candidate_loss_pct Perda de pacotes até o endpoint",
        "# TYPE protonvpn_candidate_loss_pct gauge",
    ]
    for m in measurements:
        lines.append(
            f'protonvpn_candidate_loss_pct{{server="{m.name}",country="{m.country}"}} {m.loss_pct}'
        )
    lines += [
        "# HELP protonvpn_active_server Servidor ativo no túnel (1 = ativo)",
        "# TYPE protonvpn_active_server gauge",
    ]
    for m in measurements:
        lines.append(
            f'protonvpn_active_server{{server="{m.name}",country="{m.country}"}} '
            f"{1 if m.name == active else 0}"
        )
    lines += [
        "# HELP protonvpn_best_server_switched_total Trocas de servidor aplicadas",
        "# TYPE protonvpn_best_server_switched_total counter",
        f"protonvpn_best_server_switched_total {1 if switched else 0}",
        "# HELP protonvpn_best_server_last_run_timestamp_seconds Última execução",
        "# TYPE protonvpn_best_server_last_run_timestamp_seconds gauge",
        f"protonvpn_best_server_last_run_timestamp_seconds {int(time.time())}",
    ]
    tmp = METRICS.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(METRICS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="aplica de fato a troca (sem isso, só mede e reporta)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="ignora histerese e dwell mínimo (uso manual)",
    )
    ap.add_argument("--json", action="store_true", help="saída em JSON")
    args = ap.parse_args()

    candidates = load_candidates()
    if not candidates:
        log.error("Nenhum candidato válido — nada a fazer")
        return 1

    measurements = [measure(c) for c in candidates]
    measurements.sort(key=lambda m: m.score)

    for m in measurements:
        status = f"{m.rtt_ms:.1f}ms loss={m.loss_pct:.0f}%" if m.reachable else "inalcançável"
        log.info("%-14s %-4s %s (score=%.1f)", m.name, m.country, status, m.score)

    best = measurements[0]
    if not best.reachable:
        log.error("Nenhum candidato respondeu — mantendo o servidor atual")
        write_metrics(measurements, None, False)
        return 1

    active_pubkey, active_endpoint = current_peer()
    by_name = {c.name: c for c in candidates}
    active_name = next(
        (c.name for c in candidates if c.public_key == active_pubkey), None
    )
    active_measure = next((m for m in measurements if m.name == active_name), None)

    state = load_state()
    last_switch = float(state.get("last_switch_ts", 0))
    dwell = time.time() - last_switch

    switched = False
    reason = ""

    if active_name == best.name:
        reason = f"{best.name} já é o melhor — nada a fazer"
    elif active_measure is None:
        reason = (
            f"servidor ativo ({active_endpoint}) não está na lista de candidatos — "
            f"trocando para {best.name}"
        )
    elif not args.force and dwell < MIN_DWELL_SEC:
        reason = (
            f"dwell mínimo não vencido ({dwell/60:.0f}min de {MIN_DWELL_SEC/60:.0f}min) — "
            f"mantendo {active_name}"
        )
    else:
        gain = (active_measure.score - best.score) / active_measure.score * 100
        if not args.force and gain < MIN_GAIN_PCT:
            reason = (
                f"ganho de {gain:.0f}% abaixo do mínimo de {MIN_GAIN_PCT:.0f}% — "
                f"mantendo {active_name} (evita alternância)"
            )
        else:
            reason = (
                f"{best.name} é {gain:.0f}% melhor que {active_name} "
                f"({best.score:.0f} vs {active_measure.score:.0f})"
            )
            if apply_peer(by_name[best.name], dry_run=not args.apply):
                switched = args.apply
                if switched:
                    state["last_switch_ts"] = time.time()
                    state["active"] = best.name
                    save_state(state)

    log.info("Decisão: %s", reason)
    active_final = best.name if switched else (active_name or "desconhecido")
    write_metrics(measurements, active_final, switched)

    if args.json:
        print(
            json.dumps(
                {
                    "measurements": [asdict(m) for m in measurements],
                    "active": active_final,
                    "switched": switched,
                    "reason": reason,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
