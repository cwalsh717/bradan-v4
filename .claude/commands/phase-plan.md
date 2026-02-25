---
description: "Decompose a build phase into independent and dependent tasks for parallel execution. Use at the start of any new phase."
allowed-tools: Read, Grep, Glob
---

# Phase Plan: $ARGUMENTS

Read `bradan_v4_spec.md` and find the build order for Phase $ARGUMENTS.

## Your Job

1. List every sub-task in this phase from the spec.
2. For each sub-task, identify:
   - What files/modules it touches
   - What it depends on (other sub-tasks that must complete first)
   - Estimated complexity (small / medium / large)
3. Sort into two groups:
   - **Independent tasks** — can run in parallel via sub-agents (no shared files, no dependencies on each other)
   - **Sequential tasks** — must run in order due to dependencies
4. For each task, specify which sub-agent should handle it (backend or frontend).
5. Present the plan and STOP. Do not implement anything.

## Output Format

```
## Phase [N]: [Name]

### Independent (can parallelize)
- Task A: [description] → backend agent → [files affected]
- Task B: [description] → backend agent → [files affected]

### Sequential (must be ordered)
1. Task C: [description] → depends on A → backend agent
2. Task D: [description] → depends on C → backend agent

### Test Requirements
- [list the tests needed for this phase]
```

Wait for approval before any implementation begins.
