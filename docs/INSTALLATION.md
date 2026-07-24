# Installation

This document records a reproducible target installation. The exact packages already installed on the Pi were not exported, so verify package names against the current Raspberry Pi OS version.

## 1. Clone repository

```bash
cd /home/beheerder
git clone https://github.com/Dimens102/Cat-Door-Project.git
cd Cat-Door-Project
```

## 2. Enable I²C

```bash
sudo raspi-config
```

Enable I²C under the interface options, then reboot if requested.

Confirm the ADS1115 appears:

```bash
i2cdetect -y 1
```

The common ADS1115 default address is `0x48`, but confirm the actual result rather than assuming it.

## 3. Create cat-alarm virtual environment

```bash
python3 -m venv /home/beheerder/catalarm-venv
/home/beheerder/catalarm-venv/bin/pip install --upgrade pip
/home/beheerder/catalarm-venv/bin/pip install -r requirements-cat-alarm.txt
```

## 4. Test the analog input

```bash
/home/beheerder/catalarm-venv/bin/python hardware_tests/ads_test.py
```

Do not enable the service until stable, responsive readings are confirmed.

## 5. Install alarm service

```bash
sudo cp systemd/catalarm.service /etc/systemd/system/catalarm.service
sudo systemctl daemon-reload
sudo systemctl enable --now catalarm.service
```

Inspect status:

```bash
systemctl status catalarm.service
journalctl -u catalarm.service -n 100 --no-pager
```

## 6. Enable persistent journal storage

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo cp config/99-persistent-storage.conf /etc/systemd/journald.conf.d/99-persistent-storage.conf
sudo systemctl restart systemd-journald
```

## 7. Optional camera dependencies

The camera code documents these system packages:

```bash
sudo apt install -y python3-flask python3-gpiozero python3-lgpio python3-opencv ffmpeg alsa-utils v4l-utils
```

Verify device names before starting:

```bash
v4l2-ctl --list-devices
arecord -l
aplay -l
```

## 8. Optional camera service

Only install this service after resolving the GPIO17 conflict:

```bash
sudo cp systemd/pi2b-security-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi2b-security-camera.service
```
