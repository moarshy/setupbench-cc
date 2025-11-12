# SetupBench Smoke Test Suite

This directory contains 4 carefully selected tasks (one from each SetupBench category) for quick validation that the system is working correctly.

## Tasks

| # | Category | Task ID | Base Image | Description |
|---|----------|---------|------------|-------------|
| 1 | Database Setup | `dbsetup-postgresql-1` | ubuntu:22.04 | Install PostgreSQL, create database and user, load schema/seed data |
| 2 | Dependency Resolution | `deps-acts_as_bookable-45b78` | ruby:2.7 | Install Ruby gem dependencies for acts_as_bookable |
| 3 | Background Service | `bgsetup-filewatcher-daemon` | ubuntu:22.04 | Set up file watcher as a daemon/background service |
| 4 | Repo Setup | `pytesseract-df9fce0` | ubuntu:22.04 | Clone and set up pytesseract (OCR library) |

## Base Images

- **ubuntu:22.04**: 3 tasks (database, background service, repo setup)
- **ruby:2.7**: 1 task (dependency resolution)

## Running the Smoke Test

From the project root (`setupbench-cc/`):

```bash
python run_smoke_test.py
```

This will:
1. Run all 4 tasks sequentially
2. Display progress for each task
3. Collect results with base image info
4. Generate a summary report

## Expected Runtime

- Database Setup: ~3-4 minutes
- Dependency Resolution: ~2-3 minutes
- Background Service: ~3-4 minutes
- Repo Setup: ~3-4 minutes

**Total: ~12-15 minutes**

## Output

Results are saved to `smoke_test_results/`:
```
smoke_test_results/
├── results/
│   ├── dbsetup-postgresql-1.json
│   ├── deps-acts_as_bookable-45b78.json
│   ├── bgsetup-filewatcher-daemon.json
│   └── pytesseract-df9fce0.json
├── logs/
│   └── {instance_id}/
│       ├── agent.log
│       ├── tools.jsonl
│       └── messages.jsonl
├── workspaces/
│   └── {instance_id}/
│       └── (task workspace files)
├── summary.json
└── smoke_test_summary.json
```

## Success Criteria

All 4 tasks should pass. Each result includes:
- ✅ Success status
- ⏱️ Execution time
- 🐳 Container base image used
- 📊 Token usage
- 🔧 Tool calls made

## Troubleshooting

If a task fails:

1. Check the agent log: `smoke_test_results/logs/{instance_id}/agent.log`
2. Check validation output in: `smoke_test_results/results/{instance_id}.json`
3. Verify Docker images built correctly: `docker images | grep setupbench-agent`

## Manual Testing

To run individual tasks:

```bash
python -m setupbench_runner.harness_docker \
    --task smoke_test_tasks/1_database_setup.json \
    --output test_output
```
