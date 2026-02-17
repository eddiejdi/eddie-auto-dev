"""ServerKnowledgeRAG
Standalone module for the Homelab Advisor Agent.
Provides a very small, dependency-free TF-based retriever suitable for
server knowledge RAG (short-term memory / retrieval for prompts).
"""
import os
import re
from collections import Counter as _Counter
import math
import subprocess

class ServerKnowledgeRAG:
    def __init__(self):
        self.documents = []
        self.indexed = False

    def _tokenize(self, text: str):
        toks = re.findall(r"\w+", (text or '').lower())
        return [t for t in toks if len(t) > 1]

    def _tf(self, tokens):
        c = _Counter(tokens)
        return dict(c)

    def _norm(self, vec):
        return math.sqrt(sum(v * v for v in vec.values()))

    def _dot(self, a, b):
        return sum(a.get(k, 0) * b.get(k, 0) for k in a.keys())

    def _excerpt(self, text, n=400):
        if not text:
            return ""
        return text.strip().replace('\n', ' ')[:n]

    def collect_documents(self):
        docs = []
        # docker ps
        try:
            out = subprocess.run(['docker', 'ps', '--format', '{{.Names}}: {{.Image}} - {{.Status}}'], capture_output=True, text=True, timeout=5).stdout
        except Exception as e:
            out = f"docker ps error: {e}"
        docs.append({'id': 'docker_ps', 'source': 'docker', 'text': out})

        # systemd running services
        try:
            out = subprocess.run(['systemctl', 'list-units', '--type=service', '--state=running', '--no-pager'], capture_output=True, text=True, timeout=5).stdout
        except Exception as e:
            out = f"systemctl error: {e}"
        docs.append({'id': 'systemd_services', 'source': 'systemd', 'text': out})

        # candidate files
        candidate_paths = [
            '/etc/prometheus/rules/homelab-advisor-alerts.yml',
            '/etc/prometheus/rules/homelab-alerts.yml',
            '/home/homelab/monitoring/grafana/provisioning/dashboards/homelab-copilot-agent.json'
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                except Exception as e:
                    content = f"read_error: {e}"
                docs.append({'id': f'file:{p}', 'source': 'file', 'text': content})

        # recent journal
        try:
            out = subprocess.run(['journalctl', '-u', 'estouaqui-backend', '-n', '200', '--no-pager'], capture_output=True, text=True, timeout=5).stdout
            if out:
                docs.append({'id': 'journal_estouaqui', 'source': 'journal', 'text': out})
        except Exception:
            pass

        return docs

    def index(self):
        raw_docs = self.collect_documents()
        indexed = []
        for d in raw_docs:
            text = d.get('text') or ''
            tokens = self._tokenize(text)
            if not tokens:
                continue
            tf = self._tf(tokens)
            norm = self._norm(tf) or 1.0
            indexed.append({
                'id': d.get('id'),
                'source': d.get('source'),
                'text': text,
                'tf': tf,
                'norm': norm,
                'excerpt': self._excerpt(text, 800)
            })
        self.documents = indexed
        self.indexed = True
        return len(self.documents)

    def query(self, q: str, top_k: int = 3):
        tokens = self._tokenize(q)
        if not tokens or not self.documents:
            return []
        q_tf = self._tf(tokens)
        q_norm = self._norm(q_tf) or 1.0
        results = []
        for doc in self.documents:
            try:
                score = self._dot(q_tf, doc['tf']) / (q_norm * doc['norm'])
            except Exception:
                score = 0.0
            if score > 0:
                results.append({'id': doc['id'], 'source': doc['source'], 'score': float(score), 'excerpt': doc['excerpt']})
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def status(self):
        return {'indexed': self.indexed, 'documents': len(self.documents)}
