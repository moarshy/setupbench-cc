"""
agent_logging.py
================

Logging infrastructure for SetupBench agent execution.

Provides comprehensive logging across three files:
1. agent.log - Human-readable log
2. tools.jsonl - Structured tool calls for step counting
3. messages.jsonl - Full conversation for token analysis
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from pydantic import BaseModel


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
        self.instance_id = instance_id
        self.log_dir = log_dir / instance_id
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Three log files
        self.agent_log = self.log_dir / "agent.log"
        self.tools_log = self.log_dir / "tools.jsonl"
        self.messages_log = self.log_dir / "messages.jsonl"

        # Statistics
        self.stats = {
            "total_tool_calls": 0,
            "bash_calls": 0,
            "read_calls": 0,
            "write_calls": 0,
            "edit_calls": 0,
            "errors": 0,
            "messages": 0
        }

    def log_message(self, message: str, level: str = "INFO") -> None:
        """Write to human-readable log file."""
        timestamp = datetime.now().isoformat()
        log_line = f"[{timestamp}] [{level}] {message}\n"

        with self.agent_log.open("a") as f:
            f.write(log_line)

    def log_tool_call(self, entry: ToolLogEntry) -> None:
        """Log a tool call to tools.jsonl."""
        with self.tools_log.open("a") as f:
            f.write(entry.model_dump_json() + "\n")

        # Update statistics
        if entry.event_type == "pre_tool":
            self.stats["total_tool_calls"] += 1

            tool_name = entry.tool_name.lower()
            if tool_name == "bash":
                self.stats["bash_calls"] += 1
            elif tool_name == "read":
                self.stats["read_calls"] += 1
            elif tool_name == "write":
                self.stats["write_calls"] += 1
            elif tool_name == "edit":
                self.stats["edit_calls"] += 1

        if entry.error:
            self.stats["errors"] += 1

    def log_claude_message(self, role: str, content: Any) -> None:
        """Log a Claude message to messages.jsonl."""
        message = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content
        }

        with self.messages_log.open("a") as f:
            json.dump(message, f)
            f.write("\n")

        self.stats["messages"] += 1

    def get_stats(self) -> Dict[str, int]:
        """Return current statistics."""
        return self.stats.copy()
