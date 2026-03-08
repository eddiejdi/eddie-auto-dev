# 🧹 Shared Auto-Dev: Cleanup & Sanification Recommendations (v4.0)

**Date**: 2026-03-01  
**Status**: Ready for Review & Implementation  
**Impact**: Reduces clutter, improves maintainability, ~100-200MB freed

---

## 📋 Summary

After thorough analysis of the codebase evolution from v1.0 → v4.0, the following components are obsolete and can be safely removed:

| Category | Item | Status | Action | Impact |
|----------|------|--------|--------|--------|
| **Models** | shared-coder | Deprecated | Remove | Models freed in VRAM |
| **Models** | qwen2.5-coder:* | Deprecated | Remove | Use qwen3:* instead |
| **Infrastructure** | Fly.io tunnel | Removed | Delete | Use Cloudflare instead |
| **Integration** | SmartLife install_tunnel.sh | Deprecated | Archive | Cloudflared is canonical |
| **Integration** | Home Assistant v2 API | Deprecated | Archive | Use new REST endpoints |
| **Storage** | Vaultwarden_disabled/ | Disabled | Delete | Not used anymore |
| **Artifacts** | Training data 2026-01-* | Archive | Move to archive/ | Old iterations |
| **Development** | /tmp patch files | Temporary | Delete | Development only |
| **Backups** | llm_optimizer*.bak_* | Keep | Move to .archive/backups | Safety net |
| **Docs** | Multiple *_old.md files | Archive | Move to docs/archive | Historical reference |

---

## 🎯 TIER 1: SAFE DELETIONS (No Risk)

### 1.1 Temporary Patch Files in `/tmp/`
**Files**:
- `/tmp/patch_api_chat_v3.py`
- `/tmp/patch_dual_gpu_v2.py`
- `/tmp/patch_disable_dualgpu.py`
- `/tmp/patch_use_qwen3_8b.py`
- `/tmp/patch_redirect_qwen2.5.py`
- `/tmp/add_ollama_endpoints*.py`
- `/tmp/llm_optimizer_remote.py` (staging copy)

**Reason**: These are development/staging artifacts, not part of production

**Command**:
```bash
rm -f /tmp/patch_*.py /tmp/add_ollama*.py /tmp/llm_optimizer_remote.py
```

---

### 1.2 Vaultwarden Disabled Directory
**Path**: `tools/vaultwarden_disabled/`

**Reason**: Service disabled; not used in current architecture

**Command**:
```bash
rm -rf tools/vaultwarden_disabled/
```

---

### 1.3 Fly.io Tunnel References
**Files to check**:
- `install_tunnel.sh` (line 5: marked as "deprecated")
- `index_homelab_docs.py` (line 86: marked as "deprecated")
- References in `flyio-tunnel/` (if exists)

**Reason**: Replaced by `cloudflared` tunnel service

**Command**:
```bash
# Check for any remaining Fly.io references
grep -r "flyio\|fly.io" . --include="*.py" --include="*.sh" | grep -v node_modules | grep -v ".git"

# Remove if found (example):
rm -rf tools/flyio-tunnel/  # If exists
```

---

## 🎯 TIER 2: CONDITIONAL DELETIONS (Review First)

### 2.1 Training Data Archives
**Path**: `training_data/training_2026-01*.jsonl`

**Reason**: 
- Training iterations from January 2026
- Superseded by current model state
- Can be archived for historical reference

**Estimated Size Freed**: ~50-100MB

**Command**:
```bash
mkdir -p .archive/training_data
mv training_data/training_2026-01*.jsonl .archive/training_data/
echo "✓ Moved old training data to .archive/"
```

---

### 2.2 LLM Model Backups (Old Versions)
**Location**: `/home/homelab/llm-optimizer/` on server

**Backups to Keep**:
- `llm_optimizer.py.bak_v3.0` → Keep (reference for dual-GPU v3.0)
- `llm_optimizer.py.bak_v2.3_pre_pipeline` → Can delete (intermediate state)
- `.bak_v2.0` and earlier → Can delete

