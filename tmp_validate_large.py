import subprocess, json
prompts = [
  "Explique brevemente o propósito do arquivo topic.json.",
  "Como posso customizar o label em tocInactive.json?",
  "Resuma o conteúdo do documento Estimativa_Robo_Cobrança em uma frase.",
  "O que significa o campo self_ref em topic.json?",
  "Quais ações devem ser tomadas quando uma cobrança está vencida?",
  "Como atualizar o campo content_layer em tocInactive.json?",
  "Dê um exemplo curto de pergunta/resposta útil extraída de um documento técnico.",
  "Liste 3 cuidados ao gerar índices a partir de arquivos JSON de documentação.",
  "Qual é o propósito do arquivo README.md em um repositório?",
  "Como instalar as dependências de um projeto Python com virtualenv?",
  "Explique em uma frase o que faz o script tools/auto_retrain.py.",
  "Quais sinais indicam que um OCR falhou ao extrair texto de uma imagem?",
  "Como posso verificar o espaço em disco no Linux antes de deletar arquivos?",
  "Quais são boas práticas para arquivar arquivos grandes antes de deletá-los?",
  "Como posso aumentar o timeout ao chamar um LLM local via subprocess?",
  "O que deve conter um Modelfile para criar um modelo no Ollama?",
  "Quais metadados são úteis para validar um conjunto de perguntas/respostas?",
  "Como testar rapidamente se um modelo Ollama está funcional após a criação?",
  "Quais riscos existem ao remover arquivos brutos sem backup?",
  "Sugira 3 critérios para decidir quais arquivos do GDrive podem ser removidos."
]
out = '/home/homelab/validation_results_large.jsonl'
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
