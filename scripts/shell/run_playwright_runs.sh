OUT=/tmp/openwebui_playwright_runs.jsonl
: > 
for i in 1
2
3
4
5
6
7
8
9
10; do
  ts=2026-01-25T18:45:57-05:00
  out=python3: can't open file '/home/homelab/openwebui_playwright_check.py': [Errno 13] Permission denied
  code=2
  esc=""
  printf '%s\n' "i": >> 
  sleep 1
done
# summary
python3 - <<PY > /tmp/openwebui_playwright_runs_summary.txt
import json
c_pass=0
c_fail=0
with open('/tmp/openwebui_playwright_runs.jsonl') as f:
    for l in f:
        j=json.loads(l)
        if j.get('exit',1)==0:
            c_pass+=1
        else:
            c_fail+=1
print('passed',c_pass,'failed',c_fail)
PY

echo WROTE cat > /home/homelab/run_playwright_runs.sh <<'SH'
OUT=/tmp/openwebui_playwright_runs.jsonl
: > 
for i in 1
2
3
4
5
6
7
8
9
10; do
  ts=2026-01-25T18:45:57-05:00
  out=python3: can't open file '/home/homelab/openwebui_playwright_check.py': [Errno 13] Permission denied
  code=2
  esc=""
  printf '%s\n' "ts":"" >> 
  sleep 1
done
# summary
python3 - <<PY > /tmp/openwebui_playwright_runs_summary.txt
import json
c_pass=0
c_fail=0
with open('/tmp/openwebui_playwright_runs.jsonl') as f:
    for l in f:
        j=json.loads(l)
        if j.get('exit',1)==0:
            c_pass+=1
        else:
            c_fail+=1
print('passed',c_pass,'failed',c_fail)
PY

echo WROTE cat > /home/homelab/run_playwright_runs.sh <<'SH'
OUT=/tmp/openwebui_playwright_runs.jsonl
: > 
for i in 1
2
3
4
5
6
7
8
9
10; do
  ts=2026-01-25T18:45:57-05:00
  out=python3: can't open file '/home/homelab/openwebui_playwright_check.py': [Errno 13] Permission denied
  code=2
  esc=""
  printf '%s\n' "exit": >> 
  sleep 1
done
# summary
python3 - <<PY > /tmp/openwebui_playwright_runs_summary.txt
import json
c_pass=0
c_fail=0
with open('/tmp/openwebui_playwright_runs.jsonl') as f:
    for l in f:
        j=json.loads(l)
        if j.get('exit',1)==0:
            c_pass+=1
        else:
            c_fail+=1
print('passed',c_pass,'failed',c_fail)
PY

echo WROTE cat > /home/homelab/run_playwright_runs.sh <<'SH'
OUT=/tmp/openwebui_playwright_runs.jsonl
: > 
for i in 1
2
3
4
5
6
7
8
9
10; do
  ts=2026-01-25T18:45:58-05:00
  out=python3: can't open file '/home/homelab/openwebui_playwright_check.py': [Errno 13] Permission denied
  code=2
  esc=""
  printf '%s\n' "out": >> 
  sleep 1
done
# summary
python3 - <<PY > /tmp/openwebui_playwright_runs_summary.txt
import json
c_pass=0
c_fail=0
with open('/tmp/openwebui_playwright_runs.jsonl') as f:
    for l in f:
        j=json.loads(l)
        if j.get('exit',1)==0:
            c_pass+=1
        else:
            c_fail+=1
print('passed',c_pass,'failed',c_fail)
PY

echo WROTE and /tmp/openwebui_playwright_runs_summary.txt
