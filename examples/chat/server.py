"""Real-time chat server using WebSocket transport.

This example demonstrates:
- WebSocket transport for persistent connections
- Bidirectional RPC (server can call client methods)
- Multiple connected clients
- Broadcasting messages to all clients
- Client capability management

Run:
    python examples/chat/server.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

if TYPE_CHECKING:
    from capnweb.stubs import RpcStub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatRoom(RpcTarget):
    """Chat room that manages multiple clients and broadcasts messages."""

    def __init__(self):
        self.clients: dict[str, RpcStub] = {}  # username -> client capability
        self.message_history: list[dict[str, str]] = []

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "join":
                return await self._join(args[0], args[1])
            case "leave":
                return await self._leave(args[0])
            case "sendMessage":
                return await self._send_message(args[0], args[1])
            case "getHistory":
                return self._get_history()
            case "listUsers":
                return self._list_users()
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "userCount":
                return len(self.clients)
            case "messageCount":
                return len(self.message_history)
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

    async def _join(self, username: str, client_capability: RpcStub) -> dict[str, Any]:
        """Add a client to the chat room.

        Args:
            username: The user's chosen username
            client_capability: Capability to the client for bidirectional RPC

        Returns:
            Welcome message with room info
        """
        if username in self.clients:
            msg = f"Username {username} is already taken"
            raise RpcError.bad_request(msg)

        # Store client capability
        self.clients[username] = client_capability

        # Notify all other clients about the new user
        join_msg = f"{username} joined the chat"
        await self._broadcast_system_message(join_msg, exclude=username)

        logger.info("User %s joined (total: %d users)", username, len(self.clients))

        return {
            "message": f"Welcome to the chat, {username}!",
            "userCount": len(self.clients),
            "users": list(self.clients.keys()),
        }

    async def _leave(self, username: str) -> dict[str, str]:
        """Remove a client from the chat room."""
        if username not in self.clients:
            msg = f"User {username} not found"
            raise RpcError.not_found(msg)

        # Remove client
        client = self.clients.pop(username)
        client.dispose()  # Clean up the capability

        # Notify remaining clients
        leave_msg = f"{username} left the chat"
        await self._broadcast_system_message(leave_msg)

        logger.info("User %s left (remaining: %d users)", username, len(self.clients))

        return {"message": f"Goodbye, {username}!"}

    async def _send_message(self, username: str, text: str) -> dict[str, str | int]:
        """Broadcast a message to all clients."""
        if username not in self.clients:
            msg = f"User {username} not in chat room"
            raise RpcError.not_found(msg)

        # Store in history
        message = {"username": username, "text": text, "type": "chat"}
        self.message_history.append(message)

        # Broadcast to all clients (including sender)
        await self._broadcast_message(message)

        logger.info("[%s] %s", username, text)

        return {"status": "sent", "timestamp": len(self.message_history)}

    def _get_history(self) -> list[dict[str, str]]:
        """Get recent message history."""
        # Return last 50 messages
        return self.message_history[-50:]

    def _list_users(self) -> list[str]:
        """Get list of connected users."""
        return list(self.clients.keys())

    async def _broadcast_message(self, message: dict[str, str]) -> None:
        """Broadcast a message to all clients."""
        # Create a list of tasks to call all clients in parallel
        tasks = []
        for username, client in list(self.clients.items()):
            try:
                # Call the client's onMessage method
                task = client.onMessage(message)
                tasks.append((username, task))
            except Exception as e:
                logger.error("Error preparing broadcast to %s: %s", username, e)

        # Execute all calls in parallel
        for username, task in tasks:
            try:
                await task
            except Exception as e:
                logger.error("Error broadcasting to %s: %s", username, e)
                # Remove client if they're unreachable
                if username in self.clients:
                    self.clients.pop(username).dispose()

    async def _broadcast_system_message(
        self, text: str, exclude: str | None = None
    ) -> None:
        """Broadcast a system message to all clients."""
        message = {"username": "System", "text": text, "type": "system"}
        self.message_history.append(message)

        tasks = []
        for username, client in list(self.clients.items()):
            if username != exclude:
                try:
                    task = client.onMessage(message)
                    tasks.append((username, task))
                except Exception as e:
                    logger.error(
                        "Error preparing system message to %s: %s", username, e
                    )

        for username, task in tasks:
            try:
                await task
            except Exception as e:
                logger.error("Error sending system message to %s: %s", username, e)


async def main():
    """Run the chat server."""
    config = ServerConfig(
        host="127.0.0.1",
        port=8080,
        include_stack_traces=False,  # Security: disabled in production
    )

    server = Server(config)

    # Create and register the chat room
    chat_room = ChatRoom()
    server.register_capability(0, chat_room)

    async with server:
        logger.info("🚀 Chat server running on http://127.0.0.1:8080")
        logger.info("   WebSocket endpoint: ws://127.0.0.1:8080/rpc/ws")
        logger.info("   HTTP endpoint: http://127.0.0.1:8080/rpc/batch")
        logger.info("")
        logger.info("Run clients with: python examples/chat/client.py")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("\nShutting down chat server...")


if __name__ == "__main__":
    asyncio.run(main())
