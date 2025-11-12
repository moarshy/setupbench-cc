# SetupBench Ubuntu Tasks

This directory contains all **77 ubuntu:22.04 tasks** from SetupBench, extracted into individual JSON files for easy access.

## Coverage

**77 out of 93 total SetupBench tasks (82.8%)**

We only support ubuntu:22.04 tasks because:
- `ruby:2.7` requires Python 3.10+ (has Python 3.9)
- `node-16` uses private Azure Container Registry

## Task Distribution

| Category | Count | Description |
|----------|-------|-------------|
| **Database Setup** | 15 | PostgreSQL, MySQL, SQLite, Redis, MongoDB installation and configuration |
| **Background Services** | 8 | Gunicorn, Celery, NGINX, file watchers, autossh daemons |
| **Repository Setup** | 54 | Real-world GitHub repositories across 7 languages |

## Task File Structure

Each JSON file contains:
```json
{
  "instance_id": "unique-task-id",
  "problem_statement": "Natural language task description",
  "success_command": "Validation command that outputs 'Setup successful' or 'Setup failed'",
  "base_image": "ubuntu:22.04",
  "task_type": "dbsetup | bgsetup | reposetup"
}
```

## Running Tasks

### Single Task
```bash
python -m setupbench_runner.harness_docker \
    --task tasks/ubuntu/dbsetup-postgresql-1.json \
    --output results
```

### All Tasks in Category
```bash
# Database setup tasks (15 tasks)
python -m setupbench_runner.harness_docker \
    --dataset tasks/ubuntu \
    --output results

# Or use grep to filter
ls tasks/ubuntu/dbsetup-*.json | while read f; do
    python -m setupbench_runner.harness_docker --task "$f" --output results
done
```

## Source

Tasks extracted from [microsoft/SetupBench](https://github.com/microsoft/SetupBench) repository.
- Paper: arXiv:2507.09063
- Extracted: 2025-11-12
- Version: msbench-0.0.4

## Examples

Some notable tasks:

### Database Setup
- `dbsetup-postgresql-1.json` - Basic PostgreSQL installation
- `dbsetup-mysql-3.json` - Complex MySQL with troubleshooting
- `dbsetup-mongodb-2.json` - MongoDB with import scripts

### Background Services
- `bgsetup-gunicorn-systemd-socket.json` - Gunicorn with Unix sockets
- `bgsetup-celery-redis.json` - Celery worker with Redis backend
- `bgsetup-nginx-reverse-proxy.json` - NGINX configuration

### Repository Setup
- `pytesseract-df9fce0.json` - OCR library setup
- `prometheus-2a6e8f3.json` - Monitoring system setup
- `rust-9df2cbe.json` - Rust compiler project

## Notes

- All tasks use `ubuntu:22.04` base image
- Tasks require agent to install ALL dependencies from scratch
- Validation runs in fresh shell (tests persistence)
- Some tasks include fixture files (see `../SetupBench/setupbench/fixtures/`)
