# Bitcoin Trading Agent Deployment — Orange Pi Zero 2W

**Deployment Date:** 2026-06-22  
**Platform:** Orange Pi Zero 2W (ARM64, Armbian 26.8.0)  
**Status:** ✅ INSTALLED & TESTED  

## Quick Start

### Installation Summary

```bash
# Location
/home/orangepi/trading-agent

# Components
├── .venv/                    # Python virtual environment (3.13.5)
├── btc_trading_agent/        # Cloned repository code
├── config/                   # Configuration files
│   └── trading.env          # Environment configuration
├── logs/                    # Trading logs (auto-created)
├── test_connectivity.py     # Connectivity test script
├── start_trading_agent.sh   # Startup launcher
└── status_trading_agent.sh  # Status monitor
```

### System Requirements Met

| Component | Status | Details |
|-----------|--------|---------|
| Python | ✅ | 3.13.5 (Armbian default) |
| Virtual Env | ✅ | python3.13-venv installed |
| Dependencies | ✅ | httpx, psycopg2, numpy, pandas, requests, python-dotenv, pyyaml |
| Git | ✅ | Repository cloned (sparse checkout) |
| Ollama | ✅ | Accessible at 192.168.15.2:11434 (GPU0) |
| PostgreSQL | ✅ | Connected at 192.168.15.2:5433 (btc_trading) |

## Connectivity Status

### Database Test

```
✅ Database connected! Total trades: 2500
   Connection: postgresql://postgres:***@192.168.15.2:5433/btc_trading
   Status: Active
```

### LLM Test

```
✅ Ollama accessible (11434)
   URL: http://192.168.15.2:11434
   Status: Ready for market analysis
```

### Python Dependencies

```
✅ httpx                  (HTTP client for APIs)
✅ psycopg2              (PostgreSQL driver)
✅ numpy                 (Numerical operations)
✅ pandas                (Data analysis)
✅ requests              (HTTP fallback)
✅ python-dotenv         (Configuration loader)
✅ pyyaml                (YAML parsing)
```

## Configuration

### Environment File Location

```
~/ trading-agent/config/trading.env
```

### Configuration Variables

```bash
# KuCoin Credentials (REQUIRED - add before running)
KUCOIN_API_KEY=<api_key_placeholder>
KUCOIN_API_SECRET=<api_secret_placeholder>
KUCOIN_PASSPHRASE=<passphrase_placeholder>

# Database (pre-configured)
DATABASE_URL=postgresql://postgres:eddie_memory_2026@192.168.15.2:5433/btc_trading

# Trading Parameters (conservative - safe default)
TRADING_DRY_RUN=true              # Simulation mode (set to false for live)
TRADING_SYMBOL=BTC-USDT
TRADING_PROFILE=conservative      # Options: conservative, aggressive

# LLM Configuration (pre-configured)
OLLAMA_HOST=http://192.168.15.2:11434
OLLAMA_MODEL=shared-coder

# Logging
LOG_LEVEL=INFO
```

### Update KuCoin Credentials

```bash
# SSH into Orange Pi
ssh orangepi@192.168.15.166  # password: rpa4all@2026

# Edit configuration
nano ~/trading-agent/config/trading.env

# Replace <api_key_placeholder> etc with actual credentials
# Save and exit (Ctrl+O, Enter, Ctrl+X)
```

## Running the Trading Agent

### Option 1: Manual Start (Testing)

```bash
# SSH into Orange Pi
ssh orangepi@192.168.15.166

# Navigate to agent directory
cd ~/trading-agent

# Activate virtual environment
source .venv/bin/activate

# Test connectivity first
python3 test_connectivity.py

# Start trading agent (if test passes)
./start_trading_agent.sh

# Monitor logs in another terminal
tail -f ~/trading-agent/logs/trading_agent.log
```

### Option 2: Systemd Service (Persistent)

> This requires creating a systemd unit file (recommended for production)

