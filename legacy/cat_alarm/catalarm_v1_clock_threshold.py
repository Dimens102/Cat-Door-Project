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
THRESHOLD_LUX = 5.0
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

alarm_start = None
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
        now_time = now_dt.time()

        daytime = datetime.time(6, 30) <= now_time <= datetime.time(21, 30)

        light_alarm = daytime and (lux is None or lux <= THRESHOLD_LUX)

        if light_alarm:
            if alarm_start is None:
                alarm_start = time.time()
            delayed_alarm = (time.time() - alarm_start) >= DELAY_SECONDS
        else:
            alarm_start = None
            delayed_alarm = False

        alarm = button_pressed or delayed_alarm

        GPIO.output(BUZZER_PIN, 1 if alarm else 0)

        line = (
            f"{now_dt.strftime('%Y-%m-%d %H:%M:%S')} "
            f"lux={lux} daytime={daytime} button={button_pressed} alarm={alarm}"
        )

        print(line)

        if time.time() - last_log_time >= LOG_EVERY_SECONDS:
            logger.info(line)
            last_log_time = time.time()

        time.sleep(0.5)

except KeyboardInterrupt:
    GPIO.output(BUZZER_PIN, 0)
    GPIO.cleanup()
