# Responsive media editor with video audio removal

## Version boundary

Implement the media-editor behavior introduced between Signal Android v8.22.2 (`e3a7a9c8764bf5961bbbb54f5d72d1056dd3974e`) and v8.23.0 (`64fa9f50a38fecb088135fd0200c331fe0686bd3`).

## User outcome

Users can review and edit one or more selected media items in an editor that remains usable across phone, tablet, and foldable layouts. For an ordinary video, they can remove its audio before sending while keeping edits attached to the correct item throughout the send flow.

## Functional requirements

- Keep the editor's selection, focused item, ordering, message metadata, and per-item edits synchronized with the enclosing media-send flow. Changing focus or reordering items must not transfer one item's edits to another item.
- Restore editor state after recreation so selected media, focus, and completed edits do not silently reset.
- Offer audio removal only for an editable video. Do not offer it for images, documents, or video-GIF items.
- Toggling audio removal updates only the focused video's edit state. Toggling it again restores audio, and selecting another item reveals that item's own setting.
- Give immediate user feedback when a video becomes muted.
- Treat a first video edit as invalidating any pre-uploaded version of that item so the eventual send cannot use stale media.
- Carry trim and audio-removal choices through attachment preparation and video processing. A muted video must retain its video track and omit its audio track in the sent output.
- Preserve backward compatibility for stored attachment transforms that predate audio removal; missing audio-removal data must behave as unmuted.
- When closing a flow that still contains selected media, ask before discarding it. Confirming exits and discards the pending work; canceling keeps the flow and all edits intact.
- In a camera-first flow with only the just-captured item selected, backing out of the editor discards that capture and returns to the camera rather than leaving an empty editor.

## Invariants

- Edit state is keyed to media identity, not pager position.
- Audio removal defaults to off and never applies to unsupported media types.
- Reordering or changing focus does not change media membership or edit contents.
- Sending uses the latest accepted edit state and cannot reuse an earlier pre-upload after that media was edited.
- Canceling discard has no attachment, upload, or navigation side effect.

## Failure and recovery

Discard cancellation is the required recovery path: dismissing or canceling the discard confirmation returns the user to the same media-send state with the same selection, focus, order, and per-item edits. A confirmed discard is the only close action in this path that may abandon those edits.

## Non-goals

Media capture, gallery discovery, image-tool algorithms, story publishing rules, and codec or quality-policy changes unrelated to honoring audio removal are outside this task. The ArkTS implementation is a migration target, not the benchmarked capability.