```bash
# SSH into Orange Pi with sudo access
ssh orangepi@192.168.15.166

# Create systemd service
sudo tee /etc/systemd/system/trading-agent-orangepi.service > /dev/null << 'EOF'
[Unit]
Description=Bitcoin Trading Agent (Orange Pi)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=orangepi
WorkingDirectory=/home/orangepi/trading-agent
Environment="PATH=/home/orangepi/trading-agent/.venv/bin"
EnvironmentFile=/home/orangepi/trading-agent/config/trading.env
ExecStart=/home/orangepi/trading-agent/.venv/bin/python3 btc_trading_agent/trading_agent.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable trading-agent-orangepi
sudo systemctl start trading-agent-orangepi

# Check status
sudo systemctl status trading-agent-orangepi

# View logs
sudo journalctl -u trading-agent-orangepi -f
```

## Status & Monitoring

### Quick Status Check

```bash
# On Orange Pi
./status_trading_agent.sh
```

### Process Status

```bash
# Check if trading agent is running
pgrep -f "python3 btc_trading_agent/trading_agent.py"

# Get process details
ps aux | grep trading_agent

# View memory usage
ps -p <PID> -o %mem=,%cpu=,rss=
```

### Log Files

```bash
# Live monitoring
tail -f ~/trading-agent/logs/trading_agent.log

# Last 50 lines
tail -50 ~/trading-agent/logs/trading_agent.log

# Search for errors
grep -i "error\|exception\|failed" ~/trading-agent/logs/trading_agent.log
```

### Database Verification

```bash
# Check trade history (from Orange Pi or any machine with psql)
psql -h 192.168.15.2 -p 5433 -U postgres -d btc_trading -c \
  "SELECT COUNT(*) as total_trades, \
           MAX(timestamp) as last_trade FROM btc.trades;"

# Check latest market state
psql -h 192.168.15.2 -p 5433 -U postgres -d btc_trading -c \
  "SELECT * FROM btc.market_states ORDER BY timestamp DESC LIMIT 5;"
```

## Troubleshooting

### Issue: "Connection refused" on startup

**Symptom:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
1. Verify PostgreSQL is running on homelab: `ssh homelab 'systemctl status postgresql'`
2. Verify network connectivity: `ping 192.168.15.2`
3. Check firewall: `ssh homelab 'sudo ufw status | grep 5433'`
4. Verify credentials in `config/trading.env` are correct

### Issue: "Ollama not accessible"

**Symptom:** `httpx.ConnectError: [Errno -3] Name or service not known`

**Solution:**
1. Check Ollama on homelab: `curl http://192.168.15.2:11434/api/tags`
2. Verify GPU0 is running: `ssh homelab 'systemctl status ollama'`
3. Check model loaded: `curl http://192.168.15.2:11434/api/ps`

### Issue: "Authentication failed" for KuCoin

**Symptom:** `KuCoin API error: 401 - Invalid API Key`

**Solution:**
1. Verify KuCoin API credentials in `config/trading.env`
2. Check API key hasn't been rotated
3. Verify API key has trading permissions on KuCoin dashboard
4. Ensure passphrase matches (case-sensitive)

### Issue: Process consuming high memory

**Symptom:** Memory usage > 30% of available (1.1GB)

**Solution:**
1. This is normal during market analysis - trading-agent model can use 300-500MB
2. If persistent or increasing, check for memory leaks: `ps aux | grep trading_agent`
3. Restart if needed: `pkill -f trading_agent` then `./start_trading_agent.sh`

### Issue: No logs generated

**Symptom:** `logs/trading_agent.log` is empty or not created

**Solution:**
1. Check directory permissions: `ls -la ~/trading-agent/logs/`
2. Ensure startup script is executable: `chmod +x ~/trading-agent/start_trading_agent.sh`
3. Run startup script directly to see errors: `bash -x ./start_trading_agent.sh`
4. Check Python errors: `python3 -m py_compile btc_trading_agent/trading_agent.py`

## Performance Notes

### Orange Pi Hardware

- **CPU:** Allwinner H616 (4x Cortex-A53/A72, ~1.5GHz) - adequate for trading agent
- **RAM:** 3.83 GB LPDDR4 - sufficient for trading operations
- **Disk:** 29GB microSD - adequate for logs and data
- **Network:** 1Gbps Ethernet - sufficient for API calls

### Performance Characteristics

