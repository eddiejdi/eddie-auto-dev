#!/bin/bash
# Teste de login no Open WebUI

curl -s 'https://homelab-tunnel-sparkling-sun-3565.fly.dev/api/v1/auths/signin' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"email":"eddie@localhost","password":"admin"}'
