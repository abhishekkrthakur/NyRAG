import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from vespa.package import ApplicationPackage

from nyrag.defaults import DEFAULT_VESPA_DOCKER_IMAGE
from nyrag.logger import console, logger
from nyrag.vespa_docker import resolve_vespa_docker_class


if TYPE_CHECKING:
    from nyrag.config import DeployConfig


_CLUSTER_REMOVAL_ALLOWLIST_TOKEN = "content-cluster-removal"
_MISSING_PACKAGE_ERROR = "Either application_package or application_root must be set"


def _validation_overrides_xml(*, until: date) -> str:
    return (
        "<validation-overrides>\n"
        f"  <allow until='{until.isoformat()}'>{_CLUSTER_REMOVAL_ALLOWLIST_TOKEN}</allow>\n"
        "</validation-overrides>\n"
    )


def _looks_like_cluster_removal_error(message: str) -> bool:
    if not message:
        return False
    lowered = message.lower()
    if _CLUSTER_REMOVAL_ALLOWLIST_TOKEN in lowered:
        return True
    return "content cluster" in lowered and "removed" in lowered


def _confirm_cluster_removal(message: str, *, until: date) -> bool:
    """
    Return True if it's OK to deploy with `content-cluster-removal` override.

    Behavior:
    - If stdin isn't interactive: auto-deny.
    - Otherwise, ask the user.
    """
    if not sys.stdin.isatty():
        logger.warning("Vespa deploy requires 'content-cluster-removal' override, but stdin is not interactive.")
        return False

    console.print(
        "\nVespa refused this deploy because it would remove an existing content cluster.\n"
        f"- Override: {_CLUSTER_REMOVAL_ALLOWLIST_TOKEN} (until {until.isoformat()})\n"
        "This will cause loss of all data in that cluster."
    )
    if message.strip():
        console.print(f"\nVespa message:\n{message.strip()}\n")
    answer = console.input("Purge existing cluster data and redeploy? [y/N]: ")
    return answer.strip().lower() in {"y", "yes"}


def _write_validation_overrides(app_dir: Path, *, until: date) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "validation-overrides.xml").write_text(
        _validation_overrides_xml(until=until),
        encoding="utf-8",
    )


def _deploy_with_pyvespa(deployer: Any, *, application_package: ApplicationPackage, application_root: Path) -> Any:
    """
    Deploy using pyvespa across minor API differences.

    Different pyvespa versions accept either:
    - deploy(application_package=...)
    - deploy(application_root=...)
    - deploy() after providing application_package/application_root on the deployer
    """

    def _should_fallback(exc: Exception) -> bool:
        msg = str(exc)
        if isinstance(exc, TypeError):
            return True
        return _MISSING_PACKAGE_ERROR in msg

    try:
        return deployer.deploy(application_package=application_package)
    except Exception as e:
        if not _should_fallback(e):
            raise

    try:
        return deployer.deploy(application_root=str(application_root))
    except Exception as e:
        if not _should_fallback(e):
            raise

    # Last resort: set attributes if present and call deploy() with no args.
    for attr, value in (
        ("application_package", application_package),
        ("app_package", application_package),
        ("package", application_package),
        ("application_root", str(application_root)),
    ):
        if hasattr(deployer, attr):
            try:
                setattr(deployer, attr, value)
            except Exception:
                pass
    return deployer.deploy()


def _set_vespa_endpoint_env_from_app(vespa_app: Any) -> None:
    """Extract and return endpoint info from a deployed Vespa app.

    Note: This no longer sets environment variables. It's kept for compatibility
    but the returned values should be used directly.
    """
    import os

    def _as_path_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return os.fspath(value)
        except Exception:
            pass
        if isinstance(value, str):
            return value
        return None

    # Extract but don't set env vars - values are used directly from config now
    url = getattr(vespa_app, "url", None)
    port = getattr(vespa_app, "port", None)
    cert = _as_path_str(getattr(vespa_app, "cert", None))

    # Log the extracted values for debugging
    if isinstance(url, str):
        logger.debug(f"Vespa endpoint: {url}:{port}")
    if cert:
        logger.debug(f"mTLS cert: {cert}")


