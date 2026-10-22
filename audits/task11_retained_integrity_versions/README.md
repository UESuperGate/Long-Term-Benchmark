# Task11 Independent Verifier Versions

`v1.py` preserves exact verifier source bytes referenced by the three initial
`task11_parent_{raw,base,final}_integrity_v1.json` receipts. It is historical
source, not the current executed verifier. No original receipt is rewritten.

The current verifier additionally binds execution nonce to the native bridge and
process-log marker, with exact task/role/case, output filename and byte count.
The successor v2 receipts require a new full verification; calibration assertions
and candidate source/patch are unchanged.
