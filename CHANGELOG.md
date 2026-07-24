# Changelog

All notable repository-level changes are recorded here.

## 2026-07-24 — Repository consolidation

### Added

- Consolidated cat-alarm and security-camera prototypes into one project.
- Structured `src`, `hardware_tests`, `legacy`, `config`, `systemd`, `runtime` and `docs` directories.
- Architecture, wiring, operation, installation, logging, troubleshooting and roadmap documentation.
- Contribution and repository hygiene guidance.
- Separate Python requirement files for alarm and camera subsystems.

### Preserved

- Current cat alarm implementation.
- Latest preserved Logitech C930e camera application.
- Earlier development versions showing the transition from light/PIR experiments to analog sensing and richer event handling.

### Known issues

- Analog sensor readings require hardware verification before threshold tuning.
- GPIO17 is assigned to both the alarm button and camera PIR in separate prototypes.
