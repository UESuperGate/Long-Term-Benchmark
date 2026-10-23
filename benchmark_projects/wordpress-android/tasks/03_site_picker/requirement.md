# Redesigned Site Picker

## Version boundary

- Base: WordPress for Android `24.6` (`38d40e2acee2f487dd2e43da908233e847ee4cc4`)
- Final: WordPress for Android `24.7` (`d70ced8dc334e6d930af5570b9d1498407835262`)

## User outcome

Replace the legacy site chooser with a site picker that makes frequently used sites easier to find. Users can distinguish pinned, recently accessed, and other sites; search the available sites; edit their pinned set; and select a site without losing a usable list when refresh operations fail.

## Functional requirements

1. Opening the picker shows the available sites in meaningful groups for pinned, recent, and remaining sites. A site must not appear in both the pinned and recent groups, and the currently active site remains identifiable.
2. Entering a search query replaces the grouped view with matching sites. Clearing the query or leaving search restores the complete grouped view.
3. Entering pin-editing mode exposes pin controls without selecting or opening a site. Pinning or unpinning immediately moves the site to the appropriate group, and leaving editing returns to normal selection behavior.
4. Selecting a site closes the picker through the normal selection flow and records it as recently accessed. A later visit reflects the updated recent ordering while preserving the pinned grouping rule.
5. A manual refresh visibly enters and exits a refreshing state. Successful refresh replaces the displayed data; a failed refresh stops progress and preserves the last usable list so the user can retry.
6. Picker variants that restrict site management must continue to allow valid site selection while hiding pin editing or site-creation actions that are not available in that context.

## Required state transitions

- Grouped list -> search results -> restored grouped list when search is entered and then cleared.
- Normal selection -> pin editing -> regrouped normal selection when a pin is changed and editing ends.
- Current site -> newly selected site -> updated recent ordering when the picker is opened again.
- Loaded list -> refreshing -> preserved loaded list on failure -> updated list after a successful retry.

## Failure and recovery

- A refresh failure must not strand the picker in a loading state or discard already displayed sites. Retrying after connectivity or service recovery must be able to load and display fresh data.
- A failed site-management action must leave the affected site visible and actionable so the operation can be attempted again.
- An empty result caused by search must be distinguishable from having no sites at all, and clearing search must recover the full list.

## Invariants

- A pinned site is not duplicated in the recent section.
- Editing pins does not accidentally select or switch the active site.
- Search and refresh do not silently change the selected site.
- The task is defined by observable behavior, not by specific class names, storage keys, or view hierarchy identifiers.

## Non-goals

- Restoring the removed show/hide-sites feature.
- Redesigning authentication, site creation, or account management.
- Prescribing a particular internal architecture or persistence mechanism.
