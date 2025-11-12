"""
agent.py
========

Claude Code agent configuration and execution.

Provides:
- System prompt for SetupBench tasks
- Hook creation for logging
- Agent execution logic
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

from .agent_logging import SetupBenchLogger, ToolLogEntry


# ====================================================================================
# System Prompt
# ====================================================================================

SYSTEM_PROMPT = """You are a DevOps engineer setting up a development environment in a {base_image} container.

**Your Task:**
{problem_statement}

**Success Criteria:**
Your work will be validated by running this command in a fresh shell:
```
{success_command}
```

**CRITICAL Guidelines:**

1. **Persistent Installation**: Everything must persist across shell sessions
   - Use system package managers (apt-get, yum, etc.)
   - Install globally, NOT in virtual environments or --user
   - Avoid temporary installations

2. **Complete Setup**: Install ALL required tools
   - Runtime dependencies (Python, Node, databases)
   - Build tools (compilers, headers, build-essential)
   - Test frameworks (pytest, tox, jest, etc.)
   - Don't skip test tooling!

3. **Verify Your Work**: Test installations before finishing
   - Run commands in a new shell to verify persistence
   - Check that the validation command would work

4. **No Assumptions**: This is a bare system
   - Don't assume git, curl, or build-essential are installed
   - Install everything explicitly

Use Bash, Read, Write, and Edit tools to complete this setup task.
"""


# ====================================================================================
# Hook Creation
# ====================================================================================

def create_hooks(logger: SetupBenchLogger) -> Dict[str, Any]:
    """Create hooks for logging all tool calls."""

    async def pre_tool_hook(input_data: Dict[str, Any], tool_use_id: Optional[str],
                           context: Any) -> Dict[str, Any]:  # noqa: ARG001 - Required by hook signature
        """Log before tool execution."""
        tool_name = input_data.get("name", "Unknown")
        tool_input = input_data.get("input", {})

        # Log to human-readable log
        if tool_name == "Bash":
            logger.log_message(f"TOOL CALL: {tool_name}: {tool_input.get('command', '')[:100]}", level="DEBUG")
        elif tool_name in ("Read", "Write", "Edit"):
            logger.log_message(f"TOOL CALL: {tool_name}: {tool_input.get('file_path', '')}", level="DEBUG")
        else:
            logger.log_message(f"TOOL CALL: {tool_name}", level="DEBUG")

        # Log to structured tools.jsonl
        entry = ToolLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="pre_tool",
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id
        )
        logger.log_tool_call(entry)

        return {}

    async def post_tool_hook(result: Dict[str, Any], tool_use_id: Optional[str],
                            context: Any) -> Dict[str, Any]:  # noqa: ARG001 - Required by hook signature
        """Log after tool execution."""
        tool_name = result.get("name", "Unknown")
        tool_output = result.get("output", {})
        error = result.get("error")

        # Log to structured tools.jsonl
        entry = ToolLogEntry(
            timestamp=datetime.now().isoformat(),
            event_type="post_tool",
            tool_name=tool_name,
            tool_input={},
            tool_output=tool_output,
            tool_use_id=tool_use_id,
            error=str(error) if error else None
        )
        logger.log_tool_call(entry)

        return {}

    return {
        'PreToolUse': [HookMatcher(hooks=[pre_tool_hook])],
        'PostToolUse': [HookMatcher(hooks=[post_tool_hook])]
    }


# ====================================================================================
# Agent Execution
# ====================================================================================

async def run_agent(
    task: Dict[str, Any],
    workspace: Path,
    logger: SetupBenchLogger,
    timeout: int = 7200
) -> int:
    """
    Run the Claude Code agent on a task.

    Args:
        task: Task configuration dictionary
        workspace: Working directory for the agent
        logger: Logger instance
        timeout: Maximum execution time in seconds

    Returns:
        Total token usage
    """

    # Verify API key is set
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set. "
            "Please create a .env file with your API key or set it in your environment."
        )

    # Configure agent options
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

    total_tokens = 0

    # Run agent
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

    return total_tokens
