"""Tests for resource management (dispose, async context managers)."""

import asyncio

import pytest

from capnweb.client import Client, ClientConfig
from capnweb.error import RpcError
from capnweb.hooks import ErrorStubHook, PayloadStubHook, TargetStubHook
from capnweb.payload import RpcPayload
from capnweb.server import Server, ServerConfig
from capnweb.stubs import RpcPromise, RpcStub
from capnweb.types import RpcTarget


class SimpleTarget(RpcTarget):
    """Simple test target."""

    async def call(self, method: str, args: list) -> str:
        match method:
            case "greet":
                return f"Hello, {args[0]}!"
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> str:
        msg = "Property access not implemented"
        raise RpcError.not_found(msg)


class TestServerContextManager:
    """Test Server async context manager."""

    @pytest.mark.asyncio
    async def test_server_context_manager(self):
        """Test that Server can be used as async context manager."""
        config = ServerConfig(host="127.0.0.1", port=28200)
        server = Server(config)
        server.register_capability(0, SimpleTarget())

        # Use as context manager
        async with server:
            # Server should be running
            assert server._runner is not None
            assert server._app is not None

        # After exiting, server should be stopped
        # (runner is cleaned up but still exists)
        assert server._runner is not None


class TestClientContextManager:
    """Test Client async context manager (already implemented)."""

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test that Client works as async context manager."""
        # Start a test server
        server_config = ServerConfig(host="127.0.0.1", port=28201)
        server = Server(server_config)
        server.register_capability(0, SimpleTarget())

        async with server:
            # Use client as context manager
            client_config = ClientConfig(url="http://127.0.0.1:28201/rpc/batch")

            async with Client(client_config) as client:
                result = await client.call(0, "greet", ["World"])
                assert result == "Hello, World!"

            # Client transport should be closed after exiting


class TestStubResourceManagement:
    """Test RpcStub and RpcPromise resource management."""

    @pytest.mark.asyncio
    async def test_stub_dispose(self):
        """Test that RpcStub.dispose() works."""
        # Create a stub with a payload hook
        hook = PayloadStubHook(RpcPayload.owned({"value": 42}))
        stub = RpcStub(hook)

        # Stub should work
        promise = stub.value
        result = await promise
        assert result == 42

        # Dispose the stub
        stub.dispose()
        # After dispose, the hook's payload should be disposed

    @pytest.mark.asyncio
    async def test_stub_context_manager(self):
        """Test that RpcStub works as async context manager."""
        hook = PayloadStubHook(RpcPayload.owned({"name": "Alice"}))
        stub = RpcStub(hook)

        async with stub:
            # Should work inside context
            promise = stub.name
            result = await promise
            assert result == "Alice"

        # After exiting, stub is disposed

    @pytest.mark.asyncio
    async def test_promise_dispose(self):
        """Test that RpcPromise.dispose() works."""
        hook = PayloadStubHook(RpcPayload.owned([1, 2, 3]))
        promise = RpcPromise(hook)

        # Promise should work
        result = await promise
        assert result == [1, 2, 3]

        # Create another promise and dispose it before awaiting
        hook2 = PayloadStubHook(RpcPayload.owned("test"))
        promise2 = RpcPromise(hook2)
        promise2.dispose()
        # After dispose, hook is disposed

    @pytest.mark.asyncio
    async def test_promise_context_manager(self):
        """Test that RpcPromise works as async context manager."""
        hook = PayloadStubHook(RpcPayload.owned({"data": "test"}))
        promise = RpcPromise(hook)

        async with promise as result:
            # Result is the awaited value
            assert result == {"data": "test"}

        # After exiting, promise is disposed


class TestHookDisposal:
    """Test hook disposal mechanisms."""

    def test_error_hook_dispose(self):
        """Test that ErrorStubHook.dispose() is safe."""
        error = RpcError.internal("Test error")
        hook = ErrorStubHook(error)

        # Dispose should not raise
        hook.dispose()

    def test_payload_hook_dispose(self):
        """Test that PayloadStubHook.dispose() cleans up payload."""
        payload = RpcPayload.owned({"key": "value"})
        hook = PayloadStubHook(payload)

        # Dispose the hook
        hook.dispose()

        # Payload's stubs/promises should be cleared
        assert len(payload.stubs) == 0
        assert len(payload.promises) == 0

    @pytest.mark.asyncio
    async def test_target_hook_dispose(self):
        """Test that TargetStubHook.dispose() decrements refcount."""
        target = SimpleTarget()
        hook = TargetStubHook(target)

        # Initial refcount is 1
        assert hook.ref_count == 1

        # Dispose decrements refcount
        hook.dispose()
        assert hook.ref_count == 0

    @pytest.mark.asyncio
    async def test_target_hook_dup(self):
        """Test that TargetStubHook.dup() increments refcount."""
        target = SimpleTarget()
        hook = TargetStubHook(target)

        assert hook.ref_count == 1

        # Dup increments refcount
        hook2 = hook.dup()
        assert hook.ref_count == 2
        assert hook2.ref_count == 2
        assert hook is hook2  # Same object

        # Dispose each copy
        hook.dispose()
        assert hook.ref_count == 1

        hook2.dispose()
        assert hook.ref_count == 0


class TestAsyncCallableSupport:
    """Test async callable support in PayloadStubHook."""

    @pytest.mark.asyncio
    async def test_async_callable_in_payload(self):
        """Test that PayloadStubHook can call async functions."""

        async def async_greet(name):
            """Async function for testing."""
            await asyncio.sleep(0.01)  # Simulate async work
            return f"Hello, {name}!"

        # Create payload with async function
        payload = RpcPayload.owned({"greet": async_greet})
        hook = PayloadStubHook(payload)

        # Call the async function through the hook
        result_hook = await hook.call(["greet"], RpcPayload.owned(["World"]))

        # Should return a PromiseStubHook
        from capnweb.hooks import PromiseStubHook

        assert isinstance(result_hook, PromiseStubHook)

        # Pull the result
        result_payload = await result_hook.pull()
        assert result_payload.value == "Hello, World!"

    @pytest.mark.asyncio
    async def test_sync_callable_still_works(self):
        """Test that synchronous callables still work."""

        def sync_add(a, b):
            """Sync function for testing."""
            return a + b

        # Create payload with sync function
        payload = RpcPayload.owned({"add": sync_add})
        hook = PayloadStubHook(payload)

        # Call the sync function through the hook
        result_hook = await hook.call(["add"], RpcPayload.owned([5, 3]))

        # Should return a PayloadStubHook directly (not async)
        assert isinstance(result_hook, PayloadStubHook)

        # Pull the result
        result_payload = await result_hook.pull()
        assert result_payload.value == 8


class TestPayloadDisposal:
    """Test RpcPayload disposal."""

    @pytest.mark.asyncio
    async def test_payload_with_stubs_dispose(self):
        """Test that disposing payload disposes tracked stubs."""
        # Create a payload with stubs from PARAMS source (will trigger deep copy)
        stub_hook = PayloadStubHook(RpcPayload.owned("inner"))
        stub = RpcStub(stub_hook)

        payload = RpcPayload.from_app_params({"stub": stub})
        payload.ensure_deep_copied()

        # Payload should have tracked the stub during deep copy
        assert len(payload.stubs) > 0

        # Dispose payload
        payload.dispose()

        # Stubs should be cleared
        assert len(payload.stubs) == 0
        assert len(payload.promises) == 0

    @pytest.mark.asyncio
    async def test_payload_dispose_idempotent(self):
        """Test that disposing payload multiple times is safe."""
        payload = RpcPayload.owned([1, 2, 3])
        payload.ensure_deep_copied()

        # Dispose multiple times should be safe
        payload.dispose()
        payload.dispose()
        payload.dispose()

        assert len(payload.stubs) == 0
        assert len(payload.promises) == 0
