# SetupBench: Benchmark Construction Methodology

## Overview

SetupBench was built through a combination of manual curation, automated mining from GitHub, and LLM-assisted generation. The 93-instance benchmark required careful validation to ensure each task is solvable and deterministically evaluable.

## Construction Process by Category

### 1. Repository Setup (54 instances)

#### Selection Criteria
- Popular repositories across 7 languages: Python, TypeScript, JavaScript, Go, Rust, Java, C++
- Non-trivial setup requirements (not just `pip install`)
- Active maintenance and good documentation

#### Construction Steps

**Step 1: Manual Documentation**
- Authors manually followed project documentation to identify all setup steps
- Documented dependencies, build tools, environment variables, etc.

**Step 2: Validation Command Generation (LLM-Assisted)**
- Used LLMs with repository context from scraped Markdown files
- Generated deterministic one-line validation commands
- Example for prometheus/prometheus:
  ```bash
  curl -s http://localhost:9090/metrics | grep -q 'prometheus_build_info' && echo 'Setup successful' || echo 'Setup failed'
  ```

**Step 3: End-to-End Validation**
- Tested in fresh sandboxes to ensure validation works correctly
- Only included instances that reliably returned "Setup successful" when correct and "Setup failed" otherwise

#### LLM Prompts Used

**Prompt 1: Setup-Instruction Derivation**
```
You are tasked with analyzing a GitHub repository and providing detailed
setup instructions for a project. This is part of a benchmark to evaluate
autonomous software engineering agents on their ability to set up projects
correctly. ...

<repo_url> https://github.com/ceph/ceph </repo_url>

1. Thoroughly analyze the repository documentation ...
2. Based on your analysis, provide a detailed, step-by-step guide ...
3. Determine a "success_criteria_command" that can be used to verify ...

Note: the sandbox is Ubuntu 22.04 with nothing pre-installed.
```

**Prompt 2: Success-Command Synthesis**
```
You are tasked with creating a success command for a software engineering
benchmark. This command will be used to evaluate whether a repository has been
correctly set up and configured.

Repository URL: {{ repo_url }}
Markdown files from the repository: {{ markdown_files }}

Guidelines:
1. Echo 'Setup successful' or 'Setup failed'.
2. Only succeed if the repo is fully configured.
3. Test a key functionality or component.
4. Chain commands with && and if necessary.
```

### 2. Dependency Resolution (16 instances)

This category captures real-world dependency conflicts reported by developers.

#### Mining Process

**Step 1: GitHub Issue Mining**

Used a Python script to search GitHub issues for dependency conflict patterns:

```python
ECOSYSTEMS = {
    "npm-peer-dep": {
        "search_query": "npm ERR! peer dep is:issue in:comments state:closed language:JavaScript",
        "regex": re.compile(r"npm ERR! peer dep", re.IGNORECASE),
        "manifest": "package.json",
        "lockfiles": ["package-lock.json", "yarn.lock"],
    },
    "npm-eresolve": {
        "search_query": "npm ERR! code ERESOLVE is:issue in:comments state:closed language:JavaScript",
        "regex": re.compile(r"npm ERR! code ERESOLVE", re.IGNORECASE),
        "manifest": "package.json",
        "lockfiles": ["package-lock.json", "yarn.lock"],
    },
    "pip-conflict": {
        "search_query": "ERROR: Could not install is:issue in:comments state:closed language:Python",
        "regex": re.compile(r"ERROR: (?:Could not install|ResolutionImpossible)", re.IGNORECASE),
        "manifest": "requirements.txt",
        "lockfiles": ["Pipfile.lock", "poetry.lock"],
    },
    "poetry-conflict": {
        "search_query": "ResolutionImpossible is:issue in:comments state:closed language:Python",
        "regex": re.compile(r"ResolutionImpossible", re.IGNORECASE),
        "manifest": "pyproject.toml",
        "lockfiles": ["poetry.lock"],
    },
    "bundler-compat": {
        "search_query": "Bundler could not find compatible versions is:issue in:comments state:closed language:Ruby",
        "regex": re.compile(r"Bundler could not find compatible versions", re.IGNORECASE),
        "manifest": "Gemfile",
        "lockfiles": ["Gemfile.lock"],
    },
}
```

**Key Requirements**:
- Closed issues (indicating the conflict was real and resolved)
- Lock files must be present (package-lock.json, Gemfile.lock, poetry.lock, etc.)
- Error messages matched specific regex patterns

**Step 2: Filtering**

For each mined issue:
1. Extract the commit at issue creation time (base_commit)
2. Verify at least one lock file exists at that commit
3. Extract error snippet from issue comments
4. Record metadata: repo, issue number, commit hash, ecosystem

**Step 3: Validation Command Definition**

