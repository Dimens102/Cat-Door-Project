import board
import busio
import adafruit_tsl2561
import time

i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_tsl2561.TSL2561(i2c)

sensor.enabled = True
sensor.gain = 16
sensor.integration_time = 402

while True:
    print(f"Lux: {sensor.lux:.2f}")
    time.sleep(0.5)

