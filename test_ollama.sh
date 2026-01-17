#!/bin/bash
# Teste de autocomplete com modelo leve

curl -s http://192.168.15.2:11434/api/generate \
  -d '{
    "model": "qwen2.5-coder:1.5b",
    "prompt": "def hello_world():\n    ",
    "stream": false,
    "options": {
      "num_predict": 50,
      "temperature": 0.2
    }
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('Response:', d.get('response','ERROR'))"
