"""Server implementation for Cap'n Web protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from aiohttp import web

from capnweb.error import RpcError
from capnweb.evaluator import ExpressionEvaluator
from capnweb.ids import ExportId, IdAllocator, ImportId
from capnweb.tables import ExportTable, ImportTable
from capnweb.wire import (
    WireAbort,
    WireError,
    WireMessage,
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


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for the Cap'n Web server."""

    host: str = "127.0.0.1"
    port: int = 8080
    max_batch_size: int = 100
    include_stack_traces: bool = False  # Security: disabled by default


class Server:
    """Cap'n Web server implementation.

    Supports HTTP batch transport with the protocol endpoints:
    - POST /rpc/batch: HTTP batch RPC
    """

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._id_allocator = IdAllocator()
        self._imports = ImportTable()
        self._exports = ExportTable()
        self._evaluator = ExpressionEvaluator(
            self._imports, self._exports, is_server=True
        )
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._pending_pulls: dict[ImportId, list[asyncio.Future[WireMessage]]] = {}

    def register_capability(self, export_id: int, target: RpcTarget) -> None:
        """Register a capability with the given export ID.

        Args:
            export_id: The export ID (typically 0 for main capability)
            target: The RPC target implementation
        """
        self._exports.add(ExportId(export_id), target)

    async def start(self) -> None:
        """Start the server."""
        self._app = web.Application()
        self._app.router.add_post("/rpc/batch", self._handle_batch)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await site.start()

        print(f"Server listening on {self.config.host}:{self.config.port}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._runner:
            await self._runner.cleanup()

    async def _handle_batch(self, request: web.Request) -> web.Response:
        """Handle HTTP batch requests."""
        try:
            body = await request.text()

            # Parse messages
            messages = parse_wire_batch(body)

            if len(messages) > self.config.max_batch_size:
                error = WireAbort(f"Batch size {len(messages)} exceeds maximum")
                return web.Response(
                    text=serialize_wire_batch([error]),
                    content_type="application/x-ndjson",
                    status=400,
                )

            # Process messages
            # Create a batch-local import table for this request
            # (HTTP batch is stateless - each request is a micro-session)
            batch_imports = ImportTable()

            # Track push sequence for this batch (client's import ID space)
            next_push_import_id = 1
            responses: list[WireMessage] = []
            for msg in messages:
                if isinstance(msg, WirePush):
                    # Assign the next sequential import ID for this push
                    import_id = ImportId(next_push_import_id)
                    next_push_import_id += 1
                    response = await self._handle_push(
                        msg.expression, import_id, batch_imports
                    )
                elif isinstance(msg, WirePull):
                    response = await self._handle_pull(
                        ImportId(msg.import_id), batch_imports
                    )
                else:
                    response = await self._process_message(msg)
                if response:
                    responses.append(response)

            # Send responses
            if responses:
                return web.Response(
                    text=serialize_wire_batch(responses),
                    content_type="application/x-ndjson",
                )
            return web.Response(status=204)

        except Exception as e:
            error = WireAbort(f"Server error: {e}")
            return web.Response(
                text=serialize_wire_batch([error]),
                content_type="application/x-ndjson",
                status=500,
            )

    async def _process_message(self, msg: WireMessage) -> WireMessage | None:
        """Process a single wire message.

        Returns a response message if needed, or None.
        Note: WirePush and WirePull are handled separately in _handle_batch
        to track sequential IDs and use batch-local import table.
        """
        match msg:
            case WireRelease(import_id, refcount):
                return await self._handle_release(ImportId(import_id), refcount)

            case _:
                # Push, Pull, Resolve, Reject, Abort are handled elsewhere or not expected
                return None

    async def _handle_push(
        self, expression: Any, import_id: ImportId, imports: ImportTable
    ) -> WireMessage | None:
        """Handle a push message - evaluate expression and store result.

        Args:
            expression: The expression to evaluate
            import_id: The import ID assigned sequentially for this push in the current batch
            imports: The batch-local import table

        The client's push messages are implicitly numbered sequentially (1, 2, 3...).
        The server tracks these in the import table so they can be pulled later.
        """
        try:
            # Evaluate the expression asynchronously
            # Don't wait for promises - store the future
            result_future: asyncio.Future[Any] = asyncio.create_task(
                self._evaluator.evaluate(expression, resolve_promises=True)
            )

            # Store in import table with the assigned import ID
            imports.add(import_id, result_future)

            # No immediate response - client will pull when ready
            return None

        except RpcError as e:
            # If evaluation fails immediately, we should reject
            stack = (
                str(e.data)
                if e.data
                else None
                if self.config.include_stack_traces
                else None
            )
            data = e.data if isinstance(e.data, dict) else None
            error_expr = WireError(str(e.code), e.message, stack, data)
            # Convert to export ID for the response
            return WireReject(-import_id.value, error_expr)
        except Exception as e:
            # Unexpected error - log it server-side but don't expose details to client
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in push: {e}", exc_info=True)

            # Only include stack trace if configured (security)
            stack = traceback.format_exc() if self.config.include_stack_traces else None
            error_expr = WireError("internal", "Internal server error", stack)
            # Convert to export ID for the response
            return WireReject(-import_id.value, error_expr)

    async def _handle_pull(
        self, import_id: ImportId, imports: ImportTable
    ) -> WireMessage | None:
        """Handle a pull message - send resolution when ready."""
        try:
            # Get the import (should be a future)
            result = imports.get(import_id)

            # If it's a future, wait for it
            if isinstance(result, asyncio.Future):
                result = await result

            # Convert import ID to export ID for the response
            export_id = import_id.to_export_id()

            # Send resolution
            return WireResolve(export_id.value, result)

        except RpcError as e:
            # Send rejection
            export_id = import_id.to_export_id()
            stack = (
                str(e.data)
                if e.data
                else None
                if self.config.include_stack_traces
                else None
            )
            data = e.data if isinstance(e.data, dict) else None
            error_expr = WireError(str(e.code), e.message, stack, data)
            return WireReject(export_id.value, error_expr)
        except Exception as e:
            # Unexpected error - log but don't expose details
            import logging
            import traceback

            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in pull: {e}", exc_info=True)

            export_id = import_id.to_export_id()
            stack = traceback.format_exc() if self.config.include_stack_traces else None
            error_expr = WireError("internal", "Internal server error", stack)
            return WireReject(export_id.value, error_expr)

    async def _handle_release(
        self, import_id: ImportId, refcount: int
    ) -> WireMessage | None:
        """Handle a release message - cleanup import table entries.

        Args:
            import_id: The import ID to release
            refcount: The total number of times this import has been introduced
        """
        # Release with the provided refcount
        self._imports.release(import_id, refcount)

        # No response needed for release
        return None
