# SetupBench Runner

A Python package for running Claude Code agent on the SetupBench environment-bootstrap benchmark.

## Features

- ✅ **Modular Architecture**: Clean separation of concerns (agent, logging, docker, harness)
- ✅ **Comprehensive Logging**: Three-tiered logging system (agent.log, tools.jsonl, messages.jsonl)
- ✅ **Docker Support**: Run tasks in proper containerized environments
- ✅ **Token Tracking**: Full token usage extraction from Claude Agent SDK 2.0
- ✅ **Fresh Shell Validation**: Matches SetupBench paper methodology exactly

## Quick Start

### 1. Install UV

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install the Package

```bash
# Sync dependencies and install package
uv sync
```

### 3. Set Up API Key

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Anthropic API key
# Get your API key from: https://console.anthropic.com/settings/keys
nano .env
```

Your `.env` file should look like:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### 4. Clone SetupBench

```bash
git clone https://github.com/microsoft/SetupBench
# The runner will automatically find SetupBench in parent or sibling directories
```

### 5. Run Tasks

```bash
# Single task
setupbench-runner --task path/to/task.json

# Multiple tasks
setupbench-runner --dataset path/to/tasks/ --limit 5

# All tasks
setupbench-runner --dataset path/to/tasks/
```

## Project Structure

```
setupbench-runner/
├── src/setupbench_runner/
│   ├── __init__.py          # Package initialization
│   ├── agent.py             # Claude Code agent logic
│   ├── agent_logging.py     # Logging infrastructure
│   ├── docker.py            # Docker container support
│   └── harness.py           # Main orchestration & CLI
├── scripts/
│   └── restart_docker.sh    # Docker restart helper (macOS)
├── docs/                    # Documentation
├── pyproject.toml           # Package configuration
└── README.md                # This file
```

## Output Structure

```
setupbench_output/
├── results/
│   ├── task-id-1.json          # Per-task results
│   ├── task-id-2.json
│   └── ...
├── logs/
│   ├── task-id-1/
│   │   ├── agent.log           # Human-readable log
│   │   ├── tools.jsonl         # All tool calls (for step counting)
│   │   └── messages.jsonl      # Full conversation
│   ├── task-id-2/
│   └── ...
├── workspaces/
│   ├── task-id-1/              # Agent workspace (files created)
│   └── ...
└── summary.json                # Overall statistics
```

## Metrics Collected

Each task result includes:

```json
{
  "instance_id": "task-identifier",
  "success": true,
  "total_steps": 15,              // Number of tool calls (Bash, Read, Write, Edit)
  "bash_calls": 8,                // Bash commands executed
  "total_tokens": 25000,          // LLM tokens used
  "wall_time_seconds": 45.3,      // Execution time
  "validation_output": "Setup successful",
  "logs": {
    "tools_log": "path/to/tools.jsonl",
    "messages_log": "path/to/messages.jsonl"
  }
}
```

## Analyzing Results

### View Summary
```bash
cat setupbench_output/summary.json | jq
```

### Count Tool Calls for a Task
```bash
# Count all tool calls
cat setupbench_output/logs/task-id/tools.jsonl | wc -l

# Count bash calls only
cat setupbench_output/logs/task-id/tools.jsonl | jq 'select(.tool_name == "Bash")' | wc -l
```

### View Full Conversation
```bash
cat setupbench_output/logs/task-id/messages.jsonl | jq
```

### Check Failures
```bash
# List all failed tasks
cat setupbench_output/summary.json | jq '.results[] | select(.success == false) | .instance_id'
```

## Comparison to Baseline

From SetupBench paper (Table 2):

| Model | Success Rate | Avg Tokens | Avg Steps |
|-------|-------------|------------|-----------|
| Claude 4 | 62.4% | 1129K | 47.1 |
| Claude 3.7 | 57.0% | 869K | 35.7 |
| GPT-4.1 | 50.5% | 436K | 29.5 |

Run on the full benchmark to compare!

## Key Implementation Details

### Fresh Shell Validation (Critical!)

Following the paper:
> "the harness executes a task-specific validation command in a **fresh terminal subprocess**"

Our implementation:
```python
subprocess.run(["bash", "-c", task['success_command']], cwd=workspace, ...)
```

This is why many agents fail - they install packages that work in their shell but don't persist!

### System Prompt

Explicitly instructs the agent to:
1. Install packages persistently (use system package managers)
2. Install ALL tools (runtime + test frameworks)
3. Verify installations work in fresh shells
4. Don't assume anything is pre-installed

### Logging

- **agent.log**: Human-readable log
- **tools.jsonl**: Every tool call with input/output (for counting steps)
- **messages.jsonl**: Full Claude conversation (for token analysis)

## Next Steps

1. **Test on 1 task**: Verify everything works
2. **Run on 5 tasks**: One from each category
3. **Analyze failures**: Understand failure modes
4. **Full benchmark**: Run all 93 tasks
5. **Compare results**: Against OpenHands baseline

## Documentation

- `docs/setupbench-summary.md` - Overview of SetupBench
- `docs/benchmark-construction.md` - How dataset was built
- `docs/claude-code-setupbench-plan-minimal.md` - Implementation plan

## Troubleshooting

### "Claude SDK not found"
```bash
uv sync
```

### "Task file not found"
Make sure you cloned SetupBench and the task path is correct:
```bash
ls SetupBench/tasks/  # Should show .json files
```

### Agent times out
Increase timeout (default 2 hours):
```python
await run_task(task_file, output_dir, timeout=7200)  # seconds
```

### Want to see live agent output
Check the agent.log file in real-time:
```bash
tail -f setupbench_output/logs/task-id/agent.log
```
