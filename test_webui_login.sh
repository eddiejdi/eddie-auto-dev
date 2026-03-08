#!/bin/bash
# Teste de login no Open WebUI

curl -s 'http://localhost:3000/api/v1/auths/signin' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"email":"shared@localhost","password":"admin"}'
