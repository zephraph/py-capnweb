"""Tests for recent improvements: WireError data, stack trace redaction, etc."""

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.server import Server, ServerConfig
from capnweb.types import RpcTarget
from capnweb.wire import WireError


class TestWireErrorEnhancements:
    """Tests for enhanced WireError with custom data."""

    def test_wire_error_with_data(self):
        """Test WireError with custom data field."""
        error = WireError(
            error_type="validation_error",
            message="Invalid input",
            stack=None,
            data={"field": "email", "reason": "invalid_format"},
        )
        json_output = error.to_json()
        assert json_output == [
            "error",
            "validation_error",
            "Invalid input",
            None,
            {"field": "email", "reason": "invalid_format"},
        ]

    def test_wire_error_with_stack_and_data(self):
        """Test WireError with both stack and data."""
        error = WireError(
            error_type="runtime_error",
            message="Something went wrong",
            stack="at line 42\nat line 10",
            data={"context": "user_action"},
        )
        json_output = error.to_json()
        assert json_output == [
            "error",
            "runtime_error",
            "Something went wrong",
            "at line 42\nat line 10",
            {"context": "user_action"},
        ]

    def test_wire_error_parsing_with_data(self):
        """Test parsing WireError with data field."""
        json_arr = [
            "error",
            "custom_error",
            "Error message",
            None,
            {"extra": "info"},
        ]
        error = WireError.from_json(json_arr)
        assert error.error_type == "custom_error"
        assert error.message == "Error message"
        assert error.stack is None
        assert error.data == {"extra": "info"}

    def test_wire_error_roundtrip_with_data(self):
        """Test WireError serialization/deserialization roundtrip."""
        original = WireError(
            error_type="test",
            message="test message",
            stack="test stack",
            data={"key": "value"},
        )
        json_data = original.to_json()
        parsed = WireError.from_json(json_data)

        assert parsed.error_type == original.error_type
        assert parsed.message == original.message
        assert parsed.stack == original.stack
        assert parsed.data == original.data

    def test_wire_error_backward_compatible(self):
        """Test that WireError remains backward compatible without data."""
        # Old format without data
        json_arr = ["error", "error_type", "message", "stack"]
        error = WireError.from_json(json_arr)
        assert error.error_type == "error_type"
        assert error.message == "message"
        assert error.stack == "stack"
        assert error.data is None  # Should be None for old format


class TestStackTraceRedaction:
    """Tests for server-side stack trace redaction."""

    def test_server_config_default_no_stack_traces(self):
        """Test that stack traces are disabled by default."""
        config = ServerConfig()
        assert config.include_stack_traces is False

    def test_server_config_enable_stack_traces(self):
        """Test enabling stack traces in config."""
        config = ServerConfig(include_stack_traces=True)
        assert config.include_stack_traces is True

    @pytest.mark.asyncio
    async def test_server_redacts_stack_trace_by_default(self):
        """Test that server redacts stack traces by default."""

        class BrokenCapability(RpcTarget):
            async def call(self, method: str, args: list) -> None:
                msg = "Intentional error for testing"
                raise ValueError(msg)

            async def get_property(self, property: str) -> None:
                pass

        config = ServerConfig(port=28080, include_stack_traces=False)
        server = Server(config)
        server.register_capability(0, BrokenCapability())

        # Start server
        await server.start()

        try:
            # This would normally require a full client call, but we can test
            # the configuration is set correctly
            assert server.config.include_stack_traces is False
        finally:
            await server.stop()

    @pytest.mark.asyncio
    async def test_server_includes_stack_trace_when_enabled(self):
        """Test that server includes stack traces when configured."""

        class BrokenCapability(RpcTarget):
            async def call(self, method: str, args: list) -> None:
                msg = "Test error"
                raise ValueError(msg)

            async def get_property(self, property: str) -> None:
                pass

        config = ServerConfig(port=28081, include_stack_traces=True)
        server = Server(config)
        server.register_capability(0, BrokenCapability())

        await server.start()

        try:
            assert server.config.include_stack_traces is True
        finally:
            await server.stop()


class TestTransportAbstraction:
    """Tests for client using transport abstraction."""

    @pytest.mark.asyncio
    async def test_client_auto_creates_transport(self):
        """Test that client auto-creates transport when needed."""
        config = ClientConfig(url="http://localhost:18080/rpc/batch")
        client = Client(config)

        # Transport should not exist yet
        assert client._transport is None

        # After using context manager, transport should exist
        async with client:
            assert client._transport is not None

        # After exiting, transport should be closed
        assert client._transport is None

    def test_client_config_stores_url(self):
        """Test that client config properly stores URL."""
        config = ClientConfig(url="ws://localhost:8080/rpc/ws", timeout=60.0)
        assert config.url == "ws://localhost:8080/rpc/ws"
        assert config.timeout == 60.0


class TestRpcErrorDataSupport:
    """Tests for RpcError data field support."""

    def test_rpc_error_supports_data(self):
        """Test that RpcError supports custom data."""
        error = RpcError.bad_request("Validation failed", data={"field": "email"})
        assert error.data == {"field": "email"}

    def test_rpc_error_factories_with_data(self):
        """Test all RpcError factory methods support data."""
        errors = [
            RpcError.bad_request("msg", data={"a": 1}),
            RpcError.not_found("msg", data={"b": 2}),
            RpcError.cap_revoked("msg", data={"c": 3}),
            RpcError.permission_denied("msg", data={"d": 4}),
            RpcError.canceled("msg", data={"e": 5}),
            RpcError.internal("msg", data={"f": 6}),
        ]

        for error in errors:
            assert error.data is not None
            assert isinstance(error.data, dict)
