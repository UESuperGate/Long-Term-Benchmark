# Task08 Normalizer History

Files named `<sha256>.py` preserve the exact host normalizer bytes recorded by
completed runtime executions. They are data, never imported or executed.

`verify_implementation_receipt` checks the original receipt SHA and byte length,
then requires identical ASTs for the five original normalization/assertion
functions. Public host-verifier extensions do not change historical receipts.
An archived implementation with different assertions is rejected even when
its filename and byte hash are internally consistent.

Archive an implementation before changing a live source version that has been
recorded by runtime executions. Never replace an old receipt's hash with the
new live source hash. Native fixtures and canonical contracts keep their own
independent source/hash checks.
