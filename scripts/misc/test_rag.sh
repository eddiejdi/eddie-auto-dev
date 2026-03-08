#!/bin/bash
# Test RAG endpoint

curl -s -X POST http://192.168.15.2:8503/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"test","n_results":5}'
