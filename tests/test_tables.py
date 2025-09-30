"""Tests for import and export tables."""

import asyncio

import pytest

from capnweb.error import RpcError
from capnweb.ids import ExportId, ImportId
from capnweb.tables import ExportTable, ImportTable
from capnweb.types import RpcTarget


class MockCapability(RpcTarget):
    """Mock capability for testing."""

    async def call(self, method: str, args: list) -> str:
        return f"called {method}"

    async def get_property(self, property: str) -> str:
        return f"property {property}"


class TestImportTable:
    """Tests for ImportTable."""

    def test_add_and_get(self) -> None:
        """Test adding and getting imports."""
        table = ImportTable()
        import_id = ImportId(1)

        table.add(import_id, "test value")
        value = table.get(import_id)

        assert value == "test value"

    def test_ref_counting(self) -> None:
        """Test reference counting."""
        table = ImportTable()
        import_id = ImportId(1)

        # Add twice
        table.add(import_id, "value")
        table.add(import_id, "value")

        # Release once - should still exist
        removed = table.release(import_id, 1)
        assert not removed
        assert table.contains(import_id)

        # Release again - should be removed
        removed = table.release(import_id, 1)
        assert removed
        assert not table.contains(import_id)

    def test_get_missing(self) -> None:
        """Test getting non-existent import raises error."""
        table = ImportTable()
        import_id = ImportId(999)

        with pytest.raises(RpcError) as exc_info:
            table.get(import_id)

        assert exc_info.value.code.value == "not_found"

    def test_release_missing(self) -> None:
        """Test releasing non-existent import."""
        table = ImportTable()
        import_id = ImportId(999)

        removed = table.release(import_id)
        assert not removed

    def test_contains(self) -> None:
        """Test checking if import exists."""
        table = ImportTable()
        import_id = ImportId(1)

        assert not table.contains(import_id)

        table.add(import_id, "value")
        assert table.contains(import_id)

        table.release(import_id)
        assert not table.contains(import_id)

    def test_clear(self) -> None:
        """Test clearing all imports."""
        table = ImportTable()

        table.add(ImportId(1), "value1")
        table.add(ImportId(2), "value2")

        table.clear()

        assert not table.contains(ImportId(1))
        assert not table.contains(ImportId(2))


class TestExportTable:
    """Tests for ExportTable."""

    def test_add_and_get(self) -> None:
        """Test adding and getting exports."""
        table = ExportTable()
        export_id = ExportId(-1)
        cap = MockCapability()

        table.add(export_id, cap)
        target = table.get(export_id)

        assert target is cap

    def test_add_promise(self) -> None:
        """Test adding a promise (future)."""
        table = ExportTable()
        export_id = ExportId(-1)
        future: asyncio.Future[str] = asyncio.Future()

        table.add(export_id, future)
        target = table.get(export_id)

        assert target is future

    def test_ref_counting(self) -> None:
        """Test reference counting."""
        table = ExportTable()
        export_id = ExportId(-1)
        cap = MockCapability()

        # Add twice
        table.add(export_id, cap)
        table.add(export_id, cap)

        # Release once - should still exist
        removed = table.release(export_id, 1)
        assert not removed
        assert table.contains(export_id)

        # Release again - should be removed
        removed = table.release(export_id, 1)
        assert removed
        assert not table.contains(export_id)

    def test_get_missing(self) -> None:
        """Test getting non-existent export raises error."""
        table = ExportTable()
        export_id = ExportId(-999)

        with pytest.raises(RpcError) as exc_info:
            table.get(export_id)

        assert exc_info.value.code.value == "not_found"

    def test_release_missing(self) -> None:
        """Test releasing non-existent export."""
        table = ExportTable()
        export_id = ExportId(-999)

        removed = table.release(export_id)
        assert not removed

    def test_contains(self) -> None:
        """Test checking if export exists."""
        table = ExportTable()
        export_id = ExportId(-1)
        cap = MockCapability()

        assert not table.contains(export_id)

        table.add(export_id, cap)
        assert table.contains(export_id)

        table.release(export_id)
        assert not table.contains(export_id)

    def test_clear(self) -> None:
        """Test clearing all exports."""
        table = ExportTable()

        table.add(ExportId(-1), MockCapability())
        table.add(ExportId(-2), MockCapability())

        table.clear()

        assert not table.contains(ExportId(-1))
        assert not table.contains(ExportId(-2))
