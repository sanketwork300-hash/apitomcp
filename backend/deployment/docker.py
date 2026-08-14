
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class DockerDeploymentError(RuntimeError):
    """Raised when Docker deployment fails."""


class DockerDeployer:
    """
    Handles Docker image building and container deployment
    for a generated MCP server.

    Expected generated project:

        generated/
        └── <server_name>/
            ├── server.py
            ├── Dockerfile
            ├── requirements.txt
            └── mcp.json
    """

    def __init__(
        self,
        docker_command: str = "docker",
    ):
        self.docker_command = docker_command

    def build_image(
        self,
        project_dir: str | Path,
        image_name: str,
        tag: str = "latest",
    ) -> str:
        """
        Build a Docker image from a generated MCP server.

        Returns:
            Full Docker image name.
        """

        project_path = Path(project_dir)

        self._validate_project(
            project_path
        )

        full_image_name = (
            f"{image_name}:{tag}"
        )

        command = [
            self.docker_command,
            "build",
            "-t",
            full_image_name,
            str(project_path),
        ]

        self._run(
            command,
            cwd=project_path,
        )

        return full_image_name

    def run_container(
        self,
        image_name: str,
        container_name: str,
        port: int = 8001,
        host_port: int | None = None,
        environment: dict[str, str] | None = None,
        detach: bool = True,
    ) -> str:
        """
        Run a generated MCP server container.

        Example:

            docker run -d \
                --name stock-api-mcp \
                -p 8001:8001 \
                stock-api-mcp:latest
        """

        host_port = (
            host_port
            if host_port is not None
            else port
        )

        command = [
            self.docker_command,
            "run",
        ]

        if detach:
            command.append("-d")

        command.extend(
            [
                "--name",
                container_name,
                "-p",
                f"{host_port}:{port}",
            ]
        )

        if environment:
            for key, value in environment.items():
                command.extend(
                    [
                        "-e",
                        f"{key}={value}",
                    ]
                )

        command.append(
            image_name
        )

        result = self._run(
            command
        )

        return result.strip()

    def stop_container(
        self,
        container_name: str,
    ) -> None:
        """
        Stop a running container.
        """

        command = [
            self.docker_command,
            "stop",
            container_name,
        ]

        self._run(
            command
        )

    def remove_container(
        self,
        container_name: str,
    ) -> None:
        """
        Remove a Docker container.
        """

        command = [
            self.docker_command,
            "rm",
            container_name,
        ]

        self._run(
            command
        )

    def remove_image(
        self,
        image_name: str,
    ) -> None:
        """
        Remove a Docker image.
        """

        command = [
            self.docker_command,
            "rmi",
            image_name,
        ]

        self._run(
            command
        )

    def container_exists(
        self,
        container_name: str,
    ) -> bool:
        """
        Check whether a Docker container exists.
        """

        command = [
            self.docker_command,
            "ps",
            "-a",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ]

        try:
            result = self._run(
                command
            )
        except DockerDeploymentError:
            return False

        names = [
            name.strip()
            for name in result.splitlines()
            if name.strip()
        ]

        return container_name in names

    def container_running(
        self,
        container_name: str,
    ) -> bool:
        """
        Check whether a Docker container is running.
        """

        command = [
            self.docker_command,
            "ps",
            "--filter",
            f"name=^{container_name}$",
            "--filter",
            "status=running",
            "--format",
            "{{.Names}}",
        ]

        try:
            result = self._run(
                command
            )
        except DockerDeploymentError:
            return False

        names = [
            name.strip()
            for name in result.splitlines()
            if name.strip()
        ]

        return container_name in names

    def get_container_logs(
        self,
        container_name: str,
        tail: int = 100,
    ) -> str:
        """
        Retrieve recent container logs.
        """

        command = [
            self.docker_command,
            "logs",
            "--tail",
            str(tail),
            container_name,
        ]

        return self._run(
            command
        )

    def deploy(
        self,
        project_dir: str | Path,
        image_name: str,
        container_name: str,
        *,
        tag: str = "latest",
        port: int = 8001,
        host_port: int | None = None,
        environment: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Build and run a generated MCP server.

        If a container with the requested name already exists,
        it is stopped and removed before deployment.
        """

        project_path = Path(
            project_dir
        )

        self._validate_project(
            project_path
        )

        full_image_name = self.build_image(
            project_dir=project_path,
            image_name=image_name,
            tag=tag,
        )

        if self.container_exists(
            container_name
        ):
            if self.container_running(
                container_name
            ):
                self.stop_container(
                    container_name
                )

            self.remove_container(
                container_name
            )

        container_id = self.run_container(
            image_name=full_image_name,
            container_name=container_name,
            port=port,
            host_port=host_port,
            environment=environment,
        )

        return {
            "success": True,
            "image": full_image_name,
            "container": container_name,
            "container_id": container_id,
            "port": (
                host_port
                if host_port is not None
                else port
            ),
        }

    def _validate_project(
        self,
        project_dir: Path,
    ) -> None:
        """
        Validate that a generated MCP project contains
        the files required for Docker deployment.
        """

        if not project_dir.exists():
            raise DockerDeploymentError(
                f"Project directory does not exist: "
                f"{project_dir}"
            )

        if not project_dir.is_dir():
            raise DockerDeploymentError(
                f"Project path is not a directory: "
                f"{project_dir}"
            )

        required_files = [
            "server.py",
            "Dockerfile",
            "requirements.txt",
        ]

        missing = [
            filename
            for filename in required_files
            if not (
                project_dir / filename
            ).exists()
        ]

        if missing:
            raise DockerDeploymentError(
                "Generated project is missing "
                "required files: "
                + ", ".join(missing)
            )

    def _run(
        self,
        command: list[str],
        cwd: Path | None = None,
    ) -> str:
        """
        Execute a Docker CLI command.

        Raises DockerDeploymentError when Docker returns
        a non-zero exit code.
        """

        try:
            result = subprocess.run(
                command,
                cwd=(
                    str(cwd)
                    if cwd
                    else None
                ),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DockerDeploymentError(
                "Docker CLI was not found. "
                "Make sure Docker is installed and "
                "available in PATH."
            ) from exc

        if result.returncode != 0:
            stderr = (
                result.stderr.strip()
                or "Unknown Docker error"
            )

            raise DockerDeploymentError(
                f"Docker command failed "
                f"(exit code "
                f"{result.returncode}): "
                f"{stderr}"
            )

        return result.stdout


def deploy_generated_server(
    project_dir: str | Path,
    image_name: str,
    container_name: str,
    *,
    tag: str = "latest",
    port: int = 8001,
    host_port: int | None = None,
    environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Convenience function for deploying a generated MCP server.
    """

    deployer = DockerDeployer()

    return deployer.deploy(
        project_dir=project_dir,
        image_name=image_name,
        container_name=container_name,
        tag=tag,
        port=port,
        host_port=host_port,
        environment=environment,
    )

