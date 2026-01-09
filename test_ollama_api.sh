#!/bin/bash
curl -s -X POST "http://192.168.15.2:11434/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder:1.5b","messages":[{"role":"user","content":"oi"}]}'
