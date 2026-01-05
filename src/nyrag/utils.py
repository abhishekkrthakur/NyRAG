import inspect
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from nyrag.defaults import (
    DEFAULT_CLOUD_CERT_NAME,
    DEFAULT_CLOUD_KEY_NAME,
    DEFAULT_VESPA_LOCAL_PORT,
    DEFAULT_VESPA_TLS_VERIFY,
    DEFAULT_VESPA_URL,
)


if TYPE_CHECKING:
    from nyrag.config import Config, DeployConfig


def is_cloud_mode(deploy_config: Optional["DeployConfig"] = None) -> bool:
    """Check if deployment mode is cloud based on config."""
    if deploy_config is None:
        return False
    return deploy_config.is_cloud_mode()


def get_vespa_url(config: Optional["Config"] = None) -> str:
    """Get Vespa URL from config (which reads from env var) or return default."""
    if config is None:
        return os.getenv("VESPA_URL", DEFAULT_VESPA_URL)
    return config.get_vespa_url()


def get_vespa_port(config: Optional["Config"] = None) -> int:
    """Get Vespa port from config (which reads from env var) or return default based on mode."""
    if config is None:
        port_str = os.getenv("VESPA_PORT")
        if port_str:
            return int(port_str)
        return DEFAULT_VESPA_LOCAL_PORT
    return config.get_vespa_port()


def resolve_vespa_cloud_mtls_paths(project_folder: str) -> Tuple[Path, Path]:
    """Resolve default mTLS paths for Vespa Cloud."""
    base_dir = Path.home() / ".vespa" / f"devrel-public.{project_folder}.default"
    return base_dir / DEFAULT_CLOUD_CERT_NAME, base_dir / DEFAULT_CLOUD_KEY_NAME


def get_tls_config_from_deploy(
    deploy_config: Optional["DeployConfig"] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str], bool]:
    """Get Vespa TLS configuration from deploy config (reads from env vars).

    Returns:
        Tuple of (cert_path, key_path, ca_cert, verify)
    """
    if deploy_config is None:
        # Read directly from env vars
        cert = os.getenv("VESPA_CLIENT_CERT")
        key = os.getenv("VESPA_CLIENT_KEY")
        ca = os.getenv("VESPA_CA_CERT")
        verify_str = os.getenv("VESPA_TLS_VERIFY")
        verify = verify_str.strip().lower() in ("1", "true", "yes") if verify_str else DEFAULT_VESPA_TLS_VERIFY
        return cert, key, ca, verify

    return (
        deploy_config.get_tls_client_cert(),
        deploy_config.get_tls_client_key(),
        deploy_config.get_tls_ca_cert(),
        deploy_config.get_tls_verify(),
    )


def make_vespa_client(
    vespa_url: str,
    vespa_port: int,
    cert_path: Optional[str] = None,
    key_path: Optional[str] = None,
    ca_cert: Optional[str] = None,
    verify: Optional[object] = None,
) -> Any:
    """Create a Vespa client with proper configuration for different pyvespa versions.

    Args:
        vespa_url: The Vespa endpoint URL
        vespa_port: The Vespa port
        cert_path: Path to client certificate (optional)
        key_path: Path to client key (optional)
        ca_cert: Path to CA certificate (optional)
        verify: TLS verification setting (optional)

    Returns:
        Configured Vespa client instance
    """
    from vespa.application import Vespa

    kwargs: Dict[str, Any] = {}
    try:
        sig = inspect.signature(Vespa)
    except Exception:
        sig = None

    endpoint = f"{vespa_url}:{vespa_port}"
    if sig and "endpoint" in sig.parameters:
        kwargs["endpoint"] = endpoint
    else:
        kwargs["url"] = vespa_url
        kwargs["port"] = vespa_port

    if cert_path and key_path and sig and "cert" in sig.parameters:
        if "key" in sig.parameters:
            kwargs["cert"] = cert_path
            kwargs["key"] = key_path
        else:
            kwargs["cert"] = (cert_path, key_path)

    if ca_cert and sig and "ca_cert" in sig.parameters:
        kwargs["ca_cert"] = ca_cert
    if verify is not None and sig and "verify" in sig.parameters:
        kwargs["verify"] = verify

    return Vespa(**kwargs)


def chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Split text into chunks of specified size with optional overlap.

    Args:
        text: The input text to split
        chunk_size: Size of each chunk (in words)
        overlap: Number of overlapping words between chunks

    Returns:
        List of text chunks
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    words = text.split()
    word_count = len(words)

    if word_count <= chunk_size:
        return [text]

    chunk_list = []
    start = 0
    while start < word_count:
        end = min(start + chunk_size, word_count)
        chunk_list.append(" ".join(words[start:end]))
        start += chunk_size - overlap

    return chunk_list
