# Media Upload Quality (Android v25.08.2 -> v25.08.3)

## User outcome

Before sending media, users can choose an appropriate image or video quality and understand when the resulting upload exceeds the homeserver limit.

## Functional requirements

- Load the homeserver upload limit and media metadata asynchronously while keeping the attachment preview usable.
- For images, expose the supported optimization choice and persist the selected default.
- For video, estimate output size for available quality presets and identify presets that exceed the upload limit.
- Opening, selecting, and dismissing the quality chooser must preserve the current valid choice.
- An unavailable or oversized preset cannot silently become selected.
- Sending is blocked with actionable feedback when the source or every valid output exceeds the limit.
- Metadata, estimation, or preference failures must produce a stable fallback or visible error and must not fabricate a sendable size.

## Invariants and non-goals

- The server-provided limit remains authoritative.
- Existing captions and attachment ordering are preserved when quality changes.
- New codecs and server configuration changes are outside this task.
