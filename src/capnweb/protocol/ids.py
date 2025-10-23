"""Import and Export ID management for Cap'n Web protocol.

Import/Export IDs use a bidirectional numbering scheme:
- Positive IDs (1, 2, 3...) are chosen by the importing side
- Negative IDs (-1, -2, -3...) are chosen by the exporting side
- ID 0 is reserved for the "main" interface
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ImportId:
    """Import ID - represents an entry in the import table.

    Positive IDs are chosen by the importing side.
    Negative IDs are chosen by the exporting side.
    ID 0 is reserved for the "main" interface.
    """

    value: int

    @staticmethod
    def main() -> ImportId:
        """Create the main interface ID (0)."""
        return ImportId(0)

    def is_main(self) -> bool:
        """Check if this is the main interface ID."""
        return self.value == 0

    def is_local(self) -> bool:
        """Check if this ID was allocated locally (positive)."""
        return self.value > 0

    def is_remote(self) -> bool:
        """Check if this ID was allocated remotely (negative)."""
        return self.value < 0

    def to_export_id(self) -> ExportId:
        """Convert to the corresponding export ID on the other side."""
        return ExportId(-self.value)

    def __str__(self) -> str:
        return f"Import#{self.value}"


@dataclass(frozen=True)
class ExportId:
    """Export ID - represents an entry in the export table.

    Negative IDs are chosen by the exporting side.
    Positive IDs are chosen by the importing side.
    ID 0 is reserved for the "main" interface.
    """

    value: int

    @staticmethod
    def main() -> ExportId:
        """Create the main interface ID (0)."""
        return ExportId(0)

    def is_main(self) -> bool:
        """Check if this is the main interface ID."""
        return self.value == 0

    def is_local(self) -> bool:
        """Check if this ID was allocated locally (negative)."""
        return self.value < 0

    def is_remote(self) -> bool:
        """Check if this ID was allocated remotely (positive)."""
        return self.value > 0

    def to_import_id(self) -> ImportId:
        """Convert to the corresponding import ID on the other side."""
        return ImportId(-self.value)

    def __str__(self) -> str:
        return f"Export#{self.value}"


class IdAllocator:
    """Thread-safe allocator for import and export IDs.

    Manages the sequential allocation of IDs:
    - Local imports: positive (1, 2, 3, ...)
    - Local exports: negative (-1, -2, -3, ...)
    """

    def __init__(self) -> None:
        self._next_positive: int = 1
        self._next_negative: int = -1
        self._lock: Final = threading.Lock()

    def allocate_import(self) -> ImportId:
        """Allocate a new local import ID (positive)."""
        with self._lock:
            import_id = ImportId(self._next_positive)
            self._next_positive += 1
            return import_id

    def allocate_export(self) -> ExportId:
        """Allocate a new local export ID (negative)."""
        with self._lock:
            export_id = ExportId(self._next_negative)
            self._next_negative -= 1
            return export_id

    def register_remote_import(self, value: int) -> ImportId:
        """Register a remote import ID (negative from our perspective)."""
        return ImportId(value)

    def register_remote_export(self, value: int) -> ExportId:
        """Register a remote export ID (positive from our perspective)."""
        return ExportId(value)
