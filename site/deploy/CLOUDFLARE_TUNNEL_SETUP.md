# 🌐 RPA4ALL IDE - Cloudflare Tunnel Setup

## Overview

This setup exposes your local RPA4ALL IDE (running on 192.168.15.2) to the internet securely using Cloudflare Tunnel, without opening ports on your router or exposing your IP.

## Architecture

```
Internet Users
    ↓
Cloudflare CDN (HTTPS)
    ↓
Cloudflare Tunnel (encrypted)
    ↓
Your Homelab (192.168.15.2)
    ├── IDE Static Site (port 8081)
    ├── Code Runner API (port 2000)
    ├── Specialized Agents API (port 8503)
    ├── Open WebUI (port 3000)
    └── Grafana (port 3001)
```

## Prerequisites

- Cloudflare account (free tier works)
- Domain registered with Cloudflare DNS
- Homelab server (192.168.15.2) with services running

## 🚀 Quick Setup

### On homelab server (192.168.15.2):

```bash
# Clone repo and navigate to deploy folder
cd ~/eddie-auto-dev/site/deploy

# Run automated setup script
sudo ./setup_cloudflared_ide.sh
```

This script will:
1. ✅ Install cloudflared
2. ✅ Authenticate with Cloudflare
3. ✅ Create tunnel named "rpa4all-ide"
4. ✅ Configure ingress rules for all services
5. ✅ Set up DNS records automatically
6. ✅ Install and start systemd service
7. ✅ Test all endpoints

## 📋 Manual Setup (if needed)

### 1. Install cloudflared

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb
```

### 2. Authenticate

```bash
cloudflared tunnel login
```

This opens your browser to authorize cloudflared with your Cloudflare account.

### 3. Create tunnel

```bash
cloudflared tunnel create rpa4all-ide
```

Note the tunnel ID shown in the output.

### 4. Configure tunnel

Copy the configuration template:

```bash
cp cloudflared-rpa4all-ide.yml ~/.cloudflared/config.yml
```

Edit `~/.cloudflared/config.yml` and replace `<TUNNEL_ID>` with your actual tunnel ID.

### 5. Configure DNS

Add DNS records for each subdomain:

```bash
cloudflared tunnel route dns rpa4all-ide ide.rpa4all.com
cloudflared tunnel route dns rpa4all-ide api.rpa4all.com
cloudflared tunnel route dns rpa4all-ide openwebui.rpa4all.com
cloudflared tunnel route dns rpa4all-ide grafana.rpa4all.com
```

### 6. Install as service

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## 🔍 Verification

### Check tunnel status

```bash
# Service status
sudo systemctl status cloudflared

# Live logs
sudo journalctl -u cloudflared -f

# Tunnel information
cloudflared tunnel info rpa4all-ide
```

### Test endpoints

```bash
# From anywhere on internet:
curl https://ide.rpa4all.com
curl https://api.rpa4all.com/agents-api/health
curl https://api.rpa4all.com/code-runner/health
```

## 🌐 Access URLs

After setup, your services are accessible at:

- **IDE**: https://ide.rpa4all.com
- **Agents API**: https://api.rpa4all.com/agents-api/*
- **Code Runner**: https://api.rpa4all.com/code-runner/*
- **Open WebUI**: https://openwebui.rpa4all.com
- **Grafana**: https://grafana.rpa4all.com

## 🔧 Configuration Details

### Ingress Rules

The tunnel routes traffic based on hostname and path:

| Hostname | Path | Local Service | Port |
|----------|------|---------------|------|
| ide.rpa4all.com | / | HTTP Static Server | 8081 |
| api.rpa4all.com | /code-runner/* | Flask Code Runner | 2000 |
| api.rpa4all.com | /agents-api/* | FastAPI Agents | 8503 |
| openwebui.rpa4all.com | / | Open WebUI | 3000 |
| grafana.rpa4all.com | / | Grafana | 3001 |

### Network Detection

The IDE automatically detects if you're accessing from:
- **Local network** (192.168.x.x): Uses direct connections to homelab IPs
- **External network**: Uses Cloudflare Tunnel domains

This is handled in `site/ide.js`:

```javascript
const isLocalNetwork = window.location.hostname.startsWith('192.168.') 
    || window.location.hostname === 'localhost';

const BACKEND_URL = isLocalNetwork 
    ? 'http://192.168.15.2:8503'           // Local
    : 'https://api.rpa4all.com/agents-api'; // External
```

## 🛠️ Troubleshooting

### Tunnel not connecting

```bash
# Check if services are running locally
curl http://localhost:8081
curl http://localhost:2000/health
curl http://localhost:8503/health

# Restart tunnel
sudo systemctl restart cloudflared

# Check logs for errors
sudo journalctl -u cloudflared -n 100
```

### DNS not resolving

```bash
# Check DNS records
dig ide.rpa4all.com
nslookup ide.rpa4all.com

# Manually add DNS record if needed
cloudflared tunnel route dns rpa4all-ide ide.rpa4all.com
```

### 502 Bad Gateway

This usually means the local service isn't responding:

```bash
# Check if service is running
sudo systemctl status <service-name>

# For HTTP server on 8081
ps aux | grep 'python.*http.server'

# For code runner on 2000
ps aux | grep 'flask\|app.py'
```

## 📊 Performance & Monitoring

### Check tunnel metrics

Cloudflare dashboard provides:
- Request count
- Bandwidth usage
- Response time
- Error rate

### Local monitoring

```bash
# Watch tunnel logs in real-time
sudo journalctl -u cloudflared -f

# Check connection count
sudo netstat -tnlp | grep cloudflared
```

## 🔒 Security Notes

✅ **Advantages**:
- No ports exposed on your router
- TLS/HTTPS handled by Cloudflare
- DDoS protection included
- IP address hidden
- Works behind NAT/firewall

⚠️ **Considerations**:
- All traffic goes through Cloudflare
- Free tier has bandwidth limits
- Cloudflare can see traffic (use Zero Trust for end-to-end encryption)

## 🔄 Updating Configuration

After changing `config.yml`:

```bash
sudo systemctl restart cloudflared
```

## 📚 Additional Resources

- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Tunnel CLI Reference](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/)
- [Zero Trust Dashboard](https://one.dash.cloudflare.com/)

## 🆘 Support

If you encounter issues:

1. Check service status: `sudo systemctl status cloudflared`
2. Review logs: `sudo journalctl -u cloudflared -n 200`
3. Test local services: `curl http://localhost:<port>`
4. Verify DNS: `dig ide.rpa4all.com`
5. Check Cloudflare dashboard for tunnel status

---

**Last updated**: 2026-02-07  
**Maintainer**: RPA4ALL Team
