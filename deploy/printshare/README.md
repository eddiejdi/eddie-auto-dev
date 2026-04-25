PrintShare (local) - wrapper API for Phomemo Q30

This service exposes a simple HTTP API to send text/image print jobs to a Phomemo Q30
using the existing `phomemo_print.py` driver from the workspace.

Endpoints:
- GET /health -> {"status":"ok"}
- GET /status -> calls `phomemo_print.py --status` and returns JSON
- POST /print -> JSON {"type":"text","content":"..."} or {"type":"image","content":"<base64>"}

Deployment (homelab):
1. Copy this folder to the homelab server at `/home/homelab/printshare`.
2. Ensure the Phomemo is paired and available under /dev (Bluetooth /rfcomm or USB).
3. Start with: `docker compose up -d --build`
4. Test health: `curl http://<HOMELAB_IP>:8085/health`
5. Check status: `curl http://<HOMELAB_IP>:8085/status`

Notes:
- The container is run privileged and maps `/dev` so it can access serial devices.
- Environment variables: `BAUDRATE`, `PRINTER_PORT` (optional), `PORT_HINT`.
- For image prints, POST base64-encoded PNG data as `content`.

Systemd unit (recommended)
-------------------------
To run the PrintShare container as a systemd service on the homelab host, copy the provided unit and enable it:

1. Copy unit to host:

```bash
scp deploy/printshare/printshare.service homelab@192.168.15.2:/tmp/printshare.service
ssh homelab@192.168.15.2 'sudo mv /tmp/printshare.service /etc/systemd/system/printshare.service'
```

2. Reload systemd and enable service:

```bash
ssh homelab@192.168.15.2 'sudo systemctl daemon-reload'
ssh homelab@192.168.15.2 'sudo systemctl enable --now printshare.service'
```

3. Check status and logs:

```bash
ssh homelab@192.168.15.2 'sudo systemctl status printshare.service --no-pager'
ssh homelab@192.168.15.2 'sudo journalctl -u printshare.service -f'
# or docker logs printshare
```

Notes:
- The unit runs `docker run` and mounts `/dev` and the CUPS socket; it requires root privileges.
- Remove `--privileged` or tighten mounts for production. Use the `ExecStartPre` pull step if you publish the image to a registry.
