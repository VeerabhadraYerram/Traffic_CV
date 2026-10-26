# UC4 ANPR Integration Runbook — Innovision Platform (Approach 2)

This runbook guides deployment engineers through integrating the **UC4 ANPR & Vehicle Access Control Service** into the centralized Innovision on-premise server environment.

---

## 1. Architecture Overview

UC4 operates as a decoupled, event-driven stream worker:
- **Ingress**: Consumes decoded frames from the Platform Ingestion Service via Redis Streams (`streams:frames`).
- **Processing**: Tracks vehicle movements, estimates speeds, and performs license plate consensus voting.
- **Egress**: Publishes structured alerts to `streams:alerts` and saves visitor logs to isolated PostgreSQL tables (`uc4_*`).
- **Telemetry**: Exposes a non-blocking health probe on `http://localhost:8004/health`.

---

## 2. Pre-Deployment Checks

Before starting the service, run the automated prerequisite check script:

```bash
python check_prerequisites.py
```

Ensure all items print `[PASS]`:
- Python Version (>= 3.10)
- Vehicle Model Weights (`yolo11m.pt` present in root)
- Redis Connection (`innovision-redis:6379` reachable)
- Database Connection (`innovision-db:5432` reachable)

---

## 3. Configuration Step (.env)

Verify your `.env` file matches your on-premise server topology:

```env
# Service Port & Health
SERVICE_NAME=uc4-anpr
SERVICE_PORT=8004

# Platform Redis Streams
REDIS_HOST=innovision-redis
REDIS_PORT=6379
FRAME_STREAM_NAME=streams:frames
FRAME_CONSUMER_GROUP=group:uc4:anpr
ALERT_STREAM_NAME=streams:alerts

# Bounded Queue / Overload Control
MAX_FRAME_AGE_MS=150
STREAM_BATCH_SIZE=8

# Database (Isolated UC4 Database)
DATABASE_URL=postgresql://admin:adminpassword@innovision-db:5432/uc4_anpr
DATA_RETENTION_DAYS=30
```

---

## 4. Starting the Service

### Option A: In the Complete Platform Stack (Production)
When running alongside the Innovision Platform containers on the server:

```bash
docker compose up -d --build uc4_anpr
```

Check the worker logs:
```bash
docker logs -f innovision_uc4_anpr
```

### Option B: Local Standalone Development / Testing
To test UC4 independently with a local Redis and PostgreSQL instance:

```bash
docker compose --profile dev up -d
```

---

## 5. Verifying Operation

### 1. Health Probe Verification
Query the health endpoint from another terminal or browser:
```bash
curl http://localhost:8004/health
```
Expected response:
```json
{
  "status": "healthy",
  "service": "uc4-anpr",
  "uptime_seconds": 45,
  "telemetry": {
    "processed_frames": 1250,
    "dropped_stale_frames": 2,
    "alerts_emitted": 14
  },
  "dependencies": {
    "database": "connected",
    "redis": "connected"
  }
}
```

### 2. Live Dynamic Camera Reconfiguration
To update virtual LineZones or speed limits for a camera without restarting the container:
```bash
curl -X POST http://localhost:8004/api/v1/cameras/update \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "gate-camera-01",
    "name": "North Gate",
    "speed_limit_kmh": 30,
    "entry_line_normalized": {"x1": 0.0, "y1": 0.5, "x2": 1.0, "y2": 0.5}
  }'
```

---

## 6. Troubleshooting Common Issues

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| `[FAIL] Redis Connection` | `innovision-redis` container is not on the same Docker network | Ensure `innovision_network` exists: `docker network create innovision_network` |
| `[FAIL] Database Connection` | Target database `uc4_anpr` does not exist | Run `CREATE DATABASE uc4_anpr;` in PostgreSQL |
| High `dropped_stale_frames` | Ingestion is sending frames faster than GPU inference speed | Lower RTSP ingestion frame rate in platform ingestion worker to 15 FPS or switch `INFERENCE_MODE=shared_server` |
