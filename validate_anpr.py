import os
import cv2
import re
import xml.etree.ElementTree as ET
import numpy as np
from paddleocr import PaddleOCR
from utils import enhance_plate, clean_plate, correct_indian_plate, levenshtein_distance

def run_benchmark():
    print("=== Starting ANPR Benchmark on Consolidated Validation Dataset ===")

    reader = PaddleOCR(use_angle_cls=False, lang='en', show_log=False, enable_mkldnn=False)
    annos_dir = 'datasets/anpr_validation/annotations_ocr'
    imgs_dir = 'datasets/anpr_validation/images'

    xml_files = sorted([f for f in os.listdir(annos_dir) if f.endswith('.xml')])

    total_plates = 0
    exact_matches = 0
    char_accuracies = []
    results = []

    for xml_file in xml_files:
        tree = ET.parse(os.path.join(annos_dir, xml_file))
        root = tree.getroot()
        img_elem = root.find('filename')
        img_name = img_elem.text.strip() if img_elem is not None and img_elem.text else xml_file.replace('.xml', '.jpg')
        img_path = os.path.join(imgs_dir, img_name)
        
        if not os.path.exists(img_path):
            continue
            
        image = cv2.imread(img_path)
        if image is None:
            continue
            
        h_img, w_img = image.shape[:2]
        
        objects = root.findall('object')
        for obj in objects:
            bndbox = obj.find('bndbox')
            
            gt_text = None
            for attr in obj.findall('attributes/attribute'):
                name_elem = attr.find('name')
                if name_elem is not None and name_elem.text and 'number_plate_text' in name_elem.text:
                    val = attr.find('value')
                    if val is not None and val.text:
                        gt_text = val.text.strip()
                        break
                        
            if not gt_text:
                continue
                
            clean_gt = re.sub(r'[^A-Z0-9]', '', gt_text.upper())
            if len(clean_gt) < 4:
                continue
                
            if bndbox is not None:
                xmin = max(0, int(float(bndbox.find('xmin').text)))
                ymin = max(0, int(float(bndbox.find('ymin').text)))
                xmax = min(w_img, int(float(bndbox.find('xmax').text)))
                ymax = min(h_img, int(float(bndbox.find('ymax').text)))
                
                plate_crop = image[ymin:ymax, xmin:xmax]
                if plate_crop.size == 0 or (xmax - xmin) < 15 or (ymax - ymin) < 10:
                    continue
                    
                total_plates += 1
                
                enhanced = enhance_plate(plate_crop)
                ocr_out = reader.ocr(enhanced, cls=False)
                pred_raw = ''
                pred_conf = 0.0
                if ocr_out and ocr_out[0]:
                    pred_raw = ''.join([line[1][0] for line in ocr_out[0]])
                    pred_conf = float(np.mean([line[1][1] for line in ocr_out[0]]))
                    
                pred_cleaned = clean_plate(pred_raw) or ''
                pred_corrected = correct_indian_plate(pred_cleaned) or pred_cleaned
                
                dist = levenshtein_distance(clean_gt, pred_corrected)
                max_len = max(len(clean_gt), len(pred_corrected))
                char_acc = max(0.0, 1.0 - (dist / max_len)) if max_len > 0 else 1.0
                char_accuracies.append(char_acc)
                
                is_match = (clean_gt == pred_corrected)
                if is_match:
                    exact_matches += 1
                    
                results.append({
                    'img': img_name,
                    'gt': clean_gt,
                    'pred': pred_corrected,
                    'raw': pred_raw,
                    'conf': pred_conf,
                    'match': is_match,
                    'char_acc': char_acc
                })

    if total_plates > 0:
        mean_char_acc = float(np.mean(char_accuracies)) * 100
        exact_match_pct = (exact_matches / total_plates) * 100
        print(f"\n=== Validation Results on {total_plates} Ground-Truth Plates ===")
        print(f"Average Character Accuracy: {mean_char_acc:.2f}%")
        print(f"Exact Match Accuracy:       {exact_matches}/{total_plates} ({exact_match_pct:.1f}%)")
        print(f"Levenshtein Similarity:     {mean_char_acc/100:.3f}")

        print("\nSample Predictions vs Ground Truth:")
        for r in results[:20]:
            status = "✅ MATCH" if r['match'] else "⚠️ DIFF "
            gt = r['gt']
            pred = r['pred']
            c_acc = r['char_acc'] * 100
            conf = r['conf'] * 100
            print(f"  {status} | GT: {gt:12s} | Pred: {pred:12s} | CharAcc: {c_acc:5.1f}% | Conf: {conf:5.1f}%")
    else:
        print("No plates found matching criteria!")

if __name__ == "__main__":
    run_benchmark()
