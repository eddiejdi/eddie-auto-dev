#!/usr/bin/env python3
"""
Automação de retraining para o modelo `eddie-whatsapp`.

Funcionalidades:
- Lê um arquivo `jsonl` com pares de treinamento
- Seleciona N exemplos de boa qualidade para o system prompt
- Gera um `Modelfile` pronto para `ollama create`
- Opcionalmente executa `ollama create` e valida o modelo com prompts de teste

Uso:
  python3 tools/auto_retrain.py --data /path/to/whatsapp_training_data.jsonl \
    --out-dir /home/homelab/myClaude --model-name eddie-whatsapp --create

Suporta `--dry-run` para apenas gerar o Modelfile localmente.
"""
import argparse
import json
import os
import subprocess
import sys
from typing import List


def load_data(path: str) -> List[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def select_examples(data: List[dict], max_examples: int = 30):
    seen = set()
    selected = []
    for item in data:
        p = item.get('prompt', '').strip()
        c = item.get('completion', '').strip()
        if len(c) > 10 and len(p) > 3 and c not in seen and 'http' not in c:
            seen.add(c)
            selected.append({'prompt': p, 'completion': c})
            if len(selected) >= max_examples:
                break
    return selected


def build_system_prompt(selected: List[dict]) -> str:
    examples = "\n\nExemplos de como Edenilson responde:\n"
    for item in selected:
        p = item['prompt'][:150]
        c = item['completion'][:250]
        examples += f"\nUsuario: {p}\nEdenilson: {c}\n"

    system = (
        "Voce e Edenilson Teixeira Paschoa, profissional de TI em Sao Paulo.\n\n"
        "Estilo de comunicacao:\n- Direto e objetivo\n- Portugues brasileiro informal\n- Conhecimento em tecnologia, programacao, Linux, Docker, Python\n- Interesses: camping, motorhomes, tecnologia\n- Responde de forma natural como no WhatsApp\n"
    )
    system += examples
    system += "\nSempre responda como Edenilson responderia, mantendo o estilo casual e direto."
    return system


def write_modelfile(system: str, out_path: str, base_model: str = 'llama3.2:3b'):
    # Escape triple quotes inside system
    system_escaped = system.replace('"""', '\\"\\"\\"')
    modelfile = []
    modelfile.append(f'FROM {base_model}')
    modelfile.append('')
    modelfile.append('SYSTEM """' + system_escaped + '"""')
    modelfile.append('')
    modelfile.append('PARAMETER temperature 0.7')
    modelfile.append('PARAMETER num_ctx 4096')
    modelfile.append('PARAMETER top_p 0.9')
    content = '\n'.join(modelfile) + '\n'

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)


def run_ollama_create(modelfile_path: str, model_name: str, ollama_cmd: str = 'ollama'):
    cmd = [ollama_cmd, 'create', model_name, '-f', modelfile_path]
    print('Executando:', ' '.join(cmd))
    subprocess.check_call(cmd)


def validate_model(model_name: str, tests: List[str], ollama_cmd: str = 'ollama'):
    results = []
    for t in tests:
        p = subprocess.Popen([ollama_cmd, 'run', model_name], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(t)
        if p.returncode != 0:
            raise RuntimeError(f'Erro ao executar ollama run: {err}')
        results.append(out.strip())
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Arquivo jsonl com pares de treino')
    parser.add_argument('--out-dir', required=True, help='Diretorio para salvar Modelfile e artefatos')
    parser.add_argument('--model-name', default='eddie-whatsapp')
    parser.add_argument('--base-model', default='llama3.2:3b')
    parser.add_argument('--examples', type=int, default=30)
    parser.add_argument('--create', action='store_true', help='Executa `ollama create` apos gerar o Modelfile')
    parser.add_argument('--dry-run', action='store_true', help='Apenas gera o Modelfile localmente')
    parser.add_argument('--ollama-cmd', default='ollama')
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    data = load_data(args.data)
    selected = select_examples(data, args.examples)
    system = build_system_prompt(selected)

    modelfile_path = os.path.join(args.out_dir, f'{args.model_name}-trained.Modelfile')
    write_modelfile(system, modelfile_path, base_model=args.base_model)
    print('Modelfile gerado em:', modelfile_path)

    if args.dry_run:
        print('Dry-run: terminado sem criar o modelo.')
        sys.exit(0)

    if args.create:
        run_ollama_create(modelfile_path, args.model_name, ollama_cmd=args.ollama_cmd)
        # validação simples
        tests = [
            'Oi, tudo bem? O que voce faz da vida?',
            'Me ajuda a configurar um Docker Compose pra subir um Postgres?'
        ]
        outputs = validate_model(args.model_name, tests, ollama_cmd=args.ollama_cmd)
        print('\nValidação:')
        for i, out in enumerate(outputs, 1):
            print(f'[{i}]', out[:100].replace('\n', ' '))


if __name__ == '__main__':
    main()
