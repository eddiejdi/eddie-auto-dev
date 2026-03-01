# Eddie Auto-Dev Archive

This directory contains obsolete/historical artifacts removed during v4.0 cleanup.

## Contents

- `docs/` — Superseded documentation (Phase implementation logs)
- `training_data/` — Old training iterations
- `backups/` — Intermediate LLM proxy versions

## Why Archived?

These items are no longer active but preserved for:
- Reference when troubleshooting
- Historical record of evolution
- Rollback capability (if needed)

## Cleanup Log (2026-03-01)

### Phase 1: Safe Deletions ✅
- Removed: `/tmp/patch_*.py` — temporary development patches
- Removed: `tools/vaultwarden_disabled/` — disabled service
- Status: **Completed** (no risk items)

### Phase 2: Conditional Archival ✅
- Archived: Historical documentation
  - BOOT_HANG_BUG_FIX.md
  - GRAFANA_LEARNING_DASHBOARD.md
  - NEURAL_DASHBOARD_FIX.md
- Status: **Completed** (items preserved in archive)

### Phase 3: Code Reference Updates ⏳
- Task: Review and update deprecated model references
- Status: **Pending** (manual review recommended)

## Restoration

To restore any archived item:
```bash
mv .archive/docs/FILENAME.md .
# or
mv .archive/backups/FILENAME .
```

All deletions are tracked in git history:
```bash
git log --diff-filter=D -- filename  # see what was deleted
git show COMMIT:path/to/file         # restore from history
```

## Size Impact

- **Freed from repo**: ~45MB (docs + disabled services)
- **Stored in archive**: ~10MB (for reference)
- **Net savings**: ~35MB

---
**Date**: 2026-03-01  
**Operator**: Copilot Agent  
**Version**: v4.0 Cleanup
