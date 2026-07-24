from flask import Flask, send_from_directory, redirect, request, Response, jsonify
from gpiozero import DigitalInputDevice
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock
from werkzeug.utils import secure_filename
import subprocess
import time
import json
import shutil
import zipfile

# =========================
# Basic configuration
# =========================

PIR_GPIO = 17

BASE_DIR = Path("/home/beheerder")
CLIP_DIR = BASE_DIR / "clips"
ARCHIVE_DIR = BASE_DIR / "archive"
SNAPSHOT_FILE = BASE_DIR / "latest.jpg"
SETTINGS_FILE = BASE_DIR / "camera_settings.json"

MAX_CLIPS = 20

RECORD_SECONDS = 30
SNAPSHOT_INTERVAL = 60
STATUS_REFRESH_SECONDS = 5
SNAPSHOT_WEB_REFRESH_SECONDS = 30
COOLDOWN_SECONDS = 15

PIR_STABLE_HIGH_SECONDS = 0.5
PIR_STABLE_LOW_SECONDS = 1.0
STARTUP_SETTLE_SECONDS = 20
WEB_IGNORE_SECONDS = 2

WIDTH = 1280
HEIGHT = 720
FRAMERATE = 30
STREAM_FRAMERATE = 20

# =========================
# Camera settings
# =========================

DEFAULT_CAMERA_SETTINGS = {
    "brightness": 0.0,
    "contrast": 0.8,
    "saturation": 1.3,
    "sharpness": 2.3,
    "ev": 0.0,
    "gain": 0.0,
    "shutter": 0,
    "awb": "auto",
    "exposure": "normal",
    "metering": "centre",
    "denoise": "auto",
    "hflip": False,
    "vflip": False,
}

camera_settings = DEFAULT_CAMERA_SETTINGS.copy()

profiles = {
    "day": DEFAULT_CAMERA_SETTINGS.copy(),
    "evening": DEFAULT_CAMERA_SETTINGS.copy(),
    "night": DEFAULT_CAMERA_SETTINGS.copy(),
}

# =========================
# Flask / GPIO / locks
# =========================

app = Flask(__name__)
pir = DigitalInputDevice(PIR_GPIO, pull_up=False)

camera_lock = Lock()
recording_lock = Lock()

is_recording = False
settings_mode = False
last_motion = "None yet"
last_snapshot = "None yet"
last_web_request_time = 0
service_started = datetime.now()

CLIP_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)


# =========================
# Settings persistence
# =========================

def load_settings():
    global camera_settings, profiles

    if not SETTINGS_FILE.exists():
        return

    try:
        data = json.loads(SETTINGS_FILE.read_text())

        if "camera_settings" in data:
            loaded = data["camera_settings"]
            for key in DEFAULT_CAMERA_SETTINGS:
                if key in loaded:
                    camera_settings[key] = loaded[key]

        if "profiles" in data:
            loaded_profiles = data["profiles"]
            for name in profiles:
                if name in loaded_profiles:
                    for key in DEFAULT_CAMERA_SETTINGS:
                        if key in loaded_profiles[name]:
                            profiles[name][key] = loaded_profiles[name][key]

        print("Loaded camera settings from disk", flush=True)

    except Exception as e:
        print(f"Could not load settings file: {e}", flush=True)


def save_settings_to_disk():
    try:
        data = {
            "camera_settings": camera_settings,
            "profiles": profiles,
        }
        SETTINGS_FILE.write_text(json.dumps(data, indent=4))
        print("Saved camera settings to disk", flush=True)
    except Exception as e:
        print(f"Could not save settings file: {e}", flush=True)


# =========================
# Web request tracking
# =========================

@app.before_request
def mark_web_request():
    global last_web_request_time

    # Only count normal UI/media web requests.
    # Do not count API polling as a "web refresh event", otherwise it would suppress real PIR triggers.
    if not request.path.startswith("/api/"):
        last_web_request_time = time.time()


# =========================
# Camera command helpers
# =========================

def bool_arg(value):
    return bool(value)


