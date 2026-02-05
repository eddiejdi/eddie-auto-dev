#!/usr/bin/env python3
import os
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {'.venv', 'venv', '.git', 'node_modules', '__pycache__'}


def _is_excluded_path(path: Path):
    # exclude common venv names, site-packages and hidden folders
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
        if 'venv' in part:
            return True
        if 'site-packages' in part:
            return True
        if part.startswith('.') and part != '.':
            # skip hidden dirs like .venv_selenium
            return True
    return False


def find_test_files(root):
    for p in root.rglob('test_*.py'):
        if _is_excluded_path(p):
            continue
        yield p
    for p in root.rglob('*_test.py'):
        if _is_excluded_path(p):
            continue
        yield p


def collect_nodeids_from_file(path: Path):
    try:
        src = path.read_text()
    except Exception:
        return []
    try:
        tree = ast.parse(src)
    except Exception:
        return []
    nodeids = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
            nodeids.append(f"{path.as_posix()}::{node.name}")
        if isinstance(node, ast.ClassDef):
            # collect methods
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                    nodeids.append(f"{path.as_posix()}::{node.name}::{item.name}")
    return nodeids


def collect_all_nodeids(root):
    nodeids = []
    files = sorted(set(find_test_files(root)))
    for f in files:
        nodeids.extend(collect_nodeids_from_file(f))
    return nodeids


def run_batches(nodeids, batch_size=10, pytest_bin='.venv/bin/pytest', batch_timeout=900):
    if not nodeids:
        print('Nenhum teste encontrado pelo scanner AST.')
        return 1
    total = len(nodeids)
    print(f'Encontrados {total} testes; executando em lotes de {batch_size}.')
    # cleanup stray .pyc and __pycache__ to avoid import mismatches
    print('Limpando __pycache__ e arquivos .pyc antigos...')
    for p in ROOT.rglob('__pycache__'):
        try:
            for f in p.iterdir():
                if f.is_file():
                    f.unlink()
            p.rmdir()
        except Exception:
            pass
    for f in ROOT.rglob('*.pyc'):
        try:
            f.unlink()
        except Exception:
            pass
    failures = 0
    # Build batches avoiding files with the same basename in the same pytest process
    batches = []
    cur_batch = []
    cur_basenames = set()
    for nid in nodeids:
        # nodeid like path/to/file.py::test_name or path/to/file.py::Class::test
        path = nid.split('::', 1)[0]
        basename = Path(path).name
        if len(cur_batch) >= batch_size or basename in cur_basenames:
            batches.append(cur_batch)
            cur_batch = [nid]
            cur_basenames = {basename}
        else:
            cur_batch.append(nid)
            cur_basenames.add(basename)
    if cur_batch:
        batches.append(cur_batch)

    for i, batch in enumerate(batches):
        print('\n' + '='*60)
        print(f'Lote {i+1}: {len(batch)} testes')
        print('\n'.join(batch))
        print('\nExecutando pytest para este lote...')
        try:
            proc = subprocess.run([pytest_bin, '-q', *batch], timeout=batch_timeout, capture_output=True, text=True)
            out = proc.stdout
            err = proc.stderr
            rc = proc.returncode
        except subprocess.TimeoutExpired as e:
            out = e.stdout or ''
            err = e.stderr or ''
            rc = 124
        fn = f'/tmp/pytest_batch_{i//batch_size}.txt'
        with open(fn, 'w') as fh:
            fh.write('STDOUT:\n')
            fh.write(out)
            fh.write('\n\nSTDERR:\n')
            fh.write(err)
        print(f'Resultado do lote: returncode={rc}; saída salva em {fn}')
        if rc != 0:
            failures += 1
    print('\n' + '='*60)
    print(f'Execução concluída. Lotes com falhas: {failures} / { (total+batch_size-1)//batch_size }')
    return 0 if failures == 0 else 2


if __name__ == '__main__':
    nodeids = collect_all_nodeids(ROOT)
    rc = run_batches(nodeids, batch_size=10)
    sys.exit(rc)
