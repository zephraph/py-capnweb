#!/usr/bin/env python3
"""Alice - A peer in the Cap'n Web network.

Run this alongside bob.py to demonstrate peer-to-peer communication.

Usage:
    python alice.py
"""

import asyncio
from typing import Any

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class Alice(RpcTarget):
    """Alice's capabilities."""

    def __init__(self) -> None:
        self.name = "Alice"
        self.message_count = 0

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC calls."""
        match method:
            case "greet":
                return f"Hello! I'm {self.name}."

            case "chat":
                message = args[0] if args else ""
                self.message_count += 1
                print(f"📨 Alice received: {message}")
                return f"Alice says: Thanks for the message #{self.message_count}!"

            case "get_stats":
                return {
                    "name": self.name,
                    "messages_received": self.message_count,
                }

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get property value."""
        if property == "name":
            return self.name
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)


async def main() -> None:
    """Run Alice's server and demonstrate calling Bob."""
    print("🚀 Starting Alice on port 8080...")

    # Create Alice's server
    alice = Alice()
    config = ServerConfig(host="127.0.0.1", port=8080)
    server = Server(config)
    server.register_capability(0, alice)

    await server.start()
    print("✅ Alice is running!")
    print("   - Alice exports her capabilities at http://127.0.0.1:8080/rpc/batch")
    print("   - Alice can receive calls from Bob")
    print()

    # Wait a moment for Bob to start
    await asyncio.sleep(1)

    # Try to connect to Bob
    print("🔗 Connecting to Bob at http://127.0.0.1:8081...")
    try:
        bob_client = Client(ClientConfig(url="http://127.0.0.1:8081/rpc/batch"))

        # Call Bob
        print("📞 Alice calls Bob.greet()...")
        greeting = await bob_client.call(0, "greet", [])
        print(f"   ← {greeting}")

        # Send Bob a message
        print("📞 Alice calls Bob.chat('Hi Bob!')...")
        response = await bob_client.call(0, "chat", ["Hi Bob, this is Alice!"])
        print(f"   ← {response}")

        # Get Bob's stats
        print("📞 Alice calls Bob.get_stats()...")
        stats = await bob_client.call(0, "get_stats", [])
        print(f"   ← {stats}")

        await bob_client.close()

    except Exception as e:
        print(f"❌ Could not connect to Bob: {e}")
        print("   Make sure bob.py is running!")

    # Keep server running
    print()
    print("⏳ Alice is waiting for calls from Bob...")
    print("   (Press Ctrl+C to stop)")

    try:
        # Keep running forever - wait on event that never gets set
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 Alice shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
