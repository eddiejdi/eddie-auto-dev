# Crypto Agent Systemd Drop-in Configuration

Drop-in configuration files for `crypto-agent@.service` template.

## Files

- **common.conf**: Main configuration with environment variables and dependencies
- **cpuaffinity.conf**: CPU core affinity settings
- **deps.conf**: Service dependencies

## Important Configuration Changes

### AI Trade Controls Mode (2026-04-25)

**Added**: `Environment=OLLAMA_TRADE_PARAMS_MODE=apply`

This enables dynamic parameter adjustment by the AI system. The AI will now actively adjust trading parameters based on market conditions:

- `min_confidence`: ±10% of baseline
- `min_trade_interval`: 50-180% of baseline
- `max_position_pct`: up to config limit
- `max_positions`: up to config limit

**Previous behavior** (`shadow` mode): AI generated suggestions but they were not applied.

**Current behavior** (`apply` mode): AI suggestions are blended (35-50%) with baseline values and applied automatically.

## Deployment

1. Copy files to `/etc/systemd/system/crypto-agent@.service.d/`
2. Replace placeholders in `common.conf` with actual secrets from Bitwarden
3. Reload systemd: `sudo systemctl daemon-reload`
4. Restart services: `sudo systemctl restart crypto-agent@*.service`

## Security Notes

- **Never commit real secrets** to git
- Use Bitwarden CLI (`bw get password shared/...`) to retrieve secrets
- Template file uses placeholders: `<from_bitwarden>`, `PASSWORD`, etc.
