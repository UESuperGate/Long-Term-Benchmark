# Portable voice-note waveforms

## Version boundary

Implement the voice-note waveform behavior added between Signal Android v8.28.4 (`d0b314d2d7197c38737c6189d1f6c294e76e247e`) and v8.30.0 (`d8d36376f480eb4669efe8bfee94b2c196a9f7bd`). The base can derive a local display waveform, but it cannot attach the released waveform metadata to a sent voice note or preserve a sender-provided waveform across receive, storage, rendering, and backup flows.

## User outcome

Voice notes carry a stable waveform and duration with the attachment. A recipient can display the sender-provided shape before or without downloading the media, while locally generated waveforms remain reliable through upload preparation, persistence, rendering, and recovery.

## Functional requirements

- Generate a bounded, deterministic waveform and duration from decoded audio samples, including silence and full-scale input, and persist it with the local audio attachment.
- Gate an audio attachment upload on waveform generation after compression. Do not impose the waveform step on non-audio attachments or prevent unrelated uploads from progressing.
- Include the stored waveform and positive duration in an outgoing audio attachment pointer without changing the attachment's ordinary upload identity or encryption metadata.
- Reject incoming attachment payloads whose waveform exceeds the service limit. Rejection must happen before the invalid waveform is persisted or rendered.
- Accept a valid sender-provided audio waveform, preserve its bytes and duration, and mark its origin so it is not mistaken for a local cache entry.
- Render a sender-provided waveform at the UI's stable bar count by unsigned normalization and deterministic bucket resampling. Rendering must also work when the local media URI is unavailable.
- Treat an obsolete locally generated bar count as stale and regenerate it from the local audio rather than reusing it.
- Recover from an empty placeholder left by an interrupted or failed generation attempt by regenerating and replacing the placeholder.
- Preserve sender-provided waveform metadata through attachment database reload and backup export/import.

## State transitions

- Local audio without waveform -> generation -> persisted upload-ready waveform.
- Compressed audio -> waveform generation pending -> generation complete -> upload.
- Mixed audio and non-audio uploads -> audio waits for waveform while non-audio follows its ordinary chain.
- Stored local waveform -> outgoing attachment serialization -> waveform and duration on the wire payload.
- Oversized remote waveform -> envelope validation -> rejected without persistence.
- Valid remote waveform -> attachment import -> persisted sender-provided waveform -> database reload.
- Sender-provided waveform without local media -> resampling -> fixed-size render data.
- Stale or empty local waveform -> cache check -> regeneration -> persisted replacement.
- Persisted sender waveform -> backup export -> restore -> renderable waveform retained.

## Failure and recovery

Malformed or oversized remote metadata must fail closed without contaminating attachment state. Local generation failure may leave an explicit empty placeholder, but a later request with readable media must retry generation and replace that placeholder. A stale locally generated waveform must be regenerated; a valid sender-provided waveform must be retained and resampled rather than regenerated from unavailable media.

## Invariants

- Waveform generation completes before its audio upload starts.
- Non-audio attachments never acquire waveform-generation work.
- Sender-provided bytes are not silently rewritten during persistence, rendering, or backup round-trip.
- Generated and transported waveform magnitudes are unsigned values from silence through full scale.
- Invalid remote waveform metadata never reaches database or renderer state.
- Recovery changes only waveform metadata for the same attachment and does not duplicate the upload.

## Non-goals

Voice-note capture UI, playback controls, attachment encryption, CDN behavior, server limit policy, upload retry policy, and waveform pixel styling are outside this task. The ArkTS implementation is a migration target, not the benchmarked capability.
