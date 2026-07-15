import os
import time
import requests
from database import SessionLocal
from models import Camera

db = SessionLocal()
cam = db.query(Camera).filter(Camera.is_active == True).first()
if not cam:
    print("No active camera found")
    exit(1)

cam_id = cam.id
print(f"Testing stream for camera {cam_id}")

try:
    r = requests.get(f"http://127.0.0.1:8001/api/stream/{cam_id}", stream=True, timeout=10)
    start = time.time()
    for chunk in r.iter_content(chunk_size=1024):
        if time.time() - start > 10:
            print("Finished 10 seconds of stream.")
            break
except Exception as e:
    print(f"Error: {e}")
