---
description: "Gate check for completed work. Runs tests, validates spec compliance, reports status. Use after finishing a task or before committing."
allowed-tools: Read, Bash, Grep, Glob
---

# Quality Gate Check

Run the following checks in order. Report all results. Do not fix anything — only report.

## 1. Tests
```bash
cd backend && pytest tests/ -v --tb=short 2>&1
```
Report: total tests, passed, failed, errors.

## 2. Lint
```bash
cd backend && ruff check . 2>&1
```
Report: clean or list violations.

## 3. Spec Compliance
Read `bradan_v4_spec.md`. For the most recently modified files:
- Does the implementation match the spec's schema definitions?
- Does it follow the caching strategy defined in the spec?
- Does it respect the "compute don't store" principle?
- Are the API endpoint signatures correct?

## 4. Test Coverage Gaps
Look at the files modified since the last commit. For each:
- Does a corresponding test file exist?
- Are success AND error paths tested?
- Are external APIs mocked (not hitting real endpoints)?

## Output Format

```
## Gate Check Results

### Tests: PASS/FAIL
[details]

### Lint: PASS/FAIL
[details]

### Spec Compliance: PASS/FAIL
[any deviations found]

### Coverage Gaps: PASS/FAIL
[any missing tests]

### Verdict: SHIP IT / BLOCK — [reason if blocked]
```
