# All Domains Management and Purchase Lifecycle

## Version boundary

- Base: WordPress for Android `23.6` (`08547658c58afeb4f0db8da183c8ef9928ed6b41`)
- Final: WordPress for Android `23.7` (`3dbc6929c7a74a12af63a616a22b0674010d122d`)

The base contains an early domain-list and purchase shell, but it does not provide the final connected search, purchase, checkout-result, recovery, and contained-details workflow announced for 23.7.

## User outcome

Jetpack users can manage all of their domains from one in-app flow. They can distinguish loading, empty, error, complete, and filtered states; recover failed loads; search for a new paid domain; choose whether to purchase it alone or attach it to an existing site; recover a failed cart submission; finish or cancel checkout; and safely view supported domain details without allowing arbitrary pages to remain inside the authenticated details web view.

## Functional requirements

1. Opening All Domains loads the account's domains and renders a distinct loading state followed by a complete list, an empty state, or a recoverable error state. A loaded row retains its domain identity, site title, status, expiry information, and details destination.
2. The empty-state action and the add-domain action open the new-domain search flow. A list-load error exposes retry; retry enters loading again and replaces the error with the newly fetched result.
3. Filtering an already loaded list is case-insensitive and can match the domain, site slug, or site title. Clearing the filter restores the same complete source list without refetching it or changing domain identity.
4. New-domain search ignores blank input, waits 250 ms before dispatching a nonblank query, and keeps only the latest query when another query arrives while earlier work is pending. Stale results must not replace the latest result.
5. Search results exclude free suggestions, retain product identifier, domain, price, optional sale price, and privacy support, and are ordered by descending relevance. A remote mismatch or failed suggestions response becomes an explicit error that can be retried with the retained query.
6. Selecting a proposed domain opens a purchase-mode screen with that domain's product identifier and privacy capability. The user can purchase the domain alone or choose an existing site; these modes remain distinct through cart submission.
7. Cart submission visibly distinguishes domain-only and existing-site progress, disables duplicate submissions while active, and routes a successful cart to the matching checkout or eligible plan flow. A failed cart shows an error, does not navigate, and can be acknowledged and retried from the same domain selection.
8. A successful checkout and a user-cancelled checkout both return to All Domains through the production result path. A missing or invalid checkout result remains an error rather than being treated as completion.
9. The in-app domain-details web view may remain on the matching `wordpress.com/domains/manage/all/<domain>/edit/...` path. Another host or another path is rejected from the contained web view and handed to the external-navigation path.

## Failure and recovery

List, search, cart, and checkout failures are explicit states. Retry repeats the relevant application-owned operation with the retained user input. Older search completions cannot overwrite a newer query. Cart failure never launches checkout, and an invalid checkout result never reports completion. URL rejection preserves the domain-management screen while routing the unsupported destination outside the contained details view.

## Invariants

- Filtering and remote search never mutate the account's stored domain list.
- Search results correspond to the latest normalized nonblank query.
- Product identifier, domain name, and privacy support remain attached to the selected proposal throughout purchase routing.
- A cart request is made at most once per explicit purchase attempt.
- Domain-only and existing-site cart modes never silently change into one another.
- Cancellation is not reported as a successful registration, even though both outcomes return to All Domains.
- The details web view never retains an unsupported host, domain, or path.

## Non-goals

The task does not require live WordPress.com traffic, alter server-side pricing or eligibility, prescribe an implementation architecture, score analytics payloads, or require pixel-identical Android and ArkUI rendering.
