"""Archive immutable Android wiring and the proposed ArkTS migration boundary."""

import argparse
from pathlib import Path
import shutil
import subprocess

from . import task12_13_formal_core as core

COMMIT = 'bee248e2d59149d0deab4da4b8265199cb722ffe'
ANDROID_PATHS = (
    'features/userprofile/impl/src/main/kotlin/io/element/android/features/userprofile/impl/UserProfileFlowNode.kt',
    'features/verifysession/impl/src/main/kotlin/io/element/android/features/verifysession/impl/outgoing/VerifySelfSessionPresenter.kt',
    'features/verifysession/impl/src/main/kotlin/io/element/android/features/verifysession/impl/outgoing/VerifySelfSessionStateMachine.kt',
    'libraries/matrix/api/src/main/kotlin/io/element/android/libraries/matrix/api/verification/SessionVerificationService.kt',
    'libraries/matrix/impl/src/main/kotlin/io/element/android/libraries/matrix/impl/verification/RustSessionVerificationService.kt',
    'features/roomdetails/impl/src/main/kotlin/io/element/android/features/roomdetails/impl/members/details/RoomMemberDetailsPresenter.kt',
    'features/roomdetails/impl/src/main/kotlin/io/element/android/features/roomdetails/impl/members/RoomMemberListPresenter.kt',
    'features/messages/impl/src/main/kotlin/io/element/android/features/messages/impl/crypto/identity/IdentityChangeStatePresenter.kt',
    'libraries/matrix/impl/src/main/kotlin/io/element/android/libraries/matrix/impl/room/RustMatrixRoom.kt',
    'libraries/matrix/impl/src/main/kotlin/io/element/android/libraries/matrix/impl/encryption/RustEncryptionService.kt',
    'libraries/matrix/test/src/main/kotlin/io/element/android/libraries/matrix/test/verification/FakeSessionVerificationService.kt',
)

PLAN = """# Task13 ArkTS Wiring Repair: Pending Review

Status: NOT READY. This is a proposal and an immutable-source evidence archive,
not authorization to change the final. Canonical revision5, bindings and old model
patches remain unchanged. No existing score is restored by this document.

## Confirmed Limitations

- Index.ets owns a presenter at line19, but adapter actionPrefix constructs a
  separate presenter/identity/gateway. Same class code is not same owner evidence.
- Original UI calls requestVerification at line81. Its Continue button calls
  remoteAcceptedRequest at line90. Start calls both startSasVerification and
  receiveChallenge with hardcoded SAS at lines105-106. These are not external
  SDK callbacks. Gateway only increments in-memory counters.
- Starting with a verification-violation profile hides Verify. Withdrawing to
  reveal Verify clears that identity state. Cases needing violation during the
  request cannot be established by an offline object's constructor.
- A mounted profile followed by a detached domain transition proves neither
  actual routing nor SDK effects. Retain those runs only as diagnostics.

## Immutable Android Mapping

All paths below are archived from final commit
bee248e2d59149d0deab4da4b8265199cb722ffe, not the mutable current checkout.

1. UserProfileFlowNode:87-88/112-115 pushes VerifyUser and passes
   VerificationRequest.Outgoing.User(userId) into the real verification node.
   ArkTS must have an actual profile-to-verification route preserving user ID,
   separate from self-session verification. It must own the presenter lifecycle.
2. VerifySelfSessionPresenter:98-103 dispatches only user intent. Lines149-181
   collect service events and dispatch acceptance, start, challenge, finish,
   cancellation and failure. ArkTS must subscribe/unsubscribe a production
   verification service for that same owner; no synthetic Continue/Finish SDK UI.
3. VerifySelfSessionStateMachine: request/start/approve/decline/cancel/reset
   invoke SessionVerificationService, retain actual SAS payload and pending state,
   and wait for SDK completion. Port this reducer/effect separation and ordering.
4. RustSessionVerificationService calls SessionVerificationController; its
   delegate didAcceptVerificationRequest/didStartSasVerification/
   didReceiveVerificationData/didFinish/didFail emits the real flow. Successful
   finish is gated by SDK verified status, not an evaluator boolean. The ArkTS
   Gateway must delegate the same explicit service port. Like Android's
   FakeSessionVerificationService, the evaluator may inject a controlled external
   service implementation at that port, including delayed completion/failure
   and emitted service callbacks. No Rust/Olm rewrite or real homeserver is
   required for this benchmark boundary. The double must not implement the
   production reducer, create another presenter or assign its fields.
5. RoomMemberDetailsPresenter:81-101 combines encrypted room information,
   getUserIdentity and identityStateChangesFlow. RoomMemberListPresenter:185-190
   excludes nonencrypted identity decoration. RustMatrixRoom:154 implements the
   SDK identity listener. Connect these production inputs to the profile,
   timeline and member list, including unrelated-member isolation.
6. IdentityChangeStatePresenter:60-61 and RoomMemberDetailsPresenter:112 call
   encryptionService.withdrawVerification; RustEncryptionService:213-214 calls
   the SDK identity object. A local store clear or counter is not that effect.

## Proposed Change Boundary After Review

- Archive the entire active final source and hashes before any production edit.
  Preserve immutable Android blobs, old raw runs and source inventories.
- Add production session-scoped verification/identity ports, a delegating Gateway,
  lifecycle subscriptions and route-owned state. The app composition root owns
  that service; the test harness substitutes only this external dependency.
  Record calls, completion/rejection and callback delivery at that boundary,
  not candidate-owned counters. Production presenter/reducer remains unchanged
  by evaluator injection and consumes the original service results/events.
- Replace synthetic SDK-event buttons and hardcoded SAS in Index with rendered
  subscribed production state and real user intents. Restore normal room/member
  navigation and SDK-fed encrypted/identity input chain. Do not seed testcase
  names, outcomes, success states or evaluator reducers into production.
- Observer wraps original methods while physical production UI runs, records
  same-receiver presenter/gateway/identity IDs and original SDK callback receipts.
  Never instantiate a second domain model to supply scored facts.
- External tests drive the production adapter's established service boundary, not private
  presenter field assignments. Recompute before/event/after and each invariant
  from that same run; no guessed given state or expected-value fallback.
- Version-audit the repaired final, then fresh base/final/random base-copy and
  final-copy controls under one evaluator, shared device lock and one <=3600s
  deadline. Application compile and evaluator runtimeCompile stay separate.
  Preserve actual native/execution/build/log bytes, hash then delete binaries.
- Old model patch remains tied to its original base and inputs; repaired-base
  fresh model experiments require a later separate authorized run.

Review needed: production SDK boundary/platform implementation and the precise
final migration diff. This proposal does not itself change active final.

## Proposed Service/Event Interface

Production SessionVerificationPort mirrors Android SessionVerificationService:
requestUserVerification(userId), requestCurrentSessionVerification(),
startVerification(), approveVerification(), declineVerification(),
cancelVerification(), reset(cancelAnyPendingVerificationAttempt), with real
asynchronous return/rejection and subscriptions for verificationFlowState and
verified status. Profile routing supplies one user request to one page owner.

- request -> Gateway delegates requestUserVerification; awaiting state does not
  imply acceptance. DidAcceptVerificationRequest callback alone makes Ready.
- Start user intent -> startVerification, then waits. DidStartSasVerification
  callback establishes SAS-started/pending. DidReceiveVerificationData(payload)
  delivers challenge data; never synthesize it inside the Start button.
- Accept/Decline user intent -> matching delegated service operation and loading.
  Completion alone is not verification success. DidFinish plus the original
  verified/identity input gate completes; DidFail/DidCancel drive cancellation.
- Reset delegates reset(false), preserves user request and violation state, and
  starts no success path. Initial owner setup reset(true) is a separate operation.
- IdentityPort mirrors getUserIdentity, room identity-change subscription,
  encrypted-room input and withdrawVerification(userId). Rendered warning and
  member state follow its actual updates, never unconditional local mutation.

The evaluator double is external to the candidate and retains its own ordered
call/in-flight/completion/event ledger. Native page observers capture original
method receivers and subscription IDs; all observations must agree on the same
route-owned presenter, identity input, Gateway and service instance. Mutating the
double alone must not advance UI state without the production subscription.
"""


