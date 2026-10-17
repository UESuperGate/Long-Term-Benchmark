# Account Deactivation (Android v0.6.1 -> v0.6.3)

## User outcome

Users can deliberately deactivate their own account, choose whether to erase discoverable data, and retry safely after an error.

## Functional requirements

- Expose account deactivation from settings as a separate destructive flow.
- Keep password and erase-data choice in form state until completion or explicit exit.
- The first deactivate action opens a confirmation state and does not call the server.
- Confirming sends one deactivation request with the current password and erase-data choice.
- Canceling confirmation returns to the form with no request sent.
- A failed request keeps the form values, displays failure, and permits retry without another preliminary confirmation.
- Success exits the active session through the normal post-deactivation path and cannot be retried.

## Invariants and non-goals

- Ordinary logout must not deactivate the account.
- Empty or rejected credentials never produce a local success.
- Data export and administrator deactivation are outside this task.
