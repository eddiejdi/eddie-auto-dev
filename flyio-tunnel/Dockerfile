FROM caddy:2-alpine

# Instalar ferramentas úteis
RUN apk add --no-cache curl jq

# Copiar configuração do Caddy
COPY Caddyfile /etc/caddy/Caddyfile

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile"]
