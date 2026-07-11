import os
from huggingface_hub import hf_hub_download

def download_models():
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(models_dir, exist_ok=True)

    # 1. Download PaddleOCR-VL GGUF files
    print("Downloading PaddleOCR-VL-1.6 GGUF model...")
    hf_hub_download(
        repo_id="PaddlePaddle/PaddleOCR-VL-1.6-GGUF",
        filename="PaddleOCR-VL-1.6-GGUF.gguf",
        local_dir=models_dir
    )
    
    print("Downloading PaddleOCR-VL-1.6 mmproj file...")
    hf_hub_download(
        repo_id="PaddlePaddle/PaddleOCR-VL-1.6-GGUF",
        filename="PaddleOCR-VL-1.6-GGUF-mmproj.gguf",
        local_dir=models_dir
    )

    # 2. Download YOLOv8 license plate model
    print("Downloading YOLOv8 License Plate Detection model...")
    hf_hub_download(
        repo_id="Koushim/yolov8-license-plate-detection",
        filename="best.pt",
        local_dir=models_dir
    )
    
    # Rename for clarity if needed
    best_pt_path = os.path.join(models_dir, "best.pt")
    target_pt_path = os.path.join(models_dir, "yolov8n_license_plate.pt")
    if os.path.exists(best_pt_path):
        if os.path.exists(target_pt_path):
            os.remove(target_pt_path)
        os.rename(best_pt_path, target_pt_path)

    print("All models downloaded successfully in models/ directory!")

if __name__ == "__main__":
    download_models()
