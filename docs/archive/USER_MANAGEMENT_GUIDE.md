# 👥 User Management System - Documentação Completa

## 🎯 Visão Geral

Sistema completo de gestão de usuários com **pipeline automático de setup** integrado com:

- ✅ **Authentik** - Autenticação central / SSO
- ✅ **Email Server** - Dovecot + Postfix (Roundcube webmail)
- ✅ **Environment Setup** - Home directory, SSH keys, pastas
- ✅ **PostgreSQL** - Tracking e auditoria
- ✅ **FastAPI & Streamlit** - API REST + Dashboard interativo

---

## 📋 Componentes

### 1. **Backend Python** (`user_management.py`)

Módulos principais:

#### `AuthentikManager`
```python
- create_user(config)          # Criar usuário em Authentik
- delete_user(username)        # Deletar de Authentik
- _add_to_group(...)          # Adicionar a grupos
```

#### `EmailManager`
```python
- create_email_user(config)    # Criar em Dovecot
- delete_email_user(username)  # Deletar email
- _create_email_folders(...)   # Criar pastas (Drafts, Sent, etc)
```

#### `EnvironmentSetup`
```python
- setup_user_environment(...)  # Setup completo
- _create_user_home(...)       # Criar /home/username
- _create_user_folders(...)    # Estrutura de pastas
- _generate_ssh_key(...)       # Chave SSH automática
- _create_profile(...)         # .bash_profile customizado
```

#### `UserDatabase`
```python
- create_user_record(...)      # Registrar no DB
- update_user_status(...)      # Atualizar status
- get_users()                  # Listar todos
- get_user(username)           # Obter um usuário
```

#### `UserManagementPipeline`
```python
- create_user_complete(config) # Pipeline 1-4 etapas
- delete_user_complete(...)    # Deletar tudo
```

---

### 2. **Streamlit Dashboard** (`pages/2_user_management.py`)

Interface web interativa em: `http://localhost:8502/user_management`

**Páginas:**

| Página | Função |
|--------|--------|
| **Dashboard** | 📊 Estatísticas + últimos usuários + status dos sistemas |
| **Criar Usuário** | ➕ Formulário interativo para novo usuário |
| **Listar Usuários** | 📋 Tabela com filtros/busca |
| **Gerenciar** | ⚙️ Editar, resetar senha, deletar |
| **Configurações** | ⚙️ Variáveis de ambiente, status dos módulos |

---

### 3. **FastAPI Endpoints** (`api_users.py`)

REST API em: `http://localhost:8503/api/users`

| Método | Endpoint | Função |
|--------|----------|--------|
| **POST** | `/create` | Criar novo usuário |
| **DELETE** | `/delete/{username}` | Deletar usuário |
| **GET** | `/list` | Listar todos |
| **GET** | `/get/{username}` | Obter um usuário |
| **GET** | `/status/{username}` | Verificar status do pipeline |
| **GET** | `/health` | Health check dos serviços |

---

## 🚀 Como Usar

### Instalação

#### 1. Instalar Dependências

```bash
cd /home/edenilson/shared-auto-dev

# Python packages
pip install -r requirements.txt

# Packages adicionais necessários:
pip install aiofiles psycopg2-binary streamlit streamlit-option-menu requests
```

#### 2. Configurar Variáveis de Ambiente

Editar `.env` ou `.env.email`:

```bash
# Authentik
AUTHENTIK_URL=https://auth.rpa4all.com
AUTHENTIK_TOKEN=your_token_here  # Gerar em Admin → Tokens

# Email
MAIL_DOMAIN=mail.rpa4all.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/shared

# Sistema
HOSTNAME=shared
```

#### 3. Inicializar Banco de Dados

```bash
python3 -c "
from specialized_agents.user_management import pipeline
pipeline.db._init_table()
print('✓ Tabela user_management criada')
"
```

#### 4. Configurar Sudoers (para Dovecot/Shell)

```bash
sudo visudo

# Adicionar linhas:
%shared ALL=NOPASSWD: /usr/sbin/doveadm
%shared ALL=NOPASSWD: /usr/sbin/useradd
%shared ALL=NOPASSWD: /usr/sbin/userdel
%shared ALL=NOPASSWD: /bin/systemctl
%shared ALL=NOPASSWD: /usr/sbin/chown
```

---

### Executar o Dashboard

```bash
# Via Streamlit multi-page
cd /home/edenilson/shared-auto-dev
streamlit run streamlit_app.py

# Ou diretamente
streamlit run pages/2_user_management.py
```

Acesso: `http://localhost:8502/user_management`

---

### Usar a API REST

#### Criar Usuário

```bash
curl -X POST http://localhost:8503/api/users/create \
  -H "Content-Type: application/json" \
  -d '{
    "username": "edenilson",
    "email": "edenilson@rpa4all.com",
    "full_name": "Edenilson Silva",
    "password": "senhaSegura123!",
    "groups": ["users", "email_admins"],
    "quota_mb": 5000
  }'
```

#### Listar Usuários

```bash
curl http://localhost:8503/api/users/list
```

