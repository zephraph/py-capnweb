#!/usr/bin/env python3
"""Python interop server for testing with TypeScript client.

This server implements a comprehensive test API that exercises all major
features of the Cap'n Web protocol:
- Basic method calls
- Property access
- Error handling
- Capability passing
- Promise pipelining
- Nested objects
"""

import asyncio
import sys
from typing import Any

from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget


class User(RpcTarget):
    """Represents a user object."""

    def __init__(self, user_id: int, name: str, email: str):
        self.user_id = user_id
        self.name = name
        self.email = email

    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "getName":
                return self.name
            case "getEmail":
                return self.email
            case "updateName":
                old_name = self.name
                self.name = args[0]
                return {"old": old_name, "new": self.name}
            case _:
                msg = f"Method {method} not found on User"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        match property:
            case "id":
                return self.user_id
            case "name":
                return self.name
            case "email":
                return self.email
            case _:
                msg = f"Property {property} not found on User"
                raise RpcError.not_found(msg)


class TestService(RpcTarget):
    """Main test service with comprehensive API."""

    def __init__(self):
        self.users = {
            1: User(1, "Alice", "alice@example.com"),
            2: User(2, "Bob", "bob@example.com"),
            3: User(3, "Charlie", "charlie@example.com"),
        }

    async def call(self, method: str, args: list[Any]) -> Any:
        match method:
            case "echo":
                # Simple echo - returns what it receives
                return args[0] if args else None

            case "add":
                # Basic arithmetic
                return args[0] + args[1]

            case "multiply":
                # Basic arithmetic
                return args[0] * args[1]

            case "concat":
                # String concatenation
                return "".join(str(arg) for arg in args)

            case "getUser":
                # Return a capability (User object)
                user_id = args[0]
                if user_id not in self.users:
                    msg = f"User {user_id} not found"
                    raise RpcError.not_found(msg)
                return self.users[user_id]

            case "getUserName":
                # Nested call: get user and return name
                user_id = args[0]
                if user_id not in self.users:
                    msg = f"User {user_id} not found"
                    raise RpcError.not_found(msg)
                return self.users[user_id].name

            case "createUser":
                # Create and return a new user
                user_id = args[0]
                name = args[1]
                email = args[2]
                user = User(user_id, name, email)
                self.users[user_id] = user
                return user

            case "getUserCount":
                # Simple property access
                return len(self.users)

            case "getAllUserNames":
                # Return array of names
                return [user.name for user in self.users.values()]

            case "throwError":
                # Test error handling
                error_type = args[0] if args else "internal"
                match error_type:
                    case "not_found":
                        msg = "Resource not found"
                        raise RpcError.not_found(msg)
                    case "bad_request":
                        msg = "Invalid request"
                        raise RpcError.bad_request(msg)
                    case "permission_denied":
                        msg = "Access denied"
                        raise RpcError.permission_denied(msg)
                    case _:
                        msg = "Internal server error"
                        raise RpcError.internal(msg)

            case "processArray":
                # Test array handling
                arr = args[0]
                return [x * 2 for x in arr]

            case "processObject":
                # Test object handling
                obj = args[0]
                return {
                    "original": obj,
                    "keys": list(obj.keys()),
                    "count": len(obj),
                }

            case "asyncDelay":
                # Test async behavior
                delay = args[0] if args else 0.1
                await asyncio.sleep(delay)
                return f"Delayed {delay}s"

            case "batchTest":
                # Return data for batch testing
                return {
                    "timestamp": asyncio.get_event_loop().time(),
                    "value": args[0] if args else 0,
                }

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        match property:
            case "version":
                return "1.0.0"
            case "language":
                return "python"
            case "userCount":
                return len(self.users)
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)


async def main() -> None:
    """Start the Python interop server."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    config = ServerConfig(
        host="127.0.0.1",
        port=port,
        include_stack_traces=True,  # Helpful for debugging interop issues
    )
    server = Server(config)

    # Register the main test service
    server.register_capability(0, TestService())

    await server.start()

    print(f"Python interop server listening on http://127.0.0.1:{port}/rpc/batch")
    print("Ready for interop testing...")

    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
