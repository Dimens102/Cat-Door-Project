# Architecture

## Present architecture

The repository contains two independent applications rather than one combined daemon.

```text
Analog passage sensor
        │
        ▼
     ADS1115 ──I²C── Raspberry Pi 2 B ──GPIO18── Buzzer
                         │
                         ├──GPIO17── Manual button
                         └──Files/journal── Event history

Logitech C930e ──USB── Raspberry Pi 2 B ──Flask/OpenCV── Browser
PIR sensor ──GPIO17───────────────┘
Webcam microphone ──USB───────────┘
```

The GPIO17 conflict prevents both prototypes from being deployed unchanged on one Pi.

## Cat alarm data flow

1. The ADS1115 samples the analog sensor on channel A0.
2. Threshold logic classifies the passage as clear or occupied.
3. A false-reset filter prevents one short reading from immediately ending occupancy.
4. Occupancy duration is tracked.
5. After the configured delay, the buzzer countdown begins.
6. Events, voltage information and Pi throttling status are logged.
7. Sensor readings outside configured fault limits produce fault events.

## Security camera data flow

1. One camera loop owns `/dev/video0` and continuously updates the latest frame.
2. The Flask server exposes an MJPEG stream and management pages.
3. The PIR loop validates stable motion before starting a recording.
4. Recording writes video clips and captures microphone audio using the configured ALSA device.
5. Clips, archived files, snapshots and audio messages are managed through web routes.

## Intended future architecture

The preferred direction is modular rather than extending one large script indefinitely:

```text
Sensors ──► Event engine ──► Policy/safety controller ──► Door actuator
   │              │                    │
   ├─ passage     ├─ event log         ├─ lock/open rules
   ├─ direction   ├─ camera trigger    ├─ obstruction handling
   ├─ identity    └─ notifications     └─ manual override
   └─ environment
```

Future modules should exchange explicit events such as `occupancy_start`, `occupancy_end`, `cat_entering`, `cat_leaving`, `identity_confirmed`, `door_opened` and `safety_fault`.

## Design principles

- Hardware state must be observable through logs and diagnostics.
- Safety decisions must default to a non-trapping state.
- Sensor faults must be distinguished from valid detection.
- Configuration values should eventually move out of source code.
- Runtime media and logs must not be committed to Git.
- Legacy files are reference material, not deployment targets.
