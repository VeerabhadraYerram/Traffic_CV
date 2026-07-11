import os
import sys
import cv2
import re
import time
import torch
from ultralytics import YOLO
import easyocr

def check_cuda_working():
    """
    Checks if CUDA capability is fully compatible with standard PyTorch wheels.
    Particularly handles Blackwell GPUs (sm_120) by falling back to CPU for stability.
    """
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
    """
    Applies image preprocessing to improve OCR accuracy on low-resolution plate crops:
    1. Grayscale conversion.
    2. 3x cubic interpolation upscaling.
    3. CLAHE contrast enhancement.
    """
    if crop_plate is None or crop_plate.size == 0:
        return crop_plate
    
    # 1. Grayscale
    gray = cv2.cvtColor(crop_plate, cv2.COLOR_BGR2GRAY)
    
    # 2. Upscale (3x)
    resized = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # 3. Contrast limited adaptive histogram equalization (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    
    return enhanced

def run_anpr_pipeline(image_path):
    print("\n" + "="*60)
    print("STARTING ANPR PIPELINE RUN")
    print("="*60)
    
    # STEP 1: Verify Hardware Configuration
    print("\n[STEP 1] Checking hardware resources and CUDA compatibility...")
    device_is_gpu = check_cuda_working()
    device = 'cuda' if device_is_gpu else 'cpu'
    print(f" -> CUDA GPU Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        major, minor = torch.cuda.get_device_capability(0)
        print(f" -> GPU Model Details: {torch.cuda.get_device_name(0)} (Capability sm_{major}{minor})")
    print(f" -> Selected Execution Device: {device.upper()}")
    
    # STEP 2: Validate Input Image
    print("\n[STEP 2] Loading and validating input image...")
    if not os.path.exists(image_path):
        print(f"ERROR: Image file not found at path: {image_path}")
        return
        
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: OpenCV could not decode the image file at: {image_path}")
        return
        
    h, w, c = img.shape
    print(f" -> Image loaded successfully: {os.path.basename(image_path)}")
    print(f" -> Dimensions: {w}x{h} pixels (Channels: {c})")
    
    # STEP 3: Load Neural Network Models
    print("\n[STEP 3] Initializing deep learning models...")
    print(" -> Loading YOLO11m vehicle detection model...")
    vehicle_model = YOLO("yolo11m.pt").to(device)
    
    lp_model_path = os.path.join(os.path.dirname(__file__), "models", "yolov8n_license_plate.pt")
    lp_detector = None
    if os.path.exists(lp_model_path):
        print(" -> Loading YOLOv8 license plate localization model...")
        lp_detector = YOLO(lp_model_path).to(device)
    else:
        print("WARNING: License plate model file not found in models/. Will use vehicle boundary fallback.")
        
    print(" -> Initializing EasyOCR engine...")
    reader = easyocr.Reader(['en'], gpu=device_is_gpu, verbose=False)
    print(" -> All models successfully loaded into memory.")
    
    # STEP 4: Run License Plate Localization (LPD)
    print("\n[STEP 4] Scanning image for license plate regions...")
    crop_plate = None
    plate_bbox = None
    lpd_start = time.time()
    
    if lp_detector is not None:
        lp_results = lp_detector(img, verbose=False, device=device)
        for lp_box in lp_results[0].boxes:
            lpx1, lpy1, lpx2, lpy2 = lp_box.xyxy[0].tolist()
            plate_bbox = [int(lpx1), int(lpy1), int(lpx2), int(lpy2)]
            crop_plate = img[int(lpy1):int(lpy2), int(lpx1):int(lpx2)]
            print(f" -> SUCCESS: License plate found globally at coordinates: {plate_bbox}")
            break
            
    lpd_time = (time.time() - lpd_start) * 1000
    print(f" -> Plate localization stage took {lpd_time:.2f} ms")
    
    # STEP 5: Fallback to Vehicle-Based Localization (if global LPD failed)
    if crop_plate is None or crop_plate.size == 0:
        print("\n[STEP 5] License plate detector did not find any plate. Activating vehicle search fallback...")
        vehicle_results = vehicle_model(img, classes=[1, 2, 3, 5, 7], verbose=False, device=device)
        
        crop_vehicle = img
        vehicle_bbox = [0, 0, w, h]
        vehicle_found = False
        
        for r in vehicle_results:
            for box in r.boxes:
                vx1, vy1, vx2, vy2 = box.xyxy[0].tolist()
                # Filter out tiny background boxes
                if (vx2 - vx1) < 40 or (vy2 - vy1) < 40:
                    continue
                crop_vehicle = img[int(vy1):int(vy2), int(vx1):int(vx2)]
                vehicle_bbox = [int(vx1), int(vy1), int(vx2), int(vy2)]
                vehicle_found = True
                print(f" -> Vehicle detected at: {vehicle_bbox}")
                break
                
        if vehicle_found:
            print(" -> Vehicle found. Cropping bottom 60% of vehicle area as fallback license plate region...")
            vh = crop_vehicle.shape[0]
            crop_plate = crop_vehicle[int(0.4 * vh):, :]
        else:
            print(" -> No vehicle found. Defaulting fallback region to entire image.")
            crop_plate = img
    else:
        print("\n[STEP 5] Skipping vehicle search fallback (License plate already localized).")
        
    # STEP 6: Crop Preprocessing & Quality Enhancement
    print("\n[STEP 6] Preprocessing cropped license plate region for optimal text extraction...")
    ph, pw, _ = crop_plate.shape
    print(f" -> Raw crop size: {pw}x{ph} pixels")
    
    processed_plate = preprocess_plate(crop_plate)
    
    # Save the processed image for verification
    os.makedirs("downloads", exist_ok=True)
    debug_crop_path = os.path.join("downloads", "pipeline_crop_debug.jpg")
    cv2.imwrite(debug_crop_path, processed_plate)
    print(f" -> Saved processed crop image to: {debug_crop_path} (for verification)")
    
    # STEP 7: Optical Character Recognition (OCR)
    print("\n[STEP 7] Executing character recognition on preprocessed crop...")
    ocr_start = time.time()
    ocr_results = reader.readtext(processed_plate)
    ocr_time = (time.time() - ocr_start) * 1000
    
    print(f" -> Character recognition completed in {ocr_time:.2f} ms")
    print(" -> Raw OCR outputs:")
    for bbox, text, prob in ocr_results:
        print(f"    * Detected text: '{text}' (Confidence: {prob:.2f})")
        
    # STEP 8: Consensus Filtering & Normalization
    print("\n[STEP 8] Normalizing detected characters...")
    cleaned_list = []
    for bbox, text, prob in ocr_results:
        # Keep only capital letters and numbers
        cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
        if len(cleaned) >= 4:
            cleaned_list.append(cleaned)
            
    final_plate = " ".join(cleaned_list) if cleaned_list else "No readable plate text"
    
    # Save the annotated visual output
    if plate_bbox is not None:
        cv2.rectangle(img, (plate_bbox[0], plate_bbox[1]), (plate_bbox[2], plate_bbox[3]), (0, 255, 0), 2)
        cv2.putText(img, final_plate, (plate_bbox[0], plate_bbox[1] - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
    annotated_output_path = os.path.join("downloads", "annotated_output.jpg")
    cv2.imwrite(annotated_output_path, img)
    
    print("\n" + "="*60)
    print("ANPR PROCESSING COMPLETE")
    print("="*60)
    print(f"FINAL REGISTERED PLATE READING : {final_plate}")
    print(f"TOTAL EXECUTION DURATION        : {lpd_time + ocr_time:.2f} ms")
    print(f"ANNOTATED VISUAL OUTPUT SAVED AT: {annotated_output_path}")
    print("="*60)
    
if __name__ == "__main__":
    # Get image path from arguments or ask user
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        # If run interactively without args, check if image.png exists
        if os.path.exists("image.png"):
            img_path = "image.png"
        else:
            img_path = input("Enter the path to the image file: ").strip()
            
    run_anpr_pipeline(img_path)
