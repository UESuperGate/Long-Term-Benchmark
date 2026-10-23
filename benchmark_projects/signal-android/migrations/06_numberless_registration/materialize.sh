#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$root/../../../.." && pwd)/_sources/signal-android"

sources=(
  core/models-jvm/src/main/java/org/signal/core/models/AccountEntropyPool.kt
  core/ui/src/main/java/org/signal/core/ui/compose/EventDrivenViewModel.kt
  core/util/src/main/java/org/signal/core/util/billing/OneTimePurchaseApi.kt
  feature/registration/src/main/java/org/signal/registration/ReceiptCredentialResult.kt
  feature/registration/src/main/java/org/signal/registration/RegistrationFlowEvent.kt
  feature/registration/src/main/java/org/signal/registration/RegistrationFlowState.kt
  feature/registration/src/main/java/org/signal/registration/SignalLoginPriceResult.kt
  feature/registration/src/main/java/org/signal/registration/SignalLoginPurchaseResult.kt
  feature/registration/src/main/java/org/signal/registration/SignalLoginPurchaseStep.kt
  feature/registration/src/main/java/org/signal/registration/screens/addusername/AddUsernameScreenActions.kt
  feature/registration/src/main/java/org/signal/registration/screens/addusername/AddUsernameScreenEvents.kt
  feature/registration/src/main/java/org/signal/registration/screens/addusername/AddUsernameState.kt
  feature/registration/src/main/java/org/signal/registration/screens/addusername/AddUsernameViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/shared/AccountIdFormat.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogincredentials/SignalLoginCredentialEntryScreenEvents.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogincredentials/SignalLoginCredentialEntryScreenEventHandler.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogincredentials/SignalLoginCredentialEntryState.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogincredentials/SignalLoginManualSaveConfirmationViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoScreenActions.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoScreenEvents.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoState.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/ManualReceiptCredential.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/PaymentAvailability.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentScreenActions.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentScreenEvents.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentState.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentViewModel.kt
  lib/password-manager/src/main/java/org/signal/passwordmanager/SignalCredentialManager.kt
)

tests=(
  feature/registration/src/test/java/org/signal/registration/RegistrationEndToEndTest.kt
  feature/registration/src/test/java/org/signal/registration/SignalLoginPurchaseTest.kt
  feature/registration/src/test/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentViewModelTest.kt
  feature/registration/src/test/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoViewModelTest.kt
  feature/registration/src/test/java/org/signal/registration/screens/signallogincredentials/SignalLoginManualSaveConfirmationViewModelTest.kt
  feature/registration/src/test/java/org/signal/registration/screens/signalloginmanualsave/SignalLoginViewDetailsForManualSaveViewModelTest.kt
  feature/registration/src/test/java/org/signal/registration/screens/addusername/AddUsernameViewModelTest.kt
)

production_paths=(
  feature/registration/src/main/java/org/signal/registration/RegistrationNavigation.kt
  feature/registration/src/main/java/org/signal/registration/RegistrationRepository.kt
  feature/registration/src/main/java/org/signal/registration/RegistrationViewModel.kt
  feature/registration/src/main/java/org/signal/registration/SignalLoginPurchaseStep.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/PaymentAvailability.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentState.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogininfo/SignalLoginInfoViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/signalloginmanualsave/SignalLoginViewDetailsForManualSaveViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/signallogincredentials/SignalLoginManualSaveConfirmationViewModel.kt
  feature/registration/src/main/java/org/signal/registration/screens/addusername/AddUsernameViewModel.kt
  core/util/src/main/java/org/signal/core/util/billing/OneTimePurchaseApi.kt
  lib/billing/src/main/java/org/signal/billing/OneTimePurchaseApiImpl.kt
  lib/network/src/main/java/org/signal/network/api/RegistrationApiV2.kt
  app/src/main/java/org/thoughtcrime/securesms/registration/v2/AppRegistrationNetworkController.kt
)

