"""Tests for import and export ID management."""

import threading

from capnweb.ids import ExportId, IdAllocator, ImportId


class TestImportId:
    """Tests for ImportId."""

    def test_main_id(self) -> None:
        """Test main interface ID creation."""
        import_id = ImportId.main()
        assert import_id.value == 0
        assert import_id.is_main()

    def test_local_id(self) -> None:
        """Test local (positive) ID detection."""
        import_id = ImportId(5)
        assert import_id.is_local()
        assert not import_id.is_remote()
        assert not import_id.is_main()

    def test_remote_id(self) -> None:
        """Test remote (negative) ID detection."""
        import_id = ImportId(-3)
        assert import_id.is_remote()
        assert not import_id.is_local()
        assert not import_id.is_main()

    def test_to_export_id(self) -> None:
        """Test conversion to export ID."""
        import_id = ImportId(5)
        export_id = import_id.to_export_id()
        assert export_id.value == -5

    def test_str_representation(self) -> None:
        """Test string representation."""
        import_id = ImportId(42)
        assert str(import_id) == "Import#42"


class TestExportId:
    """Tests for ExportId."""

    def test_main_id(self) -> None:
        """Test main interface ID creation."""
        export_id = ExportId.main()
        assert export_id.value == 0
        assert export_id.is_main()

    def test_local_id(self) -> None:
        """Test local (negative) ID detection."""
        export_id = ExportId(-2)
        assert export_id.is_local()
        assert not export_id.is_remote()
        assert not export_id.is_main()

    def test_remote_id(self) -> None:
        """Test remote (positive) ID detection."""
        export_id = ExportId(4)
        assert export_id.is_remote()
        assert not export_id.is_local()
        assert not export_id.is_main()

    def test_to_import_id(self) -> None:
        """Test conversion to import ID."""
        export_id = ExportId(-5)
        import_id = export_id.to_import_id()
        assert import_id.value == 5

    def test_str_representation(self) -> None:
        """Test string representation."""
        export_id = ExportId(-17)
        assert str(export_id) == "Export#-17"


class TestIdAllocator:
    """Tests for IdAllocator."""

    def test_allocate_import(self) -> None:
        """Test import ID allocation."""
        allocator = IdAllocator()

        import1 = allocator.allocate_import()
        import2 = allocator.allocate_import()

        assert import1.value == 1
        assert import2.value == 2

    def test_allocate_export(self) -> None:
        """Test export ID allocation."""
        allocator = IdAllocator()

        export1 = allocator.allocate_export()
        export2 = allocator.allocate_export()

        assert export1.value == -1
        assert export2.value == -2

    def test_register_remote_import(self) -> None:
        """Test registering remote import IDs."""
        allocator = IdAllocator()
        remote_import = allocator.register_remote_import(-5)
        assert remote_import.value == -5

    def test_register_remote_export(self) -> None:
        """Test registering remote export IDs."""
        allocator = IdAllocator()
        remote_export = allocator.register_remote_export(7)
        assert remote_export.value == 7

    def test_thread_safety(self) -> None:
        """Test thread-safe allocation."""

        allocator = IdAllocator()
        results: list[ImportId] = []
        lock = threading.Lock()

        def allocate_ids() -> None:
            for _ in range(100):
                import_id = allocator.allocate_import()
                with lock:
                    results.append(import_id)

        threads = [threading.Thread(target=allocate_ids) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Check that all IDs are unique
        values = [r.value for r in results]
        assert len(values) == len(set(values))
        assert len(values) == 1000
