import os
import cv2
import time
import re
import sys
from collections import Counter
import numpy as np
import torch
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort
import easyocr

def get_mode(items):
    if not items:
        return "UNKNOWN"
    return Counter(items).most_common(1)[0][0]

def check_cuda_working():
    if not torch.cuda.is_available():
        return False
    try:
        major, minor = torch.cuda.get_device_capability(0)
        if major >= 10:
            print(f"ℹ️ Detected Blackwell GPU with compute capability {major}.{minor}. Standard PyTorch stable wheels do not support sm_{major}{minor} yet. Falling back to CPU for stability.")
            return False
        x = torch.rand(1, 1).cuda()
        _ = x @ x
        return True
    except Exception:
        print("⚠️ CUDA is available, but compute kernels are not compatible with your GPU. Falling back to CPU.")
        return False

def preprocess_plate(crop_plate):
    if crop_plate is None or crop_plate.size == 0:
        return crop_plate
    try:
        import cv2
        gray = cv2.cvtColor(crop_plate, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(resized)
        return enhanced
    except Exception:
        return crop_plate

def run_comparative_benchmark(video_path, name, limit_frames=150):
    print(f"\n=============================================")
    print(f"🚀 Starting Comparative Benchmark on: {name}")
    print(f"=============================================")
    
    container_video_path = video_path.replace("/Users/shivaniyerram/Downloads", "/app/downloads")
    if not os.path.exists(container_video_path):
        # Check relative path
        container_video_path = os.path.abspath(video_path)
        if not os.path.exists(container_video_path):
            print(f"⚠️ Video not found: {video_path}")
            return

    device_is_gpu = check_cuda_working() or torch.backends.mps.is_available()
    print(f"Device: {'GPU' if device_is_gpu else 'CPU'}")
    
    # ------------------
    # Initialize Models
    # ------------------
    print("Loading vehicle detector (YOLO11m)...")
    vehicle_model = YOLO("yolo11m.pt")
    
    print("Loading EasyOCR Reader...")
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    
    # License Plate detector
    lp_model_path = os.path.join("models", "yolov8n_license_plate.pt")
    lp_detector = None
    if os.path.exists(lp_model_path):
        print("Loading local YOLOv8 License Plate Detector...")
        lp_detector = YOLO(lp_model_path)
    else:
        print("⚠️ YOLOv8 License Plate detector not found in models/ directory. Run download_models.py first.")
        print("Optimized pipeline will fall back to bottom-60% vehicle crop.")

    # VLM Model
    vlm_model = None
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Llava15ChatHandler
        import base64
        
        vlm_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF.gguf")
        vlm_proj_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF-mmproj.gguf")
        
        if os.path.exists(vlm_path) and os.path.exists(vlm_proj_path):
            print("Loading PaddleOCR-VL-1.6 GGUF Multimodal VLM...")
            chat_handler = Llava15ChatHandler(clip_model_path=vlm_proj_path)
            vlm_model = Llama(
                model_path=vlm_path,
                chat_format="llava-1-5",
                chat_handler=chat_handler,
                n_ctx=2048,
                n_gpu_layers=-1 if device_is_gpu else 0,
                verbose=False
            )
        else:
            print("⚠️ PaddleOCR-VL-1.6 GGUF model files not found. Skipping VLM benchmark.")
    except ImportError:
        print("ℹ️ llama-cpp-python not installed. Skipping VLM benchmark.")

    # ------------------
    # Pipelines setup
    # ------------------
    pipelines = {
        "baseline": {"desc": "YOLO + EasyOCR on Full Vehicle Crop", "active_sessions": {}},
        "optimized": {"desc": "YOLO + YOLO License Plate + EasyOCR (Two-Stage)", "active_sessions": {}}
    }
    if vlm_model is not None:
        pipelines["vlm"] = {"desc": "PaddleOCR-VL-1.6-GGUF VLM", "active_sessions": {}}

    for pipe_id, pipe in pipelines.items():
        pipe["tracker"] = DeepSort(max_age=150, n_init=2, nms_max_overlap=1.0, embedder_gpu=device_is_gpu)
        pipe["total_ocr_time"] = 0.0
        pipe["ocr_count"] = 0

    cap = cv2.VideoCapture(container_video_path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video Info: {width}x{height} | Total Frames: {total_frames} (Limit: {limit_frames})")

    frame_counter = 0
    start_time = time.time()
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret or frame_counter >= limit_frames:
            break
        frame_counter += 1

        # Run vehicle detection once per frame
        results = vehicle_model(frame, classes=[1, 2, 3, 5, 7], verbose=False, device='cuda' if device_is_gpu else 'cpu')
        bbs = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                bbs.append(([x1, y1, x2 - x1, y2 - y1], conf, cls_id))

        # Run each active pipeline
        for pipe_id, pipe in pipelines.items():
            tracks = pipe["tracker"].update_tracks(bbs, frame=frame)
            
            for track in tracks:
                if not track.is_confirmed():
                    continue
                tid = int(track.track_id)
                x1, y1, x2, y2 = track.to_ltrb()
                x1, y1 = max(0, int(x1)), max(0, int(y1))
                x2, y2 = min(width, int(x2)), min(height, int(y2))

                if tid not in pipe["active_sessions"]:
                    pipe["active_sessions"][tid] = {"plate_reads": []}

                # Only run OCR up to 10 times per tracked vehicle to avoid wasting compute
                if len(pipe["active_sessions"][tid]["plate_reads"]) < 10:
                    crop_vehicle = frame[y1:y2, x1:x2]
                    if crop_vehicle.size == 0:
                        continue

                    # 1. Baseline OCR Pipeline
                    if pipe_id == "baseline":
                        ocr_start = time.time()
                        ocr_results = reader.readtext(crop_vehicle)
                        pipe["total_ocr_time"] += (time.time() - ocr_start)
                        pipe["ocr_count"] += 1
                        
                        for _, text, prob in ocr_results:
                            if prob > 0.3:
                                cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                if 5 <= len(cleaned) <= 8:
                                    pipe["active_sessions"][tid]["plate_reads"].append(cleaned)

                    # 2. Two-Stage YOLO + EasyOCR Pipeline
                    elif pipe_id == "optimized":
                        ocr_start = time.time()
                        crop_plate = None
                        if lp_detector is not None:
                            lp_results = lp_detector(crop_vehicle, verbose=False, device='cuda' if device_is_gpu else 'cpu')
                            for lp_box in lp_results[0].boxes:
                                lpx1, lpy1, lpx2, lpy2 = lp_box.xyxy[0].tolist()
                                crop_plate = crop_vehicle[int(lpy1):int(lpy2), int(lpx1):int(lpx2)]
                                break
                        
                        # Fallback crop
                        if crop_plate is None or crop_plate.size == 0:
                            vh = y2 - y1
                            crop_plate = frame[int(y1 + 0.4 * vh):y2, x1:x2]

                        if crop_plate is not None and crop_plate.size > 0:
                            processed_plate = preprocess_plate(crop_plate)
                            ocr_results = reader.readtext(processed_plate)
                            pipe["total_ocr_time"] += (time.time() - ocr_start)
                            pipe["ocr_count"] += 1
                            
                            for _, text, prob in ocr_results:
                                if prob > 0.3:
                                    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                                    if 5 <= len(cleaned) <= 8:
                                        pipe["active_sessions"][tid]["plate_reads"].append(cleaned)

                    # 3. PaddleOCR-VL-1.6-GGUF VLM Pipeline
                    elif pipe_id == "vlm" and vlm_model is not None:
                        ocr_start = time.time()
                        
                        # Use license plate crop if available, else vehicle crop
                        crop_plate = None
                        if lp_detector is not None:
                            lp_results = lp_detector(crop_vehicle, verbose=False, device='cuda' if device_is_gpu else 'cpu')
                            for lp_box in lp_results[0].boxes:
                                lpx1, lpy1, lpx2, lpy2 = lp_box.xyxy[0].tolist()
                                crop_plate = crop_vehicle[int(lpy1):int(lpy2), int(lpx1):int(lpx2)]
                                break
                        if crop_plate is None or crop_plate.size == 0:
                            crop_plate = crop_vehicle

                        # Save crop to temporary file for llama-cpp-python
                        temp_img_path = f"temp_crop_{tid}.jpg"
                        cv2.imwrite(temp_img_path, crop_plate)
                        
                        try:
                            with open(temp_img_path, "rb") as image_file:
                                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                            image_uri = f"data:image/jpeg;base64,{base64_image}"
                            
                            response = vlm_model.create_chat_completion(
                                messages=[
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "Recognize the text in this image. Output only the license plate number."},
                                            {"type": "image_url", "image_url": {"url": image_uri}}
                                        ]
                                    }
                                ]
                            )
                            text = response["choices"][0]["message"]["content"]
                            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
                            pipe["active_sessions"][tid]["plate_reads"].append(cleaned)
                        except Exception as e:
                            print(f"VLM Error: {e}")
                        finally:
                            if os.path.exists(temp_img_path):
                                os.remove(temp_img_path)
                                
                        pipe["total_ocr_time"] += (time.time() - ocr_start)
                        pipe["ocr_count"] += 1

        if frame_counter % 20 == 0:
            print(f"Processed {frame_counter}/{limit_frames} frames...")

    cap.release()
    total_run_time = time.time() - start_time
    
    # ------------------
    # Print Results
    # ------------------
    print("\n=============================================")
    print("📊 BENCHMARK COMPARISON RESULTS")
    print("=============================================")
    print(f"Total Frames Processed: {frame_counter}")
    print(f"Overall Run Time: {total_run_time:.2f} seconds")
    print("---------------------------------------------")
    
    for pipe_id, pipe in pipelines.items():
        avg_ocr_time = (pipe["total_ocr_time"] / pipe["ocr_count"] * 1000) if pipe["ocr_count"] > 0 else 0
        overall_fps = frame_counter / total_run_time
        print(f"Pipeline: {pipe['desc']}")
        print(f"  - Unique Vehicles Tracked: {len(pipe['active_sessions'])}")
        print(f"  - Total OCR Inferences Run: {pipe['ocr_count']}")
        print(f"  - Avg OCR Inference Time: {avg_ocr_time:.2f} ms")
        
        print(f"  - Vehicle Detections & Consensus:")
        for tid, data in pipe["active_sessions"].items():
            consensus = get_mode(data["plate_reads"])
            print(f"    * Tracker ID {tid}: {consensus} (Reads: {len(data['plate_reads'])}, All: {data['plate_reads']})")
        print("---------------------------------------------")

if __name__ == "__main__":
    # Look for any test video in the downloads directory
    video_dir = "downloads"
    test_video = os.path.join(video_dir, "test_video.mp4")
    
    if not os.path.exists(test_video):
        print(f"Looking for any video files in {video_dir}...")
        videos = [f for f in os.listdir(video_dir) if f.endswith(('.mp4', '.avi', '.mov', '.mkv'))] if os.path.exists(video_dir) else []
        if videos:
            test_video = os.path.join(video_dir, videos[0])
        else:
            # Fallback to create a dummy video if none exists so compilation errors don't occur
            print(f"⚠️ No test video found in {video_dir}/. Creating a dummy black frames video for system testing...")
            os.makedirs(video_dir, exist_ok=True)
            test_video = os.path.join(video_dir, "test_video.mp4")
            out = cv2.VideoWriter(test_video, cv2.VideoWriter_fourcc(*'mp4v'), 30, (640, 480))
            for _ in range(90): # 3 seconds
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "TEST CAR 123", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                out.write(frame)
            out.release()
            
    run_comparative_benchmark(test_video, "ANPR Comparative Benchmark", limit_frames=100)
