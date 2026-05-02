# Simple Python PiCam MJPEG Server

> Simple Python script that hosts an MJPEG server on a Raspberry Pi using a Pi Camera Module 3.

![license](https://img.shields.io/github/license/rdockstader/pizero-mjpeg-server)

## Features

- Simple example of an MJPEG server
- Browser preview page and single-frame snapshot endpoint included
- Great for consuming the stream from a different device for ML/AI/Computer Vision tasks
- Runs well on a Pi Zero 2 W

## Installation

**Prerequisites:** Python, pip, Raspberry Pi OS Bullseye or later

Install the dependencies from apt:
```bash
sudo apt install -y build-essential libcap-dev python3-dev python3-libcamera python3-kms++
```

Set up the Python virtual environment and install picamera2:
```bash
python3 -m venv .venv --system-site-packages
source ./.venv/bin/activate
pip install picamera2
```

## Usage

To run the script with the defaults, while in the virtual environment:
```bash
python ./main.py
```

Once running, the server exposes three endpoints:

| Endpoint | Description |
|----------|-------------|
| `http://<pi-ip>:8080/stream` | Raw MJPEG stream (for OpenCV/AI) |
| `http://<pi-ip>:8080/` | Browser preview page |
| `http://<pi-ip>:8080/snapshot` | Single JPEG frame |

## Configuration

You can pass different arguments to the script:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--port` | number | `8080` | Port to listen on |
| `--width` | number | `1280` | Width of the stream output in pixels |
| `--height` | number | `720` | Height of the stream output in pixels |
| `--fps` | number | `30` | Target frames per second of stream output |
| `--quality` | number | `80` | Quality of output, 0-100 |

Example:
```bash
python ./main.py --port 8080 --width 640 --height 480 --fps 15 --quality 70
```

> **Running on a Pi Zero (original)?** Reduce `--fps` to 10–15 and `--width`/`--height` to 640×480 to maintain a stable stream.

## Running as a Service

To have the MJPEG server start automatically on boot and restart if it crashes, you can install it as a `systemd` service using the included `service-install.sh` unit file.

**1. Edit the unit file**

Open `service-install.sh` and update the placeholders so they match your environment:

- `User=` — the Linux user that should run the service (e.g. `pi`)
- `WorkingDirectory=` — the absolute path to the cloned repo (e.g. `/home/pi/code/pizero-mjpeg-server`)
- `ExecStart=` — must point to the `python` binary inside your `.venv` and to the absolute path of `main.py`

For example:
```ini
[Service]
User=pi
WorkingDirectory=/home/pi/code/pizero-mjpeg-server
ExecStart=/home/pi/code/pizero-mjpeg-server/.venv/bin/python /home/pi/code/pizero-mjpeg-server/main.py
```

If you want to pass custom arguments (port, resolution, fps, quality), append them to the `ExecStart` line:
```ini
ExecStart=/home/pi/code/pizero-mjpeg-server/.venv/bin/python /home/pi/code/pizero-mjpeg-server/main.py --width 640 --height 480 --fps 15
```

**2. Install the unit file**

Copy the file into `systemd`'s unit directory and reload the daemon:
```bash
sudo cp mjpeg-server.service /etc/systemd/system/mjpeg-server.service
sudo systemctl daemon-reload
```

**3. Enable and start the service**

```bash
sudo systemctl enable mjpeg-server.service
sudo systemctl start mjpeg-server.service
```

**4. Check status and logs**

```bash
sudo systemctl status mjpeg-server.service
journalctl -u mjpeg-server.service -f
```

To stop or disable the service:
```bash
sudo systemctl stop mjpeg-server.service
sudo systemctl disable mjpeg-server.service
```

## License

[MIT](./LICENSE)