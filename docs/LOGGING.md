# Logging

## Alarm event file

The alarm writes structured lines to:

```text
/home/beheerder/catalarm-events.log
```

Each line includes:

- timestamp;
- event or alarm state;
- measured values where relevant;
- Raspberry Pi throttling status.

## Journal

The same output is printed to stdout and therefore captured by systemd/journald.

Useful commands:

```bash
journalctl -u catalarm.service -n 100 --no-pager
journalctl -u catalarm.service -f
journalctl -b -1 -u catalarm.service --no-pager
```

The previous-boot command is particularly valuable after an emergency unplug or crash.

## Important alarm records

### Script startup

```text
SCRIPT=start low=... high=... delay=...
```

### Occupancy

```text
EVENT=occupancy_start volts=...
EVENT=occupancy_end duration=... classification=... raw_hits=... peak_volts=... low_volts=...
```

### Sensor fault

```text
SENSOR_FAULT volts=...
```

### Alarm transitions

```text
ALARM=countdown_started ...
ALARM=meltdown_started ...
ALARM=cutoff_reached ...
ALARM=snapshot stage=... buzzer=...
```

## Power diagnostics

Every logged line includes the result of:

```bash
vcgencmd get_throttled
```

`throttled=0x0` means no current or historical power/temperature throttle flags were reported at that moment.

## Repository policy

Logs are intentionally ignored by Git because they can be large and contain detailed household activity patterns.
