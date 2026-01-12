"""Tests for the config module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from nyrag.config import Config, CrawlParams, DeployConfig, DocParams, LLMConfig, RAGParams
from nyrag.defaults import (
    DEFAULT_DEPLOY_MODE,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_LLM_MODEL,
    DEFAULT_VESPA_CLOUD_INSTANCE,
    DEFAULT_VESPA_CLOUD_PORT,
    DEFAULT_VESPA_LOCAL_PORT,
    DEFAULT_VESPA_TLS_VERIFY,
    DEFAULT_VESPA_URL,
)
from nyrag.vespa_cli import clear_vespa_cli_cache


@pytest.fixture(autouse=True)
def _isolate_cli_home(tmp_path, monkeypatch):
    """Isolate tests from the user's home directory."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    clear_vespa_cli_cache()
    yield
    clear_vespa_cli_cache()


class TestCrawlParams:
    """Tests for CrawlParams model."""

    def test_default_values(self):
        """Test default parameter values."""
        params = CrawlParams()
        assert params.respect_robots_txt is True
        assert params.aggressive_crawl is False
        assert params.follow_subdomains is True
        assert params.strict_mode is False
        assert params.user_agent_type == "chrome"
        assert params.custom_user_agent is None
        assert params.allowed_domains is None

    def test_custom_values(self):
        """Test custom parameter values."""
        params = CrawlParams(
            respect_robots_txt=False,
            aggressive_crawl=True,
            user_agent_type="firefox",
            allowed_domains=["example.com"],
        )
        assert params.respect_robots_txt is False
        assert params.aggressive_crawl is True
        assert params.user_agent_type == "firefox"
        assert params.allowed_domains == ["example.com"]


class TestDocParams:
    """Tests for DocParams model."""

    def test_default_values(self):
        """Test default parameter values."""
        params = DocParams()
        assert params.recursive is True
        assert params.include_hidden is False
        assert params.follow_symlinks is False
        assert params.max_file_size_mb is None
        assert params.file_extensions is None

    def test_custom_values(self):
        """Test custom parameter values."""
        params = DocParams(
            recursive=False,
            include_hidden=True,
            max_file_size_mb=10.0,
            file_extensions=[".pdf", ".txt"],
        )
        assert params.recursive is False
        assert params.include_hidden is True
        assert params.max_file_size_mb == 10.0
        assert params.file_extensions == [".pdf", ".txt"]


class TestConfig:
    """Tests for Config model."""

    def test_web_mode_config(self):
        """Test configuration for web mode."""
        config = Config(name="test_web", mode="web", start_loc="https://example.com")
        assert config.name == "test_web"
        assert config.mode == "web"
        assert config.start_loc == "https://example.com"
        assert config.exclude is None
        assert isinstance(config.crawl_params, CrawlParams)
        assert isinstance(config.doc_params, DocParams)

    def test_docs_mode_config(self):
        """Test configuration for docs mode."""
        config = Config(name="test_docs", mode="docs", start_loc="/path/to/docs")
        assert config.name == "test_docs"
        assert config.mode == "docs"
        assert config.start_loc == "/path/to/docs"

    def test_doc_mode_alias(self):
        """Test that 'docs' mode works."""
        config = Config(name="test", mode="docs", start_loc="/path")
        assert config.mode == "docs"

    def test_invalid_mode(self):
        """Test that invalid mode raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Config(name="test", mode="invalid", start_loc="/path")

    def test_with_exclude(self):
        """Test configuration with exclude patterns."""
        config = Config(
            name="test",
            mode="web",
            start_loc="https://example.com",
            exclude=["*/admin/*", "*/login"],
        )
        assert config.exclude == ["*/admin/*", "*/login"]

    def test_with_rag_params(self):
        """Test configuration with RAG parameters."""
        rag_params = RAGParams(
            embedding_model="custom-model",
            chunk_size=512,
            chunk_overlap=50,
        )
        config = Config(
            name="test",
            mode="web",
            start_loc="https://example.com",
            rag_params=rag_params,
        )
        assert config.rag_params.embedding_model == "custom-model"
        assert config.rag_params.chunk_size == 512

    def test_from_yaml(self):
        """Test loading configuration from YAML file."""
        yaml_content = """
name: test_yaml
mode: web
start_loc: https://example.com
exclude:
  - "*/admin/*"
  - "*/login"
rag_params:
  embedding_model: custom-model
  chunk_size: 512
