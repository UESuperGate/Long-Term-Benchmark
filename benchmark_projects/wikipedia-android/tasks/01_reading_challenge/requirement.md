# Reading challenge lifecycle

## Version boundary

Implement the reading challenge capability introduced between `r/50579-r-2026-04-14` (`b74f202c37c50d9136a6bc9b632b47336ad21645`) and `r/50585-r-2026-05-06` (`f730d59705224aca1c8d96a6dfec3cf46264abde`).

## User outcome

Readers can enroll in a time-bounded challenge, build a persistent daily article-reading streak, see whether they still need to read today, complete the goal, and receive a coherent concluded state when an active streak can no longer continue.

## Functional requirements

- Before the challenge starts, expose a not-live-yet state. During the active window, distinguish not enrolled, enrolled but not started, needs reading today, read today, and completed states.
- Enrollment persists and begins with a zero streak.
- Opening an article while enrolled records at most one qualifying read per calendar day, increments the streak once, persists the read date, and requests the widget/analytics update effects.
- A read on the following day continues the streak. A gap of more than one day during the active challenge resets an incomplete streak, after which a later eligible read can begin again at one.
- Reaching the goal is terminal for streak-reset purposes.
- During the post-end buffer, only an active streak may continue. A broken streak is concluded and a read must not restart it.
- Date evaluation must use a clock supplied at the evaluator boundary. Do not rewrite dates in production preferences or introduce a testcase-specific date switch.

## Failure and recovery

Duplicate same-day reads are ignored without duplicate persistence, widget refresh, or analytics effects. A missed-day reset is recoverable during the active window by reading again. A broken streak after the challenge end is not recoverable.

## Invariants

- The streak never increments more than once for the same date.
- Nonqualifying reads do not alter enrollment, streak, or last-read date.
- All stored dates use ISO local-date values.
- External widget and analytics systems are leaf boundaries; application-owned eligibility, persistence, state resolution, and effect dispatch must execute.

## Non-goals

Pixel-perfect Glance rendering, live widget-host behavior, live analytics delivery, article rendering, and changes to unrelated reading history are outside this task.
