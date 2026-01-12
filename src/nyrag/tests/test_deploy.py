"""Tests for the deploy module."""

from datetime import date
from unittest.mock import patch

from nyrag.deploy import (
    DeployResult,
    _confirm_cluster_removal,
    _looks_like_cluster_removal_error,
    _validation_overrides_xml,
    _write_validation_overrides,
)


class TestDeployResult:
    """Tests for DeployResult dataclass."""

    def test_default_values(self):
        """Test DeployResult with default values."""
        result = DeployResult(success=True)
        assert result.success is True
        assert result.vespa_url is None
        assert result.vespa_port is None
        assert result.mtls_endpoint is None
        assert result.token_endpoint is None
        assert result.cert_path is None
        assert result.key_path is None

    def test_all_values(self):
        """Test DeployResult with all values set."""
        result = DeployResult(
            success=True,
            vespa_url="https://app.tenant.instance.z.vespa-app.cloud",
            vespa_port=443,
            mtls_endpoint="https://mtls.endpoint",
            token_endpoint="https://token.endpoint",
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem",
        )
        assert result.success is True
        assert result.vespa_url == "https://app.tenant.instance.z.vespa-app.cloud"
        assert result.vespa_port == 443
        assert result.mtls_endpoint == "https://mtls.endpoint"
        assert result.token_endpoint == "https://token.endpoint"
        assert result.cert_path == "/path/to/cert.pem"
        assert result.key_path == "/path/to/key.pem"

    def test_failed_result(self):
        """Test DeployResult for failed deployment."""
        result = DeployResult(success=False)
        assert result.success is False


class TestLooksLikeClusterRemovalError:
    """Tests for _looks_like_cluster_removal_error function."""

    def test_empty_message(self):
        """Test with empty message."""
        assert _looks_like_cluster_removal_error("") is False
        assert _looks_like_cluster_removal_error(None) is False

    def test_cluster_removal_token(self):
        """Test with cluster removal token in message."""
        message = "Error: content-cluster-removal override required"
        assert _looks_like_cluster_removal_error(message) is True

    def test_content_cluster_removed_message(self):
        """Test with content cluster removed message."""
        message = "A content cluster 'default' was removed which is not allowed"
        assert _looks_like_cluster_removal_error(message) is True

    def test_unrelated_error(self):
        """Test with unrelated error message."""
        message = "Connection timeout"
        assert _looks_like_cluster_removal_error(message) is False


class TestValidationOverridesXml:
    """Tests for _validation_overrides_xml function."""

    def test_generates_valid_xml(self):
        """Test that valid XML is generated."""
        until_date = date(2026, 1, 15)
        xml = _validation_overrides_xml(until=until_date)

        assert "<validation-overrides>" in xml
        assert "</validation-overrides>" in xml
        assert "<allow until='2026-01-15'>content-cluster-removal</allow>" in xml

    def test_different_dates(self):
        """Test with different dates."""
        until_date = date(2025, 6, 30)
        xml = _validation_overrides_xml(until=until_date)
        assert "until='2025-06-30'" in xml


class TestWriteValidationOverrides:
    """Tests for _write_validation_overrides function."""

    def test_writes_file(self, tmp_path):
        """Test that file is written correctly."""
        app_dir = tmp_path / "app"
        until_date = date(2026, 1, 15)

        _write_validation_overrides(app_dir, until=until_date)

        override_file = app_dir / "validation-overrides.xml"
        assert override_file.exists()

        content = override_file.read_text()
        assert "content-cluster-removal" in content
        assert "2026-01-15" in content

    def test_creates_directory(self, tmp_path):
        """Test that directory is created if it doesn't exist."""
        app_dir = tmp_path / "new" / "nested" / "app"
        until_date = date(2026, 1, 15)

        _write_validation_overrides(app_dir, until=until_date)

        assert app_dir.exists()
        assert (app_dir / "validation-overrides.xml").exists()


class TestConfirmClusterRemoval:
    """Tests for _confirm_cluster_removal function."""

    def test_non_interactive_returns_false(self):
        """Test that non-interactive stdin returns False."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = _confirm_cluster_removal("Error message", until=date(2026, 1, 15))
            assert result is False

    def test_interactive_yes_returns_true(self):
        """Test that interactive 'yes' returns True."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("nyrag.deploy.console") as mock_console:
                mock_console.input.return_value = "y"
                result = _confirm_cluster_removal("Error message", until=date(2026, 1, 15))
                assert result is True

    def test_interactive_no_returns_false(self):
        """Test that interactive 'no' returns False."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("nyrag.deploy.console") as mock_console:
                mock_console.input.return_value = "n"
                result = _confirm_cluster_removal("Error message", until=date(2026, 1, 15))
                assert result is False

    def test_interactive_empty_returns_false(self):
        """Test that empty input (default) returns False."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("nyrag.deploy.console") as mock_console:
                mock_console.input.return_value = ""
                result = _confirm_cluster_removal("Error message", until=date(2026, 1, 15))
                assert result is False

    def test_interactive_yes_uppercase(self):
        """Test that 'YES' (uppercase) works."""
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with patch("nyrag.deploy.console") as mock_console:
                mock_console.input.return_value = "YES"
                result = _confirm_cluster_removal("Error message", until=date(2026, 1, 15))
                assert result is True
