"""StubHook hierarchy for decentralized RPC capability management.

This module implements the hook pattern from the TypeScript reference implementation.
Each StubHook represents the backing implementation of an RPC-able reference.

Instead of a monolithic evaluator, different hook types handle different scenarios:
- ErrorStubHook: Holds an error
- PayloadStubHook: Wraps locally-resolved data
- TargetStubHook: Wraps a local RpcTarget object
- RpcImportHook: Represents a remote capability
- PromiseStubHook: Wraps a future that will resolve to another hook
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from capnweb.payload import RpcPayload

if TYPE_CHECKING:
    from capnweb.error import RpcError
    from capnweb.session import RpcSession
    from capnweb.types import RpcTarget


class StubHook(ABC):
    """Abstract base class for all stub hook implementations.

    A StubHook represents the backing implementation of an RPC capability.
    It knows how to handle calls, property access, promise resolution, etc.

    This is the core of the decentralized architecture - each hook type
    implements these methods according to its specific semantics.
    """

    @abstractmethod
    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Call a method through this hook.

        Args:
            path: Property path to navigate before calling (e.g., ["user", "profile", "getName"])
            args: Arguments wrapped in RpcPayload

        Returns:
            A new StubHook representing the result
        """
        ...

    @abstractmethod
    def get(self, path: list[str | int]) -> StubHook:
        """Get a property through this hook.

        Args:
            path: Property path to navigate (e.g., ["user", "id"])

        Returns:
            A new StubHook representing the property value
        """
        ...

    @abstractmethod
    async def pull(self) -> RpcPayload:
        """Pull the final value from this hook.

        This is what happens when you await a promise. It resolves the
        value (possibly waiting for network I/O) and returns the payload.

        Returns:
            The resolved payload

        Raises:
            RpcError: If the capability is in an error state
        """
        ...

    @abstractmethod
    def dispose(self) -> None:
        """Dispose this hook, releasing any resources.

        This decrements reference counts, sends release messages for remote
        capabilities, and cleans up state.
        """
        ...

    @abstractmethod
    def dup(self) -> StubHook:
        """Duplicate this hook (increment reference count).

        This is used when copying payloads to ensure proper refcounting.

        Returns:
            A new StubHook sharing the same underlying resource
        """
        ...


# TODO: make it a dataclass
class ErrorStubHook(StubHook):
    """A hook that holds an error.

    All operations on this hook either return itself or raise the error.
    This is useful for representing failed promises or broken capabilities.
    """

    def __init__(self, error: RpcError) -> None:
        """Initialize with an error.

        Args:
            error: The error this hook represents
        """
        self.error = error

    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Always returns self (errors propagate through chains)."""
        return self

    def get(self, path: list[str | int]) -> StubHook:
        """Always returns self (errors propagate through chains)."""
        return self

    async def pull(self) -> RpcPayload:
        """Raises the error."""
        raise self.error

    def dispose(self) -> None:
        """Nothing to dispose for errors."""

    def dup(self) -> StubHook:
        """Errors can be freely shared."""
        return self


class PayloadStubHook(StubHook):
    """A hook that wraps locally-resolved data.

    This represents a capability that has already been resolved to a local
    value. Method calls and property access navigate through the payload's
    object tree.
    """

    def __init__(self, payload: RpcPayload) -> None:
        """Initialize with a payload.

        Args:
            payload: The payload this hook wraps
        """
        self.payload = payload
        # Ensure payload is owned before use
        self.payload.ensure_deep_copied()

    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Navigate the path and call as a function.

        Args:
            path: Property path to navigate
            args: Arguments to pass to the function

        Returns:
            A new hook with the result
        """
        # Navigate to the target
        target = self._navigate(path)

        # If target is callable, call it
        if callable(target):
            args.ensure_deep_copied()
            # For now, assume synchronous call
            # TODO: Handle async callables
            try:
                result = (
                    target(*args.value)
                    if isinstance(args.value, list)
                    else target(args.value)
                )
                return PayloadStubHook(RpcPayload.owned(result))
            except Exception as e:
                from capnweb.error import RpcError

                error = RpcError.internal(f"Call failed: {e}")
                return ErrorStubHook(error)

        from capnweb.error import RpcError

        error = RpcError.bad_request(f"Target at {path} is not callable")
        return ErrorStubHook(error)

    def get(self, path: list[str | int]) -> StubHook:
        """Navigate the path and return the property.

        Args:
            path: Property path to navigate

        Returns:
            A new hook with the property value
        """
        try:
            value = self._navigate(path)
            return PayloadStubHook(RpcPayload.owned(value))
        except (KeyError, IndexError, AttributeError) as e:
            from capnweb.error import RpcError

            error = RpcError.not_found(f"Property {path} not found: {e}")
            return ErrorStubHook(error)

    def _navigate(self, path: list[str | int]) -> Any:
        """Navigate through the payload's value using the path.

        Args:
            path: List of property names/indices to navigate

        Returns:
            The value at the end of the path

        Raises:
            KeyError, IndexError, AttributeError: If navigation fails
        """
        current = self.payload.value

        for segment in path:
            if isinstance(segment, int):
                # Array index
                current = current[segment]
            elif isinstance(current, dict):
                # Dictionary key
                current = current[segment]
            else:
                # Object attribute
                current = getattr(current, segment)

        return current

    async def pull(self) -> RpcPayload:
        """Return the payload directly (already resolved)."""
        return self.payload

    def dispose(self) -> None:
        """Dispose the payload."""
        self.payload.dispose()

    def dup(self) -> StubHook:
        """Payloads can be shared (they manage their own stubs)."""
        # Note: The payload already tracks its stubs for disposal
        return PayloadStubHook(self.payload)


