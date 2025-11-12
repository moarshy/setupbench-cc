# Smoke Test Tasks

This directory contains 3 smoke test tasks covering different SetupBench categories, all using **ubuntu:22.04** base image.

## Supported Base Images

**We only support ubuntu:22.04 tasks** (77 out of 93 tasks, 82.8% coverage).

### Why Ubuntu-Only?

- **ruby:2.7**: Requires Python 3.10+, but ruby:2.7 has Python 3.9
  - `claude-agent-sdk` has hard requirement for Python ≥3.10
  - Would need to compile Python 3.11 from source (complex)
- **node-16 (custom Azure image)**: Not publicly accessible
  - Private Microsoft registry
  - Cannot pull without access credentials

## Smoke Test Tasks (3 tasks)

| Task | Base Image | Category | Description |
|------|-----------|----------|-------------|
| `1_database_setup.json` | ubuntu:22.04 | Database Setup | PostgreSQL installation and configuration |
| `3_background_service.json` | ubuntu:22.04 | Background Service | File watcher daemon with supervisord |
| `4_repo_setup.json` | ubuntu:22.04 | Repository Setup | Pytesseract library setup |

**Note:** Task `2_dependency_resolution.json` (Ruby/Bundler) is **not supported** and excluded from smoke tests.

## Running Smoke Tests

```bash
# Run all supported smoke tests (3 ubuntu:22.04 tasks)
python run_smoke_test_simple.py
```

This will skip the Ruby task and run only the 3 ubuntu:22.04 tasks.
