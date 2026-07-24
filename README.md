# Cat Door Project

A Raspberry Pi–based cat monitoring project that is intended to grow into a complete automated cat-door system.

The repository combines two prototypes that were built on the same Raspberry Pi 2 B:

1. **Cat passage alarm** — an analog sensor connected through an ADS1115 detects whether the passage is occupied. A buzzer escalates if the passage remains blocked.
2. **Security camera** — an optional Logitech C930e USB webcam, PIR sensor, microphone and Flask interface can record movement, provide a live image and support audio experiments.

## Current hardware

- Raspberry Pi 2 B
- ADS1115 analog-to-digital converter
- Analog passage/distance sensor on ADS1115 channel A0
- Push button on GPIO17
- Buzzer on GPIO18
- Optional TSL2561 light sensor from the earliest prototype
- Optional PIR sensor on GPIO17 when the camera subsystem is used
- Optional Logitech C930e USB webcam and microphone

> GPIO17 cannot simultaneously be the alarm push button and the camera PIR input. The two applications are preserved as separate subsystems until their GPIO allocation is redesigned.

## Repository structure

```text
src/cat_alarm/          Current cat alarm program
src/security_camera/    Latest preserved USB camera program
hardware_tests/         Small direct hardware tests
legacy/                 Earlier development versions
config/                  Example configuration files
systemd/                 Service templates
docs/                    Project documentation
runtime/                 Empty runtime-data placeholder
```

## Important current status

The alarm hardware is presently under investigation. Logged readings showed the idle voltage repeatedly sitting close to the configured high threshold and intermittently rising above 3.3 V. This produced repeated occupancy events and eventually an alarm even though the passage was not physically blocked.

Do not treat the current thresholds as final calibration values. See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Quick sensor test

Run the ADS1115 test with the same virtual environment used by the alarm:

```bash
~/catalarm-venv/bin/python hardware_tests/ads_test.py
```

Block and unblock the sensor while watching whether the voltage changes.

## Documentation

- [Project status](docs/PROJECT_STATUS.md)
- [Hardware and GPIO](docs/HARDWARE.md)
- [Alarm design](docs/CAT_ALARM.md)
- [Camera system](docs/SECURITY_CAMERA.md)
- [Installation](docs/INSTALLATION.md)
- [Logging](docs/LOGGING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Roadmap](docs/ROADMAP.md)
- [Development history](docs/DEVELOPMENT_HISTORY.md)
