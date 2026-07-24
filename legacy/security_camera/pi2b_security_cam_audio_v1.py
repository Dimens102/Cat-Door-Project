from flask import Flask, send_from_directory, redirect, request, Response, jsonify
from gpiozero import DigitalInputDevice
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock
from werkzeug.utils import secure_filename
import subprocess
import time
import shutil
import zipfile
import cv2

# =========================
# PI2B Logitech C930e Security Camera + PIR + Audio
# =========================
# Designed for:
# - Raspberry Pi 2 B
# - Logitech C930e USB webcam on /dev/video0
# - Webcam microphone as ALSA card 1, device 0: plughw:1,0
# - Pi headphone/speaker output as ALSA card 0, device 0: plughw:0,0
# - PIR sensor OUT on GPIO17, VCC 5V, GND
#
# Required packages:
# sudo apt install -y python3-flask python3-gpiozero python3-lgpio python3-opencv ffmpeg alsa-utils v4l-utils

# =========================
# Basic configuration
# =========================

PIR_GPIO = 17
BASE_DIR = Path("/home/beheerder")
CLIP_DIR = BASE_DIR / "clips"
ARCHIVE_DIR = BASE_DIR / "archive"
AUDIO_DIR = BASE_DIR / "audio_messages"
SNAPSHOT_FILE = BASE_DIR / "latest.jpg"

MAX_CLIPS = 20
RECORD_SECONDS = 30
COOLDOWN_SECONDS = 15
STATUS_REFRESH_SECONDS = 5

PIR_STABLE_HIGH_SECONDS = 0.5
PIR_STABLE_LOW_SECONDS = 1.0
STARTUP_SETTLE_SECONDS = 20
WEB_IGNORE_SECONDS = 2

VIDEO_DEVICE = "/dev/video0"
AUDIO_CAPTURE_DEVICE = "plughw:1,0"   # Logitech C930e mic
AUDIO_PLAYBACK_DEVICE = "plughw:0,0"  # Pi headphone jack

WIDTH = 1280
HEIGHT = 720
FRAMERATE = 20
JPEG_QUALITY = 80

# =========================
# Flask / GPIO / state
# =========================

app = Flask(__name__)
pir = DigitalInputDevice(PIR_GPIO, pull_up=False)

CLIP_DIR.mkdir(exist_ok=True)
ARCHIVE_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

frame_lock = Lock()
recording_lock = Lock()
recorder_lock = Lock()

latest_jpeg = None
latest_frame = None
camera_ok = False
camera_error = "Camera not started yet"

active_recorder = None
is_recording = False
talk_mode = False
last_motion = "None yet"
last_snapshot = "None yet"
last_web_request_time = 0
service_started = datetime.now()

# =========================
# File helpers
# =========================

def safe_mp4_name(filename):
    safe = secure_filename(filename)
    if not safe.endswith(".mp4"):
        return None
    return safe


def safe_wav_name(filename):
    safe = secure_filename(filename)
    if not safe.endswith(".wav"):
        return None
    return safe


