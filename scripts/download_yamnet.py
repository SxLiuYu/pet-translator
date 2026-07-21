"""
scripts/download_yamnet.py
下载 YAMNet 模型到 models 目录
"""
import logging
import os
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pet_translator.scripts")

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/yamnet/yamnet.tflite/v1/intfloat/model.tflite"

def download_yamnet(model_path: str = "models/yamnet.tflite") -> str:
    """下载 YAMNet 模型到指定路径"""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    if os.path.exists(model_path):
        size = os.path.getsize(model_path)
        logger.info(f"模型已存在: {model_path} ({size} bytes)")
        return model_path
    
    logger.info(f"正在下载 YAMNet 模型到 {model_path}...")
    response = requests.get(MODEL_URL, stream=True, timeout=120)
    response.raise_for_status()
    
    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    
    with open(model_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(f"\r下载进度: {pct}%", end="", flush=True)
    
    print()
    size = os.path.getsize(model_path)
    logger.info(f"模型下载完成: {model_path} ({size} bytes)")
    return model_path


if __name__ == "__main__":
    download_yamnet()
