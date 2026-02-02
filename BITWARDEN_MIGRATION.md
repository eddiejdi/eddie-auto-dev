# Bitwarden Migration Guide

## Purpose
Migrate secrets from the local `tools/simple_vault` to Bitwarden for centralized, secure secrets management.

## Prerequisites
- Bitwarden CLI (`bw`) installed (✓ completed)
- Authenticated Bitwarden account
- Access to homelab for credential rotation

## Step 1: Authenticate Bitwarden

```bash
# Login to your Bitwarden account
bw login edenilson.teixeira@rpa4all.com

# Unlock and export session token
export BW_SESSION=$(bw unlock --raw)
```

## Step 2: Run Migration Script

```bash
# Execute the migration from local vault to Bitwarden
./tools/simple_vault/migrate_to_bitwarden.sh
```

This script will:
- Migrate plain-text secrets from `tools/simple_vault/secrets/` to Bitwarden secure notes
- Create a login entry for the exposed OpenWebUI credential (marked for rotation)
- Generate a migration log at `tools/simple_vault/bw_migration_log.json`

## Step 3: Rotate OpenWebUI Password

The old password (`Eddie@2026`) was exposed in commit `e293156fd40445cf6931b0879d2b39466e792415` and has been detected by GitGuardian. It **MUST be rotated**.

### On Homelab

```bash
ssh homelab@192.168.15.2

# Get the new password from GitHub secrets (or from Bitwarden)
# New password: Ae9Jvoc5P9BqO9rI-TLx1tqV_J3HeEgxvbpSUvxSJrw

CURRENT_PASSWORD="Eddie@2026" \
NEW_PASSWORD="Ae9Jvoc5P9BqO9rI-TLx1tqV_J3HeEgxvbpSUvxSJrw" \
bash /home/edenilson/eddie-auto-dev/scripts/rotate_openwebui_password.sh
```

### Verify Password Change

```bash
# Test with new password
./scripts/test_openwebui_all.sh
```

## GitHub Actions Secrets

The new credentials have been automatically set in GitHub Actions:
- `OPENWEBUI_EMAIL`: `edenilson.adm@gmail.com`
- `OPENWEBUI_PASSWORD`: (new rotated password)

The workflow `.github/workflows/rotate-openwebui-api-key.yml` now uses these secrets instead of hardcoded values.

## Cleanup

After successful migration:

```bash
# Remove plain-text files from vault (do NOT commit to git)
rm tools/simple_vault/secrets/*.txt

# Keep GPG-encrypted backups for disaster recovery
# They are already in .gitignore
```

## References

- GitGuardian finding: https://dashboard.gitguardian.com (Incident #24880422)
- PR #33: Workflow fix (removed hardcoded password)
- PR #34: Formatting fixes
- PR #?: This migration guide and scripts
