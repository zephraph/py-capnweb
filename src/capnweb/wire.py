"""Wire protocol implementation for Cap'n Web.

Implements the JSON-based wire format as specified in the protocol:
https://github.com/cloudflare/capnweb/blob/main/protocol.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PropertyKey:
    """A property key, either string or numeric."""

    value: str | int

    def to_json(self) -> str | int:
        """Convert to JSON representation."""
        return self.value

    @staticmethod
    def from_json(value: Any) -> PropertyKey:
        """Parse from JSON value."""
        if isinstance(value, str):
            return PropertyKey(value)
        if isinstance(value, int):
            return PropertyKey(value)
        raise ValueError(f"Invalid property key: {value}")


# Wire Expressions


@dataclass(frozen=True)
class WireError:
    """Error expression: ["error", type, message, stack?, data?]

    The data field allows encoding custom properties that have been added to the error,
    enabling richer error information to be transmitted across the RPC boundary.
    """

    error_type: str
    message: str
    stack: str | None = None
    data: dict[str, Any] | None = None

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        result: list[Any] = ["error", self.error_type, self.message]
        if self.stack is not None:
            result.append(self.stack)
            # If we have data but no stack, we need to add null for stack
            if self.data is not None:
                result.append(self.data)
        elif self.data is not None:
            # No stack but we have data - add null for stack position
            result.extend((None, self.data))
        return result

    @staticmethod
    def from_json(arr: list[Any]) -> WireError:
        """Parse from JSON array."""
        if len(arr) < 3:
            raise ValueError("Error expression requires at least 3 elements")
        error_type = arr[1]
        message = arr[2]
        stack = arr[3] if len(arr) > 3 else None
        data = arr[4] if len(arr) > 4 and isinstance(arr[4], dict) else None
        return WireError(error_type, message, stack, data)


@dataclass(frozen=True)
class WireImport:
    """Import expression: ["import", id]"""

    import_id: int

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["import", self.import_id]

    @staticmethod
    def from_json(arr: list[Any]) -> WireImport:
        """Parse from JSON array."""
        if len(arr) != 2:
            raise ValueError("Import expression requires exactly 2 elements")
        return WireImport(arr[1])


@dataclass(frozen=True)
class WireExport:
    """Export expression: ["export", id]"""

    export_id: int
    is_promise: bool = False

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["export", self.export_id]

    @staticmethod
    def from_json(arr: list[Any]) -> WireExport:
        """Parse from JSON array."""
        if len(arr) != 2:
            raise ValueError("Export expression requires exactly 2 elements")
        return WireExport(arr[1])


@dataclass(frozen=True)
class WirePromise:
    """Promise expression: ["promise", id]"""

    promise_id: int

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["promise", self.promise_id]

    @staticmethod
    def from_json(arr: list[Any]) -> WirePromise:
        """Parse from JSON array."""
        if len(arr) != 2:
            raise ValueError("Promise expression requires exactly 2 elements")
        return WirePromise(arr[1])


@dataclass(frozen=True)
class WirePipeline:
    """Pipeline expression: ["pipeline", import_id, property_path?, args?]"""

    import_id: int
    property_path: list[PropertyKey] | None = None
    args: WireExpression | None = None

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        result: list[Any] = ["pipeline", self.import_id]
        if self.property_path is not None:
            result.append([pk.to_json() for pk in self.property_path])
        else:
            result.append(None)
        if self.args is not None:
            result.append(wire_expression_to_json(self.args))
        return result

    @staticmethod
    def from_json(arr: list[Any]) -> WirePipeline:
        """Parse from JSON array."""
        if len(arr) < 2:
            raise ValueError("Pipeline expression requires at least 2 elements")
        import_id = arr[1]
        property_path = (
            [PropertyKey.from_json(k) for k in arr[2]]
            if len(arr) > 2 and arr[2]
            else None
        )
        args = wire_expression_from_json(arr[3]) if len(arr) > 3 else None
        return WirePipeline(import_id, property_path, args)


@dataclass(frozen=True)
class WireDate:
    """Date expression: ["date", timestamp]"""

    timestamp: float

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["date", self.timestamp]

    @staticmethod
    def from_json(arr: list[Any]) -> WireDate:
        """Parse from JSON array."""
        if len(arr) != 2:
            raise ValueError("Date expression requires exactly 2 elements")
        return WireDate(arr[1])


@dataclass(frozen=True)
class WireCapture:
    """Capture expression for remap: ["import", importId] or ["export", exportId]"""

    type: str  # "import" or "export"
    id: int

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return [self.type, self.id]

    @staticmethod
    def from_json(arr: list[Any]) -> WireCapture:
        """Parse from JSON array."""
        if len(arr) != 2 or arr[0] not in ("import", "export"):
            raise ValueError("Capture requires ['import'|'export', id]")
        return WireCapture(arr[0], arr[1])


@dataclass(frozen=True)
class WireRemap:
    """Remap expression: ["remap", importId, propertyPath, captures, instructions]"""

    import_id: int
    property_path: list[PropertyKey] | None
    captures: list[WireCapture]
    instructions: list[Any]  # List of WireExpression

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        path_json = (
            [pk.to_json() for pk in self.property_path] if self.property_path else None
        )
        captures_json = [c.to_json() for c in self.captures]
        instructions_json = [
            wire_expression_to_json(instr) for instr in self.instructions
        ]
        return ["remap", self.import_id, path_json, captures_json, instructions_json]

    @staticmethod
    def from_json(arr: list[Any]) -> WireRemap:
        """Parse from JSON array."""
        if len(arr) != 5:
            raise ValueError("Remap expression requires exactly 5 elements")
        import_id = arr[1]
        property_path = (
            [PropertyKey.from_json(pk) for pk in arr[2]] if arr[2] is not None else None
        )
        captures = [WireCapture.from_json(c) for c in arr[3]]
        instructions = [wire_expression_from_json(instr) for instr in arr[4]]
        return WireRemap(import_id, property_path, captures, instructions)


# Wire expression type union
WireExpression = (
    None
    | bool
    | int
    | float
    | str
    | list[Any]
    | dict[str, Any]
    | WireError
    | WireImport
    | WireExport
    | WirePromise
    | WirePipeline
    | WireDate
    | WireRemap
)


def wire_expression_from_json(value: Any) -> WireExpression:
    """Parse a wire expression from JSON."""
    if value is None or isinstance(value, bool | int | float | str):
        return value

    if isinstance(value, dict):
        return {k: wire_expression_from_json(v) for k, v in value.items()}

    if isinstance(value, list):
        if not value:
            return value

        # Check for escaped literal arrays: [[...]]
        # If the array has exactly one element and that element is also an array,
        # and the inner array starts with a string, it's an escaped literal
        if (
            len(value) == 1
            and isinstance(value[0], list)
            and value[0]
            and isinstance(value[0][0], str)
        ):
            # This is an escaped literal array, unwrap it
            return [wire_expression_from_json(item) for item in value[0]]

        # Check for special forms (arrays starting with a string)
        if isinstance(value[0], str):
            tag = value[0]
            match tag:
                case "error":
                    return WireError.from_json(value)
                case "import":
                    return WireImport.from_json(value)
                case "export":
                    return WireExport.from_json(value)
                case "promise":
                    return WirePromise.from_json(value)
                case "pipeline":
                    return WirePipeline.from_json(value)
                case "date":
                    return WireDate.from_json(value)
                case "remap":
                    return WireRemap.from_json(value)
                case _:
                    # Regular array, parse elements
                    return [wire_expression_from_json(item) for item in value]
        else:
            # Regular array
            return [wire_expression_from_json(item) for item in value]

    raise ValueError(f"Invalid wire expression: {value}")


def wire_expression_to_json(expr: WireExpression) -> Any:
    """Convert a wire expression to JSON."""
    match expr:
        case None | bool() | int() | float() | str():
            return expr

        case dict():
            return {k: wire_expression_to_json(v) for k, v in expr.items()}

        case list():
            # Check if this is a literal array that needs escaping
            # (starts with a string that could be confused with a special form)
            serialized = [wire_expression_to_json(item) for item in expr]
            if serialized and isinstance(serialized[0], str):
                # Wrap in an extra array to escape it
                return [serialized]
            return serialized

        case (
            WireError()
            | WireImport()
            | WireExport()
            | WirePromise()
            | WirePipeline()
            | WireDate()
            | WireRemap()
        ):
            return expr.to_json()

        case _:
            raise ValueError(f"Invalid wire expression: {expr}")


# Wire Messages


@dataclass(frozen=True)
class WirePush:
    """Push message: ["push", expression]"""

    expression: WireExpression

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["push", wire_expression_to_json(self.expression)]


@dataclass(frozen=True)
class WirePull:
    """Pull message: ["pull", import_id]"""

    import_id: int

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["pull", self.import_id]


@dataclass(frozen=True)
class WireResolve:
    """Resolve message: ["resolve", export_id, value]"""

    export_id: int
    value: WireExpression

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["resolve", self.export_id, wire_expression_to_json(self.value)]


@dataclass(frozen=True)
class WireReject:
    """Reject message: ["reject", export_id, error]"""

    export_id: int
    error: WireExpression

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["reject", self.export_id, wire_expression_to_json(self.error)]


@dataclass(frozen=True)
class WireRelease:
    """Release message: ["release", importId, refcount]"""

    import_id: int
    refcount: int

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["release", self.import_id, self.refcount]


@dataclass(frozen=True)
class WireAbort:
    """Abort message: ["abort", error]"""

    error: WireExpression

    def to_json(self) -> list[Any]:
        """Convert to JSON array."""
        return ["abort", wire_expression_to_json(self.error)]


WireMessage = WirePush | WirePull | WireResolve | WireReject | WireRelease | WireAbort


def parse_wire_message(data: str) -> WireMessage:
    """Parse a wire message from JSON string."""
    arr = json.loads(data)
    if not isinstance(arr, list) or not arr:
        raise ValueError("Wire message must be a non-empty array")

    msg_type = arr[0]
    if not isinstance(msg_type, str):
        raise ValueError("Message type must be a string")

    match msg_type:
        case "push":
            if len(arr) != 2:
                raise ValueError("Push message requires exactly 2 elements")
            return WirePush(wire_expression_from_json(arr[1]))

        case "pull":
            if len(arr) != 2:
                raise ValueError("Pull message requires exactly 2 elements")
            return WirePull(arr[1])

        case "resolve":
            if len(arr) != 3:
                raise ValueError("Resolve message requires exactly 3 elements")
            return WireResolve(arr[1], wire_expression_from_json(arr[2]))

        case "reject":
            if len(arr) != 3:
                raise ValueError("Reject message requires exactly 3 elements")
            return WireReject(arr[1], wire_expression_from_json(arr[2]))

        case "release":
            if len(arr) != 3:
                raise ValueError("Release message requires exactly 3 elements")
            return WireRelease(arr[1], arr[2])

        case "abort":
            if len(arr) != 2:
                raise ValueError("Abort message requires exactly 2 elements")
            return WireAbort(wire_expression_from_json(arr[1]))

        case _:
            raise ValueError(f"Unknown message type: {msg_type}")


def serialize_wire_message(msg: WireMessage) -> str:
    """Serialize a wire message to JSON string."""
    return json.dumps(msg.to_json())


def parse_wire_batch(data: str) -> list[WireMessage]:
    """Parse a batch of newline-delimited wire messages."""
    lines = data.strip().split("\n")
    return [parse_wire_message(line) for line in lines if line.strip()]


def serialize_wire_batch(messages: list[WireMessage]) -> str:
    """Serialize a batch of wire messages to newline-delimited JSON."""
    return "\n".join(serialize_wire_message(msg) for msg in messages)
