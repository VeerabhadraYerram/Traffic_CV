#!/usr/bin/env python3
"""
Mobile Stream Setup & Camera Source Manager

Features:
1. Discover local host LAN IP addresses.
2. Probe and validate RTSP/HTTP/MJPEG/Push streams before saving to DB.
3. Update camera source in database and signal the running AI pipeline.
4. Support both CLI arguments and interactive terminal wizard.
5. Dual mode: connects directly to database or through REST API (port 8002/8001).
"""

import os
import sys
import socket
import argparse
import time
import json
import urllib.request
import urllib.error

# Force UTF-8 on Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Camera

def get_local_ip():
    """Find the host machine's primary LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def probe_stream(url: str, timeout_sec: int = 3):
    """Quickly verify if a stream URL responds with valid video frames."""
    if url == "push":
        return True, "Mobile WebPush Buffer (browser-to-server)"

    import cv2
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000|stimeout;3000000"
    
    print(f"⏳ Testing connection to {url}...")
    cap = cv2.VideoCapture(url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    t0 = time.time()
    ret = False
    frame = None

    while time.time() - t0 < timeout_sec:
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            break
        time.sleep(0.05)

    cap.release()

    if ret and frame is not None:
        h, w = frame.shape[:2]
        return True, f"Success ({w}x{h} px)"
    else:
        return False, "Could not read frame within timeout"

def get_cameras_from_api():
    """Fetch camera list from local running web API as fallback."""
    for port in [8002, 8000]:
        try:
            url = f"http://localhost:{port}/api/cameras"
            req = urllib.request.Request(url, headers={'User-Agent': 'TrafficCV-CLI'})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode('utf-8'))
        except Exception:
            continue
    return []

def update_camera_via_api(camera_id: str, new_source: str):
    """Update camera source via REST API."""
    for port in [8002, 8001, 8000]:
        try:
            url = f"http://localhost:{port}/api/cameras/{camera_id}/source"
            data = json.dumps({"video_source": new_source, "url": new_source}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 201):
                    return True
        except Exception:
            continue
    return False

def update_camera_source(stream_url: str, camera_query: str = None, skip_probe: bool = False):
    local_ip = get_local_ip()
    print("=" * 65)
    print("📱 Mobile Stream Setup for Traffic_CV")
    print("=" * 65)
    print(f"Host Machine LAN IP : {local_ip}")
    print(f"Mobile WebPush URL   : http://{local_ip}:8002/phone\n")

    # Probe stream if not skipping and not push
    if stream_url != "push" and not skip_probe:
        ok, msg = probe_stream(stream_url, timeout_sec=4)
        if not ok:
            print(f"⚠️ Warning: Probe failed ({msg}).")
            choice = input("Do you still want to set this source anyway? (y/N): ").strip().lower()
            if choice != 'y':
                print("❌ Aborted. Source not changed.")
                return False
        else:
            print(f"✅ Stream Verified: {msg}\n")

    # Try Direct DB first
    try:
        db = SessionLocal()
        if camera_query:
            cam = db.query(Camera).filter(
                (Camera.name.ilike(f"%{camera_query}%")) | 
                (Camera.id == camera_query)
            ).first()
        else:
            cam = db.query(Camera).first()

        if cam:
            old_source = cam.video_source
            cam.video_source = stream_url
            if stream_url == "push":
                cam.name = f"Phone Web Camera ({cam.name.split('(')[0].strip()})"
            elif stream_url.startswith(("rtsp://", "http://", "https://")):
                cam.name = f"Mobile RTSP Feed ({cam.name.split('(')[0].strip()})"
            
            db.commit()
            cam_id = str(cam.id)
            cam_name = cam.name
            db.close()

            print(f"✅ Camera source updated successfully (Direct DB)!")
            print(f"• Camera Name : {cam_name}")
            print(f"• Camera ID   : {cam_id}")
            print(f"• Old Source  : {old_source}")
            print(f"• New Source  : {stream_url}\n")
            print("🔗 Ready! Next steps:")
            print(f"  1. Live AI Pipeline Stream: http://localhost:8001/api/stream/{cam_id}")
            print(f"  2. Web Configurator & UI : http://localhost:8002")
            print(f"  3. Mobile Web Stream     : http://{local_ip}:8002/phone")
            print("=" * 65)
            return True
        db.close()
    except Exception as db_err:
        pass

    # Fallback to REST API
    api_cams = get_cameras_from_api()
    if api_cams:
        target_cam = api_cams[0]
        if camera_query:
            for c in api_cams:
                if camera_query.lower() in c.get("name", "").lower() or camera_query == c.get("id"):
                    target_cam = c
                    break
        
        cam_id = target_cam["id"]
        if update_camera_via_api(cam_id, stream_url):
            print(f"✅ Camera source updated successfully via Web API!")
            print(f"• Camera Name : {target_cam.get('name')}")
            print(f"• Camera ID   : {cam_id}")
            print(f"• New Source  : {stream_url}\n")
            print("🔗 Ready! Next steps:")
            print(f"  1. Live AI Pipeline Stream: http://localhost:8001/api/stream/{cam_id}")
            print(f"  2. Web Configurator & UI : http://localhost:8002")
            print(f"  3. Mobile Web Stream     : http://{local_ip}:8002/phone")
            print("=" * 65)
            return True

    print("❌ Could not connect to database or running web server.")
    print("   Make sure the Docker containers or FastAPI servers are running.")
    return False

def interactive_wizard():
    local_ip = get_local_ip()
    print("=" * 65)
    print("📱 Mobile Stream Setup Assistant")
    print("=" * 65)
    print(f"Your Local IP Address: {local_ip}\n")

    # Get camera list
    cams = []
    try:
        db = SessionLocal()
        cams = [{"id": str(c.id), "name": c.name, "video_source": c.video_source} for c in db.query(Camera).filter(Camera.is_active == True).all()]
        db.close()
    except Exception:
        cams = get_cameras_from_api()

    if not cams:
        print("⚠️ Warning: No active cameras detected. Defaulting to camera #1.")
        cams = [{"id": "a0e0a0a0-0000-0000-0000-000000000001", "name": "Main Entrance", "video_source": "/app/downloads/test_video.mp4"}]

    print("Available Cameras:")
    for idx, c in enumerate(cams):
        print(f"  [{idx + 1}] {c.get('name')} (Current Source: {c.get('video_source')})")
    
    cam_choice = input(f"\nSelect Camera [1-{len(cams)}] (Default 1): ").strip()
    selected_idx = int(cam_choice) - 1 if cam_choice.isdigit() and 1 <= int(cam_choice) <= len(cams) else 0
    selected_cam = cams[selected_idx]

    print(f"\nSelected Camera: {selected_cam.get('name')}")
    print("\nChoose Streaming Mode:")
    print("  [1] Native Mobile RTSP Stream (IP Webcam / Larix / RTSP Camera)")
    print("  [2] HTTP MJPEG Stream (e.g. IP Webcam http://192.168.x.x:8080/video)")
    print("  [3] Mobile Web Browser Camera (Instant WebPush via /phone)")
    print("  [4] Restore Local Test Video (/app/downloads/test_video.mp4)")

    mode_choice = input("\nSelect Mode [1-4] (Default 1): ").strip() or "1"

    if mode_choice == "1":
        print("\nEnter the RTSP URL from your mobile app:")
        print("  Example: rtsp://192.168.1.105:8080/h264_pcm.sdp")
        print("  Example: rtsp://192.168.1.105:8554/live")
        url = input("RTSP URL: ").strip()
        if not url:
            print("❌ Invalid URL.")
            return
        update_camera_source(url, selected_cam.get("id"))

    elif mode_choice == "2":
        print("\nEnter the HTTP video URL from your mobile app:")
        print("  Example: http://192.168.1.105:8080/video")
        url = input("HTTP Video URL: ").strip()
        if not url:
            print("❌ Invalid URL.")
            return
        update_camera_source(url, selected_cam.get("id"))

    elif mode_choice == "3":
        print(f"\n📱 Open this URL in your phone's browser (Chrome/Safari):")
        print(f"   👉 http://{local_ip}:8002/phone")
        print("Tap 'Start Live Stream' on your phone, then press Enter to link it.")
        input("Press Enter to continue...")
        update_camera_source("push", selected_cam.get("id"), skip_probe=True)

    elif mode_choice == "4":
        update_camera_source("/app/downloads/test_video.mp4", selected_cam.get("id"), skip_probe=True)

def main():
    parser = argparse.ArgumentParser(description="Configure Mobile Stream for Traffic_CV")
    parser.add_argument("source", type=str, nargs="?", help="Stream URL (e.g. rtsp://192.168.1.105:8080/h264_pcm.sdp or 'push')")
    parser.add_argument("--camera", "-c", type=str, default=None, help="Camera name or ID (defaults to first camera)")
    parser.add_argument("--no-probe", action="store_true", help="Skip live connection probe before saving")
    args = parser.parse_args()

    if args.source:
        success = update_camera_source(args.source, args.camera, skip_probe=args.no_probe)
        sys.exit(0 if success else 1)
    else:
        interactive_wizard()

if __name__ == "__main__":
    main()
