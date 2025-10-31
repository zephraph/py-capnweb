"""Core type definitions for Cap'n Web protocol."""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any, Protocol


class RpcTarget(ABC):
    """Base class for RPC capability implementations.

    Methods defined on subclasses automatically become RPC-callable,
    similar to the Cloudflare capnweb API. Methods starting with underscore
    are considered private and not exposed over RPC.

    Example:
        class Calculator(RpcTarget):
            async def add(self, a: int, b: int) -> int:
                return a + b

            async def subtract(self, a: int, b: int) -> int:
                return a - b

            def _private_helper(self):  # Not exposed over RPC
                pass

    For advanced use cases, you can override `call()` and `get_property()`
    to implement custom dispatch logic (e.g., for backward compatibility
    with match/case dispatch patterns).
    """

    async def call(self, method: str, args: list[Any]) -> Any:
        """Call a method on this capability.

        By default, this looks up the method by name on the instance
        and calls it with the provided arguments. Methods starting with
        underscore are not accessible over RPC.

        Args:
            method: The method name to call
            args: List of arguments for the method

        Returns:
            The result of the method call

        Raises:
            RpcError: If the method is not found or call fails
        """
        from .error import RpcError

        # Don't allow private methods
        if method.startswith("_"):
            raise RpcError.not_found(f"Method {method} not found")

        # Look up the method
        if not hasattr(self, method):
            raise RpcError.not_found(f"Method {method} not found")

        method_obj = getattr(self, method)

        # Check if it's callable
        if not callable(method_obj):
            raise RpcError.not_found(f"Method {method} not found")

        # Call the method
        result = method_obj(*args)

        # Handle async methods
        if inspect.iscoroutine(result):
            return await result

        return result

    async def get_property(self, property: str) -> Any:
        """Get a property from this capability.

        By default, this looks up the attribute by name on the instance.
        Attributes starting with underscore are not accessible over RPC.

        Args:
            property: The property name to access

        Returns:
            The property value

        Raises:
            RpcError: If the property is not found or access fails
        """
        from .error import RpcError

        # Don't allow private properties
        if property.startswith("_"):
            raise RpcError.not_found(f"Property {property} not found")

        # Look up the property
        if not hasattr(self, property):
            raise RpcError.not_found(f"Property {property} not found")

        value = getattr(self, property)

        # Don't expose methods as properties
        if callable(value):
            raise RpcError.not_found(f"Property {property} not found")

        return value


class Transport(Protocol):
    """Protocol for RPC transports."""

    async def send(self, data: bytes) -> None:
        """Send data over the transport.

        Args:
            data: The data to send

        Raises:
            Exception: If sending fails
        """
        ...

    async def receive(self) -> bytes:
        """Receive data from the transport.

        Returns:
            The received data

        Raises:
            Exception: If receiving fails
        """
        ...

    async def close(self) -> None:
        """Close the transport connection.

        Raises:
            Exception: If closing fails
        """
        ...
