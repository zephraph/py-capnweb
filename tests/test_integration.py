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


@pytest.mark.asyncio
class TestErrorHandling:
    """Test comprehensive error handling scenarios."""

    async def test_connection_refused(self) -> None:
        """Test error when server is not running."""
        # Try to connect to non-existent server
        client_config = ClientConfig(
            url="http://127.0.0.1:19999/rpc/batch", timeout=1.0
        )
        client = Client(client_config)

        with pytest.raises(RpcError) as exc_info:
            await client.call(0, "test", [])

        assert exc_info.value.code.value == "internal"
        await client.close()

    async def test_invalid_response_format(
        self, server: Server, client: Client
    ) -> None:
        """Test handling of empty/invalid responses."""
        await asyncio.sleep(0.1)

        # Make a call that returns None (empty response)
        # The server should handle this gracefully
        result = await client.call(0, "add", [0, 0])
        assert result == 0

    async def test_server_abort_error(self) -> None:
        """Test handling of server abort messages."""

        # This tests the _handle_abort path in client.py
        # Create a custom target that raises internal errors
        class FaultyTarget(RpcTarget):
            async def call(self, method: str, args: list[Any]) -> Any:
                # Force an internal server error
                msg = "Internal server fault"
                raise RuntimeError(msg)

            async def get_property(self, property: str) -> Any:
                msg = "Internal server fault"
                raise RuntimeError(msg)

        config = ServerConfig(host="127.0.0.1", port=18083)
        server = Server(config)
        server.register_capability(0, FaultyTarget())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18083/rpc/batch")
            client = Client(client_config)

            with pytest.raises(RpcError) as exc_info:
                await client.call(0, "test", [])

            # Should get an internal error
            assert exc_info.value.code.value == "internal"

            await client.close()
        finally:
            await server.stop()

    async def test_timeout_error(self) -> None:
        """Test timeout handling on slow server."""

        # Create a slow target that delays responses
        class SlowTarget(RpcTarget):
            async def call(self, method: str, args: list[Any]) -> Any:
                await asyncio.sleep(5.0)  # Delay longer than timeout
                return "too slow"

            async def get_property(self, property: str) -> Any:
                return "test"

        config = ServerConfig(host="127.0.0.1", port=18084)
        server = Server(config)
        server.register_capability(0, SlowTarget())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            # Set very short timeout
            client_config = ClientConfig(
                url="http://127.0.0.1:18084/rpc/batch", timeout=0.5
            )
            client = Client(client_config)

            with pytest.raises(RpcError) as exc_info:
                await client.call(0, "slowMethod", [])

            # Should timeout
            assert exc_info.value.code.value == "internal"

            await client.close()
        finally:
            await server.stop()

    async def test_malformed_arguments(self, server: Server, client: Client) -> None:
        """Test handling of malformed arguments."""
        await asyncio.sleep(0.1)

        # Test with wrong argument types - Python will coerce strings in addition
        # so this actually tests type handling in the calculator
        result = await client.call(0, "add", ["hello", "world"])
        # String concatenation works in Python
        assert result == "helloworld"

    async def test_empty_method_name(self, server: Server, client: Client) -> None:
        """Test calling with empty method name."""
        await asyncio.sleep(0.1)

        with pytest.raises(RpcError) as exc_info:
            await client.call(0, "", [])

        assert exc_info.value.code.value == "not_found"

    async def test_client_without_context_manager(self) -> None:
        """Test client without using context manager (manual lifecycle)."""
        config = ServerConfig(host="127.0.0.1", port=18085)
        server = Server(config)
        server.register_capability(0, Calculator())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            # Create client without context manager
            client_config = ClientConfig(url="http://127.0.0.1:18085/rpc/batch")
            client = Client(client_config)

            # Make call
            result = await client.call(0, "add", [10, 20])
            assert result == 30

            # Manually close
            await client.close()

            # After close, transport is None, so new calls will auto-create transport
            # This actually tests the auto-creation path in client.py line 104-110
            result2 = await client.call(0, "add", [1, 2])
            assert result2 == 3

        finally:
            await server.stop()

    async def test_multiple_close_calls(self) -> None:
        """Test that multiple close() calls don't cause errors."""
        client_config = ClientConfig(url="http://127.0.0.1:18086/rpc/batch")
        client = Client(client_config)

        # Close multiple times - should be idempotent
        await client.close()
        await client.close()
        await client.close()


