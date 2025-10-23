"""Tests for RpcSession - session management and capability tracking."""

import asyncio

import pytest

from capnweb.error import RpcError
from capnweb.hooks import PayloadStubHook, PromiseStubHook, TargetStubHook
from capnweb.payload import RpcPayload
from capnweb.session import RpcSession
from capnweb.stubs import RpcPromise, RpcStub
from capnweb.types import RpcTarget


class SimpleTarget(RpcTarget):
    """Simple RPC target for testing."""

    def __init__(self, value: str = "test"):
        self.value = value

    async def call(self, method: str, args: list) -> str:
        match method:
            case "getValue":
                return self.value
            case "echo":
                return args[0] if args else ""
            case _:
                msg = f"Method {method} not found"
                raise RpcError.not_found(msg)

    async def get_property(self, property: str) -> str:
        match property:
            case "value":
                return self.value
            case _:
                msg = f"Property {property} not found"
                raise RpcError.not_found(msg)


class TestRpcSessionBasics:
    """Test basic session initialization and ID allocation."""

    def test_session_initialization(self):
        """Test that session initializes with empty tables."""
        session = RpcSession()

        assert session._next_import_id == 1
        assert session._next_export_id == 1
        assert len(session._imports) == 0
        assert len(session._exports) == 0
        assert len(session._pending_promises) == 0
        assert session.serializer is not None
        assert session.parser is not None

    def test_allocate_import_id(self):
        """Test import ID allocation."""
        session = RpcSession()

        id1 = session.allocate_import_id()
        id2 = session.allocate_import_id()
        id3 = session.allocate_import_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3
        assert session._next_import_id == 4

    def test_allocate_export_id(self):
        """Test export ID allocation."""
        session = RpcSession()

        id1 = session._allocate_export_id()
        id2 = session._allocate_export_id()
        id3 = session._allocate_export_id()

        assert id1 == 1
        assert id2 == 2
        assert id3 == 3
        assert session._next_export_id == 4


class TestExportCapability:
    """Test capability export functionality."""

    def test_export_new_capability(self):
        """Test exporting a new capability."""
        session = RpcSession()
        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        export_id = session.export_capability(stub)

        assert export_id == 1
        assert export_id in session._exports
        assert session._exports[export_id] is not None

    def test_export_same_capability_twice(self):
        """Test that exporting the same stub twice creates separate exports.

        Note: Each export calls dup() which creates a new hook instance,
        so the identity check fails and a new export ID is allocated.
        """
        session = RpcSession()
        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)

        export_id1 = session.export_capability(stub)
        export_id2 = session.export_capability(stub)

        # Different exports because dup() creates new instances
        assert export_id1 != export_id2
        assert len(session._exports) == 2

    def test_export_different_capabilities(self):
        """Test exporting different capabilities gets different IDs."""
        session = RpcSession()

        payload1 = RpcPayload.owned({"test": "data1"})
        hook1 = PayloadStubHook(payload1)
        stub1 = RpcStub(hook1)

        payload2 = RpcPayload.owned({"test": "data2"})
        hook2 = PayloadStubHook(payload2)
        stub2 = RpcStub(hook2)

        export_id1 = session.export_capability(stub1)
        export_id2 = session.export_capability(stub2)

        assert export_id1 != export_id2
        assert len(session._exports) == 2

    def test_export_promise(self):
        """Test exporting a promise."""
        session = RpcSession()
        future: asyncio.Future = asyncio.Future()
        hook = PromiseStubHook(future)
        promise = RpcPromise(hook)

        export_id = session.export_capability(promise)

        assert export_id == 1
        assert export_id in session._exports


class TestImportCapability:
    """Test capability import functionality."""

    def test_import_new_capability(self):
        """Test importing a new capability."""
        session = RpcSession()

        hook = session.import_capability(1)

        assert hook is not None
        assert 1 in session._imports
        assert session._imports[1] is hook

    def test_import_same_capability_twice(self):
        """Test that importing same ID returns same hook."""
        session = RpcSession()

        hook1 = session.import_capability(1)
        hook2 = session.import_capability(1)

        assert hook1 is hook2
        assert len(session._imports) == 1

    def test_import_different_capabilities(self):
        """Test importing different IDs creates different hooks."""
        session = RpcSession()

        hook1 = session.import_capability(1)
        hook2 = session.import_capability(2)

        assert hook1 is not hook2
        assert len(session._imports) == 2


