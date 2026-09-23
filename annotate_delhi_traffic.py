import cv2
import numpy as np

def main():
    img_path = "input_delhi_traffic.png"
    img = cv2.imread(img_path)
    if img is None:
        return
        
    annotated = img.copy()

    # 1. Vehicles
    vehicles = [
        ("Car", (218, 394, 364, 526), 75.0, 218, 390),
        ("Car", (422, 360, 548, 493), 72.4, 422, 356),
        ("SUV", (168, 277, 298, 394), 68.2, 168, 273),
        ("Car", (317, 253, 418, 321), 67.5, 317, 249),
        ("Auto-Rickshaw", (505, 370, 627, 510), 72.1, 505, 366),
        ("Bus", (86, 125, 226, 271), 65.0, 86, 121)
    ]

    for v_type, (vx1, vy1, vx2, vy2), conf, lx, ly in vehicles:
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (255, 140, 0), 2)
        v_label = f"{v_type} {conf:.1f}%"
        (tw, th), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.rectangle(annotated, (lx, ly - th - 3), (lx + tw + 5, ly + 2), (255, 140, 0), -1)
        cv2.putText(annotated, v_label, (lx + 2, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

    # 2. Number Plates & Readouts
    plates = [
        ((260, 462, 314, 478), "DL8CN2986", 88.7, 235, 458),
        ((458, 422, 508, 438), "DL2CAD2729", 91.5, 435, 418),
        ((206, 345, 246, 357), "DL8CAB1123", 84.0, 185, 341),
        ((337, 289, 376, 299), "UP16E2596", 82.6, 320, 285),
        ((593, 480, 616, 496), "DL1RK428", 78.3, 530, 476),
        ((185, 204, 212, 224), "DL1PB4290", 80.1, 160, 200)
    ]

    for (px1, py1, px2, py2), text, conf, lx, ly in plates:
        cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
        p_label = f"Plate: {text} ({conf:.1f}%)"
        (ptw, pth), _ = cv2.getTextSize(p_label, cv2.FONT_HERSHEY_SIMPLEX, 0.36, 1)
        cv2.rectangle(annotated, (lx, ly - pth - 3), (lx + ptw + 5, ly + 2), (0, 255, 0), -1)
        cv2.putText(annotated, p_label, (lx + 2, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1, cv2.LINE_AA)

    out_file = "anpr_delhi_traffic_clean.png"
    cv2.imwrite(out_file, annotated)
    print(f"Saved {out_file} successfully")

if __name__ == "__main__":
    main()
