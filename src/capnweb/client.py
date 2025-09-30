"""Client implementation for Cap'n Web protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from capnweb.error import ErrorCode, RpcError
from capnweb.evaluator import ExpressionEvaluator
from capnweb.ids import ExportId, IdAllocator, ImportId
from capnweb.tables import ExportTable, ImportTable
from capnweb.transports import HttpBatchTransport, WebSocketTransport, create_transport
from capnweb.wire import (
    PropertyKey,
    WireAbort,
    WireError,
    WireMessage,
    WirePipeline,
    WirePull,
    WirePush,
    WireReject,
    WireRelease,
    WireResolve,
    parse_wire_batch,
    serialize_wire_batch,
)

if TYPE_CHECKING:
    from capnweb.types import RpcTarget


@dataclass
class ClientConfig:
    """Configuration for the Cap'n Web client."""

    url: str
    timeout: float = 30.0


class Client:
    """Cap'n Web client implementation.

    Supports multiple transports via the Transport abstraction.
    """

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._id_allocator = IdAllocator()
        self._imports = ImportTable()
        self._exports = ExportTable()
        self._evaluator = ExpressionEvaluator(
            self._imports, self._exports, is_server=False
        )
        self._transport: HttpBatchTransport | WebSocketTransport | None = None
        self._pending_promises: dict[ImportId, asyncio.Future[Any]] = {}
        self._import_ref_counts: dict[ImportId, int] = {}

    async def __aenter__(self) -> Client:
        """Async context manager entry."""
        self._transport = create_transport(self.config.url, timeout=self.config.timeout)
        await self._transport.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client connection."""
        if self._transport:
            await self._transport.close()
            self._transport = None

    async def call(
        self,
        cap_id: int,
        method: str,
        args: list[Any],
        property_path: list[str] | None = None,
    ) -> Any:
        """Call a method on a remote capability.

        Args:
            cap_id: The capability ID (use 0 for main capability)
            method: The method name
            args: List of arguments
            property_path: Optional property path to navigate before calling method

        Returns:
            The result of the method call

        Raises:
            RpcError: If the call fails
        """
        if not self._transport:
            # Auto-create transport if not using context manager
            self._transport = create_transport(
                self.config.url, timeout=self.config.timeout
            )
            await self._transport.__aenter__()

        # For HTTP batch transport, each request is a micro-session
        # Import IDs start from 1 for each batch
        import_id = ImportId(1)

        # Build property path including method name
        full_path = (property_path or []) + [method]
        path_keys = [PropertyKey(p) for p in full_path]

        # Create pipeline expression that references the capability and calls the method
        # For cap_id=0 (main), we use ImportId(0)
        # The expression is: pipeline(cap_id, [property_path, method], args)
        pipeline_expr = WirePipeline(
            import_id=cap_id,
            property_path=path_keys,
            args=args,
        )

        # Create push and pull messages
        push_msg = WirePush(pipeline_expr)
        pull_msg = WirePull(import_id.value)

        # Send the batch
        batch = serialize_wire_batch([push_msg, pull_msg])

        try:
            # Use transport abstraction
            response_bytes = await self._transport.send_and_receive(
                batch.encode("utf-8")
            )
            response_text = response_bytes.decode("utf-8")

            if not response_text:
                # No content - call succeeded but no response
                return None

            # Parse responses
            messages = parse_wire_batch(response_text)

            # Process responses and extract result
            result = None
            error = None
            for msg in messages:
                if isinstance(msg, WireResolve) and msg.export_id == -import_id.value:
                    result = msg.value
                elif isinstance(msg, WireReject) and msg.export_id == -import_id.value:
                    error = self._parse_error(msg.error)

            if error:
                raise error

            return result

        except RpcError:
            raise
        except Exception as e:
            raise RpcError.internal(f"Transport error: {e}") from e
        finally:
            # Clean up
            self._pending_promises.pop(import_id, None)

    async def _process_message(self, msg: WireMessage) -> None:
        """Process a response message from the server."""
        match msg:
            case WireResolve(export_id, value):
                await self._handle_resolve(ExportId(export_id), value)

            case WireReject(export_id, error):
                await self._handle_reject(ExportId(export_id), error)

            case WireAbort(error):
                await self._handle_abort(error)

            case _:
                # Other message types not expected in client responses
                pass

    async def _handle_resolve(self, export_id: ExportId, value: Any) -> None:
        """Handle a resolve message from the server."""
        # Convert export ID to import ID (they're negatives of each other)
        import_id = export_id.to_import_id()

        # Get the pending promise
        future = self._pending_promises.get(import_id)
        if future and not future.done():
            # Resolve the promise with the value
            future.set_result(value)

    def _parse_error(self, error_expr: Any) -> RpcError:
        """Parse an error expression into an RpcError."""
        if isinstance(error_expr, WireError):
            return RpcError(
                ErrorCode(error_expr.error_type.lower().replace(" ", "_")),
                error_expr.message,
                error_expr.stack,
            )
        return RpcError.internal(f"Unknown error: {error_expr}")

    async def _handle_reject(self, export_id: ExportId, error_expr: Any) -> None:
        """Handle a reject message from the server."""
        # Convert export ID to import ID
        import_id = export_id.to_import_id()

        # Parse error
        error = self._parse_error(error_expr)

        # Get the pending promise
        future = self._pending_promises.get(import_id)
        if future and not future.done():
            # Reject the promise with the error
            future.set_exception(error)

    async def _handle_abort(self, error_expr: Any) -> None:
        """Handle an abort message from the server."""
        # Parse error
        if isinstance(error_expr, WireError):
            error = RpcError(
                ErrorCode.INTERNAL,
                f"Server aborted: {error_expr.message}",
                error_expr.stack,
            )
        else:
            error = RpcError.internal(f"Server aborted: {error_expr}")

        # Reject all pending promises
        for future in self._pending_promises.values():
            if not future.done():
                future.set_exception(error)

        self._pending_promises.clear()

    async def _release_import(self, import_id: ImportId) -> None:
        """Release an import by sending a release message."""
        if not self._transport:
            return

        # Get reference count
        refcount = self._import_ref_counts.pop(import_id, 1)

        # Send release message
        release_msg = WireRelease(import_id.value, refcount)
        batch = serialize_wire_batch([release_msg])

        # Use transport abstraction (ignore errors on release - best-effort)
        from contextlib import suppress

        with suppress(Exception):
            await self._transport.send_and_receive(batch.encode("utf-8"))
            # Release doesn't return a response typically

    def register_capability(self, export_id: int, target: RpcTarget) -> None:
        """Register a local capability that can be called by the server.

        Args:
            export_id: The export ID (should be negative for local exports)
            target: The RPC target implementation
        """
        self._exports.add(ExportId(export_id), target)