class TestPromiseManagement:
    """Test promise creation and resolution."""

    def test_create_promise_hook(self):
        """Test creating a promise hook."""
        session = RpcSession()

        hook = session.create_promise_hook(1)

        assert isinstance(hook, PromiseStubHook)
        assert 1 in session._pending_promises

    def test_create_same_promise_twice(self):
        """Test creating same promise ID twice returns different hooks with same future."""
        session = RpcSession()

        hook1 = session.create_promise_hook(1)
        hook2 = session.create_promise_hook(1)

        # Different hooks, same future
        assert hook1 is not hook2
        assert len(session._pending_promises) == 1

    @pytest.mark.asyncio
    async def test_resolve_promise(self):
        """Test resolving a promise."""
        session = RpcSession()

        # Create promise
        hook = session.create_promise_hook(1)

        # Resolve it
        payload = RpcPayload.owned({"result": "success"})
        result_hook = PayloadStubHook(payload)
        session.resolve_promise(1, result_hook)

        # Verify it resolved
        assert 1 not in session._pending_promises
        resolved = await hook.pull()
        assert resolved.value == {"result": "success"}

    @pytest.mark.asyncio
    async def test_resolve_already_resolved_promise(self):
        """Test resolving an already resolved promise does nothing."""
        session = RpcSession()

        # Create and resolve promise
        hook = session.create_promise_hook(1)
        payload1 = RpcPayload.owned({"result": "first"})
        session.resolve_promise(1, PayloadStubHook(payload1))

        # Try to resolve again
        payload2 = RpcPayload.owned({"result": "second"})
        session.resolve_promise(1, PayloadStubHook(payload2))

        # Should have first result
        resolved = await hook.pull()
        assert resolved.value == {"result": "first"}

    @pytest.mark.asyncio
    async def test_reject_promise(self):
        """Test rejecting a promise with an error."""
        session = RpcSession()

        # Create promise
        hook = session.create_promise_hook(1)

        # Reject it
        error = RpcError.not_found("Test error")
        session.reject_promise(1, error)

        # Verify it rejected
        assert 1 not in session._pending_promises
        with pytest.raises(RpcError) as exc_info:
            await hook.pull()
        assert "Test error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reject_already_rejected_promise(self):
        """Test rejecting an already rejected promise does nothing."""
        session = RpcSession()

        # Create and reject promise
        hook = session.create_promise_hook(1)
        error1 = RpcError.not_found("First error")
        session.reject_promise(1, error1)

        # Try to reject again
        error2 = RpcError.internal("Second error")
        session.reject_promise(1, error2)

        # Should have first error
        with pytest.raises(RpcError) as exc_info:
            await hook.pull()
        assert "First error" in str(exc_info.value)

    def test_register_pending_import(self):
        """Test registering a pending import for pipelining."""
        session = RpcSession()

        future: asyncio.Future = asyncio.Future()
        session.register_pending_import(5, future)

        assert 5 in session._pending_promises
        assert session._pending_promises[5] is future


class TestReleaseManagement:
    """Test import/export release functionality."""

    def test_release_import(self):
        """Test releasing an imported capability."""
        session = RpcSession()

        # Import a capability
        session.import_capability(1)
        assert 1 in session._imports

        # Release it
        session.release_import(1)
        assert 1 not in session._imports

    def test_release_nonexistent_import(self):
        """Test releasing a non-existent import does nothing."""
        session = RpcSession()

        # Should not raise
        session.release_import(999)

    def test_release_export(self):
        """Test releasing an exported capability."""
        session = RpcSession()

        # Create and export a capability
        payload = RpcPayload.owned({"test": "data"})
        hook = PayloadStubHook(payload)
        stub = RpcStub(hook)
        export_id = session.export_capability(stub)

        assert export_id in session._exports

        # Release it
        session.release_export(export_id)
        assert export_id not in session._exports

    def test_release_nonexistent_export(self):
        """Test releasing a non-existent export does nothing."""
        session = RpcSession()

        # Should not raise
        session.release_export(999)


class TestTargetRegistration:
    """Test RPC target registration."""

    def test_register_target(self):
        """Test registering a local RPC target."""
        session = RpcSession()
        target = SimpleTarget("test_value")

        session.register_target(0, target)

        assert 0 in session._exports
        hook = session._exports[0]
        assert isinstance(hook, TargetStubHook)
        assert hook.target is target

    def test_register_multiple_targets(self):
        """Test registering multiple targets with different IDs."""
        session = RpcSession()
        target1 = SimpleTarget("value1")
        target2 = SimpleTarget("value2")

        session.register_target(0, target1)
        session.register_target(1, target2)

        assert len(session._exports) == 2
        hook0 = session._exports[0]
        hook1 = session._exports[1]
        assert isinstance(hook0, TargetStubHook)
        assert isinstance(hook1, TargetStubHook)
        assert hook0.target is target1
        assert hook1.target is target2


class TestGetHooks:
    """Test getting hooks from tables."""

    def test_get_export_hook(self):
        """Test getting an export hook."""
        session = RpcSession()
        target = SimpleTarget()
        session.register_target(0, target)

        hook = session.get_export_hook(0)
        assert hook is not None
        assert isinstance(hook, TargetStubHook)

    def test_get_nonexistent_export_hook(self):
        """Test getting a non-existent export hook returns None."""
        session = RpcSession()

        hook = session.get_export_hook(999)
        assert hook is None

    def test_get_import_hook(self):
        """Test getting an import hook."""
        session = RpcSession()
        session.import_capability(1)

        hook = session.get_import_hook(1)
        assert hook is not None

    def test_get_nonexistent_import_hook(self):
        """Test getting a non-existent import hook returns None."""
        session = RpcSession()

        hook = session.get_import_hook(999)
        assert hook is None


class TestNotImplementedMethods:
    """Test that abstract methods raise NotImplementedError."""

    def test_send_pipeline_call_not_implemented(self):
        """Test that send_pipeline_call raises NotImplementedError."""
        session = RpcSession()

        with pytest.raises(NotImplementedError, match="send_pipeline_call"):
            session.send_pipeline_call(1, ["method"], [], 2)

    def test_send_pipeline_get_not_implemented(self):
        """Test that send_pipeline_get raises NotImplementedError."""
        session = RpcSession()

        with pytest.raises(NotImplementedError, match="send_pipeline_get"):
            session.send_pipeline_get(1, ["prop"], 2)

    @pytest.mark.asyncio
    async def test_pull_import_not_implemented(self):
        """Test that pull_import raises NotImplementedError."""
        session = RpcSession()

        with pytest.raises(NotImplementedError, match="pull_import"):
            await session.pull_import(1)

    def test_send_release_message_does_nothing(self):
        """Test that default _send_release_message does nothing."""
        session = RpcSession()

        # Should not raise
        session._send_release_message(1)
