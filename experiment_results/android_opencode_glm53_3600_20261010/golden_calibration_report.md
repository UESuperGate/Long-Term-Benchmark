# Snapshot State Matrix Run Report

- Generated: 2026-10-10T15:50:55
- Targets: 10
- Case-target rows: 300
- Platform filter: `android`
- Target role filter: `both`
- Transition mode: `strict`
- Status counts: `{"matched": 300}`
- Semantic status counts: `{"failed": 150, "passed": 150}`

## Notes

- ArkTS cases poll for a case-specific ready marker instead of using a fixed sleep.
- Android queries the debug provider once for initial state and once per stateEvent transition.
- Every declared transition is delivered through the platform stateEvent transport and captured separately.
- Scoring combines independently observed ArkUI node ids/states with runtime semantic facts.
- Compatible mode may accept aggregate transition facts from legacy golden targets; strict mode does not.

## Non-Matched Rows
