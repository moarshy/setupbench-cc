# SetupBench vs setupbench-cc: Complete Code Reuse Analysis

This directory contains a comprehensive architectural analysis exploring whether setupbench-cc should have reused SetupBench's code, what was justified to reimplement, and opportunities for future improvements.

## Quick Start

**Choose your depth level:**

| Document | Time | Best For |
|----------|------|----------|
| **VISUAL_SUMMARY.txt** | 5 min | Quick visual overview, ASCII diagrams |
| **CODEBASE_ANALYSIS_SUMMARY.md** | 10-15 min | Executive summary, decision-making |
| **ANALYSIS_INDEX.md** | 10 min | Navigation, Q&A section |
| **CODEBASE_ANALYSIS.md** | 45-60 min | Complete deep dive, all details |

## Main Findings

### The Verdict: ✅ Justified Reimplementation

setupbench-cc's reimplementation of SetupBench functionality was **completely justified** because:

1. **SetupBench is a dataset, not a library**
   - Only 194 lines of Python code (the evaluation harness)
   - Deliberately agent-agnostic
   - Not designed for import/reuse
   - Not on PyPI

2. **setupbench-cc is a complete orchestration platform**
   - 1,647 lines implementing agent-specific features
   - Claude SDK integration (241 lines)
   - Comprehensive logging infrastructure (102 lines)
   - Docker orchestration (283 lines)
   - Dual execution harnesses (688 lines)
   - All justified for the use case

3. **The 8.5x size difference is appropriate**
   - SetupBench: minimal validator (194 lines)
   - setupbench-cc: complete orchestration (1,647 lines)
   - Difference: 1,425 custom lines = justified

### The Opportunity: 34% Code Reuse

However, there's a real opportunity to extract **~66 lines (34% of SetupBench)** into a shared package that would benefit both setupbench-cc and future agents:

| Component | Lines | Status | Effort |
|-----------|-------|--------|--------|
| Evaluation Logic | 6 | Duplicated 2x | 0.5h |
| Task Schema | 30 | Untyped | 2h |
| Fixture Utilities | 20 | Duplicated 2x | 1h |
| Success Semantics | 10 | Inlined | 0.25h |

**Recommendation: Create `setupbench-common` package**
- Extract shared utilities
- Publish on PyPI
- Enable reuse by other agents (OpenHands, Cursor, etc.)
- Effort: 5 weeks | Payoff: 8-10 weeks maintenance saved

## Architecture Overview

```
SetupBench (194 lines)
├─ evaluation_harness.py ........... Validates success commands
├─ scenarios/*.jsonl ............... 93 benchmark tasks
└─ fixtures/ ...................... Pre-built environments

setupbench-cc (1,647 lines)
├─ agent.py ....................... Claude SDK integration (241 lines)
├─ agent_logging.py ............... 3-tier logging system (102 lines)
├─ agent_docker.py ................ Container orchestration (283 lines)
├─ docker.py ....................... Container utilities (111 lines)
├─ harness_local.py ............... Local execution harness (346 lines)
├─ harness_docker.py .............. Docker execution harness (342 lines)
└─ __init__.py .................... Package interface (28 lines)

Total custom code: 1,425 lines (all justified)
Extractable code: 66 lines (34% reuse opportunity)
```

## Code Reuse Examples

### Currently Duplicated: Evaluation Logic

**SetupBench's decide_success() function (6 lines):**
```python
def decide_success(task_type, exit_code, output):
    if task_type == "dependency_resolution":
        return {"success": exit_code == 0}
    return {"success": "Setup successful" in output}
```

**Duplicated in setupbench-cc:**
- `harness_local.py` lines 122-125
- `harness_docker.py` lines 130-132

**Recommended extraction:** `setupbench_common/evaluation.py`

### Currently Missing: Task Schema

**SetupBench format (documented in README):**
```json
{
  "instance_id": "string",
  "task_type": "bgsetup|dbsetup|dependency_resolution|reposetup",
  "success_command": "string",
  "problem_statement": "string",
  "base_image": "string",
  "image_tag": "string"
}
```

**setupbench-cc current approach:**
```python
task['instance_id']        # ❌ No type checking
task['task_type']          # ❌ No enum validation
task['success_command']    # ❌ No required field validation
```

**Recommended solution:** Create Pydantic model in `setupbench_common/schema.py`

## Analysis Documents

### 1. VISUAL_SUMMARY.txt
Quick visual overview with ASCII diagrams showing:
- Project comparison tables
- Code reuse scorecard
- Architecture diagrams (current vs proposed)
- Effort/payoff analysis
- Duplication examples

**Read this first for quick understanding.**

### 2. CODEBASE_ANALYSIS_SUMMARY.md
Executive summary covering:
- Quick verdict and justification
- Size comparison with breakdown
- What SetupBench provides
- What setupbench-cc built
- Code reuse opportunities
- Recommended refactoring (setupbench-common)
- Implementation plan

**Read this for decision-making and planning.**

