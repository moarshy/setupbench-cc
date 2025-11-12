#!/usr/bin/env python3
"""
harness.py
==========

Main entry point for running SetupBench tasks with Claude Code.

Orchestrates:
- Task loading
- Workspace setup
- Fixture copying
- Agent execution
- Docker validation
- Results collection
"""

import json
import asyncio
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from .agent import run_agent
from .agent_logging import SetupBenchLogger
from .docker import DockerContainer, copy_fixtures, DOCKER_AVAILABLE


# ====================================================================================
# Task Execution
# ====================================================================================

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

    # Track metrics
    start_time = datetime.now()

    # Run agent
    try:
        total_tokens = await run_agent(task, workspace, logger, timeout)
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
        logger.log_message(validation_output, level="ERROR")
    except Exception as e:
        validation_output = f"Validation error: {e}"
        success = False
        logger.log_message(validation_output, level="ERROR")

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
        "total_steps": stats["total_tool_calls"],
        "bash_calls": stats["bash_calls"],
        "read_calls": stats["read_calls"],
        "write_calls": stats["write_calls"],
        "edit_calls": stats["edit_calls"],
        "total_tokens": total_tokens,
        "errors": stats["errors"],
        "messages": stats["messages"],
        "logs": {
            "agent_log": str(logger.agent_log),
            "tools_log": str(logger.tools_log),
            "messages_log": str(logger.messages_log)
        }
    }

    # Save individual result
    result_file = output_dir / "results" / f"{instance_id}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with result_file.open("w") as f:
        json.dump(result_data, f, indent=2)

    # Print summary
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - {instance_id}")
    print(f"Time: {elapsed:.1f}s | Steps: {stats['total_tool_calls']} | "
          f"Bash: {stats['bash_calls']} | Errors: {stats['errors']}")

    return result_data


def create_error_result(task: Dict[str, Any], logger: SetupBenchLogger,
                       start_time: datetime, error_msg: str) -> Dict[str, Any]:
    """Create a result dict for a task that errored during execution."""
    elapsed = (datetime.now() - start_time).total_seconds()
    stats = logger.get_stats()

    return {
        "instance_id": task['instance_id'],
        "task_type": task['task_type'],
        "base_image": task['base_image'],
        "success": False,
        "validation_output": f"Agent execution error: {error_msg}",
        "wall_time_seconds": elapsed,
        "total_steps": stats["total_tool_calls"],
        "bash_calls": stats["bash_calls"],
        "read_calls": stats["read_calls"],
        "write_calls": stats["write_calls"],
        "edit_calls": stats["edit_calls"],
        "total_tokens": 0,
        "errors": stats["errors"] + 1,
        "messages": stats["messages"],
        "logs": {
            "agent_log": str(logger.agent_log),
            "tools_log": str(logger.tools_log),
            "messages_log": str(logger.messages_log)
        }
    }


# ====================================================================================
# Batch Execution
# ====================================================================================

async def run_dataset(
    dataset_dir: Path,
    output_dir: Path,
    limit: int = None
) -> List[Dict[str, Any]]:
    """Run multiple tasks from a directory."""
    task_files = sorted(dataset_dir.glob("*.json"))[:limit] if limit else sorted(dataset_dir.glob("*.json"))

    print(f"Found {len(task_files)} tasks to run\n")

    results = []
    for task_file in task_files:
        result = await run_task(task_file, output_dir)
        results.append(result)

    return results


# ====================================================================================
# Summary Generation
# ====================================================================================

def generate_summary(results: List[Dict[str, Any]], output_dir: Path) -> None:
    """Generate and save summary statistics."""
    total = len(results)
    successful = sum(1 for r in results if r['success'])
    success_rate = (successful / total * 100) if total > 0 else 0

    avg_tokens = sum(r['total_tokens'] for r in results) / total if total > 0 else 0
    avg_steps = sum(r['total_steps'] for r in results) / total if total > 0 else 0
    avg_time = sum(r['wall_time_seconds'] for r in results) / total if total > 0 else 0

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": total,
        "success_rate": success_rate,
        "successful_tasks": successful,
        "failed_tasks": total - successful,
        "avg_tokens": avg_tokens,
        "avg_steps": avg_steps,
        "avg_time_seconds": avg_time,
        "results": results
    }

    # Save summary
    summary_file = output_dir / "summary.json"
    with summary_file.open("w") as f:
        json.dump(summary, f, indent=2)

    # Print summary
    print(f"\n{'='*70}")
    print("SETUPBENCH RESULTS")
    print(f"{'='*70}")
    print(f"Total tasks: {total}")
    print(f"Success rate: {successful}/{total} ({success_rate:.1f}%)")
    print(f"Avg tokens: {avg_tokens/1000:.1f}K")
    print(f"Avg steps: {avg_steps:.1f}")
    print(f"Avg time: {avg_time:.1f}s")
    print(f"{'='*70}\n")
    print(f"Results saved to: {output_dir}")
    print(f"Summary: {summary_file}")


# ====================================================================================
# Main Entry Point
# ====================================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run SetupBench tasks with Claude Code agent"
    )
    parser.add_argument(
        "--task",
        type=Path,
        help="Path to a single task JSON file"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Path to directory containing task JSON files"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("setupbench_output"),
        help="Output directory for results and logs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of tasks to run from dataset"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=7200,
        help="Timeout per task in seconds (default: 2 hours)"
    )

    args = parser.parse_args()

    if not args.task and not args.dataset:
        parser.error("Either --task or --dataset must be specified")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Run tasks
    if args.task:
        # Single task
        result = asyncio.run(run_task(args.task, args.output, args.timeout))
        results = [result]
    else:
        # Dataset
        results = asyncio.run(run_dataset(args.dataset, args.output, args.limit))

    # Generate summary
    generate_summary(results, args.output)


if __name__ == "__main__":
    main()