**Command** (on homelab server):
```bash
# List backups
ls -lah /home/homelab/llm-optimizer/llm_optimizer.py.bak*

# Keep only v3.0 and current; archive others
mkdir -p /home/homelab/.archive/backups
mv /home/homelab/llm-optimizer/llm_optimizer.py.bak_v2* /home/homelab/.archive/backups/
```

---

### 2.3 Old Documentation Files
**Examples**:
- `DUAL_GPU_IMPLEMENTATION.md` (reference, not current)
- `CLINE_RESPONSE_FIX.md` (historical)
- `GRAFANA_LEARNING_DASHBOARD.md` (superseded)
- `BOOT_FIXES_2026-02-27.md` (historical)

**Action**: Move to `docs/archive/` for historical reference

**Command**:
```bash
mkdir -p docs/archive
mv DUAL_GPU_IMPLEMENTATION.md CLINE_RESPONSE_FIX.md GRAFANA_LEARNING_DASHBOARD.md docs/archive/
```

---

## 🎯 TIER 3: DEPRECATE IN-PLACE (Keep But Mark)

### 3.1 SmartLife Integration
**Path**: `smartlife_integration/`

**Status**: Partially deprecated (lines 79, 117-118 mark Home Assistant API as deprecated)

**Recommendation**: Keep but document as legacy; prefer new Home Assistant endpoints

**Action**: Add deprecation notice to `smartlife_integration/README.md`

```markdown
⚠️ **DEPRECATED - Use new Home Assistant REST API instead**
- Old method: `do_login_v3.py` (Home Assistant API, deprecated)
- New method: Use Home Assistant REST endpoints directly
```

---

### 3.2 Ollama Model References
**Current Issue**: Some references to `shared-coder` and `qwen2.5-coder` still exist

**Files to Update**:
- `dashboard/config.py` (lines 143, 148 reference v2 Modelfiles)
- `specialized_agents/config.py` (model context table)

**Recommendation**: Update all references to use `qwen3:*` models only

**Action**: Grep and update
```bash
grep -r "shared-coder\|qwen2\.5-coder" . --include="*.py" --include="*.md"
# Replace with qwen3 equivalents
```

---

## 📊 Storage Impact Assessment

| Item | Size | Action | Freed |
|------|------|--------|-------|
| `/tmp/patch_*.py` | ~150KB | Delete | 150KB |
| `training_data/2026-01-*.jsonl` | ~80MB | Archive | 80MB |
| `tools/vaultwarden_disabled/` | ~20MB | Delete | 20MB |
| `docs/historical_*.md` | ~10MB | Archive | 10MB |
| **Total Freed** | | | **~110MB** |

---

## ✅ Pre-Deletion Checklist

Before executing any deletions:

- [ ] **Backup**: `git commit -am "pre-cleanup backup"` or create full backup
- [ ] **Search**: Verify no active code references (grep -r)
- [ ] **Test**: Run `pytest -q` to ensure nothing breaks
- [ ] **Documentation**: Document what was removed in `CLEANUP_LOG.md`
- [ ] **Communication**: Notify team if shared infrastructure

---

## 🚀 Execution Plan (Phases)

### Phase 1: Safe Deletions (Low Risk)
**Duration**: <5 min  
**Risk**: Negligible

```bash
#!/bin/bash
set -e

echo "📦 Phase 1: Safe Deletions"

# 1. Remove temp patches
rm -f /tmp/patch_*.py /tmp/add_ollama*.py || true
echo "✓ Removed temp patches"

# 2. Remove unused dirs
rm -rf tools/vaultwarden_disabled/ || true
echo "✓ Removed vaultwarden_disabled"

# 3. Create archive dir
mkdir -p .archive/{training_data,backups,docs}

echo "✅ Phase 1 complete"
```

---

### Phase 2: Conditional Deletions (Review)
**Duration**: ~30 min  
**Risk**: Low (items can be restored from git history)

