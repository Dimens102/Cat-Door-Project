#!/usr/bin/env python3

import csv
import glob
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8765
READ_INTERVAL_SECONDS = 30
RETENTION_MONTHS = 6

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_DIR = PROJECT_ROOT / "runtime" / "temperature"

latest_reading = None
latest_lock = threading.Lock()


def read_temperature():
    devices = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")

    if not devices:
        raise RuntimeError("No DS18B20 sensor found")

    sensor_file = Path(devices[0])
    sensor_id = sensor_file.parent.name

    lines = sensor_file.read_text(encoding="utf-8").splitlines()

    if len(lines) < 2 or not lines[0].strip().endswith("YES"):
        raise RuntimeError("DS18B20 CRC check failed")

    marker = "t="
    position = lines[1].find(marker)

    if position == -1:
        raise RuntimeError("Temperature value missing")

    value = int(lines[1][position + len(marker):].strip())

    return {
        "sensor_id": sensor_id,
        "temperature_millidegrees_c": value,
        "timestamp_utc": datetime.now(timezone.utc).isoformat()
    }


def append_to_csv(reading):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    csv_path = ARCHIVE_DIR / f"{now:%Y-%m}.csv"
    new_file = not csv_path.exists()

    with csv_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if new_file:
            writer.writerow([
                "timestamp_utc",
                "sensor_id",
                "temperature_millidegrees_c"
            ])

        writer.writerow([
            reading["timestamp_utc"],
            reading["sensor_id"],
            reading["temperature_millidegrees_c"]
        ])


def remove_old_archives():
    now = datetime.now()
    current_month_number = now.year * 12 + now.month

    for csv_path in ARCHIVE_DIR.glob("????-??.csv"):
        try:
            year, month = map(int, csv_path.stem.split("-"))
            file_month_number = year * 12 + month

            if current_month_number - file_month_number >= RETENTION_MONTHS:
                csv_path.unlink()
        except (ValueError, OSError):
            continue


def sensor_loop():
    global latest_reading

    while True:
        try:
            reading = read_temperature()
            append_to_csv(reading)

            with latest_lock:
                latest_reading = reading

            remove_old_archives()

        except Exception as error:
            with latest_lock:
                latest_reading = {
                    "error": str(error),
                    "timestamp_utc": datetime.now(timezone.utc).isoformat()
                }

        time.sleep(READ_INTERVAL_SECONDS)


class TemperatureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/temperature"):
            self.send_error(404)
            return

        with latest_lock:
            response = latest_reading

        if response is None:
            response = {"error": "No reading available yet"}
            status = 503
        elif "error" in response:
            status = 503
        else:
            status = 200

        body = json.dumps(response).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    sensor_thread = threading.Thread(target=sensor_loop, daemon=True)
    sensor_thread.start()

    server = HTTPServer(("0.0.0.0", PORT), TemperatureHandler)
    print(f"DS18B20 API listening on port {PORT}")
    server.serve_forever()
