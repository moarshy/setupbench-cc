# SetupBench Paper Summary

## Overview
**SetupBench** is a benchmark designed to evaluate LLM-based software engineering agents on their ability to **bootstrap development environments** from scratch. Unlike existing benchmarks (SWE-Bench, DevBench) that provide pre-configured Docker containers with all dependencies installed, SetupBench starts agents in bare Linux sandboxes and requires them to set up everything themselves.

## Key Motivation
Existing agent benchmarks don't test a critical real-world skill: **getting code to actually run**. They evaluate agents in environments where everything is already installed, missing the setup phase that empirical studies show is a major source of developer frustration.

## Benchmark Design

### Composition (93 instances across 4 categories):

1. **Repository Setup (54 instances)**: Setting up projects across 7 languages (Python, TypeScript, JavaScript, Go, Rust, Java, C++)
2. **Dependency Resolution (16 instances)**: Resolving real-world conflicts from npm, pip/Poetry, and Bundler
3. **Database Setup (15 instances)**: Installing and configuring PostgreSQL, MySQL, SQLite, Redis, MongoDB
4. **Background Services (8 instances)**: Orchestrating Gunicorn, Celery, NGINX, file-watchers, autossh

### Key Features:
- **Deterministic evaluation**: Each task has a validation command that outputs "Setup successful" or "Setup failed"
- **Minimal sandbox**: Fresh Ubuntu containers with nothing pre-installed
- **Natural language prompts**: Tasks specified in plain English
- **Graded difficulty**: Especially in database setup (3 tiers from basic to production-like troubleshooting)

## Main Findings

### Performance Results
Testing OpenHands agent with 5 models (GPT-4o, GPT-4.1, Claude 3.5, 3.7, and 4):

- **Best overall**: Claude 4 at **62.4%** success rate
- **Worst overall**: GPT-4o at **34.4%** success rate
- **Success varies dramatically by category**:
  - Background services: 50-87.5%
  - Dependency resolution: 25-87.5%
  - Repository setup: 38.9-57.4%
  - Database setup: 20-53.3% (hardest category)

### Three Critical Failure Modes

1. **Ignoring test tooling** (17-26% of repo-setup failures)
   - Agents install runtime dependencies but miss test frameworks
   - Example: Installing packages but not `tox` despite `tox.ini` being present

2. **Hallucinated task constraints**
   - Agents invent non-existent requirements (e.g., changing ports that weren't specified)
   - Aligned with literature showing 24-30% of GPT-4 failures involve spurious configuration values

3. **Non-persistent environment setup**
   - Agents install tools that work in their session but disappear in fresh shells
   - Breaks human-agent collaboration workflows
   - Example: Installing `pnpm` without making it persist across shell sessions

### Efficiency Analysis

Compared agent behavior to optimal human trajectories on 10 instances:

- **Wasted steps**: 38-69% of all actions were unnecessary
- **Claude 3.5**: Most efficient at 38% waste
- **Claude 4**: Least efficient at 69% waste (despite highest success rate)

**Three main sources of inefficiency**:
1. **Redundant file reads**: Reading same file multiple times incrementally (e.g., `head -40`, `head -60`, `head -100`)
2. **Poor instruction following**: Using `sudo` unnecessarily, checking for pre-installed packages despite being told environment is bare
3. **Off-target exploration**: Reading setup-adjacent but non-informative files

## Design Implications

The paper identifies several areas for improvement:

1. **Context-aware setup completion**: Better semantic understanding of what constitutes a "complete" development environment
2. **Environment persistence**: Agents should write changes to `.bashrc`, `/etc/profile.d/`, etc., not just current shell
3. **Efficiency-focused exploration**: Need better strategies than low-level `cd`/`ls`/`head`/`cat` commands
4. **Model selection strategies**: Performance-efficiency tradeoffs suggest hybrid approaches (light models for simple tasks, heavy models for complex ones)
5. **Constraint validation**: Systems to prevent hallucinated requirements

## Significance

SetupBench fills a critical gap in agent evaluation by focusing on the **environment-bootstrap skill** that precedes all actual coding work. The benchmark:
- Provides deterministic, reproducible evaluation
- Covers diverse technical stacks (7 languages, 5 databases, multiple package managers)
- Reflects real deployment scenarios for modern AI coding agents
- Identifies specific, actionable weaknesses in current agent architectures

The relatively low success rates (34-62%) and high inefficiency (38-69% wasted actions) reveal substantial room for improvement in agents' practical capabilities before they can truly handle end-to-end software engineering tasks.

## Key Takeaways for Agent Development

1. **Environment setup is hard**: Even state-of-the-art agents struggle with basic setup tasks
2. **Persistence matters**: Changes must survive shell sessions for real-world collaboration
3. **Efficiency vs. accuracy tradeoff**: More powerful models succeed more but waste more steps
4. **Implicit knowledge gaps**: Agents miss conventions that human developers understand (e.g., test tooling requirements)
5. **Hallucination risk**: Agents frequently invent constraints not present in task specifications

## Related Resources

- **Paper**: arXiv:2507.09063v1 [cs.SE]
- **Benchmark Repository**: https://github.com/microsoft/SetupBench
- **Authors**: Avi Arora, Jinu Jang, Roshanak Zilouchian Moghaddam (Microsoft)
- **Publication**: Preprint, under review (2025)
