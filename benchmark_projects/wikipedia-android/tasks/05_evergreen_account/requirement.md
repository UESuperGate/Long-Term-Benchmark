# Evergreen account creation encouragement

## Version boundary

Implement the evergreen account-creation encouragement introduced between `r/50603-r-2026-08-25` (`12d1dd2bffea3db7ead5a69b2025bcbf287fe64d`) and `beta/50604-beta-2026-09-02` (`669a5405fc78ef888203c974c1d67b6259f0eff2`). The final ref is the newest immutable version-50604 tag that contains feature commit `d679fd1a9530fbe08cb9d117a49ca5d4ff79dce2`; the repository has no production `r/50604` tag.

## User outcome

Readers who repeatedly use Wikipedia without a permanent account receive a personalized explanation of account benefits at an appropriate moment. They can defer it, permanently dismiss it, or enter account creation, without the prompt interrupting registered users, external article links, or ineligible reading sessions.

## Functional requirements

- The encouragement is considered only after initial onboarding and other higher-priority launch prompts have completed.
- A first-time logged-out or temporary-account reader becomes eligible after reading on two distinct days less than a fortnight apart. The earlier qualifying day must be at least one week old, and only reading history from the most recent year is considered.
- Showing the encouragement records an impression and its local date. The screen presents personalized reading, saving, and recent-use counts derived from application data.
- Choosing **Maybe later** closes the screen without permanently opting out. A second impression becomes eligible only after the reader returns on at least two distinct days after the first impression date.
- At most two ordinary impressions are shown. Once the second has been shown, later launches remain suppressed.
- Closing the screen with its dismiss control permanently opts out and survives subsequent launches.
- Choosing **Create account** opens the existing registration-first authentication flow. A successful result closes the encouragement, and the resulting permanent account suppresses future impressions.
- Permanent registered accounts are never prompted. Temporary accounts remain eligible under the same reading-history rules as logged-out readers.
- Opening an external article deep link does not launch the encouragement, even when the same reader would qualify on an ordinary application launch.

## Behavioral state transitions

- No impressions plus qualifying reading history moves to the visible first impression and persists its date.
- First impression plus **Maybe later** remains deferred after only one return-reading day, then moves to a visible second impression after the second distinct return-reading day.
- A visible impression moves to permanently dismissed when the close control is used, or to the registration flow when **Create account** is selected.
- Successful registration moves the reader to permanent-account suppression.
- Invalid persisted impression dates and stale reading history fail closed without crashing or fabricating another impression.

## Failure and recovery

- An unparsable persisted last-impression date suppresses repeat prompting and leaves the stored value intact; the application continues normally.
- Reading-history queries that do not satisfy every time-window constraint do not partially qualify the reader.
- External-link routing takes precedence over the encouragement and preserves its impression counters.
- Cancelling or leaving registration without a success result returns control without claiming account-creation success.

## Invariants

- Multiple article reads on one calendar day count as one reading day for eligibility.
- Eligibility and impression persistence use application-owned history and preference stores; analytics and authentication services are external leaves.
- Merely opening an eligible ordinary launch records one impression exactly once.
- **Maybe later** does not become permanent dismissal, while the close control does.
- Suppressed launches do not increment the impression count or replace the last-impression date.

## Non-goals

Server-side account creation, authentication protocol details, unrelated onboarding flows, changes to history retention, analytics delivery, and pixel-perfect card artwork or animation are outside this task.
