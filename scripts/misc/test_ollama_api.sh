#!/bin/bash
curl -s -X POST "${OLLAMA_URL:-http://${HOMELAB_HOST:-localhost}:11434}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:1.5b","messages":[{"role":"user","content":"oi"}]}'
