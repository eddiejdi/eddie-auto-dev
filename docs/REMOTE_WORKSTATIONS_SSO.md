# Remote Workstations com SSO (Authentik)

## Objetivo
Disponibilizar estações remotas acessíveis via navegador, com autenticação centralizada no Authentik e sem instalar cliente no computador do usuário.

## URLs de acesso
- XFCE: `https://homelab.rpa4all.com/workstation`
- Windows 11 Light: `https://homelab.rpa4all.com/windows11`

## Como o fluxo funciona
1. Usuário clica no app no `https://auth.rpa4all.com`.
2. Authentik redireciona para `homelab.rpa4all.com` via proxy provider.
3. Nginx no homelab valida sessão (`auth_request` com outpost do Authentik).
4. Nginx encaminha para o backend da workstation (noVNC/web viewer).

## Componentes
- Authentik: provider proxy + applications (tiles).
- Cloudflared: publica `homelab.rpa4all.com`.
- Nginx (`/etc/nginx/sites-available/homelab.rpa4all.com-auth`):
  - rota `/workstation` -> XFCE web
  - rota `/windows11` -> Windows 11 Light web
- Serviços locais no host `192.168.15.2`:
  - `workstation-xfce.service` (Xvfb + XFCE + x11vnc + websockify)
  - `workstation-win11l.service` (bootstrap/autostart do container Windows 11 Light)
  - `workstation-win11l` (container `dockurr/windows`, `VERSION=11l`)

## Arquivos versionados
- `config/nginx-homelab-authentik-homelab.conf`
- `scripts/misc/setup_workstation_authentik_proxy.py`
- `scripts/misc/setup_windows11_light_authentik_app.py`

## Comandos de operação
### Verificar saúde
```bash
ssh homelab@192.168.15.2 'sudo systemctl is-active nginx cloudflared-rpa4all.service workstation-xfce.service'
ssh homelab@192.168.15.2 'sudo systemctl is-active workstation-win11l.service'
ssh homelab@192.168.15.2 'docker ps --filter name=workstation-win11l'
```

### Subir/recriar Windows 11 Light (sem docker-compose)
Use este comando quando o host estiver com `docker-compose` v1:
```bash
ssh homelab@192.168.15.2 '
docker rm -f workstation-win11l || true
docker run -d \
  --name workstation-win11l \
  --device /dev/kvm \
  --device /dev/net/tun \
  --cap-add NET_ADMIN \
  -e VERSION=11l \
  -e RAM_SIZE=8G \
  -e CPU_CORES=4 \
  -e DISK_SIZE=64G \
  -e LANGUAGE=English \
  -e REGION=en-US \
  -e KEYBOARD=en-US \
  -e USERNAME=Docker \
  -e PASSWORD=admin \
  -p 127.0.0.1:8400:8006 \
  -p 127.0.0.1:3391:3389/tcp \
  -p 127.0.0.1:3391:3389/udp \
  -v /opt/workstation-win11l/storage:/storage \
  -v /opt/workstation-win11l/shared:/shared \
  --restart unless-stopped \
  dockurr/windows
'
```

### Recarregar Nginx
```bash
ssh homelab@192.168.15.2 'sudo nginx -t && sudo systemctl reload nginx'
```

### Recriar tile Windows 11 Light no Authentik
```bash
AUTHENTIK_TOKEN=... python3 scripts/misc/setup_windows11_light_authentik_app.py
```
Por padrão o script cria o app como launcher (sem provider dedicado), porque o provider `Homelab API Proxy` já está vinculado a outro app.
Se quiser forçar vínculo com provider dedicado:
```bash
AUTHENTIK_WINDOWS11_ATTACH_PROVIDER=true AUTHENTIK_TOKEN=... python3 scripts/misc/setup_windows11_light_authentik_app.py
```

## Troubleshooting
### Tela abre, mas não conecta no desktop (noVNC)
Verifique requests para `websockify`:
```bash
ssh homelab@192.168.15.2 'sudo tail -n 200 /var/log/nginx/access.log | grep -E "workstation|windows11|websockify"'
```
Se aparecer `GET /websockify 404`, a rota websocket não está apontando para a workstation correta.

### Timeout externo no domínio
```bash
ssh homelab@192.168.15.2 'sudo systemctl status cloudflared-rpa4all.service --no-pager'
```

### Authentik não redireciona corretamente
```bash
curl -kI https://homelab.rpa4all.com/workstation
curl -kI https://homelab.rpa4all.com/windows11
```
Esperado: `302` para `/outpost.goauthentik.io/start` quando sem sessão.

### Erro ao criar app no Authentik: provider já em uso
Mensagem comum:
`Application with this provider already exists.`
Solução: executar o script sem `AUTHENTIK_WINDOWS11_ATTACH_PROVIDER=true` (modo padrão), criando o tile somente com `meta_launch_url`.

### Windows 11 Light em loop de inicialização (idioma)
Mensagem comum no log:
`No download in the Portuguese language available for Windows 11 LTSC!`
Solução: ajustar `LANGUAGE=English` para `VERSION=11l`.

### docker-compose falha com `'ContainerConfig'`
Esse erro ocorre em hosts com `docker-compose` v1.
Solução prática: usar `docker run` (seção acima) ou migrar para `docker compose` plugin v2.

### Primeiro boot demora (download da imagem Windows)
No primeiro start, o container baixa a mídia da Microsoft. O portal web abre, mas o desktop só fica disponível após concluir.
```bash
ssh homelab@192.168.15.2 'docker logs -f workstation-win11l'
```
Quando o download termina, a conexão VNC/websocket passa a responder em `/windows11/websockify`.
