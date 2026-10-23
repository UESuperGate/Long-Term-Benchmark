# Phone-numberless registration

## Version boundary

Implement the phone-numberless registration capability added between Signal Android v8.26.4 and v8.28.0. The base contains preliminary screens for this work but cannot complete the released one-time-purchase registration journey. The final behavior must form a complete alternative to entering and verifying a phone number.

## User outcome

A new user can choose to create a Signal account without supplying a phone number, pay the one-time anti-spam fee, preserve the issued login credentials, and optionally claim a username before entering the app. The payment must not be directly associated with the account created from it.

## Functional requirements

- Offer phone-numberless registration as an alternative from the registration entry flow when the capability is available, without removing the ordinary phone-number path.
- Load and display the one-time purchase price and prevent purchase submission until a usable price or an already-paid purchase is available.
- Complete the one-time in-app purchase and redeem privacy-preserving proof of payment to create an account without a phone number.
- If an earlier purchase was paid but not redeemed, resume that purchase rather than charging again.
- After account creation, present the account login and recovery key and require the user to preserve and confirm them before continuing.
- Support saving the login through an available password manager and verify that the same credential can be read back before treating it as safely stored.
- Provide a manual preservation path when the password manager is unavailable, canceled, or cannot confirm the saved credential. The user must re-enter the issued values correctly before advancing.
- Allow the user to choose an optional username. Validate and reserve the current choice, confirm it before completion, and require explicit confirmation before skipping this step.
- Complete registration with numberless account state and no phone-number identity material.

## State transitions

- Registration entry -> choose registration without a number -> price loading -> purchase ready.
- Purchase ready -> purchase in progress -> payment proof redeemed -> numberless account registered -> login credentials displayed.
- Login credentials displayed -> password-manager save -> saved credential confirmed -> optional username step.
- Login credentials displayed -> manual preservation -> credential re-entry -> matching credential confirmed -> optional username step.
- Username draft -> validation and reservation -> username confirmed -> registration complete.
- Username step -> skip requested -> skip canceled and remain editing, or skip confirmed -> registration complete without a username.

## Failure and recovery

- A transient price lookup failure offers retry; a terminally unavailable purchase explains that payment cannot proceed while leaving other registration choices accessible.
- Canceling the purchase returns to a usable purchase state without creating an account or reporting success.
- A pending, unredeemed, or network-failed purchase remains recoverable. Retrying must reuse the paid purchase and its proof context rather than charge again.
- If required payment services are unavailable but repairable, the user can resolve the condition and retry price loading or purchase.
- A canceled, interrupted, mismatched, or missing password-manager credential does not count as confirmed. The user can retry or switch to manual preservation.
- A mistyped manual credential remains editable and can be corrected. Username reservation failures remain retryable without discarding the current draft.

## Invariants

- Numberless registration never requires an SMS session or a phone number and does not create phone-number identity keys.
- A successful purchase is consumed exactly once, only after its proof has registered the account successfully.
- Failed redemption or registration preserves the paid purchase for recovery and does not initiate another charge on retry.
- Registration does not advance past normal credential preservation unless the issued account ID and recovery key have been confirmed.
- Username selection remains optional, but skipping it always requires an explicit confirmation.
- Failures and cancellations never masquerade as registration success.

## Non-goals

Phone-number registration, recurring payments, donations, post-registration recovery-key management, general username editing after onboarding, server pricing policy, and unrelated backup behavior are outside this task.
