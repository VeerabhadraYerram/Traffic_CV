#!/usr/bin/env python3
"""
RTSP & Network Stream Benchmark and Diagnostic Utility

Tests RTSP, HTTP MJPEG, and video streams for:
- Connection establishment time
- Ingestion FPS (Received vs Nominal)
- Frame decoding latency (ms)
- Resolution & Aspect Ratio
- Stream stability & packet drops
"""

import os
import sys
import time
import argparse
import cv2
import numpy as np

# Force UTF-8 on Windows consoles to prevent UnicodeEncodeError
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def configure_opencv_ffmpeg():
    """Sets low-latency TCP flags for OpenCV FFmpeg capture."""
    opts = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;500000|reorder_queue_size;0|stimeout;5000000"
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = opts

def test_stream(source: str, duration_sec: int = 5, show_window: bool = False):
    print("=" * 60)
    print("🔍 RTSP / Mobile Stream Diagnostic & Benchmark Tool")
    print("=" * 60)
    print(f"Target Source: {source}")
    print(f"Test Duration: {duration_sec} seconds")
    print(f"TCP Transport & Low Delay: Forced ON\n")

    configure_opencv_ffmpeg()

    t_start = time.time()
    print("⏳ Connecting to stream source...")
    
    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG if hasattr(cv2, "CAP_FFMPEG") else cv2.CAP_ANY)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    connect_time = time.time() - t_start

    if not cap.isOpened():
        print(f"\n❌ FAILED TO CONNECT: Could not open stream at {source}")
        print("Troubleshooting tips:")
        print("  1. Verify the phone and this PC are connected to the SAME Wi-Fi network.")
        print("  2. Double-check the IP address and port in the mobile app.")
        print("  3. Check if your phone or PC firewall is blocking the port.")
        return False

    print(f"✅ Connected in {connect_time:.2f} seconds!\n")

    # Read first frame to verify dimensions
    t_read_start = time.time()
    ret, frame = cap.read()
    first_frame_latency = (time.time() - t_read_start) * 1000

    if not ret or frame is None:
        print("❌ FAILED TO READ: Connected, but received 0 valid video frames.")
        cap.release()
        return False

    h, w = frame.shape[:2]
    nominal_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    print(f"📊 Stream Properties:")
    print(f"   • Resolution       : {w} x {h} pixels")
    print(f"   • Aspect Ratio     : {w/h:.2f}:1")
    print(f"   • Nominal FPS      : {nominal_fps:.1f}")
    print(f"   • First Frame Lag  : {first_frame_latency:.1f} ms\n")

    print("🚀 Benchmarking live stream throughput...")

    frame_count = 1
    latencies = [first_frame_latency]
    bench_start = time.time()
    last_print = bench_start

    try:
        while True:
            now = time.time()
            if now - bench_start >= duration_sec:
                break

            t_read = time.time()
            ret, frame = cap.read()
            lat = (time.time() - t_read) * 1000

            if not ret or frame is None:
                print("⚠️ Frame drop / decode stall detected!")
                continue

            frame_count += 1
            latencies.append(lat)

            if show_window:
                cv2.putText(frame, f"FPS: {frame_count / (now - bench_start):.1f} | Res: {w}x{h}", 
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.imshow("Stream Test (Press Q to exit)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            if now - last_print >= 1.0:
                elapsed = now - bench_start
                current_fps = frame_count / elapsed
                avg_lat = np.mean(latencies[-30:]) if latencies else 0
                print(f"   ⏱️  [{elapsed:4.1f}s] Frames: {frame_count:4d} | Live FPS: {current_fps:5.1f} | Avg Decode Latency: {avg_lat:4.1f} ms")
                last_print = now

    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user.")
    finally:
        cap.release()
        if show_window:
            cv2.destroyAllWindows()

    total_elapsed = time.time() - bench_start
    actual_fps = frame_count / total_elapsed if total_elapsed > 0 else 0
    avg_latency = np.mean(latencies) if latencies else 0
    p95_latency = np.percentile(latencies, 95) if latencies else 0

    print("\n" + "=" * 60)
    print("📈 BENCHMARK RESULTS")
    print("=" * 60)
    print(f"• Total Frames Received : {frame_count}")
    print(f"• Total Duration        : {total_elapsed:.2f} s")
    print(f"• Realized Throughput   : {actual_fps:.2f} FPS")
    print(f"• Avg Frame Latency     : {avg_latency:.2f} ms")
    print(f"• 95th Percentile Lag   : {p95_latency:.2f} ms")

    # Quality Assessment
    if actual_fps >= 22:
        rating = "🟢 EXCELLENT (Full Speed - Ready for 30 FPS YOLO + ANPR Pipeline)"
    elif actual_fps >= 14:
        rating = "🟡 GOOD (Acceptable for access logging, slight network jitter)"
    else:
        rating = "🔴 POOR (Sub-optimal frame rate - check Wi-Fi bandwidth or mobile app resolution)"

    print(f"• Performance Rating    : {rating}")
    print("=" * 60 + "\n")
    return actual_fps >= 10

def main():
    parser = argparse.ArgumentParser(description="Benchmark RTSP / HTTP Stream for Traffic_CV")
    parser.add_argument("source", type=str, nargs="?", default="http://192.168.1.100:8080/video",
                        help="Stream URL (e.g. rtsp://192.168.1.105:8080/h264_pcm.sdp or http://192.168.1.105:8080/video)")
    parser.add_argument("--duration", "-d", type=int, default=5, help="Test duration in seconds (default: 5)")
    parser.add_argument("--preview", "-p", action="store_true", help="Display live video window during test")
    args = parser.parse_args()

    success = test_stream(args.source, args.duration, args.preview)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
