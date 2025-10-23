"""Automated tests for the microservices example.

This test suite runs the user service, order service, and API gateway
programmatically, verifying the full service mesh works correctly.
"""

# Import the microservices example classes
import sys
from pathlib import Path

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig

examples_dir = Path(__file__).parent.parent.parent / "examples" / "microservices"
sys.path.insert(0, str(examples_dir))

from api_gateway import ApiGateway  # noqa: E402  # type: ignore[import-not-found]
from order_service import OrderService  # noqa: E402  # type: ignore[import-not-found]
from user_service import UserService  # noqa: E402  # type: ignore[import-not-found]


@pytest.fixture
async def user_service():
    """Start the user service."""
    config = ServerConfig(host="127.0.0.1", port=0, include_stack_traces=True)
    server = Server(config)
    server.register_capability(0, UserService())

    await server.start()
    port = server.port
    yield f"http://127.0.0.1:{port}/rpc/batch"

    await server.stop()


@pytest.fixture
async def order_service(user_service):
    """Start the order service."""
    config = ServerConfig(host="127.0.0.1", port=0, include_stack_traces=True)
    server = Server(config)
    server.register_capability(0, OrderService(user_service_url=user_service))

    await server.start()
    port = server.port
    yield f"http://127.0.0.1:{port}/rpc/batch"

    await server.stop()


@pytest.fixture
async def api_gateway(user_service, order_service):
    """Start the API gateway."""
    config = ServerConfig(host="127.0.0.1", port=0, include_stack_traces=True)
    server = Server(config)
    gateway = ApiGateway(user_service_url=user_service, order_service_url=order_service)
    server.register_capability(0, gateway)

    await server.start()
    port = server.port
    yield f"http://127.0.0.1:{port}/rpc/batch"

    await server.stop()


@pytest.mark.asyncio
async def test_microservices_login(api_gateway):
    """Test user login through API gateway."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login as Bob
        result = await client.call(0, "login", ["bob", "password"])

        assert "token" in result
        assert result["userId"] == "user2"
        assert result["username"] == "bob"
        assert result["role"] == "user"

        # Login as Alice (admin)
        result = await client.call(0, "login", ["alice", "password"])

        assert "token" in result
        assert result["userId"] == "user1"
        assert result["username"] == "alice"
        assert result["role"] == "admin"


@pytest.mark.asyncio
async def test_microservices_get_profile(api_gateway):
    """Test getting user profile through API gateway."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # Get profile
        profile = await client.call(0, "getUserProfile", [token])

        assert profile["userId"] == "user2"
        assert profile["username"] == "bob"
        assert profile["email"] == "bob@example.com"
        assert profile["role"] == "user"


@pytest.mark.asyncio
async def test_microservices_list_users(api_gateway):
    """Test listing users through API gateway."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # List users
        users = await client.call(0, "listUsers", [token])

        assert len(users) == 3
        usernames = [u["username"] for u in users]
        assert set(usernames) == {"alice", "bob", "charlie"}


@pytest.mark.asyncio
async def test_microservices_create_order(api_gateway):
    """Test creating an order through API gateway."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # Create order
        items = [
            {"name": "Laptop", "price": 999.99, "quantity": 1},
            {"name": "Mouse", "price": 29.99, "quantity": 2},
        ]
        order = await client.call(0, "createOrder", [token, items])

        assert "orderId" in order
        assert order["userId"] == "user2"
        assert order["total"] == 1059.97
        assert order["status"] == "pending"
        assert len(order["items"]) == 2


@pytest.mark.asyncio
async def test_microservices_list_orders(api_gateway):
    """Test listing orders through API gateway."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # Create an order
        items = [{"name": "Book", "price": 19.99, "quantity": 1}]
        created_order = await client.call(0, "createOrder", [token, items])
        order_id = created_order["orderId"]

        # List orders
        orders = await client.call(0, "listOrders", [token])

        assert len(orders) >= 1
        order_ids = [o["orderId"] for o in orders]
        assert order_id in order_ids

        # Verify all orders belong to Bob
        for order in orders:
            assert order["userId"] == "user2"


@pytest.mark.asyncio
async def test_microservices_permission_denied_cancel(api_gateway):
    """Test that regular users cannot cancel orders."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login as Bob (regular user)
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # Create an order
        items = [{"name": "Item", "price": 10.0, "quantity": 1}]
        order = await client.call(0, "createOrder", [token, items])
        order_id = order["orderId"]

        # Try to cancel - should fail
        with pytest.raises(RpcError, match="permission"):
            await client.call(0, "cancelOrder", [token, order_id])


