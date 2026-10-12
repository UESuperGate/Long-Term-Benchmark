# Snapshot State Matrix Run Report

- Generated: 2026-10-12T21:00:27
- Targets: 5
- Case-target rows: 150
- Platform filter: `android`
- Target role filter: `agent_result`
- Transition mode: `strict`
- Status counts: `{"matched": 150}`
- Semantic status counts: `{"passed": 150}`

## Notes

- ArkTS cases poll for a case-specific ready marker instead of using a fixed sleep.
- Android queries the debug provider once for initial state and once per stateEvent transition.
- Every declared transition is delivered through the platform stateEvent transport and captured separately.
- Scoring combines independently observed ArkUI node ids/states with runtime semantic facts.
- Compatible mode may accept aggregate transition facts from legacy golden targets; strict mode does not.

## Non-Matched Rows