# TODO: make it a dataclass
class TargetStubHook(StubHook):
    """A hook that wraps a local RpcTarget object.

    This represents a local capability provided by the application. It
    delegates method calls to the actual Python object.
    """

    def __init__(self, target: RpcTarget) -> None:
        """Initialize with an RPC target.

        Args:
            target: The RpcTarget implementation
        """
        self.target = target
        self.ref_count = 1  # For disposal tracking

    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Call a method on the target.

        Args:
            path: Property path (last element is method name)
            args: Arguments for the call

        Returns:
            A new hook with the result
        """
        from capnweb.payload import RpcPayload as RpcPayloadClass

        args.ensure_deep_copied()

        # The last element of path is the method name
        # Earlier elements are properties to navigate
        if not path:
            from capnweb.error import RpcError

            error = RpcError.bad_request("Cannot call target without method name")
            return ErrorStubHook(error)

        # For now, assume path is just [method_name]
        # TODO: Handle property navigation before call
        method_name = str(path[-1])

        try:
            result = await self.target.call(
                method_name,
                args.value if isinstance(args.value, list) else [args.value],
            )
            return PayloadStubHook(RpcPayloadClass.from_app_return(result))
        except Exception as e:
            from capnweb.error import RpcError

            if isinstance(e, RpcError):
                return ErrorStubHook(e)
            error = RpcError.internal(f"Target call failed: {e}")
            return ErrorStubHook(error)

    def get(self, path: list[str | int]) -> StubHook:
        """Get a property from the target.

        Args:
            path: Property path

        Returns:
            A new hook with the property value
        """
        from capnweb.payload import RpcPayload as RpcPayloadClass

        # For now, delegate to target.get_property for simple case
        if len(path) == 1:

            async def get_property_async():
                try:
                    result = await self.target.get_property(str(path[0]))
                    return PayloadStubHook(RpcPayloadClass.from_app_return(result))
                except Exception as e:
                    from capnweb.error import RpcError

                    if isinstance(e, RpcError):
                        return ErrorStubHook(e)
                    error = RpcError.internal(f"Property access failed: {e}")
                    return ErrorStubHook(error)

            # Return a promise hook that will resolve to the property
            future: asyncio.Future[StubHook] = asyncio.ensure_future(
                get_property_async()
            )
            return PromiseStubHook(future)

        from capnweb.error import RpcError

        error = RpcError.not_found(
            "Complex property paths not yet supported on targets"
        )
        return ErrorStubHook(error)

    async def pull(self) -> RpcPayload:
        """Targets can't be pulled directly."""
        from capnweb.error import RpcError

        msg = "Cannot pull a target object"
        raise RpcError.bad_request(msg)

    def dispose(self) -> None:
        """Decrement reference count."""
        self.ref_count -= 1
        # TODO: Notify when refcount reaches 0 if target is disposable

    def dup(self) -> StubHook:
        """Increment reference count."""
        self.ref_count += 1
        return self


