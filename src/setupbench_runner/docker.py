"""
docker.py
=========

Docker support for running SetupBench tasks in containers.

Provides:
- DockerContainer: Context manager for running tasks in Docker
- copy_fixtures: Helper to copy SetupBench fixtures into workspace
"""

import shutil
from pathlib import Path
from typing import Dict, Any

try:
    import docker
    from docker.errors import ImageNotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class DockerContainer:
    """Manages a Docker container for running SetupBench tasks."""

    def __init__(self, image: str, workspace: Path, instance_id: str):
        if not DOCKER_AVAILABLE:
            raise RuntimeError("Docker support not available. Install with: pip install docker")

        self.image = image
        self.workspace = workspace
        self.instance_id = instance_id
        self.client = docker.from_env()
        self.container = None

    def __enter__(self):
        """Start the Docker container with workspace mounted to /testbed."""
        try:
            # Pull image if needed
            try:
                self.client.images.get(self.image)
            except ImageNotFound:
                print(f"Pulling Docker image: {self.image}")
                self.client.images.pull(self.image)

            # Start container with workspace mounted
            self.container = self.client.containers.run(
                self.image,
                command="/bin/bash -c 'tail -f /dev/null'",  # Keep container alive
                detach=True,
                volumes={
                    str(self.workspace.absolute()): {'bind': '/testbed', 'mode': 'rw'}
                },
                working_dir='/testbed',
                name=f"setupbench-{self.instance_id}",
                remove=False  # Don't auto-remove so we can inspect if needed
            )

            print(f"✓ Started Docker container: {self.container.short_id}")
            return self

        except Exception as e:
            print(f"✗ Failed to start Docker container: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop and remove the container."""
        if self.container:
            try:
                self.container.stop(timeout=5)
                self.container.remove()
                print(f"✓ Cleaned up Docker container: {self.container.short_id}")
            except Exception as e:
                print(f"Warning: Failed to cleanup container: {e}")

    def exec(self, command: str, workdir: str = "/testbed") -> tuple[int, str, str]:
        """Execute a command in the container and return (exit_code, stdout, stderr)."""
        if not self.container:
            raise RuntimeError("Container not started")

        result = self.container.exec_run(
            f"/bin/bash -c '{command}'",
            workdir=workdir,
            demux=True
        )

        exit_code = result.exit_code
        stdout = result.output[0].decode('utf-8') if result.output[0] else ""
        stderr = result.output[1].decode('utf-8') if result.output[1] else ""

        return exit_code, stdout, stderr


def copy_fixtures(task: Dict[str, Any], workspace: Path, setupbench_root: Path) -> None:
    """Copy fixture files into workspace if they exist for this task."""
    instance_id = task['instance_id']
    fixture_dir = setupbench_root / "setupbench" / "fixtures" / instance_id

    if fixture_dir.exists():
        print(f"📦 Copying fixtures from {fixture_dir}")
        # Copy all files from fixture to workspace
        for item in fixture_dir.iterdir():
            dest = workspace / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
        print(f"✓ Fixtures copied to {workspace}")
    else:
        print(f"ℹ No fixtures found for {instance_id}")
