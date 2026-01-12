"""Tests for the vespa_cli module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nyrag.vespa_cli import (
    _classify_api_key,
    _parse_application_id,
    _pick_str,
    clear_vespa_cli_cache,
    get_vespa_cli_cloud_config,
    get_vespa_cloud_secret_token,
    is_vespa_cloud_authenticated,
    load_vespa_cli_config,
    set_vespa_target_cloud,
    vespa_auth_login,
)


@pytest.fixture(autouse=True)
def _isolate_cli_home(tmp_path, monkeypatch):
    """Isolate tests from the user's home directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    clear_vespa_cli_cache()
    yield
    clear_vespa_cli_cache()


class TestLoadVespaCliConfig:
    """Tests for load_vespa_cli_config function."""

    def test_no_config_file(self):
        """Test when no config file exists."""
        result = load_vespa_cli_config()
        assert result is None

    def test_load_cli_config_json(self):
        """Test loading config from .vespa/cli/config.json."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {"current_target": "test-target", "targets": {}}
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = load_vespa_cli_config()
        assert result is not None
        assert result["current_target"] == "test-target"

    def test_load_config_json(self):
        """Test loading config from .vespa/config.json (fallback location)."""
        config_path = Path.home() / ".vespa" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {"current_target": "fallback-target"}
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = load_vespa_cli_config()
        assert result is not None
        assert result["current_target"] == "fallback-target"

    def test_invalid_json_file(self):
        """Test when config file contains invalid JSON."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("not valid json")
        clear_vespa_cli_cache()

        result = load_vespa_cli_config()
        assert result is None


class TestGetVespaCliCloudConfig:
    """Tests for get_vespa_cli_cloud_config function."""

    def test_empty_config(self):
        """Test with no config."""
        result = get_vespa_cli_cloud_config()
        assert result == {}

    def test_full_cloud_config(self):
        """Test with complete cloud config."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "current_target": "my-tenant.my-app.prod",
            "targets": {
                "my-tenant.my-app.prod": {
                    "type": "cloud",
                    "endpoint": "https://my-app.my-tenant.prod.z.vespa-app.cloud:443",
                    "tenant": "my-tenant",
                    "application": "my-app",
                    "instance": "prod",
                    "auth": {
                        "apiKeyPath": "/home/user/.vespa/key.pem",
                        "cert": "/path/to/cert.pem",
                        "key": "/path/to/key.pem",
                        "caCert": "/path/to/ca.pem",
                    },
                }
            },
        }
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = get_vespa_cli_cloud_config()
        assert result["tenant"] == "my-tenant"
        assert result["application"] == "my-app"
        assert result["instance"] == "prod"
        assert result["api_key_path"] == "/home/user/.vespa/key.pem"
        assert result["tls_client_cert"] == "/path/to/cert.pem"
        assert result["tls_client_key"] == "/path/to/key.pem"
        assert result["tls_ca_cert"] == "/path/to/ca.pem"
        assert result["endpoint"] == "https://my-app.my-tenant.prod.z.vespa-app.cloud:443"

    def test_inline_target_config(self):
        """Test with inline target config (no targets dict)."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "cloud": {
                "tenant": "inline-tenant",
                "application": "inline-app",
                "instance": "inline-instance",
            }
        }
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = get_vespa_cli_cloud_config()
        assert result["tenant"] == "inline-tenant"
        assert result["application"] == "inline-app"
        assert result["instance"] == "inline-instance"

    def test_single_target_auto_select(self):
        """Test that single target is auto-selected when no current_target."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "targets": {
                "only-target": {
                    "tenant": "only-tenant",
                    "application": "only-app",
                    "instance": "default",
                }
            }
        }
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = get_vespa_cli_cloud_config()
        assert result["tenant"] == "only-tenant"
        assert result["application"] == "only-app"

    def test_application_id_parsing(self):
        """Test that application ID is parsed from target name."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_data = {
            "current_target": "parsed-tenant.parsed-app.parsed-instance",
            "targets": {
                "parsed-tenant.parsed-app.parsed-instance": {
                    "type": "cloud",
                }
            },
        }
        config_path.write_text(json.dumps(config_data))
        clear_vespa_cli_cache()

        result = get_vespa_cli_cloud_config()
        assert result["tenant"] == "parsed-tenant"
        assert result["application"] == "parsed-app"
        assert result["instance"] == "parsed-instance"


class TestParseApplicationId:
    """Tests for _parse_application_id helper function."""

    def test_dot_separator(self):
        """Test parsing with dot separator."""
        tenant, app, instance = _parse_application_id("tenant.app.instance")
        assert tenant == "tenant"
        assert app == "app"
        assert instance == "instance"

    def test_colon_separator(self):
        """Test parsing with colon separator."""
        tenant, app, instance = _parse_application_id("tenant:app:instance")
        assert tenant == "tenant"
        assert app == "app"
        assert instance == "instance"

    def test_slash_separator(self):
        """Test parsing with slash separator."""
        tenant, app, instance = _parse_application_id("tenant/app/instance")
        assert tenant == "tenant"
        assert app == "app"
        assert instance == "instance"

    def test_empty_string(self):
        """Test parsing empty string."""
        tenant, app, instance = _parse_application_id("")
        assert tenant is None
        assert app is None
        assert instance is None

    def test_none_input(self):
        """Test parsing None input."""
        tenant, app, instance = _parse_application_id(None)
        assert tenant is None
        assert app is None
        assert instance is None

    def test_insufficient_parts(self):
        """Test parsing with insufficient parts."""
        tenant, app, instance = _parse_application_id("only.two")
        assert tenant is None
        assert app is None
        assert instance is None


