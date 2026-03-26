#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Uso:
  nas_tape_ops.sh status [--tape <barcode_ou_serial>]
  nas_tape_ops.sh eject --tape <barcode_ou_serial>
  nas_tape_ops.sh bench-rw --tape <barcode_ou_serial> [--size-mb N] --yes-destructive

Exemplos:
  nas_tape_ops.sh status
  nas_tape_ops.sh status --tape SG0R26
  nas_tape_ops.sh eject --tape SG0R26
  nas_tape_ops.sh bench-rw --tape SG0R26 --size-mb 512 --yes-destructive
EOF
}

require_cmds() {
  local missing=0
  for c in lsscsi mt sg_logs timeout; do
    if ! command -v "$c" >/dev/null 2>&1; then
      echo "Erro: comando ausente: $c" >&2
      missing=1
    fi
  done
  [[ "$missing" -eq 0 ]] || exit 1
}

trim() {
  sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//'
}

is_loaded() {
  local nst="$1"
  local out
  if ! out="$(timeout 8 mt -f "$nst" status 2>&1 || true)"; then
    return 1
  fi
  if grep -q "DR_OPEN" <<<"$out"; then
    return 1
  fi
  if grep -qi "No medium" <<<"$out"; then
    return 1
  fi
  grep -q "ONLINE" <<<"$out"
}

get_field_from_logs() {
  local sg="$1"
  local field="$2"
  timeout 10 sg_logs -p 0x17 "$sg" 2>/dev/null | awk -F':' -v k="$field" '$1 ~ k {print $2; exit}' | trim
}

list_tapes() {
  lsscsi -g | awk '
    $2=="tape" {
      st=""; sg="";
      for (i=1; i<=NF; i++) {
        if ($i ~ /^\/dev\/st[0-9]+$/) st=$i;
        if ($i ~ /^\/dev\/sg[0-9]+$/) sg=$i;
      }
      if (st != "" && sg != "") print st, sg;
    }
  '
}

resolve_nst_from_st() {
  local st="$1"
  local n="${st##*/st}"
  echo "/dev/nst${n}"
}

find_candidates() {
  local query="${1:-}"
  local st sg nst barcode serial
  while read -r st sg; do
    [[ -n "${st:-}" && -n "${sg:-}" ]] || continue
    nst="$(resolve_nst_from_st "$st")"
    barcode="$(get_field_from_logs "$sg" "Volume barcode")"
    serial="$(get_field_from_logs "$sg" "Volume serial number")"
    if [[ -n "$query" ]]; then
      shopt -s nocasematch
      if [[ "$barcode" == *"$query"* || "$serial" == *"$query"* ]]; then
        echo "$st|$nst|$sg|$barcode|$serial"
      fi
      shopt -u nocasematch
    else
      if is_loaded "$nst"; then
        echo "$st|$nst|$sg|$barcode|$serial"
      fi
    fi
  done < <(list_tapes)
}

print_status() {
  local st nst sg barcode serial
  echo "st|nst|sg|loaded|barcode|serial"
  while IFS='|' read -r st nst sg barcode serial; do
    [[ -n "${st:-}" ]] || continue
    if is_loaded "$nst"; then
      echo "$st|$nst|$sg|yes|$barcode|$serial"
    else
      echo "$st|$nst|$sg|no|$barcode|$serial"
    fi
  done < <(
    while read -r st sg; do
      nst="$(resolve_nst_from_st "$st")"
      barcode="$(get_field_from_logs "$sg" "Volume barcode")"
      serial="$(get_field_from_logs "$sg" "Volume serial number")"
      echo "$st|$nst|$sg|$barcode|$serial"
    done < <(list_tapes)
  )
}

unmount_ltfs_for_sg() {
  local sg="$1"
  local mp
  while read -r mp; do
    [[ -n "${mp:-}" ]] || continue
    umount "$mp" 2>/dev/null || umount -l "$mp" 2>/dev/null || true
  done < <(mount | awk -v s="ltfs:${sg}" '$1==s {print $3}')
}

kill_ltfs_for_sg() {
  local sg="$1"
  local pids
  pids="$(ps -ef | awk -v d="$sg" '$0 ~ /ltfs/ && $0 ~ ("devname=" d) {print $2}')"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
    sleep 1
    kill -9 $pids 2>/dev/null || true
  fi
}

