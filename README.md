# SetupBench Runner

A Python package for running Claude Code agent on the SetupBench environment-bootstrap benchmark.

## Features

- ✅ **Two Execution Modes**: Local (for testing) and Docker (SetupBench-compliant)
- ✅ **In-Container Execution**: Agent runs INSIDE Docker containers (matches SetupBench paper)
- ✅ **Comprehensive Logging**: Three-tiered logging system (agent.log, tools.jsonl, messages.jsonl)
- ✅ **Token Tracking**: Full token usage breakdown (input, output, cache creation, cache read)
- ✅ **Fresh Shell Validation**: Matches SetupBench paper methodology exactly
- ✅ **Ubuntu 22.04 Support**: Covers 77/93 tasks (82.8% of SetupBench)

## Execution Modes

### Local Mode (v1 - For Testing Only)

**How it works:**
- Agent runs on your **host system** (macOS, Linux, etc.)
- Bash commands execute on host
- Validation runs in Docker container

**Use when:**
- Quick testing and debugging
- Developing the agent code
- Not evaluating against SetupBench benchmark

**Limitations:**
- ❌ **Does NOT match SetupBench methodology**
- ❌ Agent installs packages on host, validation looks in Docker → failures
- ❌ Results not comparable to SetupBench paper baseline

```bash
python -m setupbench_runner.harness_local --task task.json
```

### Docker Mode (SetupBench-Compliant) ⭐ **RECOMMENDED**

**How it works:**
- Agent runs **INSIDE** Docker container (ubuntu:22.04, python:3.9, etc.)
- All Bash/Read/Write operations happen in container
- Validation runs in same container (fresh shell)

**Use when:**
- Running SetupBench evaluation
- Comparing results to paper baseline
- Producing publishable results

**Benefits:**
- ✅ **Matches SetupBench paper methodology exactly**
- ✅ Agent and validation share same environment
- ✅ Results comparable to paper baseline (62.4% success rate)

```bash
python -m setupbench_runner.harness_docker --task task.json
```

### Why Two Modes?

SetupBench tasks are designed to test agents' ability to bootstrap development environments **from scratch**. The paper's evaluation methodology requires:

> "The harness launches the agent inside a Docker container with the specified base image, then validates setup in a fresh terminal subprocess within the same container."

**Local mode** was our initial implementation but doesn't match this requirement. **Docker mode** is the correct implementation that matches the paper.

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

#### Docker Mode (Recommended for SetupBench evaluation)

```bash
# Single task - Docker mode
python -m setupbench_runner.harness_docker --task path/to/task.json

# Multiple tasks - Docker mode
python -m setupbench_runner.harness_docker --dataset path/to/tasks/ --limit 5

# Example: Run PostgreSQL task from SetupBench scenarios
python -m setupbench_runner.harness_docker --task ../SetupBench/setupbench/scenarios/database_setup.jsonl

# Note: The harness will automatically:
# 1. Build agent Docker image for the task's base_image
# 2. Start container with agent inside
# 3. Execute setup operations in container
# 4. Validate in same container (fresh shell)
```

#### Local Mode (For quick testing only)

```bash
# Single task - Local mode (not SetupBench-compliant)
python -m setupbench_runner.harness_local --task path/to/task.json

# Multiple tasks - Local mode
python -m setupbench_runner.harness_local --dataset path/to/tasks/ --limit 5
```

## Project Structure

