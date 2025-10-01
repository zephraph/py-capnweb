"""Client implementation for Cap'n Web protocol."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from capnweb.error import ErrorCode, RpcError
from capnweb.hooks import ErrorStubHook, PayloadStubHook, TargetStubHook
from capnweb.ids import ExportId
from capnweb.payload import RpcPayload
from capnweb.pipeline import PendingCall, PipelineBatch, PipelinePromise
from capnweb.resume import ResumeToken  # noqa: TC001
from capnweb.session import RpcSession
from capnweb.stubs import RpcStub
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


class Client(RpcSession):
    """Cap'n Web client implementation.

    Supports multiple transports via the Transport abstraction.
    Extends RpcSession to get unified import/export table management.
    """

    def __init__(self, config: ClientConfig) -> None:
        super().__init__()
        self.config = config
        self._transport: HttpBatchTransport | WebSocketTransport | None = None
        self._import_ref_counts: dict[int, int] = {}

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        self._transport = create_transport(self.config.url, timeout=self.config.timeout)
        # Manually manage transport lifecycle - we're composing context managers
        await self._transport.__aenter__()  # noqa: PLC2801
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
            # We manually manage the lifecycle here to support concurrent calls
            self._transport = create_transport(
                self.config.url, timeout=self.config.timeout
            )
            await self._transport.__aenter__()  # noqa: PLC2801

        # For HTTP batch transport, each request is a micro-session
        # Import IDs start from 1 for each batch
        import_id = 1

        # Build property path including method name
        full_path = (property_path or []) + [method]
        path_keys = [PropertyKey(p) for p in full_path]

        # Serialize arguments using the new serializer
        args_payload = RpcPayload.from_app_params(args)
        serialized_args = self.serializer.serialize_payload(args_payload)

        # Create pipeline expression that references the capability and calls the method
        # For cap_id=0 (main), we use ImportId(0)
        # The expression is: pipeline(cap_id, [property_path, method], args)
        pipeline_expr = WirePipeline(
            import_id=cap_id,
            property_path=path_keys,
            args=serialized_args,
        )

        # Create push and pull messages
        push_msg = WirePush(pipeline_expr)
        pull_msg = WirePull(import_id)

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
                # Match either positive or negative export_id
                # Different implementations may use different conventions
                if isinstance(msg, WireResolve) and abs(msg.export_id) == import_id:
                    # Parse the result using the new parser
                    result_payload = self.parser.parse(msg.value)
                    result = result_payload.value
                elif isinstance(msg, WireReject) and abs(msg.export_id) == import_id:
                    error = self._parse_error(msg.error)

            if error:
                raise error

            return result

        except RpcError:
            raise
        except Exception as e:
            msg = f"Transport error: {e}"
            raise RpcError.internal(msg) from e

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
        import_id = -export_id.value

        # Parse the value using the parser
        result_payload = self.parser.parse(value)

        # Create a PayloadStubHook and resolve the promise
        hook = PayloadStubHook(result_payload)
        self.resolve_promise(import_id, hook)

    def _parse_error(self, error_expr: Any) -> RpcError:
        """Parse an error expression into an RpcError."""
        if isinstance(error_expr, WireError):
            # Try to map error type to ErrorCode, default to INTERNAL if unknown
            error_type = error_expr.error_type.lower().replace(" ", "_")
            try:
                code = ErrorCode(error_type)
            except ValueError:
                # Unknown error code, use INTERNAL
                code = ErrorCode.INTERNAL
            return RpcError(code, error_expr.message, error_expr.stack)
        return RpcError.internal(f"Unknown error: {error_expr}")

    async def _handle_reject(self, export_id: ExportId, error_expr: Any) -> None:
        """Handle a reject message from the server."""
        # Convert export ID to import ID
        import_id = -export_id.value

        # Parse error
        error = self._parse_error(error_expr)

        # Reject the promise
        self.reject_promise(import_id, error)

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
        for _promise_id, future in list(self._pending_promises.items()):
            if not future.done():
                future.set_exception(error)

        self._pending_promises.clear()

    def _send_release_message(self, import_id: int) -> None:
        """Send a release message to the remote side.

        Args:
            import_id: The import ID to release
        """
        if not self._transport:
            return

        # Get reference count
        refcount = self._import_ref_counts.pop(import_id, 1)

        # Send release message (best-effort, non-blocking)
        async def send_release():
            if self._transport:
                release_msg = WireRelease(import_id, refcount)
                batch = serialize_wire_batch([release_msg])

                with suppress(Exception):
                    await self._transport.send_and_receive(batch.encode("utf-8"))

        # Schedule the release to run in the background
        asyncio.create_task(send_release())

    def register_capability(self, export_id: int, target: RpcTarget) -> None:
        """Register a local capability that can be called by the server.

        Args:
            export_id: The export ID (should be negative for local exports)
            target: The RPC target implementation
        """
        self.register_target(export_id, target)

    def create_stub(
        self, target: RpcTarget
    ) -> Any:  # Returns RpcStub but avoiding circular import
        """Create a stub for a local capability that can be passed to the server.

        This allocates an export ID and registers the target, returning an RpcStub
        that can be passed as an argument to server methods.

        Args:
            target: The local RpcTarget to export

        Returns:
            RpcStub that references the exported capability
        """
        # Create hook for the target
        hook = TargetStubHook(target)

        # Allocate next export ID
        export_id = len(self._exports)
        while export_id in self._exports:
            export_id += 1

        # Store the hook in exports so the serializer can find it
        self._exports[export_id] = hook

        # Return stub wrapping the hook
        return RpcStub(hook)

    def validate_resume_token(self, token: ResumeToken) -> bool:
        """Validate a resume token.

        Args:
            token: Token to validate

        Returns:
            True if token is valid (not expired, properly formed), False otherwise

        Note:
            This only validates the token structure and expiration.
            Server-side validation is required to ensure the session still exists.
        """
        return token.is_valid()

    def get_resume_token_info(self, token: ResumeToken) -> dict[str, Any]:
        """Get information about a resume token without restoring it.

        Args:
            token: Token to inspect

        Returns:
            Dictionary with token information (session_id, expires_at, etc.)
        """
        return {
            "session_id": token.session_id,
            "created_at": token.created_at,
            "expires_at": token.expires_at,
            "is_expired": token.is_expired(),
            "is_valid": token.is_valid(),
            "capability_count": len(token.capabilities),
            "metadata": token.metadata,
        }

    def pipeline(self) -> PipelineBatch:
        """Create a pipeline batch for batching multiple RPC calls.

        Returns:
            A PipelineBatch that can be used to make multiple calls
            that will be sent in a single HTTP batch

        Example:
            ```python
            batch = client.pipeline()
            user = batch.call(0, "authenticate", ["token-123"])
            profile = batch.call(0, "getUserProfile", [user.id])
            notifications = batch.call(0, "getNotifications", [user.id])

            # All three calls sent in one HTTP request
            u, p, n = await asyncio.gather(user, profile, notifications)
            ```
        """
        return PipelineBatch(self)

    def call_pipelined(
        self,
        batch: PipelineBatch,
        cap_id: int,
        method: str,
        args: list[Any],
        property_path: list[str] | None = None,
    ) -> PipelinePromise:
        """Make a pipelined RPC call as part of a batch.

        Args:
            batch: The pipeline batch this call belongs to
            cap_id: The capability ID (use 0 for main capability)
            method: The method name
            args: List of arguments (can include PipelinePromise objects)
            property_path: Optional property path to navigate before calling method

        Returns:
            A PipelinePromise that can be awaited or used in other pipelined calls

        Note:
            This method is typically called through PipelineBatch.call() rather than directly.
        """
        import_id = batch._allocate_import_id()
        pending_call = PendingCall(
            import_id=import_id,
            cap_id=cap_id,
            method=method,
            args=args,
            property_path=property_path,
        )
        batch._add_call(pending_call)
        return PipelinePromise(self, batch, import_id)

    # RpcSession abstract method implementations

    def send_pipeline_call(
        self,
        import_id: int,
        path: list[str | int],
        args: RpcPayload,
        result_import_id: int,
    ) -> None:
        """Send a pipelined call message.

        This is called by RpcImportHook when a call is made on a remote
        capability. Since HTTP batch transport can't pipeline, we need to
        send immediately and block.

        Args:
            import_id: The import ID to call on
            path: Property path + method name
            args: Arguments for the call
            result_import_id: Import ID for the result
        """
        # For HTTP batch, we can't truly pipeline - we have to send immediately
        # Create a task that will be resolved when the result comes back

        # Build property path for the wire message
        path_keys = [PropertyKey(p) for p in path]

        # Serialize arguments
        serialized_args = self.serializer.serialize_payload(args)

        # Create pipeline expression
        pipeline_expr = WirePipeline(
            import_id=import_id,
            property_path=path_keys,
            args=serialized_args,
        )

        # Create push and pull messages
        push_msg = WirePush(pipeline_expr)
        pull_msg = WirePull(result_import_id)

        # Send immediately in a background task
        async def send_and_handle():
            if not self._transport:
                return

            batch = serialize_wire_batch([push_msg, pull_msg])
            response_bytes = await self._transport.send_and_receive(
                batch.encode("utf-8")
            )
            response_text = response_bytes.decode("utf-8")

            # Parse response and resolve the pending import
            messages = parse_wire_batch(response_text)
            for msg in messages:
                if isinstance(msg, WireResolve) and msg.export_id == -result_import_id:
                    result_payload = self.parser.parse(msg.value)
                    # Get the future for this import
                    if result_import_id in self._pending_promises:
                        future = self._pending_promises.pop(result_import_id)
                        if not future.done():
                            # Create hook from the payload
                            result_hook = PayloadStubHook(result_payload)
                            future.set_result(result_hook)
                elif isinstance(msg, WireReject) and msg.export_id == -result_import_id:
                    error = self._parse_error(msg.error)
                    if result_import_id in self._pending_promises:
                        future = self._pending_promises.pop(result_import_id)
                        if not future.done():
                            error_hook = ErrorStubHook(error)
                            future.set_result(error_hook)

        # Schedule the task
        asyncio.create_task(send_and_handle())

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
        # Similar to send_pipeline_call but with no args
        self.send_pipeline_call(import_id, path, RpcPayload.owned([]), result_import_id)

    async def pull_import(self, import_id: int) -> RpcPayload:
        """Pull the value from a remote capability.

        This is called by RpcImportHook when awaiting a remote capability.

        Args:
            import_id: The import ID to pull

        Returns:
            The pulled value as RpcPayload
        """
        # Send a pull message and await the response
        if not self._transport:
            msg = "No transport available"
            raise RpcError.internal(msg)

        pull_msg = WirePull(import_id)
        batch = serialize_wire_batch([pull_msg])

        response_bytes = await self._transport.send_and_receive(batch.encode("utf-8"))
        response_text = response_bytes.decode("utf-8")

        if not response_text:
            msg = "Empty response from pull"
            raise RpcError.internal(msg)

        # Parse responses
        messages = parse_wire_batch(response_text)

        for msg in messages:
            if isinstance(msg, WireResolve) and msg.export_id == -import_id:
                # Parse and return the value
                return self.parser.parse(msg.value)
            if isinstance(msg, WireReject) and msg.export_id == -import_id:
                error = self._parse_error(msg.error)
                raise error

        msg = "No response for pull"
        raise RpcError.internal(msg)