class TestPickStr:
    """Tests for _pick_str helper function."""

    def test_picks_first_matching_key(self):
        """Test that first matching key is returned."""
        mapping = {"key1": "value1", "key2": "value2"}
        result = _pick_str(mapping, "key1", "key2")
        assert result == "value1"

    def test_skips_non_string_values(self):
        """Test that non-string values are skipped."""
        mapping = {"key1": 123, "key2": "value2"}
        result = _pick_str(mapping, "key1", "key2")
        assert result == "value2"

    def test_skips_empty_strings(self):
        """Test that empty strings are skipped."""
        mapping = {"key1": "   ", "key2": "value2"}
        result = _pick_str(mapping, "key1", "key2")
        assert result == "value2"

    def test_returns_none_for_empty_mapping(self):
        """Test that None is returned for empty mapping."""
        result = _pick_str({}, "key1")
        assert result is None

    def test_returns_none_for_none_mapping(self):
        """Test that None is returned for None mapping."""
        result = _pick_str(None, "key1")
        assert result is None


class TestClassifyApiKey:
    """Tests for _classify_api_key helper function."""

    def test_multiline_value_is_key(self):
        """Test that multiline value is classified as key content."""
        path, key = _classify_api_key("-----BEGIN PRIVATE KEY-----\nkey content\n-----END PRIVATE KEY-----")
        assert path is None
        assert "BEGIN PRIVATE KEY" in key

    def test_path_value_with_slash(self):
        """Test that value with slash is classified as path."""
        path, key = _classify_api_key("/home/user/key.pem")
        assert path == "/home/user/key.pem"
        assert key is None

    def test_path_value_with_pem_extension(self):
        """Test that value ending in .pem is classified as path."""
        path, key = _classify_api_key("my-key.pem")
        assert path is not None  # Will check if file exists or treat as path
        assert key is None or key == "my-key.pem"  # Depends on file existence

    def test_tilde_expansion(self):
        """Test that ~ is expanded in path."""
        path, key = _classify_api_key("~/my-key.pem")
        assert path is not None
        assert "~" not in path  # Tilde should be expanded

    def test_none_input(self):
        """Test with None input."""
        path, key = _classify_api_key(None)
        assert path is None
        assert key is None

    def test_empty_input(self):
        """Test with empty input."""
        path, key = _classify_api_key("")
        assert path is None
        assert key is None


class TestIsVespaCloudAuthenticated:
    """Tests for is_vespa_cloud_authenticated function."""

    def test_not_authenticated_no_files(self):
        """Test that not authenticated when no auth files exist."""
        result = is_vespa_cloud_authenticated()
        assert result is False

    def test_authenticated_with_auth_json(self):
        """Test authentication check with auth.json file."""
        auth_path = Path.home() / ".vespa" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text(json.dumps({"access_token": "valid-token"}))

        result = is_vespa_cloud_authenticated()
        assert result is True

    def test_authenticated_with_api_key(self):
        """Test authentication check with API key in config."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "current_target": "target",
                    "targets": {"target": {"auth": {"apiKeyPath": "/path/to/key.pem"}}},
                }
            )
        )
        clear_vespa_cli_cache()

        result = is_vespa_cloud_authenticated()
        assert result is True


class TestGetVespaCloudSecretToken:
    """Tests for get_vespa_cloud_secret_token function."""

    def test_from_environment(self):
        """Test getting secret token from environment variable."""
        with patch.dict("os.environ", {"VESPA_CLOUD_SECRET_TOKEN": "env-token"}):
            result = get_vespa_cloud_secret_token()
            assert result == "env-token"

    def test_no_token(self):
        """Test when no token is available."""
        with patch.dict("os.environ", {}, clear=True):
            result = get_vespa_cloud_secret_token()
            assert result is None

    def test_from_cli_config(self):
        """Test getting secret token from CLI config."""
        config_path = Path.home() / ".vespa" / "cli" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps({"secret_token": "config-token"}))
        clear_vespa_cli_cache()

        with patch.dict("os.environ", {}, clear=True):
            result = get_vespa_cloud_secret_token()
            assert result == "config-token"


class TestSetVespaTargetCloud:
    """Tests for set_vespa_target_cloud function."""

    def test_vespa_cli_not_installed(self):
        """Test when vespa CLI is not installed."""
        with patch("shutil.which", return_value=None):
            result = set_vespa_target_cloud()
            assert result is False

    def test_successful_set_target(self):
        """Test successful setting of cloud target."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/vespa"):
            with patch("subprocess.run", return_value=mock_result):
                result = set_vespa_target_cloud()
                assert result is True

    def test_failed_set_target(self):
        """Test failed setting of cloud target."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("shutil.which", return_value="/usr/bin/vespa"):
            with patch("subprocess.run", return_value=mock_result):
                result = set_vespa_target_cloud()
                assert result is False

    def test_exception_during_set_target(self):
        """Test exception during setting of cloud target."""
        with patch("shutil.which", return_value="/usr/bin/vespa"):
            with patch("subprocess.run", side_effect=Exception("test error")):
                result = set_vespa_target_cloud()
                assert result is False


class TestVespaAuthLogin:
    """Tests for vespa_auth_login function."""

    def test_vespa_cli_not_installed(self):
        """Test when vespa CLI is not installed."""
        with patch("shutil.which", return_value=None):
            result = vespa_auth_login()
            assert result is False

    def test_successful_auth(self):
        """Test successful authentication."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("shutil.which", return_value="/usr/bin/vespa"):
            with patch("subprocess.run", return_value=mock_result):
                result = vespa_auth_login()
                assert result is True

    def test_failed_auth(self):
        """Test failed authentication."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("shutil.which", return_value="/usr/bin/vespa"):
            with patch("subprocess.run", return_value=mock_result):
                result = vespa_auth_login()
                assert result is False
