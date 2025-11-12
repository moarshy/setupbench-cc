#!/usr/bin/env python3
"""
Minimal SetupBench runner for Claude Code.

Follows the exact evaluation approach from the SetupBench paper (Section 3.1):
- Agent gets natural language problem_statement
- Agent runs in workspace
- Validation command runs in FRESH SHELL
- Parse "Setup successful" vs "Setup failed"

Includes comprehensive logging for metrics calculation.
"""

import json
import asyncio
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        TextBlock,
        HookMatcher
    )
except ImportError:
    print("Warning: claude_agent_sdk not installed. Install with: pip install claude-agent-sdk")

try:
    import docker
    from docker.errors import ImageNotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    print("Warning: docker package not installed. Install with: pip install docker")
    print("Docker-based tasks will not work without it.")

# ============================================================================
# Logging Infrastructure (adapted from example code)
# ============================================================================

class ToolLogEntry(BaseModel):
    """Log entry for a tool call and its result."""
    timestamp: str
    event_type: str  # "pre_tool" or "post_tool"
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    tool_use_id: Optional[str] = None
    error: Optional[str] = None


class SetupBenchLogger:
    """Logger for SetupBench agent execution."""

    def __init__(self, instance_id: str, log_dir: Path):
        """
        Initialize logger for a task instance.

        Args:
            instance_id: Task instance ID
            log_dir: Directory to save all logs
        """
        self.instance_id = instance_id
        self.log_dir = Path(log_dir) / instance_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.agent_log = self.log_dir / "agent.log"
        self.tools_log = self.log_dir / "tools.jsonl"
        self.messages_log = self.log_dir / "messages.jsonl"

        # Initialize log files
        self.agent_log.touch(exist_ok=True)
        self.tools_log.touch(exist_ok=True)
        self.messages_log.touch(exist_ok=True)

        # Statistics
        self.stats = {
            "total_tool_calls": 0,
            "bash_calls": 0,
            "read_calls": 0,
            "write_calls": 0,
            "edit_calls": 0,
            "errors": 0,
            "messages": 0,
        }

    def log_message(self, message: str, level: str = "INFO"):
        """Log a message to agent.log."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"

        with open(self.agent_log, 'a') as f:
            f.write(log_entry)

    def log_tool_call(self, entry: ToolLogEntry):
        """Log a tool call to tools.jsonl."""
        with open(self.tools_log, 'a') as f:
            f.write(entry.model_dump_json() + '\n')

        # Update statistics
        self.stats["total_tool_calls"] += 1
        if entry.tool_name == "Bash":
            self.stats["bash_calls"] += 1
        elif entry.tool_name == "Read":
            self.stats["read_calls"] += 1
        elif entry.tool_name == "Write":
            self.stats["write_calls"] += 1
        elif entry.tool_name == "Edit":
            self.stats["edit_calls"] += 1

        if entry.error:
            self.stats["errors"] += 1

    def log_claude_message(self, role: str, content: Any):
        """Log a message from Claude conversation to messages.jsonl."""
        message_entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        }

        with open(self.messages_log, 'a') as f:
            f.write(json.dumps(message_entry) + '\n')

        self.stats["messages"] += 1

    def get_stats(self) -> Dict[str, int]:
        """Get logging statistics."""
        return self.stats.copy()


def create_hooks(logger: SetupBenchLogger):
    """
    Create hooks for logging tool calls.

    Args:
        logger: SetupBenchLogger instance

    Returns:
        Dictionary with hook configurations
    """

    async def pre_tool_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Hook that runs before tool execution."""
        try:
            tool_name = input_data.get('tool_name', 'unknown')
            tool_input = input_data.get('tool_input', {})

            # Log to agent.log with summary
            summary = f"{tool_name}"
            if tool_name == "Bash":
                cmd = tool_input.get('command', '')[:80]
                summary = f"Bash: {cmd}"
            elif tool_name == "Read":
                summary = f"Read: {tool_input.get('file_path', 'unknown')}"
            elif tool_name == "Write":
                summary = f"Write: {tool_input.get('file_path', 'unknown')}"

            logger.log_message(f"TOOL CALL: {summary}", level="DEBUG")

            # Log to tools.jsonl
            entry = ToolLogEntry(
                timestamp=datetime.now().isoformat(),
                event_type="pre_tool",
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=tool_use_id
            )
            logger.log_tool_call(entry)

        except Exception as e:
            logger.log_message(f"Error in pre_tool_hook: {e}", level="ERROR")

        return {}

    async def post_tool_hook(
        input_data: Dict[str, Any],
        tool_use_id: Optional[str],
        context: Any  # noqa: ARG001 - Required by hook signature
    ) -> Dict[str, Any]:
        """Hook that runs after tool execution."""
        try:
            tool_name = input_data.get('tool_name', 'unknown')
            tool_input = input_data.get('tool_input', {})
            tool_output = input_data.get('tool_output', {})

            # Check for errors
            error = None
            if isinstance(tool_output, dict) and tool_output.get('is_error'):
                error = str(tool_output.get('content', 'Unknown error'))

            # Log to tools.jsonl
            entry = ToolLogEntry(
                timestamp=datetime.now().isoformat(),
                event_type="post_tool",
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                tool_use_id=tool_use_id,
                error=error
            )
            logger.log_tool_call(entry)

            if error:
                logger.log_message(f"TOOL ERROR: {tool_name} - {error[:100]}", level="ERROR")

        except Exception as e:
            logger.log_message(f"Error in post_tool_hook: {e}", level="ERROR")

        return {}

    return {
        'PreToolUse': [HookMatcher(hooks=[pre_tool_hook])],
        'PostToolUse': [HookMatcher(hooks=[post_tool_hook])]
    }


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are a DevOps engineer setting up a development environment in a fresh {base_image} container.