def build(output):
    output = output.resolve()
    if output.exists():
        raise ValueError('Refusing existing wiring plan audit')
    task = core.load(core.ROOT / 'benchmark_tasks/13_user_verification/task.json')
    if task['android']['finalCommit'] != COMMIT:
        raise ValueError('Immutable final commit differs')
    output.mkdir(parents=True)
    repo = core.ROOT / '_sources/element-x-android'
    records = []
    for relative in ANDROID_PATHS:
        target = output / 'android-final' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git', '-C', str(repo), 'show', COMMIT + ':' + relative]))
        blob = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', COMMIT + ':' + relative], text=True).strip()
        records.append({'path': relative, 'gitBlob': blob, 'snapshot': core.file_record(target)})
    active = core.ROOT / task['arkts']['finalPath']
    snapshot = output / 'arkts-final-before'
    shutil.copytree(active, snapshot, ignore=shutil.ignore_patterns('.git', 'build', '.hvigor',
        '.gradle', 'oh_modules', 'node_modules'))
    original_inventory = core.source_inventory(active)
    archived_inventory = core.source_inventory(snapshot)
    if original_inventory['sha256'] != archived_inventory['sha256']:
        raise ValueError('Final snapshot incomplete')
    plan = output / 'REVIEW_PLAN.md'
    plan.write_text(PLAN)
    core.write(output / 'manifest.json', {'taskId': '13_user_verification', 'readyCandidate': False,
        'status': 'review_pending_no_production_edits', 'androidCommit': COMMIT,
        'androidSources': records, 'activeFinalInventory': original_inventory,
        'archivedFinalInventory': archived_inventory, 'plan': core.file_record(plan),
        'canonical': core.file_record(core.ROOT / 'benchmark_tasks/13_user_verification/transitions.json'),
        'binding': core.file_record(core.ROOT / 'migrations/13_user_verification/arkts/bindings.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(**vars(parser.parse_args()))