```
setupbench-runner/
├── src/setupbench_runner/
│   ├── __init__.py          # Package initialization
│   ├── agent.py             # Claude Code agent core logic
│   ├── agent_logging.py     # Logging infrastructure
│   ├── agent_docker.py      # Docker image building & agent containers
│   ├── docker.py            # Docker container utilities
│   ├── harness_local.py     # Local execution (host-based, for testing)
│   └── harness_docker.py    # Docker execution (SetupBench-compliant)
├── scripts/
│   ├── run_agent_in_container.py  # Agent entry point for Docker execution
│   └── restart_docker.sh          # Docker restart helper (macOS)
├── docs/
│   ├── ARCHITECTURE_FIX.md        # Explanation of execution architecture
│   ├── setupbench-summary.md      # SetupBench paper summary
│   └── benchmark-construction.md  # How SetupBench was built
├── Dockerfile.agent         # Builds agent images on top of base images
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

## How Docker Execution Works (v2)

### Architecture

```
┌──────────────────────────────────────────────────────┐
│              Host System (macOS/Linux)               │
│                                                      │
│  Harness (Python)                                    │
│       │                                              │
│       ├─> Build agent image                         │
│       │   (base_image + Python + Claude SDK)        │
│       │                                              │
│       └─> Start container ──────────────────────┐   │
│                                                  │   │
│  ┌───────────────────────────────────────────┐  │   │
│  │   Docker Container (ubuntu:22.04)         │◄─┘   │
│  │                                           │      │
│  │   /testbed/ (mounted from host)          │      │
│  │   /app/run_agent_in_container.py         │      │
│  │                                           │      │
│  │   ┌─────────────────────────────────┐    │      │
│  │   │  Claude Agent (Python)          │    │      │
│  │   │  - Bash commands in container   │    │      │
│  │   │  - Read/Write in /testbed       │    │      │
│  │   │  - apt-get install postgresql   │    │      │
│  │   │  - API calls to Anthropic       │    │      │
│  │   └─────────────────────────────────┘    │      │
│  │                │                          │      │
│  │                ▼                          │      │
│  │   ┌─────────────────────────────────┐    │      │
│  │   │  Fresh Bash Shell               │    │      │
│  │   │  (validation command)           │    │      │
│  │   │  - psql --version  ✓           │    │      │
│  │   └─────────────────────────────────┘    │      │
│  └───────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Image Building**
   ```bash
   # Harness builds agent image based on task's base_image
   # The agent image includes:
   #   - Python 3 + pip
   #   - Node.js 20.x (required by claude-agent-sdk)
   #   - Claude Code CLI (@anthropic-ai/claude-code)
   #   - Python packages: claude-agent-sdk, python-dotenv, pydantic
   docker build --build-arg BASE_IMAGE=ubuntu:22.04 \
                -t setupbench-agent:ubuntu-22.04 \
                -f Dockerfile.agent .
   ```

   **Note:** The `claude-agent-sdk` Python package requires the Claude Code CLI (Node.js package) to be installed. The Dockerfile.agent handles this automatically.

2. **Container Start**
   ```bash
   # Container started with workspace mounted to /testbed
   docker run -v workspace:/testbed \
              -w /testbed \
              setupbench-agent:ubuntu-22.04
   ```

3. **Agent Execution**
   ```bash
   # Inside container
   python3 /app/run_agent_in_container.py \
           '{"instance_id":"dbsetup-postgresql-1", ...}' \
           'sk-ant-api03-...'
   ```

4. **Validation**
   ```bash
   # Fresh shell in same container
   /bin/bash -c 'psql --version && echo "Setup successful"'
   ```

### Why This Works

✅ **Same Environment**: Agent installs PostgreSQL in container, validation finds it in container
✅ **Persistent Setup**: System packages (apt-get) persist across shells
✅ **Correct Base Image**: Tasks run in their specified environment (ubuntu:22.04, python:3.9, etc.)
✅ **Matches Paper**: Exactly follows SetupBench evaluation methodology

## Key Implementation Details

### Fresh Shell Validation (Critical!)

Following the paper:
> "the harness executes a task-specific validation command in a **fresh terminal subprocess**"

Docker mode implementation:
```python
# In container, fresh shell
container.exec_run(f"/bin/bash -c '{task['success_command']}'", ...)
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

- `docs/setupbench-summary.md` - Overview of SetupBench benchmark
- `docs/setupbench-compliance.md` - SetupBench compliance verification
- `docs/benchmark-construction.md` - How SetupBench dataset was built
- `docs/code-reuse-analysis.md` - Analysis of code reuse opportunities with SetupBench

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
