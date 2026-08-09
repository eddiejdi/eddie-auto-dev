#!/bin/bash
OUT=/home/homelab/monitor_status.log
echo "Monitor start $(date)" >> "$OUT"
while true; do
  echo "=== $(date) ===" >> "$OUT"
  echo "docling pids:" >> "$OUT"
  pgrep -af docling >> "$OUT" 2>&1 || true
  echo "generate_qa pids:" >> "$OUT"
  pgrep -af generate_qa_from_docling.py >> "$OUT" 2>&1 || true
  echo "gdrive_fetch pids:" >> "$OUT"
  pgrep -af gdrive_fetch_direct.py >> "$OUT" 2>&1 || true
  echo "json count and size:" >> "$OUT"
  if [ -d /home/homelab/gdrive_docling_out ]; then
    find /home/homelab/gdrive_docling_out -type f | wc -l >> "$OUT" 2>&1
    du -sh /home/homelab/gdrive_docling_out >> "$OUT" 2>&1
  else
    echo "no dir" >> "$OUT"
  fi
  echo "training.jsonl:" >> "$OUT"
  ls -l /home/homelab/gdrive_docs/training.jsonl >> "$OUT" 2>&1 || true
  echo "tail docling_extract.log:" >> "$OUT"
  tail -n 40 /home/homelab/docling_extract.log >> "$OUT" 2>&1 || true
  echo "tail generate_qa.log:" >> "$OUT"
  tail -n 40 /home/homelab/generate_qa.log >> "$OUT" 2>&1 || true
  echo "" >> "$OUT"
  sleep 30
done
