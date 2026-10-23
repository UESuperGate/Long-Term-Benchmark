# Unified bot and Happiness Engineer support

## Version boundary

Implement the unified support capability introduced between WordPress Android 26.8 (`20d41cdcd693e381a8c823ec2c93fc39efc9cf0c`) and 26.9 (`510f1cddc186a486ffa9559018578a644d303d96`), centered on pull request 22946 and merge commit `ad1de650a67b426b807e14c46d249924b028ac0c`. The official tags are release-branch snapshots rather than a locally provable ancestor chain; the 26.8 tree has been directly verified not to contain the unified support package or entry point.

## User outcome

Signed-in users reach one Get help experience that lists bot and Happiness Engineer conversations together, opens an appropriate detail experience for each type, creates bot conversations, and sends or recovers replies without losing user input.

## Functional requirements

- Replace separate bot and Happiness Engineer menu entries with one Get help entry backed by a unified list/repository path.
- Render bot and Happiness Engineer items in one list. Bot rows are identified as bot conversations; Happiness Engineer rows retain ticket status.
- Surface list request failures as an error/offline state instead of an empty successful list, and allow a later retry to recover.
- Open bot details with an inline chat composer. Open replyable Happiness Engineer details with a reply-sheet action. Open closed, non-replyable Happiness Engineer details with a closed banner and no reply action.
- Create a new bot conversation locally, then execute the application-owned bot creation bridge on the first send. Keep the local user question and append the returned bot reply.
- For an existing conversation, add an optimistic user message, clear the input while sending, execute the production repository mapping, replace list/detail state on success, clear the reply form, and clean temporary attachments.
- When offline, retain the draft, expose an offline error, and do not call the repository. On remote failure, remove only the optimistic message, restore the sent text if the user has not typed newer text, expose a general error, and leave the conversation retryable.
- Reject concurrent duplicate sends while one send is active.
- Keep reply-form state across page recreation through the production view model. Clear text, attachments, app-log selection, and sheet visibility when another conversation is opened so drafts cannot leak between conversations.

## Failure and recovery

All remote outcomes are supplied only at declared WordPress service/upload/temp-file leaves. The application-owned repository, request mapping, optimistic update, rollback, list replacement, form state, and cleanup bodies must execute. Errors remain observable state and never become synthetic empty successes.

## Invariants

- A send invokes at most one create-or-reply operation.
- A failed send never removes pre-existing messages or overwrites newer draft text.
- Temporary attachment files are cleaned after both success and failure.
- Draft state belongs to one selected conversation and cannot leak to another.
- Bot/HE presentation is derived from conversation status and reply capability, not evaluator case identity.

## Non-goals

The task does not require a live support account, alter server behavior, or restore the retired separate support flows. The ArkTS implementation is a functional migration target and not the capability being measured.