def list_clip_files():
    return sorted(CLIP_DIR.glob("motion_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)


def list_archive_files():
    return sorted(ARCHIVE_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)


def list_audio_files():
    return sorted(AUDIO_DIR.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)


def cleanup_old_clips():
    clips = sorted(CLIP_DIR.glob("motion_*.mp4"), key=lambda p: p.stat().st_mtime)
    while len(clips) > MAX_CLIPS:
        old = clips.pop(0)
        old.unlink(missing_ok=True)
        print(f"Deleted old clip: {old.name}", flush=True)


def make_archive_zip():
    zip_path = BASE_DIR / "archive_download.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for file in list_archive_files():
            z.write(file, arcname=file.name)
    return zip_path

# =========================
# Web request tracking
# =========================

@app.before_request
def mark_web_request():
    global last_web_request_time
    if not request.path.startswith("/api/"):
        last_web_request_time = time.time()

# =========================
# Camera loop: one owner of webcam
# =========================

def camera_loop():
    """Owns /dev/video0 once, creates live JPEG frames, feeds recorder when active."""
    global latest_jpeg, latest_frame, camera_ok, camera_error, last_snapshot

    while True:
        cap = None
        try:
            print(f"Opening webcam {VIDEO_DEVICE}", flush=True)
            cap = cv2.VideoCapture(VIDEO_DEVICE, cv2.CAP_V4L2)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, FRAMERATE)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

            if not cap.isOpened():
                raise RuntimeError(f"Could not open {VIDEO_DEVICE}")

            camera_ok = True
            camera_error = ""
            frame_interval = 1.0 / FRAMERATE
            last_write = 0

            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError("Webcam frame read failed")

                # Normalize frame to requested size if driver gives a different size.
                if frame.shape[1] != WIDTH or frame.shape[0] != HEIGHT:
                    frame = cv2.resize(frame, (WIDTH, HEIGHT))

                ok_jpg, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
                if ok_jpg:
                    jpg_bytes = jpg.tobytes()
                    with frame_lock:
                        latest_jpeg = jpg_bytes
                        latest_frame = frame.copy()
                    # Keep latest.jpg fresh without separate camera access.
                    SNAPSHOT_FILE.write_bytes(jpg_bytes)
                    last_snapshot = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Feed current frame to ffmpeg recording process, if active.
                with recorder_lock:
                    rec = active_recorder

                if rec is not None and rec.poll() is None:
                    try:
                        # FFmpeg expects raw BGR24 frames from OpenCV.
                        rec.stdin.write(frame.tobytes())
                    except Exception as e:
                        print(f"Recorder pipe write error: {e}", flush=True)

                elapsed = time.time() - last_write
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)
                last_write = time.time()

        except Exception as e:
            camera_ok = False
            camera_error = str(e)
            print(f"Camera loop error: {e}", flush=True)
            time.sleep(3)

        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

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
        if talk_mode:
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
# Recording with webcam video + webcam mic audio
# =========================

def record_clip():
    global active_recorder, is_recording, last_motion

    if recording_lock.locked():
        print("Recording ignored: already recording", flush=True)
        return
    if talk_mode:
        print("Recording ignored: talk mode active", flush=True)
        return
    if not camera_ok:
        print(f"Recording ignored: camera not OK: {camera_error}", flush=True)
        return

    with recording_lock:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        mp4_file = CLIP_DIR / f"motion_{timestamp}.mp4"
        last_motion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        is_recording = True

        print(f"Recording {mp4_file.name} with video + audio", flush=True)

        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{WIDTH}x{HEIGHT}",
            "-r", str(FRAMERATE),
            "-i", "-",
            "-thread_queue_size", "1024",
            "-f", "alsa",
            "-i", AUDIO_CAPTURE_DEVICE,
            "-t", str(RECORD_SECONDS),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "96k",
            "-shortest",
            str(mp4_file),
        ]

        proc = None
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            with recorder_lock:
                active_recorder = proc

            time.sleep(RECORD_SECONDS)

        except Exception as e:
            print(f"Recording start/error: {e}", flush=True)

        finally:
            with recorder_lock:
                active_recorder = None

            if proc is not None:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                try:
                    _, err = proc.communicate(timeout=10)
                    if proc.returncode not in (0, None):
                        print(f"ffmpeg returned {proc.returncode}: {err.decode(errors='ignore')[-1000:]}", flush=True)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    print("ffmpeg killed after timeout", flush=True)
                except ValueError:
                    # stdin already closed; wait is enough.
                    proc.wait(timeout=10)

            cleanup_old_clips()
            print("Recording finished", flush=True)
            print(f"Cooldown for {COOLDOWN_SECONDS} seconds", flush=True)
            time.sleep(COOLDOWN_SECONDS)
            is_recording = False

# =========================
# Audio tools
# =========================

def record_audio_message(seconds=5):
    seconds = max(1, min(int(seconds), 30))
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    wav_file = AUDIO_DIR / f"audio_{timestamp}.wav"
    print(f"Recording audio message: {wav_file.name}", flush=True)
    subprocess.run([
        "arecord", "-D", AUDIO_CAPTURE_DEVICE,
        "-f", "cd",
        "-d", str(seconds),
        str(wav_file)
    ], check=False)
    return wav_file


