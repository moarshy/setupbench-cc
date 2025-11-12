#!/usr/bin/env python3
"""
Simplified Smoke Test - 4 Tasks (Multiple Base Images)
=======================================================

Tests 4 categories across different base images:
1. Database Setup (ubuntu:22.04)
2. Dependency Resolution (ruby:2.7)
3. Background Service (ubuntu:22.04)
4. Repo Setup (ubuntu:22.04)
"""

import subprocess
import time
import json
from pathlib import Path
from datetime import datetime

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

TASKS = [
    ("1_database_setup.json", "Database Setup (PostgreSQL)"),
    ("2_dependency_resolution.json", "Dependency Resolution (Ruby gem)"),
    ("3_background_service.json", "Background Service (File watcher)"),
    ("4_repo_setup.json", "Repo Setup (Pytesseract)"),
]

OUTPUT_DIR = Path("smoke_test_simple_results")


def cleanup_containers():
    """Remove any existing setupbench-agent containers from previous runs."""
    if not DOCKER_AVAILABLE:
        print(f"{YELLOW}⚠ Docker Python library not available, skipping container cleanup{RESET}")
        return

    try:
        client = docker.from_env()
        # Find all containers with setupbench-agent in their name
        containers = client.containers.list(all=True, filters={"name": "setupbench-agent"})

        if containers:
            print(f"{YELLOW}🧹 Cleaning up {len(containers)} existing container(s)...{RESET}")
            for container in containers:
                try:
                    container.remove(force=True)
                    print(f"   ✓ Removed: {container.name}")
                except Exception as e:
                    print(f"   {RED}✗ Failed to remove {container.name}: {e}{RESET}")
        else:
            print(f"{GREEN}✓ No existing containers to clean up{RESET}")
    except Exception as e:
        print(f"{YELLOW}⚠ Failed to cleanup containers: {e}{RESET}")


def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{RESET}\n")


def run_task(task_file, task_name, num, total):
    print(f"\n{BOLD}{YELLOW}[{num}/{total}] {task_name}{RESET}")
    print(f"{'-'*70}")

    task_path = Path("smoke_test_tasks") / task_file
    with open(task_path) as f:
        task = json.load(f)

    print(f"Instance ID: {task['instance_id']}")
    print(f"Base Image:  {task['base_image']}")
    print(f"Task Type:   {task['task_type']}\n")

    start_time = time.time()
    cmd = [
        "python", "-m", "setupbench_runner.harness_docker",
        "--task", str(task_path),
        "--output", str(OUTPUT_DIR)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        elapsed = time.time() - start_time

        if result.returncode == 0 and "✅ PASS" in result.stdout:
            print(f"{GREEN}✓ Completed in {elapsed:.1f}s{RESET}")
            return True, elapsed, task['instance_id']
        else:
            print(f"{RED}✗ Failed{RESET}")
            if "✗" in result.stdout:
                print(result.stdout[result.stdout.find("✗"):result.stdout.find("✗")+200])
            return False, elapsed, task['instance_id']
    except subprocess.TimeoutExpired:
        print(f"{RED}✗ Timed out{RESET}")
        return False, time.time() - start_time, task['instance_id']
    except Exception as e:
        print(f"{RED}✗ Error: {e}{RESET}")
        return False, time.time() - start_time, task['instance_id']


def main():
    print_header("Simple Smoke Test (4 Tasks - Multiple Base Images)")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Tasks: {len(TASKS)}\n")

    # Clean up any existing containers from previous runs
    cleanup_containers()
    print()

    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    results = []
    for i, (task_file, task_name) in enumerate(TASKS, 1):
        success, elapsed, instance_id = run_task(task_file, task_name, i, len(TASKS))
        results.append({
            "name": task_name,
            "instance_id": instance_id,
            "success": success,
            "elapsed": elapsed
        })
        if i < len(TASKS):
            time.sleep(2)

    # Generate comprehensive summary from individual result files
    summary_results = []
    for r in results:
        result_file = OUTPUT_DIR / "results" / f"{r['instance_id']}.json"
        if result_file.exists():
            with open(result_file) as f:
                details = json.load(f)
                summary_results.append(details)
        else:
            # Create a minimal entry for failed tasks
            summary_results.append({
                "instance_id": r['instance_id'],
                "success": r['success'],
                "wall_time_seconds": r['elapsed'],
                "total_steps": 0,
                "total_tokens": 0
            })

    # Save smoke test summary
    smoke_summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(summary_results),
        "success_rate": sum(1 for r in summary_results if r['success']) / len(summary_results) * 100 if summary_results else 0,
        "successful_tasks": sum(1 for r in summary_results if r['success']),
        "failed_tasks": sum(1 for r in summary_results if not r['success']),
        "avg_tokens": sum(r.get('total_tokens', 0) for r in summary_results) / len(summary_results) if summary_results else 0,
        "avg_steps": sum(r.get('total_steps', 0) for r in summary_results) / len(summary_results) if summary_results else 0,
        "avg_time_seconds": sum(r.get('wall_time_seconds', 0) for r in summary_results) / len(summary_results) if summary_results else 0,
        "results": summary_results
    }

    summary_file = OUTPUT_DIR / "smoke_test_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(smoke_summary, f, indent=2)

    # Print summary
    print_header("SUMMARY")
    passed = sum(1 for r in results if r['success'])
    print(f"Total: {len(results)}")
    print(f"Passed: {GREEN}{passed}{RESET}")
    print(f"Failed: {RED}{len(results)-passed}{RESET}")
    print(f"Success Rate: {passed/len(results)*100:.1f}%\n")

    for i, r in enumerate(results, 1):
        status = f"{GREEN}✓{RESET}" if r['success'] else f"{RED}✗{RESET}"
        print(f"{i}. {r['name']:<35} {status} ({r['elapsed']:.1f}s)")

        if r['success']:
            result_file = OUTPUT_DIR / "results" / f"{r['instance_id']}.json"
            if result_file.exists():
                with open(result_file) as f:
                    details = json.load(f)
                print(f"   Steps: {details.get('total_steps', 0)}, "
                      f"Tokens: {details.get('total_tokens', 0)/1000:.1f}K, "
                      f"Base: {details.get('base_image', 'N/A')}")

    print()
    print(f"Summary saved to: {summary_file}\n")

    if passed == len(results):
        print(f"{GREEN}{BOLD}🎉 All tests passed!{RESET}\n")
        return 0
    else:
        print(f"{YELLOW}⚠ Some tests failed{RESET}\n")
        return 1


if __name__ == "__main__":
    exit(main())
