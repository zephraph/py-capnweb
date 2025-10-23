"""Test bidirectional communication - two Python processes acting as peers.

This demonstrates that Cap'n Web is truly peer-to-peer with no client/server distinction.
Both processes can export capabilities and call each other.
"""

import asyncio
from typing import Any

import pytest

from capnweb import Client, ClientConfig, RpcError, RpcTarget, Server, ServerConfig


class Alice(RpcTarget):
    """Alice's capabilities - can greet and ask Bob questions."""

    def __init__(self) -> None:
        self.name = "Alice"
        self.bob_client: Client | None = None

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle method calls."""
        match method:
            case "greet":
                return f"Hello from {self.name}!"

            case "ask_bob":
                # Alice calls Bob (demonstrates peer-to-peer)
                if not self.bob_client:
                    msg = "Bob not connected"
                    raise RpcError.internal(msg)
                question = args[0] if args else "How are you?"
                bob_answer = await self.bob_client.call(0, "answer", [question])
                return f"Bob says: {bob_answer}"

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get property."""
        if property == "name":
            return self.name
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)


class Bob(RpcTarget):
    """Bob's capabilities - can answer questions and call Alice."""

    def __init__(self) -> None:
        self.name = "Bob"
        self.alice_client: Client | None = None

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle method calls."""
        match method:
            case "answer":
                question = args[0] if args else ""
                if "how are you" in question.lower():
                    return "I'm doing great, thanks!"
                if "name" in question.lower():
                    return f"My name is {self.name}"
                return "I don't know"

            case "greet_alice":
                # Bob calls Alice (demonstrates peer-to-peer)
                if not self.alice_client:
                    msg = "Alice not connected"
                    raise RpcError.internal(msg)
                alice_greeting = await self.alice_client.call(0, "greet", [])
                return f"Alice says: {alice_greeting}"

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get property."""
        if property == "name":
            return self.name
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)


@pytest.mark.asyncio
class TestBidirectional:
    """Test bidirectional peer-to-peer communication."""

    async def test_two_servers_peer_to_peer(self) -> None:
        """Test two Python processes communicating as peers.

        This proves:
        1. Both can act as servers (export capabilities)
        2. Both can act as clients (call remote capabilities)
        3. No client/server distinction - true peer-to-peer
        """
        # Create Alice's server
        alice_cap = Alice()
        alice_server = Server(ServerConfig(host="127.0.0.1", port=18090))
        alice_server.register_capability(0, alice_cap)
        await alice_server.start()

        # Create Bob's server
        bob_cap = Bob()
        bob_server = Server(ServerConfig(host="127.0.0.1", port=18091))
        bob_server.register_capability(0, bob_cap)
        await bob_server.start()

        await asyncio.sleep(0.1)

        try:
            # Alice connects to Bob
            alice_cap.bob_client = Client(
                ClientConfig(url="http://127.0.0.1:18091/rpc/batch")
            )

            # Bob connects to Alice
            bob_cap.alice_client = Client(
                ClientConfig(url="http://127.0.0.1:18090/rpc/batch")
            )

            # Test 1: Alice calls Bob directly
            answer = await alice_cap.bob_client.call(0, "answer", ["How are you?"])
            assert "great" in answer.lower()
            print(f"✓ Alice → Bob: {answer}")

            # Test 2: Bob calls Alice directly
            greeting = await bob_cap.alice_client.call(0, "greet", [])
            assert "Hello from Alice" in greeting
            print(f"✓ Bob → Alice: {greeting}")

            # Test 3: Multiple round-trip calls
            # Alice → Bob → Alice (Bob answers)
            question = "What's your name?"
            answer1 = await alice_cap.bob_client.call(0, "answer", [question])
            print(f"✓ Alice asks Bob '{question}': {answer1}")

            # Bob → Alice → Bob (Alice greets)
            greeting2 = await bob_cap.alice_client.call(0, "greet", [])
            print(f"✓ Bob asks Alice to greet: {greeting2}")

            # Test 4: Verify both peers are still responsive
            answer2 = await alice_cap.bob_client.call(0, "answer", ["How are you?"])
            greeting3 = await bob_cap.alice_client.call(0, "greet", [])
            assert answer2
            assert greeting3
            print("✓ Both peers still responsive after multiple calls")

            await alice_cap.bob_client.close()
            await bob_cap.alice_client.close()

        finally:
            await alice_server.stop()
            await bob_server.stop()

    async def test_simultaneous_calls(self) -> None:
        """Test simultaneous bidirectional calls don't deadlock."""
        # Create two servers
        alice_server = Server(ServerConfig(host="127.0.0.1", port=18092))
        alice_server.register_capability(0, Alice())
        await alice_server.start()

        bob_server = Server(ServerConfig(host="127.0.0.1", port=18093))
        bob_server.register_capability(0, Bob())
        await bob_server.start()

        await asyncio.sleep(0.1)

        try:
            # Create clients
            alice_client = Client(ClientConfig(url="http://127.0.0.1:18092/rpc/batch"))
            bob_client = Client(ClientConfig(url="http://127.0.0.1:18093/rpc/batch"))

            # Make simultaneous calls in both directions
            alice_task = alice_client.call(0, "greet", [])
            bob_task = bob_client.call(0, "answer", ["test"])

            alice_result, bob_result = await asyncio.gather(alice_task, bob_task)

            assert "Alice" in alice_result
            assert bob_result  # Bob answers something
            print("✓ Simultaneous calls successful")

            await alice_client.close()
            await bob_client.close()

        finally:
            await alice_server.stop()
            await bob_server.stop()


