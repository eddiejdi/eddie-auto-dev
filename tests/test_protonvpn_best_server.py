from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "homelab" / "protonvpn_best_server.py"
)
_SPEC = importlib.util.spec_from_file_location("protonvpn_best_server", MODULE_PATH)
assert _SPEC and _SPEC.loader
pbs = importlib.util.module_from_spec(_SPEC)
# @dataclass resolve anotações via sys.modules[cls.__module__]; sem registrar
# antes do exec_module o decorator estoura com AttributeError.
sys.modules["protonvpn_best_server"] = pbs
_SPEC.loader.exec_module(pbs)


# Réplica reduzida da conf real: o que importa é que o [Interface] carregue
# PostUp/PostDown e que eles sobrevivam intactos à reescrita do [Peer].
CONF = """[Interface]
Address = 10.2.0.2/32
FwMark = 0xca6c
Table = 205
PrivateKey = PRIVADA_NAO_TOCAR=
PostUp = ip route add default dev protonvpn table 205 2>/dev/null || true
PostUp = ip rule add not fwmark 0xca6c lookup 205 priority 32764 2>/dev/null || true
PostDown = ip route del default dev protonvpn table 205 2>/dev/null || true

[Peer]
# BE#72
PublicKey = ANTIGA_PUBKEY=
AllowedIPs = 0.0.0.0/0
Endpoint = 79.127.164.65:51820
PersistentKeepalive = 25
"""

AR = pbs.Candidate(
    name="AR#12", country="AR", public_key="NOVA_PUBKEY=", endpoint="1.2.3.4:51820"
)


class TestRewritePeer:
    def test_troca_pubkey_e_endpoint(self):
        out = pbs.rewrite_peer(CONF, AR)
        assert "PublicKey = NOVA_PUBKEY=" in out
        assert "Endpoint = 1.2.3.4:51820" in out
        assert "ANTIGA_PUBKEY=" not in out
        assert "79.127.164.65" not in out

    def test_preserva_interface_e_postup(self):
        """O bloco [Interface] é a razão de existir do syncconf — perder um
        PostUp aqui derruba o roteamento da LAN inteira."""
        out = pbs.rewrite_peer(CONF, AR)
        assert "PrivateKey = PRIVADA_NAO_TOCAR=" in out
        assert out.count("PostUp = ") == 2
        assert out.count("PostDown = ") == 1
        assert "FwMark = 0xca6c" in out
        assert "Table = 205" in out

    def test_preserva_allowedips_e_keepalive(self):
        out = pbs.rewrite_peer(CONF, AR)
        assert "AllowedIPs = 0.0.0.0/0" in out
        assert "PersistentKeepalive = 25" in out

    def test_atualiza_comentario_do_servidor(self):
        out = pbs.rewrite_peer(CONF, AR)
        assert "# AR#12" in out
        assert "# BE#72" not in out

    def test_conf_sem_peer_falha(self):
        with pytest.raises(ValueError, match="sem bloco"):
            pbs.rewrite_peer("[Interface]\nAddress = 10.2.0.2/32\n", AR)

    def test_reescrita_e_idempotente(self):
        uma = pbs.rewrite_peer(CONF, AR)
        duas = pbs.rewrite_peer(uma, AR)
        assert uma == duas

    def test_peer_sem_comentario_ganha_um(self):
        sem_comentario = CONF.replace("# BE#72\n", "")
        out = pbs.rewrite_peer(sem_comentario, AR)
        assert "# AR#12" in out
        assert "PublicKey = NOVA_PUBKEY=" in out


