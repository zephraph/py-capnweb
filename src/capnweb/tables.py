"""Import and Export table management for Cap'n Web protocol."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from capnweb.error import RpcError

if TYPE_CHECKING:
    from capnweb.ids import ExportId, ImportId
    from capnweb.types import RpcTarget


@dataclass
class ImportEntry:
    """Entry in the import table."""

    import_id: ImportId
    # For imports, we store the capability reference or promise
    value: Any
    ref_count: int = 1


@dataclass
class ExportEntry:
    """Entry in the export table."""

    export_id: ExportId
    # For exports, we store the actual capability or promise future
    target: RpcTarget | asyncio.Future[Any]
    ref_count: int = 1


class ImportTable:
    """Import table for managing imported capabilities and promises."""

    def __init__(self) -> None:
        self._entries: dict[ImportId, ImportEntry] = {}

    def add(self, import_id: ImportId, value: Any) -> None:
        """Add or increment reference count for an import."""
        if import_id in self._entries:
            self._entries[import_id].ref_count += 1
        else:
            self._entries[import_id] = ImportEntry(import_id, value)

    def get(self, import_id: ImportId) -> Any:
        """Get the value for an import ID."""
        entry = self._entries.get(import_id)
        if entry is None:
            msg = f"Import {import_id} not found"
            raise RpcError.not_found(msg)
        return entry.value

    def release(self, import_id: ImportId, ref_count: int = 1) -> bool:
        """Release an import. Returns True if the entry was removed."""
        entry = self._entries.get(import_id)
        if entry is None:
            return False

        entry.ref_count -= ref_count
        if entry.ref_count <= 0:
            del self._entries[import_id]
            return True
        return False

    def contains(self, import_id: ImportId) -> bool:
        """Check if an import ID exists."""
        return import_id in self._entries

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def snapshot(self) -> dict[int, tuple[Any, int]]:
        """Create a snapshot of the import table state.

        Returns:
            Dictionary mapping import_id -> (value, ref_count)
        """
        return {
            entry.import_id.value: (entry.value, entry.ref_count)
            for entry in self._entries.values()
        }

    def restore(self, snapshot: dict[int, tuple[Any, int]]) -> None:
        """Restore import table from a snapshot.

        Args:
            snapshot: Dictionary mapping import_id -> (value, ref_count)
        """
        from capnweb.ids import ImportId

        self._entries.clear()
        for import_id_val, (value, ref_count) in snapshot.items():
            import_id = ImportId(import_id_val)
            self._entries[import_id] = ImportEntry(import_id, value, ref_count)


class ExportTable:
    """Export table for managing exported capabilities and promises."""

    def __init__(self) -> None:
        self._entries: dict[ExportId, ExportEntry] = {}

    def add(self, export_id: ExportId, target: RpcTarget | asyncio.Future[Any]) -> None:
        """Add or increment reference count for an export."""
        if export_id in self._entries:
            self._entries[export_id].ref_count += 1
        else:
            self._entries[export_id] = ExportEntry(export_id, target)

    def get(self, export_id: ExportId) -> RpcTarget | asyncio.Future[Any]:
        """Get the target for an export ID."""
        entry = self._entries.get(export_id)
        if entry is None:
            msg = f"Export {export_id} not found"
            raise RpcError.not_found(msg)
        return entry.target

    def release(self, export_id: ExportId, ref_count: int = 1) -> bool:
        """Release an export. Returns True if the entry was removed."""
        entry = self._entries.get(export_id)
        if entry is None:
            return False

        entry.ref_count -= ref_count
        if entry.ref_count <= 0:
            del self._entries[export_id]
            return True
        return False

    def contains(self, export_id: ExportId) -> bool:
        """Check if an export ID exists."""
        return export_id in self._entries

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()

    def snapshot(self) -> dict[int, tuple[Any, int]]:
        """Create a snapshot of the export table state.

        Returns:
            Dictionary mapping export_id -> (target, ref_count)

        Note:
            Futures/promises are not serialized and will be lost on restoration.
            This is acceptable for HTTP batch (stateless) but may need enhancement
            for WebSocket sessions.
        """
        return {
            entry.export_id.value: (entry.target, entry.ref_count)
            for entry in self._entries.values()
            if not isinstance(entry.target, asyncio.Future)  # Skip promises
        }

    def restore(self, snapshot: dict[int, tuple[Any, int]]) -> None:
        """Restore export table from a snapshot.

        Args:
            snapshot: Dictionary mapping export_id -> (target, ref_count)
        """
        from capnweb.ids import ExportId

        self._entries.clear()
        for export_id_val, (target, ref_count) in snapshot.items():
            export_id = ExportId(export_id_val)
            self._entries[export_id] = ExportEntry(export_id, target, ref_count)
