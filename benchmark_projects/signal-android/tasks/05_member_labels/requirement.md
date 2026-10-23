# Group member labels

## Version boundary

The evaluated candidate boundary is Signal Android v8.4.1 (`c7ec3ab837b3c149d5579840317b1dc6cd4629f3`) to v8.5.0 (`068eaff8010365353410914fbcf1bed79e69d6bb`). This candidate is rejected because the complete behavior described below is already present in the base release.

## User outcome

Group members can create, edit, and clear a short role label that appears with their identity inside that group. Group administrators can choose whether every member or only administrators may set labels, with safe handling when a permission change would invalidate existing labels.

## Functional requirements

- Load the current member's label and show an editable text and optional emoji representation together with a preview of how it will appear.
- Treat unchanged, empty, over-limit, whitespace-only, or emoji-only input according to the label validation rules, and enable saving only for a valid change or an intentional clear.
- Saving a valid edit transitions through an in-progress state and synchronizes the sanitized label as a group change. A successful save makes the new label available to conversation and member-detail surfaces.
- Clearing an existing label is a valid change and removes both its text and emoji after a successful save.
- Preserve labels through group synchronization and backup export/import.
- Let administrators choose between all-members and administrators-only label permissions through the Edit group info controls.
- If restricting permission would invalidate labels held by non-administrators, warn before applying the change. Confirmation applies the restriction and its cleanup; cancellation preserves the current permission and labels.
- Members without permission cannot submit a label change and receive permission-specific feedback.

## State transitions

- Loaded label -> edited valid label -> save in progress -> saved label.
- Existing label -> cleared draft -> save in progress -> no label.
- All-members permission -> restriction warning -> confirmed administrators-only permission, or canceled unchanged permission.
- Save in progress -> network or permission error -> editable state -> corrected or retried save.

## Invariants

- Labels are scoped to a group and member identity and do not replace global profile data.
- An emoji without valid label text is not a valid saved label.
- Repeating an unchanged value does not submit a group mutation.
- Permission changes do not silently remove affected labels before confirmation.
- Network or permission failure does not report success or discard the editable value.

## Failure and recovery

A network failure returns the editor to a recoverable error state with the draft preserved for retry. A permission failure reports that the member can no longer make the change. Canceling the administrator warning leaves access control and existing non-admin labels unchanged.

## Non-goals

Group termination, general role administration, global profile editing, and unrelated conversation presentation are outside this candidate.

## Rejection rationale

This document records the intended state graph for evidence review, but it is not a valid implementation handoff for the stated boundary. The base already contains the editor, validation, protocol mutation, permission control, backup support, focused tests, and failure states. The only member-label-related candidate-interval change adds a guard for terminated groups, which belongs to the separate group-termination capability. The closest release activation before v8.4.0 is a feature-flag removal, which does not satisfy the long-horizon gate.