crawl_params:
  respect_robots_txt: false
  user_agent_type: firefox
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            config = Config.from_yaml(temp_path)
            assert config.name == "test_yaml"
            assert config.mode == "web"
            assert config.start_loc == "https://example.com"
            assert config.exclude == ["*/admin/*", "*/login"]
            assert config.rag_params.embedding_model == "custom-model"
            assert config.crawl_params.respect_robots_txt is False
            assert config.crawl_params.user_agent_type == "firefox"
        finally:
            Path(temp_path).unlink()

    def test_get_schema_name(self):
        """Test schema name generation."""
        config = Config(name="my-test-app", mode="web", start_loc="https://example.com")
        assert config.get_schema_name() == "nyragmytestapp"

    def test_get_app_package_name(self):
        """Test app package name generation."""
        config = Config(name="my-test-app", mode="web", start_loc="https://example.com")
        assert config.get_app_package_name() == "nyragmytestapp"

    def test_get_schema_params(self):
        """Test schema parameters extraction."""
        config = Config(
            name="test",
            mode="web",
            start_loc="https://example.com",
            rag_params=RAGParams(
                embedding_dim=512,
                chunk_size=2048,
                distance_metric="euclidean",
            ),
        )
        schema_params = config.get_schema_params()
        assert schema_params["embedding_dim"] == 512
        assert schema_params["chunk_size"] == 2048
        assert schema_params["distance_metric"] == "euclidean"

    def test_default_schema_params(self):
        """Test default schema parameters when using defaults."""
        config = Config(name="test", mode="web", start_loc="https://example.com")
        schema_params = config.get_schema_params()
        # Defaults are now filled in from RAGParams model
        assert schema_params["embedding_dim"] == 384
        assert schema_params["chunk_size"] == 1024
        assert schema_params["distance_metric"] == "angular"


class TestLLMConfig:
    """Tests for LLMConfig model."""

    def test_default_values(self):
        """Test default LLM configuration."""
        config = LLMConfig()
        assert config.base_url == DEFAULT_LLM_BASE_URL
        assert config.model == DEFAULT_LLM_MODEL
        assert config.api_key is None

    def test_custom_values(self):
        """Test custom LLM configuration."""
        config = LLMConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4",
            api_key="test-key",
        )
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"


class TestDeployConfig:
    """Tests for DeployConfig model."""

    def test_default_values(self):
        """Test default deploy configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig()
            assert config.deploy_mode == DEFAULT_DEPLOY_MODE
            assert config.cloud_tenant is None
            assert config.cloud_application is None
            assert config.cloud_instance is None

    def test_is_cloud_mode(self):
        """Test is_cloud_mode method."""
        cloud_config = DeployConfig(deploy_mode="cloud")
        local_config = DeployConfig(deploy_mode="local")
        assert cloud_config.is_cloud_mode() is True
        assert local_config.is_cloud_mode() is False

    def test_is_local_mode(self):
        """Test is_local_mode method."""
        cloud_config = DeployConfig(deploy_mode="cloud")
        local_config = DeployConfig(deploy_mode="local")
        assert cloud_config.is_local_mode() is False
        assert local_config.is_local_mode() is True

    def test_get_vespa_url_default(self):
        """Test default Vespa URL for local mode."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="local")
            assert config.get_vespa_url() == DEFAULT_VESPA_URL

    def test_get_vespa_url_from_env(self):
        """Test Vespa URL from environment variable."""
        with patch.dict(os.environ, {"VESPA_URL": "http://custom-vespa:8080"}):
            config = DeployConfig(deploy_mode="local")
            assert config.get_vespa_url() == "http://custom-vespa:8080"

    def test_get_vespa_port_local_default(self):
        """Test default Vespa port for local mode."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="local")
            assert config.get_vespa_port() == DEFAULT_VESPA_LOCAL_PORT

    def test_get_vespa_port_cloud_default(self):
        """Test default Vespa port for cloud mode."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="cloud")
            assert config.get_vespa_port() == DEFAULT_VESPA_CLOUD_PORT

    def test_get_vespa_port_from_env(self):
        """Test Vespa port from environment variable."""
        with patch.dict(os.environ, {"VESPA_PORT": "9090"}):
            config = DeployConfig(deploy_mode="local")
            assert config.get_vespa_port() == 9090

    def test_get_cloud_tenant_from_config(self):
        """Test cloud tenant from config."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="cloud", cloud_tenant="my-tenant")
            assert config.get_cloud_tenant() == "my-tenant"

    def test_get_cloud_application_from_config(self):
        """Test cloud application from config."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="cloud", cloud_application="my-app")
            assert config.get_cloud_application() == "my-app"

    def test_get_cloud_instance_default(self):
        """Test default cloud instance."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="cloud")
            assert config.get_cloud_instance() == DEFAULT_VESPA_CLOUD_INSTANCE

    def test_get_cloud_instance_from_config(self):
        """Test cloud instance from config."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="cloud", cloud_instance="prod")
            assert config.get_cloud_instance() == "prod"

    def test_get_tls_verify_default(self):
        """Test default TLS verify setting."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig()
            assert config.get_tls_verify() == DEFAULT_VESPA_TLS_VERIFY

    def test_get_tls_verify_from_env(self):
        """Test TLS verify from environment variable."""
        with patch.dict(os.environ, {"VESPA_TLS_VERIFY": "0"}):
            config = DeployConfig()
            assert config.get_tls_verify() is False

        with patch.dict(os.environ, {"VESPA_TLS_VERIFY": "true"}):
            config = DeployConfig()
            assert config.get_tls_verify() is True

        with patch.dict(os.environ, {"VESPA_TLS_VERIFY": "yes"}):
            config = DeployConfig()
            assert config.get_tls_verify() is True

    def test_get_cloud_api_key_from_env(self):
        """Test cloud API key from environment variable."""
        with patch.dict(os.environ, {"VESPA_CLOUD_API_KEY": "my-api-key"}):
            config = DeployConfig(deploy_mode="cloud")
            assert config.get_cloud_api_key() == "my-api-key"

    def test_get_tls_client_cert_local_mode(self):
        """Test that TLS client cert returns None for local mode without CLI."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="local")
            assert config.get_tls_client_cert() is None

    def test_get_tls_client_key_local_mode(self):
        """Test that TLS client key returns None for local mode without CLI."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="local")
            assert config.get_tls_client_key() is None

    def test_get_tls_ca_cert_local_mode(self):
        """Test that TLS CA cert returns None for local mode without CLI."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig(deploy_mode="local")
            assert config.get_tls_ca_cert() is None

    def test_get_cloud_secret_token_from_env(self):
        """Test cloud secret token from environment variable."""
        with patch.dict(os.environ, {"VESPA_CLOUD_SECRET_TOKEN": "my-token"}):
            config = DeployConfig(deploy_mode="cloud")
            assert config.get_cloud_secret_token() == "my-token"

    def test_get_configserver_url_default(self):
        """Test default config server URL."""
        with patch.dict(os.environ, {}, clear=True):
            config = DeployConfig()
            # Should return default
            url = config.get_configserver_url()
            assert "localhost" in url or "19071" in url

    def test_get_configserver_url_from_env(self):
        """Test config server URL from environment variable."""
        with patch.dict(os.environ, {"VESPA_CONFIGSERVER_URL": "http://vespa:19071"}):
            config = DeployConfig()
            assert config.get_configserver_url() == "http://vespa:19071"


