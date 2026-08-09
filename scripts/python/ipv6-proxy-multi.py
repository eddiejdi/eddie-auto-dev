#!/usr/bin/env python3
"""
IPv6-to-IPv4 TCP Proxy for Fly.io Private Network
Bridges Fly6PN IPv6 connections to local IPv4 services

Ambientes:
- PROD: portas 8081-8085
- HOM:  portas 8091-8095
- CER:  portas 8101-8105
"""
import asyncio
import socket
import os

TARGET_HOST = os.environ.get("PROXY_TARGET_HOST", "127.0.0.1")
IPV6_BIND_ADDR = os.environ.get("IPV6_BIND_ADDR")

# Mapeamento de portas para servicos locais
SERVICES = {
    # ============ PROD (existente) ============
    8081: (TARGET_HOST, 3000),   # Open WebUI
    8082: (TARGET_HOST, 11434),  # Ollama
    8083: (TARGET_HOST, 8001),   # RAG API
    8084: (TARGET_HOST, 8501),   # RAG Dashboard
    8085: (TARGET_HOST, 8502),   # GitHub Agent
    
    # ============ HOM ============
    8091: (TARGET_HOST, 3000),   # Open WebUI (mesmo servico)
    8092: (TARGET_HOST, 11434),  # Ollama
    8093: (TARGET_HOST, 8001),   # RAG API
    8094: (TARGET_HOST, 8501),   # RAG Dashboard
    8095: (TARGET_HOST, 8502),   # GitHub Agent
    
    # ============ CER ============
    8101: (TARGET_HOST, 3000),   # Open WebUI (mesmo servico)
    8102: (TARGET_HOST, 11434),  # Ollama
    8103: (TARGET_HOST, 8001),   # RAG API
    8104: (TARGET_HOST, 8501),   # RAG Dashboard
    8105: (TARGET_HOST, 8502),   # GitHub Agent
}

async def forward_data(reader, writer):
    try:
        while True:
            data = await reader.read(8192)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except:
            pass

async def handle_connection(local_reader, local_writer, target_host, target_port):
    try:
        remote_reader, remote_writer = await asyncio.open_connection(target_host, target_port)
        await asyncio.gather(
            forward_data(local_reader, remote_writer),
            forward_data(remote_reader, local_writer)
        )
    except Exception as e:
        print(f"Connection error to {target_host}:{target_port}: {e}")
    finally:
        try:
            local_writer.close()
            await local_writer.wait_closed()
        except:
            pass

async def start_proxy(listen_port, target_host, target_port):
    def client_connected(reader, writer):
        asyncio.create_task(handle_connection(reader, writer, target_host, target_port))
    
    servers = []
    
    # IPv6 opcional via ambiente, evitando depender de um endereco hardcoded.
    if IPV6_BIND_ADDR:
        try:
            server = await asyncio.start_server(
                client_connected,
                host=IPV6_BIND_ADDR,
                port=listen_port,
            )
            servers.append(server)
            print(f"OK Proxy {IPV6_BIND_ADDR}[{listen_port}] -> {target_host}:{target_port}")
        except Exception as e:
            print(f"WARN Failed IPv6 binding on {listen_port} ({IPV6_BIND_ADDR}): {e}")
    
    # IPv4 para acesso local
    try:
        server = await asyncio.start_server(
            client_connected,
            host="0.0.0.0",
            port=listen_port,
        )
        servers.append(server)
        print(f"OK Proxy 0.0.0.0:{listen_port} -> {target_host}:{target_port}")
    except Exception as e:
        print(f"WARN Failed IPv4 binding on {listen_port}: {e}")
    
    return servers

async def main():
    print("=" * 60)
    print("IPv6-to-IPv4 Proxy for Fly.io Private Network")
    print("=" * 60)
    print()
    print("Ambientes configurados:")
    print("   PROD: portas 8081-8085")
    print("   HOM:  portas 8091-8095")
    print("   CER:  portas 8101-8105")
    print(f"   Target host: {TARGET_HOST}")
    if IPV6_BIND_ADDR:
        print(f"   IPv6 bind: {IPV6_BIND_ADDR}")
    else:
        print("   IPv6 bind: desabilitado (defina IPV6_BIND_ADDR para ativar)")
    print()
    
    all_servers = []
    for listen_port, (target_host, target_port) in SERVICES.items():
        try:
            servers = await start_proxy(listen_port, target_host, target_port)
            all_servers.extend(servers)
        except Exception as e:
            print(f"ERR Failed to start proxy on {listen_port}: {e}")
    
    print()
    print(f"Started {len(all_servers)} proxy servers")
    
    if all_servers:
        await asyncio.gather(*[s.serve_forever() for s in all_servers])
    else:
        print("ERR No servers started!")

if __name__ == "__main__":
    asyncio.run(main())
