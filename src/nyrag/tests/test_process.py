"""Tests for the process module."""

import json
from datetime import datetime

import pytest

from nyrag.process import load_processed_locations, save_to_jsonl


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


class TestLoadProcessedLocations:
    """Tests for load_processed_locations function."""

    def test_empty_file(self, temp_output_dir):
        """Test loading from empty file."""
        jsonl_file = temp_output_dir / "data.jsonl"
        jsonl_file.touch()

        result = load_processed_locations(jsonl_file)
        assert result == set()

    def test_file_not_exists(self, temp_output_dir):
        """Test loading from non-existent file."""
        jsonl_file = temp_output_dir / "nonexistent.jsonl"

        result = load_processed_locations(jsonl_file)
        assert result == set()

    def test_load_locations(self, temp_output_dir):
        """Test loading locations from JSONL file."""
        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"loc": "https://example.com/page1", "content": "test"}) + "\n")
            f.write(json.dumps({"loc": "https://example.com/page2", "content": "test"}) + "\n")
            f.write(json.dumps({"loc": "/path/to/file.txt", "content": "test"}) + "\n")

        result = load_processed_locations(jsonl_file)
        assert len(result) == 3
        assert "https://example.com/page1" in result
        assert "https://example.com/page2" in result
        assert "/path/to/file.txt" in result

    def test_skip_lines_without_loc(self, temp_output_dir):
        """Test that lines without loc field are skipped."""
        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"loc": "https://example.com/page1", "content": "test"}) + "\n")
            f.write(json.dumps({"content": "test without loc"}) + "\n")
            f.write(json.dumps({"loc": "https://example.com/page2", "content": "test"}) + "\n")

        result = load_processed_locations(jsonl_file)
        assert len(result) == 2

    def test_skip_empty_lines(self, temp_output_dir):
        """Test that empty lines are skipped."""
        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"loc": "https://example.com/page1", "content": "test"}) + "\n")
            f.write("\n")
            f.write("   \n")
            f.write(json.dumps({"loc": "https://example.com/page2", "content": "test"}) + "\n")

        result = load_processed_locations(jsonl_file)
        assert len(result) == 2

    def test_handle_invalid_json(self, temp_output_dir):
        """Test handling of invalid JSON lines (should log warning and return empty)."""
        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "w") as f:
            f.write("not valid json\n")

        result = load_processed_locations(jsonl_file)
        assert result == set()


class TestSaveToJsonl:
    """Tests for save_to_jsonl function."""

    def test_save_single_record(self, temp_output_dir):
        """Test saving a single record."""
        save_to_jsonl(
            loc="https://example.com/page",
            content="# Test Content",
            title="Test Page",
            output_path=temp_output_dir,
        )

        jsonl_file = temp_output_dir / "data.jsonl"
        assert jsonl_file.exists()

        with open(jsonl_file, "r") as f:
            line = f.readline()
            data = json.loads(line)

        assert data["loc"] == "https://example.com/page"
        assert data["content"] == "# Test Content"
        assert data["title"] == "Test Page"
        assert "timestamp" in data

    def test_save_multiple_records(self, temp_output_dir):
        """Test saving multiple records (appending)."""
        save_to_jsonl(
            loc="https://example.com/page1",
            content="Content 1",
            title="Page 1",
            output_path=temp_output_dir,
        )
        save_to_jsonl(
            loc="https://example.com/page2",
            content="Content 2",
            title="Page 2",
            output_path=temp_output_dir,
        )

        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "r") as f:
            lines = f.readlines()

        assert len(lines) == 2
        assert json.loads(lines[0])["loc"] == "https://example.com/page1"
        assert json.loads(lines[1])["loc"] == "https://example.com/page2"

    def test_custom_output_file(self, temp_output_dir):
        """Test saving with custom output file name."""
        save_to_jsonl(
            loc="https://example.com/page",
            content="Content",
            title="Title",
            output_path=temp_output_dir,
            output_file="custom.jsonl",
        )

        custom_file = temp_output_dir / "custom.jsonl"
        assert custom_file.exists()

        with open(custom_file, "r") as f:
            data = json.loads(f.readline())
        assert data["loc"] == "https://example.com/page"

    def test_creates_output_directory(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        output_dir = tmp_path / "new" / "nested" / "dir"

        save_to_jsonl(
            loc="https://example.com/page",
            content="Content",
            title="Title",
            output_path=output_dir,
        )

        assert output_dir.exists()
        assert (output_dir / "data.jsonl").exists()

    def test_unicode_content(self, temp_output_dir):
        """Test saving content with unicode characters."""
        save_to_jsonl(
            loc="https://example.com/日本語",
            content="Unicode content: 你好世界 🎉 émojis",
            title="日本語ページ",
            output_path=temp_output_dir,
        )

        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "r", encoding="utf-8") as f:
            data = json.loads(f.readline())

        assert data["loc"] == "https://example.com/日本語"
        assert "你好世界" in data["content"]
        assert "🎉" in data["content"]
        assert data["title"] == "日本語ページ"

    def test_timestamp_format(self, temp_output_dir):
        """Test that timestamp is in ISO format."""
        save_to_jsonl(
            loc="https://example.com/page",
            content="Content",
            title="Title",
            output_path=temp_output_dir,
        )

        jsonl_file = temp_output_dir / "data.jsonl"
        with open(jsonl_file, "r") as f:
            data = json.loads(f.readline())

        # Verify timestamp can be parsed as ISO format
        timestamp = data["timestamp"]
        parsed = datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime)