### 3. ANALYSIS_INDEX.md
Navigation guide with:
- Document descriptions
- Key findings summary
- File paths for reference
- Detailed section list
- How to use analysis for different roles
- Q&A section
- Next steps

**Use this for navigation and quick answers.**

### 4. CODEBASE_ANALYSIS.md (Comprehensive)
Deep-dive technical analysis with:
- Section 1: SetupBench's actual scope
- Section 2: setupbench-cc's reimplementation analysis
- Section 3: Code reuse opportunities
- Section 4: Side-by-side comparisons
- Section 5: Integration analysis
- Section 6: Detailed code examples
- Section 7: Why integration wasn't feasible
- Section 8: Detailed recommendations
- Section 9: Architecture assessment
- Section 10: Code reuse scorecard
- Section 11: Refactoring options
- Section 12: Final conclusions

**Read for architectural decisions and detailed planning.**

## Key Insights

### 1. SetupBench is Dataset-First
- Primary value: 93 benchmark tasks + fixtures
- Secondary value: 194-line evaluation harness
- Deliberately not designed as a library
- Intentionally minimal and agent-agnostic

### 2. setupbench-cc is Platform-First
- Primary value: Claude Code orchestration
- Secondary value: extensible framework
- Claude-specific (not immediately reusable by others)
- Adds logging, metrics, automation that SetupBench doesn't

### 3. Complete Integration Wasn't Feasible
- SetupBench not on PyPI (git repo only)
- No public API (only CLI binary)
- No type system (raw dicts)
- No logging infrastructure
- Different maturity levels

### 4. Selective Extraction is the Answer
- Extract shared utilities into `setupbench-common`
- Independent package on PyPI
- Usable by other agents
- Can eventually propose upstream to SetupBench

## Recommendations Summary

### Short Term (This Week)
1. Extract evaluation logic (0.5 hour)
2. Add task schema validation (2-3 hours)
3. Extract fixture utilities (1 hour)

### Medium Term (1-2 Weeks)
1. Create `setupbench-common` package
2. Integrate with setupbench-cc
3. Publish on PyPI

### Long Term (3-6 Months)
1. Propose upstream to SetupBench
2. Create standard agent adapter interface
3. Enable ecosystem of agents

## Why This Matters

### For setupbench-cc
- ✅ Cleaner codebase (remove duplication)
- ✅ Better type safety (Pydantic validation)
- ✅ Easier maintenance (single source of truth)
- ✅ Professional packaging

### For SetupBench
- ✅ Becomes library-friendly
- ✅ Enables typed integration
- ✅ Supports ecosystem of agents

### For Other Agents
- ✅ Can reuse common utilities
- ✅ Consistent SetupBench integration
- ✅ Comparable methodology

### For Research
- ✅ Standardized evaluation
- ✅ Fair agent comparison
- ✅ Reproducible results

## File Paths

All analysis documents are located in:
```
docs/
├─ VISUAL_SUMMARY.txt               ← Start here (5 min)
├─ code-reuse-analysis.md           ← This file (quick start)
├─ CODEBASE_ANALYSIS_SUMMARY.md     ← Executive overview (15 min)
├─ ANALYSIS_INDEX.md                ← Navigation guide (10 min)
└─ CODEBASE_ANALYSIS.md             ← Complete analysis (60 min)
```

Other documentation:
```
docs/
├─ setupbench-summary.md            ← Overview of SetupBench
├─ setupbench-compliance.md         ← SetupBench compliance verification
└─ benchmark-construction.md        ← How SetupBench was built
```

## Implementation Path

To proceed with `setupbench-common` extraction:

1. **Review** CODEBASE_ANALYSIS.md Section 8 (Recommendations)
2. **Start** with Opportunity 8.1 (evaluation logic) - 0.5 hour
3. **Test** that both harnesses work with extracted code
4. **Expand** to schema validation (2-3 hours)
5. **Extract** fixture utilities (1 hour)
6. **Create** setupbench_common package structure
7. **Test** thoroughly with unit tests
8. **Publish** to PyPI
9. **Coordinate** with SetupBench maintainers

**Total effort: ~5 weeks | Expected payoff: 8-10 weeks of future maintenance**

## Conclusion

setupbench-cc's 8.5x expansion over SetupBench is completely justified—they solve different problems. However, extracting shared utilities into `setupbench-common` would:

- Improve code quality (remove duplication)
- Enable agent ecosystem (other implementations)
- Standardize SetupBench integration (consistent approach)
- Professional packaging (on PyPI)

**Recommendation: Proceed with `setupbench-common` extraction** as a medium-priority initiative that pays dividends for years.

---

## Questions?

Refer to the Q&A section in **ANALYSIS_INDEX.md** or check the detailed analysis in **CODEBASE_ANALYSIS.md**.

For specific code examples, see **CODEBASE_ANALYSIS.md Section 6**.

For implementation details, see **CODEBASE_ANALYSIS.md Section 8**.

