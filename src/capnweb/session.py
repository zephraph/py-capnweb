"""RpcSession - unified session management for Client and Server.

This module provides the RpcSession base class that manages import/export
tables and implements both the Exporter and Importer protocols. Both Client
and Server extend this class to get unified capability management.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from capnweb.hooks import (
    PromiseStubHook,
    RpcImportHook,
    StubHook,
    TargetStubHook,
)
from capnweb.parser import Parser
from capnweb.serializer import Serializer

if TYPE_CHECKING:
    from capnweb.stubs import RpcPromise, RpcStub
    from capnweb.types import RpcTarget


class RpcSession:
    """Base class for RPC sessions (Client and Server).

    This class manages the import and export tables, and implements both
    the Exporter and Importer protocols needed by Serializer and Parser.

    Responsibilities:
    1. Track imported capabilities (remote capabilities we reference)
    2. Track exported capabilities (local capabilities we expose)
    3. Allocate import/export IDs
    4. Create hooks for imports/exports
    5. Handle promise resolution
    """

    def __init__(self) -> None:
        """Initialize the RPC session."""
        # Import table: import_id -> StubHook (remote capabilities)
        self._imports: dict[int, StubHook] = {}
        self._next_import_id = 1

        # Export table: export_id -> StubHook (local capabilities)
        self._exports: dict[int, StubHook] = {}
        self._next_export_id = 1

        # Pending promises: promise_id -> Future[StubHook]
        self._pending_promises: dict[int, asyncio.Future[StubHook]] = {}

        # Create serializer and parser
        self.serializer = Serializer(exporter=self)
        self.parser = Parser(importer=self)

    # Exporter Protocol Implementation

    def export_capability(self, stub: RpcStub | RpcPromise) -> int:
        """Export a capability and return its export ID.

        This is called by the Serializer when it encounters a stub/promise
        that needs to be sent over the wire.

        Args:
            stub: The RpcStub or RpcPromise to export

        Returns:
            The export ID assigned to this capability
        """
        # Get the underlying hook
        hook: StubHook = stub._hook  # type: ignore[assignment]

        # Check if we've already exported this hook
        for export_id, existing_hook in self._exports.items():
            if existing_hook is hook:
                # Already exported, return existing ID
                return export_id

        # Allocate new export ID
        export_id = self._allocate_export_id()

        # Duplicate the hook (increment refcount) and store
        duped_hook: StubHook = hook.dup()  # type: ignore[assignment]
        self._exports[export_id] = duped_hook

        return export_id

    def _allocate_export_id(self) -> int:
        """Allocate a new export ID.

        Returns:
            A new export ID
        """
        export_id = self._next_export_id
        self._next_export_id += 1
        return export_id

    # Importer Protocol Implementation

    def import_capability(self, import_id: int) -> StubHook:
        """Import a capability and return its hook.

        This is called by the Parser when it encounters ["export", id] in
        the wire format (the remote side is exporting to us).

        Args:
            import_id: The import ID for this capability

        Returns:
            A StubHook representing the imported capability
        """
        # Check if we already have this import
        if import_id in self._imports:
            return self._imports[import_id]

        # Create a new RpcImportHook for this capability
        import_hook = RpcImportHook(session=self, import_id=import_id)
        self._imports[import_id] = import_hook

        return import_hook

    def create_promise_hook(self, promise_id: int) -> StubHook:
        """Create a promise hook for a future value.

        This is called by the Parser when it encounters ["promise", id] in
        the wire format.

        Args:
            promise_id: The promise ID

        Returns:
            A PromiseStubHook that will resolve when the promise settles
        """
        # Check if we already have a pending promise for this ID
        if promise_id in self._pending_promises:
            future = self._pending_promises[promise_id]
        else:
            # Create a new future for this promise
            future: asyncio.Future[StubHook] = asyncio.Future()
            self._pending_promises[promise_id] = future

        return PromiseStubHook(future)

    # Session Management

    def allocate_import_id(self) -> int:
        """Allocate a new import ID.

        Returns:
            A new import ID
        """
        import_id = self._next_import_id
        self._next_import_id += 1
        return import_id

    def register_pending_import(
        self, import_id: int, future: asyncio.Future[StubHook]
    ) -> None:
        """Register a pending import that will be resolved later.

        This is used for pipelining - we allocate an import ID before
        we know what the result will be.

        Args:
            import_id: The import ID to register
            future: The future that will resolve to the StubHook
        """
        self._pending_promises[import_id] = future

    def resolve_promise(self, promise_id: int, hook: StubHook) -> None:
        """Resolve a pending promise with a hook.

        Args:
            promise_id: The promise ID to resolve
            hook: The StubHook to resolve with
        """
        if promise_id in self._pending_promises:
            future = self._pending_promises.pop(promise_id)
            if not future.done():
                future.set_result(hook)

    def reject_promise(self, promise_id: int, error: Exception) -> None:
        """Reject a pending promise with an error.

        Args:
            promise_id: The promise ID to reject
            error: The error to reject with
        """
        if promise_id in self._pending_promises:
            future = self._pending_promises.pop(promise_id)
            if not future.done():
                future.set_exception(error)

    def release_import(self, import_id: int) -> None:
        """Release an imported capability.

        This is called when the local side is done with a remote capability.
        It should send a release message to the remote side.

        Args:
            import_id: The import ID to release
        """
        if import_id in self._imports:
            hook = self._imports.pop(import_id)
            hook.dispose()

            # Subclasses should override to send release message
            self._send_release_message(import_id)

    def release_export(self, export_id: int) -> None:
        """Release an exported capability.

        This is called when the remote side releases a capability we exported.

        Args:
            export_id: The export ID to release
        """
        if export_id in self._exports:
            hook = self._exports.pop(export_id)
            hook.dispose()

    def _send_release_message(self, import_id: int) -> None:
        """Send a release message to the remote side.

        Subclasses should override this to send the actual message.

        Args:
            import_id: The import ID to release
        """
        # Default implementation does nothing
        # Client/Server will override to send release messages

    # Target Management (for Server)

    def register_target(self, export_id: int, target: RpcTarget) -> None:
        """Register a local RPC target as an export.

        This is typically used by Server to expose local objects.

        Args:
            export_id: The export ID to use (usually 0 for main capability)
            target: The RpcTarget implementation
        """
        target_hook = TargetStubHook(target)
        self._exports[export_id] = target_hook

    # Pipelining Support (used by RpcImportHook)

    def send_pipeline_call(
        self,
        import_id: int,
        path: list[str | int],
        args: Any,
        result_import_id: int,
    ) -> None:
        """Send a pipelined call message.

        This is called by RpcImportHook when a call is made on a remote
        capability. Subclasses must implement the actual message sending.

        Args:
            import_id: The import ID to call on
            path: Property path + method name
            args: Arguments for the call
            result_import_id: Import ID for the result
        """
        msg = "Subclasses must implement send_pipeline_call"
        raise NotImplementedError(msg)

    def send_pipeline_get(
        self,
        import_id: int,
        path: list[str | int],
        result_import_id: int,
    ) -> None:
        """Send a pipelined property get message.

        This is called by RpcImportHook when a property is accessed on a
        remote capability.

        Args:
            import_id: The import ID to get from
            path: Property path
            result_import_id: Import ID for the result
        """
        msg = "Subclasses must implement send_pipeline_get"
        raise NotImplementedError(msg)

    async def pull_import(self, import_id: int) -> Any:
        """Pull the value from a remote capability.

        This is called by RpcImportHook when awaiting a remote capability.

        Args:
            import_id: The import ID to pull

        Returns:
            The pulled value
        """
        msg = "Subclasses must implement pull_import"
        raise NotImplementedError(msg)

    def get_export_hook(self, export_id: int) -> StubHook | None:
        """Get the hook for an exported capability.

        Args:
            export_id: The export ID

        Returns:
            The StubHook for this export, or None if not found
        """
        return self._exports.get(export_id)

    def get_import_hook(self, import_id: int) -> StubHook | None:
        """Get the hook for an imported capability.

        Args:
            import_id: The import ID

        Returns:
            The StubHook for this import, or None if not found
        """
        return self._imports.get(import_id)
