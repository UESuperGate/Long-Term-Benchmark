# Snapshot State Matrix Run Report

- Generated: 2026-10-09T13:18:29
- Targets: 10
- Case-target rows: 300
- Platform filter: `arkts`
- Target role filter: `both`
- Transition mode: `compatible`
- Status counts: `{"matched": 300}`
- Semantic status counts: `{"failed": 150, "passed": 150}`

## Notes

- ArkTS cases poll for a case-specific ready marker instead of using a fixed sleep.
- Every declared transition is delivered through the stateEvent Want parameter and captured separately.
- Scoring combines independently observed ArkUI node ids/states with runtime semantic facts.
- Compatible mode may accept aggregate transition facts from legacy golden targets; strict mode does not.

## Non-Matched Rows
