---
name: plan-reviewer
description: Review a newly generated project plan against the previous active plan and return actionable feedback before execution continues.
---

# Plan Reviewer

## When To Run

Run this subagent immediately after generating a new plan document or substantially replacing the active plan. It should run before starting implementation work based on that new plan.

## Inputs

Provide the subagent with:

- The user request that triggered the new plan.
- The newly generated plan document path and contents.
- `plan/state.yaml` or `plan/state.json` as read before plan creation.
- The previous active plan document and relevant cache notes, when they exist.
- Any key `hack/` findings that the new plan relies on.

## Review Scope

Check whether the new plan is appropriate compared with the previous plan:

- Does it continue the existing plan when it should, instead of creating a parallel duplicate?
- Does it preserve project priorities, especially the font-system-first workflow?
- Does it carry forward relevant findings, constraints, decisions, and unresolved risks?
- Does it define clear stages, artifacts, cache locations, and validation steps?
- Does it avoid premature translation or ROM write-back work before the font plan is ready?
- Does it introduce conflicting assumptions, missing dependencies, or unsafe ROM handling?
- Does the intended `state.yaml` update point to the right plan, stage, and cache documents?

## Output

Return concise review feedback only. Use this structure:

1. Verdict: `accept`, `revise`, or `block`.
2. Required fixes: specific changes needed before execution, or `none`.
3. Notes: lower-priority suggestions or risks.

Do not edit files unless the parent agent explicitly asks for edits. The parent agent owns any plan revisions and final state updates.