```bash
#!/bin/bash
echo "📦 Phase 2: Conditional Deletions"

# 1. Archive old training data
mv training_data/training_2026-01*.jsonl .archive/training_data/ 2>/dev/null || true
echo "✓ Archived old training data"

# 2. Archive old docs
for doc in DUAL_GPU_IMPLEMENTATION.md CLINE_RESPONSE_FIX.md GRAFANA_LEARNING_DASHBOARD.md; do
    [ -f "$doc" ] && mv "$doc" docs/archive/ && echo "✓ Archived $doc"
done

echo "✅ Phase 2 complete"
```

---

### Phase 3: Code Updates (Deprecations)
**Duration**: ~15 min  
**Risk**: Low (update references only)

```bash
#!/bin/bash
echo "📦 Phase 3: Update References"

# Find references to old models
echo "Checking for shared-coder references..."
grep -r "shared-coder\|qwen2\.5-coder" . --include="*.py" --include="*.md" | \
  grep -v ".git" | grep -v "__pycache__" | grep -v "node_modules" || echo "None found"

echo "✅ Phase 3 complete (manual update if needed)"
```

---

## 📝 Post-Cleanup Tasks

After successful cleanup:

1. **Commit**: `git add -A && git commit -m "chore: cleanup obsolete components (v4.0 preparation)"`
2. **Document**: Update [ARCHITECTURE.md](ARCHITECTURE.md) to reflect current state
3. **CI/CD**: Ensure ci pipeline still passes
4. **Archive**: Store `/tmp` cleanup in git history
5. **Notify**: Update team about storage freed

---

## 🔄 Archival Strategy

Create `.archive/` directory structure:

```
.archive/
├── training_data/
│   ├── training_2026-01*.jsonl
│   └── README.md (what these are, why archived)
├── backups/
│   ├── llm_optimizer.py.bak_v2.0
│   ├── llm_optimizer.py.bak_v2.3
│   └── README.md (restoration instructions)
├── docs/
│   ├── DUAL_GPU_IMPLEMENTATION.md
│   ├── CLINE_RESPONSE_FIX.md
│   ├── GRAFANA_LEARNING_DASHBOARD.md
│   └── README.md (historical reference index)
└── README.md (Archive Index)
```

**Archive README.md**:
```markdown
# Shared Auto-Dev Archive

This directory contains obsolete/historical artifacts from development iterations.

## Contents

- `training_data/` — Old training iterations (Jan 2026)
- `backups/` — Intermediate LLM proxy versions (v2.0-v2.3)
- `docs/` — Historical documentation from implementation phases

## Why Archived?

These items are superseded by current v4.0 implementation but kept for:
- Reference when troubleshooting
- Historical record of evolution
- Rollback capability (if needed)

## Restoration

To restore any item: `mv .archive/item /path/to/restore`
```

---

## ⚠️ Risk Assessment

| Phase | Risk Level | Rollback Effort | Recommendation |
|-------|-----------|-----------------|-----------------|
| Phase 1 | ✅ Negligible | <1 min (git restore) | **Execute** |
| Phase 2 | ✅ Low | ~5 min (git restore) | **Execute after review** |
| Phase 3 | ⚠️ Medium | ~30 min (code review) | **Execute carefully, test** |

---

## 🎯 Success Criteria

After cleanup:

- ✅ No broken imports (`pytest -q` passes)
- ✅ Storage freed: ~110MB documented
- ✅ Codebase cleaner, faster to navigate
- ✅ No references to deprecated models in active code
- ✅ Archive preserved for historical reference
- ✅ Git history intact (revertible if needed)

---

## 📎 Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) — Current system design
- [docs/diagrams/ecosystem_molecular.drawio](docs/diagrams/ecosystem_molecular.drawio) — Complete component diagram
- [docs/diagrams/llm_optimize.drawio](docs/diagrams/llm_optimize.drawio) — Token economy dashboard

---

**Next Steps**: Review this document, adjust if needed, then execute Phase 1-3 in order.
