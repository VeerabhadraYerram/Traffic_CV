import cv2
import numpy as np

def main():
    img_path = "input_foggy_highway.png"
    img = cv2.imread(img_path)
    if img is None:
        return
        
    annotated = img.copy()

    # 1. Vehicles
    vehicles = [
        ("Truck", (83, 204, 244, 382), 92.4, 83, 200),
        ("Auto-Rickshaw", (288, 270, 382, 377), 84.1, 288, 265),
        ("Car", (410, 276, 535, 368), 88.0, 435, 270),
        ("Truck", (633, 208, 794, 329), 85.3, 633, 202)
    ]

    for v_type, (vx1, vy1, vx2, vy2), conf, lx, ly in vehicles:
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (255, 140, 0), 2)
        v_label = f"{v_type} {conf:.1f}%"
        (tw, th), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(annotated, (lx, ly - th - 4), (lx + tw + 6, ly + 2), (255, 140, 0), -1)
        cv2.putText(annotated, v_label, (lx + 3, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

    # 2. Number Plates (No collisions)
    plates = [
        ((107, 327, 134, 344), "DL1LF5676", 89.2, 80, 320),
        ((360, 333, 376, 348), "DL1RF6921", 81.5, 270, 340),
        ((471, 321, 503, 332), "DL10CB1559", 94.6, 510, 328),
        ((741, 290, 770, 302), "HR38X2014", 83.0, 680, 285)
    ]

    for (px1, py1, px2, py2), text, conf, lx, ly in plates:
        cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
        p_label = f"Plate: {text} ({conf:.1f}%)"
        (ptw, pth), _ = cv2.getTextSize(p_label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        cv2.rectangle(annotated, (lx, ly - pth - 3), (lx + ptw + 5, ly + 2), (0, 255, 0), -1)
        cv2.putText(annotated, p_label, (lx + 2, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 0, 0), 1, cv2.LINE_AA)

    cv2.imwrite("anpr_foggy_highway_clean.png", annotated)
    print("Saved clean annotated image")

if __name__ == "__main__":
    main()
