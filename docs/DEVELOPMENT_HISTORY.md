# Development History

## Light-based first version

The first alarm used a TSL2561 light sensor and a time-of-day window. The basic idea was to trigger when the measured lux dropped below a threshold during daytime.

This produced useful experiments and logging, but ambient light varied too much to be a reliable direct passage detector.

## Transition to analog sensing

An ADS1115 ADC and analog sensor replaced the lux-only method. Early versions used narrow fixed voltage thresholds and a simple delay before continuous buzzer activation.

## Noise filtering

A false-reset counter was added so a few normal samples would not immediately end an occupancy event. This helped with noisy boundary readings.

## Improved buzzer pattern

The buzzer changed from a simple on/off alarm to an escalating warning pattern:

- slow beeps;
- progressively faster beeps;
- continuous alarm;
- later, a forced safety cutoff.

A separate shorter button countdown was retained for testing/manual activation.

## Residual buzzer fix

A faint buzz could remain after an alarm. The idle handling was changed so GPIO18 is driven low and then switched to input with pull-down.

## Event-oriented diagnostics

The script evolved from periodic status text to structured events:

- occupancy start;
- occupancy end;
- event duration;
- raw hit count;
- peak and low voltage;
- event classification;
- alarm-stage snapshots.

## Persistent system logs

Journald was configured with persistent storage so evidence remains after a reboot or emergency power removal.

## Power-status correlation

`vcgencmd get_throttled` was added to each event line to correlate sensor problems with undervoltage or thermal throttling.

## Current baseline/fault investigation

The July 2026 incident showed idle readings clustered around the exact high threshold and occasional fault-range peaks. The logs proved that the alarm logic was functioning, but the physical input was unstable or incorrectly calibrated.

## Camera development

A separate camera project progressed through:

1. Raspberry Pi camera command-based recording;
2. Logitech C930e USB webcam support;
3. OpenCV live streaming;
4. FFmpeg audio/video recording;
5. archive and web management;
6. a Pi 2 timing workaround that duplicates frames to retain real-time duration.

These components are now preserved as part of the future cat-door platform.