def play_audio_file(path):
    print(f"Playing audio: {path.name}", flush=True)
    subprocess.run([
        "aplay", "-D", AUDIO_PLAYBACK_DEVICE,
        str(path)
    ], check=False)

# =========================
# Live MJPEG stream
# =========================

def mjpeg_stream():
    while True:
        with frame_lock:
            frame = latest_jpeg

        if frame is None:
            time.sleep(0.1)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Cache-Control: no-cache\r\n\r\n" +
            frame +
            b"\r\n"
        )
        time.sleep(1.0 / FRAMERATE)

# =========================
# API routes
# =========================

@app.route("/api/status")
def api_status():
    clips = list_clip_files()
    uptime = str(datetime.now() - service_started).split(".")[0]
    if talk_mode:
        status = "TALK MODE"
    elif is_recording:
        status = "RECORDING"
    else:
        status = "IDLE"

    return jsonify({
        "status": status,
        "is_recording": is_recording,
        "talk_mode": talk_mode,
        "pir_state": int(pir.value),
        "last_motion": last_motion,
        "last_snapshot": last_snapshot,
        "stored_clips": len(clips),
        "max_clips": MAX_CLIPS,
        "record_seconds": RECORD_SECONDS,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "uptime": uptime,
        "camera_ok": camera_ok,
        "camera_error": camera_error,
        "video_device": VIDEO_DEVICE,
        "audio_capture_device": AUDIO_CAPTURE_DEVICE,
        "audio_playback_device": AUDIO_PLAYBACK_DEVICE,
    })

