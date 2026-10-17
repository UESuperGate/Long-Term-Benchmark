# Custom Notification Sounds (Android v26.05.2 -> v26.06.1)

## User outcome

Users can independently choose message sounds and call ringtones from presets or device files and keep those choices across restarts.

## Functional requirements

- Message sound and call ringtone have independent current values, labels, dialogs, picker launches, and error states.
- Users can choose the system default, a bundled preset, or a supported device audio document.
- A device document is copied into app-owned storage before it becomes active; display names remain available after restart.
- Persist the chosen sound and update the corresponding notification channel so future notifications use it.
- Migrate an existing call-channel ringtone without overwriting an explicit new preference.
- Serialize concurrent updates per sound slot so late operations cannot overwrite a newer valid choice.
- Copy, persistence, or channel-update failure preserves the previous effective sound and exposes a dismissible retryable error.

## Invariants and non-goals

- Changing the message sound never changes the call ringtone, and vice versa.
- Per-room sounds, remote ringtone downloads, and push-rule changes are outside this task.
