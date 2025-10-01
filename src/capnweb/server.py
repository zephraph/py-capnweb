"""Server implementation for Cap'n Web protocol."""

from __future__ import annotations

import asyncio
import logging
import traceback
from collections import UserDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, Self, cast

from aiohttp import web

from capnweb.error import RpcError
from capnweb.hooks import ErrorStubHook, PromiseStubHook, StubHook
from capnweb.ids import ImportId
from capnweb.payload import RpcPayload
from capnweb.resume import ResumeToken, ResumeTokenManager
from capnweb.session import RpcSession
from capnweb.wire import (
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


class ExportsProtocol(Protocol):
    """Protocol for exports that support both dict and ExportTable API."""

    def contains(self, export_id: Any) -> bool:
        """Check if export ID exists."""
        ...

    @property
    def _entries(self) -> dict[int, StubHook]:
        """Get raw entries dict."""
        ...

    def __getitem__(self, key: int) -> StubHook:
        """Get item by key."""
        ...

    def __setitem__(self, key: int, value: StubHook) -> None:
        """Set item by key."""
        ...

    def keys(self) -> Any:
        """Get keys."""
        ...

    def clear(self) -> None:
        """Clear all items."""
        ...

    def update(self, other: Any) -> None:
        """Update with other dict."""
        ...


@dataclass(frozen=True)
class ServerConfig:
    """Configuration for the Cap'n Web server."""

    host: str = "127.0.0.1"
    port: int = 8080
    max_batch_size: int = 100
    include_stack_traces: bool = False  # Security: disabled by default
    resume_token_ttl: float = 3600.0  # Resume token TTL in seconds (1 hour)


class Server(RpcSession):
    """Cap'n Web server implementation.

    Supports HTTP batch transport with the protocol endpoints:
    - POST /rpc/batch: HTTP batch RPC

    Extends RpcSession to get unified import/export table management.

    Session State and Transport Considerations:
    -------------------------------------------
    This server manages session state (Import/Export tables) that persists between
    requests when using resume tokens. This creates important architectural considerations:

    1. **HTTP Batch (Stateless Transport)**:
       - Each HTTP request is independent
       - Server holds session state in memory between requests
       - Memory usage grows with number of active sessions
       - Resume tokens enable "sessionful" model over stateless HTTP
       - Best for: Short-lived sessions, single-server deployments

    2. **WebSocket (Stateful Transport)**:
       - Long-lived connection with natural session lifecycle
       - Session state lifetime tied to connection
       - More resource-efficient (session ends when connection closes)
       - No need for resume tokens within same connection
       - Best for: Long-running sessions, real-time communication

    For production deployments:
    - Consider memory implications of holding sessions for HTTP clients
    - Use WebSocket for long-lived, stateful interactions
    - Use distributed session store (Redis) for multi-server HTTP deployments
    - Set appropriate `resume_token_ttl` to balance UX and resource usage
    """

    def __init__(self, config: ServerConfig) -> None:
        super().__init__()
        self.config = config
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._resume_manager = ResumeTokenManager(
            default_ttl=self.config.resume_token_ttl
        )
        # Track batch-local import tables for HTTP batch requests
        self._batch_imports: dict[int, StubHook] = {}

        # Create a wrapper that exposes both dict and ExportTable API
        self._exports_wrapper = self._create_exports_wrapper()

    @property
    def _exports_typed(self) -> ExportsProtocol:
        """Get _exports as ExportsProtocol for type checking."""
        return cast("ExportsProtocol", self._exports)

    def _create_exports_wrapper(self):
        """Create a wrapper that provides both dict and ExportTable API."""
        # Get the parent's _exports dict
        parent_exports = self.__dict__.get("_exports", {})

        class ExportsWrapper(UserDict):
            """Wrapper that acts like both a dict and ExportTable."""

            def contains(self, export_id):
                """ExportTable API compatibility."""
                if hasattr(export_id, "value"):
                    return export_id.value in self
                return export_id in self

            @property
            def _entries(self):
                """ExportTable API compatibility."""
                return self

        # Create wrapper with parent's exports
        wrapper = ExportsWrapper(parent_exports)
        # Store it directly in __dict__
        self.__dict__["_exports"] = wrapper
        return wrapper

    def register_capability(self, export_id: int, target: RpcTarget) -> None:
        """Register a capability with the given export ID.

        Args:
            export_id: The export ID (typically 0 for main capability)
            target: The RPC target implementation
        """
        self.register_target(export_id, target)

    async def __aenter__(self) -> Self:
        """Enter async context manager - starts the server."""
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager - stops the server."""
        await self.stop()

    @property
    def port(self) -> int:
        """Get the actual bound port (useful when port=0 for dynamic allocation)."""
        if self._site is None:
            return self.config.port
        # Get the first server socket from the site
        if self._site._server:  # noqa: SLF001
            return self._site._server.sockets[0].getsockname()[1]  # noqa: SLF001  # type: ignore[union-attr]
        return self.config.port

    async def start(self) -> None:
        """Start the server."""
        self._app = web.Application()
        self._app.router.add_post("/rpc/batch", self._handle_batch)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await self._site.start()

        print(f"Server listening on {self.config.host}:{self.port}")

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
            batch_imports: dict[int, StubHook] = {}

            # Track push sequence for this batch (client's import ID space)
            next_push_import_id = 1
            responses: list[WireMessage] = []
            for msg in messages:
                match msg:
                    case WirePush():
                        # Assign the next sequential import ID for this push
                        import_id = next_push_import_id
                        next_push_import_id += 1
                        response = await self._handle_push(
                            msg.expression, import_id, batch_imports
                        )
                    case WirePull():
                        response = await self._handle_pull(msg.import_id, batch_imports)
                    case _:
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
        self, expression: Any, import_id: int, imports: dict[int, StubHook]
    ) -> WireMessage | None:
        """Handle a push message - evaluate pipeline expression and store result.

        Args:
            expression: The wire expression (expected to be WirePipeline)
            import_id: The import ID assigned sequentially for this push in the current batch
            imports: The batch-local import table

        The client's push messages are implicitly numbered sequentially (1, 2, 3...).
        The server tracks these in the import table so they can be pulled later.

        Note: WirePipeline expressions are handled directly here, not through the Parser,
        because they are a server-side execution construct, not a serialized data type.
        """
        try:
            # Validate the pipeline expression
            if not isinstance(expression, WirePipeline):
                msg = "Expected WirePipeline expression in push"
                raise RpcError.bad_request(msg)

            # Get the target hook (either from batch imports or our exports)
            target_hook = imports.get(expression.import_id)
            if target_hook is None:
                target_hook = self.get_export_hook(expression.import_id)

            if target_hook is None:
                msg = f"Capability {expression.import_id} not found"
                raise RpcError.not_found(msg)

            # Parse arguments using the session's parser
            # This handles any ["export", id] references within the args
            args_payload = (
                self.parser.parse(expression.args)
                if expression.args is not None
                else RpcPayload.owned([])
            )

            # Extract the path (method and property names)
            path: list[str | int] = [
                str(pk.value) for pk in (expression.property_path or [])
            ]

            # Execute the call asynchronously
            async def execute_call() -> StubHook:
                """Execute the method call and return the result hook."""
                try:
                    # target_hook is guaranteed non-None at this point due to check above
                    assert target_hook is not None
                    # Call through the hook chain
                    result_hook = await target_hook.call(path, args_payload)
                    return result_hook

                except RpcError as e:
                    # RPC errors become ErrorStubHook
                    return ErrorStubHook(e)
                except Exception as e:
                    # Other errors become internal RPC errors
                    logger = logging.getLogger(__name__)
                    logger.exception("Call execution failed: %s", e)
                    return ErrorStubHook(RpcError.internal(f"Target call failed: {e}"))

            # Create a future for the result
            result_future: asyncio.Future[StubHook] = asyncio.create_task(
                execute_call()
            )

            # Store the future in the batch imports as a PromiseStubHook
            # so the client can pull it later
            imports[import_id] = PromiseStubHook(result_future)

            # No immediate response - client will pull when ready
            return None

        except RpcError as e:
            # If setup fails immediately, we should reject
            stack = (
                str(e.data)
                if e.data
                else None
                if self.config.include_stack_traces
                else None
            )
            data = e.data if isinstance(e.data, dict) else None
            error_expr = WireError(str(e.code.value), e.message, stack, data)
            return WireReject(-import_id, error_expr)

        except Exception as e:
            # Unexpected error - log it server-side but don't expose details to client
            logger = logging.getLogger(__name__)
            logger.exception("Unexpected error in push: %s", e)

            # Only include stack trace if configured (security)
            stack = traceback.format_exc() if self.config.include_stack_traces else None
            error_expr = WireError("internal", "Internal server error", stack)
            return WireReject(-import_id, error_expr)

    async def _handle_pull(
        self, import_id: int, imports: dict[int, StubHook]
    ) -> WireMessage | None:
        """Handle a pull message - resolve and send the result.

        Args:
            import_id: The import ID the client wants to pull
            imports: The batch-local import table

        Returns:
            WireResolve with the serialized result, or WireReject on error
        """
        try:
            # Get the hook from batch imports
            hook = imports.get(import_id)

            if hook is None:
                msg = f"Import {import_id} not found in batch"
                raise RpcError.not_found(msg)

            # Pull the final payload from the hook
            # This awaits the promise if it's a PromiseStubHook
            payload = await hook.pull()

            # Serialize the payload using the session's serializer
            # This will handle exporting any RpcStub/RpcPromise within the result
            serialized_value = self.serializer.serialize_payload(payload)

            # Export ID matches the import ID in the response
            export_id = import_id

            # Send resolution
            return WireResolve(export_id, serialized_value)

        except RpcError as e:
            # Send rejection
            export_id = import_id
            stack = (
                str(e.data)
                if e.data
                else None
                if self.config.include_stack_traces
                else None
            )
            data = e.data if isinstance(e.data, dict) else None
            error_expr = WireError(str(e.code.value), e.message, stack, data)
            return WireReject(export_id, error_expr)
        except Exception as e:
            # Unexpected error - log but don't expose details
            logger = logging.getLogger(__name__)
            logger.exception("Unexpected error in pull: %s", e)

            export_id = import_id
            stack = traceback.format_exc() if self.config.include_stack_traces else None
            error_expr = WireError("internal", "Internal server error", stack)
            return WireReject(export_id, error_expr)

    def create_resume_token(
        self, metadata: dict[str, Any] | None = None
    ) -> ResumeToken:
        """Create a resume token for the current session.

        Args:
            metadata: Optional custom metadata to include in the token

        Returns:
            ResumeToken that can be used to restore this session
        """
        # Snapshot current session state
        # For now, we'll store just the export IDs since imports are batch-local
        imports_dict = dict.fromkeys(self._imports.keys())  # Placeholder
        exports_dict = dict.fromkeys(self._exports.keys())  # Placeholder

        return self._resume_manager.create_token(
            imports=imports_dict, exports=exports_dict, metadata=metadata
        )

    def restore_from_token(self, token: ResumeToken) -> bool:
        """Restore session state from a resume token.

        Args:
            token: Token to restore from

        Returns:
            True if restoration was successful and session was found, False otherwise
        """
        result = self._resume_manager.restore_session(token)
        if result is None:
            return False

        imports_dict, exports_dict, session_found = result

        # If session was not found, this is a failed restoration
        if not session_found:
            return False

        # Restore exports into the wrapper
        # The wrapper is a dict subclass, so we can update it directly
        self._exports.clear()
        self._exports.update(exports_dict)

        # Restore imports if any were saved
        # Note: For HTTP batch mode, imports are batch-local, so restoration
        # mainly applies to WebSocket/stateful connections
        if imports_dict:
            self._imports.clear()
            self._imports.update(imports_dict)

        return True

    def invalidate_resume_token(self, session_id: str) -> None:
        """Invalidate a resume token.

        Args:
            session_id: Session ID to invalidate
        """
        self._resume_manager.invalidate_token(session_id)

    def cleanup_expired_tokens(self) -> int:
        """Clean up expired resume tokens.

        Returns:
            Number of tokens cleaned up
        """
        return self._resume_manager.cleanup_expired()

    async def _handle_release(
        self, import_id: ImportId, refcount: int
    ) -> WireMessage | None:
        """Handle a release message - cleanup import table entries.

        Args:
            import_id: The import ID to release
            refcount: The total number of times this import has been introduced
        """
        # Release the import
        self.release_import(import_id.value)

        # No response needed for release
        return None

    # RpcSession abstract method implementations

    def send_pipeline_call(
        self,
        import_id: int,
        path: list[str | int],
        args: RpcPayload,
        result_import_id: int,
    ) -> None:
        """Send a pipelined call message.

        Not used in HTTP batch mode - raises NotImplementedError.
        """
        msg = "Pipelining from server not supported in HTTP batch mode"
        raise NotImplementedError(msg)

    def send_pipeline_get(
        self,
        import_id: int,
        path: list[str | int],
        result_import_id: int,
    ) -> None:
        """Send a pipelined property get message.

        Not used in HTTP batch mode - raises NotImplementedError.
        """
        msg = "Pipelining from server not supported in HTTP batch mode"
        raise NotImplementedError(msg)

    async def pull_import(self, import_id: int) -> RpcPayload:
        """Pull the value from a remote capability.

        Not used in HTTP batch mode - raises NotImplementedError.
        """
        msg = "Pull from server not supported in HTTP batch mode"
        raise NotImplementedError(msg)