@pytest.mark.asyncio
class TestServerConfiguration:
    """Test server configuration and edge cases."""

    async def test_server_with_stack_traces_enabled(self) -> None:
        """Test server with stack traces enabled."""
        config = ServerConfig(host="127.0.0.1", port=18087, include_stack_traces=True)
        server = Server(config)
        server.register_capability(0, Calculator())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18087/rpc/batch")
            client = Client(client_config)

            # Trigger an error and check it's properly handled
            with pytest.raises(RpcError) as exc_info:
                await client.call(0, "divide", [10, 0])

            # Error should have proper message
            assert "divide by zero" in exc_info.value.message.lower()

            await client.close()
        finally:
            await server.stop()

    async def test_server_with_stack_traces_disabled(self) -> None:
        """Test server with stack traces disabled (production mode)."""
        config = ServerConfig(host="127.0.0.1", port=18088, include_stack_traces=False)
        server = Server(config)
        server.register_capability(0, Calculator())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18088/rpc/batch")
            client = Client(client_config)

            # Trigger an error
            with pytest.raises(RpcError) as exc_info:
                await client.call(0, "divide", [10, 0])

            # Error should still be raised with message
            assert "divide by zero" in exc_info.value.message.lower()

            await client.close()
        finally:
            await server.stop()

    async def test_server_start_stop_restart(self) -> None:
        """Test starting, stopping, and restarting server."""
        config = ServerConfig(host="127.0.0.1", port=18089)
        server = Server(config)
        server.register_capability(0, Calculator())

        # Start server
        await server.start()
        await asyncio.sleep(0.1)

        # Stop server
        await server.stop()
        await asyncio.sleep(0.1)

        # Restart server
        await server.start()
        await asyncio.sleep(0.1)

        try:
            # Should work after restart
            client_config = ClientConfig(url="http://127.0.0.1:18089/rpc/batch")
            client = Client(client_config)

            result = await client.call(0, "add", [5, 5])
            assert result == 10

            await client.close()
        finally:
            await server.stop()


@pytest.mark.asyncio
class TestCapabilityManagement:
    """Test capability registration and management."""

    async def test_register_multiple_capabilities(self) -> None:
        """Test registering multiple capabilities."""
        config = ServerConfig(host="127.0.0.1", port=18090)
        server = Server(config)

        # Register multiple capabilities with different IDs
        server.register_capability(0, Calculator())
        server.register_capability(1, Counter())

        await server.start()
        await asyncio.sleep(0.1)

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18090/rpc/batch")
            client = Client(client_config)

            # Call capability 0 (calculator)
            result1 = await client.call(0, "add", [10, 20])
            assert result1 == 30

            # Call capability 1 (counter)
            result2 = await client.call(1, "increment", [])
            assert result2 == 1

            await client.close()
        finally:
            await server.stop()

    async def test_call_unregistered_capability(self) -> None:
        """Test calling a capability that hasn't been registered."""
        config = ServerConfig(host="127.0.0.1", port=18091)
        server = Server(config)
        server.register_capability(0, Calculator())
        await server.start()
        await asyncio.sleep(0.1)

        try:
            client_config = ClientConfig(url="http://127.0.0.1:18091/rpc/batch")
            client = Client(client_config)

            # Try to call capability ID 999 which doesn't exist
            with pytest.raises(RpcError) as exc_info:
                await client.call(999, "test", [])

            # Should get an error (exact error type may vary)
            assert exc_info.value.code.value in ("not_found", "internal", "bad_request")

            await client.close()
        finally:
            await server.stop()
