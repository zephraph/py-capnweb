#!/usr/bin/env python3
"""Bob - A peer in the Cap'n Web network.

Run this alongside alice.py to demonstrate peer-to-peer communication.

Usage:
    python bob.py
"""

import asyncio
from typing import Any

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class Bob(RpcTarget):
    """Bob's capabilities."""

    def __init__(self) -> None:
        self.name = "Bob"
        self.message_count = 0

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC calls."""
        match method:
            case "greet":
                return f"Hey there! I'm {self.name}."

            case "chat":
                message = args[0] if args else ""
                self.message_count += 1
                print(f"📨 Bob received: {message}")
                return f"Bob says: Got your message #{self.message_count}!"

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
    """Run Bob's server and demonstrate calling Alice."""
    print("🚀 Starting Bob on port 8081...")

    # Create Bob's server
    bob = Bob()
    config = ServerConfig(host="127.0.0.1", port=8081)
    server = Server(config)
    server.register_capability(0, bob)

    await server.start()
    print("✅ Bob is running!")
    print("   - Bob exports his capabilities at http://127.0.0.1:8081/rpc/batch")
    print("   - Bob can receive calls from Alice")
    print()

    # Wait a moment
    await asyncio.sleep(2)

    # Try to connect to Alice
    print("🔗 Connecting to Alice at http://127.0.0.1:8080...")
    try:
        alice_client = Client(ClientConfig(url="http://127.0.0.1:8080/rpc/batch"))

        # Call Alice
        print("📞 Bob calls Alice.greet()...")
        greeting = await alice_client.call(0, "greet", [])
        print(f"   ← {greeting}")

        # Send Alice a message
        print("📞 Bob calls Alice.chat('Hi Alice!')...")
        response = await alice_client.call(0, "chat", ["Hi Alice, this is Bob!"])
        print(f"   ← {response}")

        # Get Alice's stats
        print("📞 Bob calls Alice.get_stats()...")
        stats = await alice_client.call(0, "get_stats", [])
        print(f"   ← {stats}")

        await alice_client.close()

    except Exception as e:
        print(f"❌ Could not connect to Alice: {e}")
        print("   Make sure alice.py is running!")

    # Keep server running
    print()
    print("⏳ Bob is waiting for calls from Alice...")
    print("   (Press Ctrl+C to stop)")

    try:
        # Keep running forever
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Bob shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
