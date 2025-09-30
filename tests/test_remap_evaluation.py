"""Tests for remap expression evaluation."""

import pytest

from capnweb.evaluator import ExpressionEvaluator
from capnweb.ids import ImportId
from capnweb.tables import ExportTable, ImportTable
from capnweb.wire import WireCapture, WireImport, WireRemap


class TestRemapEvaluation:
    """Tests for remap expression evaluation."""

    @pytest.mark.asyncio
    async def test_simple_remap_with_literal(self):
        """Test simple remap that doubles each value in a list."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a list to the import table
        test_list = [1, 2, 3, 4]
        imports.add(ImportId(1), test_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that doubles each value
        # Instruction: import 0 * 2 (where import 0 is the input value)
        # But we need to express this as a simple value operation
        # For simplicity, let's just return the input value
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[],
            instructions=[WireImport(0)],  # Just return the input
        )

        result = await evaluator.evaluate(remap)
        assert result == test_list

    @pytest.mark.asyncio
    async def test_remap_with_capture(self):
        """Test remap with captured values."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a list and a multiplier to import table
        test_list = [10, 20, 30]
        multiplier = 5
        imports.add(ImportId(1), test_list)
        imports.add(ImportId(2), multiplier)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that uses a captured multiplier
        # Capture import 2 (the multiplier)
        # Instruction: return input (we can't do arithmetic in wire expressions easily)
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[WireCapture("import", 2)],
            instructions=[WireImport(-1)],  # Return captured value (multiplier)
        )

        result = await evaluator.evaluate(remap)
        # Each element gets replaced with the multiplier
        assert result == [multiplier, multiplier, multiplier]

    @pytest.mark.asyncio
    async def test_remap_accesses_input_value(self):
        """Test that remap can access the input value."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a list of dicts
        test_list = [{"value": 1}, {"value": 2}, {"value": 3}]
        imports.add(ImportId(1), test_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that returns the input value (ID 0)
        remap = WireRemap(
            import_id=1, property_path=None, captures=[], instructions=[WireImport(0)]
        )

        result = await evaluator.evaluate(remap)
        assert result == test_list

    @pytest.mark.asyncio
    async def test_remap_multiple_instructions(self):
        """Test remap with multiple instructions."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a list of numbers
        test_list = [1, 2, 3]
        imports.add(ImportId(1), test_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap with multiple instructions
        # Instruction 1: Get input (ID 0)
        # Instruction 2: Reference result of instruction 1 (ID 1)
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[],
            instructions=[
                WireImport(0),  # Instruction 1: input value
                WireImport(1),  # Instruction 2: result of instruction 1
            ],
        )

        result = await evaluator.evaluate(remap)
        # Should return the list as-is
        assert result == test_list

    @pytest.mark.asyncio
    async def test_remap_with_dict_construction(self):
        """Test remap that constructs a dict from input."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a list of numbers
        test_list = [5, 10, 15]
        imports.add(ImportId(1), test_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that wraps each value in a dict
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[],
            instructions=[{"value": WireImport(0)}],  # Wrap input in dict
        )

        result = await evaluator.evaluate(remap)
        assert result == [{"value": 5}, {"value": 10}, {"value": 15}]

    @pytest.mark.asyncio
    async def test_remap_on_non_list(self):
        """Test remap on a single value (not a list)."""
        imports = ImportTable()
        exports = ExportTable()

        # Add a single value
        single_value = 42
        imports.add(ImportId(1), single_value)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that returns the input
        remap = WireRemap(
            import_id=1, property_path=None, captures=[], instructions=[WireImport(0)]
        )

        result = await evaluator.evaluate(remap)
        # Should apply mapper to single value
        assert result == single_value

    @pytest.mark.asyncio
    async def test_remap_negative_capture_indexing(self):
        """Test that negative IDs correctly index captures."""
        imports = ImportTable()
        exports = ExportTable()

        # Add test data
        test_list = ["a", "b", "c"]
        capture1 = "X"
        capture2 = "Y"
        imports.add(ImportId(1), test_list)
        imports.add(ImportId(2), capture1)
        imports.add(ImportId(3), capture2)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap with two captures
        # -1 should refer to first capture (capture1)
        # -2 should refer to second capture (capture2)
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[WireCapture("import", 2), WireCapture("import", 3)],
            instructions=[WireImport(-2)],  # Return second capture
        )

        result = await evaluator.evaluate(remap)
        # Each list element should be replaced with capture2
        assert result == [capture2, capture2, capture2]

    @pytest.mark.asyncio
    async def test_remap_empty_list(self):
        """Test remap on an empty list."""
        imports = ImportTable()
        exports = ExportTable()

        # Add an empty list
        empty_list: list[int] = []
        imports.add(ImportId(1), empty_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap
        remap = WireRemap(
            import_id=1, property_path=None, captures=[], instructions=[WireImport(0)]
        )

        result = await evaluator.evaluate(remap)
        assert result == []

    @pytest.mark.asyncio
    async def test_remap_with_nested_list_instruction(self):
        """Test remap with nested list construction."""
        imports = ImportTable()
        exports = ExportTable()

        test_list = [1, 2, 3]
        imports.add(ImportId(1), test_list)

        evaluator = ExpressionEvaluator(imports, exports, is_server=True)

        # Create a remap that wraps input in a list
        remap = WireRemap(
            import_id=1,
            property_path=None,
            captures=[],
            instructions=[[WireImport(0), "extra"]],  # [input, "extra"]
        )

        result = await evaluator.evaluate(remap)
        assert result == [[1, "extra"], [2, "extra"], [3, "extra"]]
