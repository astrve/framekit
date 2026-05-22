"""Tests for dry-run mode functionality."""

from __future__ import annotations

from framekit.core.dry_run import (
    DryRunOperation,
    DryRunRecorder,
    dry_run_mode,
    is_dry_run,
    record_operation,
)


class TestDryRunOperation:
    """Test dry-run operation dataclass."""

    def test_operation_creation(self):
        """Test creating a dry-run operation."""
        op = DryRunOperation(
            operation_type="delete",
            target="/tmp/test.mkv",
            description="Delete test file",
        )
        assert op.operation_type == "delete"
        assert op.target == "/tmp/test.mkv"
        assert op.description == "Delete test file"
        assert op.metadata == {}

    def test_operation_with_metadata(self):
        """Test operation with metadata."""
        op = DryRunOperation(
            operation_type="modify",
            target="/tmp/test.mkv",
            description="Modify file",
            metadata={"size_before": 1000, "size_after": 500},
        )
        assert op.metadata["size_before"] == 1000
        assert op.metadata["size_after"] == 500

    def test_operation_to_dict(self):
        """Test converting operation to dict."""
        op = DryRunOperation(
            operation_type="create",
            target="/tmp/new.mkv",
            description="Create new file",
        )
        data = op.to_dict()
        assert data["operation_type"] == "create"
        assert data["target"] == "/tmp/new.mkv"


class TestDryRunRecorder:
    """Test dry-run recorder."""

    def test_recorder_initialization(self):
        """Test recorder initialization."""
        recorder = DryRunRecorder()
        assert not recorder.is_active
        assert len(recorder.operations) == 0

    def test_recorder_activation(self):
        """Test activating recorder."""
        recorder = DryRunRecorder()
        recorder.activate()
        assert recorder.is_active

    def test_recorder_deactivation(self):
        """Test deactivating recorder."""
        recorder = DryRunRecorder()
        recorder.activate()
        recorder.deactivate()
        assert not recorder.is_active

    def test_record_operation(self):
        """Test recording an operation."""
        recorder = DryRunRecorder()
        recorder.activate()

        recorder.record(
            operation_type="delete",
            target="/tmp/test.mkv",
            description="Delete file",
        )

        assert len(recorder.operations) == 1
        assert recorder.operations[0].operation_type == "delete"

    def test_record_operation_inactive(self):
        """Test recording when inactive does nothing."""
        recorder = DryRunRecorder()
        # Not activated

        recorder.record(
            operation_type="delete",
            target="/tmp/test.mkv",
            description="Delete file",
        )

        assert len(recorder.operations) == 0

    def test_record_multiple_operations(self):
        """Test recording multiple operations."""
        recorder = DryRunRecorder()
        recorder.activate()

        recorder.record("create", "/tmp/file1.mkv", "Create file 1")
        recorder.record("modify", "/tmp/file2.mkv", "Modify file 2")
        recorder.record("delete", "/tmp/file3.mkv", "Delete file 3")

        assert len(recorder.operations) == 3

    def test_clear_operations(self):
        """Test clearing operations."""
        recorder = DryRunRecorder()
        recorder.activate()
        recorder.record("delete", "/tmp/test.mkv", "Delete")

        assert len(recorder.operations) == 1
        recorder.clear()
        assert len(recorder.operations) == 0

    def test_get_summary(self):
        """Test getting operation summary."""
        recorder = DryRunRecorder()
        recorder.activate()

        recorder.record("create", "/tmp/file1.mkv", "Create")
        recorder.record("modify", "/tmp/file2.mkv", "Modify")
        recorder.record("delete", "/tmp/file3.mkv", "Delete")
        recorder.record("delete", "/tmp/file4.mkv", "Delete")

        summary = recorder.get_summary()
        assert summary["total"] == 4
        assert summary["by_type"]["create"] == 1
        assert summary["by_type"]["modify"] == 1
        assert summary["by_type"]["delete"] == 2

    def test_format_summary(self):
        """Test formatting summary for display."""
        recorder = DryRunRecorder()
        recorder.activate()

        recorder.record("create", "/tmp/file1.mkv", "Create file")
        recorder.record("delete", "/tmp/file2.mkv", "Delete file")

        formatted = recorder.format_summary()
        assert "Dry-Run Summary" in formatted
        assert "create" in formatted.lower()
        assert "delete" in formatted.lower()
        assert "/tmp/file1.mkv" in formatted
        assert "/tmp/file2.mkv" in formatted

    def test_format_operations(self):
        """Test formatting operations list."""
        recorder = DryRunRecorder()
        recorder.activate()

        recorder.record(
            "modify",
            "/tmp/test.mkv",
            "Modify file",
            metadata={"size": 1000},
        )

        formatted = recorder.format_operations()
        assert "modify" in formatted.lower()
        assert "/tmp/test.mkv" in formatted
        assert "Modify file" in formatted


