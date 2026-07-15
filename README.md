# Production Vehicle Access Logging System (Traffic_CV)

A production-ready Computer Vision pipeline designed for local, on-premise execution to log vehicle entries and exits through live video streams. The system leverages state-of-the-art YOLO object detection alongside PaddleOCR for highly accurate, real-time license plate reading.

## 🌟 Key Features
- **Accurate Tracking**: DeepSort and YOLOv11 track vehicle movements to determine exact entry and exit times.
- **Robust OCR**: Uses PaddleOCR to read license plates. Stabilized to prevent memory leaks and C++ runtime errors.
- **On-Premise Ready**: 100% local execution—no cloud storage or external API requirements.
- **Live Dashboard**: A fast web UI to configure streams, define detection zones, and monitor live vehicle logs.

---

## 🛠️ Recent Improvements & Architecture Updates
Following a deep audit for production stability, the codebase has been significantly optimized:

1. **PaddleOCR Integration (Stability Upgrade)**
   - Replaced `EasyOCR` (which caused `CUDA error: out of memory` under peak loads) with `PaddleOCR`.
   - **Dependency Locking:** Locked `paddlepaddle==2.6.2` and `paddleocr==2.8.1` to bypass known `oneDNN` C++ bugs present in the newer Paddle 3.x engines.
   
2. **Codebase Cleanup & Modularization**
   - Removed all legacy and duplicate scripts (e.g., `run_cameras.py`, `stream_server.py`, old benchmark files).
   - Extracted shared utilities (plate correction, DB flushing, consensus voting) into a lightweight `utils.py` module.
   - Cleared gigabytes of stale static UI assets and old debug videos.

3. **Docker Consolidation**
   - Streamlined Docker environment into three highly stable containers: `traffic_db` (Postgres), `traffic_pipeline` (Computer Vision Engine), and `traffic_web` (Dashboard).

---

## 🚀 How to Run the Pipeline

The entire system is containerized via Docker for reliable execution.

### Prerequisites
- Docker and Docker Compose installed.
- (Optional but Recommended) NVIDIA GPU with the latest drivers and NVIDIA Container Toolkit installed for native CUDA acceleration.

### Startup
1. Open your terminal in the project root directory.
2. Build and start the containers in detached mode:
   ```bash
   docker compose up -d --build
   ```
3. To check the logs of the pipeline engine as it starts up:
   ```bash
   docker logs -f traffic_pipeline
   ```

*Note: On the first run, the system will download the YOLO weights and the pre-trained PaddleOCR models directly into the container.*

---

## 📊 How to Visualize in the Dashboard

Once the containers are successfully running, the Web UI acts as your primary control center.

1. **Open the Dashboard**
   - Navigate to **[http://localhost:8000](http://localhost:8000)** in your web browser.

2. **Configure Video Streams**
   - In the UI, add your video stream sources (RTSP camera links or local MP4 files like `downloads/sample.mp4`).
   - Draw or define your **LineZones** (the virtual gates that vehicles cross to register an entry or exit).
   
3. **Monitor Live Tracking**
   - You can watch the processed video stream in real time.
   - The dashboard displays a live feed of logged vehicles, including their timestamps, direction (Entry/Exit), and captured License Plate text.

4. **Database Access**
   - All vehicle events are saved permanently to the PostgreSQL database.
   - If you need direct access to the database (e.g., via DBeaver or PGAdmin), connect using:
     - **Host:** `localhost`
     - **Port:** `5435`
     - **User:** `admin`
     - **Password:** `adminpassword`
     - **DB Name:** `traffic`
