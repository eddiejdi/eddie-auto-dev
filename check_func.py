#!/usr/bin/env python3
import requests
import re

BASE = 'http://192.168.15.2:3000'
session = requests.Session()

r = session.post(f'{BASE}/api/v1/auths/signin', json={'email':'edenilson.adm@gmail.com','password':'Eddie@2026'})
token = r.json().get('token')
headers = {'Authorization': f'Bearer {token}'}

# Listar funções
r = session.get(f'{BASE}/api/v1/functions/', headers=headers)
funcs = r.json()

for f in funcs:
    if f.get('id') == 'director_eddie':
        print("=== FUNÇÃO DIRECTOR_EDDIE ===\n")
        content = f.get('content', '')
        
        # Procurar modelo
        matches = re.findall(r'(qwen[^\"\'\s]+)', content)
        print(f'Modelos qwen no código: {matches}')
        
        # Procurar 14b
        if '14b' in content:
            print('\n!!! 14b ENCONTRADO NO CÓDIGO!')
            for i, line in enumerate(content.split('\n')):
                if '14b' in line:
                    print(f'  Linha {i}: {line.strip()[:100]}')
        else:
            print('\nOK: 14b NÃO está no código da função')
            
        # Mostrar DIRECTOR_MODEL
        match = re.search(r'DIRECTOR_MODEL.*?default\s*=\s*["\']([^"\']+)', content)
        if match:
            print(f'\nDIRECTOR_MODEL = {match.group(1)}')
        
        # Mostrar linhas com model
        print("\n=== LINHAS COM 'model' ===")
        for i, line in enumerate(content.split('\n')):
            if 'model' in line.lower() and ('qwen' in line.lower() or '7b' in line or '14b' in line):
                print(f'{i:3}: {line.strip()[:100]}')

# Agora verificar modelos
print("\n" + "=" * 50)
print("MODELOS NO OPEN WEBUI")
print("=" * 50)

r = session.get(f'{BASE}/api/v1/models', headers=headers)
data = r.json()
models = data.get('data', [])

for m in models:
    mid = m.get('id', '?')
    mname = m.get('name', '')
    owned = m.get('owned_by', '')
    
    # Verificar se tem info com base_model_id
    info = m.get('info', {})
    base = info.get('base_model_id', '')
    
    if 'diretor' in mid.lower() or 'diretor' in mname.lower():
        print(f"\n!!! MODELO DIRETOR: {mid}")
        print(f"    name: {mname}")
        print(f"    owned_by: {owned}")
        print(f"    base_model_id: {base}")
        print(f"    info: {info}")
    
    # Procurar 14b em qualquer lugar
    m_str = str(m)
    if '14b' in m_str:
        print(f"\n!!! 14b em modelo: {mid}")
        print(f"    {m}")
