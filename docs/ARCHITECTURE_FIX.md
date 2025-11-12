# Architecture Fix: Running Claude Code Inside Docker

## Problem Statement

Our current implementation has a critical architectural flaw: the Claude Code agent runs on the **host system** (macOS), but SetupBench tasks require the agent to run **inside** Docker containers.

### Current (Incorrect) Flow

```
┌─────────────────────────────────────┐
│        macOS Host System            │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Claude Agent (Python)      │  │
│  │   - Executes Bash on macOS   │  │
│  │   - Read/Write on macOS      │  │
│  │   - API calls to Anthropic   │  │
│  └──────────────────────────────┘  │
│               │                     │
│               │ Workspace mounted   │
│               ▼                     │
│  ┌──────────────────────────────┐  │
│  │   Docker Container           │  │
│  │   (ubuntu:22.04)             │  │
│  │   - Only validation runs     │  │
│  │   - No agent activity        │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘

Result: Agent installs PostgreSQL on macOS,
        but validation looks for it in Docker → FAIL
```

### SetupBench Expected Flow

```
┌─────────────────────────────────────┐
│        macOS Host System            │
│                                     │
│  ┌──────────────────────────────┐  │
│  │   Docker Container           │  │
│  │   (ubuntu:22.04)             │  │
│  │                              │  │
│  │  ┌────────────────────────┐  │  │
│  │  │  Claude Agent (Python) │  │  │
│  │  │  - Bash in container   │  │  │
│  │  │  - Read/Write in /testbed │ │
│  │  │  - API calls to Anthropic │ │
│  │  └────────────────────────┘  │  │
│  │               │              │  │
│  │               ▼              │  │
│  │  ┌────────────────────────┐  │  │
│  │  │  Fresh Shell           │  │  │
│  │  │  (validation)          │  │  │
│  │  └────────────────────────┘  │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘

Result: Agent installs PostgreSQL in container,
        validation finds it → SUCCESS
```

## Why This Matters

1. **Installation Persistence**: When agent runs `apt-get install postgresql` on macOS, it fails or installs in wrong place
2. **Base Image Requirements**: Tasks specify `ubuntu:22.04`, `python:3.9`, etc. - agent must run in those environments
3. **Fresh Shell Validation**: Validation runs in Docker, so setup must also happen in Docker

## Solution: Run Agent Inside Docker

### Approach

1. **Build Agent Docker Image**: Create image with Python + Claude SDK + dependencies
2. **Layer on Base Image**: Use task's base_image (ubuntu:22.04, etc.) and install agent on top
3. **Execute Agent in Container**: Run Python script inside container
4. **Mount Workspace**: Container writes to /testbed (mounted from host)
5. **Validate in Same Container**: Fresh shell validation in same environment

### Implementation Steps

#### Step 1: Create Agent Dockerfile

```dockerfile
# Build on task's base image (e.g., ubuntu:22.04)
ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

# Install Python 3 and pip if not present
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Agent SDK and dependencies
RUN pip3 install --no-cache-dir \
    claude-agent-sdk \
    python-dotenv \
    pydantic

# Copy agent code
COPY src/setupbench_runner /app/setupbench_runner
WORKDIR /testbed

# Environment for API key
ENV ANTHROPIC_API_KEY=""

# Agent will be invoked with: python3 /app/run_agent_in_container.py
```

#### Step 2: Create In-Container Agent Script

```python
# scripts/run_agent_in_container.py

import json
import sys
import asyncio
from pathlib import Path
from setupbench_runner.agent import run_agent
from setupbench_runner.agent_logging import SetupBenchLogger

async def main():
    # Task JSON passed as first argument
    task_json = sys.argv[1]
    task = json.loads(task_json)

    # Setup logging (write to /testbed/.agent_logs/)
    logger = SetupBenchLogger(
        task['instance_id'],
        Path("/testbed/.agent_logs")
    )

    # Run agent with /testbed as workspace
    await run_agent(
        task,
        workspace=Path("/testbed"),
        logger=logger,
        timeout=7200
    )

if __name__ == "__main__":
    asyncio.run(main())
```

#### Step 3: Modify Harness to Use Docker Execution

```python
# In harness.py

async def run_task(task_file: Path, output_dir: Path, timeout: int = 7200):
    """Run task with agent executing inside Docker."""

    # Load task
    task = json.load(open(task_file))

    # Build agent image based on task's base_image
    agent_image = build_agent_image(task['base_image'])

    # Create workspace and copy fixtures
    workspace = output_dir / "workspaces" / task['instance_id']
    workspace.mkdir(parents=True, exist_ok=True)
    copy_fixtures(task, workspace, setupbench_root)

    # Start container
    with DockerContainer(agent_image, workspace, task['instance_id']) as container:
        # Run agent INSIDE container
        exit_code, stdout, stderr = container.exec(
            f"python3 /app/run_agent_in_container.py '{json.dumps(task)}'"
        )

        # Agent logs are in workspace/.agent_logs/
        # Copy them to output_dir/logs/

        # Run validation in same container (fresh shell)
        exit_code, stdout, stderr = container.exec(
            task['success_command']
        )

        success = "Setup successful" in (stdout + stderr)

    return create_result(task, success, stdout, ...)
```

#### Step 4: Build Agent Images

```bash
# Build for each unique base image
docker build \
    --build-arg BASE_IMAGE=ubuntu:22.04 \
    -t setupbench-agent:ubuntu-22.04 \
    -f Dockerfile.agent \
    .

docker build \
    --build-arg BASE_IMAGE=python:3.9 \
    -t setupbench-agent:python-3.9 \
    -f Dockerfile.agent \
    .
```

## Benefits of This Approach

1. ✅ **Correct Execution Model**: Matches SetupBench paper methodology
2. ✅ **Any Base Image**: Works with ubuntu:22.04, python:3.9, ruby:2.7, etc.
3. ✅ **Persistent Installations**: Everything installed in container stays there for validation
4. ✅ **Isolated Environment**: Each task runs in clean container
5. ✅ **Easy Debugging**: Can exec into container to inspect state

## Alternative Considered: Command Proxying

We considered keeping agent on host and proxying Bash commands to Docker via `docker exec`.

**Problems:**
- Claude SDK's Bash tool directly executes on host - can't easily intercept
- File operations (Read/Write) would need complex mounting logic
- Environment variables, working directory would be inconsistent

**Verdict:** Running agent inside Docker is cleaner and more correct.

## Migration Plan

### Phase 1: Build Infrastructure (1-2 hours)
1. Create Dockerfile.agent
2. Create run_agent_in_container.py script
3. Build test images for ubuntu:22.04 and python:3.9

### Phase 2: Modify Harness (2-3 hours)
1. Add image building logic
2. Modify run_task() to execute agent in container
3. Handle log collection from container

### Phase 3: Testing (2-4 hours)
1. Test with test-simple-echo (sanity check)
2. Test with dbsetup-postgresql-1
3. Test with one task from each category
4. Compare results to current baseline

### Phase 4: Full Evaluation (8-12 hours)
1. Run all 93 tasks
2. Calculate success rate
3. Compare to SetupBench paper baseline (62.4%)

## Expected Improvements

With correct execution model:
- **PostgreSQL tasks**: Should now pass (currently failing due to macOS execution)
- **All database tasks**: Should work correctly
- **Dependency resolution**: Should work correctly
- **Repository setup**: Should improve significantly

**Estimated success rate improvement**: 0% → 40-50% (conservative estimate)

## Next Steps

1. Create Dockerfile.agent
2. Create run_agent_in_container.py
3. Test with single task to verify approach
4. Full implementation if successful
