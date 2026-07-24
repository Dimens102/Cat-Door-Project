# Troubleshooting

## Current incident: false continuous alarm

The retained log demonstrates that the alarm followed its configured logic:

1. Sensor readings repeatedly crossed the `1.90 V` high threshold.
2. Many short occupancy events were generated.
3. Several high spikes reached the sensor-fault range.
4. One event remained occupied for more than 30 seconds.
5. The alarm countdown started.

The immediate problem is therefore the input signal, not an unexplained buzzer activation.

## First test: use the correct Pi and Python

The cat alarm runs on **PI2B** and uses the virtual environment:

```bash
~/catalarm-venv/bin/python
```

Running the test with normal `python3` on PI3A produced:

```text
ModuleNotFoundError: No module named 'adafruit_ads1x15'
```

That error only indicates the wrong machine or Python environment; it does not prove the ADS1115 is broken.

## Direct ADS1115 test

Stop the service first so two processes do not read/control the same hardware while troubleshooting:

```bash
sudo systemctl stop catalarm.service
```

Then run:

```bash
cd /home/beheerder/Cat-Door-Project
~/catalarm-venv/bin/python hardware_tests/ads_test.py
```

Block and unblock the sensor.

Interpretation:

- **Clearly changing voltage:** ADS1115 and sensor path are responding.
- **Fixed plausible voltage:** sensor output may be stuck, blocked, mispowered or disconnected.
- **Near 0 V:** signal, power or ground may be missing.
- **Near full scale / repeated >3.3 V:** loose/floating signal, supply problem or incorrect wiring is likely.
- **I²C exception:** inspect ADS1115 power, SDA, SCL and address.

## Physical inspection order

Power the Pi off before moving wires.

1. Check common ground.
2. Check sensor supply wire.
3. Check sensor output to ADS1115 A0.
4. Check ADS1115 SDA and SCL.
5. Check whether any recently added sensor shifted a Dupont connector by one pin.
6. Inspect loose breadboard rows and splitters.
7. Reapply power and rerun only the direct ADS test.

## I²C bus check

```bash
i2cdetect -y 1
```

If the ADS1115 no longer appears, focus on its power and I²C wiring rather than the analog sensor.

## Do not change thresholds yet

A software threshold increase can hide a drifting but still functional baseline. It cannot safely solve intermittent 3.4–3.6 V readings. Restore stable hardware readings first.

## Buzzer remains active

Stop the service:

```bash
sudo systemctl stop catalarm.service
```

The application cleanup and GPIO input/pull-down handling should silence the buzzer. If the buzzer remains powered with the service stopped, inspect its wiring or driver circuit.