class TestConfigMethods:
    """Tests for Config class methods."""

    def test_is_web_mode(self):
        """Test is_web_mode method."""
        web_config = Config(name="test", mode="web", start_loc="https://example.com")
        docs_config = Config(name="test", mode="docs", start_loc="/path")
        assert web_config.is_web_mode() is True
        assert docs_config.is_web_mode() is False

    def test_is_docs_mode(self):
        """Test is_docs_mode method."""
        web_config = Config(name="test", mode="web", start_loc="https://example.com")
        docs_config = Config(name="test", mode="docs", start_loc="/path")
        assert web_config.is_docs_mode() is False
        assert docs_config.is_docs_mode() is True

    def test_is_cloud_deploy_mode(self):
        """Test is_cloud_mode method for deploy mode check."""
        with patch.dict(os.environ, {}, clear=True):
            cloud_config = Config(name="test", mode="docs", start_loc="/path", deploy_mode="cloud")
            local_config = Config(name="test", mode="docs", start_loc="/path", deploy_mode="local")
            assert cloud_config.is_cloud_mode() is True
            assert local_config.is_cloud_mode() is False

    def test_is_local_deploy_mode(self):
        """Test is_local_deploy_mode method."""
        with patch.dict(os.environ, {}, clear=True):
            cloud_config = Config(name="test", mode="docs", start_loc="/path", deploy_mode="cloud")
            local_config = Config(name="test", mode="docs", start_loc="/path", deploy_mode="local")
            assert cloud_config.is_local_deploy_mode() is False
            assert local_config.is_local_deploy_mode() is True

    def test_get_deploy_config(self):
        """Test get_deploy_config method."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config(
                name="test",
                mode="docs",
                start_loc="/path",
                deploy_mode="cloud",
                cloud_tenant="my-tenant",
            )
            deploy_config = config.get_deploy_config()
            assert isinstance(deploy_config, DeployConfig)
            assert deploy_config.deploy_mode == "cloud"
            assert deploy_config.cloud_tenant == "my-tenant"

    def test_get_output_path(self):
        """Test get_output_path method."""
        config = Config(name="my-app", mode="docs", start_loc="/path")
        output_path = config.get_output_path()
        assert isinstance(output_path, Path)
        assert "my-app" in str(output_path) or "nyrag" in str(output_path)

    def test_get_app_path(self):
        """Test get_app_path method."""
        config = Config(name="my-app", mode="docs", start_loc="/path")
        app_path = config.get_app_path()
        assert isinstance(app_path, Path)
