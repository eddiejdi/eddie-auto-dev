# Mail Roundcube + Authentik

Esta integracao protege `https://mail.rpa4all.com/` com `forward auth` do Authentik.

Topologia em producao:

1. Cloudflare Tunnel recebe `mail.rpa4all.com`
2. O tunnel entrega em `http://localhost:9002` no homelab
3. O Nginx do homelab valida a sessao em `http://127.0.0.1:9000/outpost.goauthentik.io/`
4. Se autenticado, o Nginx entrega o Roundcube em `http://127.0.0.1:9080`

Importante:

- Isso protege o acesso ao webmail, nao autentica IMAP/SMTP.
- O login da caixa postal continua sendo a credencial do proprio email.
- `docker/docker-compose.email-simple.yml` e `config/nginx-simple.conf` servem para validacao local; o dominio publico depende do Nginx do homelab e do `cloudflared`.

## 1. Configuracao do Provider no Authentik

Crie um `Proxy Provider` com:

- `external_host`: `https://mail.rpa4all.com`
- `mode`: `forward_single`
- fluxo padrao de login/autorizacao
- provider vinculado na aplicacao `mailu-email`
- provider presente no `authentik Embedded Outpost`

Existe um script idempotente para isso:

```bash
export AUTHENTIK_TOKEN='...'
python3 scripts/misc/setup_mail_authentik_proxy.py
```

Variaveis opcionais:

- `AUTHENTIK_URL`
- `AUTHENTIK_EMBEDDED_OUTPOST_ID`
- `AUTHENTIK_AUTHENTICATION_FLOW_ID`
- `AUTHENTIK_AUTHORIZATION_FLOW_ID`
- `AUTHENTIK_INVALIDATION_FLOW_ID`

O script:

- cria ou reutiliza o provider `Mail Roundcube Proxy`
- aponta a aplicacao `mailu-email` para esse provider
- garante o provider no embedded outpost

## 2. Configuracao do Nginx no Homelab

Arquivo versionado: `config/nginx-mail-authentik-homelab.conf`

Instalacao:

```bash
sudo cp config/nginx-mail-authentik-homelab.conf /etc/nginx/sites-available/mail.rpa4all.com-auth
sudo ln -s /etc/nginx/sites-available/mail.rpa4all.com-auth /etc/nginx/sites-enabled/mail.rpa4all.com-auth
sudo nginx -t
sudo systemctl reload nginx
```

Esse vhost:

- escuta em `127.0.0.1:9002`
- exige autenticacao via `auth_request`
- expõe `/outpost.goauthentik.io/`
- faz proxy do Roundcube local em `127.0.0.1:9080`

## 3. Configuracao do Cloudflare Tunnel

No homelab, em `/etc/cloudflared/config.yml`, a regra publica precisa apontar para o Nginx autenticado e nao para o Roundcube direto:

```yaml
- hostname: mail.rpa4all.com
  service: http://localhost:9002
  originRequest:
    connectTimeout: 30s
```

Aplicacao:

```bash
sudo systemctl restart cloudflared-rpa4all.service
```

Se houver erro de permissao no logfile, garanta:

```bash
sudo install -o _rpa4all -g _rpa4all -m 0640 /dev/null /var/log/cloudflared.log
```

## 4. Validacao

Valide o fluxo publico:

```bash
curl -kI https://mail.rpa4all.com/
curl -kI 'https://mail.rpa4all.com/outpost.goauthentik.io/start?rd=https://mail.rpa4all.com/'
```

Esperado:

- a raiz responde `302` para `/outpost.goauthentik.io/start`
- o endpoint `start` responde `302` para `https://auth.rpa4all.com/application/o/authorize/...`

Valide o homelab localmente:

```bash
curl -s -o /dev/null -D - -H 'Host: mail.rpa4all.com' http://127.0.0.1:9002/
sudo systemctl status cloudflared-rpa4all.service --no-pager
sudo nginx -t
```
