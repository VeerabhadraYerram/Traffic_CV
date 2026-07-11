import os
import cv2
import time
import base64
import torch
from ultralytics import YOLO

def check_cuda_working():
    if not torch.cuda.is_available():
        return False
    try:
        major, minor = torch.cuda.get_device_capability(0)
        if major >= 10:
            return False
        x = torch.rand(1, 1).cuda()
        _ = x @ x
        return True
    except Exception:
        return False

def extract_and_test():
    device_is_gpu = check_cuda_working()
    device = 'cuda' if device_is_gpu else 'cpu'
    
    video_path = os.path.join("downloads", "test_video.mp4")
    if not os.path.exists(video_path):
        print(f"Error: Video file {video_path} not found.")
        return
        
    print("Opening video file to extract a frame with a vehicle...")
    cap = cv2.VideoCapture(video_path)
    
    # Load vehicle detector
    model = YOLO("yolo11m.pt").to(device)
    
    # Load license plate detector
    lp_model_path = os.path.join("models", "yolov8n_license_plate.pt")
    lp_detector = YOLO(lp_model_path).to(device) if os.path.exists(lp_model_path) else None

    car_crop_path = os.path.join("downloads", "car_test.jpg")
    plate_crop_path = os.path.join("downloads", "plate_test.jpg")
    
    frame_found = False
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Detect vehicles (car/truck/motorcycle/bus)
        results = model(frame, classes=[1, 2, 3, 5, 7], verbose=False, device=device)
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # We found a vehicle! Crop it.
                crop_vehicle = frame[int(y1):int(y2), int(x1):int(x2)]
                if crop_vehicle.size > 0:
                    cv2.imwrite(car_crop_path, crop_vehicle)
                    print(f"Saved vehicle crop to {car_crop_path}")
                    
                    # Try to find the license plate within the crop
                    crop_plate = None
                    if lp_detector is not None:
                        lp_results = lp_detector(crop_vehicle, verbose=False, device=device)
                        for lp_box in lp_results[0].boxes:
                            lpx1, lpy1, lpx2, lpy2 = lp_box.xyxy[0].tolist()
                            crop_plate = crop_vehicle[int(lpy1):int(lpy2), int(lpx1):int(lpx2)]
                            break
                            
                    # Fallback crop bottom 60% of vehicle
                    if crop_plate is None or crop_plate.size == 0:
                        vh = y2 - y1
                        crop_plate = frame[int(y1 + 0.4 * vh):int(y2), int(x1):int(x2)]
                        
                    if crop_plate is not None and crop_plate.size > 0:
                        cv2.imwrite(plate_crop_path, crop_plate)
                        print(f"Saved license plate crop to {plate_crop_path}")
                        frame_found = True
                        break
            if frame_found:
                break
        if frame_found:
            break
            
    cap.release()
    
    if not frame_found:
        print("Could not find any vehicles in the video to test.")
        return

    # -------------------------------------------------------------
    # Now run inference using the PaddleOCR-VL-1.6-GGUF model
    # -------------------------------------------------------------
    vlm_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF.gguf")
    vlm_proj_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF-mmproj.gguf")
    
    if not os.path.exists(vlm_path) or not os.path.exists(vlm_proj_path):
        print("Error: PaddleOCR-VL GGUF model files not found.")
        return
        
    print("\n-------------------------------------------------------------")
    print("🤖 RUNNING PADDLEOCR-VL-1.6-GGUF TEST")
    print("-------------------------------------------------------------")
    
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Llava15ChatHandler
        
        print("Loading PaddleOCR-VL-1.6 model into memory (using CPU)...")
        chat_handler = Llava15ChatHandler(clip_model_path=vlm_proj_path)
        llm = Llama(
            model_path=vlm_path,
            chat_format="llava-1-5",
            chat_handler=chat_handler,
            n_ctx=2048,
            n_gpu_layers=0, # Force CPU to avoid Blackwell compatibility issue
            verbose=False
        )
        
        # Test 1: Inference on the License Plate Crop
        print("\n=== Test 1: License Plate Crop ===")
        with open(plate_crop_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        image_uri = f"data:image/jpeg;base64,{base64_image}"
        
        start_time = time.time()
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Recognize the text in this image. Output only the alphanumeric characters of the license plate."},
                        {"type": "image_url", "image_url": {"url": image_uri}}
                    ]
                }
            ]
        )
        duration = time.time() - start_time
        result_plate = response["choices"][0]["message"]["content"]
        print(f"Result: {result_plate.strip()}")
        print(f"Time Taken: {duration:.2f} seconds")
        
        # Test 2: Inference on the Full Vehicle Crop
        print("\n=== Test 2: Full Vehicle Crop ===")
        with open(car_crop_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        image_uri = f"data:image/jpeg;base64,{base64_image}"
        
        start_time = time.time()
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Recognize the text in this image. Output only the alphanumeric characters of the license plate."},
                        {"type": "image_url", "image_url": {"url": image_uri}}
                    ]
                }
            ]
        )
        duration = time.time() - start_time
        result_car = response["choices"][0]["message"]["content"]
        print(f"Result: {result_car.strip()}")
        print(f"Time Taken: {duration:.2f} seconds")
        print("-------------------------------------------------------------")
        
    except Exception as e:
        print(f"❌ VLM Inference Error: {e}")

if __name__ == "__main__":
    extract_and_test()
