"""
agent_docker.py
===============

Docker image building and management for running agents inside containers.

Provides:
- build_agent_image: Build agent Docker image on top of task's base image
- AgentContainer: Context manager for running agent inside Docker
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import docker
    from docker.errors import ImageNotFound, APIError, BuildError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


def build_agent_image(base_image: str, force_rebuild: bool = False) -> str:
    """
    Build agent Docker image on top of the specified base image.

    Args:
        base_image: Base image to build on (e.g., "ubuntu:22.04", "python:3.9")
        force_rebuild: Force rebuild even if image exists

    Returns:
        Name of the built agent image (e.g., "setupbench-agent:ubuntu-22.04")

    Raises:
        RuntimeError: If Docker is not available or build fails
    """
    if not DOCKER_AVAILABLE:
        raise RuntimeError("Docker support not available. Install with: pip install docker")

    client = docker.from_env()

    # Generate agent image name from base image
    # ubuntu:22.04 → setupbench-agent:ubuntu-22.04
    # python:3.9 → setupbench-agent:python-3.9
    agent_image_tag = base_image.replace(':', '-').replace('/', '-')
    agent_image_name = f"setupbench-agent:{agent_image_tag}"

    # Check if image already exists
    if not force_rebuild:
        try:
            client.images.get(agent_image_name)
            print(f"✓ Agent image already exists: {agent_image_name}")
            return agent_image_name
        except ImageNotFound:
            pass

    # Build agent image
    print(f"🔨 Building agent image: {agent_image_name}")
    print(f"   Base image: {base_image}")

    # Find project root (where Dockerfile.agent is)
    project_root = Path(__file__).parent.parent.parent

    try:
        # Build image
        image, build_logs = client.images.build(
            path=str(project_root),
            dockerfile="Dockerfile.agent",
            buildargs={"BASE_IMAGE": base_image},
            tag=agent_image_name,
            rm=True,  # Remove intermediate containers
            forcerm=True  # Always remove intermediate containers
        )

        # Print build logs
        for log in build_logs:
            if 'stream' in log:
                print(f"   {log['stream'].strip()}")

        print(f"✓ Built agent image: {agent_image_name}")
        return agent_image_name

    except BuildError as e:
        print(f"✗ Failed to build agent image: {e}")
        for log in e.build_log:
            if 'stream' in log:
                print(f"   {log['stream'].strip()}")
        raise RuntimeError(f"Failed to build agent image: {e}")


class AgentContainer:
    """Context manager for running agent inside a Docker container."""

    def __init__(
        self,
        agent_image: str,
        workspace: Path,
        log_dir: Path,
        instance_id: str,
        api_key: str
    ):
        """
        Initialize agent container.

        Args:
            agent_image: Agent Docker image name
            workspace: Host workspace directory to mount to /testbed
            log_dir: Host log directory to mount to /logs
            instance_id: Task instance ID
            api_key: Anthropic API key
        """
        if not DOCKER_AVAILABLE:
            raise RuntimeError("Docker support not available. Install with: pip install docker")

        self.agent_image = agent_image
        self.workspace = workspace
        self.log_dir = log_dir
        self.instance_id = instance_id
        self.api_key = api_key
        self.client = docker.from_env()
        self.container = None

    def __enter__(self):
        """Start the Docker container with workspace and logs mounted."""
        try:
            # Ensure log directory exists
            self.log_dir.mkdir(parents=True, exist_ok=True)

            # Start container in background
            self.container = self.client.containers.run(
                self.agent_image,
                command="/bin/bash -c 'tail -f /dev/null'",  # Keep alive
                detach=True,
                volumes={
                    str(self.workspace.absolute()): {'bind': '/testbed', 'mode': 'rw'},
                    str(self.log_dir.absolute()): {'bind': '/logs', 'mode': 'rw'}
                },
                working_dir='/testbed',
                name=f"setupbench-agent-{self.instance_id}",
                remove=False  # Don't auto-remove for debugging
            )

            print(f"✓ Started agent container: {self.container.short_id}")
            return self

        except Exception as e:
            print(f"✗ Failed to start agent container: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop and remove the container."""
        if self.container:
            try:
                self.container.stop(timeout=5)
                self.container.remove()
                print(f"✓ Cleaned up agent container: {self.container.short_id}")
            except Exception as e:
                print(f"Warning: Failed to cleanup container: {e}")

    def run_agent(self, task: Dict[str, Any]) -> tuple[int, str, str]:
        """
        Execute the agent inside the container.

        Args:
            task: Task configuration dictionary

        Returns:
            (exit_code, stdout, stderr)
        """
        if not self.container:
            raise RuntimeError("Container not started")

        # Serialize task to JSON for passing to script
        task_json = json.dumps(task)

        # Run agent script inside container
        print(f"🤖 Running agent in container for {task['instance_id']}...")

        # Pass as list to avoid shell quoting issues with special chars in JSON
        result = self.container.exec_run(
            ["python3", "/app/run_agent_in_container.py", task_json, self.api_key],
            workdir="/testbed",
            demux=True,
            stream=False
        )

        exit_code = result.exit_code
        stdout = result.output[0].decode('utf-8') if result.output[0] else ""
        stderr = result.output[1].decode('utf-8') if result.output[1] else ""

        if exit_code != 0:
            print(f"✗ Agent execution failed with exit code {exit_code}")
            if stderr:
                print(f"   Error: {stderr[:500]}")
        else:
            print(f"✓ Agent execution completed successfully")

        return exit_code, stdout, stderr

    def run_validation(self, success_command: str) -> tuple[bool, str]:
        """
        Run validation command in a fresh shell inside the container.

        Args:
            success_command: Validation command to run

        Returns:
            (success: bool, output: str)
        """
        if not self.container:
            raise RuntimeError("Container not started")

        print(f"✓ Running validation in fresh shell...")

        # Pass as list to avoid shell quoting issues with special chars in command
        result = self.container.exec_run(
            ["/bin/bash", "-c", success_command],
            workdir="/testbed",
            demux=True
        )

        exit_code = result.exit_code
        stdout = result.output[0].decode('utf-8') if result.output[0] else ""
        stderr = result.output[1].decode('utf-8') if result.output[1] else ""
        output = stdout + stderr

        success = "Setup successful" in output or exit_code == 0

        return success, output

    def collect_logs(self, output_dir: Path) -> Dict[str, Path]:
        """
        Copy agent logs from container to host.

        Args:
            output_dir: Host directory to copy logs to

        Returns:
            Dictionary mapping log type to host path
        """
        if not self.container:
            raise RuntimeError("Container not started")

        # Logs are written to mounted /logs directory (self.log_dir)
        # which maps to /logs/<instance_id>/ in container
        # No need to extract - they're already on the host!

        log_files = {}

        # Check for each log file in the mounted directory
        for log_name in ["agent.log", "tools.jsonl", "messages.jsonl"]:
            log_path = self.log_dir / self.instance_id / log_name
            if log_path.exists():
                log_files[log_name] = log_path
            else:
                print(f"Warning: Log file not found: {log_path}")

        return log_files

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from mounted log directory.

        Returns:
            Dictionary with metrics
        """
        if not self.container:
            raise RuntimeError("Container not started")

        try:
            # Read metrics directly from mounted log directory
            metrics_file = self.log_dir / "metrics.json"
            if metrics_file.exists():
                with open(metrics_file) as f:
                    metrics = json.load(f)

            return metrics

        except Exception as e:
            print(f"Warning: Could not collect metrics: {e}")
            return {}
