#!/usr/bin/env python3
"""
run_agent_in_container.py
==========================

Agent execution script that runs INSIDE Docker containers.

This script is executed within the task's base Docker image (ubuntu:22.04, python:3.9, etc.)
and performs all setup operations in that environment.

Usage:
    python3 /app/run_agent_in_container.py '<task_json>' '<api_key>'

Output:
    - Writes logs to /testbed/.agent_logs/
    - Writes metrics to /testbed/.agent_metrics.json
    - Performs all setup operations in container
"""

import json
import sys
import os
import asyncio
from pathlib import Path

# Add setupbench_runner to path
sys.path.insert(0, '/app')

from setupbench_runner.agent import run_agent
from setupbench_runner.agent_logging import SetupBenchLogger


async def main():
    """Main entry point for in-container agent execution."""

    if len(sys.argv) < 3:
        print("Usage: run_agent_in_container.py '<task_json>' '<api_key>'", file=sys.stderr)
        sys.exit(1)

    # Parse arguments
    task_json = sys.argv[1]
    api_key = sys.argv[2]

    try:
        task = json.loads(task_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing task JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Set API key in environment
    os.environ['ANTHROPIC_API_KEY'] = api_key

    # Setup logging - write to /testbed/.agent_logs/
    log_dir = Path("/testbed/.agent_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = SetupBenchLogger(
        instance_id=task['instance_id'],
        log_dir=log_dir
    )

    logger.log_message(f"Starting in-container agent execution for {task['instance_id']}")
    logger.log_message(f"Base image: {task['base_image']}")
    logger.log_message(f"Task type: {task['task_type']}")
    logger.log_message(f"Working directory: {os.getcwd()}")

    # Run agent with /testbed as workspace
    try:
        total_tokens = await run_agent(
            task=task,
            workspace=Path("/testbed"),
            logger=logger,
            timeout=7200
        )

        # Write metrics to file for harness to collect
        metrics = {
            "total_tokens": total_tokens,
            **logger.get_stats()
        }

        metrics_file = Path("/testbed/.agent_metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        logger.log_message(f"Agent execution completed. Tokens: {total_tokens}")

    except Exception as e:
        logger.log_message(f"Agent execution failed: {e}", level="ERROR")

        # Write error metrics
        metrics = {
            "error": str(e),
            **logger.get_stats()
        }

        metrics_file = Path("/testbed/.agent_metrics.json")
        with open(metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2)

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
