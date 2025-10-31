"""Tests for automatic method dispatch in RpcTarget.

This test suite validates the new automatic method dispatch API where
methods on RpcTarget subclasses are automatically exposed as RPC endpoints.
"""

import asyncio
from typing import Any

import pytest

from capnweb import Client, ClientConfig, RpcError, RpcTarget, Server, ServerConfig


class AutoCalculator(RpcTarget):
    """Calculator using automatic method dispatch."""

    async def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    async def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers (sync method)."""
        return a * b

    async def divide(self, a: float, b: float) -> float:
        """Divide a by b."""
        if b == 0:
            msg = "Cannot divide by zero"
            raise ValueError(msg)
        return a / b

    def _private_method(self) -> str:
        """Private method - should not be accessible via RPC."""
        return "secret"


class StatefulService(RpcTarget):
    """Service with state and properties."""

    def __init__(self):
        self.count = 0
        self.name = "StatefulService"
        self._internal_state = "hidden"

    async def set(self, count: int) -> int:
        self.count = count
        return self.count

    async def increment(self) -> int:
        """Increment the counter."""
        self.count += 1
        return self.count

    async def decrement(self) -> int:
        """Decrement the counter."""
        self.count -= 1
        return self.count

    async def reset(self) -> int:
        """Reset the counter."""
        self.count = 0
        return self.count

    def get_name(self) -> str:
        """Get the service name (sync method)."""
        return self.name


class MixedService(RpcTarget):
    """Service that overrides call() for some methods but uses auto-dispatch for others."""

    async def auto_method(self) -> str:
        """This uses automatic dispatch."""
        return "auto"

    async def call(self, method: str, args: list[Any]) -> Any:
        """Custom implementation that handles some methods manually."""
        # Handle specific method manually
        if method == "manual_method":
            return "manual"

        # Fall back to automatic dispatch for other methods
        return await super().call(method, args)


@pytest.fixture
async def auto_server():
    """Create and start a test server with automatic dispatch."""
    config = ServerConfig(host="127.0.0.1", port=18081)
    server_instance = Server(config)

    # Register capabilities
    server_instance.register_capability(0, AutoCalculator())
    server_instance.register_capability(1, StatefulService())
    server_instance.register_capability(2, MixedService())

    await server_instance.start()

    yield server_instance

    await server_instance.stop()


@pytest.fixture
async def auto_client():
    """Create a test client."""
    config = ClientConfig(url="http://127.0.0.1:18081/rpc/batch", timeout=5.0)
    client_instance = Client(config)

    yield client_instance

    await client_instance.close()


@pytest.mark.asyncio
class TestAutomaticMethodDispatch:
    """Tests for automatic method dispatch."""

    async def test_async_method_call(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test calling an async method automatically."""
        await asyncio.sleep(0.1)

        result = await auto_client.call(0, "add", [5, 3])
        assert result == 8

    async def test_sync_method_call(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test calling a sync method automatically."""
        await asyncio.sleep(0.1)

        result = await auto_client.call(0, "multiply", [6, 7])
        assert result == 42

    async def test_multiple_methods(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test calling multiple methods."""
        await asyncio.sleep(0.1)

        result1 = await auto_client.call(0, "add", [10, 20])
        result2 = await auto_client.call(0, "subtract", [50, 15])
        result3 = await auto_client.call(0, "multiply", [3, 4])

        assert result1 == 30
        assert result2 == 35
        assert result3 == 12

    async def test_method_with_exception(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test that exceptions in methods are properly propagated."""
        await asyncio.sleep(0.1)

        with pytest.raises(RpcError) as exc_info:
            await auto_client.call(0, "divide", [10, 0])

        # The ValueError gets wrapped in an RpcError
        assert exc_info.value.code.value in ["internal", "bad_request"]

    async def test_private_method_blocked(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test that private methods (starting with _) are not accessible."""
        await asyncio.sleep(0.1)

        with pytest.raises(RpcError) as exc_info:
            await auto_client.call(0, "_private_method", [])

        assert exc_info.value.code.value == "not_found"
        assert "not found" in exc_info.value.message.lower()

    async def test_nonexistent_method(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test that calling a non-existent method raises an error."""
        await asyncio.sleep(0.1)

        with pytest.raises(RpcError) as exc_info:
            await auto_client.call(0, "nonexistent_method", [])

        assert exc_info.value.code.value == "not_found"

    async def test_concurrent_auto_calls(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test concurrent calls with automatic dispatch."""
        await asyncio.sleep(0.1)

        # Make multiple concurrent calls
        tasks = [auto_client.call(0, "add", [i, i + 1]) for i in range(10)]

        results = await asyncio.gather(*tasks)

        # Verify results
        for i, result in enumerate(results):
            assert result == i + (i + 1)


@pytest.mark.asyncio
class TestStatefulAutoDispatch:
    """Tests for stateful services with automatic dispatch."""

    async def test_stateful_operations(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test stateful operations maintain state correctly."""
        await asyncio.sleep(0.1)

        # Increment multiple times
        result1 = await auto_client.call(1, "increment", [])
        assert result1 == 1

        result2 = await auto_client.call(1, "increment", [])
        assert result2 == 2

        # Decrement
        result4 = await auto_client.call(1, "decrement", [])
        assert result4 == 1

        # Reset
        result5 = await auto_client.call(1, "reset", [])
        assert result5 == 0

    async def test_sync_method_on_stateful(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test calling sync methods on stateful services."""
        await asyncio.sleep(0.1)

        result = await auto_client.call(1, "get_name", [])
        assert result == "StatefulService"


@pytest.mark.asyncio
class TestMixedDispatch:
    """Tests for mixed manual/automatic dispatch."""

    async def test_manual_method(
        self, auto_server: Server, auto_client: Client
    ) -> None:
        """Test manually dispatched method."""
        await asyncio.sleep(0.1)

        result = await auto_client.call(2, "manual_method", [])
        assert result == "manual"

    async def test_auto_method(self, auto_server: Server, auto_client: Client) -> None:
        """Test automatically dispatched method."""
        await asyncio.sleep(0.1)

        result = await auto_client.call(2, "auto_method", [])
        assert result == "auto"


@pytest.mark.asyncio
class TestDirectInvocation:
    """Tests for direct invocation of RpcTarget methods (unit tests)."""

    async def test_direct_call_async_method(self) -> None:
        """Test calling methods directly via call()."""
        calc = AutoCalculator()

        result = await calc.call("add", [5, 3])
        assert result == 8

    async def test_direct_call_sync_method(self) -> None:
        """Test calling sync methods directly via call()."""
        calc = AutoCalculator()

        result = await calc.call("multiply", [6, 7])
        assert result == 42

    async def test_direct_call_private_blocked(self) -> None:
        """Test that private methods are blocked when called directly."""
        calc = AutoCalculator()

        with pytest.raises(RpcError) as exc_info:
            await calc.call("_private_method", [])

        assert exc_info.value.code.value == "not_found"

    async def test_direct_get_property(self) -> None:
        """Test getting properties directly."""
        service = StatefulService()
        service.count = 42

        result = await service.get_property("count")
        assert result == 42

    async def test_direct_get_private_property_blocked(self) -> None:
        """Test that private properties are blocked."""
        service = StatefulService()

        with pytest.raises(RpcError) as exc_info:
            await service.get_property("_internal_state")

        assert exc_info.value.code.value == "not_found"

    async def test_get_property_method_blocked(self) -> None:
        """Test that methods are not accessible as properties."""
        service = StatefulService()

        with pytest.raises(RpcError) as exc_info:
            await service.get_property("increment")

        assert exc_info.value.code.value == "not_found"
