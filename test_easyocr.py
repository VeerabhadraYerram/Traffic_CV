import os
import cv2
import time
import re
import torch
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

def test_ocr():
    device_is_gpu = check_cuda_working()
    print(f"Device for EasyOCR: {'GPU' if device_is_gpu else 'CPU'}")
    
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    
    car_path = os.path.join("downloads", "car_test.jpg")
    plate_path = os.path.join("downloads", "plate_test.jpg")
    
    if not os.path.exists(car_path) or not os.path.exists(plate_path):
        print("Error: Test images not found. Run extract_car_frame.py first.")
        return
        
    print("\n-------------------------------------------------------------")
    print("RUNNING TWO-STAGE OCR TEST (EasyOCR)")
    print("-------------------------------------------------------------")
    
    # 1. OCR on the license plate crop (Optimized)
    print("Loading license plate crop...")
    img_plate = cv2.imread(plate_path)
    if img_plate is not None:
        start_time = time.time()
        results = reader.readtext(img_plate)
        duration = time.time() - start_time
        
        print("\n=== Optimized: License Plate Crop ===")
        print(f"Time Taken: {duration * 1000:.2f} ms")
        print("Raw Reads:")
        for bbox, text, prob in results:
            print(f"  - '{text}' (Confidence: {prob:.2f})")
            
        # Cleaned output
        cleaned_list = []
        for bbox, text, prob in results:
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if len(cleaned) >= 4:
                cleaned_list.append(cleaned)
        print(f"Consensus Plate: {' / '.join(cleaned_list) if cleaned_list else 'No readable text'}")
        
    # 2. OCR on the full vehicle crop (Baseline)
    print("\nLoading full vehicle crop...")
    img_car = cv2.imread(car_path)
    if img_car is not None:
        start_time = time.time()
        results = reader.readtext(img_car)
        duration = time.time() - start_time
        
        print("\n=== Baseline: Full Vehicle Crop ===")
        print(f"Time Taken: {duration * 1000:.2f} ms")
        print("Raw Reads:")
        for bbox, text, prob in results:
            print(f"  - '{text}' (Confidence: {prob:.2f})")
            
        cleaned_list = []
        for bbox, text, prob in results:
            cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
            if len(cleaned) >= 4:
                cleaned_list.append(cleaned)
        print(f"Consensus Plate: {' / '.join(cleaned_list) if cleaned_list else 'No readable text'}")
    print("-------------------------------------------------------------")

if __name__ == "__main__":
    test_ocr()
