# State Dynamic Target Matrix

- Generated: 2026-10-09T12:58:07
- Targets: 25
- Case-target rows: 750
- Golden polarity: base fail; groundtruth_final pass
- Agent result scoring: agent_result is expected pass against final-oriented cases, but is not used to validate testcase polarity

## Targets
- `01_user_status:android:base` role `base` expected `fail` groundtruth `True` tag `v26.07.0` artifactExists `False`
- `01_user_status:android:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.4` artifactExists `False`
- `01_user_status:arkts:base` role `base` expected `fail` groundtruth `True` tag `v26.07.0` artifactExists `True`
- `01_user_status:arkts:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.4` artifactExists `True`
- `01_user_status:arkts:agent_result` role `agent_result` expected `pass` groundtruth `False` tag `v26.08.4` artifactExists `True`
- `02_gallery_messages:android:base` role `base` expected `fail` groundtruth `True` tag `v26.06.1` artifactExists `False`
- `02_gallery_messages:android:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.1` artifactExists `False`
- `02_gallery_messages:arkts:base` role `base` expected `fail` groundtruth `True` tag `v26.06.1` artifactExists `True`
- `02_gallery_messages:arkts:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.1` artifactExists `True`
- `02_gallery_messages:arkts:agent_result` role `agent_result` expected `pass` groundtruth `False` tag `v26.08.1` artifactExists `True`
- `03_timeline_protection_rich_events:android:base` role `base` expected `fail` groundtruth `True` tag `v26.07.1` artifactExists `False`
- `03_timeline_protection_rich_events:android:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.0` artifactExists `False`
- `03_timeline_protection_rich_events:arkts:base` role `base` expected `fail` groundtruth `True` tag `v26.07.1` artifactExists `True`
- `03_timeline_protection_rich_events:arkts:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.0` artifactExists `True`
- `03_timeline_protection_rich_events:arkts:agent_result` role `agent_result` expected `pass` groundtruth `False` tag `v26.08.0` artifactExists `True`
- `04_live_location:android:base` role `base` expected `fail` groundtruth `True` tag `v26.04.0` artifactExists `False`
- `04_live_location:android:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.05.1` artifactExists `False`
- `04_live_location:arkts:base` role `base` expected `fail` groundtruth `True` tag `v26.04.0` artifactExists `True`
- `04_live_location:arkts:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.05.1` artifactExists `True`
- `04_live_location:arkts:agent_result` role `agent_result` expected `pass` groundtruth `False` tag `v26.05.1` artifactExists `True`
- `05_link_new_device:android:base` role `base` expected `fail` groundtruth `True` tag `v26.05.0` artifactExists `False`
- `05_link_new_device:android:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.2` artifactExists `False`
- `05_link_new_device:arkts:base` role `base` expected `fail` groundtruth `True` tag `v26.05.0` artifactExists `True`
- `05_link_new_device:arkts:groundtruth_final` role `groundtruth_final` expected `pass` groundtruth `True` tag `v26.08.2` artifactExists `True`
- `05_link_new_device:arkts:agent_result` role `agent_result` expected `pass` groundtruth `False` tag `v26.08.2` artifactExists `True`

## Execution Meaning

A testcase validates the benchmark only when the task's golden base rows fail and golden final rows pass.
Agent result rows are scored against the same final-oriented semantic assertions and reported separately for discriminativity.
A blocked row is not a pass or fail; it means the required state adapter, device, or build artifact is missing.
