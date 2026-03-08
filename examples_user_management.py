#!/usr/bin/env python3
"""
Exemplos de uso do User Management System

Rodar:
    python3 examples_user_management.py
"""

import asyncio
import json
from specialized_agents.user_management import (
    UserConfig,
    create_user,
    delete_user,
    list_users,
    get_user,
    pipeline,
)


async def example_create_developer():
    """Exemplo 1: Criar um desenvolvedor"""
    print("\n" + "=" * 60)
    print("EXEMPLO 1: Criar Desenvolvedor")
    print("=" * 60)

    config = UserConfig(
        username="dev_alice",
        email="alice@rpa4all.com",
        full_name="Alice Developer",
        password="AliceSecure123!",
        groups=["users", "developers"],
        quota_mb=5000,
        storage_quota_mb=500000,
        create_ssh_key=True,
        create_folders=True,
    )

    print(f"\n📝 Criando usuário: {config.username}")
    print(f"   Email: {config.email}")
    print(f"   Grupos: {config.groups}")

    result = await create_user(config)

    print(f"\n✅ Resultado:")
    print(json.dumps(result, indent=2, default=str))


async def example_create_admin():
    """Exemplo 2: Criar um administrador"""
    print("\n" + "=" * 60)
    print("EXEMPLO 2: Criar Administrador")
    print("=" * 60)

    config = UserConfig(
        username="admin_bob",
        email="bob@rpa4all.com",
        full_name="Bob Admin",
        password="BobSecure123!@",
        groups=["users", "admin", "email_admins"],
        quota_mb=10000,
        storage_quota_mb=1000000,
        create_ssh_key=True,
        create_folders=True,
    )

    print(f"\n📝 Criando admin: {config.username}")
    print(f"   Grupos: {config.groups}")

    result = await create_user(config)

    print(f"\n✅ Resultado:")
    print(json.dumps(result, indent=2, default=str))


async def example_create_email_only():
    """Exemplo 3: Criar usuário apenas de email (cliente)"""
    print("\n" + "=" * 60)
    print("EXEMPLO 3: Criar Usuário Email-Only (Cliente)")
    print("=" * 60)

    config = UserConfig(
        username="client_carol",
        email="carol@rpa4all.com",
        full_name="Carol Client",
        password="CarolPass123!",
        groups=["email_users"],
        quota_mb=2000,
        storage_quota_mb=10000,
        create_ssh_key=False,  # Sem acesso SSH
        create_folders=False,
    )

    print(f"\n📧 Criando email user: {config.username}")
    print(f"   Sem SSH, sem home directory")
    print(f"   Quota: {config.quota_mb}MB")

    result = await create_user(config)

    print(f"\n✅ Resultado:")
    print(json.dumps(result, indent=2, default=str))


def example_list_users():
    """Exemplo 4: Listar usuários"""
    print("\n" + "=" * 60)
    print("EXEMPLO 4: Listar Usuários")
    print("=" * 60)

    users = list_users()

    print(f"\n👥 Total: {len(users)} usuário(s)\n")

    for user in users:
        status_emoji = {
            "complete": "🟢",
            "pending": "🟡",
            "authentik_created": "🟠",
            "email_created": "🟡",
            "env_setup": "🟠",
            "failed": "🔴",
        }.get(user.get("status"), "❓")

        print(f"{status_emoji} {user['username']:20} | {user['email']:30} | {user['status']}")


def example_get_user():
    """Exemplo 5: Obter dados de um usuário"""
    print("\n" + "=" * 60)
    print("EXEMPLO 5: Obter Dados de Usuário")
    print("=" * 60)

    users = list_users()
    if users:
        username = users[0]["username"]
        print(f"\n📋 Buscando: {username}")

        user = get_user(username)

        if user:
            print("\n✅ Dados do usuário:")
            for key, value in user.items():
                print(f"   {key}: {value}")
        else:
            print(f"❌ Usuário não encontrado")
    else:
        print("❌ Nenhum usuário para buscar")


async def example_delete_user():
    """Exemplo 6: Deletar usuário"""
    print("\n" + "=" * 60)
    print("EXEMPLO 6: Deletar Usuário (CUIDADO!)")
    print("=" * 60)

    users = list_users()
    if users:
        # Pegar último usuário criado (mais recente)
        username = users[0]["username"]

        print(f"\n🗑️  Deletando: {username}")
        print("⚠️  Esta ação é IRREVERSÍVEL!")

        result = await delete_user(username)

        print(f"\n✅ Resultado:")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("❌ Nenhum usuário para deletar")


async def example_bulk_create():
    """Exemplo 7: Criar vários usuários em lote"""
    print("\n" + "=" * 60)
    print("EXEMPLO 7: Criar Usuários em Lote")
    print("=" * 60)

    users_to_create = [
        {
            "username": "team_dev1",
            "email": "dev1@rpa4all.com",
            "full_name": "Developer 1",
            "password": "Dev1Pass123!",
            "groups": ["developers"],
        },
        {
            "username": "team_dev2",
            "email": "dev2@rpa4all.com",
            "full_name": "Developer 2",
            "password": "Dev2Pass123!",
            "groups": ["developers"],
        },
        {
            "username": "team_support",
            "email": "support@rpa4all.com",
            "full_name": "Support Team",
            "password": "SupportPass123!",
            "groups": ["users"],
        },
    ]

    print(f"\n📦 Criando {len(users_to_create)} usuários...\n")

    results = []
    for user_data in users_to_create:
        config = UserConfig(**user_data)

        print(f"  ⏳ Criando: {config.username}...")
        result = await create_user(config)

        if result["success"]:
            print(f"  ✅ {config.username}")
            results.append({"username": config.username, "success": True})
        else:
            print(f"  ❌ {config.username}: {result['error']}")
            results.append({"username": config.username, "success": False})

    print(f"\n📊 Resumo:")
    success_count = len([r for r in results if r["success"]])
    print(f"   ✅ Sucesso: {success_count}/{len(users_to_create)}")
    print(f"   ❌ Falhas: {len(users_to_create) - success_count}/{len(users_to_create)}")


async def main():
    """Menu principal"""
    print("\n" + "=" * 60)
    print("USER MANAGEMENT SYSTEM - EXEMPLOS DE USO")
    print("=" * 60)

    print("\nEscolha um exemplo para executar:")
    print("  1. Criar desenvolvedor")
    print("  2. Criar administrador")
    print("  3. Criar usuário email-only")
    print("  4. Listar usuários")
    print("  5. Obter dados de um usuário")
    print("  6. Deletar usuário (CUIDADO!)")
    print("  7. Criar usuários em lote")
    print("  0. Sair")

    choice = input("\nDigite sua escolha (0-7): ").strip()

    if choice == "1":
        await example_create_developer()
    elif choice == "2":
        await example_create_admin()
    elif choice == "3":
        await example_create_email_only()
    elif choice == "4":
        example_list_users()
    elif choice == "5":
        example_get_user()
    elif choice == "6":
        confirm = input("⚠️  Tem certeza? (sim/não): ").lower()
        if confirm == "sim":
            await example_delete_user()
        else:
            print("Cancelado")
    elif choice == "7":
        await example_bulk_create()
    elif choice == "0":
        print("Saindo...")
        return

    print("\n" + "=" * 60)
    print("Exemplo concluído!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
