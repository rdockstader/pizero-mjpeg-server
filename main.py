"""
MJPEG Streaming Server for Raspberry Pi Zero W + Camera Module 3
-----------------------------------------------------------------
Streams live MJPEG video over HTTP, suitable for AI consumption.

Usage:
    python3 mjpeg_stream.py [--port 8080] [--width 640] [--height 480] [--fps 15] [--quality 80]

Access the stream at:
    http://<pi-ip>:8080/stream   <- raw MJPEG (for AI/OpenCV)
    http://<pi-ip>:8080/         <- browser preview page
    http://<pi-ip>:8080/snapshot <- single JPEG frame

Requirements:
    pip install picamera2
    (picamera2 is pre-installed on Raspberry Pi OS Bullseye+)
"""

import argparse
import io
import logging
import socketserver
import threading
import time
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="MJPEG stream server for Pi Camera Module 3")
parser.add_argument("--port",    type=int, default=8080,  help="HTTP port (default: 8080)")
parser.add_argument("--width",   type=int, default=640,   help="Frame width  (default: 640)")
parser.add_argument("--height",  type=int, default=480,   help="Frame height (default: 480)")
parser.add_argument("--fps",     type=int, default=15,    help="Frames per second (default: 15)")
parser.add_argument("--quality", type=int, default=80,    help="JPEG quality 1-95 (default: 80)")
args = parser.parse_args()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mjpeg")

# ---------------------------------------------------------------------------
# Shared frame buffer with condition variable for efficient waiting
# ---------------------------------------------------------------------------

class StreamOutput(io.BufferedIOBase):
    """Thread-safe buffer that holds the latest JPEG frame."""

    def __init__(self):
        self.frame: bytes = b""
        self.condition = Condition()

    def write(self, buf: bytes) -> int:
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)


output = StreamOutput()

# ---------------------------------------------------------------------------
# HTML preview page
# ---------------------------------------------------------------------------

INDEX_HTML = f"""\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pi Camera Stream</title>
  <style>
    body {{ margin: 0; background: #111; display: flex; flex-direction: column;
           align-items: center; justify-content: center; min-height: 100vh;
           font-family: monospace; color: #0f0; }}
    h1   {{ font-size: 1rem; letter-spacing: 0.2em; margin-bottom: 1rem; }}
    img  {{ max-width: 100%; border: 1px solid #0f04; border-radius: 4px; }}
    p    {{ font-size: 0.75rem; color: #0f08; margin-top: 0.5rem; }}
  </style>
</head>
<body>
  <h1>&#9679; LIVE STREAM</h1>
  <img src="/stream" alt="MJPEG stream">
  <p>{args.width}&times;{args.height} &nbsp;&bull;&nbsp; {args.fps} fps &nbsp;&bull;&nbsp; q{args.quality}</p>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class Handler(server.BaseHTTPRequestHandler):
    """Handles /, /stream, and /snapshot endpoints."""

    def log_message(self, fmt, *a):
        # Suppress per-frame access logs to reduce noise; log errors only
        if self.command != "GET" or self.path not in ("/stream",):
            log.info("%s - %s", self.address_string(), fmt % a)

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_index()
        elif self.path == "/stream":
            self._serve_mjpeg()
        elif self.path == "/snapshot":
            self._serve_snapshot()
        else:
            self.send_error(404)

    # ----------------------------------------------------------- index page
    def _serve_index(self):
        content = INDEX_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # ------------------------------------------------------- MJPEG stream
    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header(
            "Content-Type",
            "multipart/x-mixed-replace; boundary=FRAME"
        )
        self.end_headers()

        try:
            while True:
                with output.condition:
                    output.condition.wait()   # block until new frame arrives
                    frame = output.frame

                self.wfile.write(
                    b"--FRAME\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    b"\r\n" + frame + b"\r\n"
                )
        except Exception:
            # Client disconnected — normal; just stop the loop
            pass

    # --------------------------------------------------- single JPEG frame
    def _serve_snapshot(self):
        with output.condition:
            output.condition.wait()
            frame = output.frame

        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(frame)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(frame)


# ---------------------------------------------------------------------------
# Threaded HTTP server
# ---------------------------------------------------------------------------

class ThreadedHTTPServer(socketserver.ThreadingMixIn, server.HTTPServer):
    """Handles each client in its own thread."""
    allow_reuse_address = True
    daemon_threads = True

# ---------------------------------------------------------------------------
# Main — camera setup + server start
# ---------------------------------------------------------------------------

def main():
    log.info("Initialising Camera Module 3 …")
    cam = Picamera2()

    # Video configuration — autofocus is enabled by default on Module 3
    config = cam.create_video_configuration(
        main={"size": (args.width, args.height), "format": "RGB888"},
        controls={
            "FrameRate": float(args.fps),
        },
    )
    cam.configure(config)

    # Use JPEG encoder with quality setting
    encoder = JpegEncoder(q=args.quality)
    cam.start_recording(encoder, FileOutput(output))

    log.info("Camera started: %dx%d @ %d fps  quality=%d",
             args.width, args.height, args.fps, args.quality)

    addr = ("", args.port)
    httpd = ThreadedHTTPServer(addr, Handler)

    log.info("Serving on port %d", args.port)
    log.info("  Stream   → http://<this-pi-ip>:%d/stream", args.port)
    log.info("  Preview  → http://<this-pi-ip>:%d/", args.port)
    log.info("  Snapshot → http://<this-pi-ip>:%d/snapshot", args.port)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down …")
    finally:
        cam.stop_recording()
        httpd.server_close()


if __name__ == "__main__":
    main()