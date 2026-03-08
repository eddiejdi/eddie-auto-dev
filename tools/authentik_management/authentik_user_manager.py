#!/usr/bin/env python3
"""
Script para gerenciar usuários e permissões no Authentik via API.
Uso: python3 authentik_user_manager.py [create|update|list|assign-group]
"""

import requests
import json
import sys
from typing import Dict, List, Optional

class AuthentikManager:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def api_call(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Fazer requisição à API."""
        api_url = f"{self.url}/api/v3{endpoint}"
        try:
            if method == "GET":
                resp = requests.get(api_url, headers=self.headers, verify=False)
            elif method == "POST":
                resp = requests.post(api_url, json=data, headers=self.headers, verify=False)
            elif method == "PATCH":
                resp = requests.patch(api_url, json=data, headers=self.headers, verify=False)
            else:
                raise ValueError(f"Método {method} não suportado")
            
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na API: {e}")
            return {"error": str(e)}
    
    def list_users(self) -> List[Dict]:
        """Listar todos os usuários."""
        result = self.api_call("GET", "/core/users/?format=json")
        return result.get("results", [])
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Buscar usuário por username."""
        users = self.list_users()
        return next((u for u in users if u["username"] == username), None)
    
    def create_user(self, username: str, email: str, name: str, password: str = None) -> Dict:
        """Criar novo usuário."""
        data = {
            "username": username,
            "email": email,
            "name": name,
            "is_active": True
        }
        if password:
            data["password"] = password
        
        return self.api_call("POST", "/core/users/", data)
    
    def update_user(self, user_id: int, **kwargs) -> Dict:
        """Atualizar usuário."""
        return self.api_call("PATCH", f"/core/users/{user_id}/", kwargs)
    
    def list_groups(self) -> List[Dict]:
        """Listar todos os grupos."""
        result = self.api_call("GET", "/core/groups/?format=json")
        return result.get("results", [])
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        """Buscar grupo por nome."""
        groups = self.list_groups()
        return next((g for g in groups if g["name"] == name), None)
    
    def create_group(self, name: str, description: str = "") -> Dict:
        """Criar novo grupo."""
        data = {
            "name": name,
            "name_en": name
        }
        if description:
            data["name_en"] = description
        
        return self.api_call("POST", "/core/groups/", data)
    
    def add_user_to_group(self, user_id: int, group_id: int) -> bool:
        """Adicionar usuário ao grupo."""
        user = self.api_call("GET", f"/core/users/{user_id}/")
        if "error" in user:
            return False
        
        group_ids = user.get("groups", [])
        if group_id not in group_ids:
            group_ids.append(group_id)
            self.update_user(user_id, groups=group_ids)
        
        return True

def main():
    import os
    url = os.environ.get("AUTHENTIK_URL", "https://auth.rpa4all.com")
    token = os.environ.get("AUTHENTIK_TOKEN", "ak-homelab-authentik-api-2026")
    
    manager = AuthentikManager(url, token)
    
    if len(sys.argv) < 2:
        print("Uso: python3 authentik_user_manager.py [create|update|list|assign-group]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        print("\n=== USUÁRIOS ===")
        for user in manager.list_users():
            print(f"{user['pk']}: {user['username']} ({user['email']})")
        
        print("\n=== GRUPOS ===")
        for group in manager.list_groups():
            print(f"{group['pk']}: {group['name']}")
    
    elif command == "create":
        if len(sys.argv) < 5:
            print("Uso: python3 authentik_user_manager.py create <username> <email> <name> [password]")
            sys.exit(1)
        
        username = sys.argv[2]
        email = sys.argv[3]
        name = sys.argv[4]
        password = sys.argv[5] if len(sys.argv) > 5 else None
        
        result = manager.create_user(username, email, name, password)
        print(f"✅ Usuário criado: {result.get('username', 'erro')}")
    
    else:
        print(f"Comando desconhecido: {command}")

if __name__ == "__main__":
    main()
