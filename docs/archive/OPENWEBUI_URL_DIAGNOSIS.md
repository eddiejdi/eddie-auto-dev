# 🔍 Diagnóstico - URL /openwebui/ Quebrada

**Data:** 02/02/2026  
**URL:** https://www.rpa4all.com/openwebui/  
**Status:** 🟡 Parcialmente Funcional

---

## ❌ O Problema

A URL https://www.rpa4all.com/openwebui/ retorna **HTTP 200**, mas a página não funciona corretamente porque:

### 1. **Erro de Carregamento de Assets** ⚠️

O OpenWebUI está programado para servir assets (JS, CSS, imagens) no **caminho raiz `/`**, mas quando acessado via `/openwebui/`, os links viram:

❌ /static/loader.js          → 404 (não existe em raiz)
✅ /openwebui/static/loader.js → Correto (mas não há redirect)
### 2. **Problema Raiz: OpenWebUI não suporta subrotas**

O OpenWebUI é uma SPA (Single Page Application) que assume estar na raiz do domínio. Quando servido via `/openwebui/`, todos os assets ficam quebrados porque os links viram:

```html
<!-- No arquivo HTML retornado -->
<link rel="stylesheet" href="/static/custom.css" />  ❌ 404
<script src="/static/loader.js" defer></script>       ❌ 404
---

## 📋 Configuração Atual

### Nginx (Correto)
```nginx
location /openwebui {
    proxy_pass http://127.0.0.1:8002;
    # Sem trailing slash = preserva /openwebui/ no path
}
### Docker (Problema)
```bash
open-webui:
  ports:
    - "0.0.0.0:8002->8080"
  # Espera estar em http://localhost:8080/ (raiz)
---

## 🔧 Soluções

### ✅ Solução 1: Servir OpenWebUI na Raiz (RECOMENDADO)

**Criar um domínio separado:**

```nginx
# /etc/nginx/sites-available/openwebui.rpa4all.com

server {
    listen 443 ssl http2;
    server_name openwebui.rpa4all.com;
    
    ssl_certificate /etc/letsencrypt/live/openwebui.rpa4all.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openwebui.rpa4all.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_buffering off;
    }
}
**Depois:**
1. Ativar site: `sudo ln -s /etc/nginx/sites-available/openwebui.rpa4all.com /etc/nginx/sites-enabled/`
2. Testar: `sudo nginx -t`
3. Recarregar: `sudo systemctl reload nginx`
4. Atualizar landing page: `https://openwebui.rpa4all.com/`

---

### ⚠️ Solução 2: Usar Proxy com Reescrita de Paths

Modificar Nginx para reescrever caminhos:

```nginx
location /openwebui {
    # Reescrever paths internos
    rewrite ^/openwebui/(.*)$ /$1 break;
    proxy_pass http://127.0.0.1:8002;
    
    # Reescrever respostas HTML
    sub_filter 'href="/' 'href="/openwebui/';
    sub_filter 'src="/' 'src="/openwebui/';
    sub_filter_once off;
}
**Desvantagem:** Mais complexo, mais overhead, pode quebrar URLs dinâmicas

---

### ⚠️ Solução 3: Configurer OpenWebUI com BASE_URL (Não funciona)

O OpenWebUI não suporta servir em subpaths - até a versão 0.x não há configuração oficial para `BASE_URL=/openwebui`

---

## 🎯 Recomendação

**Use a Solução 1 (Domínio Separado)** porque:

✅ Simples e limpo  
✅ Sem overhead de reescrita  
✅ URLs funcionam corretamente  
✅ Padrão da indústria (ex: GitHub Pages, Vercel, etc)  
✅ Escalável para adicionar outros serviços

---

## 📊 Impacto Atual

| Local | Status | Razão |
|-------|--------|-------|
| https://www.rpa4all.com/ | ✅ OK | Landing page estática |
| https://www.rpa4all.com/grafana/ | ✅ OK | Grafana suporta subpaths (BASE_URL config) |
| https://www.rpa4all.com/openwebui/ | 🔴 QUEBRADO | SPA sem suporte a subpaths |

---

## 🚀 Implementação Imediata

```bash
# 1. Criar config nginx
cat > /tmp/openwebui_vhost.conf <<'EOF'
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name openwebui.rpa4all.com;
    
    ssl_certificate /etc/letsencrypt/live/openwebui.rpa4all.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/openwebui.rpa4all.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 3600s;
        proxy_buffering off;
    }
}
EOF

# 2. Copiar para homelab
scp -i ~/.ssh/shared_deploy_rsa /tmp/openwebui_vhost.conf homelab@192.168.15.2:/tmp/

# 3. No homelab:
ssh -i ~/.ssh/shared_deploy_rsa homelab@192.168.15.2 << 'CMDS'
sudo cp /tmp/openwebui_vhost.conf /etc/nginx/sites-available/openwebui.rpa4all.com
sudo ln -sf /etc/nginx/sites-available/openwebui.rpa4all.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
CMDS

# 4. Atualizar landing page (index.html)
# Mudar: href="https://www.rpa4all.com/openwebui/"
# Para:  href="https://openwebui.rpa4all.com/"
---

## 🎓 Por que Grafana funciona?

Grafana suporta subpaths via variável de ambiente:

```bash
GF_SERVER_ROOT_URL=http://localhost:3002/grafana
Mas OpenWebUI não tem essa opção (limitação do projeto).

---

## 📝 Resumo

| Aspecto | Detalhes |
|--------|----------|
| **Problema** | OpenWebUI é SPA, não suporta subpaths |
| **URL Quebrada** | https://www.rpa4all.com/openwebui/ |
| **Motivo** | Assets retornam 404 (/static/... em vez de /openwebui/static/...) |
| **Solução** | Usar domínio separado: openwebui.rpa4all.com |
| **Tempo de Fix** | ~5 minutos |
| **Risco** | Baixo (apenas reconfig nginx) |
| **Impacto** | Melhora UX, URLs mais limpas |

---

**Gerado por:** GitHub Copilot  
**Status:** 🔍 ANÁLISE COMPLETA
