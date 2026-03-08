#!/bin/bash
# Script para gerenciar usuários via Django Shell

AUTHENTIK_URL="${AUTHENTIK_URL:-https://auth.rpa4all.com}"

echo "Executando Django Shell no Authentik..."
sudo docker exec authentik-server ak shell << EOF
from authentik.core.models import User, Group
import sys

# Mostrar usuários
print("\n=== USUÁRIOS EXISTENTES ===")
for user in User.objects.all()[:10]:
    groups = list(user.groups.values_list('name', flat=True))
    print(f"{user.pk}: {user.username} ({user.email}) - Grupos: {groups}")

# Mostrar grupos
print("\n=== GRUPOS EXISTENTES ===")
for group in Group.objects.all():
    print(f"{group.pk}: {group.name} ({group.users.count()} users)")

print("\n✅ Use os comandos acima para referência")
print("Exemplo de adicionar user a grupo:")
print("  user = User.objects.get(username='homelab')")
print("  group = Group.objects.get(name='Grafana Admins')")
print("  user.groups.add(group)")
EOF
