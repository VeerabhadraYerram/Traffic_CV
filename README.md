# VigilantEye — ANPR & Traffic CV System

VigilantEye is an enterprise-grade real-time system for traffic monitoring, vehicle tracking, and violation analytics. It consists of a high-performance computer vision pipeline and an interactive web control center.

---

## 🏗️ System Architecture

The system is designed for 100% on-premise, air-gapped deployment capability (no cloud API keys required) and consists of three core components:

1. **Computer Vision Pipeline (`traffic_pipeline`)**: A multi-threaded Python application utilizing **YOLO11m** (for vehicle detection), **DeepSORT** (for vehicle tracking), and **EasyOCR** (for plate reading) to process video feeds.
2. **Database (`traffic_db`)**: A PostgreSQL 15 database that manages camera configurations and access logs.
3. **Web Analytics Dashboard (`dashboard`)**: A low-latency web control center with live event feeds, geospatial vehicle tracking, and historical analytics.

```mermaid
graph TD
    A[CCTV / RTSP Feed] --> B[YOLO11 + DeepSORT]
    B --> C[EasyOCR ALPR]
    C --> D[Temporal Consensus Algorithm]
    D --> E[(PostgreSQL Database)]
    E --> F[Appwrite Sync]
    F --> G[React Web Dashboard]
```

---

## 📊 Dashboard Preview

Here is a preview of the interactive web control center:

### 1. Live Events Feed & Real-time Monitor
Displays live video metadata, recent crossings, status badges ("Inside"/"Exited"), and camera logs with filtering.
![Live Events Feed](dashboard/playwright_verified_light_mode.png)

### 2. Geospatial Vehicle Tracking & Search
Allows searching vehicles by license plate, displaying their traversal history, last-seen camera details, and a mapping component.
![Vehicle Tracking & Search](dashboard/tracking_page.png)

### 3. Traffic Analytics & Volume Dashboard
Features vehicle composition stats (Cars, Bikes, Trucks, Buses), volume trends over time, and alert frequency logs.
![Traffic Analytics](dashboard/analytics_page.png)

---

## 📹 Part 1: Computer Vision Pipeline & Infrastructure

### Core Features
- **Zero Cloud Dependency**: Completely local execution. No API keys, no credit limits, no internet requirement.
- **Dynamic Hardware Acceleration**: Automatically detects and leverages NVIDIA CUDA GPUs, Apple Silicon MPS, or standard CPUs depending on the deployment server.
- **Database-Driven Configuration**: Camera video sources, roles, and crossing lines are fetched dynamically from Postgres. No need to touch Python code to add a new gate.
- **Smart-Cropped OCR Pipeline**: To eliminate background noise and maximize FPS, the system intelligently crops out the bottom 60% of tracked vehicle bounding boxes before feeding images into the EasyOCR engine, drastically improving license plate read accuracy and effectively doubling processing speed.
- **Aggressive DeepSORT Tracking**: Tracking parameters (`max_age=30`, `nms_max_overlap=0.5`) are heavily tuned for dense, low-speed traffic, eliminating duplicate bounding boxes and preventing "ghosting" tracks after cars leave the frame.
- **Temporal ALPR Consensus**: Instead of saving messy, single-frame OCR reads, the pipeline accumulates all plate readings for a given tracking ID and calculates the statistical **mode** (majority vote) upon the vehicle's exit, writing only the highest-confidence string to the database.

### Prerequisites
Before you begin, ensure you have the following installed on your host machine:
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- Git
*(Note: For production deployments, ensure the server has the `nvidia-container-toolkit` installed to enable GPU acceleration).*

### How to Run and Test the Pipeline
1. **Clone the Repository**
   ```bash
   git clone https://github.com/VeerabhadraYerram/Traffic_CV.git
   cd Traffic_CV
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

---

## 📹 Adding & Configuring Live Cameras

The system is fully modular. To process a new live camera feed in production, you simply add a row to the `cameras` table in the PostgreSQL database.

#### Using Live RTSP Streams
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

#### Coordinate System & Custom Lines
The system uses **Normalized Coordinates** (from `0.0` to `1.0`) instead of hardcoded pixels. This ensures that if a camera is upgraded from 1080p to 4K, the virtual lines stay in the exact same physical location.
- `x = 0.0` is the left edge, `x = 1.0` is the right edge.
- `y = 0.0` is the top edge, `y = 1.0` is the bottom edge.

---

## 📊 Part 2: Web Analytics Dashboard

The Web Analytics Dashboard provides an interactive control panel for smart city operators and traffic law enforcement.

### Tech Stack
- **Framework:** React 19, TypeScript 6, Vite 8
- **Routing:** React Router v7
- **State:** TanStack Query v5, TanStack Table v8
- **Styling:** Tailwind CSS v4, shadcn/ui (Radix UI)
- **Charts:** Recharts v3
- **Maps:** Google Maps API
- **Backend Sync:** Appwrite SDK
- **Notifications:** Sonner

### Getting Started
1. **Install Dependencies**
   ```bash
   npm install
   ```
2. **Start the Development Server**
   ```bash
   npm run dev
   ```
3. **Build for Production**
   ```bash
   npm run build
   ```
4. **Preview Production Build**
   ```bash
   npm run preview
   ```

---

## 📂 Documentation Reference
- [Product Requirements](dashboard/docs/PRD.md)
- [UI Design & Wireframes](dashboard/docs/DESIGN.md)
- [Database Schema](dashboard/docs/DB.md)
- [Tech Stack Architecture](dashboard/docs/TechStack.md)
