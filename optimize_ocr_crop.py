import os
import cv2
import re
import easyocr

def preprocess_and_test():
    img_path = "image.png"
    if not os.path.exists(img_path):
        print("Error: image.png not found.")
        return

    # Load image
    img = cv2.imread(img_path)
    
    # Crop the plate using our verified coordinates: [136, 185, 238, 215]
    # Crop height: 185 to 215, crop width: 136 to 238
    crop = img[185:216, 136:239]
    os.makedirs("downloads", exist_ok=True)
    cv2.imwrite("downloads/raw_crop.jpg", crop)
    
    # Initialize EasyOCR Reader
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    
    # Test 1: Raw Crop OCR
    print("\n--- Test 1: Raw Crop OCR ---")
    results = reader.readtext(crop)
    for bbox, text, prob in results:
        print(f"  Raw: '{text}' (Conf: {prob:.2f})")

    # Test 2: Resized 3x + Grayscale + Contrast Enhancement (CLAHE)
    print("\n--- Test 2: Upscaled (3x) + Grayscale + CLAHE ---")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    cv2.imwrite("downloads/enhanced_crop.jpg", enhanced)
    
    results_enhanced = reader.readtext(enhanced)
    for bbox, text, prob in results_enhanced:
        print(f"  Enhanced: '{text}' (Conf: {prob:.2f})")
        
    # Test 3: Resized 3x + Grayscale + Bilateral Filter (de-noising)
    print("\n--- Test 3: Upscaled (3x) + Bilateral Filter ---")
    gray_bi = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    resized_bi = cv2.resize(gray_bi, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    filtered = cv2.bilateralFilter(resized_bi, 9, 75, 75)
    cv2.imwrite("downloads/filtered_crop.jpg", filtered)
    
    results_filtered = reader.readtext(filtered)
    for bbox, text, prob in results_filtered:
        print(f"  Filtered: '{text}' (Conf: {prob:.2f})")

    # Test 4: Thresholding (Binary) on Resized Image
    print("\n--- Test 4: Thresholded (Otsu Binarization) ---")
    _, thresholded = cv2.threshold(resized_bi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite("downloads/thresholded_crop.jpg", thresholded)
    
    results_thresh = reader.readtext(thresholded)
    for bbox, text, prob in results_thresh:
        print(f"  Thresholded: '{text}' (Conf: {prob:.2f})")

if __name__ == "__main__":
    preprocess_and_test()