One validation command per package manager ecosystem:

- **npm**: `npm ci --ignore-scripts`
- **Bundler**: `bundle install --jobs=1 --retry=2 --without development test`
- **pip/Poetry**: Standard install commands

**Step 4: Reproduction and Manual Resolution**

```python
def process(entry, done):
    # Clone repo at specific commit
    subprocess.run(["git", "clone", "--depth", "1", repo_url, tmp/"r"])
    subprocess.run(["git", "-C", tmp/"r", "fetch", "--depth", "1",
                    "origin", entry["base_commit"]])
    subprocess.run(["git", "-C", tmp/"r", "checkout", entry["base_commit"]])

    # Run validation command in Docker
    for cmd in cfg["cmds"]:
        out += docker_run(workdir, cfg["image"], cmd)
        if cfg["err"].search(out):
            success = True  # Conflict reproduced!
```

- Reproduced conflicts in fresh environments
- Manually resolved each conflict to validate task feasibility
- Only included validated instances in final benchmark

**Final Set**: 9 npm + 7 Bundler = 16 dependency conflicts

### 3. Database Setup (15 instances)

Handcrafted tasks across 5 database engines with 3 difficulty tiers.

#### Database Engines Covered
- PostgreSQL
- MySQL
- SQLite
- Redis
- MongoDB

#### Three-Tier Difficulty Structure

**Tier 1: Basic Installation and Data Seeding**

Example (MySQL Tier 1):
```json
{
    "instance_id": "dbsetup-mysql-1",
    "success_command": "mysql -u root -e \"USE benchmark_db; SHOW TABLES;\" | grep -q products && echo \"Setup successful\" || echo \"Setup failed\"",
    "requirements": [
        "Non-interactive MySQL installation with root login",
        "Create benchmark_db",
        "Decompress and import dump.sql.gz"
    ]
}
```

**Tier 2: Configuration and Migration Management**

Example (MySQL Tier 2):
```json
{
    "instance_id": "dbsetup-mysql-2",
    "requirements": [
        "Apply numbered .sql.gz migrations with foreign keys",
        "Ensure server and database use utf8mb4",
        "Enable root password authentication"
    ]
}
```

**Tier 3: Production Troubleshooting with Deliberate Obstacles**

Example (MySQL Tier 3):
```json
{
    "instance_id": "dbsetup-mysql-3",
    "success_command": "mysql -u benchmark_user -pbenchmark_pass -e \"USE benchmark_db; SELECT COUNT(*) FROM products;\" | grep -q '[1-9]' && echo \"Setup successful\" || echo \"Setup failed\"",
    "requirements": [
        "Run MySQL on port 3307 (3306 blocked)",
        "Operate under STRICT_TRANS_TABLES",
        "Patch migrations that reference missing DEFINER",
        "Re-order and fix out-of-sequence migrations",
        "Create user benchmark_user/benchmark_pass with privileges"
    ]
}
```

**Design Philosophy**: Tier 3 deliberately introduces realistic production issues:
- Blocked ports
- Corrupted migrations
- Strict SQL modes
- Permission issues

Agents must diagnose and resolve through error message analysis.

### 4. Background Service Orchestration (8 instances)

Scenarios requiring coordination of long-running services through supervisord.

#### Service Types Covered
- Gunicorn servers
- Celery workers with Redis backends
- NGINX reverse proxies
- File-watching daemons
- Autossh tunnels
- Producer-consumer pipelines

#### Construction Approach

**Example: Gunicorn + Unix Socket**

```json
{
    "instance_id": "bgsetup-gunicorn-systemd-socket",
    "success_command": "curl --unix-socket /tmp/gunicorn.sock http://localhost/ | grep -q \"Hello\" && echo \"Setup successful\" || echo \"Setup failed\"",
    "requirements": [
        "Install Python, Flask, Gunicorn, and supervisord",
        "Serve /testbed/app.py via Gunicorn on /tmp/gunicorn.sock",
        "Configure supervisord to restart on failure",
        "Endpoint must return the string 'Hello' over the Unix socket"
    ]
}
```

**Validation Strategy**: Commands verify observable side effects:
- HTTP responses
- Redis keys
- Log messages
- Process status

## Dataset Structure

### Standard Fields (All Tasks)

```json
{
    "instance_id": "unique-identifier",
    "problem_statement": "Natural language description of the task",
    "success_command": "Deterministic one-line validation command",
    "base_image": "Docker base image (e.g., 'ruby:2.7', 'python:3.9')",
    "task_type": "One of: repo_setup, dependency_resolution, database_setup, background_service"
}
```

### Category-Specific Fields

