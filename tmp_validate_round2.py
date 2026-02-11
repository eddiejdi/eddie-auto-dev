import subprocess, json
prompts = [
  "Explique brevemente o propósito do arquivo topic.json.",
  "Como posso customizar o label em tocInactive.json?",
  "Resuma o conteúdo do documento Estimativa_Robo_Cobrança em uma frase.",
  "O que significa o campo self_ref em topic.json?",
  "Quais ações devem ser tomadas quando uma cobrança está vencida?",
  "Como atualizar o campo content_layer em tocInactive.json?",
  "Dê um exemplo curto de pergunta/resposta útil extraída de um documento técnico.",
  "Liste 3 cuidados ao gerar índices a partir de arquivos JSON de documentação."
]
out = '/home/homelab/validation_results_round2.jsonl'
with open(out, 'w', encoding='utf-8') as f:
    for p in prompts:
        try:
            proc = subprocess.run(['ollama','run','eddie-whatsapp:latest'], input=p, text=True, capture_output=True, timeout=180)
            resp = proc.stdout.strip()
        except Exception as e:
            resp = f'ERROR: {e}'
        json.dump({'prompt': p, 'response': resp}, f, ensure_ascii=False)
        f.write('\n')
# summary
lines = open(out, 'r', encoding='utf-8').read().splitlines()
print('WROTE', len(lines), 'lines to', out)
print('--- TAIL 5 ---')
for l in lines[-5:]:
    print(l)
