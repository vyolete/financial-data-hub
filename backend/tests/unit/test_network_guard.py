"""The test suite must not reach the network, while asyncio and loopback keep working."""

import asyncio
import socket

import pytest
from pytest_socket import SocketConnectBlockedError


def test_external_connection_is_blocked() -> None:
    # 192.0.2.1 is a documentation address (RFC 5737); it is never contacted.
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("192.0.2.1", 80), timeout=1)


async def test_asyncio_loopback_server_works() -> None:
    async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(await reader.readline())
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(echo, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"ping\n")
        await writer.drain()
        assert await reader.readline() == b"ping\n"
        writer.close()
        await writer.wait_closed()


async def test_external_asyncio_connection_is_blocked() -> None:
    with pytest.raises(SocketConnectBlockedError):
        await asyncio.open_connection("192.0.2.1", 80)