# TODO: make it a dataclass
class RpcImportHook(StubHook):
    """A hook representing a remote capability.

    This hook communicates with an RpcSession to send messages over the network.
    It tracks the import ID and delegates to the session for actual I/O.
    """

    def __init__(self, session: RpcSession, import_id: int) -> None:
        """Initialize with a session and import ID.

        Args:
            session: The RpcSession managing this import
            import_id: The import ID for this capability
        """
        self.session = session
        self.import_id = import_id
        self.ref_count = 1

    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Call a method on the remote capability.

        Args:
            path: Property path + method name
            args: Arguments

        Returns:
            A PromiseStubHook for the result
        """
        # Create a new import ID for the result
        result_import_id = self.session.allocate_import_id()

        # Create a future for the result
        future: asyncio.Future[StubHook] = asyncio.Future()

        # Register the future with the session
        self.session.register_pending_import(result_import_id, future)

        # Send a pipeline call message
        # This will be handled by the session
        self.session.send_pipeline_call(self.import_id, path, args, result_import_id)

        return PromiseStubHook(future)

    def get(self, path: list[str | int]) -> StubHook:
        """Get a property from the remote capability.

        Args:
            path: Property path

        Returns:
            A PromiseStubHook for the property
        """
        # Similar to call, but no arguments
        result_import_id = self.session.allocate_import_id()
        future: asyncio.Future[StubHook] = asyncio.Future()
        self.session.register_pending_import(result_import_id, future)
        self.session.send_pipeline_get(self.import_id, path, result_import_id)
        return PromiseStubHook(future)

    async def pull(self) -> RpcPayload:
        """Pull the value from the remote capability.

        Returns:
            The resolved payload
        """
        # Send a pull message and wait for response
        return await self.session.pull_import(self.import_id)

    def dispose(self) -> None:
        """Decrement refcount and send release if needed."""
        self.ref_count -= 1
        if self.ref_count == 0:
            self.session.release_import(self.import_id)

    def dup(self) -> StubHook:
        """Increment refcount."""
        self.ref_count += 1
        return self


# TODO: make it a dataclass
class PromiseStubHook(StubHook):
    """A hook wrapping a future that will resolve to another hook.

    This represents a promise - a value that will be available in the future.
    Operations on this hook create chained promises.
    """

    def __init__(self, future: asyncio.Future[StubHook]) -> None:
        """Initialize with a future hook.

        Args:
            future: The future that will resolve to a StubHook
        """
        self.future = future

    async def call(self, path: list[str | int], args: RpcPayload) -> StubHook:
        """Wait for the promise to resolve, then call on the result.

        Args:
            path: Property path + method name
            args: Arguments

        Returns:
            A new PromiseStubHook for the chained result
        """

        async def chained_call():
            resolved_hook = await self.future
            return await resolved_hook.call(path, args)

        chained_future: asyncio.Future[StubHook] = asyncio.ensure_future(chained_call())
        return PromiseStubHook(chained_future)

    def get(self, path: list[str | int]) -> StubHook:
        """Wait for the promise to resolve, then get property on the result.

        Args:
            path: Property path

        Returns:
            A new PromiseStubHook for the chained result
        """

        async def chained_get():
            resolved_hook = await self.future
            return resolved_hook.get(path)

        chained_future: asyncio.Future[StubHook] = asyncio.ensure_future(chained_get())
        return PromiseStubHook(chained_future)

    async def pull(self) -> RpcPayload:
        """Wait for the promise to resolve, then pull from the result.

        Returns:
            The final payload
        """
        resolved_hook = await self.future
        return await resolved_hook.pull()

    def dispose(self) -> None:
        """Cancel the promise if not resolved, or dispose the result if resolved."""
        if not self.future.done():
            self.future.cancel()
        elif not self.future.cancelled():
            try:
                result = self.future.result()
                result.dispose()
            except Exception:
                pass

    def dup(self) -> StubHook:
        """Share the same future (promises can be shared)."""
        return PromiseStubHook(self.future)