safe_eject() {
  local st="$1" nst="$2" sg="$3"
  echo "Eject alvo: st=$st nst=$nst sg=$sg"
  unmount_ltfs_for_sg "$sg"
  kill_ltfs_for_sg "$sg"
  sync; sync
  timeout 20 mt -f "$nst" unlock >/dev/null 2>&1 || true
  if command -v sg_prevent >/dev/null 2>&1; then
    timeout 20 sg_prevent --allow "$sg" >/dev/null 2>&1 || true
  fi
  timeout 30 mt -f "$nst" rewind >/dev/null 2>&1 || true
  timeout 30 mt -f "$nst" rewoffl >/dev/null 2>&1 || true
  timeout 30 mt -f "$nst" offline >/dev/null 2>&1 || true
  timeout 30 mt -f "$nst" eject >/dev/null 2>&1 || true

  local out
  out="$(timeout 10 mt -f "$nst" status 2>&1 || true)"
  if grep -q "DR_OPEN" <<<"$out" || grep -qi "No medium" <<<"$out"; then
    echo "OK: fita ejetada ($nst)"
  else
    echo "ATENCAO: estado apos eject requer validacao manual."
    echo "$out"
    return 1
  fi
}

bench_rw() {
  local nst="$1" size_mb="$2" destructive_ok="$3"
  if [[ "$destructive_ok" != "yes" ]]; then
    echo "Erro: bench-rw exige --yes-destructive" >&2
    return 1
  fi

  echo "Benchmark RW em $nst (append no EOD), tamanho=${size_mb}MiB"
  timeout 30 mt -f "$nst" status >/dev/null
  timeout 60 mt -f "$nst" eod

  echo "[WRITE]"
  (dd if=/dev/zero of="$nst" bs=1M count="$size_mb" status=progress) 2>&1
  timeout 30 mt -f "$nst" weof 1

  echo "[READBACK]"
  timeout 30 mt -f "$nst" bsf 1 || true
  (dd if="$nst" of=/dev/null bs=1M iflag=fullblock count="$size_mb" status=progress) 2>&1

  timeout 60 mt -f "$nst" rewind || true
}

OP="${1:-}"
shift || true
TAPE_QUERY=""
SIZE_MB=512
DESTRUCTIVE_OK="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tape)
      TAPE_QUERY="${2:-}"
      shift 2
      ;;
    --size-mb)
      SIZE_MB="${2:-512}"
      shift 2
      ;;
    --yes-destructive)
      DESTRUCTIVE_OK="yes"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argumento invalido: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmds

case "$OP" in
  status)
    print_status
    if [[ -n "$TAPE_QUERY" ]]; then
      echo
      echo "Filtro por tape='$TAPE_QUERY':"
      find_candidates "$TAPE_QUERY" || true
    fi
    ;;
  eject)
    [[ -n "$TAPE_QUERY" ]] || { echo "Erro: informe --tape <barcode_ou_serial>" >&2; exit 1; }
    mapfile -t matches < <(find_candidates "$TAPE_QUERY")
    [[ "${#matches[@]}" -ge 1 ]] || { echo "Erro: fita '$TAPE_QUERY' nao encontrada." >&2; exit 1; }
    if [[ "${#matches[@]}" -gt 1 ]]; then
      echo "Erro: consulta ambigua para '$TAPE_QUERY':" >&2
      printf '%s\n' "${matches[@]}" >&2
      exit 1
    fi
    IFS='|' read -r st nst sg barcode serial <<<"${matches[0]}"
    safe_eject "$st" "$nst" "$sg"
    ;;
  bench-rw)
    [[ -n "$TAPE_QUERY" ]] || { echo "Erro: informe --tape <barcode_ou_serial>" >&2; exit 1; }
    mapfile -t matches < <(find_candidates "$TAPE_QUERY")
    [[ "${#matches[@]}" -ge 1 ]] || { echo "Erro: fita '$TAPE_QUERY' nao encontrada." >&2; exit 1; }
    if [[ "${#matches[@]}" -gt 1 ]]; then
      echo "Erro: consulta ambigua para '$TAPE_QUERY':" >&2
      printf '%s\n' "${matches[@]}" >&2
      exit 1
    fi
    IFS='|' read -r _st nst _sg _barcode _serial <<<"${matches[0]}"
    bench_rw "$nst" "$SIZE_MB" "$DESTRUCTIVE_OK"
    ;;
  *)
    usage
    exit 1
    ;;
esac
