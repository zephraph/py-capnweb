"""Order Service - Manages orders with user authentication.

This microservice demonstrates:
- Service-to-service RPC calls
- Cross-service authentication using capabilities
- Permission checking via user capabilities
- Service mesh communication

Run:
    python examples/microservices/order_service.py
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Order(RpcTarget):
    """Represents a single order."""

    order_id: str
    user_id: str
    items: list[dict]
    total: float
    status: str = "pending"

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle method calls."""
        match method:
            case "getId":
                return self.order_id
            case "getUserId":
                return self.user_id
            case "getItems":
                return self.items
            case "getTotal":
                return self.total
            case "getStatus":
                return self.status
            case "cancel":
                return await self._cancel()
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "id":
                return self.order_id
            case "userId":
                return self.user_id
            case "items":
                return self.items
            case "total":
                return self.total
            case "status":
                return self.status
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

    async def _cancel(self) -> dict[str, str]:
        """Cancel the order."""
        if self.status == "cancelled":
            msg = "Order is already cancelled"
            raise RpcError.bad_request(msg)

        self.status = "cancelled"
        logger.info("Order %s cancelled", self.order_id)

        return {"status": "cancelled", "orderId": self.order_id}


class OrderService(RpcTarget):
    """Order service - manages orders and coordinates with user service."""

    def __init__(self, user_service_url: str):
        self.user_service_url = user_service_url
        self.user_service_client: Client | None = None
        self.orders: dict[str, Order] = {}
        self.next_order_id = 1

    async def call(self, method: str, args: list[Any]) -> Any:
        """Handle RPC method calls."""
        match method:
            case "createOrder":
                return await self._create_order(args[0], args[1])
            case "getOrder":
                return self._get_order(args[0])
            case "listOrders":
                return await self._list_orders(args[0] if args else None)
            case "cancelOrder":
                return await self._cancel_order(args[0])
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Handle property access."""
        match property:
            case "orderCount":
                return len(self.orders)
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)

    async def _get_user_service(self) -> Client:
        """Get or create user service client."""
        if self.user_service_client is None:
            config = ClientConfig(url=self.user_service_url)
            self.user_service_client = Client(config)
        return self.user_service_client

    async def _create_order(self, user_id: str, items: list[dict]) -> dict[str, Any]:
        """Create a new order.

        Args:
            user_id: User ID from auth token (permissions already checked by gateway)
            items: List of items to order
        """
        # Calculate total
        total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)

        # Create order
        order_id = f"order{self.next_order_id}"
        self.next_order_id += 1

        order = Order(order_id, user_id, items, total)
        self.orders[order_id] = order

        logger.info(
            "Created order %s for user %s, total: $%.2f", order_id, user_id, total
        )

        return {
            "orderId": order_id,
            "userId": user_id,
            "items": items,
            "total": total,
            "status": "pending",
        }

    def _get_order(self, order_id: str) -> Order:
        """Get an order by ID (returns capability)."""
        if order_id not in self.orders:
            msg = f"Order {order_id} not found"
            raise RpcError.not_found(msg)

        return self.orders[order_id]

    async def _list_orders(self, user_id: str | None = None) -> list[dict]:
        """List orders (optionally filtered by user)."""
        if user_id is None:
            # No filter, return all orders
            orders = list(self.orders.values())
        else:
            # Filter by user
            orders = [o for o in self.orders.values() if o.user_id == user_id]

        return [
            {
                "orderId": o.order_id,
                "userId": o.user_id,
                "items": o.items,
                "total": o.total,
                "status": o.status,
            }
            for o in orders
        ]

    async def _cancel_order(self, order_id: str) -> dict[str, str]:
        """Cancel an order (permissions already checked by gateway)."""
        order = self._get_order(order_id)

        # Cancel the order
        return await order.call("cancel", [])


async def main():
    """Run the order service."""
    config = ServerConfig(
        host="127.0.0.1",
        port=8082,  # Order service on port 8082
        include_stack_traces=False,
    )

    server = Server(config)

    # Register the order service at capability ID 0
    # It will call the user service at http://127.0.0.1:8081
    order_service = OrderService(user_service_url="http://127.0.0.1:8081/rpc/batch")
    server.register_capability(0, order_service)

    async with server:
        logger.info("📦 Order Service running on http://127.0.0.1:8082")
        logger.info("   Endpoint: http://127.0.0.1:8082/rpc/batch")
        logger.info("   User Service: http://127.0.0.1:8081/rpc/batch")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("\nShutting down order service...")


if __name__ == "__main__":
    asyncio.run(main())
