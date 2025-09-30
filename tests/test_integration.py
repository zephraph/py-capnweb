"""Integration tests for Cap'n Web server and client."""

import asyncio
from typing import Any

import pytest

from capnweb import Client, ClientConfig, RpcError, RpcTarget, Server, ServerConfig


class Calculator(RpcTarget):
    """Test calculator capability."""

    async def call(self, method: str, args: list[Any]) -> Any:
        """Call a calculator method."""
        match method:
            case "add":
                if len(args) != 2:
                    msg = "add requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] + args[1]

            case "subtract":
                if len(args) != 2:
                    msg = "subtract requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] - args[1]

            case "multiply":
                if len(args) != 2:
                    msg = "multiply requires 2 arguments"
                    raise RpcError.bad_request(msg)
                return args[0] * args[1]

            case "divide":
                if len(args) != 2:
                    msg = "divide requires 2 arguments"
                    raise RpcError.bad_request(msg)
                if args[1] == 0:
                    msg = "Cannot divide by zero"
                    raise RpcError.bad_request(msg)
                return args[0] / args[1]

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get a property."""
        match property:
            case "version":
                return "1.0.0"
            case "name":
                return "Calculator"
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)


class Counter(RpcTarget):
    """Test counter capability with state."""

    def __init__(self) -> None:
        self._count = 0

    async def call(self, method: str, args: list[Any]) -> Any:
        """Call a counter method."""
        match method:
            case "increment":
                self._count += 1
                return self._count

            case "decrement":
                self._count -= 1
                return self._count

            case "get":
                return self._count

            case "reset":
                self._count = 0
                return self._count

            case "add":
                if len(args) != 1:
                    msg = "add requires 1 argument"
                    raise RpcError.bad_request(msg)
                self._count += args[0]
                return self._count

            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> Any:
        """Get a property."""
        if property == "count":
            return self._count
        msg = f"Property {property} not found"
        raise RpcError.not_found(msg)


@pytest.fixture
async def server():
    """Create and start a test server."""
    config = ServerConfig(host="127.0.0.1", port=18080)
    server_instance = Server(config)

    # Register capabilities
    server_instance.register_capability(0, Calculator())

    await server_instance.start()

    yield server_instance

    await server_instance.stop()


@pytest.fixture
async def client():
    """Create a test client."""
    config = ClientConfig(url="http://127.0.0.1:18080/rpc/batch", timeout=5.0)
    client_instance = Client(config)

    yield client_instance

    await client_instance.close()


@pytest.mark.asyncio
class TestServerClientIntegration:
    """Integration tests for server and client."""

    async def test_simple_call(self, server: Server, client: Client) -> None:
        """Test a simple RPC call."""
        # Give server time to start
        await asyncio.sleep(0.1)

        # Call add method
        result = await client.call(0, "add", [5, 3])
        assert result == 8

    async def test_multiple_calls(self, server: Server, client: Client) -> None:
        """Test multiple RPC calls."""
        await asyncio.sleep(0.1)

        # Multiple calls
        result1 = await client.call(0, "add", [10, 20])
        result2 = await client.call(0, "subtract", [50, 15])
        result3 = await client.call(0, "multiply", [6, 7])

        assert result1 == 30
        assert result2 == 35
        assert result3 == 42

    async def test_error_handling(self, server: Server, client: Client) -> None:
        """Test error handling."""
        await asyncio.sleep(0.1)

        # Call unknown method
        with pytest.raises(RpcError) as exc_info:
            await client.call(0, "unknown_method", [])

        assert exc_info.value.code.value == "not_found"

    async def test_bad_request(self, server: Server, client: Client) -> None:
        """Test bad request handling."""
        await asyncio.sleep(0.1)

        # Call with wrong number of arguments
        with pytest.raises(RpcError) as exc_info:
            await client.call(0, "add", [1, 2, 3])

        assert exc_info.value.code.value == "bad_request"

    async def test_divide_by_zero(self, server: Server, client: Client) -> None:
        """Test divide by zero error."""
        await asyncio.sleep(0.1)

        with pytest.raises(RpcError) as exc_info:
            await client.call(0, "divide", [10, 0])

        assert exc_info.value.code.value == "bad_request"
        assert "divide by zero" in exc_info.value.message.lower()

    async def test_concurrent_calls(self, server: Server, client: Client) -> None:
        """Test concurrent RPC calls."""
        await asyncio.sleep(0.1)

        # Make multiple concurrent calls
        tasks = [client.call(0, "add", [i, i + 1]) for i in range(10)]

        results = await asyncio.gather(*tasks)

        # Verify results
        for i, result in enumerate(results):
            assert result == i + (i + 1)


@pytest.mark.asyncio
class TestStatefulCapabilities:
    """Test stateful capabilities."""

    async def test_counter(self) -> None:
        """Test counter capability."""
        # Create server with counter
        config = ServerConfig(host="127.0.0.1", port=18081)
        server = Server(config)
        server.register_capability(0, Counter())
        await server.start()

        # Give server time to start
        await asyncio.sleep(0.1)

        try:
            # Create client
            client_config = ClientConfig(url="http://127.0.0.1:18081/rpc/batch")
            client = Client(client_config)

            # Test increment
            result = await client.call(0, "increment", [])
            assert result == 1

            result = await client.call(0, "increment", [])
            assert result == 2

            # Test decrement
            result = await client.call(0, "decrement", [])
            assert result == 1

            # Test add
            result = await client.call(0, "add", [5])
            assert result == 6

            # Test get
            result = await client.call(0, "get", [])
            assert result == 6

            # Test reset
            result = await client.call(0, "reset", [])
            assert result == 0

            await client.close()

        finally:
            await server.stop()


@pytest.mark.asyncio
class TestClientContextManager:
    """Test client context manager usage."""

    async def test_context_manager(self) -> None:
        """Test using client as async context manager."""
        # Create server
        config = ServerConfig(host="127.0.0.1", port=18082)
        server = Server(config)
        server.register_capability(0, Calculator())
        await server.start()

        await asyncio.sleep(0.1)

        try:
            # Use client as context manager
            client_config = ClientConfig(url="http://127.0.0.1:18082/rpc/batch")
            async with Client(client_config) as client:
                result = await client.call(0, "add", [100, 200])
                assert result == 300

        finally:
            await server.stop()
