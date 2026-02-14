# Guia de Configuração: Google Home / Smart Device Management API

Este guia explica como configurar a integração com Google Home para controlar dispositivos via Gemini.

## Pré-requisitos

- Conta Google com dispositivos Google Home/Nest configurados
- Acesso ao Google Cloud Console
- Dispositivos smart home vinculados ao Google Home

## Passo 1: Criar Projeto no Google Cloud Console

1. Acesse https://console.cloud.google.com/
2. Crie um novo projeto (ou selecione um existente)
   - Nome sugerido: "Eddie Home Automation"
3. Anote o **Project ID**

## Passo 2: Habilitar Smart Device Management API

1. No Google Cloud Console, vá em "APIs & Services" > "Library"
2. Pesquise por "Smart Device Management API"
3. Clique em "Enable"

## Passo 3: Criar Credenciais OAuth 2.0

1. Vá em "APIs & Services" > "Credentials"
2. Clique em "Create Credentials" > "OAuth client ID"
3. Se solicitado, configure a "OAuth consent screen":
   - User Type: **External**
   - App name: "Eddie Home Assistant"
   - User support email: seu email
   - Developer contact: seu email
   - Scopes: adicione `https://www.googleapis.com/auth/sdm.service`
   - Test users: adicione seu email (edenilson.adm@gmail.com)
4. Volte para criar o OAuth client ID:
   - Application type: **Web application**
   - Name: "Eddie Home Client"
   - Authorized redirect URIs: adicione `http://localhost:8080`
5. Clique em "Create"
6. **Anote o Client ID e Client Secret**

## Passo 4: Criar Device Access Project

1. Acesse https://console.nest.google.com/device-access/
2. Clique em "Create project"
3. Preencha:
   - Project name: "Eddie Home Access"
   - OAuth client ID: cole o Client ID do passo 3
4. Aceite os termos (taxa única de $5 USD para acesso à API Nest)
5. **Anote o Project ID** (formato: `projects/project-id-123456`)

## Passo 5: Executar Script de Configuração

1. Edite o arquivo `setup_google_home_oauth.py`:
   ```python
   OAUTH_CLIENT_ID = "seu-client-id-aqui"
   OAUTH_CLIENT_SECRET = "seu-client-secret-aqui"
   SDM_PROJECT_ID = "projects/seu-project-id-aqui"
   ```

2. Execute o script:
   ```bash
   source .venv/bin/activate
   python3 setup_google_home_oauth.py
   ```

3. O navegador abrirá para autorização
4. Faça login com sua conta Google
5. Autorize o acesso
6. Retorne ao terminal

7. O script salvará as credenciais em:
   - `google_home_credentials.json`
   - `agent_data/home_automation/google_credentials.json`

## Passo 6: Configurar Variáveis de Ambiente

Adicione ao arquivo `.env` ou exporte no terminal:

```bash
export GOOGLE_HOME_TOKEN="access-token-gerado"
export GOOGLE_SDM_PROJECT_ID="projects/seu-project-id"
```

## Passo 7: Testar Integração

Execute o teste:

```bash
python3 - << 'EOF'
import asyncio
from specialized_agents.gemini_connector import webhook
from pydantic import BaseModel

class Cmd(BaseModel):
    text: str

async def test():
    cmd = Cmd(text='ligar ventilador do escritório')
    result = await webhook(cmd)
    print(result)

asyncio.run(test())
EOF
```

## Troubleshooting

### Erro "invalid_grant"
- O código de autorização expirou (válido por 10 minutos)
- Execute o script novamente

### Erro "access_denied"
- Certifique-se de que seu email está na lista de "Test users" no OAuth consent screen
- Verifique se os escopos estão corretos

### Erro "404 Not Found" ao listar dispositivos
- Verifique se o SDM_PROJECT_ID está correto
- Certifique-se de que há dispositivos vinculados ao Google Home

### Token expira rapidamente
- Use o `refresh_token` para obter novos `access_token`s
- O refresh_token é salvo automaticamente no JSON de credenciais

## Renovação de Token

O access_token expira em 1 hora. Para renovar:

```python
import requests

token_data = {
    "client_id": "seu-client-id",
    "client_secret": "seu-client-secret",
    "refresh_token": "seu-refresh-token",
    "grant_type": "refresh_token",
}

response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
new_token = response.json()["access_token"]
```

## Custos

- **Google Cloud**: Gratuito para uso pessoal (dentro dos limites)
- **Device Access API**: Taxa única de $5 USD

## Referências

- [Smart Device Management API](https://developers.google.com/nest/device-access/api)
- [OAuth 2.0 Google](https://developers.google.com/identity/protocols/oauth2)
- [Device Access Console](https://console.nest.google.com/device-access/)
