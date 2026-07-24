# Cat Door Project1

A Raspberry Pi project for detecting activity at a cat passage and developing that prototype into a reliable, automated cat-door system.

The repository combines two working prototypes:

1. **Cat alarm** — reads an analog passage sensor through an ADS1115, tracks occupancy, logs events, and activates an escalating buzzer if the passage remains occupied.
2. **Security camera** — uses a Logitech C930e USB webcam, PIR input, microphone, OpenCV and Flask for live viewing, motion-triggered recording, snapshots, clip management and audio experiments.

The current objective is consolidation: preserve what already works, document the hardware and software accurately, and create a stable base for direction sensing, cat identification and eventual door control.

## Current status

| Subsystem | Status | Main limitation |
|---|---|---|
| Cat alarm | Deployed prototype | Analog input has shown unstable readings and requires hardware verification |
| Security camera | Preserved working prototype | Shares GPIO17 with the alarm button and is not yet integrated |
| Automated door | Planned | Actuator, lock design, safety sensing and identification are not yet implemented |

See [Project status](docs/PROJECT_STATUS.md) and [Roadmap](docs/ROADMAP.md).

## Hardware presently represented

- Raspberry Pi 2 B
- ADS1115 analog-to-digital converter
- Analog passage sensor connected to ADS1115 A0
- Active buzzer on GPIO18
- Push button on GPIO17
- Optional PIR sensor on GPIO17 for the camera prototype
- Logitech C930e USB webcam and microphone
- Earlier TSL2561 light-sensor prototype retained under `legacy/`

> **GPIO conflict:** the alarm uses GPIO17 for its button; the camera prototype uses GPIO17 for PIR input. Do not run both with the present wiring. See [Hardware](docs/HARDWARE.md) and [Wiring](docs/WIRING.md).

## Repository layout

```text
Cat-Door-Project/
├── src/
│   ├── cat_alarm/          Current alarm application
│   └── security_camera/    Current preserved camera application
├── hardware_tests/         Small direct hardware tests
├── config/                 Example configuration
├── systemd/                Service templates
├── docs/                   Design, operation and troubleshooting documents
├── legacy/                 Earlier development versions
├── runtime/                Runtime-data policy; generated data is not committed
├── requirements-*.txt      Python dependencies by subsystem
├── CHANGELOG.md
└── README.md
```

## Quick checks

### ADS1115 sensor

Run with the same virtual environment used by the alarm:

```bash
cd /home/beheerder/Cat-Door-Project
~/catalarm-venv/bin/python hardware_tests/ads_test.py
```

Observe the voltage with the passage clear and blocked. Stable, repeatable values must be established before thresholds are adjusted.

### Repository validation

```bash
cd /home/beheerder/Cat-Door-Project
python3 -m compileall -q src hardware_tests
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Hardware](docs/HARDWARE.md)
- [Wiring](docs/WIRING.md)
- [Cat alarm](docs/CAT_ALARM.md)
- [Security camera](docs/SECURITY_CAMERA.md)
- [Installation](docs/INSTALLATION.md)
- [Operations](docs/OPERATIONS.md)
- [Logging](docs/LOGGING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Development history](docs/DEVELOPMENT_HISTORY.md)
- [Roadmap](docs/ROADMAP.md)
- [Contributing](CONTRIBUTING.md)

## Safety boundary

The current code is a monitoring and alarm prototype. It must not directly control a powered door until obstruction detection, manual release, actuator limits, fail-safe behavior and recovery after power loss have been designed and tested.

# Cat Door Project2

## DS18B20 Temperature Service

The Cat Door PI (PI2B) exposes a lightweight temperature service
intended for other systems such as the Radio Tower PI.

### Purpose

-   Read the DS18B20 every 30 seconds.
-   Store every reading in a monthly CSV archive.
-   Expose the latest reading through a JSON endpoint.
-   Start automatically during boot.
-   Keep six months of history.

The Radio Tower polls this endpoint every 30 seconds and is responsible
for formatting, graphs, alerts and presentation.

## Hardware

-   Sensor: DS18B20
-   GPIO: BCM GPIO24 (Physical pin 18)
-   Interface: 1-Wire

Enable:

``` text
dtoverlay=w1-gpio,gpiopin=24
```

## Service

Service name:

``` text
catdoor-temperature.service
```

Useful commands:

``` bash
sudo systemctl status catdoor-temperature.service
sudo systemctl restart catdoor-temperature.service
sudo journalctl -u catdoor-temperature.service -f
```

## JSON API

Endpoint:

``` text
http://PI2B:8765/temperature
```

Example:

``` json
{
  "sensor_id": "28-000008c84830",
  "temperature_millidegrees_c": 20625,
  "timestamp_utc": "2026-07-24T01:02:17.114731+00:00"
}
```

## CSV Archive

Location:

``` text
runtime/temperature/
```

One file is created per month:

``` text
YYYY-MM.csv
```

CSV format:

``` csv
timestamp_utc,sensor_id,temperature_millidegrees_c
2026-07-24T01:01:15Z,28-000008c84830,20562
```

Files older than six months are removed automatically.

## Repository Layout

``` text
src/
└── temperature_api/
    └── ds18b20_api.py

runtime/
└── temperature/

systemd/
└── catdoor-temperature.service
```
