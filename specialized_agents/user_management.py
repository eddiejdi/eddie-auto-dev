"""
User Management System - Complete User Setup Pipeline

Integra com:
- Authentik (autenticação central)
- Email Server (Dovecot)
- Ambientes (SSH, Pastas)
- Banco de dados (Tracking)
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

import aiofiles
import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class UserStatus(str, Enum):
    """Status do usuário no pipeline"""

    PENDING = "pending"
    AUTHENTIK_CREATED = "authentik_created"
    EMAIL_CREATED = "email_created"
    ENV_SETUP = "env_setup"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class UserConfig:
    """Configuração completa do usuário"""

    username: str
    email: str
    full_name: str
    password: str
    groups: list[str] | None = None
    quota_mb: int = 5000
    storage_quota_mb: int = 100000
    create_ssh_key: bool = True
    create_folders: bool = True
    send_welcome_email: bool = True

    def __post_init__(self):
        """Validação básica"""
        if not self.groups:
            self.groups = ["users"]


class AuthentikManager:
    """Gerenciar usuários em Authentik"""

    def __init__(self):
        self.base_url = os.getenv("AUTHENTIK_URL", "https://auth.rpa4all.com")
        self.token = os.getenv("AUTHENTIK_TOKEN")
        self.api_url = f"{self.base_url}/api/v3"

    async def create_user(self, config: UserConfig) -> dict:
        """Criar usuário em Authentik"""
        logger.info(f"📝 Criando usuário em Authentik: {config.username}")

        headers = {"Authorization": f"Bearer {self.token}"}

        # 1. Criar usuário
        user_data = {
            "username": config.username,
            "name": config.full_name,
            "email": config.email,
            "groups": [],
            "is_active": True,
        }

        try:
            resp = requests.post(
                f"{self.api_url}/core/users/",
                json=user_data,
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            user = resp.json()
            logger.info(f"✓ Usuário criado em Authentik: {user['uuid']}")

            # 2. Definir password
            password_data = {
                "password": config.password,
                "force_change": True,
            }
            requests.post(
                f"{self.api_url}/core/users/{user['pk']}/set_password/",
                json=password_data,
                headers=headers,
                timeout=10,
            )
            logger.info(f"✓ Senha definida (forçar mudança no login)")

            # 3. Adicionar a grupos
            for group_name in config.groups:
                await self._add_to_group(user["pk"], group_name, headers)

            return {"uuid": user["pk"], "username": user["username"]}

        except requests.RequestException as e:
            logger.error(f"✗ Erro criando usuário Authentik: {e}")
            raise

    async def _add_to_group(self, user_pk: int, group_name: str, headers: dict):
        """Adicionar usuário a grupo"""
        try:
            # Buscar grupo
            resp = requests.get(
                f"{self.api_url}/core/groups/?name={group_name}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            groups = resp.json()["results"]

            if not groups:
                logger.warning(f"⚠ Grupo não encontrado: {group_name}")
                return

            group = groups[0]

            # Adicionar usuário ao grupo
            requests.patch(
                f"{self.api_url}/core/groups/{group['pk']}/",
                json={"users": [user_pk]},
                headers=headers,
                timeout=10,
            )
            logger.info(f"✓ Usuário adicionado ao grupo: {group_name}")

        except requests.RequestException as e:
            logger.error(f"✗ Erro adicionando usuário ao grupo: {e}")

    async def delete_user(self, username: str) -> bool:
        """Deletar usuário de Authentik"""
        logger.info(f"🗑 Deletando usuário de Authentik: {username}")

        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            # Buscar usuário
            resp = requests.get(
                f"{self.api_url}/core/users/?username={username}",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            users = resp.json()["results"]

            if not users:
                logger.warning(f"⚠ Usuário não encontrado: {username}")
                return False

            user = users[0]

            # Deletar
            requests.delete(
                f"{self.api_url}/core/users/{user['pk']}/",
                headers=headers,
                timeout=10,
            )
            logger.info(f"✓ Usuário deletado de Authentik: {username}")
            return True

        except requests.RequestException as e:
            logger.error(f"✗ Erro deletando usuário: {e}")
            return False


class EmailManager:
    """Gerenciar usuários de email (Dovecot/Postfix)"""

    def __init__(self):
        self.domain = os.getenv("MAIL_DOMAIN", "mail.rpa4all.com")
        self.doveadm_cmd = "sudo doveadm"  # Assuming sudoers configured

    async def create_email_user(self, config: UserConfig) -> bool:
        """Criar usuário de email via doveadm"""
        email = f"{config.username}@{self.domain}"
        logger.info(f"📧 Criando usuário de email: {email}")

        try:
            # Criar conta de email
            cmd = [
                "sudo",
                "doveadm",
                "user",
                "add",
                "-u",
                str(config.quota_mb),
                email,
                config.password,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"✗ Erro criando email: {result.stderr}")
                return False

            logger.info(f"✓ Usuário de email criado: {email}")

            # Criar pastas iniciais
            if config.create_folders:
                await self._create_email_folders(email)

            return True

        except Exception as e:
            logger.error(f"✗ Erro em create_email_user: {e}")
            return False

    async def _create_email_folders(self, email: str):
        """Criar pastas padrão de email"""
        folders = ["Drafts", "Sent", "Trash", "Spam"]

        for folder in folders:
            try:
                cmd = [
                    "sudo",
                    "doveadm",
                    "mailbox",
                    "create",
                    "-u",
                    email,
                    folder,
                ]
                subprocess.run(cmd, capture_output=True, timeout=5)
                logger.info(f"✓ Pasta criada: {folder}")
            except Exception as e:
                logger.warning(f"⚠ Erro criando pasta {folder}: {e}")

    async def delete_email_user(self, username: str) -> bool:
        """Deletar usuário de email"""
        email = f"{username}@{self.domain}"
        logger.info(f"🗑 Deletando usuário de email: {email}")

        try:
            cmd = ["sudo", "doveadm", "user", "delete", email]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"✗ Erro deletando email: {result.stderr}")
                return False

            logger.info(f"✓ Usuário de email deletado: {email}")
            return True

        except Exception as e:
            logger.error(f"✗ Erro em delete_email_user: {e}")
            return False


class EnvironmentSetup:
    """Configurar ambiente do usuário"""

    def __init__(self):
        self.home_base = "/home"

    async def setup_user_environment(self, config: UserConfig) -> bool:
        """Setup completo do ambiente do usuário"""
        logger.info(f"⚙ Configurando ambiente para: {config.username}")

        try:
            # 1. Criar diretório home
            home_dir = f"{self.home_base}/{config.username}"
            await self._create_user_home(config.username, home_dir)

            # 2. Criar estrutura de pastas
            if config.create_folders:
                await self._create_user_folders(home_dir)

            # 3. Gerar SSH key
            if config.create_ssh_key:
                await self._generate_ssh_key(config.username, home_dir)

            # 4. Criar arquivo .profile
            await self._create_profile(home_dir, config.username)

            logger.info(f"✓ Ambiente configurado: {home_dir}")
            return True

        except Exception as e:
            logger.error(f"✗ Erro em setup_user_environment: {e}")
            return False

    async def _create_user_home(self, username: str, home_dir: str):
        """Criar diretório home do usuário"""
        try:
            # Criar usando useradd (system user)
            cmd = [
                "sudo",
                "useradd",
                "-m",
                "-s",
                "/bin/bash",
                "-c",
                f"User {username}",
                username,
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)
            logger.info(f"✓ Diretório home criado: {home_dir}")
        except Exception as e:
            logger.warning(f"⚠ Erro criando home (pode já existir): {e}")

    async def _create_user_folders(self, home_dir: str):
        """Criar estrutura de pastas"""
        folders = ["Documents", "Downloads", "Desktop", ".config", ".local/share"]

        for folder in folders:
            try:
                path = os.path.join(home_dir, folder)
                os.makedirs(path, exist_ok=True)
                logger.info(f"✓ Pasta criada: {path}")
            except Exception as e:
                logger.warning(f"⚠ Erro criando pasta: {e}")

    async def _generate_ssh_key(self, username: str, home_dir: str):
        """Gerar chave SSH para o usuário"""
        try:
            ssh_dir = os.path.join(home_dir, ".ssh")
            os.makedirs(ssh_dir, exist_ok=True)

            # Gerar chave
            cmd = [
                "ssh-keygen",
                "-t",
                "rsa",
                "-b",
                "4096",
                "-f",
                f"{ssh_dir}/id_rsa",
                "-N",
                "",
                "-C",
                f"{username}@{os.getenv('HOSTNAME', 'eddie')}",
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)

            # Corrigir permissões
            subprocess.run(
                ["sudo", "chown", "-R", f"{username}:{username}", ssh_dir],
                capture_output=True,
                timeout=10,
            )

            logger.info(f"✓ Chave SSH gerada: {ssh_dir}/id_rsa")
        except Exception as e:
            logger.warning(f"⚠ Erro gerando SSH key: {e}")

    async def _create_profile(self, home_dir: str, username: str):
        """Criar .bashrc/.profile do usuário"""
        try:
            profile_content = f"""#!/bin/bash
