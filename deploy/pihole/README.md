# Pi-hole (homelab) — anti-drift

## Contract

| Surface | Owner |
|---------|--------|
| `:80` / `:443` | **nginx** (vhosts rpa4all) |
| `:8053` | **Pi-hole Admin** (`FTLCONF_webserver_port=8053`) |
| `:53` | host **dnsmasq** and/or FTL (validate after changes) |
| Config data | Docker volumes **`pihole_config`**, **`pihole_dnsmasq`** (on storj) |

## Why this exists

`pihole-run.sh` used to `docker start` any existing container and exit. A drifted container (no `FTLCONF_webserver_port`, wrong bind mounts) stayed on **:80/:443** and broke nginx forever.

## Deploy to host

```bash
# from monorepo
sudo install -m 0755 deploy/pihole/pihole-run.sh /usr/local/sbin/pihole-run.sh
sudo install -m 0644 deploy/pihole/docker-compose.yml /home/homelab/pihole/docker-compose.yml
# optional unit already points at pihole-run.sh
sudo systemctl daemon-reload
sudo systemctl start pihole.service
```

Optional password file (root-only):

```bash
# /etc/pihole/container.env
WEBPASSWORD=...
```

## Verify

```bash
ss -lntp | grep -E ':80 |:443 |:8053 '
# expect nginx on 80/443, something on 8053
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8053/admin/
docker inspect pihole --format '{{range .Config.Env}}{{println .}}{{end}}' | grep webserver
```

Admin UI: `http://192.168.15.2:8053/admin/`

## Rollback

Use backup recreate scripts under `/home/homelab/pihole/backups/nginx-pihole-*/` if needed.
