
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "authentik.root.settings")
django.setup()

from authentik.core.models import User, Group

print("=== CRIANDO GRUPOS ===")
groups_data = [
    "Grafana Admins",
    "Grafana Users", 
    "Nextcloud Admins",
    "Nextcloud Users",
    "OpenWebUI Admins",
    "OpenWebUI Users"
]

for name in groups_data:
    group, created = Group.objects.get_or_create(name=name)
    status = "✅ CRIADO" if created else "⏭️  EXISTE"
    print(f"{status}: {name} (pk={group.pk})")

print("\n=== CONFIGURANDO USUÁRIOS ===")

# Usuário 1: homelab
try:
    user = User.objects.get(username="homelab")
    print(f"\n👤 homelab (pk={user.pk})")
    
    admin_groups = ["Grafana Admins", "Nextcloud Admins", "OpenWebUI Admins"]
    for group_name in admin_groups:
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            print(f"   ✅ Adicionado: {group_name}")
        except Group.DoesNotExist:
            print(f"   ❌ Grupo não existe: {group_name}")
            
except User.DoesNotExist:
    print("❌ Usuário homelab não encontrado")

# Usuário 2: edenilson.paschoa@rpa4all.com
try:
    user = User.objects.get(email="edenilson.paschoa@rpa4all.com")
    print(f"\n👤 {user.username} (pk={user.pk})")
    
    user_groups = ["Grafana Admins", "Nextcloud Users", "OpenWebUI Users"]
    for group_name in user_groups:
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
            print(f"   ✅ Adicionado: {group_name}")
        except Group.DoesNotExist:
            print(f"   ❌ Grupo não existe: {group_name}")
            
except User.DoesNotExist:
    print("❌ Usuário edenilson.paschoa@rpa4all.com não encontrado")

print("\n=== VERIFICANDO RESULTADO ===")
for user in User.objects.filter(is_active=True)[:10]:
    groups = list(user.groups.values_list("name", flat=True))
    print(f"👤 {user.username} ({user.email})")
    if groups:
        for g in groups:
            print(f"   ├─ {g}")
    else:
        print(f"   └─ Nenhum grupo")
