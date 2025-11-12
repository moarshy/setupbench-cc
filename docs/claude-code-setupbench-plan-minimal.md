# Claude Code on SetupBench: Minimal Implementation Plan

## Key Insight: Keep It Simple

From the SetupBench paper (Section 3.1 - Experimental Setup), the evaluation is **extremely simple**:

> "Each container ran with root privileges and outbound network access, launching a **black-box entry point to the agent** followed by our automated evaluation harness. After the agent completes its final action, the harness executes a task-specific validation command in a **fresh terminal subprocess**."

**What this means:**
1. Agent gets a natural language `problem_statement`
2. Agent runs in a Docker container (from `base_image`)
3. Agent does whatever it needs to do
4. When agent finishes, run `success_command` in **fresh shell**
5. Parse output: "Setup successful" = pass, "Setup failed" = fail

**That's it.** No complex orchestration needed.

---

## Minimal Setup (What We Actually Need)

### 1. Get SetupBench Dataset
```bash
cd /Users/arshath/play/naptha/better-onboarding/setupbench-cc
git clone https://github.com/microsoft/SetupBench
```

The dataset is just JSON files. Each task looks like:
```json
{
  "instance_id": "deps-acts_as_bookable-45b78",
  "problem_statement": "There is a dependency conflict... Please resolve...",
  "success_command": "bundle install --jobs=1 --retry=2 --without development test",
  "base_image": "ruby:2.7",
  "task_type": "dependency_resolution"
}
```

### 2. Create Minimal Agent

The agent needs to:
1. Read `problem_statement` from task JSON
2. Use Claude Code SDK to solve the problem
3. Return when done

**That's it. No Docker management needed** - we can use Claude Code's native workspace functionality.

---

## Implementation: Single Python Script

