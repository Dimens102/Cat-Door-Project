# Operations

## Pre-start checks

```bash
cd /home/beheerder/Cat-Door-Project
i2cdetect -y 1
```

The ADS1115 is commonly visible at address `0x48`, depending on its address-pin wiring.

Run the direct sensor test:

```bash
~/catalarm-venv/bin/python hardware_tests/ads_test.py
```

## Manual alarm start

```bash
cd /home/beheerder/Cat-Door-Project
~/catalarm-venv/bin/python src/cat_alarm/catalarm.py
```

Stop with `Ctrl+C`. The program performs GPIO cleanup during a normal shutdown.

## Service management

After installing the provided service template:

```bash
sudo systemctl status catalarm.service
sudo systemctl restart catalarm.service
sudo journalctl -u catalarm.service -f
```

## Event log

The current alarm writes to:

```text
/home/beheerder/catalarm-events.log
```

Useful commands:

```bash
tail -50 /home/beheerder/catalarm-events.log
tail -f /home/beheerder/catalarm-events.log
grep 'EVENT=sensor_fault' /home/beheerder/catalarm-events.log
```

## Camera start

The camera application owns the webcam device and should be started only when no other process is using `/dev/video0`:

```bash
cd /home/beheerder/Cat-Door-Project
python3 src/security_camera/pi2b_security_cam_audio.py
```

Its directories are currently hard-coded under `/home/beheerder`: `clips`, `archive`, `audio_messages` and `latest.jpg`.

## Before committing changes

```bash
cd /home/beheerder/Cat-Door-Project
python3 -m compileall -q src hardware_tests
git status
git diff --check
```
