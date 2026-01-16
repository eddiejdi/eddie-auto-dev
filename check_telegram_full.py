#!/usr/bin/env python3
"""Verificar webhook info e últimas atualizações"""
import requests
import json

TELEGRAM_TOKEN = "1105143633:AAEC1kmqDD_MDSpRFgEVHctwAfvfjVSp8B4"
BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def main():
    print("=== WEBHOOK INFO ===\n")
    
    # Verificar webhook atual
    response = requests.get(f"{BASE_URL}/getWebhookInfo")
    data = response.json()
    
    if data.get("ok"):
        result = data["result"]
        print(f"URL: {result.get('url', 'Nenhum')}")
        print(f"Pending updates: {result.get('pending_update_count', 0)}")
        print(f"Last error: {result.get('last_error_message', 'Nenhum')}")
        print(f"Last error date: {result.get('last_error_date', 'N/A')}")
    
    print("\n=== DELETANDO WEBHOOK TEMPORARIAMENTE ===")
    
    # Deletar webhook para poder usar getUpdates
    response = requests.get(f"{BASE_URL}/deleteWebhook")
    print(f"Delete webhook: {response.json()}")
    
    print("\n=== ATUALIZAÇÕES RECENTES ===\n")
    
    # Buscar updates
    response = requests.get(f"{BASE_URL}/getUpdates", params={"limit": 50})
    data = response.json()
    
    if not data.get("ok"):
        print(f"Erro: {data}")
        return
    
    updates = data.get("result", [])
    
    if not updates:
        print("Nenhuma atualização pendente no buffer.")
        print("(Isso pode significar que o webhook já processou tudo)")
        return
    
    callbacks = []
    messages = []
    
    for u in updates:
        # Callback query (clique em botão)
        if "callback_query" in u:
            cb = u["callback_query"]
            callbacks.append({
                "data": cb.get("data"),
                "user": cb.get("from", {}).get("first_name"),
                "user_id": cb.get("from", {}).get("id"),
                "msg_id": cb.get("message", {}).get("message_id")
            })
        
        # Mensagem de texto
        if "message" in u:
            msg = u["message"]
            if msg.get("text"):
                messages.append({
                    "text": msg["text"][:100],
                    "user": msg.get("from", {}).get("first_name"),
                    "date": msg.get("date")
                })
    
    if callbacks:
        print(f"🔘 CLIQUES EM BOTÕES ({len(callbacks)}):")
        for cb in callbacks:
            print(f"   - {cb['user']} clicou: {cb['data']}")
    else:
        print("Nenhum clique em botão encontrado no buffer")
    
    print()
    
    if messages:
        print(f"💬 MENSAGENS ({len(messages)}):")
        for msg in messages[-10:]:  # últimas 10
            print(f"   - {msg['user']}: {msg['text']}")
    
    print("\n✅ Verificação concluída!")

if __name__ == "__main__":
    main()