def deploy_app_package(
    app_dir: Optional[Path],
    *,
    app_package: ApplicationPackage,
    deploy_config: Optional["DeployConfig"] = None,
) -> bool:
    """
    Deploy the application package using pyvespa deployments.

    Deployment mode is determined by deploy_config.deploy_mode:
    - "local" => start local Vespa via `VespaDocker`
    - "cloud" => deploy to `VespaCloud`

    Connection settings come from environment variables:
    - VESPA_URL, VESPA_PORT, VESPA_CONFIGSERVER_URL (for local)
    - VESPA_CLOUD_* env vars (for cloud)
    """
    from nyrag.config import DeployConfig

    if deploy_config is None:
        deploy_config = DeployConfig()

    mode = "docker" if deploy_config.is_local_mode() else "cloud"

    attempted_override = False
    while True:
        try:
            tmp: Optional[tempfile.TemporaryDirectory] = None
            effective_app_dir = Path(app_dir) if app_dir is not None else None
            if effective_app_dir is None:
                tmp = tempfile.TemporaryDirectory()
                effective_app_dir = Path(tmp.name)
                app_package.to_files(str(effective_app_dir))

            if mode == "docker":
                VespaDocker = resolve_vespa_docker_class()

                if VespaDocker.__name__ == "ComposeVespaDocker":
                    logger.info("Deploying with ComposeVespaDocker")
                    cfgsrv_url = deploy_config.get_configserver_url()
                    logger.info(f"Deploying via compose config server at {cfgsrv_url}")
                else:
                    logger.info(f"Deploying with VespaDocker (image={DEFAULT_VESPA_DOCKER_IMAGE})")

                import inspect

                init_sig = inspect.signature(VespaDocker)
                init_kwargs = {}
                if "image" in init_sig.parameters:
                    init_kwargs["image"] = DEFAULT_VESPA_DOCKER_IMAGE
                elif "docker_image" in init_sig.parameters:
                    init_kwargs["docker_image"] = DEFAULT_VESPA_DOCKER_IMAGE

                # Pass config server URL for compose deployer
                if "cfgsrv_url" in init_sig.parameters:
                    init_kwargs["cfgsrv_url"] = deploy_config.get_configserver_url()

                # Some pyvespa versions want the application package/root on the deployer instance.
                if "application_package" in init_sig.parameters:
                    init_kwargs["application_package"] = app_package
                if "application_root" in init_sig.parameters:
                    init_kwargs["application_root"] = str(effective_app_dir)

                docker = VespaDocker(**init_kwargs) if init_kwargs else VespaDocker()

                vespa_app = _deploy_with_pyvespa(
                    docker,
                    application_package=app_package,
                    application_root=effective_app_dir,
                )
                _set_vespa_endpoint_env_from_app(vespa_app)
                logger.success("VespaDocker deploy succeeded")
                return True

            if mode == "cloud":
                from vespa.deployment import VespaCloud  # type: ignore

                tenant = deploy_config.get_cloud_tenant()
                if not tenant:
                    raise RuntimeError("Missing env var: VESPA_CLOUD_TENANT")

                application = deploy_config.get_cloud_application() or app_package.name
                instance = deploy_config.get_cloud_instance()

                if not deploy_config.get_cloud_application():
                    logger.info(f"VESPA_CLOUD_APPLICATION not set; using generated app name '{application}'")
                logger.info(f"Deploying to Vespa Cloud: {tenant}/{application}/{instance}")

                import inspect

                init_sig = inspect.signature(VespaCloud)
                init_kwargs = {}
                for key, value in (
                    ("tenant", tenant),
                    ("application", application),
                    ("instance", instance),
                ):
                    if key in init_sig.parameters:
                        init_kwargs[key] = value

                # Some pyvespa versions require application_root/application_package on the deployer.
                if "application_package" in init_sig.parameters:
                    init_kwargs["application_package"] = app_package
                if "application_root" in init_sig.parameters:
                    init_kwargs["application_root"] = str(effective_app_dir)

                api_key_path = deploy_config.get_cloud_api_key_path()
                api_key = deploy_config.get_cloud_api_key()
                if api_key_path and "api_key_path" in init_sig.parameters:
                    init_kwargs["api_key_path"] = api_key_path
                if api_key and "api_key" in init_sig.parameters:
                    init_kwargs["api_key"] = api_key

                cloud = VespaCloud(**init_kwargs)

                vespa_app = _deploy_with_pyvespa(
                    cloud,
                    application_package=app_package,
                    application_root=effective_app_dir,
                )
                _set_vespa_endpoint_env_from_app(vespa_app)
                logger.success("Vespa Cloud deploy succeeded")
                return True

            raise ValueError(f"Unknown Vespa deploy mode: {mode!r}")
        except Exception as e:
            message = str(e)
            if _looks_like_cluster_removal_error(message) and not attempted_override:
                until = date.today() + timedelta(days=7)
                if not _confirm_cluster_removal(message, until=until):
                    logger.warning(
                        "Skipping Vespa deploy to avoid content cluster removal; "
                        "feeding/query may fail until the app is deployed."
                    )
                    return False

                # Write overrides into the on-disk app package and retry.
                target_dir = Path(app_dir) if app_dir is not None else None
                if target_dir is None:
                    tmp = tempfile.TemporaryDirectory()
                    target_dir = Path(tmp.name)
                    app_package.to_files(str(target_dir))
                _write_validation_overrides(target_dir, until=until)
                app_dir = target_dir

                attempted_override = True
                continue

            raise