@pytest.mark.asyncio
async def test_microservices_admin_can_cancel(api_gateway):
    """Test that admin users can cancel orders."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Bob creates an order
        bob_login = await client.call(0, "login", ["bob", "password"])
        bob_token = bob_login["token"]

        items = [{"name": "Item", "price": 10.0, "quantity": 1}]
        order = await client.call(0, "createOrder", [bob_token, items])
        order_id = order["orderId"]

        # Alice (admin) logs in
        alice_login = await client.call(0, "login", ["alice", "password"])
        alice_token = alice_login["token"]

        # Alice cancels Bob's order - should succeed
        result = await client.call(0, "cancelOrder", [alice_token, order_id])

        assert result["status"] == "cancelled"
        assert result["orderId"] == order_id

        # Verify order is cancelled
        orders = await client.call(0, "listOrders", [bob_token])
        cancelled_order = next(o for o in orders if o["orderId"] == order_id)
        assert cancelled_order["status"] == "cancelled"


@pytest.mark.asyncio
async def test_microservices_cross_service_capability_passing(api_gateway):
    """Test capability passing between services."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login as Bob
        login_result = await client.call(0, "login", ["bob", "password"])
        token = login_result["token"]

        # Create order - this passes User capability from User Service to Order Service
        items = [{"name": "Widget", "price": 50.0, "quantity": 2}]
        order = await client.call(0, "createOrder", [token, items])

        # Order service verified permissions via User capability
        assert order["userId"] == "user2"
        assert order["total"] == 100.0

        # The fact that this succeeded means:
        # 1. API gateway got User capability from User Service
        # 2. API gateway passed User capability to Order Service
        # 3. Order Service called user_capability.hasPermission("order.create")
        # 4. User Service responded to the permission check
        # This demonstrates cross-service capability passing!


@pytest.mark.asyncio
async def test_microservices_invalid_token(api_gateway):
    """Test that invalid tokens are rejected."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Try to use invalid token
        with pytest.raises(RpcError, match="Invalid"):
            await client.call(0, "getUserProfile", ["invalid_token"])


@pytest.mark.asyncio
async def test_microservices_multiple_orders(api_gateway):
    """Test creating and managing multiple orders."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Login
        login_result = await client.call(0, "login", ["charlie", "password"])
        token = login_result["token"]

        # Create multiple orders
        order1 = await client.call(
            0, "createOrder", [token, [{"name": "A", "price": 10, "quantity": 1}]]
        )
        order2 = await client.call(
            0, "createOrder", [token, [{"name": "B", "price": 20, "quantity": 1}]]
        )
        order3 = await client.call(
            0, "createOrder", [token, [{"name": "C", "price": 30, "quantity": 1}]]
        )

        # List orders
        orders = await client.call(0, "listOrders", [token])

        # Should have at least 3 orders
        assert len(orders) >= 3

        # Verify all order IDs are present
        order_ids = [o["orderId"] for o in orders]
        assert order1["orderId"] in order_ids
        assert order2["orderId"] in order_ids
        assert order3["orderId"] in order_ids


@pytest.mark.asyncio
async def test_microservices_user_isolation(api_gateway):
    """Test that users can only see their own orders."""
    config = ClientConfig(url=api_gateway)

    async with Client(config) as client:
        # Bob creates an order
        bob_login = await client.call(0, "login", ["bob", "password"])
        bob_token = bob_login["token"]
        bob_order = await client.call(
            0,
            "createOrder",
            [bob_token, [{"name": "Bob's Item", "price": 10, "quantity": 1}]],
        )

        # Charlie creates an order
        charlie_login = await client.call(0, "login", ["charlie", "password"])
        charlie_token = charlie_login["token"]
        charlie_order = await client.call(
            0,
            "createOrder",
            [charlie_token, [{"name": "Charlie's Item", "price": 20, "quantity": 1}]],
        )

        # Bob lists his orders - should not see Charlie's order
        bob_orders = await client.call(0, "listOrders", [bob_token])
        bob_order_ids = [o["orderId"] for o in bob_orders]
        assert bob_order["orderId"] in bob_order_ids
        assert charlie_order["orderId"] not in bob_order_ids

        # Charlie lists his orders - should not see Bob's order
        charlie_orders = await client.call(0, "listOrders", [charlie_token])
        charlie_order_ids = [o["orderId"] for o in charlie_orders]
        assert charlie_order["orderId"] in charlie_order_ids
        assert bob_order["orderId"] not in charlie_order_ids