**Environment:**
- Fresh {base_image} container
- Nothing is pre-installed except base OS packages
- You have root access
- Network access available

**Task:**
{problem_statement}

**Success Criteria:**
After you complete the setup, this command will be run in a FRESH SHELL:
```bash
{success_command}
```

This command must output exactly "Setup successful" for the task to pass.

**CRITICAL Guidelines:**
1. **Persistence**: All installations must persist across shell sessions
   - Use system package managers (apt-get, yum, etc.)
   - Don't install with --user flags
   - Update PATH in /etc/profile.d/ or .bashrc if needed

2. **Complete Setup**: Install ALL required tools
   - Don't just install runtime dependencies
   - Install build tools, test frameworks, development dependencies
   - Check project files (tox.ini, package.json, Gemfile) for test requirements

3. **Verify Your Work**: Test installations before finishing
   - Run commands in a new shell to verify persistence
   - Check that the validation command would work

4. **No Assumptions**: This is a bare system
   - Don't assume git, curl, or build-essential are installed
   - Install everything explicitly

Use Bash, Read, Write, and Edit tools to complete this setup task.
"""

# ============================================================================
# Docker Support Functions
# ============================================================================

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


# ============================================================================
# Task Runner
# ============================================================================

async def run_task(
    task_file: Path,
    output_dir: Path,
    timeout: int = 7200
) -> Dict[str, Any]:
    """
    Run a single SetupBench task with full logging.

    Args:
        task_file: Path to task JSON file
        output_dir: Where to save results and logs
        timeout: Max time in seconds (default: 2 hours)

    Returns:
        Dictionary with task result and metrics
    """

    # Load task
    with open(task_file) as f:
        task = json.load(f)

    instance_id = task['instance_id']

    print(f"\n{'='*70}")
    print(f"Task: {instance_id}")
    print(f"Type: {task['task_type']}")
    print(f"Base Image: {task['base_image']}")
    print(f"{'='*70}\n")

    # Create logger
    logger = SetupBenchLogger(instance_id, output_dir / "logs")
    logger.log_message(f"Starting task: {instance_id}")
    logger.log_message(f"Task type: {task['task_type']}")
    logger.log_message(f"Base image: {task['base_image']}")

    # Create workspace
    workspace = output_dir / "workspaces" / instance_id
    workspace.mkdir(parents=True, exist_ok=True)
    logger.log_message(f"Workspace: {workspace}")

    # Copy fixtures if they exist (for database/background service tasks)
    # Try to find SetupBench directory (parent, sibling, or explicitly set)
    setupbench_paths = [
        Path("../SetupBench"),  # Sibling directory
        Path("SetupBench"),     # Subdirectory
        Path.cwd().parent / "SetupBench"  # Parent's sibling
    ]

    for setupbench_root in setupbench_paths:
        if setupbench_root.exists():
            copy_fixtures(task, workspace, setupbench_root)
            break
    else:
        logger.log_message("SetupBench directory not found, skipping fixture copy")

    # Configure Claude Code with hooks
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT.format(
            base_image=task['base_image'],
            problem_statement=task['problem_statement'],
            success_command=task['success_command']
        ),
        allowed_tools=["Bash", "Read", "Write", "Edit"],
        cwd=str(workspace),
        max_turns=100,
        hooks=create_hooks(logger)
    )

    # Track metrics
    start_time = datetime.now()
    total_tokens = 0

    # Run agent
    try:
        async with ClaudeSDKClient(options=options) as client:
            # Log user message
            logger.log_claude_message("user", task['problem_statement'])

            # Send initial task
            await client.query(task['problem_statement'])

            # Collect responses and log all messages
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Extract message content
                    message_content = []
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            message_content.append({
                                "type": "text",
                                "text": block.text
                            })
                        else:
                            message_content.append({
                                "type": type(block).__name__,
                                "data": str(block)
                            })

                    # Log assistant message
                    logger.log_claude_message("assistant", message_content)

                elif isinstance(message, ResultMessage):
                    # Extract token usage from ResultMessage
                    if message.usage:
                        usage = message.usage
                        # Calculate total tokens: input + output + cache tokens
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)
                        cache_creation = usage.get("cache_creation_input_tokens", 0)
                        cache_read = usage.get("cache_read_input_tokens", 0)

                        total_tokens = input_tokens + output_tokens + cache_creation + cache_read

                        logger.log_message(
                            f"Token usage: input={input_tokens}, output={output_tokens}, "
                            f"cache_creation={cache_creation}, cache_read={cache_read}, "
                            f"total={total_tokens}",
                            level="INFO"
                        )

    except Exception as e:
        logger.log_message(f"Agent error: {e}", level="ERROR")
        return create_error_result(task, logger, start_time, str(e))

    elapsed = (datetime.now() - start_time).total_seconds()

    # ========================================================================
    # CRITICAL: Validate in FRESH SHELL (exactly like SetupBench paper)
    # ========================================================================

    logger.log_message("Running validation command in fresh shell...")
    print(f"\nValidating: {task['success_command']}\n")

    # Determine if we need Docker for validation
    use_docker = task['base_image'] != "local" and DOCKER_AVAILABLE

    try:
        if use_docker:
            # Run validation in Docker container
            logger.log_message(f"Using Docker image: {task['base_image']}")
            print(f"🐳 Running validation in Docker: {task['base_image']}")

            with DockerContainer(task['base_image'], workspace, instance_id) as container:
                exit_code, stdout, stderr = container.exec(task['success_command'])
                validation_output = stdout + stderr

                # Check success based on task type (from SetupBench evaluation harness)
                if task.get('task_type') == 'dependency_resolution':
                    success = exit_code == 0
                else:
                    success = "Setup successful" in validation_output
        else:
            # Run validation locally (for local tasks or when Docker unavailable)
            result = subprocess.run(
                ["bash", "-c", task['success_command']],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=120
            )

            validation_output = result.stdout + result.stderr
            success = "Setup successful" in validation_output

        logger.log_message(f"Validation output: {validation_output[:500]}")
        logger.log_message(f"Result: {'PASS' if success else 'FAIL'}")

    except subprocess.TimeoutExpired:
        validation_output = "Validation command timed out after 120s"
        success = False
        logger.log_message("Validation timeout", level="ERROR")
    except Exception as e:
        validation_output = f"Validation error: {e}"
        success = False
        logger.log_message(f"Validation error: {e}", level="ERROR")

    # Collect final statistics
    stats = logger.get_stats()

    # Create result
    result_data = {
        "instance_id": instance_id,
        "task_type": task['task_type'],
        "base_image": task['base_image'],
        "success": success,
        "validation_output": validation_output,
        "wall_time_seconds": elapsed,

        # Metrics (matching SetupBench paper Table 2)
        "total_steps": stats["total_tool_calls"],  # Step count metric
        "bash_calls": stats["bash_calls"],
        "read_calls": stats["read_calls"],
        "write_calls": stats["write_calls"],
        "edit_calls": stats["edit_calls"],
        "total_tokens": total_tokens,  # Token usage metric

        # Additional stats
        "errors": stats["errors"],
        "messages": stats["messages"],

        # Log file paths for analysis
        "logs": {
            "agent_log": str(logger.agent_log),
            "tools_log": str(logger.tools_log),
            "messages_log": str(logger.messages_log)
        }
    }

    # Save result
    result_file = output_dir / "results" / f"{instance_id}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)

    with open(result_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    # Print summary
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - {instance_id}")
    print(f"Time: {elapsed:.1f}s | Steps: {stats['total_tool_calls']} | "
          f"Bash: {stats['bash_calls']} | Errors: {stats['errors']}\n")

    return result_data


def create_error_result(
    task: Dict,
    logger: SetupBenchLogger,
    start_time: datetime,
    error_msg: str
) -> Dict[str, Any]:
    """Create result dict when agent crashes."""
    elapsed = (datetime.now() - start_time).total_seconds()
    stats = logger.get_stats()

    return {
        "instance_id": task['instance_id'],
        "task_type": task['task_type'],
        "success": False,
        "validation_output": f"Agent crashed: {error_msg}",
        "wall_time_seconds": elapsed,
        "total_steps": stats["total_tool_calls"],
        "total_tokens": 0,
        "errors": stats["errors"] + 1,
        "logs": {
            "agent_log": str(logger.agent_log),
            "tools_log": str(logger.tools_log),
            "messages_log": str(logger.messages_log)
        }
    }


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run SetupBench evaluation."""

    import argparse

    parser = argparse.ArgumentParser(description="Run Claude Code on SetupBench")
    parser.add_argument("--task", type=Path, help="Single task JSON file")
    parser.add_argument("--dataset", type=Path, help="Directory with task JSONs")
    parser.add_argument("--output", type=Path, default=Path("setupbench_output"),
                       help="Output directory for results and logs")
    parser.add_argument("--limit", type=int, help="Limit number of tasks")

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # Find tasks
    if args.task:
        task_files = [args.task]
    elif args.dataset:
        task_files = sorted(args.dataset.glob("*.json"))
        if args.limit:
            task_files = task_files[:args.limit]
    else:
        print("Error: Specify --task or --dataset")
        return

    print(f"\nFound {len(task_files)} tasks to run\n")

    # Run tasks
    results = []
    for task_file in task_files:
        result = await run_task(task_file, output_dir)
        results.append(result)

    # Calculate summary statistics (matching SetupBench Table 2)
    total = len(results)
    success_count = sum(1 for r in results if r['success'])
    success_rate = (success_count / total * 100) if total > 0 else 0

    avg_tokens = sum(r['total_tokens'] for r in results) / total if total > 0 else 0
    avg_steps = sum(r['total_steps'] for r in results) / total if total > 0 else 0
    avg_time = sum(r['wall_time_seconds'] for r in results) / total if total > 0 else 0

    # Print summary
    print(f"\n{'='*70}")
    print(f"SETUPBENCH RESULTS")
    print(f"{'='*70}")
    print(f"Total tasks: {total}")
    print(f"Success rate: {success_count}/{total} ({success_rate:.1f}%)")
    print(f"Avg tokens: {avg_tokens/1000:.1f}K")
    print(f"Avg steps: {avg_steps:.1f}")
    print(f"Avg time: {avg_time:.1f}s")
    print(f"{'='*70}\n")

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": total,
        "success_rate": success_rate,
        "successful_tasks": success_count,
        "failed_tasks": total - success_count,
        "avg_tokens": avg_tokens,
        "avg_steps": avg_steps,
        "avg_time_seconds": avg_time,
        "results": results
    }

    summary_file = output_dir / "summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"Results saved to: {output_dir}")
    print(f"Summary: {summary_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