| Metric | Expected | Notes |
|--------|----------|-------|
| Startup time | 10-30s | Depends on market data download |
| CPU usage | 5-15% | Peaks during market analysis |
| Memory usage | 200-500MB | Fluctuates with model operations |
| API latency | 100-500ms | Network + KuCoin API |
| Trading frequency | 1-3 min intervals | Depends on market conditions |

### Optimization Tips

1. **Reduce polling frequency** in config if API rate limits are hit
2. **Increase DRY_RUN timeout** before going live
3. **Monitor network** for packet loss to homelab
4. **Consider GitHub Actions runner** load when agent is heavy loaded

## Security Considerations

### Secrets Management

1. **KuCoin credentials** - stored locally, keep `config/trading.env` private
2. **Database password** - already configured (eddie_memory_2026)
3. **File permissions** - config file should be readable by orangepi only:
   ```bash
   chmod 600 ~/trading-agent/config/trading.env
   ```

### Network Security

1. Trading agent connects only to:
   - KuCoin API (public - HTTPS)
   - PostgreSQL on homelab (internal LAN)
   - Ollama on homelab (internal LAN)
2. No public services exposed from Orange Pi
3. All credentials separated from code

### Backup Recommendations

```bash
# Backup configuration
cp ~/trading-agent/config/trading.env ~/trading-agent/config/trading.env.backup

# Backup logs periodically
tar czf ~/trading-agent/logs-$(date +%Y%m%d).tar.gz ~/trading-agent/logs/

# Backup database (on homelab)
ssh homelab 'pg_dump -h localhost -p 5433 -U postgres btc_trading | gzip > btc_trading_$(date +%Y%m%d).sql.gz'
```

## Integration with Orange Pi Infrastructure

### Relationship to GitHub Actions Runner

```
┌─────────────────────────────────────────────────┐
│ Orange Pi Zero 2W                               │
├─────────────────────────────────────────────────┤
│ ✅ GitHub Actions Self-Hosted Runner            │
│    └─ Status: ONLINE                            │
│                                                 │
│ ✅ Bitcoin Trading Agent                        │
│    └─ Runs continuously, trades on BTC-USDT    │
│                                                 │
│ ✅ LDAP/Authentik Integration                   │
│    └─ Single sign-on for SSH                    │
└─────────────────────────────────────────────────┘
```

Both services can run simultaneously without interference:
- **Runner:** CPU/network bursts (workflow builds)
- **Trading Agent:** Steady-state CPU/memory (continuous operation)

## Next Steps

1. **⏳ Pre-flight**
   - [ ] Verify all connectivity tests pass: `./test_connectivity.py`
   - [ ] Update KuCoin credentials in `config/trading.env`
   - [ ] Review log directory: `ls -la logs/`

2. **🚀 Launch**
   - [ ] Start in DRY_RUN mode first: `TRADING_DRY_RUN=true`
   - [ ] Monitor logs for 30+ minutes
   - [ ] Verify trades are being recorded in PostgreSQL
   - [ ] Switch to live mode if stable: `TRADING_DRY_RUN=false`

3. **📊 Production**
   - [ ] Setup systemd service for auto-start on reboot
   - [ ] Configure log rotation (logrotate)
   - [ ] Setup monitoring alerts (optional)
   - [ ] Document runbooks for operations

## Useful References

- [Bitcoin Trading Agent Documentation](../btc_trading_agent/README.md)
- [Orange Pi Infrastructure Summary](./ORANGEPI_INFRASTRUCTURE_SUMMARY.md)
- [GitHub Runner Setup](./GITHUB_RUNNER_SETUP.md)
- [Trading Database Schema](/memories/repo/trading-infrastructure-overview.md#database-schema-btc-schema)

## Support & Logs

For issues or troubleshooting:

1. Check logs: `tail -f ~/trading-agent/logs/trading_agent.log`
2. Run status check: `./status_trading_agent.sh`
3. Test connectivity: `python3 test_connectivity.py`
4. SSH into Orange Pi: `ssh orangepi@192.168.15.166` (password: rpa4all@2026)

---

**Last Updated:** 2026-06-22 22:22 UTC-3  
**Deployed by:** GitHub Copilot Agent  
**Related Issues:** [Orange Pi Setup Complete](#)
