import os
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import IO, Optional
from urllib.parse import urlparse

import httpx
from vespa.application import Vespa
from vespa.package import ApplicationPackage

from nyrag.defaults import DEFAULT_VESPA_LOCAL_PORT
from nyrag.logger import logger


_DEFAULT_CONFIGSERVER_URL = "http://localhost:19071"
_DEFAULT_VESPA_PORT = DEFAULT_VESPA_LOCAL_PORT


def _use_compose_deployer(deploy_config=None) -> bool:
    """Check if compose deployer should be used.

    Only uses compose deployer when NYRAG_VESPA_COMPOSE=1 is set.
    This is for running inside a docker-compose setup alongside Vespa.
    """
    return os.getenv("NYRAG_VESPA_COMPOSE", "").strip() == "1"


def resolve_vespa_docker_class(deploy_config=None):
    """Resolve which Docker deployer class to use."""
    if _use_compose_deployer(deploy_config):
        return ComposeVespaDocker
    from vespa.deployment import VespaDocker  # type: ignore

    return VespaDocker


class ComposeVespaDocker:
    """Deploy to an already-running Vespa config server (e.g., docker-compose)."""

    def __init__(
        self,
        image: Optional[str] = None,
        docker_image: Optional[str] = None,
        application_package: Optional[ApplicationPackage] = None,
        application_root: Optional[str] = None,
        cfgsrv_url: Optional[str] = None,
        vespa_url: Optional[str] = None,
        vespa_port: Optional[int] = None,
        output_file: IO = sys.stdout,
    ) -> None:
        self.container_image = image or docker_image
        self.output = output_file
        self.application_package = application_package
        self.app_package = application_package
        self.package = application_package
        self.application_root = application_root
        self.cfgsrv_url = (cfgsrv_url or _DEFAULT_CONFIGSERVER_URL).rstrip("/")
        self.url = _resolve_vespa_url(vespa_url, self.cfgsrv_url)
        self.port = _resolve_vespa_port(vespa_port)

    def deploy(
        self,
        application_package: Optional[ApplicationPackage] = None,
        application_root: Optional[str] = None,
        max_wait_configserver: int = 60,
        max_wait_deployment: int = 300,
        max_wait_docker: int = 300,
        debug: bool = False,
    ) -> Vespa:
        del max_wait_docker, debug
        package = application_package or self.application_package
        root = _resolve_application_root(application_root, self.application_root)
        if package is None and root is None:
            raise ValueError("Either application_package or application_root must be set")

        logger.info(f"Deploying via compose config server at {self.cfgsrv_url}")
        _wait_for_config_server(self.cfgsrv_url, max_wait_configserver)

        if package is not None:
            data = package.to_zip()
        else:
            data = _read_app_package_from_disk(root)

        _deploy_to_config_server(self.cfgsrv_url, data)
        app = Vespa(url=self.url, port=self.port, application_package=package)
        app.wait_for_application_up(max_wait=max_wait_deployment)
        return app

    def deploy_from_disk(
        self,
        application_name: str,
        application_root: Path,
        max_wait_configserver: int = 60,
        max_wait_application: int = 300,
        docker_timeout: int = 300,
        debug: bool = False,
    ) -> Vespa:
        del docker_timeout, debug
        package = ApplicationPackage(name=application_name)
        data = _read_app_package_from_disk(application_root)
        logger.info(f"Deploying via compose config server at {self.cfgsrv_url}")
        _wait_for_config_server(self.cfgsrv_url, max_wait_configserver)
        _deploy_to_config_server(self.cfgsrv_url, data)
        app = Vespa(url=self.url, port=self.port, application_package=package)
        app.wait_for_application_up(max_wait=max_wait_application)
        return app


def _resolve_vespa_url(vespa_url: Optional[str], cfgsrv_url: str) -> str:
    """Resolve Vespa URL from parameter or infer from config server URL."""
    if vespa_url:
        return vespa_url.strip().rstrip("/")
    parsed = urlparse(cfgsrv_url)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    return f"{scheme}://{host}"


def _resolve_vespa_port(vespa_port: Optional[int]) -> int:
    """Resolve Vespa port from parameter or use default."""
    if vespa_port is not None:
        return int(vespa_port)
    return _DEFAULT_VESPA_PORT


def _resolve_application_root(
    application_root: Optional[str],
    fallback_root: Optional[str],
) -> Optional[Path]:
    root = (application_root or fallback_root or "").strip()
    if not root:
        return None
    return Path(root)


def _read_app_package_from_disk(application_root: Path) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(application_root, followlinks=True):
            for filename in files:
                full_path = Path(root) / filename
                rel_path = full_path.relative_to(application_root)
                zipf.write(full_path, rel_path.as_posix())
    return buffer.getvalue()


def _wait_for_config_server(cfgsrv_url: str, max_wait: int) -> None:
    deadline = time.time() + max_wait
    status_url = f"{cfgsrv_url}/ApplicationStatus"
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.head(status_url, timeout=5.0)
            if response.status_code == 200:
                return
        except httpx.RequestError as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f"Config server did not start within {max_wait} seconds. Last error: {last_error}")


def _deploy_to_config_server(cfgsrv_url: str, data: bytes) -> None:
    url = f"{cfgsrv_url}/application/v2/tenant/default/prepareandactivate"
    headers = {"Content-Type": "application/zip"}
    response = httpx.post(url, content=data, headers=headers, timeout=60.0)
    if response.status_code != 200:
        raise RuntimeError(
            f"Deployment failed ({response.status_code}): {response.text.strip() or 'no response body'}"
        )
