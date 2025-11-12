# Implementation Summary: Claude Code on SetupBench

## What We Built

A minimal, clean implementation to run Claude Code on the SetupBench benchmark, following the exact evaluation methodology from the paper.

## Key Files

### 1. `run_setupbench.py` - Main Runner (450 lines)

**Core functionality:**
- Load SetupBench task JSONs
- Run Claude Code agent with task `problem_statement`
- Validate with `success_command` in **fresh shell** (critical!)
- Log everything for metrics calculation

**Architecture:**
```python
run_task(task_file):
    1. Load task JSON
    2. Create logger (logs/, workspaces/, results/)
    3. Configure Claude Code with system prompt + hooks
    4. Run agent (collect messages)
    5. Validate in fresh subprocess
    6. Save result + metrics
```

### 2. Logging System (Based on Example Code)

**Three log files per task:**

1. **`agent.log`** - Human-readable log
   ```
   [2025-01-14T10:30:45] [INFO] Starting task: deps-acts_as_bookable-45b78
   [2025-01-14T10:30:47] [DEBUG] TOOL CALL: Bash: apt-get update
   [2025-01-14T10:30:50] [DEBUG] TOOL CALL: Read: Gemfile
   ```

2. **`tools.jsonl`** - Structured tool calls (for step counting)
   ```json
   {"timestamp": "...", "event_type": "pre_tool", "tool_name": "Bash", "tool_input": {...}}
   {"timestamp": "...", "event_type": "post_tool", "tool_name": "Bash", "tool_output": {...}}
   ```

3. **`messages.jsonl`** - Full conversation (for token counting)
   ```json
   {"timestamp": "...", "role": "user", "content": "..."}
   {"timestamp": "...", "role": "assistant", "content": [{...}]}
   ```

### 3. Metrics Collection

**Matches SetupBench paper (Table 2):**

```python
{
    "success": bool,              # Pass/fail
    "total_steps": int,           # Tool call count
    "bash_calls": int,           # Bash commands
    "total_tokens": int,         # LLM tokens
    "wall_time_seconds": float   # Execution time
}
```

## Design Decisions

### 1. Fresh Shell Validation (Most Critical!)

**From paper:**
> "the harness executes a task-specific validation command in a **fresh terminal subprocess**"

**Our implementation:**
```python
subprocess.run(["bash", "-c", task['success_command']], cwd=workspace, ...)
```

This is why agents fail - installations must persist across shells!

### 2. System Prompt

**Key instructions:**
- Install packages persistently (system package managers)
- Install ALL tools (runtime + test frameworks)
- Verify work in fresh shells
- No assumptions about pre-installed packages

**Example:**
```python
SYSTEM_PROMPT = """
You are a DevOps engineer in a fresh {base_image} container.

CRITICAL Guidelines:
1. **Persistence**: Use apt-get, not --user installs
2. **Complete Setup**: Install test frameworks too (tox, pytest, etc.)
3. **Verify**: Test in fresh shell before finishing
4. **No Assumptions**: Install git, curl, build-essential explicitly
"""
```

### 3. Logging with Hooks

**Uses Claude SDK hooks (like example code):**
- `PreToolUse` - Log before tool execution
- `PostToolUse` - Log after tool execution + errors

**Statistics tracked:**
```python
{
    "total_tool_calls": int,
    "bash_calls": int,
    "read_calls": int,
    "write_calls": int,
    "edit_calls": int,
    "errors": int,
    "messages": int
}
```

### 4. Pydantic Models

**Using Pydantic instead of dataclasses:**
```python
class ToolLogEntry(BaseModel):
    timestamp: str
    event_type: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    tool_use_id: Optional[str] = None
    error: Optional[str] = None

# Serialize with:
entry.model_dump_json()
```

## Usage

### Quick Start
```bash
# Single task
python run_setupbench.py --task SetupBench/tasks/example.json

# Multiple tasks
python run_setupbench.py --dataset SetupBench/tasks --limit 5

# All 93 tasks
python run_setupbench.py --dataset SetupBench/tasks
```