class TestScore:
    """Perda pesa mais que RTT: vídeo tolera latência, não tolera stall."""

    def _medir(self, monkeypatch, ping_out: str) -> pbs.Measurement:
        monkeypatch.setattr(pbs, "resolve", lambda h: "1.2.3.4")
        monkeypatch.setattr(
            pbs,
            "run",
            lambda cmd, **kw: type("P", (), {"stdout": ping_out, "stderr": "", "returncode": 0})(),
        )
        return pbs.measure(AR, count=10)

    def test_medicao_usa_fwmark_para_escapar_do_tunel(self, monkeypatch):
        """Regressão do bug de projeto: sem -m, todo candidato mede o RTT do
        túnel atual somado ao real e a escolha vira ruído."""
        vistos = []

        def fake_run(cmd, **kw):
            vistos.append(cmd)
            return type(
                "P",
                (),
                {
                    "stdout": "10 packets transmitted, 10 received, 0% packet loss\n"
                    "rtt min/avg/max/mdev = 5.0/7.0/9.0/1.0 ms\n",
                    "stderr": "",
                    "returncode": 0,
                },
            )()

        monkeypatch.setattr(pbs, "resolve", lambda h: "1.2.3.4")
        monkeypatch.setattr(pbs, "run", fake_run)
        pbs.measure(AR, count=4)
        assert "-m" in vistos[0]
        assert str(pbs.PING_FWMARK) in vistos[0]

    def test_fallback_quando_ping_nao_suporta_fwmark(self, monkeypatch):
        """ping antigo rejeita -m: mede pelo túnel em vez de estourar."""
        chamadas = []

        def fake_run(cmd, **kw):
            chamadas.append(cmd)
            if "-m" in cmd:
                return type(
                    "P", (), {"stdout": "", "stderr": "ping: invalid argument", "returncode": 2}
                )()
            return type(
                "P",
                (),
                {
                    "stdout": "10 packets transmitted, 10 received, 0% packet loss\n"
                    "rtt min/avg/max/mdev = 200.0/210.0/220.0/5.0 ms\n",
                    "stderr": "",
                    "returncode": 0,
                },
            )()

        monkeypatch.setattr(pbs, "resolve", lambda h: "1.2.3.4")
        monkeypatch.setattr(pbs, "run", fake_run)
        m = pbs.measure(AR, count=4)
        assert len(chamadas) == 2
        assert "-m" not in chamadas[1]
        assert m.reachable
        assert m.rtt_ms == 210.0

    def test_rtt_e_loss_extraidos(self, monkeypatch):
        out = (
            "10 packets transmitted, 10 received, 0% packet loss, time 2700ms\n"
            "rtt min/avg/max/mdev = 30.1/42.5/55.0/6.2 ms\n"
        )
        m = self._medir(monkeypatch, out)
        assert m.rtt_ms == 42.5
        assert m.loss_pct == 0.0
        assert m.score == 42.5
        assert m.reachable

    def test_perda_penaliza_score(self, monkeypatch):
        out = (
            "10 packets transmitted, 9 received, 10% packet loss, time 2700ms\n"
            "rtt min/avg/max/mdev = 30.1/40.0/55.0/6.2 ms\n"
        )
        m = self._medir(monkeypatch, out)
        assert m.rtt_ms == 40.0
        assert m.loss_pct == 10.0
        # 40ms + 10% * 8ms = 120 — perde para um servidor limpo de 70ms.
        assert m.score == pytest.approx(120.0)

    def test_servidor_mudo_nao_vence_por_ausencia_de_dado(self, monkeypatch):
        """Regressão: sem esse guard, 100% de perda vira score baixo e o
        seletor migraria para um servidor morto."""
        out = "10 packets transmitted, 0 received, 100% packet loss, time 2700ms\n"
        m = self._medir(monkeypatch, out)
        assert not m.reachable
        assert m.score == pbs.UNREACHABLE_SCORE

    def test_dns_falho_e_inalcancavel(self, monkeypatch):
        monkeypatch.setattr(pbs, "resolve", lambda h: None)
        m = pbs.measure(AR, count=3)
        assert not m.reachable
        assert m.score == pbs.UNREACHABLE_SCORE


class TestCandidateParsing:
    def test_host_sem_porta(self):
        assert AR.host == "1.2.3.4"

    def test_host_ipv6_usa_ultimo_separador(self):
        c = pbs.Candidate("X", "XX", "k", "[2001:db8::1]:51820")
        assert c.host == "[2001:db8::1]"

    def test_candidatos_invalidos_sao_ignorados(self, tmp_path, monkeypatch):
        arq = tmp_path / "cand.json"
        arq.write_text(
            '{"servers": ['
            '{"name": "OK", "country": "AR", "public_key": "k", "endpoint": "1.2.3.4:51820"},'
            '{"name": "SEM_PORTA", "country": "AR", "public_key": "k", "endpoint": "1.2.3.4"},'
            '{"name": "SEM_CHAVE", "endpoint": "1.2.3.4:51820"}'
            "]}"
        )
        monkeypatch.setattr(pbs, "CANDIDATES", arq)
        out = pbs.load_candidates()
        assert [c.name for c in out] == ["OK"]

    def test_arquivo_ausente_retorna_vazio(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pbs, "CANDIDATES", tmp_path / "nao-existe.json")
        assert pbs.load_candidates() == []


class TestCurrentPeer:
    def _dump(self, monkeypatch, saida: str, rc: int = 0):
        monkeypatch.setattr(
            pbs,
            "run",
            lambda cmd, **kw: type("P", (), {"stdout": saida, "stderr": "", "returncode": rc})(),
        )

    def test_extrai_pubkey_e_endpoint(self, monkeypatch):
        dump = (
            "PRIV\tPUB\t38460\t0xca6c\n"
            "PEERPUB\tPSK\t79.127.164.65:51820\t0.0.0.0/0\t1785240000\t100\t200\t25\n"
        )
        self._dump(monkeypatch, dump)
        pub, ep = pbs.current_peer()
        assert pub == "PEERPUB"
        assert ep == "79.127.164.65:51820"

    def test_sem_peer_retorna_none(self, monkeypatch):
        self._dump(monkeypatch, "PRIV\tPUB\t38460\t0xca6c\n")
        assert pbs.current_peer() == (None, None)

    def test_endpoint_none_quando_sem_conexao(self, monkeypatch):
        dump = "PRIV\tPUB\t38460\t0xca6c\nPEERPUB\tPSK\t(none)\t0.0.0.0/0\t0\t0\t0\t25\n"
        self._dump(monkeypatch, dump)
        pub, ep = pbs.current_peer()
        assert pub == "PEERPUB"
        assert ep is None
