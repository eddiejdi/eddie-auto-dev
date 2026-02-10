import os
import tempfile
import json
import subprocess


def test_dry_run_generates_modelfile():
    # Cria um jsonl temporario com 3 pares
    sample = [
        {"prompt": "Oi, como vai?", "completion": "Tudo bem, e voce?"},
        {"prompt": "Me ajuda com Docker?", "completion": "Claro, o que voce precisa?"},
        {"prompt": "Qual sua cidade?", "completion": "Sao Paulo"},
    ]

    with tempfile.TemporaryDirectory() as td:
        data_path = os.path.join(td, 'sample.jsonl')
        with open(data_path, 'w', encoding='utf-8') as f:
            for s in sample:
                f.write(json.dumps(s, ensure_ascii=False) + '\n')

        out_dir = os.path.join(td, 'out')
        os.makedirs(out_dir)

        # Executa o script em modo dry-run
        cmd = ['python3', 'tools/auto_retrain.py', '--data', data_path, '--out-dir', out_dir, '--dry-run']
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.returncode == 0, f"Saida de erro: {p.stderr}"

        # Verifica que o Modelfile foi gerado
        files = os.listdir(out_dir)
        assert any(f.endswith('.Modelfile') for f in files), 'Modelfile não encontrado no out_dir'