#### Obter Status

```bash
curl http://localhost:8503/api/users/status/edenilson
```

#### Deletar Usuário

```bash
curl -X DELETE http://localhost:8503/api/users/delete/edenilson
```

---

## 📊 Pipeline de Criação

```
Usuário solicitado
        ↓
    ┌───┴────────────────────┐
    │  REGISTRO NO DATABASE  │
    └───────────┬────────────┘
                ↓
    ┌───────────────────────┐
    │ 1️⃣  AUTHENTIK MANAGER  │
    │  - Criar usuário      │
    │  - Set password       │
    │  - Adicionar a grupos │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │  2️⃣  EMAIL MANAGER     │
    │  - Criar em Dovecot   │
    │  - Pastas (IMAP)      │
    │  - Limites (quota)    │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │ 3️⃣  ENVIRONMENT SETUP  │
    │  - /home/username     │
    │  - SSH key            │
    │  - .bash_profile      │
    │  - Pastas base        │
    └───────────┬───────────┘
                ↓
    ┌───────────────────────┐
    │   ✅ STATUS: COMPLETE │
    │   Usuário pronto!     │
    └───────────────────────┘
```

**Status Possíveis:**
- 🟡 `pending` - Criação iniciada
- 🟠 `authentik_created` - Authentik OK
- 🟡 `email_created` - Email OK
- 🟠 `env_setup` - Ambiente OK
- 🟢 `complete` - Tudo pronto!
- 🔴 `failed` - Erro em alguma etapa

---

## 🔐 Segurança

### Autenticação Authentik

1. Usuário criado em Authentik com:
   - Username único
   - Password (força mudança no login)
   - Grupos configuráveis

2. Integração LDAP/OAuth automática

### Email

1. Quota de armazenamento configurável
2. Pastas isoladas por usuário
3. Acesso via IMAP/POP3 seguro (TLS obrigatório)

### Servidor

1. SSH keys com RSA-4096
2. Home directory com permissões corretas
3. Sudoers configurado (sem password)

---

## 📈 Exemplos de Uso

### Criar Desenvolvedor

```python
from specialized_agents.user_management import UserConfig, create_user
import asyncio

config = UserConfig(
    username="dev_fulano",
    email="fulano@rpa4all.com",
    full_name="Fulano de Tal",
    password="SecurePass123!",
    groups=["users", "developers"],
    quota_mb=5000,
    storage_quota_mb=500000,  # 500GB para projetos
    create_ssh_key=True,
    create_folders=True,
)

result = asyncio.run(create_user(config))
print(result)
```

### Criar Admin

```python
config = UserConfig(
    username="admin_maria",
    email="maria@rpa4all.com",
    full_name="Maria Admin",
    password="SuperSecureAdmin123!",
    groups=["users", "admin", "email_admins"],
    quota_mb=10000,  # Limite maior
    storage_quota_mb=1000000,  # 1TB
)

result = asyncio.run(create_user(config))
```

### Criar Email-Only User

```python
config = UserConfig(
    username="client_john",
    email="john@rpa4all.com",
    full_name="John Client",
    password="ClientPass123!",
    groups=["email_users"],  # Apenas email
    quota_mb=2000,
    storage_quota_mb=10000,
    create_ssh_key=False,  # Sem acesso SSH
    create_folders=False,
)

result = asyncio.run(create_user(config))
```

---

## 🛠️ Troubleshooting

### Problema: "pull access denied for Authentik"

**Solução**: Verificar `AUTHENTIK_TOKEN`

```bash
# Gerar novo token em Authentik UI:
# Settings → Tokens → Create
# Salvar em .env: AUTHENTIK_TOKEN=xxxx
```

### Problema: Dovecot não encontrado

```bash
# Verificar serviço
sudo systemctl status dovecot

# Verificar comando
which doveadm

# Teste
sudo doveadm user add test@mail.rpa4all.com password
```

### Problema: Permissões SSH

```bash
# Verificar sudoers
sudo visudo -c

# Executar manual
sudo useradd -m username
sudo doveadm user add username@domain password
```

### Problema: Banco de dados

```bash
# Conectar
psql $DATABASE_URL

# Ver tabela
SELECT * FROM user_management;

# Resetar
DROP TABLE user_management;
# Depois rodar _init_table() novamente
```

---

## 📚 Referências

- **Authentik API**: https://docs.goauthentik.io/api/
- **Dovecot**: https://doc.dovecot.org/
- **Postfix**: http://www.postfix.org/documentation.html
- **FastAPI**: https://fastapi.tiangolo.com/
- **Streamlit**: https://docs.streamlit.io/

---

## 📞 Suporte

**Log de Operações:**

```bash
# Ver último erro
tail -100 ~/.local/share/shared/user_management.log

# Ativar debug
export LOG_LEVEL=DEBUG
python3 -c "from specialized_agents.user_management import pipeline; ..."
```

**Contato:** Shared System Admin

---

**Última atualização**: 2026-03-07  
**Versão**: 1.0  
**Status**: ✅ Production Ready
