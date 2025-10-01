"""API Gateway - Entry point for all client requests.

This demonstrates:
- Service mesh orchestration
- Request routing to backend services
- Authentication token management
- Capability-based security across services

Run (after starting user_service and order_service):
    python examples/microservices/api_gateway.py
"""

import asyncio
import logging
from typing import Any

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApiGateway(RpcTarget):
    """API Gateway that routes requests to backend services."""

    def __init__(self, user_service_url: str, order_service_url: str):
        self.user_service_url = user_service_url
        self.order_service_url = order_service_url
        self.user_client: Client | None = None
        self.order_client: Client | None = None

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "login":
                return await self._login(args[0], args[1])
            case "listUsers":
                return await self._list_users(args[0])
            case "createOrder":
                return await self._create_order(args[0], args[1])
            case "listOrders":
                return await self._list_orders(args[0])
            case "cancelOrder":
                return await self._cancel_order(args[0], args[1])
            case "getUserProfile":
                return await self._get_user_profile(args[0])
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)

    async def _get_user_client(self) -> Client:
        """Get or create user service client."""
        if self.user_client is None:
            config = ClientConfig(url=self.user_service_url)
            self.user_client = Client(config)
        return self.user_client

    async def _get_order_client(self) -> Client:
        """Get or create order service client."""
        if self.order_client is None:
            config = ClientConfig(url=self.order_service_url)
            self.order_client = Client(config)
        return self.order_client

    async def _login(self, username: str, password: str) -> dict[str, Any]:
        """Login via user service."""
        user_client = await self._get_user_client()
        result = await user_client.call(0, "authenticate", [username, password])

        logger.info("User %s logged in, role: %s", username, result["role"])
        return result

    async def _list_users(self, token: str) -> list[dict]:
        """List users (requires authentication)."""
        user_client = await self._get_user_client()

        # Verify token is valid (this will raise error if invalid)
        await user_client.call(0, "getUserDataByToken", [token])

        # Get user list
        users = await user_client.call(0, "listUsers", [])

        return users

    async def _create_order(self, token: str, items: list[dict]) -> dict[str, Any]:
        """Create an order (requires authentication)."""
        user_client = await self._get_user_client()
        order_client = await self._get_order_client()

        # Get user data from token
        user_data = await user_client.call(0, "getUserDataByToken", [token])
        user_id = user_data["userId"]

        # Check permission
        has_permission = await user_client.call(
            0, "checkPermission", [token, "order.create"]
        )
        if not has_permission:
            msg = "You don't have permission to create orders"
            raise RpcError.permission_denied(msg)

        # Create order in order service
        result = await order_client.call(0, "createOrder", [user_id, items])

        logger.info(
            "Order %s created by %s, total: $%.2f",
            result["orderId"],
            user_data["username"],
            result["total"],
        )

        return result

    async def _list_orders(self, token: str) -> list[dict]:
        """List user's orders."""
        user_client = await self._get_user_client()
        order_client = await self._get_order_client()

        # Get user data
        user_data = await user_client.call(0, "getUserDataByToken", [token])
        user_id = user_data["userId"]

        # List orders for this user
        orders = await order_client.call(0, "listOrders", [user_id])

        return orders

    async def _cancel_order(self, token: str, order_id: str) -> dict[str, str]:
        """Cancel an order."""
        user_client = await self._get_user_client()
        order_client = await self._get_order_client()

        # Check permission
        has_permission = await user_client.call(
            0, "checkPermission", [token, "order.cancel"]
        )
        if not has_permission:
            msg = "You don't have permission to cancel orders"
            raise RpcError.permission_denied(msg)

        # Cancel order
        result = await order_client.call(0, "cancelOrder", [order_id])

        return result

    async def _get_user_profile(self, token: str) -> dict[str, Any]:
        """Get user profile information."""
        user_client = await self._get_user_client()

        # Get user data directly (no capability needed)
        user_data = await user_client.call(0, "getUserDataByToken", [token])

        return user_data


async def main():
    """Run the API gateway."""
    config = ServerConfig(
        host="127.0.0.1",
        port=8080,  # API gateway on port 8080
        include_stack_traces=False,
    )

    server = Server(config)

    # Create API gateway that connects to backend services
    gateway = ApiGateway(
        user_service_url="http://127.0.0.1:8081/rpc/batch",
        order_service_url="http://127.0.0.1:8082/rpc/batch",
    )
    server.register_capability(0, gateway)

    async with server:
        logger.info("🌐 API Gateway running on http://127.0.0.1:8080")
        logger.info("   Endpoint: http://127.0.0.1:8080/rpc/batch")
        logger.info("")
        logger.info("Backend services:")
        logger.info("   User Service:  http://127.0.0.1:8081")
        logger.info("   Order Service: http://127.0.0.1:8082")
        logger.info("")
        logger.info("Run client with: python examples/microservices/client.py")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("\nShutting down API gateway...")


if __name__ == "__main__":
    asyncio.run(main())
