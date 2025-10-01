"""User Service - Manages user data and authentication.

This microservice demonstrates:
- Service-to-service RPC
- Capability passing between services
- Cross-service authentication
- Resource management

Run:
    python examples/microservices/user_service.py
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class User(RpcTarget):
    """Represents a single user - a capability that can be passed between services."""

    user_id: str
    username: str
    email: str
    role: str = "user"
    metadata: dict[str, Any] = field(default_factory=dict)

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle method calls on the user."""
        match method:
            case "getId":
                return self.user_id
            case "getUsername":
                return self.username
            case "getEmail":
                return self.email
            case "getRole":
                return self.role
            case "hasPermission":
                return self._has_permission(args[0])
            case "setMetadata":
                return self._set_metadata(args[0], args[1])
            case "getMetadata":
                return self._get_metadata(args[0])
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "id":
                return self.user_id
            case "username":
                return self.username
            case "email":
                return self.email
            case "role":
                return self.role
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

    def _has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Simple role-based access control
        user_permissions = {"order.create", "order.view", "profile.edit"}

        if self.role == "admin":
            return True  # Admin has all permissions
        if self.role == "user":
            return permission in user_permissions
        return False

    def _set_metadata(self, key: str, value: Any) -> dict[str, str]:
        """Set user metadata."""
        self.metadata[key] = value
        return {"status": "ok"}

    def _get_metadata(self, key: str) -> Any:
        """Get user metadata."""
        if key not in self.metadata:
            msg = f"Metadata key {key} not found"
            raise RpcError.not_found(msg)
        return self.metadata[key]


class UserService(RpcTarget):
    """User service - manages user accounts and authentication."""

    def __init__(self):
        # In-memory user database
        self.users: dict[str, User] = {
            "user1": User("user1", "alice", "alice@example.com", "admin"),
            "user2": User("user2", "bob", "bob@example.com", "user"),
            "user3": User("user3", "charlie", "charlie@example.com", "user"),
        }
        # Session tokens
        self.sessions: dict[str, User] = {}

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "authenticate":
                return await self._authenticate(args[0], args[1])
            case "getUser":
                return self._get_user(args[0])
            case "getUserByToken":
                return self._get_user_by_token(args[0])
            case "getUserDataByToken":
                return self._get_user_data_by_token(args[0])
            case "checkPermission":
                return self._check_permission(args[0], args[1])
            case "listUsers":
                return self._list_users()
            case "createUser":
                return self._create_user(args[0], args[1], args[2])
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "userCount":
                return len(self.users)
            case "sessionCount":
                return len(self.sessions)
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

    async def _authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate a user and return a session token.

        In a real system, this would verify password hashes.
        For this example, we just check username exists.
        """
        # Find user by username
        user = None
        for u in self.users.values():
            if u.username == username:
                user = u
                break

        if user is None:
            msg = "Invalid credentials"
            raise RpcError.permission_denied(msg)

        # Create session token (in real system, use secure random tokens)
        session_token = f"token_{username}_{len(self.sessions)}"
        self.sessions[session_token] = user

        logger.info("User %s authenticated, token: %s", username, session_token)

        return {
            "token": session_token,
            "userId": user.user_id,
            "username": user.username,
            "role": user.role,
        }

    def _get_user(self, user_id: str) -> User:
        """Get a user by ID.

        Returns a User capability that can be passed to other services.
        """
        if user_id not in self.users:
            msg = f"User {user_id} not found"
            raise RpcError.not_found(msg)

        return self.users[user_id]

    def _get_user_by_token(self, token: str) -> User:
        """Get a user by session token.

        Returns a User capability.
        """
        if token not in self.sessions:
            msg = "Invalid or expired token"
            raise RpcError.permission_denied(msg)

        return self.sessions[token]

    def _get_user_data_by_token(self, token: str) -> dict[str, str]:
        """Get user data by session token (returns plain data, not capability)."""
        if token not in self.sessions:
            msg = "Invalid or expired token"
            raise RpcError.permission_denied(msg)

        user = self.sessions[token]
        return {
            "userId": user.user_id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }

    def _check_permission(self, token: str, permission: str) -> bool:
        """Check if the user with this token has the given permission."""
        if token not in self.sessions:
            return False

        user = self.sessions[token]
        return user._has_permission(permission)

    def _list_users(self) -> list[dict[str, str]]:
        """List all users (returns public info only, not capabilities)."""
        return [
            {"id": user.user_id, "username": user.username, "role": user.role}
            for user in self.users.values()
        ]

    def _create_user(
        self, username: str, email: str, role: str = "user"
    ) -> dict[str, str]:
        """Create a new user."""
        # Check if username already exists
        for user in self.users.values():
            if user.username == username:
                msg = f"Username {username} already exists"
                raise RpcError.bad_request(msg)

        # Generate new user ID
        user_id = f"user{len(self.users) + 1}"

        # Create user
        user = User(user_id, username, email, role)
        self.users[user_id] = user

        logger.info("Created new user: %s (id: %s, role: %s)", username, user_id, role)

        return {"userId": user_id, "username": username, "email": email, "role": role}


async def main():
    """Run the user service."""
    config = ServerConfig(
        host="127.0.0.1",
        port=8081,  # User service on port 8081
        include_stack_traces=False,
    )

    server = Server(config)

    # Register the user service at capability ID 0
    user_service = UserService()
    server.register_capability(0, user_service)

    async with server:
        logger.info("🔐 User Service running on http://127.0.0.1:8081")
        logger.info("   Endpoint: http://127.0.0.1:8081/rpc/batch")
        logger.info("")
        logger.info("Available users:")
        logger.info("  - alice (admin)")
        logger.info("  - bob (user)")
        logger.info("  - charlie (user)")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("\nShutting down user service...")


if __name__ == "__main__":
    asyncio.run(main())
