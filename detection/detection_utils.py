# detection/detection_utils.py
import os
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

CLASS_NAMES = {
    0: 'person',
    2: 'car',
    7: 'truck',
    16: 'dog',
    17: 'horse',
    18: 'sheep',
    19: 'cow',
    20: 'elephant',
    21: 'bear',
    22: 'zebra',
    23: 'giraffe',
}

ANIMAL_TO_DEER_MAP = {
    'dog': 'deer',
    'horse': 'deer',
    'sheep': 'deer',
    'cow': 'deer',
    'elephant': 'deer',
    'bear': 'deer',
    'zebra': 'deer',
    'giraffe': 'deer',
}

# Global model (load once)
_model = None


def get_yolo_model():
    global _model
    if _model is None:
        logger.info(f"🔄 Loading YOLO model: {YOLO_MODEL_PATH}")
        _model = YOLO(YOLO_MODEL_PATH)
        _model.to(YOLO_DEVICE)
        logger.info(f"✅ Model loaded on {YOLO_DEVICE}")
    return _model


def detect_objects(photo_id: int, s3_key: str) -> Optional[Dict]:
    local_path = None
    try:
        local_path = download_from_s3(s3_key)
        if not local_path:
            logger.error(f"❌ Failed to download photo {photo_id} from S3")
            return None

        model = get_yolo_model()

        # Detection
        logger.info(f"🔍 Detecting objects in photo {photo_id}")
        results: List[Results] = model.predict(
            local_path,
            device=YOLO_DEVICE,
            conf=YOLO_MIN_CONFIDENCE,
            verbose=False
        )

        if not results:
            logger.warning(f"⚠️ No results from YOLO for photo {photo_id}")
            return None

        result = results[0]

        counts = {
            'car_above': 0,
            'car_below': 0,
            'truck_above': 0,
            'truck_below': 0,
            'person_above': 0,
            'person_below': 0,
            'deer_above': 0,
            'deer_below': 0,
        }

        detected_objects = []

        for i, box in enumerate(result.boxes, 1):
            confidence = float(box.conf)
            class_id = int(box.cls)

            if class_id not in CLASS_NAMES:
                continue

            original_class_name = CLASS_NAMES[class_id]

            if original_class_name in ANIMAL_TO_DEER_MAP:
                class_name = ANIMAL_TO_DEER_MAP[original_class_name]
                logger.debug(f"🦌 Detected {original_class_name} → mapped to {class_name}")
            else:
                class_name = original_class_name

            x1, y1, x2, y2 = box.xyxy.squeeze().tolist()
            width = x2 - x1
            height = y2 - y1

            if confidence >= YOLO_SYSTEM_CONFIDENCE:
                counts[f'{class_name}_above'] += 1
                is_above = True
            else:
                counts[f'{class_name}_below'] += 1
                is_above = False

            object_s3_key = None
            if SAVE_DETECTED_OBJECTS:
                try:
                    crop_img = result.orig_img[int(y1):int(y2), int(x1):int(x2)]

                    import cv2
                    _, buffer = cv2.imencode('.jpg', crop_img)

                    object_s3_key = f"objects/{original_class_name}/{photo_id}_{i}.jpg"
                    success, _ = upload_to_s3(
                        file_data=buffer.tobytes(),
                        s3_key=object_s3_key,
                        content_type='image/jpeg'
                    )

                    if not success:
                        object_s3_key = None

                except Exception as e:
                    logger.warning(f"⚠️ Failed to save object crop: {e}")
                    object_s3_key = None

            detected_objects.append({
                'name': class_name,  # deer, car, truck, person
                'original_name': original_class_name,  # horse, dog, etc.
                'confidence': confidence,
                'x': x1,
                'y': y1,
                'width': width,
                'height': height,
                's3_key': object_s3_key,
                'is_above_system_confidence': is_above
            })

        if os.path.exists(local_path):
            os.remove(local_path)

        total_objects = len(detected_objects)
        if total_objects > 0:
            summary = []
            for key in ['car', 'truck', 'person', 'deer']:
                total = counts[f'{key}_above'] + counts[f'{key}_below']
                if total > 0:
                    summary.append(f"{key}={total}")
            logger.info(f"✅ Photo {photo_id}: {total_objects} objects ({', '.join(summary)})")
        else:
            logger.info(f"ℹ️ Photo {photo_id}: No objects detected")

        return {
            'photo_id': photo_id,
            'counts': counts,
            'detected_objects': detected_objects,
            'has_detected_objects': len(detected_objects) > 0
        }

    except Exception as e:
        logger.error(f"❌ Detection error for photo {photo_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove temp file: {e}")