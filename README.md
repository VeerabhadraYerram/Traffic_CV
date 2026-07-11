# Production Vehicle Access Logging System

A scalable, on-premise computer vision system designed to monitor vehicle entries and exits, perform Automatic License Plate Recognition (ALPR), and reliably log timestamped data into a PostgreSQL database.

This project uses an advanced **YOLO11 + DeepSORT + EasyOCR** computer vision stack running concurrently across multiple video feeds, and leverages a Temporal Consensus Algorithm to eliminate motion blur and ensure high-accuracy license plate reads.

---

## 🏗️ Architecture Overview

The system is designed for 100% on-premise, air-gapped deployment capability (no cloud API keys required) and consists of two core Docker containers:
1. **Database Container (`traffic_db`)**: A PostgreSQL 15 database that manages camera configurations and access logs.
2. **Pipeline Container (`traffic_pipeline`)**: A multi-threaded Python application utilizing **YOLO11m** (for vehicle detection), **DeepSORT** (for vehicle tracking), and **EasyOCR** (for plate reading) to process video feeds.

### Core Features
- **Zero Cloud Dependency**: Completely local execution. No API keys, no credit limits, no internet requirement.
- **Dynamic Hardware Acceleration**: Automatically detects and leverages NVIDIA CUDA GPUs, Apple Silicon MPS, or standard CPUs depending on the deployment server.
- **Database-Driven Configuration**: Camera video sources, roles, and crossing lines are fetched dynamically from Postgres. No need to touch Python code to add a new gate.
- **Smart-Cropped OCR Pipeline**: To eliminate background noise and maximize FPS, the system intelligently crops out the bottom 60% of tracked vehicle bounding boxes before feeding images into the EasyOCR engine, drastically improving license plate read accuracy and effectively doubling processing speed.
- **Aggressive DeepSORT Tracking**: Tracking parameters (`max_age=30`, `nms_max_overlap=0.5`) are heavily tuned for dense, low-speed traffic, eliminating duplicate bounding boxes and preventing "ghosting" tracks after cars leave the frame.
- **Temporal ALPR Consensus**: Instead of saving messy, single-frame OCR reads, the pipeline accumulates all plate readings for a given tracking ID and calculates the statistical **mode** (majority vote) upon the vehicle's exit, writing only the highest-confidence string to the database.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your host machine:
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- Git

*(Note: For production deployments, ensure the server has the `nvidia-container-toolkit` installed to enable GPU acceleration).*

---

## 🚀 How to Run and Test the Pipeline

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd Traffic_Analysis_Workflow
   ```

2. **Launch the Infrastructure**
   Run the following command to build the images, spin up the Postgres database, execute the initial `schema.sql` migration, and start the processing pipeline:
   ```bash
   docker compose up -d --build
   ```
   *(Note: The first build will take a few minutes as it downloads PyTorch, YOLO11, OpenCV, and DeepSORT dependencies).*

3. **How to Test with Local Video Files**
   In the `docker-compose.yml`, the `data/downloads` folder inside this repository is mounted to `/app/downloads/` inside the container. 
   
   To test the pipeline on a video file:
   - Create a folder named `data/downloads` inside this project directory.
   - Drop a test video (e.g., `test_video.mp4`) into `data/downloads/`.
   - Connect to the local Postgres database (`localhost:5432`, user: `admin`, pass: `adminpassword`).
   - Insert a row into the `cameras` table pointing to your video:
     ```sql
     INSERT INTO cameras (name, video_source, camera_role, entry_line_normalized, exit_line_normalized, is_active)
     VALUES ('Test Video', '/app/downloads/test_video.mp4', 'bidirectional', '{"x1": 0.0, "y1": 0.3, "x2": 1.0, "y2": 0.3}'::jsonb, '{"x1": 0.0, "y1": 0.7, "x2": 1.0, "y2": 0.7}'::jsonb, true);
     ```
   - Restart the pipeline so it picks up the new camera:
     ```bash
     docker restart traffic_pipeline
     ```

4. **NVIDIA GPU Acceleration (Optional)**
   If your server has an NVIDIA GPU, you can unlock 60+ FPS processing. Open `docker-compose.yml`, locate the `deploy` block under the `app` service, and uncomment it to enable native Docker GPU passthrough.

5. **Web Configuration Dashboard**
   A sleek web interface is automatically started alongside the pipeline. You can use it to visually draw entry and exit tripwires for any camera.
   - Open your browser to: `http://localhost:8000`
   - Select a camera from the dropdown to load a snapshot frame.
   - Use the drawing tools to place your green and red lines.
   - Click "Save Configuration" to instantly update the PostgreSQL database.

6. **Monitor Live Logs**
   ```bash
   docker logs -f traffic_pipeline
   ```

7. **Generate a Debug/Visualization Video (Optional)**
   If you need to verify tracking accuracy or see exactly where your crossing lines are physically drawn, you can run the debugging visualization script. This will output a file named `your_video_output.mp4` to your `data/downloads/` folder showing YOLO bounding boxes, tracker IDs, OCR reads, and the entry/exit lines.
   ```bash
   # Automatically visualize the first active camera in your database
   docker compose run --rm app python visualize.py
   
   # Or explicitly specify which camera to visualize
   docker compose run --rm app python visualize.py --camera "Test Video Bidirectional"
   ```

---

## 📹 Adding & Configuring Live Cameras

The system is fully modular. To process a new live camera feed in production, you simply add a row to the `cameras` table in the PostgreSQL database.

### Using Live RTSP Streams
For real IP security cameras, simply insert the camera's network link into the database:
```sql
INSERT INTO cameras (name, video_source, camera_role, entry_line_normalized, exit_line_normalized, is_active)
VALUES (
    'North Gate',
    'rtsp://admin:password@192.168.1.100:554/stream1',
    'entrance',
    '{"x1": 0.1, "y1": 0.5, "x2": 0.9, "y2": 0.5}'::jsonb,
    NULL,
    true
);
```
### 📐 Coordinate System & Custom Lines
The system uses **Normalized Coordinates** (from `0.0` to `1.0`) instead of hardcoded pixels. This ensures that if a camera is upgraded from 1080p to 4K, the virtual lines stay in the exact same physical location.
- `x = 0.0` is the left edge, `x = 1.0` is the right edge.
- `y = 0.0` is the top edge, `y = 1.0` is the bottom edge.

#### Quick Testing Template
If you are just adding a test video and don't want to calculate exact pixels, you can safely paste this generic template into the database row. It draws horizontal lines at the top-third and bottom-third of the screen, which works perfectly for most downward-facing cameras:
- **entry_line_normalized**: `{"x1": 0.0, "y1": 0.3, "x2": 1.0, "y2": 0.3}`
- **exit_line_normalized**: `{"x1": 0.0, "y1": 0.7, "x2": 1.0, "y2": 0.7}`

---

## 📊 Viewing the Data

The ultimate product of this pipeline is the `premise_access_logs` table in Postgres. 

### Option 1: Database GUI (Recommended)
Connect to the database using any SQL client (DBeaver, TablePlus, Postico):
- **Host**: `localhost`
- **Port**: `5432`
- **User**: `admin`
- **Password**: `adminpassword`
- **Database**: `traffic`

### Option 2: Terminal Script
A convenience script is provided to view the data directly in your terminal.
```bash
# In your local Python environment
pip install pandas psycopg2-binary SQLAlchemy
python query_db.py
```