class TestDryRunContext:
    """Test dry-run context manager."""

    def test_context_manager_basic(self):
        """Test basic context manager usage."""
        assert not is_dry_run()

        with dry_run_mode() as recorder:
            assert is_dry_run()
            assert isinstance(recorder, DryRunRecorder)

        assert not is_dry_run()

    def test_context_manager_records_operations(self):
        """Test context manager records operations."""
        with dry_run_mode() as recorder:
            record_operation("delete", "/tmp/test.mkv", "Delete file")
            record_operation("create", "/tmp/new.mkv", "Create file")

        assert len(recorder.operations) == 2

    def test_context_manager_cleanup(self):
        """Test context manager cleans up on exit."""
        with dry_run_mode():
            assert is_dry_run()
            record_operation("delete", "/tmp/test.mkv", "Delete")

        # After exit, dry-run should be disabled
        assert not is_dry_run()

        # Recording should not work outside context
        record_operation("delete", "/tmp/test2.mkv", "Delete")
        # This should not raise, just do nothing

    def test_context_manager_exception_handling(self):
        """Test context manager handles exceptions."""
        try:
            with dry_run_mode():
                assert is_dry_run()
                raise ValueError("Test error")
        except ValueError:
            pass

        # Dry-run should be disabled even after exception
        assert not is_dry_run()

    def test_nested_context_not_supported(self):
        """Test nested dry-run contexts."""
        with dry_run_mode():
            assert is_dry_run()
            # Nested context should work but use same recorder
            with dry_run_mode():
                assert is_dry_run()


class TestDryRunGlobalFunctions:
    """Test global dry-run functions."""

    def test_is_dry_run_default(self):
        """Test is_dry_run returns False by default."""
        assert not is_dry_run()

    def test_record_operation_global(self):
        """Test global record_operation function."""
        with dry_run_mode() as recorder:
            record_operation(
                "delete",
                "/tmp/test.mkv",
                "Delete file",
                metadata={"size": 1000},
            )

            assert len(recorder.operations) == 1
            assert recorder.operations[0].metadata["size"] == 1000

    def test_record_operation_outside_context(self):
        """Test recording outside context does nothing."""
        # Should not raise, just do nothing
        record_operation("delete", "/tmp/test.mkv", "Delete")
        assert not is_dry_run()


class TestDryRunIntegration:
    """Test dry-run integration scenarios."""

    def test_file_operations_dry_run(self):
        """Test simulating file operations in dry-run."""
        with dry_run_mode() as recorder:
            # Simulate file operations
            record_operation(
                "delete",
                "/tmp/old.mkv",
                "Delete old file",
                metadata={"size": 1000},
            )
            record_operation(
                "create",
                "/tmp/new.mkv",
                "Create new file",
                metadata={"size": 500},
            )
            record_operation(
                "modify",
                "/tmp/existing.mkv",
                "Modify existing file",
                metadata={"size_before": 1000, "size_after": 800},
            )

        summary = recorder.get_summary()
        assert summary["total"] == 3
        assert summary["by_type"]["delete"] == 1
        assert summary["by_type"]["create"] == 1
        assert summary["by_type"]["modify"] == 1

    def test_batch_operations_dry_run(self):
        """Test batch operations in dry-run."""
        files = [f"/tmp/file{i}.mkv" for i in range(10)]

        with dry_run_mode() as recorder:
            for file in files:
                record_operation("process", file, f"Process {file}")

        assert len(recorder.operations) == 10

    def test_conditional_dry_run(self):
        """Test conditional operations based on dry-run mode."""

        def process_file(path: str, dry_run: bool = False) -> None:
            if dry_run:
                record_operation("process", path, f"Would process {path}")
            else:
                # Actual processing would happen here
                pass

        with dry_run_mode() as recorder:
            process_file("/tmp/test.mkv", dry_run=True)

        assert len(recorder.operations) == 1

    def test_dry_run_with_size_estimates(self):
        """Test dry-run with size estimates."""
        with dry_run_mode() as recorder:
            # Simulate compression operations
            files = [
                ("/tmp/file1.mkv", 1000, 500),
                ("/tmp/file2.mkv", 2000, 1000),
                ("/tmp/file3.mkv", 1500, 750),
            ]

            for path, size_before, size_after in files:
                record_operation(
                    "compress",
                    path,
                    f"Compress {path}",
                    metadata={
                        "size_before": size_before,
                        "size_after": size_after,
                        "savings": size_before - size_after,
                    },
                )

        # Calculate total savings: (1000-500) + (2000-1000) + (1500-750) = 500 + 1000 + 750 = 2250
        total_savings = sum(op.metadata.get("savings", 0) for op in recorder.operations)
        assert total_savings == 2250


# Made with Bob
