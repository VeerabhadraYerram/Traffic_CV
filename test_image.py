import os
import cv2
import re
import time
import torch
from ultralytics import YOLO
import easyocr

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

def preprocess_plate(crop_plate):
    if crop_plate is None or crop_plate.size == 0:
        return crop_plate
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(crop_plate, cv2.COLOR_BGR2GRAY)
        # Upscale 3x using cubic interpolation
        resized = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        # Apply CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(resized)
        return enhanced
    except Exception as e:
        print(f"Error preprocessing plate image: {e}")
        return crop_plate

def test_image_pipeline(image_path):
    if not os.path.exists(image_path):
        print(f"Error: Image {image_path} not found.")
        return

    device_is_gpu = check_cuda_working()
    device = 'cuda' if device_is_gpu else 'cpu'
    print(f"Device: {'GPU' if device_is_gpu else 'CPU'}")

    # Load models
    print("Loading models...")
    vehicle_model = YOLO("yolo11m.pt").to(device)
    
    lp_model_path = os.path.join("models", "yolov8n_license_plate.pt")
    lp_detector = YOLO(lp_model_path).to(device) if os.path.exists(lp_model_path) else None
    
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)

    print(f"Reading image: {image_path}")
    frame = cv2.imread(image_path)
    if frame is None:
        print("Error: Could not read image.")
        return

    # 1. Try Global License Plate Detection (Most robust for bumper-zoom cameras)
    crop_plate = None
    plate_bbox = None
    
    if lp_detector is not None:
        print("Running Global License Plate Detector...")
        lp_results = lp_detector(frame, verbose=False, device=device)
        for lp_box in lp_results[0].boxes:
            lpx1, lpy1, lpx2, lpy2 = lp_box.xyxy[0].tolist()
            crop_plate = frame[int(lpy1):int(lpy2), int(lpx1):int(lpx2)]
            plate_bbox = [int(lpx1), int(lpy1), int(lpx2), int(lpy2)]
            print(f"License plate detected globally at: {plate_bbox}")
            break

    # 2. Fallback to Vehicle Detection + Crop if global LPD failed
    if crop_plate is None or crop_plate.size == 0:
        print("Global license plate detector did not find any plates. Trying vehicle detection fallback...")
        results = vehicle_model(frame, classes=[1, 2, 3, 5, 7], verbose=False, device=device)
        
        crop_vehicle = frame
        vehicle_bbox = [0, 0, frame.shape[1], frame.shape[0]]
        vehicle_found = False
        
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                # Skip tiny background vehicle boxes
                if (x2 - x1) < 40 or (y2 - y1) < 40:
                    continue
                crop_vehicle = frame[int(y1):int(y2), int(x1):int(x2)]
                vehicle_bbox = [int(x1), int(y1), int(x2), int(y2)]
                vehicle_found = True
                break
                
        print(f"Vehicle fallback search: found={vehicle_found} (Coords: {vehicle_bbox})")
        
        # Crop the bottom 60% of the vehicle area
        vh = crop_vehicle.shape[0]
        crop_plate = crop_vehicle[int(0.4 * vh):, :]

    # 3. Perform OCR
    print("\n-------------------------------------------------------------")
    print("ANPR TEST RESULTS FOR: " + os.path.basename(image_path))
    print("-------------------------------------------------------------")

    if crop_plate is not None and crop_plate.size > 0:
        # Save plate crop for user view
        os.makedirs("downloads", exist_ok=True)
        cv2.imwrite(os.path.join("downloads", "plate_image.jpg"), crop_plate)
        print("Saved license plate crop to: downloads/plate_image.jpg")
        
        start = time.time()
        processed_plate = preprocess_plate(crop_plate)
        ocr_results = reader.readtext(processed_plate)
        duration = time.time() - start
        
        print("\n--- Optimized: Crop License Plate OCR ---")
        print(f"Time Taken: {duration * 1000:.2f} ms")
        print("Raw Readings:")
        for bbox, text, prob in ocr_results:
            print(f"  - '{text}' (Confidence: {prob:.2f})")
            
        cleaned_list = []
        for bbox, text, prob in ocr_results:
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if len(cleaned) >= 4:
                cleaned_list.append(cleaned)
        print(f"Consensus Plate: {' '.join(cleaned_list) if cleaned_list else 'No readable text'}")
    
    # Baseline for comparison
    start = time.time()
    raw_ocr = reader.readtext(frame)
    duration = time.time() - start
    print("\n--- Baseline: Full Image OCR ---")
    print(f"Time Taken: {duration * 1000:.2f} ms")
    print("Raw Readings:")
    for bbox, text, prob in raw_ocr:
        print(f"  - '{text}' (Confidence: {prob:.2f})")
        
    cleaned_raw = []
    for bbox, text, prob in raw_ocr:
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        if len(cleaned) >= 4:
            cleaned_raw.append(cleaned)
    print(f"Consensus Plate: {' '.join(cleaned_raw) if cleaned_raw else 'No readable text'}")
    print("-------------------------------------------------------------")

if __name__ == "__main__":
    test_image_pipeline("image.png")
