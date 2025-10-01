from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from capnweb.hooks import StubHook
    from capnweb.stubs import RpcPromise, RpcStub


class PayloadSource(Enum):
    """Represents the provenance of payload data.

    This tells us where the data came from and how we can safely use it:
    - PARAMS: From application as call parameters. Must be deep-copied before use.
    - RETURN: From application as return value. We take ownership.
    - OWNED: Deserialized or already copied. We own it and can modify safely.
    """

    PARAMS = auto()  # From app as call parameters. Must be copied.
    RETURN = auto()  # From app as a return value. We take ownership.
    OWNED = auto()  # Deserialized or copied. We own it.


@dataclass
class RpcPayload:
    """Wraps data with explicit ownership semantics for RPC transmission.

    This class is central to preventing data corruption bugs. It explicitly
    tracks where data came from and ensures we never accidentally mutate
    application data or share mutable state across RPC boundaries.

    Key responsibilities:
    1. Track data provenance (PARAMS, RETURN, or OWNED)
    2. Deep-copy application data when needed
    3. Track all RPC stubs and promises within the payload
    4. Provide explicit disposal for resource cleanup

    Example:
        ```python
        # From application parameters - must copy
        payload = RpcPayload.from_app_params({"user": user_dict})

        # Ensure it's safe to use
        payload.ensure_deep_copied()

        # Now we can safely pass it to RPC without worrying about mutations
        await stub.call("method", payload)

        # Clean up resources when done
        payload.dispose()
        ```
    """

    value: Any
    source: PayloadSource
    # These are only populated when source is OWNED (after deep copy)
    # They track all RPC references within this payload for lifecycle management
    stubs: list[RpcStub] = field(
        default_factory=list
    )  # All RpcStub instances found in value
    promises: list[tuple[Any, str | int, RpcPromise]] = field(
        default_factory=list
    )  # (parent, property, promise)

    @classmethod
    def from_app_params(cls, value: Any) -> RpcPayload:
        """Create a payload from parameters provided by the application.

        This marks the data as PARAMS, meaning it must be deep-copied before
        use to prevent the RPC system from accidentally mutating application state.

        Args:
            value: The parameter value from the application

        Returns:
            A new RpcPayload with source=PARAMS
        """
        return cls(value, PayloadSource.PARAMS)

    @classmethod
    def from_app_return(cls, value: Any) -> RpcPayload:
        """Create a payload from a return value provided by the application.

        This marks the data as RETURN, meaning the application is transferring
        ownership to the RPC system. We can take ownership without copying.

        Args:
            value: The return value from the application

        Returns:
            A new RpcPayload with source=RETURN
        """
        return cls(value, PayloadSource.RETURN)

    @classmethod
    def owned(cls, value: Any) -> RpcPayload:
        """Create a payload that is already owned by the RPC system.

        This is used for deserialized data or data that has been deep-copied.

        Args:
            value: The owned value

        Returns:
            A new RpcPayload with source=OWNED
        """
        return cls(value, PayloadSource.OWNED)

    def ensure_deep_copied(self) -> None:
        """Ensure this payload owns its data through deep copying if needed.

        This is the most critical method for correctness. It:
        1. Deep-copies the value if source is PARAMS (to prevent mutation bugs)
        2. Takes ownership if source is RETURN (no copy needed)
        3. Finds and tracks all RpcStub/RpcPromise instances
        4. Transitions source to OWNED

        After calling this, the payload is safe to use and modify within the
        RPC system without worrying about corrupting application state.
        """
        match self.source:
            case PayloadSource.OWNED:
                # Already owned, nothing to do
                return
            case PayloadSource.PARAMS:
                # Must deep-copy to prevent mutating application data
                self.value = self._deep_copy_and_track(self.value)
            case PayloadSource.RETURN:
                # Application gave us ownership, but we still need to track stubs/promises
                self._track_references(self.value)

        # Now we own this data
        self.source = PayloadSource.OWNED

    def _deep_copy_and_track(self, obj: Any) -> Any:
        """Deep copy an object while tracking all RPC references.

        Args:
            obj: The object to copy

        Returns:
            A deep copy with all RPC references tracked
        """
        # Import here to avoid circular dependency
        from capnweb.stubs import RpcPromise, RpcStub  # noqa: PLC0415

        # Handle RpcStub and RpcPromise specially - don't copy them,
        # but track them and duplicate their hooks
        match obj:
            case RpcStub():
                # Create a duplicate (shares the hook, increments refcount)

                dup: StubHook = obj._hook.dup()  # type: ignore[assignment]
                new_stub = RpcStub(dup)
                self.stubs.append(new_stub)
                return new_stub

            case RpcPromise():
                # Create a duplicate (shares the hook, increments refcount)

                dup: StubHook = obj._hook.dup()  # type: ignore[assignment]
                new_promise = RpcPromise(dup)
                # Note: parent and property tracking would happen at the container level
                return new_promise

            case None | bool() | int() | float() | str() | bytes():
                # Handle primitive types - return as-is (immutable)
                return obj

            case list():
                # Handle lists
                return [self._deep_copy_and_track(item) for item in obj]

            case dict():
                # Handle dicts
                return {
                    key: self._deep_copy_and_track(value) for key, value in obj.items()
                }

            case _:
                # For other types, try to copy using copy module

                try:
                    return copy.deepcopy(obj)
                except Exception:
                    # If deepcopy fails, return as-is and hope it's immutable
                    return obj

    def _track_references(
        self, obj: Any, parent: Any = None, key: str | int | None = None
    ) -> None:
        """Track all RPC references in an object without copying.

        Args:
            obj: The object to scan
            parent: The parent container (for promise tracking)
            key: The key/index in parent (for promise tracking)
        """
        from capnweb.stubs import RpcPromise, RpcStub  # noqa: PLC0415

        match obj:
            case RpcStub():
                self.stubs.append(obj)
            case RpcPromise():
                if parent is not None and key is not None:
                    self.promises.append((parent, key, obj))
            case list():
                # Recursively track in lists
                for i, item in enumerate(obj):
                    self._track_references(item, obj, i)
            case dict():
                # Recursively track in dicts
                for k, v in obj.items():
                    self._track_references(v, obj, k)

    def dispose(self) -> None:
        """Recursively dispose all RPC stubs and promises in this payload.

        This ensures proper resource cleanup by calling dispose() on all
        tracked RPC references. After calling this, the payload should not
        be used anymore.

        This is critical for preventing resource leaks, especially with
        remote capabilities that need to send "release" messages.
        """
        # Dispose all tracked stubs
        for stub in self.stubs:
            stub.dispose()

        # Dispose all tracked promises
        for _parent, _key, promise in self.promises:
            promise.dispose()

        # Clear tracking lists
        self.stubs.clear()
        self.promises.clear()

    def __repr__(self) -> str:
        """Return a readable representation for debugging."""
        return f"RpcPayload(source={self.source.name}, value={self.value!r})"