materialize() {
  local name="$1" ref="$2" project
  project="$root/android/$name"
  rm -rf "$project/immutable-src"
  mkdir -p "$project/immutable-src"
  : > "$project/.inventory.tsv"
  for source in "${sources[@]}"; do
    if [[ "$name" == base ]]; then
      case "$source" in
        core/models-jvm/src/main/java/org/signal/core/models/AccountEntropyPool.kt|\
        core/ui/src/main/java/org/signal/core/ui/compose/EventDrivenViewModel.kt|\
        feature/registration/src/main/java/org/signal/registration/ReceiptCredentialResult.kt|\
        feature/registration/src/main/java/org/signal/registration/RegistrationFlowEvent.kt|\
        feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/ManualReceiptCredential.kt|\
        feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentScreenActions.kt|\
        feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentScreenEvents.kt|\
        feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentState.kt|\
        feature/registration/src/main/java/org/signal/registration/screens/signalloginpayment/SignalLoginPaymentViewModel.kt) ;;
        *) continue ;;
      esac
    fi
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      mkdir -p "$project/immutable-src/$(dirname "$source")"
      git -C "$repo" cat-file blob "$ref:$source" > "$project/immutable-src/$source"
      printf '%s\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(wc -c < "$project/immutable-src/$source" | tr -d ' ')" "$(shasum -a 256 "$project/immutable-src/$source" | awk '{print $1}')" >> "$project/.inventory.tsv"
    fi
  done
  : > "$project/.tests.tsv"
  for source in "${tests[@]}"; do
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      printf '%s\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(git -C "$repo" cat-file -s "$ref:$source")" "$(git -C "$repo" cat-file blob "$ref:$source" | shasum -a 256 | awk '{print $1}')" >> "$project/.tests.tsv"
    fi
  done
  : > "$project/.production.tsv"
  for source in "${production_paths[@]}"; do
    if git -C "$repo" cat-file -e "$ref:$source" 2>/dev/null; then
      printf '%s\tpresent\t%s\t%s\t%s\n' "$source" "$(git -C "$repo" rev-parse "$ref:$source")" "$(git -C "$repo" cat-file -s "$ref:$source")" "$(git -C "$repo" cat-file blob "$ref:$source" | shasum -a 256 | awk '{print $1}')" >> "$project/.production.tsv"
    else
      printf '%s\tabsent\t\t0\t\n' "$source" >> "$project/.production.tsv"
    fi
  done
  python3 - "$project" "$ref" <<'PY'
import json, pathlib, sys
project, ref = pathlib.Path(sys.argv[1]), sys.argv[2]
def rows(name):
    values=[]
    for line in (project/name).read_text().splitlines():
        path, blob, size, sha = line.split('\t')
        values.append({'path': path, 'gitBlob': blob, 'bytes': int(size), 'sha256': sha})
    return values
(project/'IMMUTABLE_SOURCES.json').write_text(json.dumps({'schemaVersion':2,'sourceCommit':ref,'classification':'official_immutable_production_bytes','files':rows('.inventory.tsv')},indent=2)+'\n')
(project/'VERIFIED_TEST_PATHS.json').write_text(json.dumps({'schemaVersion':1,'sourceCommit':ref,'classification':'official_test_evidence_not_packaged','files':rows('.tests.tsv')},indent=2)+'\n')
production=[]
for line in (project/'.production.tsv').read_text().splitlines():
    path, status, blob, size, sha = line.split('\t')
    production.append({'path': path, 'status': status, 'gitBlob': blob or None, 'bytes': int(size), 'sha256': sha or None})
(project/'VERIFIED_PRODUCTION_PATHS.json').write_text(json.dumps({'schemaVersion':1,'sourceCommit':ref,'classification':'official_task_production_path_evidence','files':production},indent=2)+'\n')
(project/'.inventory.tsv').unlink()
(project/'.tests.tsv').unlink()
(project/'.production.tsv').unlink()
PY
}

materialize base 15e5d644924352fa03900969ad6de0e648e5e2d0
materialize final c6e21632f6abb16f1e8ccc303201b68d5d700353
