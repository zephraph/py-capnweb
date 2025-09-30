"""Expression evaluator for Cap'n Web protocol.

This module handles the evaluation of wire expressions into actual values,
resolving imports, exports, and performing RPC calls.
"""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import Any, TYPE_CHECKING

from capnweb.error import RpcError
from capnweb.ids import ExportId, ImportId
from capnweb.types import RpcTarget
from capnweb.wire import (
    WireDate,
    WireError,
    WireExport,
    WireExpression,
    WireImport,
    WirePipeline,
    WirePromise,
    WireRemap,
)

if TYPE_CHECKING:
    from capnweb.tables import ExportTable, ImportTable


class ExpressionEvaluator:
    """Evaluates wire expressions into concrete values.

    Handles resolution of imports, exports, capability calls, and promise pipelining.
    """

    def __init__(
        self, imports: ImportTable, exports: ExportTable, is_server: bool = True
    ) -> None:
        """Initialize the evaluator.

        Args:
            imports: Import table for resolving remote references
            exports: Export table for resolving local references
            is_server: True if evaluating on server side, False for client side
        """
        self._imports = imports
        self._exports = exports
        self._is_server = is_server

    async def evaluate(
        self, expr: WireExpression, resolve_promises: bool = True
    ) -> Any:
        """Evaluate a wire expression to a concrete value.

        Args:
            expr: The wire expression to evaluate
            resolve_promises: If True, wait for promises to resolve before returning

        Returns:
            The evaluated value

        Raises:
            RpcError: If evaluation fails
        """
        match expr:
            # Handle literal values
            case None | bool() | int() | float() | str():
                return expr

            # Handle collections
            case dict():
                result = {}
                for key, value in expr.items():
                    result[key] = await self.evaluate(value, resolve_promises)
                return result

            case list():
                result = []
                for item in expr:
                    result.append(await self.evaluate(item, resolve_promises))
                return result

            # Handle special forms
            case WireError():
                # Return an RpcError instance
                from capnweb.error import ErrorCode

                return RpcError(
                    ErrorCode.INTERNAL,
                    expr.message,
                    {"type": expr.error_type, "stack": expr.stack},
                )

            case WireDate():
                # Convert to Python datetime
                from datetime import datetime

                return datetime.fromtimestamp(expr.timestamp / 1000.0, tz=UTC)

            case WireImport():
                # Resolve import from import table
                import_id = ImportId(expr.import_id)
                value = self._imports.get(import_id)

                # If it's a promise and we should resolve it, wait for it
                if resolve_promises and isinstance(value, asyncio.Future):
                    return await value

                return value

            case WireExport():
                # Resolve export from export table
                export_id = ExportId(expr.export_id)
                target = self._exports.get(export_id)

                # If it's a promise and we should resolve it, wait for it
                if resolve_promises and isinstance(target, asyncio.Future):
                    return await target

                return target

            case WirePromise():
                # Promise references always resolve to the future
                export_id = ExportId(expr.promise_id)
                target = self._exports.get(export_id)

                if not isinstance(target, asyncio.Future):
                    raise RpcError.internal(
                        f"Promise export {export_id} is not a Future"
                    )

                if resolve_promises:
                    return await target

                return target

            case WirePipeline():
                # Pipelined call - call on a capability or promise result
                # The import_id in pipeline can refer to:
                # - A local export (if we're the server and client is calling us)
                # - A remote import (if we're referencing a previous call result)

                # Try to resolve the target
                target = None

                # First try exports (for local capabilities)
                export_id = ExportId(expr.import_id)
                if self._exports.contains(export_id):
                    target = self._exports.get(export_id)
                else:
                    # Try imports (for remote references or promise results)
                    import_id = ImportId(expr.import_id)
                    if self._imports.contains(import_id):
                        target = self._imports.get(import_id)
                    else:
                        raise RpcError.not_found(
                            f"Capability/import {expr.import_id} not found"
                        )

                # If target is a promise, wait for it to resolve
                if isinstance(target, asyncio.Future):
                    target = await target

                # Navigate property path if specified, but save the last element for method call
                if expr.property_path and expr.args is None:
                    # Property access only - navigate the whole path
                    for prop_key in expr.property_path:
                        prop_name = prop_key.value
                        if isinstance(target, RpcTarget):
                            target = await target.get_property(str(prop_name))
                        elif isinstance(target, dict):
                            target = target.get(prop_name)
                        elif hasattr(target, str(prop_name)):
                            target = getattr(target, str(prop_name))
                        else:
                            raise RpcError.not_found(
                                f"Property {prop_name} not found on {type(target)}"
                            )
                    return target

                # If args are provided, make a method call
                if expr.args is not None:
                    # Evaluate arguments
                    args = await self.evaluate(expr.args, resolve_promises)
                    if not isinstance(args, list):
                        args = [args]

                    # Navigate property path except the last element (which is the method name)
                    if expr.property_path:
                        # Navigate to the object containing the method
                        for prop_key in expr.property_path[:-1]:
                            prop_name = prop_key.value
                            if isinstance(target, RpcTarget):
                                target = await target.get_property(str(prop_name))
                            elif isinstance(target, dict):
                                target = target.get(prop_name)
                            elif hasattr(target, str(prop_name)):
                                target = getattr(target, str(prop_name))
                            else:
                                raise RpcError.not_found(
                                    f"Property {prop_name} not found on {type(target)}"
                                )

                        # Call the method (last element in property path)
                        method = str(expr.property_path[-1].value)

                        if isinstance(target, RpcTarget):
                            result = await target.call(method, args)
                            return result
                        if callable(target):
                            return target(*args)
                        raise RpcError.bad_request(
                            f"Cannot call {method} on {type(target)}, not callable"
                        )
                    raise RpcError.bad_request(
                        "Pipeline call requires a method name in property path"
                    )

                return target

            case WireRemap():
                # Evaluate remap expression (implements .map() operation)
                return await self._evaluate_remap(expr, resolve_promises)

            case _:
                # Unknown expression type
                raise RpcError.bad_request(f"Unknown expression type: {type(expr)}")

    async def call_capability(
        self, export_id: ExportId, method: str, args: list[Any]
    ) -> Any:
        """Call a method on a capability.

        Args:
            export_id: The export ID of the capability
            method: The method name to call
            args: List of arguments

        Returns:
            The result of the method call

        Raises:
            RpcError: If the call fails
        """
        target = self._exports.get(export_id)

        if not isinstance(target, RpcTarget):
            raise RpcError.internal(
                f"Export {export_id} is not a capability, got {type(target)}"
            )

        return await target.call(method, args)

    async def get_capability_property(self, export_id: ExportId, property: str) -> Any:
        """Get a property from a capability.

        Args:
            export_id: The export ID of the capability
            property: The property name

        Returns:
            The property value

        Raises:
            RpcError: If the property access fails
        """
        target = self._exports.get(export_id)

        if not isinstance(target, RpcTarget):
            raise RpcError.internal(
                f"Export {export_id} is not a capability, got {type(target)}"
            )

        return await target.get_property(property)

    async def _evaluate_remap(
        self, remap: WireRemap, resolve_promises: bool = True
    ) -> Any:
        """Evaluate a remap expression (implements .map() operation).

        Args:
            remap: The remap expression
            resolve_promises: Whether to resolve promises

        Returns:
            A callable that executes the map function

        The remap creates a function that:
        - Has access to captured stubs
        - Executes a series of instructions
        - Uses a special import table where:
          - Negative IDs refer to captures (-1 = captures[0], -2 = captures[1], etc.)
          - ID 0 refers to the input value
          - Positive IDs refer to previous instruction results (1 = instructions[0], etc.)
        """
        # First, get the target value to map over
        target_import_id = ImportId(remap.import_id)
        target_value = self._imports.get(target_import_id)

        # If it's a promise, resolve it
        if resolve_promises and isinstance(target_value, asyncio.Future):
            target_value = await target_value

        # Navigate property path if specified
        if remap.property_path:
            for prop_key in remap.property_path:
                prop_name = prop_key.value
                if isinstance(target_value, RpcTarget):
                    target_value = await target_value.get_property(str(prop_name))
                elif isinstance(target_value, dict):
                    target_value = target_value.get(prop_name)
                elif hasattr(target_value, str(prop_name)):
                    target_value = getattr(target_value, str(prop_name))
                else:
                    raise RpcError.not_found(
                        f"Property {prop_name} not found on {type(target_value)}"
                    )

        # Resolve captures - convert WireCapture to actual values
        captured_values = []
        for capture in remap.captures:
            if capture.type == "import":
                import_id = ImportId(capture.id)
                value = self._imports.get(import_id)
                if resolve_promises and isinstance(value, asyncio.Future):
                    value = await value
                captured_values.append(value)
            elif capture.type == "export":
                export_id = ExportId(capture.id)
                value = self._exports.get(export_id)
                if resolve_promises and isinstance(value, asyncio.Future):
                    value = await value
                captured_values.append(value)
            else:
                raise RpcError.bad_request(f"Invalid capture type: {capture.type}")

        # Create a mapper function that executes the instructions
        async def mapper(input_value: Any) -> Any:
            """Execute the remap instructions on the input value."""
            # Create a temporary evaluator with a special import table
            # that implements the remap semantics
            remap_evaluator = RemapExpressionEvaluator(
                input_value=input_value,
                captures=captured_values,
                base_imports=self._imports,
                base_exports=self._exports,
                is_server=self._is_server,
            )

            # Execute instructions in order
            instruction_results = []
            for instruction in remap.instructions:
                result = await remap_evaluator.evaluate_instruction(
                    instruction, instruction_results
                )
                instruction_results.append(result)

            # Return the result of the last instruction
            if instruction_results:
                return instruction_results[-1]
            return input_value

        # If target_value is a list/array, map over it
        if isinstance(target_value, list):
            results = []
            for item in target_value:
                result = await mapper(item)
                results.append(result)
            return results
        # Single value - just apply the mapper
        return await mapper(target_value)


