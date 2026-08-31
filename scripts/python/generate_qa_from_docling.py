#!/usr/bin/env python3
import json, os, time, subprocess, re
from glob import glob

DOC_OUT_DIR = '/home/homelab/gdrive_docling_out'
TRAINING_FILE = '/home/homelab/gdrive_docs/training.jsonl'
MODEL = 'llama3.2:3b'
MAX_WAIT = 300
POLL = 5

os.makedirs(os.path.dirname(TRAINING_FILE), exist_ok=True)
seen = set()


def ensure_text(t):
    if t is None:
        return ''
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        for k in ('text', 'content', 'body', 'plain_text'):
            if k in t and isinstance(t[k], str):
                return t[k]
        return json.dumps(t, ensure_ascii=False)
    if isinstance(t, list):
        parts = []
        for item in t:
            if isinstance(item, dict):
                parts.append(item.get('text', ''))
            else:
                parts.append(str(item))
        return '\n\n'.join(parts)
    return str(t)


def extract_text_from_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            obj = json.load(f)
    except Exception:
        return None, None
    title = obj.get('title') or obj.get('file_name') or os.path.basename(path)
    text = None
    for k in ('text', 'content', 'body', 'plain_text'):
        if k in obj and obj[k]:
            text = obj[k]
            break
    if not text:
        pages = obj.get('pages') or obj.get('page_texts')
        if pages and isinstance(pages, list):
            parts = []
            for p in pages:
                if isinstance(p, dict):
                    parts.append(p.get('text', ''))
                else:
                    parts.append(str(p))
            text = '\n\n'.join(parts)
    text = ensure_text(text)
    return title or os.path.basename(path), (text or '')


def parse_ollama_output(out_text):
    out_text = (out_text or '').strip()
    if not out_text:
        return []
    results = []
    # 1) Try JSON lines
    for line in out_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            results.append(obj)
        except Exception:
            pass
    if results:
        return results
    # 2) Find JSON objects anywhere in text
    for m in re.finditer(r'\{(?:[^{}]|\n)*?\}', out_text, re.DOTALL):
        s = m.group(0)
        try:
            obj = json.loads(s)
            results.append(obj)
        except Exception:
            continue
    if results:
        return results
    # 3) Fallback: extract Q/A patterns
    pairs = []
    # split by double newline blocks
    blocks = re.split(r'\n\s*\n', out_text)
    for b in blocks:
        q = None
        a = None
        m = re.search(r'Q[:\-]\s*(.+)', b, re.I)
        n = re.search(r'A[:\-]\s*(.+)', b, re.I)
        if m and n:
            q = m.group(1).strip()
            a = n.group(1).strip()
            pairs.append({'prompt': q, 'completion': a})
            continue
        # numbered list like "1) Question\nAnswer"
        m = re.findall(r'\d+\)\s*(.+?)(?:\n|$)', b)
        if m and len(m) >= 2:
            for i in range(0, len(m), 2):
                try:
                    prompt = m[i].strip()
                    completion = m[i+1].strip()
                    pairs.append({'prompt': prompt, 'completion': completion})
                except Exception:
                    continue
    return pairs


start = time.time()
while True:
    json_files = glob(os.path.join(DOC_OUT_DIR, '**', '*.json'), recursive=True)
    if json_files:
        break
    if time.time() - start > MAX_WAIT:
        print('Timeout waiting for docling JSON files in', DOC_OUT_DIR)
        raise SystemExit(1)
    print('Waiting for docling output...')
    time.sleep(POLL)

json_files = sorted(json_files)
print('Found', len(json_files), 'json files')
count = 0
with open(TRAINING_FILE, 'a', encoding='utf-8') as out:
    for jf in json_files:
        try:
            title, text = extract_text_from_json(jf)
            if not text or not text.strip():
                continue
            key = title + '|' + (text[:200])
            if key in seen:
                continue
            seen.add(key)
            prompt_in = f"Title: {title}\n\n{text[:6000]}\n\n---\nRespond with up to 3 JSON lines with keys 'prompt' and 'completion'."
            print('Processing', jf)
            try:
                p = subprocess.run(['ollama', 'run', MODEL], input=prompt_in, text=True, capture_output=True, timeout=240)
            except Exception as e:
                print('ollama run failed for', jf, e)
                continue
            out_text = p.stdout or ''
            if not out_text.strip():
                print('ollama returned empty output for', jf)
                continue
            objs = parse_ollama_output(out_text)
            if not objs:
                print('No parseable Q/A found in ollama output for', jf)
                # save raw output for debugging
                try:
                    rawp = '/home/homelab/generate_qa_raw/' + os.path.basename(jf) + '.out'
                    with open(rawp, 'w', encoding='utf-8') as rf:
                        rf.write(out_text)
                    print('Saved raw output to', rawp)
                except Exception:
                    pass
                continue
            for obj in objs:
                # normalize keys
                if not isinstance(obj, dict):
                    continue
                prompt = obj.get('prompt') or obj.get('question') or obj.get('q')
                completion = obj.get('completion') or obj.get('answer') or obj.get('a')
                if prompt and completion:
                    out.write(json.dumps({'prompt': prompt, 'completion': completion}, ensure_ascii=False) + '\n')
                    out.flush()
                    count += 1
        except Exception as e:
            print('Error processing', jf, e)

print('Q&A generation finished. wrote', count, 'pairs to', TRAINING_FILE)
