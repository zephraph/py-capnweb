"""User-facing RPC stub and promise classes.

These classes provide the Pythonic interface to RPC capabilities. They are
thin wrappers around StubHook instances and use Python's magic methods to
provide a natural, Proxy-like API.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Self

from capnweb.payload import RpcPayload

if TYPE_CHECKING:
    from capnweb.hooks import StubHook


class RpcStub:
    """A reference to an RPC capability (stub).

    This class wraps a StubHook and provides a Pythonic interface using
    magic methods. It acts like a Proxy in TypeScript - property access
    and method calls are delegated to the hook.

    Example:
        ```python
        # Get a property - returns a promise
        user_id = stub.user.id

        # Call a method - returns a promise
        result = stub.calculate(5, 3)

        # Await the promise
        value = await result
        ```
    """

    def __init__(self, hook: StubHook) -> None:
        """Initialize with a hook.

        Args:
            hook: The StubHook backing this stub
        """
        # Use object.__setattr__ to avoid triggering __setattr__
        object.__setattr__(self, "_hook", hook)

    def __getattr__(self, name: str) -> RpcPromise:
        """Access a property, returning a promise for the value.

        Args:
            name: The property name

        Returns:
            An RpcPromise that will resolve to the property value
        """
        if name.startswith("_"):
            # Avoid infinite recursion for private attrs
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)

        # Get the property through the hook
        result_hook = self._hook.get([name])
        return RpcPromise(result_hook)  # type: ignore[arg-type]

    def __call__(self, *args: Any, **kwargs: Any) -> RpcPromise:
        """Call the stub as a function.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments (not yet supported)

        Returns:
            An RpcPromise that will resolve to the call result
        """
        if kwargs:
            msg = "Keyword arguments not yet supported in RPC calls"
            raise NotImplementedError(msg)

        # Package arguments into a payload
        args_payload = RpcPayload.from_app_params(list(args))

        # Call through the hook (empty path = call the stub itself)
        async def do_call():
            result_hook = await self._hook.call([], args_payload)
            return result_hook

        future = asyncio.ensure_future(do_call())

        from capnweb.hooks import PromiseStubHook  # noqa: PLC0415

        return RpcPromise(PromiseStubHook(future))

    def dispose(self) -> None:
        """Dispose this stub, releasing resources.

        After calling dispose, the stub should not be used anymore.
        """
        self._hook.dispose()

    async def __aenter__(self) -> Self:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager, disposing the stub."""
        self.dispose()

    def __repr__(self) -> str:
        """Return a readable representation."""
        return f"RpcStub({self._hook!r})"


class RpcPromise:
    """A promise for an RPC value.

    This class wraps a StubHook (usually a PromiseStubHook) and provides
    both promise chaining (property access, method calls) and awaiting.

    Example:
        ```python
        # Chain operations before awaiting
        promise = stub.user.profile.getName()

        # Await to get the final value
        name = await promise

        # Or use as async context manager
        async with stub.user.profile.getName() as name:
            print(name)
        ```
    """

    def __init__(self, hook: StubHook) -> None:
        """Initialize with a hook.

        Args:
            hook: The StubHook backing this promise
        """
        object.__setattr__(self, "_hook", hook)

    def __getattr__(self, name: str) -> RpcPromise:
        """Access a property on the promised value, returning a new promise.

        This enables chaining: `promise.user.id`

        Args:
            name: The property name

        Returns:
            A new RpcPromise for the property
        """
        if name.startswith("_"):
            msg = f"'{type(self).__name__}' object has no attribute '{name}'"
            raise AttributeError(msg)

        result_hook = self._hook.get([name])
        return RpcPromise(result_hook)  # type: ignore[arg-type]

    def __call__(self, *args: Any, **kwargs: Any) -> RpcPromise:
        """Call the promised value as a function, returning a new promise.

        This enables chaining: `promise.getUser(123).getName()`

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments (not yet supported)

        Returns:
            A new RpcPromise for the call result
        """
        if kwargs:
            msg = "Keyword arguments not yet supported in RPC calls"
            raise NotImplementedError(msg)

        args_payload = RpcPayload.from_app_params(list(args))

        async def do_call():
            result_hook = await self._hook.call([], args_payload)
            return result_hook

        future = asyncio.ensure_future(do_call())

        from capnweb.hooks import PromiseStubHook  # noqa: PLC0415

        return RpcPromise(PromiseStubHook(future))

    def __await__(self):
        """Make this promise awaitable.

        Returns:
            An awaitable that resolves to the final value
        """

        async def resolve():
            payload = await self._hook.pull()
            return payload.value

        return resolve().__await__()

    def dispose(self) -> None:
        """Dispose this promise, canceling it if pending."""
        self._hook.dispose()

    async def __aenter__(self) -> Any:
        """Enter async context manager, awaiting the value."""
        return await self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager, disposing the promise."""
        self.dispose()

    def __repr__(self) -> str:
        """Return a readable representation."""
        return f"RpcPromise({self._hook!r})"