def get_camera_args():
    args = [
        "--brightness", str(camera_settings["brightness"]),
        "--contrast", str(camera_settings["contrast"]),
        "--saturation", str(camera_settings["saturation"]),
        "--sharpness", str(camera_settings["sharpness"]),
        "--ev", str(camera_settings["ev"]),
        "--awb", str(camera_settings["awb"]),
        "--exposure", str(camera_settings["exposure"]),
        "--metering", str(camera_settings["metering"]),
        "--denoise", str(camera_settings["denoise"]),
    ]

    gain = float(camera_settings.get("gain", 0.0))
    if gain > 0:
        args += ["--gain", str(gain)]

    shutter = int(camera_settings.get("shutter", 0))
    if shutter > 0:
        args += ["--shutter", str(shutter)]

    if bool_arg(camera_settings.get("hflip", False)):
        args.append("--hflip")

    if bool_arg(camera_settings.get("vflip", False)):
        args.append("--vflip")

    return args


# =========================
# File helpers
# =========================

def safe_mp4_name(filename):
    safe = secure_filename(filename)
    if not safe.endswith(".mp4"):
        return None
    return safe


def list_clip_files():
    return sorted(CLIP_DIR.glob("motion_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)


def list_archive_files():
    return sorted(ARCHIVE_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)


def cleanup_old_clips():
    clips = sorted(CLIP_DIR.glob("motion_*.mp4"), key=lambda p: p.stat().st_mtime)
    while len(clips) > MAX_CLIPS:
        old = clips.pop(0)
        old.unlink()
        print(f"Deleted old clip: {old.name}", flush=True)


def make_archive_zip():
    zip_path = BASE_DIR / "archive_download.zip"

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for file in list_archive_files():
            z.write(file, arcname=file.name)

    return zip_path


# =========================
# Snapshots
# =========================

def take_snapshot():
    global last_snapshot

    if is_recording or settings_mode:
        return

    with camera_lock:
        if is_recording or settings_mode:
            return

        tmp_file = BASE_DIR / "latest_tmp.jpg"

        try:
            subprocess.run([
                "rpicam-still",
                "-n",
                "--immediate",
                "--width", str(WIDTH),
                "--height", str(HEIGHT),
                *get_camera_args(),
                "-o", str(tmp_file)
            ], check=True)

            tmp_file.replace(SNAPSHOT_FILE)
            last_snapshot = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Snapshot updated: {last_snapshot}", flush=True)

        except Exception as e:
            print(f"Snapshot error: {e}", flush=True)


def snapshot_loop():
    print("Snapshot loop running", flush=True)
    time.sleep(5)

    while True:
        take_snapshot()
        time.sleep(SNAPSHOT_INTERVAL)


# =========================
# PIR handling
# =========================

def pir_is_stably_high():
    start = time.time()
    while time.time() - start < PIR_STABLE_HIGH_SECONDS:
        if pir.value != 1:
            return False
        time.sleep(0.05)
    return True


def wait_for_stable_low():
    print("Waiting for PIR to return stable LOW...", flush=True)

    while True:
        if pir.value == 0:
            start = time.time()
            while time.time() - start < PIR_STABLE_LOW_SECONDS:
                if pir.value != 0:
                    break
                time.sleep(0.05)
            else:
                print("PIR stable LOW. Armed again.", flush=True)
                return

        time.sleep(0.1)


def pir_loop():
    print("PIR loop running", flush=True)
    print(f"Startup settle delay: {STARTUP_SETTLE_SECONDS} seconds", flush=True)
    time.sleep(STARTUP_SETTLE_SECONDS)

    print(f"PIR armed. Current GPIO17={int(pir.value)}", flush=True)

    if pir.value == 1:
        print("PIR HIGH at startup. Waiting for LOW.", flush=True)
        wait_for_stable_low()

    while True:
        if settings_mode:
            time.sleep(0.2)
            continue

        if pir.value == 1:
            if time.time() - last_web_request_time < WEB_IGNORE_SECONDS:
                print("Ignored PIR HIGH near web request", flush=True)
                time.sleep(0.5)
                continue

            print("PIR HIGH detected. Checking stability...", flush=True)

            if pir_is_stably_high():
                print("Stable PIR trigger confirmed.", flush=True)
                record_clip()
                wait_for_stable_low()
            else:
                print("Ignored unstable PIR spike.", flush=True)

        time.sleep(0.1)


# =========================
# Recording
# =========================

def record_clip():
    global is_recording, last_motion

    if recording_lock.locked():
        print("Recording ignored: already recording", flush=True)
        return

    if settings_mode:
        print("Recording ignored: camera settings mode active", flush=True)
        return

    with recording_lock:
        with camera_lock:
            is_recording = True
            last_motion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            raw_file = CLIP_DIR / f"motion_{timestamp}.h264"
            mp4_file = CLIP_DIR / f"motion_{timestamp}.mp4"

            print(f"Recording {mp4_file.name}", flush=True)

            try:
                subprocess.run([
                    "rpicam-vid",
                    "-n",
                    "-t", str(RECORD_SECONDS * 1000),
                    "--width", str(WIDTH),
                    "--height", str(HEIGHT),
                    "--framerate", str(FRAMERATE),
                    *get_camera_args(),
                    "-o", str(raw_file)
                ], check=True)

                subprocess.run([
                    "ffmpeg",
                    "-y",
                    "-framerate", str(FRAMERATE),
                    "-i", str(raw_file),
                    "-c", "copy",
                    str(mp4_file)
                ], check=True)

                raw_file.unlink()
                cleanup_old_clips()
                print("Recording finished", flush=True)

            except Exception as e:
                print(f"Recording error: {e}", flush=True)

            finally:
                print(f"Cooldown for {COOLDOWN_SECONDS} seconds", flush=True)
                time.sleep(COOLDOWN_SECONDS)
                is_recording = False


# =========================
# Live MJPEG settings stream
# =========================

def mjpeg_stream():
    with camera_lock:
        cmd = [
            "rpicam-vid",
            "-n",
            "-t", "0",
            "--codec", "mjpeg",
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--framerate", str(STREAM_FRAMERATE),
            *get_camera_args(),
            "-o", "-"
        ]

        print("Starting settings MJPEG stream", flush=True)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        try:
            buffer = b""

            while settings_mode:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break

                buffer += chunk

                start = buffer.find(b"\xff\xd8")
                end = buffer.find(b"\xff\xd9")

                if start != -1 and end != -1 and end > start:
                    jpg = buffer[start:end + 2]
                    buffer = buffer[end + 2:]

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" +
                        jpg +
                        b"\r\n"
                    )

        finally:
            print("Stopping settings MJPEG stream", flush=True)
            process.terminate()
            process.wait()


# =========================
# API routes
# =========================

@app.route("/api/status")
def api_status():
    clips = list_clip_files()
    uptime = str(datetime.now() - service_started).split(".")[0]

    return jsonify({
        "status": "RECORDING" if is_recording else ("SETTINGS MODE" if settings_mode else "IDLE"),
        "is_recording": is_recording,
        "settings_mode": settings_mode,
        "pir_state": int(pir.value),
        "last_motion": last_motion,
        "last_snapshot": last_snapshot,
        "stored_clips": len(clips),
        "max_clips": MAX_CLIPS,
        "record_seconds": RECORD_SECONDS,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "pir_stable_high_seconds": PIR_STABLE_HIGH_SECONDS,
        "web_ignore_seconds": WEB_IGNORE_SECONDS,
        "uptime": uptime,
        "camera_settings": camera_settings,
    })


@app.route("/api/clips")
def api_clips():
    clips = []
    for clip in list_clip_files():
        clips.append({
            "name": clip.name,
            "url": f"/clips/{clip.name}",
            "mtime": datetime.fromtimestamp(clip.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size_mb": round(clip.stat().st_size / 1024 / 1024, 1),
        })
    return jsonify(clips)


# =========================
# Action routes
# =========================

@app.route("/record-now")
def record_now():
    Thread(target=record_clip, daemon=True).start()
    return redirect("/")


@app.route("/delete-all-videos")
def delete_all_videos():
    for file in list_clip_files():
        file.unlink()
    return redirect("/")


@app.route("/delete-clip/<filename>")
def delete_clip(filename):
    safe = safe_mp4_name(filename)
    if safe:
        file = CLIP_DIR / safe
        if file.exists():
            file.unlink()
    return redirect("/")


@app.route("/archive-clip/<filename>")
def archive_clip(filename):
    safe = safe_mp4_name(filename)
    if safe:
        src = CLIP_DIR / safe
        dst = ARCHIVE_DIR / safe
        if src.exists():
            shutil.move(str(src), str(dst))
    return redirect("/")


@app.route("/delete-archive/<filename>")
def delete_archive(filename):
    safe = safe_mp4_name(filename)
    if safe:
        file = ARCHIVE_DIR / safe
        if file.exists():
            file.unlink()
    return redirect("/archive")


@app.route("/delete-all-archive")
def delete_all_archive():
    for file in list_archive_files():
        file.unlink()
    return redirect("/archive")


@app.route("/download-archive")
def download_archive():
    zip_path = make_archive_zip()
    return send_from_directory(str(BASE_DIR), zip_path.name, as_attachment=True)


# =========================
# Settings routes
# =========================

@app.route("/stream.mjpg")
def stream_mjpg():
    return Response(
        mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/update-settings")
def update_settings():
    for key in camera_settings:
        if key in ["hflip", "vflip"]:
            camera_settings[key] = request.args.get(key, "false") == "true"
        elif key == "shutter":
            try:
                camera_settings[key] = int(request.args.get(key, camera_settings[key]))
            except ValueError:
                pass
        else:
            try:
                value = request.args.get(key, camera_settings[key])
                if key in ["awb", "exposure", "metering", "denoise"]:
                    camera_settings[key] = str(value)
                else:
                    camera_settings[key] = float(value)
            except ValueError:
                pass

    return "OK"


@app.route("/save-settings")
def save_settings():
    global settings_mode
    save_settings_to_disk()
    settings_mode = False
    return redirect("/")


@app.route("/exit-settings")
def exit_settings():
    global settings_mode
    settings_mode = False
    return redirect("/")


@app.route("/save-profile/<profile>")
def save_profile(profile):
    if profile in profiles:
        profiles[profile] = camera_settings.copy()
        save_settings_to_disk()
    return redirect("/settings")


@app.route("/load-profile/<profile>")
def load_profile(profile):
    if profile in profiles:
        for key in DEFAULT_CAMERA_SETTINGS:
            camera_settings[key] = profiles[profile].get(key, DEFAULT_CAMERA_SETTINGS[key])
    return redirect("/settings")


# =========================
# Pages
# =========================

def option_html(value, current):
    selected = "selected" if value == current else ""
    return f'<option value="{value}" {selected}>{value}</option>'


@app.route("/settings")
def settings():
    global settings_mode
    settings_mode = True

    return f"""
<!doctype html>
<html>
<head>
    <title>Camera Settings V3.2</title>
    <style>
        body {{
            font-family: Arial;
            background: #111;
            color: #eee;
            margin: 20px;
        }}
        a {{ color: #8ab4f8; }}
        button {{
            padding: 8px;
            font-size: 14px;
            margin: 3px;
            cursor: pointer;
        }}
        .layout {{
            display: grid;
            grid-template-columns: 430px 1fr;
            gap: 20px;
            align-items: start;
        }}
        .controls {{
            background: #1b1b1b;
            padding: 15px;
            border: 1px solid #333;
        }}
        .preview {{
            background: #1b1b1b;
            padding: 15px;
            border: 1px solid #333;
            position: sticky;
            top: 20px;
        }}
        .row {{
            margin-bottom: 13px;
        }}
        .row label {{
            display: block;
            font-weight: bold;
            margin-bottom: 4px;
        }}
        input[type="range"] {{
            width: 310px;
        }}
        select {{
            width: 180px;
        }}
        img {{
            border: 2px solid #444;
            max-width: 100%;
        }}
        .small {{
            color: #aaa;
            font-size: 13px;
        }}
        .value {{
            display: inline-block;
            min-width: 65px;
            color: #8ab4f8;
        }}
    </style>
</head>
<body>
    <h1>Camera Settings V3.2</h1>
    <p><b>Motion detection is paused while this page is open.</b></p>

    <div class="layout">
        <div class="controls">
            <h2>Profiles</h2>
            <p>
                <a href="/load-profile/day"><button>Load Day</button></a>
                <a href="/load-profile/evening"><button>Load Evening</button></a>
                <a href="/load-profile/night"><button>Load Night</button></a>
            </p>
            <p>
                <a href="/save-profile/day"><button>Save as Day</button></a>
                <a href="/save-profile/evening"><button>Save as Evening</button></a>
                <a href="/save-profile/night"><button>Save as Night</button></a>
            </p>

            <h2>Image Controls</h2>

            <div class="row">
                <label>Brightness <span class="value" id="brightnessValue">{camera_settings["brightness"]}</span></label>
                <input id="brightness" type="range" min="-1.0" max="1.0" step="0.1" value="{camera_settings["brightness"]}">
            </div>

            <div class="row">
                <label>Contrast <span class="value" id="contrastValue">{camera_settings["contrast"]}</span></label>
                <input id="contrast" type="range" min="0.0" max="2.0" step="0.1" value="{camera_settings["contrast"]}">
            </div>

            <div class="row">
                <label>Saturation <span class="value" id="saturationValue">{camera_settings["saturation"]}</span></label>
                <input id="saturation" type="range" min="0.0" max="2.0" step="0.1" value="{camera_settings["saturation"]}">
            </div>

            <div class="row">
                <label>Sharpness <span class="value" id="sharpnessValue">{camera_settings["sharpness"]}</span></label>
                <input id="sharpness" type="range" min="0.0" max="4.0" step="0.1" value="{camera_settings["sharpness"]}">
            </div>

            <div class="row">
                <label>EV Compensation <span class="value" id="evValue">{camera_settings["ev"]}</span></label>
                <input id="ev" type="range" min="-10.0" max="10.0" step="0.5" value="{camera_settings["ev"]}">
                <div class="small">Exposure compensation. Try -2 to +2 first.</div>
            </div>

            <div class="row">
                <label>Analogue Gain <span class="value" id="gainValue">{camera_settings["gain"]}</span></label>
                <input id="gain" type="range" min="0.0" max="16.0" step="0.5" value="{camera_settings["gain"]}">
                <div class="small">0 = auto. Higher is brighter but noisier.</div>
            </div>

            <div class="row">
                <label>Shutter Speed µs <span class="value" id="shutterValue">{camera_settings["shutter"]}</span></label>
                <input id="shutter" type="range" min="0" max="100000" step="1000" value="{camera_settings["shutter"]}">
                <div class="small">0 = auto. 10000 = 1/100s, 20000 = 1/50s.</div>
            </div>

            <h2>Modes</h2>

            <div class="row">
                <label>AWB Mode</label>
                <select id="awb">
                    {option_html("auto", camera_settings["awb"])}
                    {option_html("incandescent", camera_settings["awb"])}
                    {option_html("tungsten", camera_settings["awb"])}
                    {option_html("fluorescent", camera_settings["awb"])}
                    {option_html("indoor", camera_settings["awb"])}
                    {option_html("daylight", camera_settings["awb"])}
                    {option_html("cloudy", camera_settings["awb"])}
                    {option_html("custom", camera_settings["awb"])}
                </select>
            </div>

            <div class="row">
                <label>Exposure Mode</label>
                <select id="exposure">
                    {option_html("normal", camera_settings["exposure"])}
                    {option_html("short", camera_settings["exposure"])}
                    {option_html("long", camera_settings["exposure"])}
                    {option_html("custom", camera_settings["exposure"])}
                </select>
            </div>

            <div class="row">
                <label>Metering Mode</label>
                <select id="metering">
                    {option_html("centre", camera_settings["metering"])}
                    {option_html("spot", camera_settings["metering"])}
                    {option_html("average", camera_settings["metering"])}
                    {option_html("custom", camera_settings["metering"])}
                </select>
            </div>

            <div class="row">
                <label>Denoise Mode</label>
                <select id="denoise">
                    {option_html("auto", camera_settings["denoise"])}
                    {option_html("off", camera_settings["denoise"])}
                    {option_html("cdn_off", camera_settings["denoise"])}
                    {option_html("cdn_fast", camera_settings["denoise"])}
                    {option_html("cdn_hq", camera_settings["denoise"])}
                </select>
            </div>

            <h2>Orientation</h2>

            <div class="row">
                <label>
                    <input id="hflip" type="checkbox" {"checked" if camera_settings["hflip"] else ""}>
                    Horizontal flip
                </label>
            </div>

            <div class="row">
                <label>
                    <input id="vflip" type="checkbox" {"checked" if camera_settings["vflip"] else ""}>
                    Vertical flip
                </label>
            </div>

            <h2>Exit</h2>
            <p>
                <a href="/save-settings"><button>Save settings and resume detection</button></a>
                <a href="/exit-settings"><button>Exit without saving new profiles</button></a>
            </p>
        </div>

        <div class="preview">
            <h2>Live Camera Stream</h2>
            <p class="small">Changing values restarts the stream after you stop moving a slider.</p>
            <img id="preview" src="/stream.mjpg?ts={time.time()}" width="1280">
        </div>
    </div>

<script>
let restartTimer = null;

function getBool(id) {{
    return document.getElementById(id).checked ? "true" : "false";
}}

function updateSettings() {{
    const b = document.getElementById("brightness").value;
    const c = document.getElementById("contrast").value;
    const s = document.getElementById("saturation").value;
    const sh = document.getElementById("sharpness").value;
    const ev = document.getElementById("ev").value;
    const gain = document.getElementById("gain").value;
    const shutter = document.getElementById("shutter").value;

    const awb = document.getElementById("awb").value;
    const exposure = document.getElementById("exposure").value;
    const metering = document.getElementById("metering").value;
    const denoise = document.getElementById("denoise").value;

    const hflip = getBool("hflip");
    const vflip = getBool("vflip");

    document.getElementById("brightnessValue").innerText = b;
    document.getElementById("contrastValue").innerText = c;
    document.getElementById("saturationValue").innerText = s;
    document.getElementById("sharpnessValue").innerText = sh;
    document.getElementById("evValue").innerText = ev;
    document.getElementById("gainValue").innerText = gain;
    document.getElementById("shutterValue").innerText = shutter;

    const url = `/update-settings?brightness=${{b}}&contrast=${{c}}&saturation=${{s}}&sharpness=${{sh}}&ev=${{ev}}&gain=${{gain}}&shutter=${{shutter}}&awb=${{awb}}&exposure=${{exposure}}&metering=${{metering}}&denoise=${{denoise}}&hflip=${{hflip}}&vflip=${{vflip}}`;

    fetch(url).then(() => {{
        clearTimeout(restartTimer);
        restartTimer = setTimeout(function() {{
            const preview = document.getElementById("preview");
            preview.src = "";
            setTimeout(function() {{
                preview.src = "/stream.mjpg?ts=" + new Date().getTime();
            }}, 150);
        }}, 1200);
    }});
}}

[
    "brightness", "contrast", "saturation", "sharpness",
    "ev", "gain", "shutter",
    "awb", "exposure", "metering", "denoise",
    "hflip", "vflip"
].forEach(id => {{
    document.getElementById(id).addEventListener("input", updateSettings);
    document.getElementById(id).addEventListener("change", updateSettings);
}});
</script>
</body>
</html>
"""


@app.route("/archive")
def archive_page():
    files = list_archive_files()

    archive_html = ""
    for file in files:
        archive_html += f"""
        <div class="clip">
            <h3>{file.name}</h3>
            <p>{round(file.stat().st_size / 1024 / 1024, 1)} MB - {datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")}</p>
            <video width="640" controls preload="metadata">
                <source src="/archive-files/{file.name}" type="video/mp4">
            </video>
            <br>
            <a href="/archive-files/{file.name}" download><button>Download</button></a>
            <a href="/delete-archive/{file.name}" onclick="return confirm('Delete archived video {file.name}?');"><button>Delete</button></a>
        </div>
        """

    return f"""
<!doctype html>
<html>
<head>
    <title>Archive</title>
    <style>
        body {{ font-family: Arial; background: #111; color: #eee; margin: 20px; }}
        a {{ color: #8ab4f8; }}
        button {{ padding: 8px; margin: 3px; cursor: pointer; }}
        .card, .clip {{
            background: #1b1b1b;
            border: 1px solid #333;
            padding: 15px;
            margin-bottom: 15px;
        }}
        video {{ border: 2px solid #444; }}
    </style>
</head>
<body>
    <h1>Video Archive</h1>

    <div class="card">
        <a href="/"><button>Back to main page</button></a>
        <a href="/download-archive"><button>Download full archive ZIP</button></a>
        <a href="/delete-all-archive" onclick="return confirm('Delete all archived videos?');"><button>Delete full archive</button></a>
    </div>

    <div class="card">
        <b>Archived videos:</b> {len(files)}
    </div>

    {archive_html}
</body>
</html>
"""


@app.route("/")
def index():
    global settings_mode

    # Main page resumes detection.
    settings_mode = False

    clips = list_clip_files()

    clip_html = ""
    for clip in clips:
        clip_html += f"""
        <div class="clip" data-name="{clip.name}">
            <h3>{clip.name}</h3>
            <p>{round(clip.stat().st_size / 1024 / 1024, 1)} MB - {datetime.fromtimestamp(clip.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")}</p>
            <video width="640" controls preload="metadata">
                <source src="/clips/{clip.name}" type="video/mp4">
            </video>
            <br>
            <a href="/clips/{clip.name}" download><button>Download</button></a>
            <a href="/archive-clip/{clip.name}"><button>Store in archive</button></a>
            <a href="/delete-clip/{clip.name}" onclick="return confirm('Delete video {clip.name}?');"><button>Delete this video</button></a>
        </div>
        """

    status = "RECORDING" if is_recording else "IDLE"
    status_class = "status-recording" if is_recording else "status-idle"

    return f"""
<!doctype html>
<html>
<head>
    <title>PI2B Security Camera</title>
    <style>
        body {{
            font-family: Arial;
            background: #111;
            color: #eee;
            margin: 20px;
        }}
        a {{ color: #8ab4f8; }}
        button {{
            padding: 10px;
            font-size: 16px;
            cursor: pointer;
            margin-right: 5px;
            margin-bottom: 5px;
        }}
        img, video {{
            border: 2px solid #444;
            max-width: 100%;
        }}
        .dashboard {{
            display: grid;
            grid-template-columns: 1fr 300px;
            gap: 20px;
            align-items: start;
        }}
        .card {{
            background: #1b1b1b;
            border: 1px solid #333;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .card h2 {{
            margin-top: 0;
            border-bottom: 1px solid #333;
            padding-bottom: 8px;
        }}
        .status-idle {{
            color: #8fd18f;
            font-weight: bold;
        }}
        .status-recording {{
            color: #ff9999;
            font-weight: bold;
        }}
        .setting-row {{
            display: flex;
            justify-content: space-between;
            border-bottom: 1px solid #2a2a2a;
            padding: 4px 0;
        }}
        .setting-row span:first-child {{
            color: #bbb;
        }}
        .clip {{
            margin-bottom: 25px;
            padding: 10px;
            background: #1b1b1b;
            border: 1px solid #333;
        }}
        .small {{
            color: #aaa;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <h1>PI2B Security Camera</h1>

    <div class="dashboard">
        <div>
            <div class="card">
                <h2>Status</h2>
                <p>
                    <b>Current state:</b>
                    <span id="status" class="{status_class}">{status}</span>
                </p>
                <p><b>PIR state:</b> <span id="pir_state">{int(pir.value)}</span></p>
                <p><b>Service uptime:</b> <span id="uptime">-</span></p>
                <p><b>Last snapshot:</b> <span id="last_snapshot">{last_snapshot}</span></p>
                <p><b>Stored clips:</b> <span id="stored_clips">{len(clips)}</span> / {MAX_CLIPS}</p>
                <p><b>Status refresh:</b> {STATUS_REFRESH_SECONDS} seconds</p>
                <p><b>Snapshot web refresh:</b> {SNAPSHOT_WEB_REFRESH_SECONDS} seconds</p>
            </div>

            <div class="card">
                <h2>Motion</h2>
                <p><b>Last motion:</b> <span id="last_motion">{last_motion}</span></p>
                <p><b>Recording length:</b> {RECORD_SECONDS} seconds</p>
                <p><b>Cooldown:</b> {COOLDOWN_SECONDS} seconds</p>
                <p><b>PIR stable-high check:</b> {PIR_STABLE_HIGH_SECONDS} seconds</p>
                <p><b>Web-refresh PIR ignore window:</b> {WEB_IGNORE_SECONDS} seconds</p>
                <p class="small">Web-triggered PIR spikes are ignored to prevent refresh loops.</p>
            </div>

            <div class="card">
                <h2>Latest Snapshot</h2>
                <img id="snapshot" src="/latest.jpg?ts={time.time()}" width="1280">
            </div>

            <div class="card">
                <h2>History</h2>
                <p class="small">This list updates only when the page is manually refreshed. Videos will no longer stop because of page auto-refresh.</p>
                {clip_html}
            </div>
        </div>

        <div>
            <div class="card">
                <h2>Buttons</h2>
                <p><a href="/record-now"><button>Record 30 seconds now</button></a></p>
                <p><a href="/settings"><button>Camera settings</button></a></p>
                <p><a href="/archive"><button>Archive page</button></a></p>
                <p><a href="/delete-all-videos" onclick="return confirm('Delete all current videos?');"><button>Delete all videos</button></a></p>
            </div>

            <div class="card">
                <h2>Camera Settings</h2>

                <div class="setting-row"><span>Brightness</span><span id="cam_brightness">{camera_settings["brightness"]}</span></div>
                <div class="setting-row"><span>Contrast</span><span id="cam_contrast">{camera_settings["contrast"]}</span></div>
                <div class="setting-row"><span>Saturation</span><span id="cam_saturation">{camera_settings["saturation"]}</span></div>
                <div class="setting-row"><span>Sharpness</span><span id="cam_sharpness">{camera_settings["sharpness"]}</span></div>
                <div class="setting-row"><span>EV</span><span id="cam_ev">{camera_settings["ev"]}</span></div>
                <div class="setting-row"><span>Gain</span><span id="cam_gain">{camera_settings["gain"]}</span></div>
                <div class="setting-row"><span>Shutter</span><span id="cam_shutter">{camera_settings["shutter"]}</span></div>
                <div class="setting-row"><span>AWB</span><span id="cam_awb">{camera_settings["awb"]}</span></div>
                <div class="setting-row"><span>Exposure</span><span id="cam_exposure">{camera_settings["exposure"]}</span></div>
                <div class="setting-row"><span>Metering</span><span id="cam_metering">{camera_settings["metering"]}</span></div>
                <div class="setting-row"><span>Denoise</span><span id="cam_denoise">{camera_settings["denoise"]}</span></div>
                <div class="setting-row"><span>HFlip</span><span id="cam_hflip">{camera_settings["hflip"]}</span></div>
                <div class="setting-row"><span>VFlip</span><span id="cam_vflip">{camera_settings["vflip"]}</span></div>
            </div>
        </div>
    </div>

<script>
function updateStatus() {{
    fetch("/api/status")
        .then(response => response.json())
        .then(data => {{
            const status = document.getElementById("status");
            status.innerText = data.status;
            status.className = data.is_recording ? "status-recording" : "status-idle";

            document.getElementById("pir_state").innerText = data.pir_state;
            document.getElementById("uptime").innerText = data.uptime;
            document.getElementById("last_snapshot").innerText = data.last_snapshot;
            document.getElementById("last_motion").innerText = data.last_motion;
            document.getElementById("stored_clips").innerText = data.stored_clips;

            document.getElementById("cam_brightness").innerText = data.camera_settings.brightness;
            document.getElementById("cam_contrast").innerText = data.camera_settings.contrast;
            document.getElementById("cam_saturation").innerText = data.camera_settings.saturation;
            document.getElementById("cam_sharpness").innerText = data.camera_settings.sharpness;
            document.getElementById("cam_ev").innerText = data.camera_settings.ev;
            document.getElementById("cam_gain").innerText = data.camera_settings.gain;
            document.getElementById("cam_shutter").innerText = data.camera_settings.shutter;
            document.getElementById("cam_awb").innerText = data.camera_settings.awb;
            document.getElementById("cam_exposure").innerText = data.camera_settings.exposure;
            document.getElementById("cam_metering").innerText = data.camera_settings.metering;
            document.getElementById("cam_denoise").innerText = data.camera_settings.denoise;
            document.getElementById("cam_hflip").innerText = data.camera_settings.hflip;
            document.getElementById("cam_vflip").innerText = data.camera_settings.vflip;
        }});
}}

function updateSnapshot() {{
    document.getElementById("snapshot").src = "/latest.jpg?ts=" + new Date().getTime();
}}

setInterval(updateStatus, {STATUS_REFRESH_SECONDS * 1000});
setInterval(updateSnapshot, {SNAPSHOT_WEB_REFRESH_SECONDS * 1000});
updateStatus();
</script>

</body>
</html>
"""


@app.route("/latest.jpg")
def latest_snapshot():
    if SNAPSHOT_FILE.exists():
        return send_from_directory(str(BASE_DIR), "latest.jpg")
    return "No snapshot yet", 404


@app.route("/clips/<path:filename>")
def clips(filename):
    return send_from_directory(str(CLIP_DIR), filename)


@app.route("/archive-files/<path:filename>")
def archive_files(filename):
    return send_from_directory(str(ARCHIVE_DIR), filename)


# =========================
# Start
# =========================

load_settings()

Thread(target=snapshot_loop, daemon=True).start()
Thread(target=pir_loop, daemon=True).start()

app.run(host="0.0.0.0", port=8080, threaded=True)
