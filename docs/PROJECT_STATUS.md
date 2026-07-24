# Project Status

## Objective

Develop a dependable cat-door platform that can detect passage activity, record evidence, identify direction and eventually control a safe motorized door or lock.

## Current deployed prototype: cat alarm

The current alarm application is `src/cat_alarm/catalarm.py` on Raspberry Pi 2 B.

Implemented behavior:

- ADS1115 A0 voltage sampling;
- low/high threshold occupancy logic;
- five-sample false-reset filtering;
- 30-second delay before automatic buzzer escalation;
- separate manual-button buzzer pattern;
- event and status logging;
- Raspberry Pi throttling-status capture;
- configured sensor-fault bounds;
- maximum continuous-buzzer cutoff;
- GPIO cleanup on shutdown.

Current constants include a low threshold of 1.35 V, high threshold of 1.90 V and fault bounds of 0.50–3.30 V. These are prototype calibration values, not universal sensor specifications.

## Active technical issue

Historical logs showed the nominal reading drifting near the high threshold, frequent short occupancy transitions and occasional peaks above the configured 3.30 V fault limit. A later continuous occupied interval correctly caused the programmed alarm sequence.

The software therefore reacted to its input; the unresolved question is why the analog path reported those values. Primary investigation targets are sensor power, ground, signal wiring, connector quality and the ADS1115 input.

## Preserved camera prototype

`src/security_camera/pi2b_security_cam_audio.py` contains the latest preserved USB-camera application. Implemented capabilities include:

- single long-running OpenCV camera owner;
- 1280×720, 20 fps configured capture;
- MJPEG browser stream;
- PIR-stabilized recording trigger;
- 30-second clips and 15-second cooldown;
- snapshot serving;
- clip deletion and archive management;
- webcam microphone recording;
- audio upload/playback/delete functions;
- Flask status and management routes.

The program remains a separate prototype. It uses GPIO17 for PIR, which conflicts with the alarm button.

## Repository state

- Current applications are under `src/`.
- Direct component tests are under `hardware_tests/`.
- Earlier designs are preserved under `legacy/`.
- Runtime data is intentionally excluded from Git.
- Service templates and installation documentation are present.

## Immediate work order

1. Run the ADS1115 direct test and record clear/blocked values.
2. Reseat and inspect the analog wiring.
3. Confirm stable operation before adjusting thresholds.
4. Resolve GPIO17 allocation before integrating camera and alarm.
5. Move deployment-specific constants into configuration.
