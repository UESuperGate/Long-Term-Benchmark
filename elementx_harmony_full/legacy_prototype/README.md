# Legacy Prototype

This directory preserves the original fixture-backed ArkTS prototype for audit
history. It is intentionally outside `entry/src/main` and is not packaged in
the production HAP.

The active application entry point is `pages/ReconstructedRoot`. Production
code fails closed when a Matrix transport capability is not implemented.
