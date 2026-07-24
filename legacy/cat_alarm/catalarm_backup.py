import time
import datetime
import logging
from logging.handlers import TimedRotatingFileHandler

import board
import busio
import adafruit_tsl2561
import RPi.GPIO as GPIO

BUZZER_PIN = 18
BUTTON_PIN = 17

MIN_BASELINE_LUX = 20.0
DROP_THRESHOLD = 15.0
RECOVERY_LUX = 40.0
DELAY_SECONDS = 5

LOG_FILE = "/home/beheerder/catalarm.log"
LOG_EVERY_SECONDS = 10

i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_tsl2561.TSL2561(i2c)
sensor.enabled = True
sensor.gain = 16
sensor.integration_time = 402

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

baseline_lux = None
drop_start = None
last_log_time = 0

logger = logging.getLogger("catalarm")
logger.setLevel(logging.INFO)

handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=10
)

formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

try:
    while True:
        lux = sensor.lux
        button_pressed = GPIO.input(BUTTON_PIN) == 0

        now_dt = datetime.datetime.now()

        valid_lux = lux is not None
        too_dark = (not valid_lux) or lux < MIN_BASELINE_LUX

        drop_detected = (
            baseline_lux is not None
            and baseline_lux >= MIN_BASELINE_LUX
            and (
                (not valid_lux)
                or lux < MIN_BASELINE_LUX
                or (baseline_lux - lux) >= DROP_THRESHOLD
            )
        )

        if valid_lux and MIN_BASELINE_LUX <= lux <= 150 and not drop_detected:
            if baseline_lux is None:
                baseline_lux = lux
            elif lux > baseline_lux:
                baseline_lux = lux
            else:
                baseline_lux = (baseline_lux * 0.95) + (lux * 0.05)

        if drop_detected:
            if drop_start is None:
                drop_start = time.time()
            delayed_alarm = (time.time() - drop_start) >= DELAY_SECONDS

        else:
            drop_start = None
            delayed_alarm = False

        if delayed_alarm and valid_lux and lux >= RECOVERY_LUX:
            drop_start = None
            delayed_alarm = False
            baseline_lux = lux

        alarm = button_pressed or delayed_alarm

        GPIO.output(BUZZER_PIN, 1 if alarm else 0)

        lux_text = "None" if lux is None else f"{lux:.1f}"
        base_text = "None" if baseline_lux is None else f"{baseline_lux:.1f}"

        line = (
            f"{now_dt.strftime('%Y-%m-%d %H:%M:%S')} "
            f"baseline={base_text} "
            f"drop={drop_detected} "
            f"too_dark={too_dark} "
            f"button={button_pressed} "
            f"alarm={alarm} "
            f"lux={lux_text}"
        )

        print(line)

        if time.time() - last_log_time >= LOG_EVERY_SECONDS:
            logger.info(line)
            last_log_time = time.time()

        time.sleep(0.5)

except KeyboardInterrupt:
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
