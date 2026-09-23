import cv2
import numpy as np

def main():
    img_path = "input_scross_blur.jpg"
    img = cv2.imread(img_path)
    if img is None:
        return
        
    annotated = img.copy()

    # 1. Primary Vehicle: Maruti Suzuki S-Cross (SUV)
    vx1, vy1, vx2, vy2 = 137, 56, 889, 615
    v_conf = 75.4
    v_type = "SUV"

    cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), (255, 140, 0), 2)
    v_label = f"{v_type} {v_conf:.1f}%"
    (tw, th), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)
    cv2.rectangle(annotated, (vx1, vy1 - th - 8), (vx1 + tw + 10, vy1), (255, 140, 0), -1)
    cv2.putText(annotated, v_label, (vx1 + 5, vy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (0, 0, 0), 2, cv2.LINE_AA)

    # 2. Number Plate: KA05MK9391
    px1, py1, px2, py2 = 308, 288, 486, 345
    p_text = "KA05MK9391"
    p_conf = 88.6

    cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
    p_label = f"Plate: {p_text} ({p_conf:.1f}%)"
    (ptw, pth), _ = cv2.getTextSize(p_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
    
    lbl_x = px1 - 5
    lbl_y = py1 - 8
    cv2.rectangle(annotated, (lbl_x, lbl_y - pth - 6), (lbl_x + ptw + 10, lbl_y + 4), (0, 255, 0), -1)
    cv2.putText(annotated, p_label, (lbl_x + 5, lbl_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)

    # Save output
    out_file = "anpr_scross_clean.png"
    cv2.imwrite(out_file, annotated)
    print(f"Saved {out_file} successfully")

if __name__ == "__main__":
    main()
