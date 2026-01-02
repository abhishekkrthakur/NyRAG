from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, field_validator


class CrawlParams(BaseModel):
    """Parameters specific to web crawling."""

    respect_robots_txt: bool = True
    aggressive_crawl: bool = False
    follow_subdomains: bool = True
    strict_mode: bool = False
    user_agent_type: Literal["chrome", "firefox", "safari", "mobile", "bot"] = "chrome"
    custom_user_agent: Optional[str] = None
    allowed_domains: Optional[List[str]] = None


class DocParams(BaseModel):
    """Parameters specific to document processing."""

    recursive: bool = True
    include_hidden: bool = False
    follow_symlinks: bool = False
    max_file_size_mb: Optional[float] = None
    file_extensions: Optional[List[str]] = None


class LLMConfig(BaseModel):
    """Configuration for LLM providers."""

    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


class Config(BaseModel):
    """Configuration model for nyrag."""

    name: str
    mode: Literal["web", "docs"]
    start_loc: str
    exclude: Optional[List[str]] = None
    rag_params: Optional[Dict[str, Any]] = None
    crawl_params: Optional[CrawlParams] = None
    doc_params: Optional[DocParams] = None
    llm_config: Optional[LLMConfig] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        """Validate and normalize mode."""
        if v.lower() in ["web", "docs", "doc"]:
            return "docs" if v.lower() in ["docs", "doc"] else "web"
        raise ValueError("mode must be 'web' or 'docs'")

    def model_post_init(self, __context):
        """Initialize params with defaults if None."""
        if self.crawl_params is None:
            self.crawl_params = CrawlParams()
        if self.doc_params is None:
            self.doc_params = DocParams()

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "Config":
        """Load configuration from a YAML file."""
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def get_output_path(self) -> Path:
        """Get the output directory path."""
        # Use schema name format for consistency (lowercase alphanumeric only)
        schema_name = self.get_schema_name()
        return Path("output") / schema_name

    def get_app_path(self) -> Path:
        """Get the app directory path for Vespa schema."""
        return self.get_output_path() / "app"

    def get_schema_name(self) -> str:
        """Get the schema name in format nyragPROJECTNAME (lowercase alphanumeric only)."""
        # Remove hyphens, underscores, and convert to lowercase for valid Vespa schema name
        clean_name = self.name.replace("-", "").replace("_", "").lower()
        return f"nyrag{clean_name}"

    def get_app_package_name(self) -> str:
        """Get a valid application package name (lowercase, no hyphens, max 20 chars)."""
        # Remove hyphens and convert to lowercase
        clean_name = self.name.replace("-", "").replace("_", "").lower()
        # Prefix with nyrag and limit to 20 characters
        app_name = f"nyrag{clean_name}"[:20]
        return app_name

    def get_schema_params(self) -> Dict[str, Any]:
        """Get schema parameters from rag_params."""
        if self.rag_params is None:
            return {}
        return {
            "embedding_dim": self.rag_params.get("embedding_dim", 384),
            "chunk_size": self.rag_params.get("chunk_size", 1024),
            "distance_metric": self.rag_params.get("distance_metric", "angular"),
        }

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration from llm_config or rag_params (legacy)."""
        if self.llm_config:
            return {
                "llm_base_url": self.llm_config.base_url,
                "llm_model": self.llm_config.model,
                "llm_api_key": self.llm_config.api_key,
            }

        if self.rag_params is None:
            return {}

        return {
            "llm_base_url": self.rag_params.get("llm_base_url"),
            "llm_model": self.rag_params.get("llm_model"),
            "llm_api_key": self.rag_params.get("llm_api_key"),
        }

    def is_web_mode(self) -> bool:
        """Check if config is for web crawling."""
        return self.mode == "web"

    def is_docs_mode(self) -> bool:
        """Check if config is for document processing."""
        return self.mode == "docs"


def get_config_options(mode: str = "web") -> Dict[str, Any]:
    """
    Return the interactive configuration schema for the frontend.
    Dynamically hides irrelevant sections (crawl_params for docs, doc_params for web).
    """
    # Common base fields
    schema = {
        "name": {"type": "string", "label": "name"},
        "mode": {"type": "select", "label": "mode", "options": ["web", "docs"]},
        "start_loc": {"type": "string", "label": "start_loc"},
        "exclude": {"type": "list", "label": "exclude"},
    }

    # Web Mode Specifics
    if mode == "web":
        schema["crawl_params"] = {
            "type": "nested",
            "label": "crawl_params",
            "fields": {
                "respect_robots_txt": {"type": "boolean", "label": "respect_robots_txt"},
                "follow_subdomains": {"type": "boolean", "label": "follow_subdomains"},
                "user_agent_type": {
                    "type": "select",
                    "label": "user_agent_type",
                    "options": ["chrome", "firefox", "bot"],
                },
                "aggressive": {"type": "boolean", "label": "aggressive"},
                "strict_mode": {"type": "boolean", "label": "strict_mode"},
                "custom_user_agent": {"type": "string", "label": "custom_user_agent"},
                "allowed_domains": {"type": "list", "label": "allowed_domains"},
            },
        }

    # Doc Mode Specifics
    if mode == "docs":
        schema["doc_params"] = {
            "type": "nested",
            "label": "doc_params",
            "fields": {
                "recursive": {"type": "boolean", "label": "recursive"},
                "include_hidden": {"type": "boolean", "label": "include_hidden"},
                "follow_symlinks": {"type": "boolean", "label": "follow_symlinks"},
                "max_file_size_mb": {"type": "number", "label": "max_file_size_mb"},
                "file_extensions": {"type": "list", "label": "file_extensions"},
            },
        }

    # Always include RAG and LLM params
    schema["rag_params"] = {
        "type": "nested",
        "label": "rag_params",
        "fields": {
            "embedding_model": {"type": "string", "label": "embedding_model"},
            "embedding_dim": {"type": "number", "label": "embedding_dim"},
            "chunk_size": {"type": "number", "label": "chunk_size"},
            "chunk_overlap": {"type": "number", "label": "chunk_overlap"},
            "distance_metric": {
                "type": "select",
                "label": "distance_metric",
                "options": ["angular", "euclidean", "dot", "hamming"],
            },
        },
    }

    schema["llm_config"] = {
        "type": "nested",
        "label": "llm_config",
        "optional": True,
        "fields": {
            "base_url": {"type": "string", "label": "base_url"},
            "model": {"type": "string", "label": "model"},
            "api_key": {"type": "string", "label": "api_key", "masked": True},
        },
    }

    return schema


def get_example_configs() -> Dict[str, str]:
    """
    Return available example configurations from the package.
    Returns a dict of {name: yaml_content}.
    """
    import importlib.resources as pkg_resources

    examples: Dict[str, str] = {}
    try:
        # Python 3.9+ style
        files = pkg_resources.files("nyrag.examples")
        for item in files.iterdir():
            if item.name.endswith(".yml") or item.name.endswith(".yaml"):
                name = item.name.rsplit(".", 1)[0]
                examples[name] = item.read_text()
    except Exception:
        # Fallback for older Python or missing package
        pass

    return examples
