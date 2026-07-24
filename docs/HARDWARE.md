# Hardware and GPIO

## Raspberry Pi

Current platform: **Raspberry Pi 2 B**.

## Cat alarm wiring

| Function | Connection |
|---|---|
| ADS1115 SDA | Raspberry Pi SDA / GPIO2 |
| ADS1115 SCL | Raspberry Pi SCL / GPIO3 |
| ADS1115 power | According to the existing build; verify before rewiring |
| ADS1115 ground | Common Raspberry Pi ground |
| Analog sensor output | ADS1115 channel A0 |
| Push button | GPIO17, active low, internal pull-up |
| Buzzer | GPIO18 |

The uploaded source confirms GPIO17 and GPIO18, but the exact physical pin numbers, analog sensor model and its supply voltage are not recoverable from the uploaded files alone. These must be documented from the physical build before rewiring.

## Optional light sensor

The earliest design used a TSL2561 I²C light sensor. It was configured with:

- gain 16;
- integration time 402 ms;
- I²C bus shared through `board.SCL` and `board.SDA`.

This approach was superseded by the analog sensor because ambient illumination was not a sufficiently direct measure of passage occupancy.

## Optional camera hardware

The latest USB-camera code was written for:

- Logitech C930e on `/dev/video0`;
- webcam microphone at ALSA `plughw:1,0`;
- Raspberry Pi headphone output at ALSA `plughw:0,0`;
- PIR output on GPIO17;
- PIR VCC at 5 V and common ground.

## GPIO conflict

The alarm button and camera PIR both use GPIO17. They cannot be connected and operated as written at the same time.

Future integration should assign separate pins, for example:

- retain GPIO17 for the alarm button;
- move PIR to another free GPIO;
- centralize the pin assignments in one configuration module.

## Future cat-door hardware candidates

The future door is expected to require additional hardware, likely including:

- two passage sensors for direction detection;
- door-position switches;
- motor driver;
- geared motor or actuator;
- obstruction detection;
- manual override button;
- emergency release;
- stable regulated power supply;
- optional RFID or vision-based identity detection.

These are roadmap items, not current confirmed hardware.
