Auto-retraining
================

Este diretório contem um utilitário para automatizar a criação do Modelfile
e, opcionalmente, criar/validar o modelo no Ollama.

Uso rápido:

```bash
python3 tools/auto_retrain.py --data /path/to/whatsapp_training_data.jsonl \
  --out-dir /home/homelab/myClaude --model-name eddie-whatsapp --create
```

Para testar localmente sem criar o modelo (útil para CI):

```bash
python3 tools/auto_retrain.py --data tests/sample.jsonl --out-dir /tmp/out --dry-run
```