**Dependency Resolution**:
```json
{
    "ecosystem": "npm-eresolve | bundler-compat | pip-conflict | poetry-conflict",
    "base_commit": "Git commit hash where conflict exists",
    "repo": "owner/repo",
    "issue_number": 123,
    "issue_url": "https://github.com/...",
    "manifest": "package.json | Gemfile | requirements.txt | pyproject.toml",
    "lockfiles_found": ["package-lock.json"]
}
```

**Repository Setup**:
```json
{
    "language": "Python | TypeScript | JavaScript | Go | Rust | Java | C++",
    "repo_url": "https://github.com/..."
}
```

## Quality Assurance Process

### 1. Deterministic Validation
- Every task must have a validation command that outputs exactly "Setup successful" or "Setup failed"
- No LLM-as-judge (unlike GitGoodBench, DevBench)
- No flaky test suites (unlike SWE-bench)

### 2. Manual Verification
- All 93 tasks underwent manual review
- Roughly half were constructed entirely by human authors
- Rest were adapted from real-world repositories
- Each task tested in fresh environments multiple times

### 3. Reproducibility Testing
```python
# Validation harness executes in fresh terminal subprocess
# Ensures results reflect actual system state, not cached output
subprocess.run(success_command, shell=True, capture_output=True)
```

### 4. Feasibility Confirmation
- Authors manually solved each task before inclusion
- Documented expected solution path
- Verified edge cases and potential failure modes

## Evaluation Infrastructure

### Docker-Based Execution

```python
# Standardized Docker image per task
# Bare Ubuntu 22.04 with minimal tooling
docker run --rm \
    -v /path/to/workspace:/workspace \
    -w /workspace \
    ubuntu:22.04 \
    bash -c "${VALIDATION_COMMAND}"
```

### Container Specifications
- **CPU**: 16 cores
- **Memory**: 62 GiB
- **Disk**: 695 GB
- **Timeout**: 2 hours wall-clock time
- **Privileges**: Root access
- **Network**: Unrestricted outbound access

### Validation Harness

1. Launch container with task environment
2. Inject agent code at runtime
3. Execute agent (black-box entry point)
4. After agent completes, run validation command in fresh subprocess
5. Parse output for "Setup successful" vs "Setup failed"
6. Record metrics: success rate, token usage, step count

## Tools and Scripts Provided

The benchmark includes:

1. **Mining scripts** (dependency-resolution)
   - GitHub issue searcher
   - Conflict validator
   - Metadata extractor

2. **LLM prompt templates** (repo-setup)
   - Setup instruction derivation
   - Success command synthesis

3. **Validation scripts**
   - Docker orchestration
   - Parallel execution framework
   - Result aggregation

4. **Dataset files**
   - JSONL format
   - One instance per line
   - Metadata included

## Key Design Decisions

### Why Manual Curation?

- **Quality over quantity**: Ensures each task is well-defined and solvable
- **Realistic difficulty**: Tasks reflect actual developer pain points
- **Deterministic evaluation**: Human verification prevents false positives/negatives

### Why Closed GitHub Issues?

- Confirms the problem was real (reported by actual developer)
- Confirms the problem was solvable (issue was resolved)
- Provides authentic error messages and context

### Why Three Tiers for Databases?

- **Tier 1**: Tests basic capability (can you install and seed?)
- **Tier 2**: Tests configuration knowledge (charset, migrations)
- **Tier 3**: Tests troubleshooting and debugging (real production scenarios)

Progressive difficulty reveals different capability levels.

### Why Bare Sandboxes?

Unlike SWE-bench's pre-configured containers:
- Tests the full setup workflow
- Mirrors real deployment scenarios for AI agents
- Exposes failure modes invisible in pre-baked environments
- Reflects actual developer experience ("clone and run")

## Limitations Acknowledged

1. **Scale**: 93 tasks is modest compared to SWE-bench's 2k+
   - Tradeoff: Manual curation ensures quality
   - Future: Scripts provided for community scaling

2. **Domain coverage**: Omits GPU drivers, Kubernetes, infrastructure-as-code
   - Future extension opportunity

3. **Security context**: Agents run with root + unrestricted network
   - Simplifies execution
   - Future: Add permission constraints

## Extensibility

The benchmark is designed for community contribution:

- **Open source**: All scripts and prompts on GitHub
- **Documented methodology**: Can replicate for new languages/ecosystems
- **Modular structure**: Easy to add new categories
- **Standardized format**: JSONL dataset structure

## Summary

SetupBench was built through a rigorous three-phase process:

1. **Source authentic tasks**: Mine GitHub issues, select popular repos
2. **Manual validation**: Reproduce, solve, and verify each task
3. **Deterministic evaluation**: Craft single-line validation commands

The result is a high-quality benchmark that fills a critical gap in agent evaluation: the ability to bootstrap development environments from scratch.