@app.route("/api/clips")
def api_clips():
    return jsonify([
        {
            "name": clip.name,
            "url": f"/clips/{clip.name}",
            "mtime": datetime.fromtimestamp(clip.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size_mb": round(clip.stat().st_size / 1024 / 1024, 1),
        }
        for clip in list_clip_files()
    ])

@app.route("/api/audio")
def api_audio():
    return jsonify([
        {
            "name": f.name,
            "url": f"/audio-files/{f.name}",
            "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "size_kb": round(f.stat().st_size / 1024, 1),
        }
        for f in list_audio_files()
    ])

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
        file.unlink(missing_ok=True)
    return redirect("/")

@app.route("/delete-clip/<filename>")
def delete_clip(filename):
    safe = safe_mp4_name(filename)
    if safe:
        file = CLIP_DIR / safe
        file.unlink(missing_ok=True)
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
        file.unlink(missing_ok=True)
    return redirect("/archive")

@app.route("/delete-all-archive")
def delete_all_archive():
    for file in list_archive_files():
        file.unlink(missing_ok=True)
    return redirect("/archive")

@app.route("/download-archive")
def download_archive():
    zip_path = make_archive_zip()
    return send_from_directory(str(BASE_DIR), zip_path.name, as_attachment=True)

@app.route("/record-audio")
def record_audio_route():
    seconds = request.args.get("seconds", "5")
    Thread(target=record_audio_message, args=(seconds,), daemon=True).start()
    return redirect("/talk")

@app.route("/play-audio/<filename>")
def play_audio_route(filename):
    safe = safe_wav_name(filename)
    if safe:
        path = AUDIO_DIR / safe
        if path.exists():
            Thread(target=play_audio_file, args=(path,), daemon=True).start()
    return redirect("/talk")

@app.route("/delete-audio/<filename>")
def delete_audio_route(filename):
    safe = safe_wav_name(filename)
    if safe:
        path = AUDIO_DIR / safe
        path.unlink(missing_ok=True)
    return redirect("/talk")

@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    file = request.files.get("audiofile")
    if file:
        safe = secure_filename(file.filename)
        if safe.endswith(".wav"):
            file.save(AUDIO_DIR / safe)
    return redirect("/talk")

@app.route("/exit-talk")
def exit_talk():
    global talk_mode
    talk_mode = False
    return redirect("/")

# =========================
# Media routes
# =========================

@app.route("/stream.mjpg")
def stream_mjpg():
    return Response(mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

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

@app.route("/audio-files/<path:filename>")
def audio_files(filename):
    return send_from_directory(str(AUDIO_DIR), filename)

# =========================
# Pages
# =========================

def page_style():
    return """
    <style>
        body { font-family: Arial; background: #111; color: #eee; margin: 20px; }
        a { color: #8ab4f8; }
        button { padding: 10px; font-size: 16px; cursor: pointer; margin-right: 5px; margin-bottom: 5px; }
        img, video { border: 2px solid #444; max-width: 100%; }
        .dashboard { display: grid; grid-template-columns: 1fr 320px; gap: 20px; align-items: start; }
        .card, .clip { background: #1b1b1b; border: 1px solid #333; padding: 15px; margin-bottom: 15px; }
        .card h2 { margin-top: 0; border-bottom: 1px solid #333; padding-bottom: 8px; }
        .status-idle { color: #8fd18f; font-weight: bold; }
        .status-recording { color: #ff9999; font-weight: bold; }
        .status-talk { color: #ffd27f; font-weight: bold; }
        .small { color: #aaa; font-size: 13px; }
        input[type=number] { width: 70px; }
    </style>
    """

@app.route("/")
def index():
    global talk_mode
    talk_mode = False

    clips = list_clip_files()
    clip_html = ""
    for clip in clips:
        clip_html += f"""
        <div class="clip">
            <h3>{clip.name}</h3>
            <p>{round(clip.stat().st_size / 1024 / 1024, 1)} MB - {datetime.fromtimestamp(clip.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}</p>
            <video width="640" controls preload="metadata"><source src="/clips/{clip.name}" type="video/mp4"></video><br>
            <a href="/clips/{clip.name}" download><button>Download</button></a>
            <a href="/archive-clip/{clip.name}"><button>Store in archive</button></a>
            <a href="/delete-clip/{clip.name}" onclick="return confirm('Delete video {clip.name}?');"><button>Delete this video</button></a>
        </div>
        """

    return f"""
<!doctype html>
<html>
<head><title>PI2B Security Camera + Audio</title>{page_style()}</head>
<body>
<h1>PI2B Security Camera + Audio</h1>
<div class="dashboard">
    <div>
        <div class="card">
            <h2>Live Video</h2>
            <p class="small">This is MJPEG video only. PIR recordings include microphone audio.</p>
            <img src="/stream.mjpg" width="1280">
        </div>
        <div class="card">
            <h2>History</h2>
            {clip_html if clip_html else '<p>No clips yet.</p>'}
        </div>
    </div>
    <div>
        <div class="card">
            <h2>Status</h2>
            <p><b>Current state:</b> <span id="status">-</span></p>
            <p><b>PIR state:</b> <span id="pir_state">-</span></p>
            <p><b>Camera:</b> <span id="camera_ok">-</span></p>
            <p><b>Uptime:</b> <span id="uptime">-</span></p>
            <p><b>Last motion:</b> <span id="last_motion">{last_motion}</span></p>
            <p><b>Stored clips:</b> <span id="stored_clips">{len(clips)}</span> / {MAX_CLIPS}</p>
        </div>
        <div class="card">
            <h2>Buttons</h2>
            <p><a href="/record-now"><button>Record {RECORD_SECONDS}s now</button></a></p>
            <p><a href="/talk"><button>Talk / Audio page</button></a></p>
            <p><a href="/archive"><button>Archive page</button></a></p>
            <p><a href="/delete-all-videos" onclick="return confirm('Delete all current videos?');"><button>Delete all videos</button></a></p>
        </div>
        <div class="card">
            <h2>Devices</h2>
            <p><b>Video:</b> {VIDEO_DEVICE}</p>
            <p><b>Mic:</b> {AUDIO_CAPTURE_DEVICE}</p>
            <p><b>Speaker:</b> {AUDIO_PLAYBACK_DEVICE}</p>
        </div>
    </div>
</div>
<script>
function updateStatus() {{
    fetch('/api/status').then(r => r.json()).then(data => {{
        const s = document.getElementById('status');
        s.innerText = data.status;
        s.className = data.is_recording ? 'status-recording' : (data.talk_mode ? 'status-talk' : 'status-idle');
        document.getElementById('pir_state').innerText = data.pir_state;
        document.getElementById('camera_ok').innerText = data.camera_ok ? 'OK' : data.camera_error;
        document.getElementById('uptime').innerText = data.uptime;
        document.getElementById('last_motion').innerText = data.last_motion;
        document.getElementById('stored_clips').innerText = data.stored_clips;
    }});
}}
setInterval(updateStatus, {STATUS_REFRESH_SECONDS * 1000});
updateStatus();
</script>
</body></html>
"""

@app.route("/talk")
def talk_page():
    global talk_mode
    talk_mode = True
    audio_html = ""
    for f in list_audio_files():
        audio_html += f"""
        <div class="clip">
            <h3>{f.name}</h3>
            <p>{round(f.stat().st_size / 1024, 1)} KB - {datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}</p>
            <audio controls src="/audio-files/{f.name}"></audio><br>
            <a href="/play-audio/{f.name}"><button>Play on Pi speaker</button></a>
            <a href="/audio-files/{f.name}" download><button>Download</button></a>
            <a href="/delete-audio/{f.name}" onclick="return confirm('Delete audio {f.name}?');"><button>Delete</button></a>
        </div>
        """

    return f"""
<!doctype html>
<html>
<head><title>Talk / Audio</title>{page_style()}</head>
<body>
<h1>Talk / Audio Page</h1>
<div class="card">
    <p><b>PIR motion detection is paused while this page is open.</b></p>
    <a href="/exit-talk"><button>Exit talk mode / resume PIR</button></a>
</div>
<div class="dashboard">
    <div>
        <div class="card">
            <h2>Live Video</h2>
            <img src="/stream.mjpg" width="1280">
        </div>
        <div class="card">
            <h2>Recorded Audio Messages</h2>
            {audio_html if audio_html else '<p>No audio messages yet.</p>'}
        </div>
    </div>
    <div>
        <div class="card">
            <h2>Record from Webcam Mic</h2>
            <form action="/record-audio" method="get">
                <label>Seconds: <input type="number" name="seconds" min="1" max="30" value="5"></label><br><br>
                <button type="submit">Record audio message</button>
            </form>
            <p class="small">Records from {AUDIO_CAPTURE_DEVICE}.</p>
        </div>
        <div class="card">
            <h2>Upload WAV</h2>
            <form action="/upload-audio" method="post" enctype="multipart/form-data">
                <input type="file" name="audiofile" accept=".wav,audio/wav"><br><br>
                <button type="submit">Upload WAV</button>
            </form>
            <p class="small">Only .wav files are accepted in this first version.</p>
        </div>
        <div class="card">
            <h2>Important</h2>
            <p class="small">This is not true browser-to-Pi live talkback yet. It records and plays WAV messages. True live talkback needs WebRTC or a WebSocket audio path.</p>
        </div>
    </div>
</div>
</body></html>
"""

@app.route("/archive")
def archive_page():
    files = list_archive_files()
    archive_html = ""
    for file in files:
        archive_html += f"""
        <div class="clip">
            <h3>{file.name}</h3>
            <p>{round(file.stat().st_size / 1024 / 1024, 1)} MB - {datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}</p>
            <video width="640" controls preload="metadata"><source src="/archive-files/{file.name}" type="video/mp4"></video><br>
            <a href="/archive-files/{file.name}" download><button>Download</button></a>
            <a href="/delete-archive/{file.name}" onclick="return confirm('Delete archived video {file.name}?');"><button>Delete</button></a>
        </div>
        """
    return f"""
<!doctype html>
<html>
<head><title>Archive</title>{page_style()}</head>
<body>
<h1>Video Archive</h1>
<div class="card">
    <a href="/"><button>Back to main page</button></a>
    <a href="/download-archive"><button>Download full archive ZIP</button></a>
    <a href="/delete-all-archive" onclick="return confirm('Delete all archived videos?');"><button>Delete full archive</button></a>
</div>
<div class="card"><b>Archived videos:</b> {len(files)}</div>
{archive_html if archive_html else '<p>No archived videos yet.</p>'}
</body></html>
"""

# =========================
# Start
# =========================

Thread(target=camera_loop, daemon=True).start()
Thread(target=pir_loop, daemon=True).start()

app.run(host="0.0.0.0", port=8080, threaded=True)
