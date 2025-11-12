"""
SetupBench Runner
=================

A Python package for running SetupBench tasks with Claude Code agent.

Components:
- agent: Claude Code agent configuration and execution
- agent_logging: Comprehensive logging infrastructure
- docker: Docker container support for task execution
- harness: Main orchestration and CLI
"""

__version__ = "0.1.0"

from .agent import run_agent, SYSTEM_PROMPT
from .agent_logging import SetupBenchLogger, ToolLogEntry
from .docker import DockerContainer, copy_fixtures, DOCKER_AVAILABLE

__all__ = [
    "run_agent",
    "SYSTEM_PROMPT",
    "SetupBenchLogger",
    "ToolLogEntry",
    "DockerContainer",
    "copy_fixtures",
    "DOCKER_AVAILABLE",
]
