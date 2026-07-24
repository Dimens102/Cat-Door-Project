# Security Camera Subsystem

## Purpose

The camera subsystem was created as a reusable Raspberry Pi security camera and is retained for eventual cat-door monitoring.

## Latest preserved implementation

The latest uploaded version is stored as:

```text
src/security_camera/pi2b_security_cam_audio.py
```

It targets a Logitech C930e USB webcam rather than a Raspberry Pi CSI camera.

## Main capabilities

- Flask web interface;
- OpenCV ownership of `/dev/video0`;
- live MJPEG stream;
- continuously refreshed `latest.jpg`;
- PIR-triggered recording;
- 30-second recordings;
- MP4 creation through FFmpeg;
- webcam microphone capture;
- local sound playback experiments;
- clip retention limit;
- archive folder and ZIP download;
- status API;
- recording and talk-mode locks.

## Pi 2 performance workaround

The camera loop may not deliver a full real-time frame rate while the Pi 2 is also streaming and serving Flask. Earlier recordings therefore became short, fast-forward videos.

The later code duplicates frames according to wall-clock time before feeding FFmpeg. This preserves the correct recording duration even if the number of unique captured frames falls below the nominal frame rate.

## Current defaults

| Setting | Value |
|---|---:|
| Video device | `/dev/video0` |
| Resolution | 1280 × 720 |
| Nominal frame rate | 20 fps |
| Recording duration | 30 seconds |
| Cooldown | 15 seconds |
| Maximum normal clips | 20 |
| PIR GPIO | GPIO17 |
| Webcam microphone | `plughw:1,0` |
| Pi audio output | `plughw:0,0` |

## Integration constraints

The camera software currently expects the PIR on GPIO17, while the alarm expects a push button on GPIO17. Before merger, the camera must either:

- receive passage events from the central alarm process; or
- move its PIR to a different GPIO.

A better long-term architecture is one central service that publishes sensor events and asks the camera module to record, rather than two independent applications both reading GPIO.

## Privacy and repository policy

Do not commit:

- recorded clips;
- audio messages;
- live snapshots;
- archive ZIP files;
- identifying images.
