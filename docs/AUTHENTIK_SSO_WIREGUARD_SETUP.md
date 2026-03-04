# Authentik SSO + WireGuard VPN — Implementação Homelab

**Data:** 2026-03-04  
**Status:** ✅ Implementado e testado

## Visão Geral

Centralização de autenticação via Authentik SSO (OpenID Connect / OAuth2) para todos os serviços web do homelab, com acesso remoto seguro via WireGuard VPN.

## Componentes

### Authentik SSO (auth.rpa4all.com)

| Item | Valor |
|------|-------|
| URL | https://auth.rpa4all.com |
| Versão | 2024.12 |
| Admin | akadmin |
| API Token | ak-homelab-authentik-api-2026 |
| Compose | /mnt/raid1/authentik/docker-compose.yml |
| DB | authentik-postgres (PostgreSQL 16) em /mnt/disk2/authentik-db |
| Cache | authentik-redis (Redis 7 Alpine) |

**Containers:** authentik-server (:9000/:9443), authentik-worker, authentik-redis, authentik-postgres

### Integrações OAuth2/OIDC

| Serviço | Client ID | Redirect URI | Status |
|---------|-----------|-------------|--------|
| Nextcloud | authentik-nextcloud | /apps/user_oidc/code | ✅ user_oidc v8.5.0 |
| Grafana | authentik-grafana | /login/generic_oauth | ✅ Botão "Authentik" no login |
| OpenWebUI | authentik-openwebui | /oauth/oidc/callback | ✅ OIDC habilitado |

**Discovery endpoints:**
- Nextcloud: `https://auth.rpa4all.com/application/o/nextcloud/.well-known/openid-configuration`
- Grafana: `https://auth.rpa4all.com/application/o/grafana/.well-known/openid-configuration`
- OpenWebUI: `https://auth.rpa4all.com/application/o/openwebui/.well-known/openid-configuration`

### WireGuard VPN

| Item | Valor |
|------|-------|
| Interface | wg0 |
| Subnet | 10.66.66.0/24 |
| Server IP | 10.66.66.1 |
| Porta | 51820/UDP |
| Config | /etc/wireguard/wg0.conf |

**Peers configurados:**

| Nome | IP VPN | Status |
|------|--------|--------|
| eddie-client (PC) | 10.66.66.2 | Configurado |
| eddie-phone (Android) | 10.66.66.3 | Ativo (handshake recente) |

**Rede:** IP forwarding habilitado, MASQUERADE ativo para enp1s0. Clientes VPN acessam todos os serviços via 192.168.15.2.

## Cloudflare Tunnel Routes

```yaml
# /etc/cloudflared/config.yml
ingress:
  - hostname: dns.rpa4all.com      → :8453
  - hostname: www.rpa4all.com      → :8090
  - hostname: openwebui.rpa4all.com → :3000
  - hostname: auth.rpa4all.com     → :9000  # Authentik
  - hostname: nextcloud.rpa4all.com → :8880
  - hostname: grafana.rpa4all.com  → :3002
  - hostname: rpa4all.com          → :8090
  - service: http_status:404
```

## Containers Ativos (13)

| Container | Status | Porta |
|-----------|--------|-------|
| authentik-server | ✅ healthy | 9000, 9443 |
| authentik-worker | ✅ healthy | — |
| authentik-redis | ✅ healthy | 6379 |
| authentik-postgres | ✅ healthy | 5432 |
| grafana | ✅ up | 127.0.0.1:3002→3000 |
| prometheus | ✅ up | 127.0.0.1:9090 |
| nextcloud | ✅ up | 8880→80 |
| nextcloud-db | ✅ healthy | 3306 |
| open-webui | ✅ healthy | 3000→8080 |
| roundcube | ✅ up | 9080→80 |
| mailserver | ✅ healthy | 25,143,465,587,993 |
| eddie-postgres | ✅ up | 5433→5432 |
| pihole | ✅ healthy | 53, 8053→80 |

## Testes Realizados

- [x] auth.rpa4all.com → HTTP 200 (login flow)
- [x] OIDC discovery endpoints (3/3) → HTTP 200
- [x] nextcloud.rpa4all.com/login → HTTP 200
- [x] grafana.rpa4all.com/login → HTTP 200, botão "Authentik" presente
- [x] openwebui.rpa4all.com → HTTP 200
- [x] WireGuard wg0 UP, 2 peers, IP forwarding + NAT ativos
- [x] Todos 13 containers healthy/up

## Credenciais (referência)

> ⚠️ Secrets armazenados em vault, não em texto claro.

- Authentik admin: `akadmin` / vault:authentik-admin-password
- Nextcloud user: `edenilson.paschoa@rpa4all.com` / vault:nextcloud-user-password
- Grafana admin: `admin` / vault:grafana-admin-password
- OAuth2 secrets: vault:authentik-{nextcloud,grafana,openwebui}-client-secret
