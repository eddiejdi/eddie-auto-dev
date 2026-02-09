## Homelab helper scripts

Scripts to run on the homelab host. Use with care; most require SSH access or running from the homelab itself.

- `update_landing_links.sh` — atualiza `/var/www/rpa4all.com/index.html` para apontar Jira e Confluence ao Atlassian Cloud, faz backup e recarrega o nginx.

Usage example (on homelab):
```bash
sudo bash /home/homelab/tools/homelab/update_landing_links.sh
```