### Output Structure
```
setupbench_output/
├── results/
│   ├── task-1.json          # Individual results
│   └── task-2.json
├── logs/
│   ├── task-1/
│   │   ├── agent.log        # Human-readable
│   │   ├── tools.jsonl      # Step counting
│   │   └── messages.jsonl   # Full conversation
│   └── task-2/
├── workspaces/
│   └── task-1/              # Agent workspace
└── summary.json             # Aggregate stats
```

## Comparison to Baseline

**SetupBench paper results (Table 2):**

| Model | Success Rate | Avg Tokens | Avg Steps |
|-------|-------------|------------|-----------|
| Claude 4 | **62.4%** | 1129K | 47.1 |
| Claude 3.7 | 57.0% | 869K | 35.7 |
| GPT-4.1 | 50.5% | 436K | 29.5 |

**Our goal:**
- Match or beat 62.4% success rate
- Understand failure modes
- Improve efficiency (reduce wasted steps)

## Analysis Tools

### Count steps
```bash
# Total tool calls
cat logs/task-1/tools.jsonl | wc -l

# Bash calls only
cat logs/task-1/tools.jsonl | jq 'select(.tool_name == "Bash")' | wc -l
```

### View failures
```bash
# List failed tasks
cat summary.json | jq '.results[] | select(.success == false) | .instance_id'

# See why a task failed
cat results/task-1.json | jq '.validation_output'
```

### Analyze agent behavior
```bash
# View full conversation
cat logs/task-1/messages.jsonl | jq

# See all bash commands
cat logs/task-1/tools.jsonl | jq 'select(.tool_name == "Bash") | .tool_input.command'
```

## Key Differences from Complex Plan

| Original Plan | Actual Implementation |
|--------------|----------------------|
| Multi-file architecture | Single 450-line script |
| Custom Docker manager | Use Claude SDK's workspace |
| Complex orchestration | Simple asyncio |
| Custom validation harness | subprocess.run() |
| Separate result schemas | Dict with standard fields |

**Why simpler is better:**
- Paper shows OpenHands used "black-box entry point"
- Easier to debug and understand
- Follows example code patterns
- Less code to maintain

## Next Steps

### Phase 1: Smoke Test (1 hour)
1. Clone SetupBench
2. Pick simplest task
3. Run `python run_setupbench.py --task ...`
4. Verify logging works
5. Check if task passes/fails

### Phase 2: Category Test (2-4 hours)
1. Run 1 task from each category (5 total)
2. Analyze failures
3. Adjust system prompt if needed
4. Compare step counts to paper

### Phase 3: Full Benchmark (1-2 days)
1. Run all 93 tasks
2. Calculate success rate by category
3. Compare to baseline (62.4%)
4. Analyze failure modes
5. Write analysis report

## Expected Challenges

### 1. Non-Persistent Installations

**Symptom:** Agent installs package, validation fails

**Example:**
```bash
# Agent's shell:
npm install -g foo  # Works
foo --version       # Works

# Fresh shell (validation):
foo --version       # Command not found!
```

**Fix:** System prompt emphasizes persistence

### 2. Missing Test Tools

**Symptom:** Runtime deps installed, but tox/pytest missing

**Example:**
```bash
apt-get install python3  # Runtime OK
python3 --version        # Works
tox                      # Not found!
```

**Fix:** System prompt says "Install ALL tools including test frameworks"

### 3. Dependency Conflicts

**Symptom:** Agent stuck in dependency resolution

**Fix:** May need task-specific hints or increased timeout

## Success Metrics

**Minimum Viable:**
- ✅ Script runs without crashes
- ✅ Logs are generated correctly
- ✅ At least 1 task passes

**Phase 1 Success:**
- ✅ 50%+ success rate on initial 5 tasks
- ✅ Logs are complete and parseable
- ✅ Can count steps accurately

**Full Success:**
- ✅ >60% success rate on all 93 tasks
- ✅ Detailed failure mode analysis
- ✅ Comparable or better than baseline

## References

- **SetupBench Paper**: arXiv:2507.09063v1 [cs.SE]
- **SetupBench Repo**: https://github.com/microsoft/SetupBench
- **Example Code**: `setupbench-cc/example-claude-code/`
- **Docs**: `setupbench-cc/docs/`
