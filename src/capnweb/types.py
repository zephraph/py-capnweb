"""Core type definitions for Cap'n Web protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol


class RpcTarget(ABC):
    """Abstract base class for RPC capability implementations.

    Capabilities are objects that can receive method calls and property access
    over the RPC protocol.
    """

    @abstractmethod
    async def call(self, method: str, args: list[Any]) -> Any:
        """Call a method on this capability.

        Args:
            method: The method name to call
            args: List of arguments for the method

        Returns:
            The result of the method call

        Raises:
            RpcError: If the method call fails
        """
        ...

    @abstractmethod
    async def get_property(self, property: str) -> Any:
        """Get a property from this capability.

        Args:
            property: The property name to access

        Returns:
            The property value

        Raises:
            RpcError: If the property access fails
        """
        ...


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
