import os
import sys
import base64

def run_vlm_inference(image_path):
    model_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF.gguf")
    mmproj_path = os.path.join("models", "PaddleOCR-VL-1.6-GGUF-mmproj.gguf")
    
    if not os.path.exists(model_path) or not os.path.exists(mmproj_path):
        print(f"Error: Model files not found. Run download_models.py first.")
        return
        
    try:
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Llava15ChatHandler
    except ImportError:
        print("llama-cpp-python is not installed. To run this script, please install it using:")
        print("  pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu")
        print("For GPU support, follow the llama-cpp-python compilation guide.")
        return
        
    print("Loading PaddleOCR-VL-1.6 GGUF model...")
    try:
        # Initialize chat handler for vision capabilities
        chat_handler = Llava15ChatHandler(clip_model_path=mmproj_path)
        
        # Load Llama model with chat handler
        llm = Llama(
            model_path=model_path,
            chat_format="llava-1-5",
            chat_handler=chat_handler,
            n_ctx=2048,
            n_gpu_layers=-1 # Use GPU if available
        )
        
        # Convert image to base64 data URI
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        image_uri = f"data:image/jpeg;base64,{base64_image}"
        
        print("Running PaddleOCR-VL-1.6 inference...")
        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Recognize the text in this image. Output only the license plate number."},
                        {"type": "image_url", "image_url": {"url": image_uri}}
                    ]
                }
            ]
        )
        
        result = response["choices"][0]["message"]["content"]
        print(f"\n--- VLM OCR Result ---")
        print(result)
        print(f"----------------------")
        return result
    except Exception as e:
        print(f"❌ Error during model execution: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_vlm.py <path_to_image>")
    else:
        run_vlm_inference(sys.argv[1])
