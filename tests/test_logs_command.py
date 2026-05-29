from __future__ import annotations

from click.testing import CliRunner

from ouro.commands.logs import logs_command


def test_logs_view_filters_level(tmp_path) -> None:
    log_file = tmp_path / "ouro.log"
    log_file.write_text(
        "\n".join(
            [
                '{"level":"INFO","message":"ok"}',
                '{"level":"ERROR","message":"boom"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        logs_command,
        ["view", "--path", str(log_file), "--level", "ERROR", "--lines", "50"],
    )
    assert result.exit_code == 0
    assert "boom" in result.output
    assert "ok" not in result.output


def test_logs_analyze_prints_counts(tmp_path) -> None:
    log_file = tmp_path / "ouro.log"
    log_file.write_text(
        "\n".join(
            [
                '{"level":"INFO","message":"a"}',
                '{"level":"INFO","message":"b"}',
                '{"level":"ERROR","message":"c"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(logs_command, ["analyze", "--path", str(log_file)])
    assert result.exit_code == 0
    assert "INFO count" in result.output
    assert "ERROR count" in result.output
    assert "2" in result.output


def test_logs_clear_all_truncates_current_file(tmp_path) -> None:
    log_file = tmp_path / "ouro.log"
    rotated = tmp_path / "ouro.log.1"
    log_file.write_text("line\n", encoding="utf-8")
    rotated.write_text("old\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        logs_command,
        ["clear", "--path", str(log_file), "--all", "--yes", "--older-than", "0"],
    )
    assert result.exit_code == 0
    assert log_file.read_text(encoding="utf-8") == ""
    assert not rotated.exists()


def test_logs_rotate_creates_timestamped_copy(tmp_path) -> None:
    log_file = tmp_path / "ouro.log"
    log_file.write_text("hello\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(logs_command, ["rotate", "--path", str(log_file)])
    assert result.exit_code == 0
    rotated_files = list(tmp_path.glob("ouro.log.*"))
    assert rotated_files
    assert log_file.read_text(encoding="utf-8") == ""


def test_logs_view_rejects_unsupported_path(tmp_path) -> None:
    other_file = tmp_path / "notes.txt"
    other_file.write_text("secret\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(logs_command, ["view", "--path", str(other_file)])
    assert result.exit_code != 0
    assert "Unsupported log path" in result.output


def test_logs_rotate_requires_primary_log_file(tmp_path) -> None:
    rotated = tmp_path / "ouro.log.1"
    rotated.write_text("line\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(logs_command, ["rotate", "--path", str(rotated)])
    assert result.exit_code != 0
    assert "primary ouro.log" in result.output


def test_logs_view_accepts_module_session_log_path(tmp_path) -> None:
    log_file = tmp_path / "prez_logs_20260520_0146.log"
    log_file.write_text('{"level":"ERROR","message":"module boom"}\n', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(logs_command, ["view", "--path", str(log_file), "--lines", "10"])
    assert result.exit_code == 0
    assert "module boom" in result.output
