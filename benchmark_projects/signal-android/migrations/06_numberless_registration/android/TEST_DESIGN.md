# Android focused runtime test design

The evaluator materializes exact official reducer and state-model bytes from the
commits pinned in `android/task.json`. The final probe directly executes the
upstream payment, credential confirmation, login-info, and username ViewModels.
The base probe executes the legacy payment reducer through `Initialize` and
`ContinueClicked`; its reachable purchase branch is still a TODO, so each missing
canonical transition is scored as a semantic failure after a real common prefix.

The ten cases cover purchase eligibility and price, held completion, cancellation,
billing retry, private receipt registration propagation, manual credential
verification mismatch, username skip confirmation, discriminator conflict
recovery, purchase-context restoration, and password-manager save/readback plus
final registration navigation. Process restoration uses real file IO and a new
repository-leaf instance; the credential case passes through the exact production
reducers on both save and readback legs.

The complete production and test path sets from the task contract are verified
against Git objects in `VERIFIED_PRODUCTION_PATHS.json` and
`VERIFIED_TEST_PATHS.json`. The dependency-heavy repository/network, billing,
credential platform, navigation, and service implementations are controlled
leaves; they record ordered effects but do not replace the exact ViewModel
reducers under test.

The scorer consumes only runtime state/effect observations, accepts an explicit
candidate directory, and does not inspect role markers or source patterns. Both
focused projects compiled into signed installable APKs and ran on API37 ART: base
0/10, final 10/10, with zero unscored cases.
