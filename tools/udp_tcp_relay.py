#!/usr/bin/env python3
"""
UDP-over-TCP relay with proper datagram framing.

Each UDP datagram is framed as: [2-byte big-endian length][payload]
This preserves datagram boundaries through TCP streams.

Usage:
  Server mode (TCP listen → UDP forward):
    udp_tcp_relay.py server --tcp-listen 51821 --udp-target 127.0.0.1:51820

  Client mode (UDP listen → TCP connect):
    udp_tcp_relay.py client --udp-listen 51823 --tcp-target 127.0.0.1:51822
"""

import argparse
import asyncio
import logging
import struct
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("udp-tcp-relay")


class UDPRelayProtocol(asyncio.DatagramProtocol):
    """UDP endpoint that relays datagrams through a TCP connection."""

    def __init__(self):
        self.transport = None
        self.tcp_writer = None
        self.client_addr = None

    def connection_made(self, transport):
        self.transport = transport

    async def _drain_tcp(self):
        try:
            if self.tcp_writer is not None and not self.tcp_writer.is_closing():
                await self.tcp_writer.drain()
        except Exception as e:
            log.error(f"tcp drain error: {e}")

    def datagram_received(self, data: bytes, addr: tuple):
        log.info(f"UDP datagram_received: {len(data)} bytes from {addr}")
        if self.tcp_writer is None or self.tcp_writer.is_closing():
            log.warning("No TCP writer available, dropping UDP datagram")
            return
        self.client_addr = addr
        frame = struct.pack("!H", len(data)) + data
        try:
            self.tcp_writer.write(frame)
            # schedule drain to flush TCP buffer
            try:
                asyncio.get_event_loop().create_task(self._drain_tcp())
            except Exception:
                # fallback if loop not available
                pass
        except Exception as e:
            log.error(f"TCP write error: {e}")

    def send_to_client(self, data: bytes):
        if self.transport and self.client_addr:
            log.info(f"Sending UDP -> {self.client_addr}: {len(data)} bytes")
            try:
                self.transport.sendto(data, self.client_addr)
            except Exception as e:
                log.error(f"Error sending UDP to client {self.client_addr}: {e}")


async def tcp_reader(reader: asyncio.StreamReader, udp_proto: UDPRelayProtocol):
    """Read length-prefixed frames from TCP and send as UDP datagrams."""
    try:
        while True:
            header = await reader.readexactly(2)
            length = struct.unpack("!H", header)[0]
            log.info(f"TCP reader: next frame length={length}")
            if length == 0:
                continue
            data = await reader.readexactly(length)
            log.info(f"TCP reader: received {len(data)} bytes, forwarding to UDP client")
            udp_proto.send_to_client(data)
    except asyncio.IncompleteReadError:
        log.info("TCP connection closed (EOF)")
    except Exception as e:
        log.error(f"TCP reader error: {e}")


async def run_server(tcp_port: int, udp_host: str, udp_port: int):
    """Server mode: accept TCP connections and relay to UDP target."""
    loop = asyncio.get_event_loop()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        log.info(f"TCP client connected: {peer}")

        # Create UDP socket to target
        transport, proto = await loop.create_datagram_endpoint(
            UDPRelayProtocol,
            remote_addr=(udp_host, udp_port),
        )
        proto.tcp_writer = writer

        # Override send_to_client to send directly to the connected UDP target
        original_send = proto.send_to_client
        def send_back(data):
            if proto.transport:
                proto.transport.sendto(data)
        proto.send_to_client = send_back

        # Override datagram_received to not need client_addr
        original_recv = proto.datagram_received
        def recv_from_udp(data, addr):
            if writer.is_closing():
                return
            frame = struct.pack("!H", len(data)) + data
            try:
                log.info(f"Server: UDP->TCP forwarding {len(data)} bytes to {writer.get_extra_info('peername')}")
                writer.write(frame)
                try:
                    asyncio.get_event_loop().create_task(writer.drain())
                except Exception:
                    pass
            except Exception as e:
                log.error(f"TCP write error: {e}")
        proto.datagram_received = recv_from_udp

        try:
            # Read from TCP → send to UDP
            while True:
                header = await reader.readexactly(2)
                length = struct.unpack("!H", header)[0]
                if length == 0:
                    continue
                data = await reader.readexactly(length)
                transport.sendto(data)
        except asyncio.IncompleteReadError:
            log.info(f"TCP client disconnected: {peer}")
        except Exception as e:
            log.error(f"Server handler error: {e}")
        finally:
            transport.close()
            writer.close()

    server = await asyncio.start_server(handle_client, "0.0.0.0", tcp_port)
    log.info(f"Server listening on TCP:{tcp_port} → UDP:{udp_host}:{udp_port}")

    async with server:
        await server.serve_forever()


async def run_client(udp_port: int, tcp_host: str, tcp_port: int):
    """Client mode: listen UDP and relay through TCP connection."""
    loop = asyncio.get_event_loop()

    # Create UDP listener
    transport, proto = await loop.create_datagram_endpoint(
        UDPRelayProtocol,
        local_addr=("127.0.0.1", udp_port),
    )
    log.info(f"Client listening on UDP:{udp_port}")

    while True:
        try:
            reader, writer = await asyncio.open_connection(tcp_host, tcp_port)
            log.info(f"Connected to TCP:{tcp_host}:{tcp_port}")
            proto.tcp_writer = writer

            # Read from TCP → send to UDP client
            await tcp_reader(reader, proto)
        except ConnectionRefusedError:
            log.warning(f"TCP connection refused, retrying in 2s...")
        except Exception as e:
            log.error(f"Client error: {e}")
        finally:
            proto.tcp_writer = None

        await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="UDP-over-TCP relay")
    sub = parser.add_subparsers(dest="mode", required=True)

    srv = sub.add_parser("server", help="TCP listen → UDP forward")
    srv.add_argument("--tcp-listen", type=int, required=True)
    srv.add_argument("--udp-target", required=True, help="host:port")

    cli = sub.add_parser("client", help="UDP listen → TCP connect")
    cli.add_argument("--udp-listen", type=int, required=True)
    cli.add_argument("--tcp-target", required=True, help="host:port")

    args = parser.parse_args()

    loop = asyncio.new_event_loop()

    def shutdown(sig, frame):
        log.info("Shutting down...")
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    if args.mode == "server":
        host, port = args.udp_target.rsplit(":", 1)
        loop.run_until_complete(run_server(args.tcp_listen, host, int(port)))
    else:
        host, port = args.tcp_target.rsplit(":", 1)
        loop.run_until_complete(run_client(args.udp_listen, host, int(port)))


if __name__ == "__main__":
    main()
