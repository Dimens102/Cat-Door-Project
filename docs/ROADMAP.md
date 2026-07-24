# Roadmap

The roadmap is ordered by dependency and risk. Later milestones assume the earlier sensing and safety work is stable.

## Milestone 1 — Stabilize the existing alarm

- Verify ADS1115 wiring and power.
- Establish repeatable clear and occupied voltage ranges.
- Capture raw-value diagnostics during faults.
- Confirm false-reset and countdown behavior with controlled tests.
- Confirm the buzzer cannot remain energized indefinitely.
- Record a known-good hardware baseline.

**Exit criterion:** several days of operation without unexplained occupancy events or sensor-fault spikes.

## Milestone 2 — Consolidate configuration and services

- Move thresholds, GPIO assignments and paths into configuration.
- Resolve the GPIO17 button/PIR conflict.
- Standardize systemd services and working directories.
- Add startup validation for I²C, camera and writable runtime paths.
- Add a version field to structured events.

**Exit criterion:** both applications can be installed predictably without editing source constants.

## Milestone 3 — Improve passage detection

- Evaluate two-sensor direction detection.
- Distinguish entering, leaving, hesitation and partial obstruction.
- Add timing diagrams and recorded test cases.
- Compare analog, break-beam, ToF and other suitable sensors.

**Exit criterion:** direction and occupancy are classified reliably under normal cat movement.

## Milestone 4 — Integrate camera evidence

- Trigger snapshots or short clips from alarm events.
- Correlate media with event IDs and timestamps.
- Add retention limits and privacy controls.
- Separate camera acquisition from the web interface.

**Exit criterion:** each relevant passage event can be reviewed without continuous recording.

## Milestone 5 — Cat identification

Candidate approaches:

- RFID collar/tag reader;
- visual classification;
- combined RFID and camera confirmation.

Identification must degrade safely: an unknown or unreadable identity may be logged, but must not create a trapping hazard.

## Milestone 6 — Door mechanism prototype

- Select actuator and mechanical lock/opening method.
- Add open/closed limit detection.
- Add obstruction sensing.
- Add manual release.
- Define behavior for power loss, software crash and sensor disagreement.
- Bench-test away from the cat before installation.

**Exit criterion:** repeated mechanical cycles complete safely and recover from simulated faults.

## Milestone 7 — Unified controller and interface

- Central event/state service.
- Dashboard for current state, health and history.
- Manual controls with authentication.
- Alerts for hardware faults or prolonged obstruction.
- Backup/export of configuration and event history.
