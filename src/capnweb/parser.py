"""Parser (Evaluator) for converting wire format to Python objects.

This module replaces the old ExpressionEvaluator's deserialization logic with
a cleaner, more explicit approach. The Parser takes JSON-serializable wire
expressions and, with the help of an Importer (the RpcSession), converts them
to Python objects wrapped in RpcPayload.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from capnweb.error import ErrorCode, RpcError
from capnweb.hooks import (
    ErrorStubHook,
)
from capnweb.payload import RpcPayload
from capnweb.stubs import RpcPromise, RpcStub
from capnweb.wire import WireError, WireExport
from capnweb.wire import WirePromise as WirePromiseType

if TYPE_CHECKING:
    from capnweb.hooks import StubHook


class Importer(Protocol):
    """Protocol for objects that can import capabilities.

    This is typically implemented by RpcSession (Client/Server).
    """

    def import_capability(self, import_id: int) -> StubHook:
        """Import a capability and return its hook.

        Args:
            import_id: The import ID for this capability

        Returns:
            A StubHook representing the imported capability
        """
        ...

    def create_promise_hook(self, promise_id: int) -> StubHook:
        """Create a promise hook for a future value.

        Args:
            promise_id: The promise ID

        Returns:
            A PromiseStubHook that will resolve when the promise settles
        """
        ...


class Parser:
    """Converts wire format to Python objects for RPC reception.

    This class (called Evaluator in TypeScript) is responsible for:
    1. Taking JSON-serializable wire expressions
    2. Finding ["export", id] and creating RpcStub with RpcImportHook
    3. Finding ["promise", id] and creating RpcPromise with PromiseStubHook
    4. Finding ["error", ...] and creating ErrorStubHook
    5. Returning the final result as RpcPayload.owned()

    The key difference from the old evaluator: this is a pure, stateless
    transformation. All state management happens in the RpcSession (Importer).
    """

    def __init__(self, importer: Importer) -> None:
        """Initialize with an importer.

        Args:
            importer: The RpcSession that manages import IDs
        """
        self.importer = importer

    def parse(self, wire_value: Any) -> RpcPayload:
        """Parse a wire expression into a Python value wrapped in RpcPayload.

        This is the main entry point. It recursively walks the wire structure
        and converts it to Python objects, creating stubs/promises as needed.

        Args:
            wire_value: The wire expression to parse (JSON-serializable)

        Returns:
            An RpcPayload.owned() containing the parsed value
        """
        parsed = self._parse_value(wire_value)
        return RpcPayload.owned(parsed)

    def _parse_value(self, value: Any) -> Any:
        """Parse a single wire value recursively.

        Args:
            value: The wire value to parse

        Returns:
            The parsed Python value
        """
        # Handle None and primitives
        if value is None or isinstance(value, (bool, int, float, str)):
            return value

        # Handle lists - could be wire expressions or arrays
        if isinstance(value, list):
            if len(value) >= 2 and isinstance(value[0], str):
                # This might be a wire expression like ["export", id]
                wire_type = value[0]

                if wire_type == "export":
                    # ["export", export_id]
                    return self._parse_export(value)

                if wire_type == "import":
                    # ["import", import_id]
                    return self._parse_import(value)

                if wire_type == "promise":
                    # ["promise", promise_id]
                    return self._parse_promise(value)

                if wire_type == "error":
                    # ["error", type, message, ...]
                    return self._parse_error(value)

                if wire_type == "pipeline":
                    # ["pipeline", import_id, [...path], args]
                    # This is handled by the session, not here
                    # For now, treat as error

                    error = RpcError.bad_request(
                        "Pipeline expressions should not appear in parse input"
                    )
                    return RpcStub(ErrorStubHook(error))

            # Regular array - parse each element
            return [self._parse_value(item) for item in value]

        # Handle dicts - parse each value
        if isinstance(value, dict):
            return {key: self._parse_value(val) for key, val in value.items()}

        # For other types, return as-is
        return value

    def _parse_export(self, wire_expr: list[Any]) -> Any:
        """Parse an export expression.

        When we receive ["export", id], it means the remote side is exporting
        a capability to us. We create an import for it.

        Args:
            wire_expr: ["export", export_id]

        Returns:
            An RpcStub wrapping an RpcImportHook
        """

        wire_export = WireExport.from_json(wire_expr)
        export_id = wire_export.export_id

        # The export ID becomes our import ID
        # (we're importing what they're exporting)
        import_hook = self.importer.import_capability(export_id)
        return RpcStub(import_hook)

    def _parse_import(self, wire_expr: list[Any]) -> Any:
        """Parse an import expression.

        When we receive ["import", id], it means the remote side is referencing
        a capability we exported to them. This shouldn't normally appear in
        parse input - it's typically used in serialization.

        Args:
            wire_expr: ["import", import_id]

        Returns:
            An error stub (imports shouldn't appear in received data)
        """

        error = RpcError.bad_request(
            "Import expressions should not appear in parse input"
        )
        return RpcStub(ErrorStubHook(error))

    def _parse_promise(self, wire_expr: list[Any]) -> Any:
        """Parse a promise expression.

        When we receive ["promise", id], it means the remote side is sending
        us a promise that will resolve later.

        Args:
            wire_expr: ["promise", promise_id]

        Returns:
            An RpcPromise wrapping a PromiseStubHook
        """

        wire_promise = WirePromiseType.from_json(wire_expr)
        promise_id = wire_promise.promise_id

        # Create a promise hook that will resolve when the promise settles
        promise_hook = self.importer.create_promise_hook(promise_id)
        return RpcPromise(promise_hook)

    def _parse_error(self, wire_expr: list[Any]) -> Any:
        """Parse an error expression.

        When we receive ["error", type, message, ...], we create an ErrorStubHook
        containing the RpcError.

        Args:
            wire_expr: ["error", type, message, stack?, data?]

        Returns:
            An RpcStub wrapping an ErrorStubHook
        """

        wire_error = WireError.from_json(wire_expr)

        # Convert string error type to ErrorCode enum
        try:
            error_code = ErrorCode(wire_error.error_type)
        except ValueError:
            # If unknown error type, default to internal
            error_code = ErrorCode.INTERNAL

        # Create RpcError from wire error
        error = RpcError(
            code=error_code,
            message=wire_error.message,
            data=wire_error.data,
        )

        # Wrap in ErrorStubHook and return as stub
        return RpcStub(ErrorStubHook(error))

    def parse_payload_value(self, wire_value: Any) -> RpcPayload:
        """Parse a wire value and return as owned payload.

        This is a convenience method that ensures the result is wrapped
        in an owned RpcPayload.

        Args:
            wire_value: The wire value to parse

        Returns:
            An RpcPayload.owned() containing the parsed value
        """
        return self.parse(wire_value)