# .bash_profile for {username}
# Generated automatically by User Management System

export HOSTNAME=${{HOSTNAME:-eddie}}
export USER={username}
export HOME={home_dir}

# Basic prompt
PS1='[\\u@\\h \\W]\\$ '

# Aliases
alias ll='ls -lah'
alias la='ls -A'
alias l='ls -CF'

# Source .bashrc if exists
if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi

echo "Welcome, {username}!"
"""

            profile_path = os.path.join(home_dir, ".bash_profile")
            async with aiofiles.open(profile_path, "w") as f:
                await f.write(profile_content)

            subprocess.run(
                ["sudo", "chown", f"{username}:{username}", profile_path],
                capture_output=True,
            )
            logger.info(f"✓ Arquivo .bash_profile criado")

        except Exception as e:
            logger.warning(f"⚠ Erro criando .bash_profile: {e}")


class UserDatabase:
    """Rastrear usuários em banco de dados"""

    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            logger.warning("⚠ DATABASE_URL não configurado")

    def _get_connection(self):
        """Conectar ao PostgreSQL"""
        if not self.db_url:
            return None

        try:
            return psycopg2.connect(self.db_url)
        except Exception as e:
            logger.error(f"✗ Erro conectando ao DB: {e}")
            return None

    def _init_table(self):
        """Criar tabela se não existir"""
        conn = self._get_connection()
        if not conn:
            return

        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_management (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        full_name VARCHAR(255),
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        authentik_uuid VARCHAR(255),
                        email_created BOOLEAN DEFAULT FALSE,
                        env_setup BOOLEAN DEFAULT FALSE,
                        notes TEXT
                    )
                """)
                conn.commit()
                logger.info("✓ Tabela user_management criada/verificada")
        except Exception as e:
            logger.error(f"✗ Erro criando tabela: {e}")
        finally:
            conn.close()

    def create_user_record(self, config: UserConfig, status: UserStatus) -> bool:
        """Registrar novo usuário no DB"""
        conn = self._get_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_management 
                    (username, email, full_name, status)
                    VALUES (%s, %s, %s, %s)
                """,
                    (config.username, config.email, config.full_name, status.value),
                )
                conn.commit()
                logger.info(f"✓ Usuário registrado no DB: {config.username}")
                return True
        except Exception as e:
            logger.error(f"✗ Erro registrando usuário: {e}")
            return False
        finally:
            conn.close()

    def update_user_status(self, username: str, status: UserStatus) -> bool:
        """Atualizar status do usuário"""
        conn = self._get_connection()
        if not conn:
            return False

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE user_management SET status = %s, updated_at = NOW() WHERE username = %s",
                    (status.value, username),
                )
                conn.commit()
                logger.info(f"✓ Status atualizado: {username} -> {status.value}")
                return True
        except Exception as e:
            logger.error(f"✗ Erro atualizando status: {e}")
            return False
        finally:
            conn.close()

    def get_users(self) -> list[dict]:
        """Listar todos os usuários"""
        conn = self._get_connection()
        if not conn:
            return []

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM user_management ORDER BY created_at DESC")
                columns = [desc[0] for desc in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"✗ Erro listando usuários: {e}")
            return []
        finally:
            conn.close()

    def get_user(self, username: str) -> dict | None:
        """Obter dados de um usuário"""
        conn = self._get_connection()
        if not conn:
            return None

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM user_management WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
                if row:
                    columns = [desc[0] for desc in cur.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.error(f"✗ Erro obtendo usuário: {e}")
            return None
        finally:
            conn.close()


class UserManagementPipeline:
    """Pipeline completo de criação de usuário"""

    def __init__(self):
        self.authentik = AuthentikManager()
        self.email = EmailManager()
        self.env = EnvironmentSetup()
        self.db = UserDatabase()
        self.db._init_table()

    async def create_user_complete(self, config: UserConfig) -> dict:
        """Pipeline completo de criação de usuário"""
        logger.info(f"🚀 Iniciando pipeline de criação: {config.username}")

        result = {
            "username": config.username,
            "success": False,
            "steps": {},
            "error": None,
        }

        try:
            # 1. Registrar no DB
            self.db.create_user_record(config, UserStatus.PENDING)
            result["steps"]["db_record"] = "✓"

            # 2. Criar em Authentik
            logger.info("📝 Passo 1: Autentik...")
            auth_result = await self.authentik.create_user(config)
            result["steps"]["authentik"] = "✓"
            self.db.update_user_status(config.username, UserStatus.AUTHENTIK_CREATED)

            # 3. Criar email
            logger.info("📧 Passo 2: Email Server...")
            if await self.email.create_email_user(config):
                result["steps"]["email"] = "✓"
                self.db.update_user_status(
                    config.username, UserStatus.EMAIL_CREATED
                )
            else:
                result["steps"]["email"] = "✗"

            # 4. Setup ambiente
            logger.info("⚙ Passo 3: Ambiente...")
            if await self.env.setup_user_environment(config):
                result["steps"]["environment"] = "✓"
                self.db.update_user_status(config.username, UserStatus.ENV_SETUP)
            else:
                result["steps"]["environment"] = "✗"

            # 5. Finalize
            self.db.update_user_status(config.username, UserStatus.COMPLETE)
            result["success"] = True
            result["steps"]["complete"] = "✓"

            logger.info(f"✅ Pipeline completo: {config.username}")

        except Exception as e:
            logger.error(f"❌ Erro no pipeline: {e}")
            result["error"] = str(e)
            self.db.update_user_status(config.username, UserStatus.FAILED)
            result["steps"]["complete"] = "✗"

        return result

    async def delete_user_complete(self, username: str) -> dict:
        """Deletar usuário de todos os sistemas"""
        logger.info(f"🗑 Iniciando deleção: {username}")

        result = {
            "username": username,
            "success": False,
            "steps": {},
            "error": None,
        }

        try:
            # 1. Deletar de Authentik
            if await self.authentik.delete_user(username):
                result["steps"]["authentik"] = "✓"
            else:
                result["steps"]["authentik"] = "✗"

            # 2. Deletar email
            if await self.email.delete_email_user(username):
                result["steps"]["email"] = "✓"
            else:
                result["steps"]["email"] = "✗"

            # 3. Remover home (cuidado!)
            try:
                cmd = ["sudo", "userdel", "-r", username]
                subprocess.run(cmd, capture_output=True, timeout=10)
                result["steps"]["home"] = "✓"
            except Exception as e:
                logger.warning(f"⚠ Erro removendo home: {e}")
                result["steps"]["home"] = "✗"

            result["success"] = True
            logger.info(f"✅ Usuário deletado: {username}")

        except Exception as e:
            logger.error(f"❌ Erro deletando usuário: {e}")
            result["error"] = str(e)

        return result


# Instância global
pipeline = UserManagementPipeline()


async def create_user(config: UserConfig) -> dict:
    """Criar usuário com pipeline completo"""
    return await pipeline.create_user_complete(config)


async def delete_user(username: str) -> dict:
    """Deletar usuário"""
    return await pipeline.delete_user_complete(username)


def list_users() -> list[dict]:
    """Listar usuários"""
    return pipeline.db.get_users()


def get_user(username: str) -> dict | None:
    """Obter usuário"""
    return pipeline.db.get_user(username)
