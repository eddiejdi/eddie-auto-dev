#!/bin/bash
curl -s --max-time 30 -H "Content-Type: application/json" http://localhost:11434/v1/chat/completions -d '{"model":"qwen2.5-coder:1.5b","messages":[{"role":"user","content":"Oi"}]}'
