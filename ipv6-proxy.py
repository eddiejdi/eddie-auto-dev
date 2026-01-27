#!/usr/bin/env python3
"""
IPv6-to-IPv4 TCP Proxy
Bridges IPv6 connections to local IPv4 services on a host. IPv6 bind
address is optional and can be provided via `IPV6_BIND_ADDR` environment variable.
"""
import asyncio
import socket
import os

SERVICES = {
    8081: ("127.0.0.1", 3000),   # Open WebUI
    8082: ("127.0.0.1", 11434),  # Ollama
    8083: ("127.0.0.1", 8001),   # RAG API
    8084: ("127.0.0.1", 8501),   # RAG Dashboard
    8085: ("127.0.0.1", 8502),   # GitHub Agent
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
    
    # Create servers on multiple interfaces
    servers = []
    
    # Optionally bind to a configured IPv6 address (set IPV6_BIND_ADDR env var).
    ipv6_addr = os.environ.get('IPV6_BIND_ADDR')
    if ipv6_addr:
        try:
            server = await asyncio.start_server(
                client_connected,
                host=ipv6_addr,
                port=listen_port,
            )
            servers.append(server)
            print(f"Proxy {ipv6_addr}[{listen_port}] -> {target_host}:{target_port}")
        except Exception as e:
            print(f"Failed IPv6 binding on {listen_port} ({ipv6_addr}): {e}")
    
    # Also bind to all IPv4 interfaces
    try:
        server = await asyncio.start_server(
            client_connected,
            host="0.0.0.0",
            port=listen_port,
        )
        servers.append(server)
        print(f"Proxy 0.0.0.0:{listen_port} -> {target_host}:{target_port}")
    except Exception as e:
        print(f"Failed IPv4 binding on {listen_port}: {e}")
    
    return servers

async def main():
    all_servers = []
    for listen_port, (target_host, target_port) in SERVICES.items():
        try:
            servers = await start_proxy(listen_port, target_host, target_port)
            all_servers.extend(servers)
        except Exception as e:
            print(f"Failed to start proxy on {listen_port}: {e}")
    
    if all_servers:
        print(f"Started {len(all_servers)} proxy servers")
        await asyncio.gather(*[s.serve_forever() for s in all_servers])
    else:
        print("No servers started!")

if __name__ == "__main__":
    print("Starting IPv6-to-IPv4 Proxy")
    asyncio.run(main())
