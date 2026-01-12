"""Tests for the vespa_docker module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nyrag.vespa_docker import (
    ComposeVespaDocker,
    _resolve_application_root,
    _resolve_vespa_port,
    _resolve_vespa_url,
    _use_compose_deployer,
    resolve_vespa_docker_class,
)


class TestUseComposeDeployer:
    """Tests for _use_compose_deployer function."""

    def test_compose_mode_enabled(self):
        """Test when NYRAG_VESPA_COMPOSE=1 is set."""
        with patch.dict(os.environ, {"NYRAG_VESPA_COMPOSE": "1"}):
            assert _use_compose_deployer() is True

    def test_compose_mode_disabled(self):
        """Test when NYRAG_VESPA_COMPOSE is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _use_compose_deployer() is False

    def test_compose_mode_other_value(self):
        """Test when NYRAG_VESPA_COMPOSE has other value."""
        with patch.dict(os.environ, {"NYRAG_VESPA_COMPOSE": "0"}):
            assert _use_compose_deployer() is False

        with patch.dict(os.environ, {"NYRAG_VESPA_COMPOSE": "true"}):
            assert _use_compose_deployer() is False


class TestResolveVespaDockerClass:
    """Tests for resolve_vespa_docker_class function."""

    def test_compose_deployer_selected(self):
        """Test that ComposeVespaDocker is returned when compose mode is enabled."""
        with patch.dict(os.environ, {"NYRAG_VESPA_COMPOSE": "1"}):
            cls = resolve_vespa_docker_class()
            assert cls is ComposeVespaDocker

    def test_standard_deployer_selected(self):
        """Test that standard VespaDocker is returned when compose mode is disabled."""
        with patch.dict(os.environ, {}, clear=True):
            cls = resolve_vespa_docker_class()
            # Should return the standard VespaDocker from vespa.deployment
            assert cls is not ComposeVespaDocker


class TestResolveVespaUrl:
    """Tests for _resolve_vespa_url function."""

    def test_explicit_url(self):
        """Test with explicit URL provided."""
        result = _resolve_vespa_url("https://vespa.example.com", "http://localhost:19071")
        assert result == "https://vespa.example.com"

    def test_trailing_slash_stripped(self):
        """Test that trailing slash is stripped."""
        result = _resolve_vespa_url("https://vespa.example.com/", "http://localhost:19071")
        assert result == "https://vespa.example.com"

    def test_infer_from_configserver(self):
        """Test inferring URL from config server URL."""
        result = _resolve_vespa_url(None, "http://vespa-configserver:19071")
        assert result == "http://vespa-configserver"

    def test_infer_from_localhost(self):
        """Test inferring URL from localhost config server."""
        result = _resolve_vespa_url(None, "http://localhost:19071")
        assert result == "http://localhost"

    def test_infer_https_scheme(self):
        """Test inferring HTTPS scheme from config server."""
        result = _resolve_vespa_url(None, "https://vespa-configserver:19071")
        assert result == "https://vespa-configserver"


class TestResolveVespaPort:
    """Tests for _resolve_vespa_port function."""

    def test_explicit_port(self):
        """Test with explicit port provided."""
        result = _resolve_vespa_port(9090)
        assert result == 9090

    def test_default_port(self):
        """Test default port when not provided."""
        result = _resolve_vespa_port(None)
        assert result == 8080  # DEFAULT_VESPA_LOCAL_PORT


class TestResolveApplicationRoot:
    """Tests for _resolve_application_root function."""

    def test_primary_root(self):
        """Test with primary application root provided."""
        result = _resolve_application_root("/app/root", "/fallback/root")
        assert result == Path("/app/root")

    def test_fallback_root(self):
        """Test with fallback application root."""
        result = _resolve_application_root(None, "/fallback/root")
        assert result == Path("/fallback/root")

    def test_no_root(self):
        """Test with no application root."""
        result = _resolve_application_root(None, None)
        assert result is None

    def test_empty_strings(self):
        """Test with empty strings."""
        result = _resolve_application_root("", "")
        assert result is None

    def test_whitespace_stripped(self):
        """Test that whitespace is stripped."""
        result = _resolve_application_root("  /app/root  ", None)
        assert result == Path("/app/root")


class TestComposeVespaDocker:
    """Tests for ComposeVespaDocker class."""

    def test_initialization_defaults(self):
        """Test initialization with default values."""
        deployer = ComposeVespaDocker()
        assert deployer.cfgsrv_url == "http://localhost:19071"
        assert deployer.url == "http://localhost"
        assert deployer.port == 8080

    def test_initialization_custom_values(self):
        """Test initialization with custom values."""
        deployer = ComposeVespaDocker(
            cfgsrv_url="http://vespa-configserver:19071",
            vespa_url="http://vespa:8080",
            vespa_port=9090,
        )
        assert deployer.cfgsrv_url == "http://vespa-configserver:19071"
        assert deployer.url == "http://vespa:8080"
        assert deployer.port == 9090

    def test_initialization_with_image(self):
        """Test initialization with docker image."""
        deployer = ComposeVespaDocker(image="vespaengine/vespa:8.0.0")
        assert deployer.container_image == "vespaengine/vespa:8.0.0"

    def test_initialization_with_docker_image(self):
        """Test initialization with docker_image parameter."""
        deployer = ComposeVespaDocker(docker_image="vespaengine/vespa:latest")
        assert deployer.container_image == "vespaengine/vespa:latest"

    def test_initialization_trailing_slash_stripped(self):
        """Test that trailing slash is stripped from config server URL."""
        deployer = ComposeVespaDocker(cfgsrv_url="http://localhost:19071/")
        assert deployer.cfgsrv_url == "http://localhost:19071"

    def test_deploy_requires_package_or_root(self):
        """Test that deploy requires application_package or application_root."""
        deployer = ComposeVespaDocker()

        with pytest.raises(
            ValueError,
            match="Either application_package or application_root must be set",
        ):
            deployer.deploy()

    def test_application_package_attribute_aliases(self):
        """Test that application_package is available under different attribute names."""
        mock_package = MagicMock()
        deployer = ComposeVespaDocker(application_package=mock_package)

        assert deployer.application_package is mock_package
        assert deployer.app_package is mock_package
        assert deployer.package is mock_package
