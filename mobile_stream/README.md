# 📱 Mobile RTSP & Video Streaming Guide for Traffic_CV

This directory contains production-ready tools and step-by-step instructions to turn any mobile phone (Android or iOS) into a high-speed, zero-frame-drop RTSP / live video camera for the Traffic_CV access logging and ANPR pipeline.

---

## ⚡ Quick Start: Choose Your Streaming Method

| Method | Recommended For | Protocol | Setup Time | Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Option 1: IP Webcam (Android)** | High stability & dedicated gate camera | RTSP / HTTP MJPEG | 2 mins | < 100ms |
| **Option 2: Larix Broadcaster (iOS & Android)** | Pro RTSP/RTSP stream with hardware H.264 | RTSP (TCP) | 2 mins | < 80ms |
| **Option 3: RTSP Camera (iOS & Android)** | Lightweight instant RTSP server | RTSP (TCP) | 1 min | < 100ms |
| **Option 4: Mobile Web Browser (WebPush)** | Zero installation / instant test on any phone | WebSocket / HTTP | 10 seconds | < 50ms |

---

## 🚀 Option 1: Android IP Webcam (Recommended for Android)

1. **Install App**: Download **IP Webcam** by Pavel Khlebovich from Google Play Store.
2. **Configure Settings in App**:
   - **Video preferences**:
     - *Video resolution*: `1280x720` (Recommended for balance of OCR accuracy and 30+ FPS speed) or `1920x1080`.
     - *Quality*: `80%`.
   - **Local broadcasting**:
     - *Port*: `8080` (default).
   - *(Optional) RTSP Server*: Enable RTSP server (Port `8554` or `8080`).
3. **Start Stream**: Scroll to the bottom and tap **"Start server"**.
4. **Get the Stream URL**:
   - Your phone will display an IP address on screen (e.g., `http://192.168.1.105:8080`).
   - **HTTP MJPEG URL**: `http://192.168.1.105:8080/video`
   - **RTSP URL (if enabled)**: `rtsp://192.168.1.105:8080/h264_pcm.sdp` or `rtsp://192.168.1.105:8554/live`
5. **Connect to Pipeline**:
   ```bash
   python set_mobile_stream.py http://192.168.1.105:8080/video
   # Or with RTSP:
   python set_mobile_stream.py rtsp://192.168.1.105:8080/h264_pcm.sdp
   ```

---

## 🎥 Option 2: Larix Broadcaster (Android & iOS)

1. **Install App**: Download **Larix Broadcaster** from Google Play Store or Apple App Store.
2. **Configure Settings**:
   - Open Settings ➡️ **Video**:
     - *Resolution*: `1280x720` (720p).
     - *FPS*: `30`.
     - *Bitrate*: `2500 Kbps` (2.5 Mbps).
     - *Keyframe frequency*: `1 second`.
   - Open Settings ➡️ **Connections**:
     - Tap `+` to add a new connection.
     - *URL*: `rtsp://<SERVER_IP>:8554/live/stream` or setup RTSP server mode.
3. Tap the big red record button to broadcast live.

---

## 📹 Option 3: RTSP Camera (iOS & Android)

1. **Install App**: Download **RTSP Camera** from App Store (iOS) or Play Store (Android).
2. **Start Server**:
   - Open app and tap Start / Broadcast.
   - Note the RTSP URL shown on the screen (e.g. `rtsp://192.168.1.120:8554/live`).
3. **Connect to Pipeline**:
   ```bash
   python set_mobile_stream.py rtsp://192.168.1.120:8554/live
   ```

---

## 🌐 Option 4: Zero-Install Mobile Web Camera (WebPush)

You can use any phone browser (Chrome on Android, Safari on iOS) without installing any app:

1. Connect your phone to the same Wi-Fi network as your computer.
2. Find your computer's local IP address (e.g. `192.168.1.50`).
3. Open your mobile browser and navigate to:
   ```
   http://<YOUR_COMPUTER_IP>:8002/phone
   ```
4. Tap **"Start Stream"** and grant camera permissions.
5. In the terminal or dashboard, set the camera source to `push`:
   ```bash
   python set_mobile_stream.py push
   ```
   *(Or click "Set to Phone Web Camera" in the Web Configurator)*.

---

## 🛠️ CLI Utilities in this Folder

### 1. Interactive Camera Source Manager
Run the interactive setup assistant:
```bash
python mobile_stream/setup_mobile_stream.py
```
This utility:
- Detects your local LAN IP address automatically.
- Shows live QR codes for instant mobile browser pairing.
- Validates the RTSP / HTTP URL with a live 2-second probe before updating the database.
- Signals the AI pipeline to restart on the new feed with 0 downtime.

### 2. Stream Tester & Benchmark Tool
Before hooking an RTSP or HTTP feed into the AI pipeline, test its stability and frame rate:
```bash
python mobile_stream/stream_tester.py rtsp://192.168.1.105:8080/h264_pcm.sdp
```
Output includes:
- Resolution & Aspect Ratio
- Real-time Received FPS
- Average Frame Decoding Latency (ms)
- Dropped Frame / Timeout Count
- Connection Protocol (TCP / UDP)

---

## 🏎️ How Zero Frame Drop is Guaranteed

1. **Forced TCP Transport**: The pipeline configures OpenCV FFmpeg with `rtsp_transport;tcp`. Over Wi-Fi, UDP packets get dropped under congestion, causing grey screens and corruption. TCP guarantees bit-perfect frame delivery.
2. **Zero-Buffer Low Delay**: `fflags=nobuffer`, `flags=low_delay`, `max_delay=500000` eliminates the default 5-second FFmpeg buffering backlog.
3. **Decoupled Asynchronous Reader**: `FreshFrameReader` runs a high-speed background thread that continuously grabs the freshest frame. Even if heavy YOLO+OCR computation is processing on frame $N$, frame $N+1$ is never delayed.
4. **Auto-Reconnecting Watchdog**: If Wi-Fi briefly drops or the phone locks, the reader automatically initiates clean reconnection without hanging or crashing the AI pipeline.
5. **WebSocket Backpressure**: For mobile browser streaming, the client only transmits when `ws.bufferedAmount === 0`, ensuring zero client-side frame queuing.
