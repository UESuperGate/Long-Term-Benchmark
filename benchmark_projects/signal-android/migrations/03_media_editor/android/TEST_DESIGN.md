# Android focused runtime test design

The evaluator materializes exact official source bytes from the commits pinned in
`android/task.json`. The final probe executes the upstream media-send reducer,
saved-state restoration, transform construction, and streaming transcoder. The
base probe executes the legacy `EditorState.VideoTrim` and
`TransformProperties.empty()` production prefix, then records the absence of the
canonical per-video mute transition as a semantic failure.

The ten cases cover mute eligibility, mute/unmute, focus and reorder preservation,
process restoration, cancel/discard behavior, legacy transform defaults, muted
transform preparation, and audio-free transcoding. Case 10 supplies a real
1558-byte H.264 MP4 fixture (SHA-256
`d0349b049dec32cce83e2f04967e94e4484801cb6a7a972db3d9bf5c33a69996`) to
Android's `MediaMetadataRetriever`, then observes the exact production
`StreamingTranscoder.transcode()` call into the controlled converter leaf.

Evaluator probes and leaves are outside `immutable-src`. The scorer consumes only
runtime before/after states, ordered effects, absent effects, and invariants. It
accepts an explicit candidate directory, does not inspect source patterns or role
markers, and requires a reachable common production prefix for base semantic
failures. Both focused projects compiled into signed installable APKs and ran on
API37 ART: base 0/10, final 10/10, with zero unscored cases.