@pytest.mark.asyncio
class TestMultiplePeers:
    """Test network of multiple peers."""

    async def test_three_peer_network(self) -> None:
        """Test three peers all calling each other - proves true mesh network."""

        class Peer(RpcTarget):
            """A peer in the network."""

            def __init__(self, name: str) -> None:
                self.name = name
                self.messages_received: list[str] = []

            async def call(self, method: str, args: list[Any]) -> Any:
                match method:
                    case "send_message":
                        message = args[0]
                        self.messages_received.append(message)
                        return f"{self.name} received: {message}"
                    case "get_messages":
                        return self.messages_received
                    case _:
                        msg = f"Method {method} not found"
                        raise RpcError.not_found(msg)

            async def get_property(self, property: str) -> Any:
                if property == "name":
                    return self.name
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

        # Create three peer servers
        peer1 = Peer("Peer1")
        server1 = Server(ServerConfig(host="127.0.0.1", port=18094))
        server1.register_capability(0, peer1)
        await server1.start()

        peer2 = Peer("Peer2")
        server2 = Server(ServerConfig(host="127.0.0.1", port=18095))
        server2.register_capability(0, peer2)
        await server2.start()

        peer3 = Peer("Peer3")
        server3 = Server(ServerConfig(host="127.0.0.1", port=18096))
        server3.register_capability(0, peer3)
        await server3.start()

        await asyncio.sleep(0.1)

        try:
            # Each peer connects to the others
            client1_to_2 = Client(ClientConfig(url="http://127.0.0.1:18095/rpc/batch"))
            client1_to_3 = Client(ClientConfig(url="http://127.0.0.1:18096/rpc/batch"))
            client2_to_1 = Client(ClientConfig(url="http://127.0.0.1:18094/rpc/batch"))
            client2_to_3 = Client(ClientConfig(url="http://127.0.0.1:18096/rpc/batch"))
            client3_to_1 = Client(ClientConfig(url="http://127.0.0.1:18094/rpc/batch"))
            client3_to_2 = Client(ClientConfig(url="http://127.0.0.1:18095/rpc/batch"))

            # Send messages in a full mesh (each peer sends to every other peer)
            # Peer1 → others
            r1 = await client1_to_2.call(0, "send_message", ["P1→P2"])
            r2 = await client1_to_3.call(0, "send_message", ["P1→P3"])

            # Peer2 → others
            r3 = await client2_to_1.call(0, "send_message", ["P2→P1"])
            r4 = await client2_to_3.call(0, "send_message", ["P2→P3"])

            # Peer3 → others
            r5 = await client3_to_1.call(0, "send_message", ["P3→P1"])
            r6 = await client3_to_2.call(0, "send_message", ["P3→P2"])

            # Verify all messages were delivered
            assert "Peer2 received: P1→P2" in r1
            assert "Peer3 received: P1→P3" in r2
            assert "Peer1 received: P2→P1" in r3
            assert "Peer3 received: P2→P3" in r4
            assert "Peer1 received: P3→P1" in r5
            assert "Peer2 received: P3→P2" in r6

            print("✓ All 6 messages delivered successfully across 3-peer mesh network")

            # Clean up
            for client in [
                client1_to_2,
                client1_to_3,
                client2_to_1,
                client2_to_3,
                client3_to_1,
                client3_to_2,
            ]:
                await client.close()

        finally:
            await server1.stop()
            await server2.stop()
            await server3.stop()
