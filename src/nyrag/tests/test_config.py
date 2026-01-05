"""Tests for the config module."""

import tempfile
from pathlib import Path

import pytest

from nyrag.config import Config, CrawlParams, DocParams, RAGParams


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
