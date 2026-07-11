import os
import cv2
import easyocr

def test_preprocessing():
    img_path = r"C:\Users\purus\.gemini\antigravity-ide\brain\1f472c77-e8d9-4483-be34-3a6a3c4acb0c\media__1783671843795.png"
    if not os.path.exists(img_path):
        print("Error: Image not found.")
        return
        
    img = cv2.imread(img_path)
    
    # Crop using plate coordinates: [343, 262, 428, 283]
    # Crop height: 262 to 283, crop width: 343 to 428
    crop = img[262:284, 343:429]
    cv2.imwrite("downloads/raw_user_crop.jpg", crop)
    
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    
    # Option 1: Raw crop
    print("--- Option 1: Raw Crop ---")
    print(reader.readtext(crop))
    
    # Option 2: 3x Gray CLAHE (Current)
    print("\n--- Option 2: 3x Gray + CLAHE (Current) ---")
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(resized)
    cv2.imwrite("downloads/enhanced_user_crop.jpg", enhanced)
    print(reader.readtext(enhanced))
    
    # Option 3: 4x Upscale + Bilateral Filter
    print("\n--- Option 3: 4x Upscale + Bilateral Filter ---")
    resized_4x = cv2.resize(gray, (0, 0), fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    filtered = cv2.bilateralFilter(resized_4x, 9, 75, 75)
    cv2.imwrite("downloads/filtered_user_crop.jpg", filtered)
    print(reader.readtext(filtered))
    
    # Option 4: 3x Upscale + Thresholding
    print("\n--- Option 4: 3x Upscale + Thresholding ---")
    _, thresholded = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    cv2.imwrite("downloads/threshold_user_crop.jpg", thresholded)
    print(reader.readtext(thresholded))

if __name__ == "__main__":
    test_preprocessing()
