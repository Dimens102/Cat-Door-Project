# File Inventory

## Current code

| Repository file | Origin |
|---|---|
| `src/cat_alarm/catalarm.py` | Current uploaded `catalarm.py` |
| `src/security_camera/pi2b_security_cam_audio.py` | Latest uploaded USB-camera v3 script |
| `config/camera/pi2b_camera_settings.json` | Uploaded camera settings |

## Hardware tests

| File | Purpose |
|---|---|
| `ads_test.py` | Continuously prints ADS1115 A0 voltage |
| `button_test.py` | Prints GPIO17 button state |
| `lux_test.py` | Prints TSL2561 lux values |
| `pir_raw_monitor.py` | Logs raw GPIO17 PIR transitions |
| `pir_test.py` | Basic gpiozero MotionSensor callback test |

## Legacy alarm code

Earlier scripts are retained for traceability. They should not be deployed as the current production service.

## Legacy camera code

Earlier CSI-camera and USB-camera versions are retained to preserve working features and performance experiments.

## Deliberately excluded

The following were visible on the Pi but are not included:

- `catalarm-events.log`;
- historic alarm logs;
- video clips;
- camera snapshots;
- WAV files;
- Python virtual environment;
- `__pycache__`;
- test media files;
- command-like accidental filename;
- unknown binary/pickle file `catalarm.p`.

They are runtime artifacts or potentially unsafe/unnecessary for source control.
