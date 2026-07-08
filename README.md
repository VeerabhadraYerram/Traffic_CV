# Production Vehicle Access Logging System

A scalable, on-premise computer vision system designed to monitor vehicle entries and exits, perform Automatic License Plate Recognition (ALPR), and reliably log timestamped data into a PostgreSQL database.

This project uses Roboflow inference models running concurrently across multiple video feeds, and leverages a Temporal Consensus Algorithm to eliminate motion blur and ensure high-accuracy license plate reads.

---

## 🏗️ Architecture Overview

The system is designed for 100% on-premise, air-gapped deployment capability and consists of two core Docker containers:
1. **Database Container (`traffic_db`)**: A PostgreSQL 15 database that manages camera configurations and access logs.
2. **Pipeline Container (`traffic_pipeline`)**: A multi-threaded Python application utilizing **SQLAlchemy** (for connection pooling) and **Roboflow Inference** to process video feeds.

### Core Features
- **Database-Driven Configuration**: Camera video sources, roles, and crossing lines are fetched dynamically from Postgres. No need to touch Python code to add a new gate.
- **Concurrent Processing**: Multiple RTSP streams or video files are processed in parallel.
- **Temporal ALPR Consensus**: Instead of saving messy, single-frame OCR reads, the pipeline accumulates all plate readings for a given tracking ID and calculates the statistical **mode** (majority vote) upon the vehicle's exit, writing only the highest-confidence string to the database.

---

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your host machine:
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- Git

You will also need a **Roboflow API Key** to run the underlying model. Set it in a `.env` file in the root directory:
```env
ROBOFLOW_API_KEY=your_api_key_here
```

---

## 🚀 Installation & Setup

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
   *(Note: The first build will take 5-10 minutes as it downloads PyTorch, OpenCV, and Inference dependencies).*

3. **Monitor Live Logs**
   To watch the computer vision models track vehicles and resolve plates in real-time, view the Docker logs:
   ```bash
   docker compose logs -f traffic_pipeline
   ```

---

## 📹 Adding & Configuring Cameras

The system is fully modular. To process a new camera feed, you simply add a row to the `cameras` table in the PostgreSQL database.

### Using Local Video Files (Testing)
In the `docker-compose.yml`, the local `/Users/shivaniyerram/Downloads` folder is mounted to `/app/downloads/` inside the container. 
1. Drop `video.mp4` into your Downloads folder.
2. Insert a row into the database setting `video_source = '/app/downloads/video.mp4'`.

### Using Live RTSP Streams (Production)
For real IP security cameras, you do not need a volume mount. Simply insert the camera's network link into the database:
```sql
INSERT INTO cameras (name, video_source, camera_role, entry_line_normalized, exit_line_normalized)
VALUES (
    'North Gate',
    'rtsp://admin:password@192.168.1.100:554/stream1',
    'entrance',
    '{"x1": 0.1, "y1": 0.5, "x2": 0.9, "y2": 0.5}'::jsonb,
    NULL
);
```
### 📐 Coordinate System & Custom Lines
The system uses **Normalized Coordinates** (from `0.0` to `1.0`) instead of hardcoded pixels. This ensures that if a camera is upgraded from 1080p to 4K, the virtual lines stay in the exact same physical location.
- `x = 0.0` is the left edge, `x = 1.0` is the right edge.
- `y = 0.0` is the top edge, `y = 1.0` is the bottom edge.

#### How to Configure Precise Lines for a Real Camera
When deploying a new CCTV camera to production, your team must define exactly where the virtual "Entry" and "Exit" gates are located in that specific camera's view.

1. **Take a Snapshot**: Capture a single image frame from the live CCTV camera. Let's assume the camera is 1920x1080 resolution.
2. **Find the Pixels**: Open the image in any image viewer (like MS Paint or Photoshop). Hover your mouse over where you want the line to start and end. Let's say you want a diagonal line across a gate:
   - Start point: `(X: 480, Y: 800)`
   - End point: `(X: 1440, Y: 800)`
3. **Calculate the Percentage**: Divide your X pixels by the image width (1920), and your Y pixels by the image height (1080).
   - Normalized Start: `480 / 1920 = 0.25`, `800 / 1080 = 0.74`
   - Normalized End: `1440 / 1920 = 0.75`, `800 / 1080 = 0.74`
4. **Input into the Database**: Open your PostgreSQL database viewer, locate this specific camera's row in the `cameras` table, and paste the resulting JSON directly into the column:
   - `entry_line_normalized` column: `{"x1": 0.25, "y1": 0.74, "x2": 0.75, "y2": 0.74}`

Because the configuration lives entirely in the database row for that specific camera, the Python pipeline will dynamically draw the custom lines for every camera individually.

#### Quick Testing Template
If you are just adding a test video and don't want to calculate exact pixels, you can safely paste this generic template into the database row. It draws horizontal lines at the top-third and bottom-third of the screen, which works perfectly for most downward-facing cameras:
- **entry_line_normalized**: `{"x1": 0.0, "y1": 0.3, "x2": 1.0, "y2": 0.3}`
- **exit_line_normalized**: `{"x1": 0.0, "y1": 0.7, "x2": 1.0, "y2": 0.7}`

*(After updating the database, run `docker restart traffic_pipeline` to load the new lines!)*

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

---

## 🤝 For Contributors & Teammates

### Expanding Features
This architecture is built for expansion. When adding new features like **Speed Detection** or **Traffic Violations**:
1. Add the necessary columns/tables to `schema.sql`.
2. Map the new tables in `models.py` using SQLAlchemy.
3. Hook into the `handle_predictions` callback in `run_cameras.py` to evaluate your custom logic alongside the ALPR consensus logic.

### Air-Gapped Deployment
The current implementation pulls the Roboflow model weights from the cloud via API key on startup. To transition to a 100% offline, air-gapped deployment, the model weights must be compiled and mounted directly into the Docker image, and `InferencePipeline` must be configured for offline mode.
