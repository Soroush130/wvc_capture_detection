# detection/detection_utils.py
import os
import torch
from typing import List, Dict, Optional
from ultralytics import YOLO
from ultralytics.engine.results import Results
from logger_config import get_logger
from aws_s3.s3_download import download_from_s3
from aws_s3.s3_utils import upload_to_s3

logger = get_logger(__name__)

YOLO_MODEL_PATH = os.getenv('YOLO_MODEL_PATH', 'yolo_models/yolov8n.pt')
YOLO_DEVICE = os.getenv('YOLO_DEVICE', 'cpu')
YOLO_MIN_CONFIDENCE = float(os.getenv('YOLO_MIN_CONFIDENCE', 0.25))
YOLO_SYSTEM_CONFIDENCE = float(os.getenv('YOLO_SYSTEM_CONFIDENCE', 0.5))
SAVE_DETECTED_OBJECTS = os.getenv('SAVE_DETECTED_OBJECTS', 'True').lower() == 'true'


# ==================== GPU DETECTION ====================
def detect_gpu():
    """
    Detect available GPU and return device
    این تابع خودکار CPU یا GPU را تشخیص می‌دهد
    """
    if YOLO_DEVICE.lower() == 'cpu':
        logger.info("🖥️ YOLO_DEVICE set to CPU (forced)")
        return 'cpu'

    # Check CUDA availability
    if not torch.cuda.is_available():
        logger.warning("⚠️ CUDA not available, falling back to CPU")
        logger.warning(f"   PyTorch version: {torch.__version__}")
        logger.warning(f"   CUDA compiled: {torch.version.cuda}")
        return 'cpu'

    # Get GPU info
    gpu_count = torch.cuda.device_count()
    logger.info(f"🎮 Found {gpu_count} GPU(s)")

    for i in range(gpu_count):
        gpu_name = torch.cuda.get_device_name(i)
        gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024 ** 3
        logger.info(f"   GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")

    # Use specified device or first GPU
    if YOLO_DEVICE.lower() == 'cuda':
        device = 'cuda:0'
    elif YOLO_DEVICE.lower().startswith('cuda:'):
        device = YOLO_DEVICE.lower()
    else:
        device = 'cuda:0'

    logger.info(f"✅ Using device: {device}")
    return device

# ... بقیه کد (CLASS_CONFIG, get_yolo_model, detect_objects)
# همان کدی که قبلاً فرستادم