```python
#!/usr/bin/env python3
"""
Minimal SetupBench runner for Claude Code.
Follows the exact same approach as OpenHands evaluation.
"""

import json
import asyncio
import subprocess
from pathlib import Path
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

# ============================================================================
# System Prompt (matches SetupBench evaluation approach)
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
After you complete the setup, this command will be run in a fresh shell:
```bash
{success_command}
```

This command must output exactly "Setup successful" for the task to pass.

**Important Guidelines:**
1. Install packages persistently (they must work in fresh shells)
2. Don't make assumptions - follow the task exactly
3. Ensure installations persist across shell sessions
4. Test your work before finishing

Use Bash commands to complete this setup task.
"""

# ============================================================================
# Runner
# ============================================================================

async def run_task(task_file: Path, output_dir: Path, timeout: int = 7200):
    """
    Run a single SetupBench task.

    Args:
        task_file: Path to task JSON file
        output_dir: Where to save results
        timeout: Max time in seconds (default: 2 hours like paper)
    """

    # Load task
    with open(task_file) as f:
        task = json.load(f)

    instance_id = task['instance_id']
    print(f"\n{'='*60}")
    print(f"Running: {instance_id}")
    print(f"Type: {task['task_type']}")
    print(f"Image: {task['base_image']}")
    print(f"{'='*60}\n")

    # Create workspace (Docker container or local directory)
    workspace = output_dir / f"workspace_{instance_id}"
    workspace.mkdir(parents=True, exist_ok=True)

    # Configure Claude Code
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT.format(
            base_image=task['base_image'],
            problem_statement=task['problem_statement'],
            success_command=task['success_command']
        ),
        allowed_tools=["Bash", "Read", "Write", "Edit"],
        cwd=str(workspace),
        max_turns=100,  # Allow multi-step problem solving
    )

    # Track metrics
    start_time = asyncio.get_event_loop().time()
    total_tokens = 0
    total_steps = 0

    # Run agent
    async with ClaudeSDKClient(options=options) as client:
        # Send initial task
        await client.query(task['problem_statement'])

        # Collect responses
        async for message in client.receive_response():
            # Count steps and tokens
            total_steps += 1
            # (extract token usage from message if available)

    elapsed = asyncio.get_event_loop().time() - start_time

    # ========================================================================
    # CRITICAL: Validate in FRESH SHELL (like paper does)
    # ========================================================================

    print(f"\nAgent finished. Running validation command in fresh shell...")

    result = subprocess.run(
        ["bash", "-c", task['success_command']],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=120
    )

    output = result.stdout + result.stderr
    success = "Setup successful" in output

    # Save result
    result_data = {
        "instance_id": instance_id,
        "task_type": task['task_type'],
        "success": success,
        "validation_output": output,
        "wall_time_seconds": elapsed,
        "total_steps": total_steps,
        "total_tokens": total_tokens,
    }

    result_file = output_dir / f"{instance_id}_result.json"
    with open(result_file, 'w') as f:
        json.dump(result_data, f, indent=2)

    status = "✅ PASS" if success else "❌ FAIL"
    print(f"\n{status} - {instance_id}")
    print(f"Time: {elapsed:.1f}s | Steps: {total_steps}\n")

    return result_data

# ============================================================================
# Main
# ============================================================================

async def main():
    """Run SetupBench evaluation."""

    # Paths
    dataset_dir = Path("SetupBench/tasks")  # Adjust based on actual repo structure
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)

    # Start with 1 simple task for testing
    task_files = list(dataset_dir.glob("*.json"))[:1]

    print(f"Found {len(task_files)} tasks")

    results = []
    for task_file in task_files:
        result = await run_task(task_file, output_dir)
        results.append(result)

    # Summary
    success_count = sum(1 for r in results if r['success'])
    success_rate = success_count / len(results) * 100

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Tasks: {len(results)}")
    print(f"Success: {success_count} ({success_rate:.1f}%)")
    print(f"Failed: {len(results) - success_count}")

    # Save summary
    summary = {
        "total_tasks": len(results),
        "success_rate": success_rate,
        "results": results
    }

    with open(output_dir / "summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Critical Details from Paper

### 1. Fresh Shell Validation (MOST IMPORTANT)

From paper:
> "the harness executes a task-specific validation command in a **fresh terminal subprocess**"

This is why agents fail! They install things in current shell, but validation runs in **new shell**.

**Our implementation:**
```python
# Run in completely fresh bash process
subprocess.run(["bash", "-c", task['success_command']], ...)
```

### 2. Docker Setup (from paper)

```
Container specs:
- CPU: 16 cores
- Memory: 62 GiB
- Disk: 695 GB
- Root privileges
- Outbound network access
- Timeout: 2 hours
```

**For testing locally:**
- Start with lighter containers
- Use local workspace first
- Only use Docker if needed for base_image

### 3. What Agent Gets (Input)

```json
{
  "problem_statement": "Natural language task description",
  "base_image": "ruby:2.7",
  "success_command": "bundle install --jobs=1 --retry=2 ..."
}
```

**What agent does NOT get:**
- Pre-cloned repository (repo-setup tasks provide repo URL in problem_statement)
- Any installed packages
- Any configuration files
- Any hints beyond the problem statement

### 4. Metrics to Track

From Table 2 in paper:

```python
metrics = {
    "success_rate": bool,           # Did success_command pass?
    "avg_tokens": int,              # Total LLM tokens used
    "avg_steps": int,               # Number of tool calls (bash, read, write, edit)
}
```

---

## Testing Strategy

### Phase 1: Single Task Smoke Test

Pick the simplest task:

```bash
# Find an easy repo-setup task
grep -l "python" SetupBench/tasks/repo-setup/*.json | head -1
```

Run on this ONE task first:
```bash
python run_setupbench.py --task SetupBench/tasks/repo-setup/whisper-task.json
```

**Expected outcome:**
- Agent runs
- Makes some bash commands
- Validation runs in fresh shell
- Either passes or fails (we see why)

### Phase 2: Expand to 5 Tasks

One from each category:
1. Repo setup (easy)
2. Dependency resolution (medium)
3. Database Tier 1 (easy)
4. Database Tier 2 (medium)
5. Background service (medium)

### Phase 3: Full Benchmark

Run all 93 tasks:
```bash
python run_setupbench.py --all --parallel 3
```

---

## Key Differences from Complex Plan

| Complex Plan | Minimal Plan (Actual) |
|-------------|---------------------|
| Build Docker images | Use base images directly |
| Custom orchestration | Simple Python script |
| Complex environment manager | subprocess.run() |
| Multi-file architecture | Single script |
| Custom validation harness | Just run success_command |
| Parallel workers with semaphores | asyncio.gather() |

**Rationale:**
- Paper shows OpenHands used "black-box entry point" - very simple
- Validation is just running a bash command
- No need to over-engineer

---

## Implementation Checklist

### Step 1: Setup (15 min)
- [ ] Clone SetupBench repo
- [ ] Explore dataset structure
- [ ] Pick 1 simple task
- [ ] Read task JSON

### Step 2: Minimal Script (1 hour)
- [ ] Create `run_setupbench.py`
- [ ] Implement task loading
- [ ] Implement Claude Code invocation
- [ ] Implement fresh-shell validation
- [ ] Test on 1 task

### Step 3: Debug & Iterate (2-4 hours)
- [ ] Run on simple task
- [ ] Check agent output
- [ ] Check validation result
- [ ] If failed, understand why
- [ ] Adjust system prompt if needed

### Step 4: Expand (1-2 days)
- [ ] Run on 5 tasks (different categories)
- [ ] Track metrics properly
- [ ] Add result aggregation
- [ ] Compare to paper baselines

### Step 5: Full Run (1-2 days)
- [ ] Run all 93 tasks
- [ ] Analyze failure modes
- [ ] Compare to OpenHands results
- [ ] Write analysis report

---

## Expected Challenges

### 1. Fresh Shell Problem

**Symptom:** Agent installs package, validation fails

**Diagnosis:**
```bash
# In agent shell:
npm install -g foo  # Works
foo --version       # Works

# In fresh shell (validation):
foo --version       # Command not found!
```

**Fix:** Ensure installations persist:
- Use system package managers (apt, yum)
- Update PATH in persistent files (.bashrc, /etc/profile.d/)
- Avoid --user installs without persisting

### 2. Repository Not Cloned

**Symptom:** Task says "setup this repo" but agent has no code

**Diagnosis:** Repo-setup tasks require agent to clone first

**Fix:** Problem statement includes repo URL, agent must:
```bash
git clone https://github.com/owner/repo
cd repo
# Now follow setup instructions
```

### 3. Docker Base Image Issues

**Symptom:** Can't install packages, missing dependencies

**Diagnosis:** Minimal base images don't have apt, git, etc.

**Fix:** Install build tools first:
```bash
apt-get update && apt-get install -y build-essential git curl
```

---

## Success Criteria

**Minimum Viable:**
- ✅ Script runs on 1 task without crashing
- ✅ Validation command executes in fresh shell
- ✅ Result is deterministically pass/fail

**Phase 1 Success:**
- ✅ 1 task from each category completes
- ✅ At least 1 task passes validation
- ✅ Understand why failures happen

**Full Success:**
- ✅ Run all 93 tasks
- ✅ Success rate > 50%
- ✅ Results comparable to OpenHands baseline (34-62%)

**Stretch Goal:**
- ✅ Beat Claude 4 baseline (62.4%)
- ✅ Detailed failure mode analysis
- ✅ Efficiency improvements (fewer wasted steps)

---

## Next Immediate Actions

1. **Clone SetupBench** (5 min)
   ```bash
   cd /Users/arshath/play/naptha/better-onboarding/setupbench-cc
   git clone https://github.com/microsoft/SetupBench
   ```

2. **Explore dataset** (10 min)
   ```bash
   cd SetupBench
   find . -name "*.json" | head -5
   cat [one-of-the-json-files]
   ```

3. **Pick simplest task** (5 min)
   - Find a simple Python repo-setup task
   - Read the problem_statement
   - Read the success_command
   - Manually understand what needs to be done

4. **Create minimal script** (30 min)
   - Just the run_task() function
   - Hard-code the test task
   - Get Claude Code to run
   - See what happens

5. **First validation** (15 min)
   - Run success_command manually first
   - Should fail (nothing is set up)
   - This confirms baseline

Once we have one task working end-to-end, we can expand.

---

## Questions to Answer First

Before coding, let's answer:

1. **Where is the actual dataset?**
   - Look in SetupBench repo structure
   - Are tasks in `/tasks`, `/data`, `/instances`?

2. **Do repo-setup tasks include code?**
   - Or just a problem_statement with repo URL?
   - Check a repo-setup example

3. **How do we run in base_image container?**
   - Do we need Docker locally?
   - Or can Claude Code SDK handle this?

4. **What's in a workspace?**
   - Empty directory?
   - Cloned repo?
   - Depends on task type?

Let's find these answers by exploring SetupBench repo first, then build the minimal script.
