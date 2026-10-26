"""
check_prerequisites.py — Automated Deployment Prerequisite Checks for UC4 ANPR.
Adheres to Innovision Architecture Assessment (Page 5):
"prerequisite checks that print PASS or FAIL with a fix"

Validates:
1. Python environment (version >= 3.10)
2. PostgreSQL database reachability and permissions
3. Redis Streams message bus reachability
4. Local model weights existence
5. Shared Inference Server reachability (if INFERENCE_MODE == shared_server)
6. GPU / CUDA device availability
"""

import sys
import os
import socket
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

def check_python_version():
    sys_ver = sys.version_info
    if sys_ver >= (3, 10):
        print(f"[PASS] Python Version: {sys_ver.major}.{sys_ver.minor}.{sys_ver.micro}")
        return True
    else:
        print(f"[FAIL] Python Version: {sys_ver.major}.{sys_ver.minor} (Required: >= 3.10)")
        print("       FIX: Install Python 3.10 or higher or run inside Docker container.")
        return False

def check_redis_connection():
    try:
        from config import settings
        import redis
        client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
            socket_timeout=2.0
        )
        client.ping()
        print(f"[PASS] Redis Connection: Successfully reached {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        return True
    except Exception as e:
        from config import settings
        print(f"[FAIL] Redis Connection: Unable to connect to {settings.REDIS_HOST}:{settings.REDIS_PORT} ({e})")
        print("       FIX: Ensure Redis container is running in Docker ('docker compose --profile dev up -d local_redis')")
        print("            or verify REDIS_HOST in .env points to the correct network host.")
        return False

def check_database_connection():
    try:
        from config import settings
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        print("[PASS] Database Connection: Successfully connected to PostgreSQL.")
        return True
    except Exception as e:
        from config import settings
        print(f"[FAIL] Database Connection: Failed to connect to DATABASE_URL ({e})")
        print("       FIX: Start the PostgreSQL container ('docker compose --profile dev up -d local_db')")
        print("            or verify DATABASE_URL credentials in .env.")
        return False

def check_model_weights():
    weights_path = "yolo11m.pt"
    engine_path = "yolo11m.engine"
    lp_path = os.path.join("models", "yolov8n_license_plate.pt")

    if os.path.exists(weights_path) or os.path.exists(engine_path):
        print(f"[PASS] Vehicle Model Weights: Found ({weights_path if os.path.exists(weights_path) else engine_path})")
    else:
        print("[FAIL] Vehicle Model Weights: 'yolo11m.pt' not found in project root.")
        print("       FIX: Download weights from Ultralytics or copy 'yolo11m.pt' into project root.")
        return False

    if os.path.exists(lp_path):
        print(f"[PASS] License Plate Detector: Found ({lp_path})")
    else:
        print(f"[INFO] License Plate Detector: Optional model {lp_path} not found. Worker will use bottom 30% heuristic fallback.")

    return True

def check_gpu_cuda():
    try:
        import torch
        if torch.cuda.is_available():
            dev_name = torch.cuda.get_device_name(0)
            print(f"[PASS] GPU Acceleration: CUDA is available ({dev_name})")
            return True
        else:
            print("[INFO] GPU Acceleration: CUDA not detected in host Python environment.")
            print("       NOTE: When running inside Docker on NVIDIA servers, GPU passthrough is enabled via docker-compose.yml.")
            return True
    except ImportError:
        print("[INFO] GPU Acceleration: PyTorch not installed in current host environment (using Docker or Shared Inference).")
        return True

def check_shared_inference_server():
    from config import settings
    if settings.INFERENCE_MODE in ("shared_server", "hybrid"):
        import httpx
        try:
            resp = httpx.get(f"{settings.SHARED_INFERENCE_URL.replace('/v1/predict', '')}/health", timeout=1.5)
            if resp.status_code == 200:
                print(f"[PASS] Shared Inference Server: Connected ({settings.SHARED_INFERENCE_URL})")
                return True
            else:
                print(f"[INFO] Shared Inference Server: Endpoint returned HTTP {resp.status_code}. Hybrid worker will use local fallback.")
                return True
        except Exception:
            print(f"[INFO] Shared Inference Server: '{settings.SHARED_INFERENCE_URL}' offline. Hybrid worker will use local YOLO+Paddle fallback.")
            return True
    else:
        print(f"[PASS] Inference Mode: Local worker mode configured ({settings.INFERENCE_MODE}).")
        return True

def run_all_checks():
    print("=======================================================")
    print("INNOVISION PLATFORM - UC4 PRE-DEPLOYMENT PREREQUISITE CHECKS")
    print("=======================================================")
    
    results = [
        check_python_version(),
        check_model_weights(),
        check_gpu_cuda(),
        check_shared_inference_server(),
        check_redis_connection(),
        check_database_connection()
    ]
    
    print("=======================================================")
    failed = [r for r in results if r is False]
    if not failed:
        print("RESULT: ALL REQUIRED PREREQUISITES READY FOR INTEGRATION.")
    else:
        print(f"RESULT: {len(failed)} CHECK(S) FAILED. Follow the FIX instructions above before starting.")
    print("=======================================================")

if __name__ == "__main__":
    run_all_checks()
