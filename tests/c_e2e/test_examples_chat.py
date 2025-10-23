"""Automated tests for the chat example.

This test suite runs the chat server and clients programmatically,
verifying the full flow works correctly.
"""

import asyncio

# Import the chat example classes
import sys
from pathlib import Path

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

examples_dir = Path(__file__).parent.parent.parent / "examples" / "chat"
sys.path.insert(0, str(examples_dir))

from server import ChatRoom  # noqa: E402  # type: ignore[import-not-found]


class MockChatClient(RpcTarget):
    """Mock client that collects messages instead of printing them."""

    def __init__(self, username: str):
        self.username = username
        self.messages: list[dict] = []

    async def call(self, method: str, args: list) -> None:
        match method:
            case "onMessage":
                self.messages.append(args[0])
            case _:
                msg = f"Unknown method: {method}"
                raise ValueError(msg)

    async def get_property(self, property: str):
        msg = f"Unknown property: {property}"
        raise ValueError(msg)


@pytest.fixture
async def chat_server():
    """Start a chat server for testing."""
    config = ServerConfig(host="127.0.0.1", port=0, include_stack_traces=False)
    server = Server(config)
    server.register_capability(0, ChatRoom())

    await server.start()
    port = server.port
    # Use WebSocket for bidirectional RPC
    yield f"ws://127.0.0.1:{port}/rpc/ws"

    await server.stop()


@pytest.mark.asyncio
async def test_chat_basic_flow(chat_server):
    """Test basic chat flow: join, send message, leave."""
    url = chat_server

    # Create client
    config = ClientConfig(url=url)

    async with Client(config) as client:
        # Create test client
        test_client = MockChatClient("Alice")
        client_stub = client.create_stub(test_client)

        # Join chat
        welcome = await client.call(0, "join", ["Alice", client_stub])
        assert welcome["message"] == "Welcome to the chat, Alice!"
        assert welcome["userCount"] == 1
        assert "Alice" in welcome["users"]

        # Send a message
        await client.call(0, "sendMessage", ["Alice", "Hello, World!"])

        # Alice should receive her own message
        await asyncio.sleep(0.1)  # Give server time to broadcast
        assert len(test_client.messages) >= 1
        msg = test_client.messages[-1]
        assert msg["username"] == "Alice"
        assert msg["text"] == "Hello, World!"
        assert msg["type"] == "chat"

        # List users
        users = await client.call(0, "listUsers", [])
        assert users == ["Alice"]

        # Leave chat
        await client.call(0, "leave", ["Alice"])


@pytest.mark.asyncio
async def test_chat_multiple_users(chat_server):
    """Test multiple users chatting."""
    url = chat_server

    # Create two clients
    alice_config = ClientConfig(url=url)
    bob_config = ClientConfig(url=url)

    async with Client(alice_config) as alice_client, Client(bob_config) as bob_client:
        # Create test clients
        alice_test = MockChatClient("Alice")
        bob_test = MockChatClient("Bob")

        alice_stub = alice_client.create_stub(alice_test)
        bob_stub = bob_client.create_stub(bob_test)

        # Alice joins
        await alice_client.call(0, "join", ["Alice", alice_stub])

        # Bob joins
        welcome = await bob_client.call(0, "join", ["Bob", bob_stub])
        assert welcome["userCount"] == 2
        assert set(welcome["users"]) == {"Alice", "Bob"}

        # Alice should see Bob joined
        await asyncio.sleep(0.1)
        assert len(alice_test.messages) >= 1
        join_msg = alice_test.messages[-1]
        assert join_msg["type"] == "system"
        assert "Bob joined" in join_msg["text"]

        # Alice sends message
        await alice_client.call(0, "sendMessage", ["Alice", "Hi Bob!"])

        # Bob should receive Alice's message
        await asyncio.sleep(0.1)
        assert len(bob_test.messages) >= 1
        msg = [m for m in bob_test.messages if m.get("type") == "chat"][-1]
        assert msg["username"] == "Alice"
        assert msg["text"] == "Hi Bob!"

        # Bob replies
        await bob_client.call(0, "sendMessage", ["Bob", "Hi Alice!"])

        # Alice should receive Bob's message
        await asyncio.sleep(0.1)
        msg = [m for m in alice_test.messages if m.get("type") == "chat"][-1]
        assert msg["username"] == "Bob"
        assert msg["text"] == "Hi Alice!"

        # List users
        users = await alice_client.call(0, "listUsers", [])
        assert set(users) == {"Alice", "Bob"}

        # Alice leaves
        await alice_client.call(0, "leave", ["Alice"])

        # Bob should see Alice left
        await asyncio.sleep(0.1)
        leave_msg = bob_test.messages[-1]
        assert leave_msg["type"] == "system"
        assert "Alice left" in leave_msg["text"]

        # Clean up
        await bob_client.call(0, "leave", ["Bob"])


