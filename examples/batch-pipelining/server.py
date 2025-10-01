"""Minimal HTTP server exposing an RPC endpoint over HTTP batching.

Usage:
    1) Start server: python examples/batch-pipelining/server.py
    2) In another terminal: python examples/batch-pipelining/client.py
"""

import asyncio
import os
from typing import Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

# Simple in-memory data
USERS = {
    "cookie-123": {"id": "u_1", "name": "Ada Lovelace"},
    "cookie-456": {"id": "u_2", "name": "Alan Turing"},
}

PROFILES = {
    "u_1": {"id": "u_1", "bio": "Mathematician & first programmer"},
    "u_2": {"id": "u_2", "bio": "Mathematician & computer science pioneer"},
}

NOTIFICATIONS = {
    "u_1": ["Welcome to capnweb!", "You have 2 new followers"],
    "u_2": ["New feature: pipelining!", "Security tips for your account"],
}


class Api(RpcTarget):
    """Server-side API implementation."""

    async def authenticate(self, session_token: str) -> dict[str, str]:
        """Simulate authentication from a session cookie/token."""
        delay_ms = int(os.getenv("DELAY_AUTH_MS", "80"))
        await asyncio.sleep(delay_ms / 1000.0)

        user = USERS.get(session_token)
        if not user:
            msg = "Invalid session"
            raise ValueError(msg)
        return user  # {"id": ..., "name": ...}

    async def get_user_profile(self, user_id: str) -> dict[str, str]:
        """Get user profile by ID."""
        delay_ms = int(os.getenv("DELAY_PROFILE_MS", "120"))
        await asyncio.sleep(delay_ms / 1000.0)

        profile = PROFILES.get(user_id)
        if not profile:
            msg = "No such user"
            raise ValueError(msg)
        return profile  # {"id": ..., "bio": ...}

    async def get_notifications(self, user_id: str) -> list[str]:
        """Get notifications for user."""
        delay_ms = int(os.getenv("DELAY_NOTIFS_MS", "120"))
        await asyncio.sleep(delay_ms / 1000.0)

        return NOTIFICATIONS.get(user_id, [])

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC calls by delegating to specific methods."""
        match method:
            case "authenticate":
                return await self.authenticate(args[0] if args else "")
            case "getUserProfile":
                return await self.get_user_profile(args[0] if args else "")
            case "getNotifications":
                return await self.get_notifications(args[0] if args else "")
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get property value."""
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)


async def main() -> None:
    """Run the RPC server."""
    port = int(os.getenv("PORT", "3000"))

    # Create server and register API
    config = ServerConfig(host="localhost", port=port)
    server = Server(config)
    api = Api()

    # Register the API as the main capability (export_id=0)
    server.register_capability(0, api)

    # Start the server
    await server.start()

    print(f"RPC server listening on http://localhost:{port}/rpc/batch")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
