# Status Operacional — 15 de abril de 2026

> Snapshot pos-recuperacao do Pi-hole, Cloudflare Tunnel e servicos publicados no homelab.

## Estado Geral

- **Homelab**: operacional
- **Pi-hole DNS**: operacional na LAN
- **DHCP LAN**: operacional no host via `dnsmasq`
- **Cloudflare Tunnel**: operacional
- **Mail / Roundcube**: operacional
- **Guardrails**: operacional e autenticado
- **NAS publicado**: pendente

## Servicos Criticos

| Servico | Estado |
|---|---|
| `docker` | `active` |
| `pihole.service` | `active` |
| `homelab-lan-dhcp.service` | `active` |
| `cloudflared-rpa4all.service` | `active` |
| `trading-guardrails-control.service` | `active` |

## Validacao Pi-hole

| Teste | Resultado |
|---|---|
| `dig @192.168.15.2 google.com` | `NOERROR` |
| `dig @192.168.15.2 pi.hole` | `NOERROR` |
| `http://192.168.15.2:8053/admin/` | `302 Found` |

## Dominios Publicados

| Dominio | Resultado |
|---|---|
| `www.rpa4all.com` | `200` |
| `auth.rpa4all.com` | `302` |
| `openwebui.rpa4all.com` | `200` |
| `grafana.rpa4all.com` | `200` |
| `wiki.rpa4all.com` | `200` |
| `homelab.rpa4all.com` | `302` |
| `mail.rpa4all.com` | `302` |
| `guardrails.rpa4all.com` | `401` |
| `nas.rpa4all.com` | `502` |

## Principais Ajustes Aplicados

- Pi-hole convertido para operacao apenas DNS.
- Novo bootstrap do Pi-hole via `systemd` e script local.
- `cloudflared` ajustado para `protocol: http2`.
- Rotas de excecao da Cloudflare configuradas fora da VPN.
- Allowlist NordVPN ajustada para a edge da Cloudflare.
- `guardrails` corrigido para responder `HEAD`.
- `roundcube` reativado.

## Ponto Pendente

`nas.rpa4all.com` ainda falha porque o upstream configurado em `192.168.15.4` nao responde na LAN. O problema remanescente e do destino final, nao do tunel.

## Referencia

- Relatorio detalhado: [docs/HOMELAB_NETWORK_RECOVERY_2026-04-15.md](HOMELAB_NETWORK_RECOVERY_2026-04-15.md)

---

**Data:** 2026-04-15  
**Status Geral:** operacional com pendencia isolada no NAS
