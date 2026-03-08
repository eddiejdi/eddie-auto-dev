#!/bin/bash
# Enviar mensagem WhatsApp

curl -s -X POST "http://localhost:3000/api/sendText" \
  -H "X-Api-Key: 96263ae8a9804541849ebc5efa212e0e" \
  -H "Content-Type: application/json" \
  -d '{"session":"default","chatId":"5511981193899@c.us","text":"oi"}' | python3 -m json.tool
