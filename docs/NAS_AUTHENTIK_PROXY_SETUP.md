# NAS OMV + Authentik

Esta integracao protege o painel web do NAS (`OMV`) com `forward auth` do Authentik.

Topologia:

1. Cliente acessa `https://nas.rpa4all.com`
2. Cloudflare Tunnel entrega em `http://localhost:9004` no homelab
3. Nginx valida sessao em `http://127.0.0.1:9000/outpost.goauthentik.io/`
4. Se autenticado, Nginx faz proxy para `http://192.168.15.4` (OMV)

## 1. Provider no Authentik

Script idempotente:

```bash
export AUTHENTIK_TOKEN='...'
python3 scripts/misc/setup_nas_authentik_proxy.py
```

Variaveis opcionais:

- `AUTHENTIK_URL` (default `https://auth.rpa4all.com`)
- `AUTHENTIK_NAS_EXTERNAL_HOST` (default `https://nas.rpa4all.com`)
- `AUTHENTIK_NAS_APP_SLUG` (default `nas-omv`)
- `AUTHENTIK_NAS_APP_NAME` (default `NAS OMV`)

## 2. Nginx no Homelab

Arquivo versionado: `config/nginx-nas-authentik-homelab.conf`

Instalacao:

```bash
sudo cp config/nginx-nas-authentik-homelab.conf /etc/nginx/sites-available/nas.rpa4all.com-auth
sudo ln -s /etc/nginx/sites-available/nas.rpa4all.com-auth /etc/nginx/sites-enabled/nas.rpa4all.com-auth
sudo nginx -t
sudo systemctl reload nginx
```

## 3. Cloudflare Tunnel

Adicionar rota:

```yaml
- hostname: nas.rpa4all.com
  service: http://localhost:9004
```

Aplicar:

```bash
sudo systemctl restart cloudflared-rpa4all.service
```

## 4. Validacao

```bash
curl -kI https://nas.rpa4all.com/
curl -s -o /dev/null -D - -H 'Host: nas.rpa4all.com' http://127.0.0.1:9004/
```

Esperado:

- raiz retorna `302` para `/outpost.goauthentik.io/start`
- login redireciona para `https://auth.rpa4all.com/application/o/authorize/...`
