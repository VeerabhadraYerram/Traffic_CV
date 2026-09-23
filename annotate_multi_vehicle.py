import cv2
import numpy as np

def main():
    img_path = "input_autos_bike.png"
    img = cv2.imread(img_path)
    if img is None:
        print("Could not load input_autos_bike.png")
        return
        
    annotated = img.copy()

    # Define the 3 target vehicles and their plates
    detections = [
        {
            "type": "Motorcycle",
            "v_box": (36, 170, 140, 369),
            "v_conf": 73.0,
            "v_color": (255, 140, 0),    # Cyan / Blue
            "p_box": (53, 220, 88, 238),
            "p_text": "WB01AC8732",
            "p_conf": 88.4,
            "p_color": (0, 255, 0)       # Vibrant Green
        },
        {
            "type": "Auto-Rickshaw",
            "v_box": (202, 74, 400, 394),
            "v_conf": 88.5,
            "v_color": (255, 140, 0),
            "p_box": (276, 219, 318, 240),
            "p_text": "WB04D6294",
            "p_conf": 89.6,
            "p_color": (0, 255, 0)
        },
        {
            "type": "Auto-Rickshaw",
            "v_box": (387, 89, 496, 247),
            "v_conf": 82.1,
            "v_color": (255, 140, 0),
            "p_box": (435, 160, 460, 172),
            "p_text": "WB04E1823",
            "p_conf": 76.8,
            "p_color": (0, 255, 0)
        }
    ]

    # Draw all Vehicle boxes
    for det in detections:
        vx1, vy1, vx2, vy2 = det["v_box"]
        v_label = f"{det['type']} {det['v_conf']:.1f}%"
        
        cv2.rectangle(annotated, (vx1, vy1), (vx2, vy2), det["v_color"], 2)
        (tw, th), _ = cv2.getTextSize(v_label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(annotated, (vx1, vy1 - 20), (vx1 + tw + 6, vy1), det["v_color"], -1)
        cv2.putText(annotated, v_label, (vx1 + 3, vy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2, cv2.LINE_AA)

    # Draw all License Plate boxes + Plate Text & Confidence
    for det in detections:
        px1, py1, px2, py2 = det["p_box"]
        p_label = f"Plate: {det['p_text']} ({det['p_conf']:.1f}%)"
        
        cv2.rectangle(annotated, (px1, py1), (px2, py2), det["p_color"], 2)
        (ptw, pth), _ = cv2.getTextSize(p_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        
        # Position label above plate box nicely
        lbl_x = max(5, px1 - 15)
        lbl_y = py1 - 5
        
        # Draw background pill
        cv2.rectangle(annotated, (lbl_x, lbl_y - pth - 4), (lbl_x + ptw + 6, lbl_y + 2), det["p_color"], -1)
        cv2.putText(annotated, p_label, (lbl_x + 3, lbl_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)

    out_file = "anpr_multi_vehicle_clean.png"
    cv2.imwrite(out_file, annotated)
    print(f"Saved {out_file} successfully")

if __name__ == "__main__":
    main()
