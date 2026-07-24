# Wiring

This document records the connections represented by the current source code. Verify the physical installation before relying on it.

## Current cat alarm

| Function | Raspberry Pi connection | Other endpoint | Notes |
|---|---:|---|---|
| ADS1115 power | 3.3 V | ADS1115 VDD | Use 3.3 V logic with the Pi |
| ADS1115 ground | GND | ADS1115 GND | All components require a common ground |
| I²C data | GPIO2 / SDA | ADS1115 SDA | Default Pi I²C bus |
| I²C clock | GPIO3 / SCL | ADS1115 SCL | Default Pi I²C bus |
| Analog signal | — | ADS1115 A0 | Source must remain within the ADC/input configuration limits |
| Manual button | GPIO17 | Button to ground | Code enables an internal pull-up; pressed state is LOW |
| Buzzer control | GPIO18 | Buzzer control/input | Confirm whether a transistor/driver is required for the actual buzzer |

## Security-camera prototype

| Function | Raspberry Pi connection | Other endpoint | Notes |
|---|---:|---|---|
| PIR output | GPIO17 | PIR signal | Conflicts with alarm button |
| Camera/video | USB | Logitech C930e | Source expects `/dev/video0` |
| Microphone | USB/ALSA | C930e microphone | Source default: `plughw:1,0` |
| Audio playback | 3.5 mm/ALSA | Pi audio output | Source default: `plughw:0,0` |

## GPIO conflict

Both current applications assign GPIO17:

- `src/cat_alarm/catalarm.py`: push button
- `src/security_camera/pi2b_security_cam_audio.py`: PIR input

A combined installation must move one signal to another suitable GPIO and update the corresponding source or future configuration file.

## Wiring checks for unstable analog readings

1. Power off the Pi before reseating wires.
2. Confirm a shared ground between sensor, ADS1115 and Pi.
3. Check the sensor signal cannot exceed the permitted input range.
4. Check for loose Dupont connectors or partially inserted breadboard wires.
5. Keep the analog signal wire away from buzzer and motor wiring.
6. Run `hardware_tests/ads_test.py` before restarting the complete alarm.