@pytest.mark.asyncio
async def test_chat_duplicate_username(chat_server):
    """Test that duplicate usernames are rejected."""
    url = chat_server

    config1 = ClientConfig(url=url)
    config2 = ClientConfig(url=url)

    async with Client(config1) as client1, Client(config2) as client2:
        test1 = MockChatClient("Alice")
        test2 = MockChatClient("Alice")

        stub1 = client1.create_stub(test1)
        stub2 = client2.create_stub(test2)

        # First Alice joins
        await client1.call(0, "join", ["Alice", stub1])

        # Second Alice should be rejected
        with pytest.raises(Exception, match="already taken"):
            await client2.call(0, "join", ["Alice", stub2])

        # Clean up
        await client1.call(0, "leave", ["Alice"])


@pytest.mark.asyncio
async def test_chat_message_history(chat_server):
    """Test that new users receive message history."""
    url = chat_server

    # Alice joins and sends messages
    config1 = ClientConfig(url=url)
    async with Client(config1) as alice_client:
        alice_test = MockChatClient("Alice")
        alice_stub = alice_client.create_stub(alice_test)

        await alice_client.call(0, "join", ["Alice", alice_stub])
        await alice_client.call(0, "sendMessage", ["Alice", "Message 1"])
        await alice_client.call(0, "sendMessage", ["Alice", "Message 2"])

        await asyncio.sleep(0.1)

        # Bob joins - should see history in welcome
        config2 = ClientConfig(url=url)
        async with Client(config2) as bob_client:
            bob_test = MockChatClient("Bob")
            bob_stub = bob_client.create_stub(bob_test)

            welcome = await bob_client.call(0, "join", ["Bob", bob_stub])

            # Check history is present
            assert "history" in welcome
            history = welcome["history"]
            assert len(history) >= 2

            # Verify messages
            texts = [msg["text"] for msg in history]
            assert "Message 1" in texts
            assert "Message 2" in texts

            await bob_client.call(0, "leave", ["Bob"])

        await alice_client.call(0, "leave", ["Alice"])


@pytest.mark.asyncio
async def test_chat_broadcast_to_all(chat_server):
    """Test that messages are broadcast to all connected users."""
    url = chat_server

    # Create three clients
    configs = [ClientConfig(url=url) for _ in range(3)]
    clients = [Client(config) for config in configs]
    names = ["Alice", "Bob", "Charlie"]

    try:
        # Open all clients
        for client in clients:
            await client.__aenter__()  # noqa: PLC2801

        # Create test clients and join
        test_clients = []
        for i, name in enumerate(names):
            test_client = MockChatClient(name)
            test_clients.append(test_client)
            stub = clients[i].create_stub(test_client)
            await clients[i].call(0, "join", [name, stub])

        await asyncio.sleep(0.1)

        # Alice sends a message
        await clients[0].call(0, "sendMessage", ["Alice", "Hello everyone!"])

        # Wait for broadcast
        await asyncio.sleep(0.1)

        # All users should receive the message
        for test_client in test_clients:
            chat_messages = [m for m in test_client.messages if m.get("type") == "chat"]
            assert len(chat_messages) >= 1
            msg = chat_messages[-1]
            assert msg["username"] == "Alice"
            assert msg["text"] == "Hello everyone!"

        # Clean up
        for i, name in enumerate(names):
            await clients[i].call(0, "leave", [name])

    finally:
        # Close all clients
        for client in clients:
            await client.__aexit__(None, None, None)
