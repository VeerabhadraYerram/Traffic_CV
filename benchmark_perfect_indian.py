import os
import cv2
import numpy as np
from paddleocr import PaddleOCR
from utils import enhance_plate, clean_plate, correct_indian_plate

def main():
    reader = PaddleOCR(use_angle_cls=False, lang='en', show_log=False, enable_mkldnn=False)
    test_dir = 'perfect_indian_license_plates/images/test'
    files = sorted(os.listdir(test_dir))

    print(f"Testing ANPR on {len(files)} Indian license plates in {test_dir}...\n")

    valid_format_count = 0
    high_conf_count = 0
    results = []

    for f in files:
        img_path = os.path.join(test_dir, f)
        img = cv2.imread(img_path)
        if img is None:
            continue
        
        # 1. Enhance plate
        enhanced = enhance_plate(img)
        
        # 2. OCR
        ocr_res = reader.ocr(enhanced, cls=False)
        raw_text = ''
        conf = 0.0
        if ocr_res and ocr_res[0]:
            lines = [l[1][0] for l in ocr_res[0]]
            confs = [l[1][1] for l in ocr_res[0]]
            raw_text = ' '.join(lines)
            conf = float(np.mean(confs))
            
        cleaned = clean_plate(raw_text)
        corrected = correct_indian_plate(cleaned) if cleaned else None
        
        if corrected:
            valid_format_count += 1
        if conf > 0.80:
            high_conf_count += 1
            
        results.append((f, raw_text, cleaned, corrected, conf))

    pct_valid = (valid_format_count / len(files)) * 100
    pct_high_conf = (high_conf_count / len(files)) * 100

    print(f"=== Benchmark Summary ===")
    print(f"Total Test Plates:           {len(files)}")
    print(f"Valid Indian Format Parsed:  {valid_format_count}/{len(files)} ({pct_valid:.1f}%)")
    print(f"High-Confidence Reads (>80%): {high_conf_count}/{len(files)} ({pct_high_conf:.1f}%)")
    print(f"Average Read Confidence:     {np.mean([r[4] for r in results])*100:.1f}%\n")

    print(f"{'Image':<10} | {'Raw OCR Output':<25} | {'Cleaned':<14} | {'Formatted Plate':<18} | {'Conf':<6}")
    print("-" * 85)
    for f, raw, cleaned, corr, conf in results:
        c_str = corr if corr else "---"
        cl_str = cleaned if cleaned else "---"
        print(f"{f:<10} | {raw[:25]:<25} | {cl_str:<14} | {c_str:<18} | {conf*100:5.1f}%")

if __name__ == "__main__":
    main()
