#!/usr/bin/env python3
"""
harness_v2.py
=============

SetupBench harness with IN-CONTAINER agent execution (correct architecture).

This version runs the Claude Code agent INSIDE the Docker container, matching
the SetupBench paper methodology.

Key differences from v1:
- Agent executes inside container, not on host
- All Bash/Read/Write operations happen in container environment
- Validation runs in same container (fresh shell)
- Results match SetupBench paper baseline
"""

import json
import os
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv

from .agent_docker import build_agent_image, AgentContainer, DOCKER_AVAILABLE
from .docker import copy_fixtures

# Load environment variables
load_dotenv()


# ====================================================================================
# Task Execution
# ====================================================================================

async def run_task_v2(
    task_file: Path,
    output_dir: Path,
    timeout: int = 7200
) -> Dict[str, Any]:
    """
    Run a single SetupBench task with agent executing inside Docker.

    Args:
        task_file: Path to task JSON file
        output_dir: Where to save results and logs
        timeout: Max time in seconds (default: 2 hours)

    Returns:
        Dictionary with task result and metrics
    """

    if not DOCKER_AVAILABLE:
        raise RuntimeError(
            "Docker is required for SetupBench evaluation. "
            "Install with: pip install docker"
        )

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please create a .env file with your API key."
        )

    # Load task
    with open(task_file) as f:
        task = json.load(f)

    instance_id = task['instance_id']
    base_image = task['base_image']

    print(f"\n{'='*70}")
    print(f"Task: {instance_id}")
    print(f"Type: {task['task_type']}")
    print(f"Base Image: {base_image}")
    print(f"{'='*70}\n")

    # Create workspace
    workspace = output_dir / "workspaces" / instance_id
    workspace.mkdir(parents=True, exist_ok=True)

    # Copy fixtures if they exist
    setupbench_paths = [
        Path("../SetupBench"),
        Path("SetupBench"),
        Path.cwd().parent / "SetupBench"
    ]

    for setupbench_root in setupbench_paths:
        if setupbench_root.exists():
            copy_fixtures(task, workspace, setupbench_root)
            break

    # Build agent Docker image
    print(f"\n📦 Preparing agent image...")
    try:
        agent_image = build_agent_image(base_image)
    except Exception as e:
        print(f"✗ Failed to build agent image: {e}")
        return create_error_result_v2(task, output_dir, str(e))

    # Track metrics
    start_time = datetime.now()

    # Run agent inside Docker container
    print(f"\n🚀 Starting agent execution in container...")

    try:
        with AgentContainer(agent_image, workspace, instance_id, api_key) as container:

            # Run agent
            exit_code, stdout, stderr = container.run_agent(task)

            if exit_code != 0:
                error_msg = f"Agent execution failed: {stderr[:500]}"
                return create_error_result_v2(task, output_dir, error_msg)

            # Collect metrics from container
            metrics = container.collect_metrics()

            # Run validation in fresh shell (same container)
            print(f"\n✓ Running validation command...")
            success, validation_output = container.run_validation(task['success_command'])

            # Collect logs from container
            print(f"\n📋 Collecting logs...")
            log_files = container.collect_logs(output_dir)

    except Exception as e:
        print(f"✗ Container execution error: {e}")
        return create_error_result_v2(task, output_dir, str(e))

    elapsed = (datetime.now() - start_time).total_seconds()

    # Create result
    result_data = {
        "instance_id": instance_id,
        "task_type": task['task_type'],
        "base_image": base_image,
        "success": success,
        "validation_output": validation_output[:1000],  # Limit output size
        "wall_time_seconds": elapsed,
        "total_steps": metrics.get("total_tool_calls", 0),
        "bash_calls": metrics.get("bash_calls", 0),
        "read_calls": metrics.get("read_calls", 0),
        "write_calls": metrics.get("write_calls", 0),
        "edit_calls": metrics.get("edit_calls", 0),
        "total_tokens": metrics.get("total_tokens", 0),
        "errors": metrics.get("errors", 0),
        "messages": metrics.get("messages", 0),
        "logs": {k: str(v) for k, v in log_files.items()}
    }

    # Save individual result
    result_file = output_dir / "results" / f"{instance_id}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with result_file.open("w") as f:
        json.dump(result_data, f, indent=2)

    # Print summary
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - {instance_id}")
    print(f"Time: {elapsed:.1f}s | Steps: {result_data['total_steps']} | "
          f"Tokens: {result_data['total_tokens']/1000:.1f}K")
    print(f"{'='*70}\n")

    return result_data


def create_error_result_v2(
    task: Dict[str, Any],
    output_dir: Path,
    error_msg: str
) -> Dict[str, Any]:
    """Create a result dict for a task that errored."""

    return {
        "instance_id": task['instance_id'],
        "task_type": task['task_type'],
        "base_image": task['base_image'],
        "success": False,
        "validation_output": f"Error: {error_msg}",
        "wall_time_seconds": 0,
        "total_steps": 0,
        "bash_calls": 0,
        "read_calls": 0,
        "write_calls": 0,
        "edit_calls": 0,
        "total_tokens": 0,
        "errors": 1,
        "messages": 0,
        "logs": {}
    }


# ====================================================================================
# Batch Execution
# ====================================================================================

async def run_dataset_v2(
    dataset_dir: Path,
    output_dir: Path,
    limit: int = None
) -> List[Dict[str, Any]]:
    """Run multiple tasks from a directory."""
    task_files = sorted(dataset_dir.glob("*.json"))[:limit] if limit else sorted(dataset_dir.glob("*.json"))

    print(f"Found {len(task_files)} tasks to run\n")

    results = []
    for task_file in task_files:
        result = await run_task_v2(task_file, output_dir)
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
    print("SETUPBENCH RESULTS (In-Container Execution)")
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
        description="Run SetupBench tasks with in-container Claude Code agent"
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
        default=Path("setupbench_output_v2"),
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
        result = asyncio.run(run_task_v2(args.task, args.output, args.timeout))
        results = [result]
    else:
        # Dataset
        results = asyncio.run(run_dataset_v2(args.dataset, args.output, args.limit))

    # Generate summary
    generate_summary(results, args.output)


if __name__ == "__main__":
    main()