class RemapExpressionEvaluator:
    """Special evaluator for remap instruction execution.

    Implements the special import table semantics for remap:
    - Negative IDs refer to captures (-1 = captures[0], -2 = captures[1], etc.)
    - ID 0 refers to the input value
    - Positive IDs refer to previous instruction results (1 = results[0], etc.)
    """

    def __init__(
        self,
        input_value: Any,
        captures: list[Any],
        base_imports: ImportTable,
        base_exports: ExportTable,
        is_server: bool = True,
    ) -> None:
        """Initialize the remap evaluator.

        Args:
            input_value: The input value (import ID 0)
            captures: List of captured values (negative IDs)
            base_imports: Base import table for fallback
            base_exports: Base export table
            is_server: Whether evaluating on server side
        """
        self._input_value = input_value
        self._captures = captures
        self._base_imports = base_imports
        self._base_exports = base_exports
        self._is_server = is_server

    async def evaluate_instruction(
        self, expr: WireExpression, results: list[Any]
    ) -> Any:
        """Evaluate a single instruction in the remap context.

        Args:
            expr: The expression to evaluate
            results: Previous instruction results (for positive ID lookups)

        Returns:
            The evaluated value
        """
        # Handle literal values
        if expr is None or isinstance(expr, bool | int | float | str):
            return expr

        # Handle collections
        if isinstance(expr, dict):
            result = {}
            for key, value in expr.items():
                result[key] = await self.evaluate_instruction(value, results)
            return result

        if isinstance(expr, list):
            result = []
            for item in expr:
                result.append(await self.evaluate_instruction(item, results))
            return result

        # Handle WireImport with special remap semantics
        if isinstance(expr, WireImport):
            import_id = expr.import_id

            if import_id < 0:
                # Negative ID - refers to captures
                capture_index = (-import_id) - 1
                if capture_index >= len(self._captures):
                    raise RpcError.bad_request(
                        f"Capture index {capture_index} out of bounds (have {len(self._captures)} captures)"
                    )
                return self._captures[capture_index]

            if import_id == 0:
                # ID 0 - refers to input value
                return self._input_value

            # Positive ID - refers to previous instruction results
            result_index = import_id - 1
            if result_index >= len(results):
                raise RpcError.bad_request(
                    f"Result index {result_index} out of bounds (have {len(results)} results)"
                )
            return results[result_index]

        # Handle WireExport - use base export table
        if isinstance(expr, WireExport):
            export_id = ExportId(expr.export_id)
            value = self._base_exports.get(export_id)
            if isinstance(value, asyncio.Future):
                value = await value
            return value

        # Handle other wire types using standard evaluator logic
        if isinstance(expr, WireError):
            from capnweb.error import ErrorCode

            return RpcError(
                ErrorCode.INTERNAL,
                expr.message,
                {"type": expr.error_type, "stack": expr.stack},
            )

        if isinstance(expr, WireDate):
            from datetime import datetime

            return datetime.fromtimestamp(expr.timestamp / 1000.0, tz=UTC)

        if isinstance(expr, WirePipeline):
            # Pipeline calls within remap - resolve using remap import table
            # The import_id could be:
            # - Negative (capture)
            # - Zero (input)
            # - Positive (previous result)
            import_id = expr.import_id

            if import_id < 0:
                capture_index = (-import_id) - 1
                if capture_index >= len(self._captures):
                    raise RpcError.bad_request("Capture index out of bounds")
                target = self._captures[capture_index]
            elif import_id == 0:
                target = self._input_value
            else:
                result_index = import_id - 1
                if result_index >= len(results):
                    raise RpcError.bad_request("Result index out of bounds")
                target = results[result_index]

            # If target is a promise/future, resolve it
            if isinstance(target, asyncio.Future):
                target = await target

            # Handle property access and method calls
            if expr.property_path and expr.args is None:
                # Property access only
                for prop_key in expr.property_path:
                    prop_name = prop_key.value
                    if isinstance(target, RpcTarget):
                        target = await target.get_property(str(prop_name))
                    elif isinstance(target, dict):
                        target = target.get(prop_name)
                    elif hasattr(target, str(prop_name)):
                        target = getattr(target, str(prop_name))
                    else:
                        raise RpcError.not_found(f"Property {prop_name} not found")
                return target

            # Method call
            if expr.args is not None:
                args = await self.evaluate_instruction(expr.args, results)
                if not isinstance(args, list):
                    args = [args]

                if expr.property_path:
                    # Navigate to method
                    for prop_key in expr.property_path[:-1]:
                        prop_name = prop_key.value
                        if isinstance(target, RpcTarget):
                            target = await target.get_property(str(prop_name))
                        elif isinstance(target, dict):
                            target = target.get(prop_name)
                        elif hasattr(target, str(prop_name)):
                            target = getattr(target, str(prop_name))
                        else:
                            raise RpcError.not_found(f"Property {prop_name} not found")

                    method = str(expr.property_path[-1].value)
                    if isinstance(target, RpcTarget):
                        return await target.call(method, args)
                    if callable(target):
                        return target(*args)
                    raise RpcError.bad_request(f"Cannot call {method}")
                raise RpcError.bad_request("Pipeline call requires method name")

            return target

        # Unknown expression type
        raise RpcError.bad_request(f"Unknown expression type in remap: {type(expr)}")
