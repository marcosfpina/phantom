"""
Integration tests for the Phantom CLI.

Uses typer.testing.CliRunner — no subprocess spawned.
"""

from typer.testing import CliRunner

from phantom.cli.main import app

runner = CliRunner()


class TestVersionCommand:
    def test_version_exits_0(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0

    def test_version_contains_phantom(self):
        result = runner.invoke(app, ["version"])
        assert "Phantom" in result.stdout or "PHANTOM" in result.stdout

    def test_version_contains_version_number(self):
        result = runner.invoke(app, ["version"])
        assert "0.1.0" in result.stdout


class TestExtractCommand:
    def test_extract_missing_input_fails(self):
        result = runner.invoke(app, ["extract", "-o", "/tmp/out.jsonl"])
        assert result.exit_code != 0

    def test_extract_missing_output_fails(self):
        result = runner.invoke(app, ["extract", "-i", "/tmp/input"])
        assert result.exit_code != 0


class TestAnalyzeCommand:
    def test_analyze_missing_file_fails(self):
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code != 0


class TestClassifyCommand:
    def test_classify_missing_dir_fails(self):
        result = runner.invoke(app, ["classify"])
        assert result.exit_code != 0


class TestHelpOutput:
    def test_root_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "extract" in result.stdout
        assert "analyze" in result.stdout
        assert "classify" in result.stdout

    def test_rag_help(self):
        result = runner.invoke(app, ["rag", "--help"])
        assert result.exit_code == 0
        assert "query" in result.stdout
        assert "ingest" in result.stdout

    def test_tools_help(self):
        result = runner.invoke(app, ["tools", "--help"])
        assert result.exit_code == 0
        assert "vram" in result.stdout

    def test_api_help(self):
        result = runner.invoke(app, ["api", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.stdout
