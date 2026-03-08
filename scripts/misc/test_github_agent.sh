#!/bin/bash
curl -s -X POST "http://192.168.15.2:11434/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"github-agent:latest","messages":[{"role":"user","content":"oi"}]}'
