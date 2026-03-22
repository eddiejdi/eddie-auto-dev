#!/usr/bin/env bash
set -euo pipefail

COMMAND=${1:-refresh}

LOGICAL_ROOT=${LOGICAL_ROOT:-/mnt/lto-archive}
CACHE_BRANCH=${CACHE_BRANCH:-/mnt/raid1/lto6-cache}
TAPE_BRANCHES=${TAPE_BRANCHES:-/mnt/lto6:/mnt/lto6b}
MIN_TARGET_TOTAL_BYTES=${MIN_TARGET_TOTAL_BYTES:-1099511627776}
MERGERFS_BIN=${MERGERFS_BIN:-/usr/bin/mergerfs}
MERGERFS_OPTIONS=${MERGERFS_OPTIONS:-allow_other,use_ino,cache.files=off,dropcacheonclose=true,category.create=ff,func.getattr=newest,fsname=lto-logical}
STATE_FILE=${STATE_FILE:-/run/lto-logical-mount.branches}


branch_total_bytes() {
  local branch=$1
  local blocks block_size
  blocks=$(stat -f -c '%b' "$branch")
  block_size=$(stat -f -c '%S' "$branch")
  echo $((blocks * block_size))
}


healthy_tape_branch() {
  local branch=$1
  [[ -d "$branch" ]] || return 1
  mountpoint -q "$branch" || return 1
  [[ $(branch_total_bytes "$branch") -ge ${MIN_TARGET_TOTAL_BYTES} ]] || return 1
}


build_branch_signature() {
  local branches=()
  [[ -d "$CACHE_BRANCH" ]] || {
    echo "cache branch is missing: $CACHE_BRANCH" >&2
    return 2
  }
  branches+=("$CACHE_BRANCH")

  local branch
  IFS=: read -r -a raw_tape_branches <<<"$TAPE_BRANCHES"
  for branch in "${raw_tape_branches[@]}"; do
    [[ -n "$branch" ]] || continue
    if healthy_tape_branch "$branch"; then
      branches+=("$branch")
    fi
  done

  local signature
  signature=$(IFS=:; echo "${branches[*]}")
  printf '%s\n' "$signature"
}


stop_mount() {
  if mountpoint -q "$LOGICAL_ROOT"; then
    if command -v fusermount >/dev/null 2>&1; then
      fusermount -u "$LOGICAL_ROOT" || umount "$LOGICAL_ROOT"
    else
      umount "$LOGICAL_ROOT"
    fi
  fi
  rm -f "$STATE_FILE"
}


refresh_mount() {
  command -v mount >/dev/null 2>&1 || {
    echo "mount command not available" >&2
    return 2
  }
  [[ -x "$MERGERFS_BIN" ]] || {
    echo "mergerfs binary not found: $MERGERFS_BIN" >&2
    return 2
  }

  local signature current_signature
  signature=$(build_branch_signature)
  current_signature=""
  if [[ -f "$STATE_FILE" ]]; then
    current_signature=$(<"$STATE_FILE")
  fi

  install -d "$LOGICAL_ROOT"
  if mountpoint -q "$LOGICAL_ROOT" && [[ "$current_signature" == "$signature" ]]; then
    printf '%s\n' "logical mount already up to date: $signature"
    return 0
  fi

  stop_mount || true
  mount -t fuse.mergerfs -o "$MERGERFS_OPTIONS" "$signature" "$LOGICAL_ROOT"
  for _ in $(seq 1 20); do
    if mountpoint -q "$LOGICAL_ROOT"; then
      break
    fi
    sleep 0.25
  done
  mountpoint -q "$LOGICAL_ROOT" || {
    echo "failed to mount logical root: $LOGICAL_ROOT" >&2
    return 1
  }
  printf '%s\n' "$signature" >"$STATE_FILE"
  printf '%s\n' "logical mount active: $signature"
}


print_status() {
  local signature
  signature=$(build_branch_signature)
  printf 'logical_root=%s\n' "$LOGICAL_ROOT"
  printf 'configured_branches=%s\n' "$signature"
  if mountpoint -q "$LOGICAL_ROOT"; then
    printf 'mounted=yes\n'
    findmnt "$LOGICAL_ROOT"
  else
    printf 'mounted=no\n'
  fi
}


case "$COMMAND" in
  refresh|start)
    refresh_mount
    ;;
  stop)
    stop_mount
    ;;
  status)
    print_status
    ;;
  branches)
    build_branch_signature
    ;;
  *)
    echo "usage: $0 {refresh|start|stop|status|branches}" >&2
    exit 2
    ;;
esac
