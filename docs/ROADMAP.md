# Roadmap

## Phase 1 — Stabilize the existing alarm

- Repair or reseat the current sensor connection.
- Record stable idle and blocked voltage ranges.
- Confirm fault limits.
- Add a repeatable calibration procedure.
- Keep alarm logging and persistent journald.
- Add an explicit safe startup delay and sensor-health check.

## Phase 2 — Repository and deployment discipline

- Run the project from the Git clone instead of loose files in `/home/beheerder`.
- Keep runtime data outside the repository.
- Add a configuration file instead of editing thresholds in source.
- Add an installation script.
- Add a hardware self-test command.
- Record actual service files from the Pi and replace the current templates.

## Phase 3 — Camera reintegration

- Resolve the GPIO17 conflict.
- Trigger camera recording from alarm events.
- Store an image or clip reference with important events.
- Reduce CPU load on Pi 2 or migrate camera work to a newer Pi.
- Separate camera configuration from source code.

## Phase 4 — Passage direction

- Add a second sensor.
- Detect sensor A → sensor B versus B → A.
- Distinguish entering, leaving, hesitation and reversal.
- Reject impossible or noisy sequences.

## Phase 5 — Cat identity

Evaluate one or more:

- RFID collar tag;
- image recognition;
- weight measurement;
- combined sensor signature.

Identity must fail safely: an uncertain result must not trap the cat.

## Phase 6 — Motorized door

- Select actuator and motor driver.
- Add open and closed limit switches.
- Add obstruction/current detection.
- Add manual override.
- Add emergency mechanical release.
- Add watchdog and power-loss behavior.

## Phase 7 — User interface and automation

- Web dashboard.
- Sensor-health state.
- Door state and manual control.
- Event timeline.
- Camera clips linked to events.
- Configurable schedules and rules.
- Notifications only for meaningful failures or exceptions.
